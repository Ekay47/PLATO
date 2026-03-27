import json
import logging
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional
from pydantic import BaseModel

from src.core.llm_client import LLMClient
from src.core.nlp_optional import NLPConfig, coref_info_for_prompt, dependency_tree_for_prompt

logger = logging.getLogger("plato.modeling")
ProgressEmitter = Callable[[str], Awaitable[None]]

class ModelingResult(BaseModel):
    activities: List[str]
    plantuml: str

class BehaviorModelGenerator:
    def __init__(self, *, llm: Any = None):
        prompts_path = Path(__file__).resolve().parents[1] / "prompts" / "modeling.json"
        self.prompts = json.loads(prompts_path.read_text(encoding="utf-8"))
        self.llm = llm or LLMClient()
        self.nlp_cfg = NLPConfig.from_env()

    def _render_prompt_user(self, template: str, mapping: Dict[str, str]) -> str:
        out = template
        for k, v in mapping.items():
            out = out.replace("{{" + k + "}}", v)
        return out

    async def _call_llm(self, system: str, user: str) -> str:
        t0 = time.perf_counter()
        try:
            out = await self.llm.chat(system, user, temperature=0.2)
            logger.info(
                "modeling.llm ok=1 model=%s api_url=%s sys_chars=%d user_chars=%d out_chars=%d ms=%d",
                getattr(self.llm, "model", None),
                getattr(self.llm, "api_url", None),
                len(system or ""),
                len(user or ""),
                len(out or ""),
                int((time.perf_counter() - t0) * 1000),
            )
            return out
        except Exception:
            logger.error(
                "modeling.llm ok=0 model=%s api_url=%s ms=%d",
                getattr(self.llm, "model", None),
                getattr(self.llm, "api_url", None),
                int((time.perf_counter() - t0) * 1000),
                exc_info=True,
            )
            raise

    def _strip_code_fences(self, content: str) -> str:
        content = content.strip()
        if "```" not in content:
            return content
        parts = content.split("```")
        if len(parts) < 2:
            return content
        candidate = parts[1].strip()
        if candidate.lower().startswith("plantuml"):
            candidate = candidate[len("plantuml"):].strip()
        if candidate.lower().startswith("json"):
            candidate = candidate[len("json"):].strip()
        return candidate.strip()

    def _parse_activities(self, content: str) -> List[str]:
        try:
            cleaned = self._strip_code_fences(content)
            activities = json.loads(cleaned)
        except Exception:
            activities = [line.strip() for line in content.split("\n") if line.strip()]
        return [str(x).strip() for x in activities if str(x).strip()]

    async def identify_activities(self, text: str, *, emit: Optional[ProgressEmitter] = None) -> List[str]:
        id_prompt = self.prompts["identification"]
        if emit:
            await emit("identify: calling LLM")
        coref_info = await coref_info_for_prompt(text, cfg=self.nlp_cfg)
        if emit:
            await emit(f"identify: coref={'enabled' if bool(coref_info) else 'disabled'}")

        extra = f"\n\nCoreference Hints:\n{coref_info}" if coref_info else ""
        id_user = id_prompt["user"].replace("{{text}}", text + extra)
        id_result_raw = await self._call_llm(id_prompt["system"], id_user)
        activities = self._parse_activities(id_result_raw)

        if coref_info:
            refine_user = (
                f"Requirement: {text}\n"
                f"Coreference Hints:\n{coref_info}\n"
                f"Initial Activities: {json.dumps(activities, ensure_ascii=False)}\n\n"
                "Refine the activities with coreference consistency and output only a JSON array of strings."
            )
            refined = await self._call_llm(id_prompt["system"], refine_user)
            parsed_refined = self._parse_activities(refined)
            if parsed_refined:
                activities = parsed_refined
        if emit:
            await emit(f"identify: activities={len(activities)}")
        return activities

    async def generate_plantuml(self, text: str, activities: List[str], diagram_type: str, integration: str = "") -> str:
        recon_prompt = self.prompts["reconstruction"]
        recon_system = recon_prompt["system"].replace("{{diagram_type}}", diagram_type.capitalize())
        recon_user = self._render_prompt_user(
            recon_prompt["user"],
            {
                "activities": json.dumps(activities, ensure_ascii=False),
                "integration": integration,
                "text": text,
                "diagram_type": diagram_type.capitalize(),
            },
        )
        plantuml = await self._call_llm(recon_system, recon_user)
        plantuml = self._strip_code_fences(plantuml)
        return plantuml

    async def decompose_structure(self, text: str, activities: List[str], diagram_type: str, *, emit: Optional[ProgressEmitter] = None) -> str:
        prompt = self.prompts.get("decomposition", self.prompts.get("identification"))
        if emit:
            enabled = self.nlp_cfg.dependency_provider == "corenlp" and bool(self.nlp_cfg.corenlp_url)
            await emit(f"nlp: dependency_tree={'enabled' if enabled else 'disabled'}")
            await emit("decompose: calling LLM")
        dependency = await dependency_tree_for_prompt(text, cfg=self.nlp_cfg)
        user = self._render_prompt_user(
            prompt["user"],
            {
                "text": text,
                "activities": json.dumps(activities, ensure_ascii=False),
                "diagram_type": diagram_type.capitalize(),
                "dependency": dependency,
            },
        )
        result = await self._call_llm(prompt["system"], user)
        return self._strip_code_fences(result)

    async def integrate_information(self, text: str, decomposition: str, diagram_type: str, activities: Optional[List[str]] = None) -> str:
        prompt = self.prompts.get("integration", self.prompts.get("decomposition", self.prompts.get("identification")))
        user = self._render_prompt_user(
            prompt["user"],
            {
                "text": text,
                "decomposition": decomposition,
                "activities": json.dumps(activities or [], ensure_ascii=False),
                "diagram_type": diagram_type.capitalize(),
            },
        )
        result = await self._call_llm(prompt["system"], user)
        return self._strip_code_fences(result)

    async def generate_model(self, text: str, diagram_type: str = "activity") -> Dict:
        activities = await self.identify_activities(text)
        decomposition = await self.decompose_structure(text, activities, diagram_type)
        integration = await self.integrate_information(text, decomposition, diagram_type, activities)
        plantuml = await self.generate_plantuml(text, activities, diagram_type, integration)
        return {
            "identification": activities,
            "decomposition": decomposition,
            "integration": integration,
            "plantuml": plantuml,
            "activities": activities
        }
