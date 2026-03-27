import json
import re
from dataclasses import dataclass
from typing import Awaitable, Callable, List, Optional

from src.core.llm_client import LLMClient
from src.core.lato_assets import LatoAssets
from src.core.nlp_optional import NLPConfig, coref_info_for_prompt, dependency_tree_for_prompt
from src.core.plantuml_kb import PlantUMLKB
from src.core.plantuml_validator import validate_with_jar


def _strip_code_fences(content: str) -> str:
    c = (content or "").strip()
    if "```" not in c:
        return c
    parts = c.split("```")
    if len(parts) < 2:
        return c
    candidate = parts[1].strip()
    candidate = re.sub(r"^[a-zA-Z0-9_-]+\s*\n", "", candidate).strip()
    return candidate


def _ensure_wrapped_uml(code: str) -> str:
    c = (code or "").strip()
    if "@startuml" in c and "@enduml" in c:
        return c
    if c.lower().startswith("start"):
        return "@startuml\n" + c + "\n@enduml"
    return "@startuml\nstart\n" + c + "\nstop\n@enduml"


ProgressEmitter = Callable[[str], Awaitable[None]]


@dataclass
class LatoResult:
    activities: List[str]
    decomposition: str
    integration: str
    plantuml: str


class LATOWorkflow:
    def __init__(self, *, llm: Optional[LLMClient] = None, assets: Optional[LatoAssets] = None) -> None:
        self.llm = llm or LLMClient()
        self.assets = assets or LatoAssets.from_env()
        self.nlp_cfg = NLPConfig.from_env()
        self.kb = PlantUMLKB()

    async def identify(self, text: str, *, emit: Optional[ProgressEmitter] = None) -> List[str]:
        prompt = self.assets.load_prompt("identify")
        examples = self.assets.load_examples("identify")
        user = prompt["human"].format(Examples=examples, Input=text)
        if emit:
            await emit("identify: calling LLM")
        raw = await self.llm.chat(prompt["system"], user, temperature=0.2)
        cleaned = _strip_code_fences(raw)
        try:
            activities = json.loads(cleaned)
            if not isinstance(activities, list):
                raise ValueError("identify output is not a list")
            activities = [str(x).strip() for x in activities if str(x).strip()]
        except Exception:
            lines = [ln.strip(" \t-•") for ln in cleaned.splitlines() if ln.strip()]
            activities = [x for x in lines if x]

        if emit:
            await emit(f"identify: activities={len(activities)}")

        coref_info = await coref_info_for_prompt(text, cfg=self.nlp_cfg)
        if coref_info:
            calibrate_prompt = self.assets.load_prompt("calibrate")
            calibrate_examples = self.assets.load_examples("calibrate")
            max_rounds = 3 if len(text or "") < 200 else (6 if len(text or "") < 800 else 8)
            last_output = json.dumps(activities, ensure_ascii=False)
            prev_output = ""

            if emit:
                await emit("identify: coref=enabled")

            for _ in range(max_rounds):
                if last_output == prev_output:
                    break
                prev_output = last_output
                calibrate_user = calibrate_prompt["human"].format(
                    Examples=calibrate_examples,
                    Input=text,
                    Output=last_output,
                    CoreF=coref_info,
                )
                calibrated = _strip_code_fences(await self.llm.chat(calibrate_prompt["system"], calibrate_user, temperature=0.0)).strip()
                if "[ok]" in calibrated.lower():
                    break
                try:
                    arr = json.loads(calibrated)
                    if isinstance(arr, list):
                        activities = [str(x).strip() for x in arr if str(x).strip()]
                        last_output = json.dumps(activities, ensure_ascii=False)
                except Exception:
                    break

            if emit:
                await emit(f"identify: activities={len(activities)}")

        return activities

    async def decompose(
        self,
        text: str,
        *,
        activities: Optional[List[str]] = None,
        emit: Optional[ProgressEmitter] = None,
        max_level: int = 6,
        max_retry: int = 3,
    ) -> str:
        decompose_prompt = self.assets.load_prompt("decompose")
        verify_prompt = self.assets.load_prompt("verify")
        examples = self.assets.load_examples("decompose")
        depend_tree = await dependency_tree_for_prompt(text, cfg=self.nlp_cfg)
        if emit:
            enabled = self.nlp_cfg.dependency_provider == "corenlp" and bool(self.nlp_cfg.corenlp_url)
            await emit(f"nlp: dependency_tree={'enabled' if enabled else 'disabled'}")

        former_output = ""
        last_check = ""
        level = 1
        retry = 0

        while True:
            if level > max_level:
                return former_output + f"\n[Terminated: exceed max_level {max_level}]"

            if emit:
                await emit(f"decompose: level {level} (try {retry + 1}/{max_retry})")

            decompose_user = decompose_prompt["human"].format(
                Examples=examples,
                Input=(text.strip() + (("\n\n#Activity Identification\n" + ", ".join(activities)) if activities else "")),
                FormerOutput=former_output + last_check,
                Level=level,
            )
            execution = _strip_code_fences(await self.llm.chat(decompose_prompt["system"], decompose_user, temperature=0.3))

            verify_user = verify_prompt["human"].format(
                Examples=examples,
                Input=text,
                FormerOutput=former_output,
                Output=execution,
                Depend=depend_tree,
            )
            verification = _strip_code_fences(await self.llm.chat(verify_prompt["system"], verify_user, temperature=0.0))

            if "[valid]" in verification.lower():
                if emit:
                    await emit("verify: Valid")
                former_output += execution.strip() + "\n"
                last_check = ""
                level += 1
                retry = 0

                v = verification.lower()
                if "[valid][done]" in v:
                    return former_output.strip()
                if "[valid][more]" in v:
                    continue
                if "[" not in execution and "]" not in execution:
                    return former_output.strip()
                continue

            retry += 1
            last_check = "\n" + verification.strip()
            if emit:
                await emit(f"verify: retry {retry}/{max_retry}")
            if retry >= max_retry:
                return (former_output + f"\n[Terminated at level {level} after {max_retry} retries. Last check: {verification}]").strip()

    async def reconstruct(
        self,
        text: str,
        *,
        activities: List[str],
        decomposition: str,
        emit: Optional[ProgressEmitter] = None,
    ) -> str:
        prompt = self.assets.load_prompt("reconstruct")
        examples = self.assets.load_examples("reconstruct")
        stitched = (
            text.strip()
            + "\n\n#Activity Identification\n"
            + ", ".join(activities)
            + "\n\n#Relation Decomposition\n"
            + decomposition.strip()
            + "\n"
        )
        user = prompt["human"].format(Examples=examples, Input=stitched)
        if emit:
            await emit("reconstruct: calling LLM")
        out = await self.llm.chat(prompt["system"], user, temperature=0.2)
        integration = _strip_code_fences(out).strip()
        if emit:
            await emit("reconstruct: completed")
        return integration

    async def generate(
        self,
        text: str,
        *,
        integration: str,
        emit: Optional[ProgressEmitter] = None,
        max_repair: int = 2,
    ) -> str:
        generate_prompt = self.assets.load_prompt("generate_rag")
        regenerate_prompt = self.assets.load_prompt("regenerate")
        examples = self.assets.load_examples("generate")

        requirements = (text or "").strip()
        structured = (integration or "").strip()
        knowledge = self.kb.format_for_prompt_from_structured(diagram_type="activity", structured=structured)
        if emit:
            await emit(f"generate: rag_chunks={len(knowledge.split('###')) - 1 if knowledge else 0}")

        user = generate_prompt["human"].format(
            Examples=examples,
            Requirements=requirements,
            Structured=structured,
            Knowledge=knowledge or "(none)",
        )
        if emit:
            await emit("generate: calling LLM")
        plantuml = _strip_code_fences(await self.llm.chat(generate_prompt["system"], user, temperature=0.2)).strip()

        plantuml = self._normalize_plantuml(plantuml)
        if emit:
            await emit(f"generate: plantuml_lines={len((plantuml or '').splitlines())}")
        for attempt in range(max_repair):
            errors = self._validate_plantuml(plantuml)
            if not errors:
                return plantuml
            if emit:
                await emit(f"generate: repairing ({attempt + 1}/{max_repair})")
            repair_user = regenerate_prompt["human"].format(
                Examples=examples,
                Input=structured,
                Knowledge=knowledge or "(none)",
                uml_code=plantuml,
                errors="\n".join(errors)[:1200],
            )
            plantuml = _strip_code_fences(await self.llm.chat(regenerate_prompt["system"], repair_user, temperature=0.2)).strip()
            plantuml = self._normalize_plantuml(plantuml)
            if emit:
                await emit(f"generate: plantuml_lines={len((plantuml or '').splitlines())}")

        return plantuml

    async def run(self, text: str, *, emit: Optional[ProgressEmitter] = None) -> LatoResult:
        activities = await self.identify(text, emit=emit)
        decomposition = await self.decompose(text, activities=activities, emit=emit)
        integration = await self.reconstruct(text, activities=activities, decomposition=decomposition, emit=emit)
        plantuml = await self.generate(text, integration=integration, emit=emit)
        return LatoResult(activities=activities, decomposition=decomposition, integration=integration, plantuml=plantuml)

    def _normalize_plantuml(self, code: str) -> str:
        c = _strip_code_fences(code)
        c = _ensure_wrapped_uml(c)
        return c.strip()

    def _validate_plantuml(self, code: str) -> List[str]:
        errors: List[str] = []
        c = (code or "").strip()
        if "@startuml" not in c:
            errors.append("Missing @startuml")
        if "@enduml" not in c:
            errors.append("Missing @enduml")
        if "start" not in c.lower():
            errors.append("Missing start node")
        if "stop" not in c.lower() and "end" not in c.lower():
            errors.append("Missing stop/end node")
        jar_errors = validate_with_jar(c)
        if jar_errors is not None:
            errors.extend([f"Jar: {e}" for e in jar_errors if e])
        return errors

