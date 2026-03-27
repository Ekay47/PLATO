import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import yaml
from src.core.settings_loader import settings


@dataclass(frozen=True)
class KBConfig:
    root_dir: str
    max_chars: int
    top_k: int

    @staticmethod
    def from_env() -> "KBConfig":
        default_root = str(Path(__file__).resolve().parents[2] / "nl2diagram" / "kb" / "plantuml")
        return KBConfig(
            root_dir=(settings.get_str("plantuml.kb_root", "") or default_root).strip(),
            max_chars=int(settings.get_str("plantuml.kb_max_chars", "") or "6000"),
            top_k=int(settings.get_str("plantuml.kb_top_k", "") or "6"),
        )


@dataclass(frozen=True)
class KBDoc:
    id: str
    diagram_type: str
    topic: str
    title: str
    keywords: Tuple[str, ...]
    intent: Tuple[str, ...]
    rules: Tuple[str, ...]
    syntax: str
    examples: Tuple[str, ...]
    anti_examples: Tuple[str, ...]

    def score(self, query: str) -> int:
        q = (query or "").lower()
        if not q:
            return 0

        score = 0
        for kw in self.keywords:
            k = (kw or "").strip().lower()
            if not k:
                continue
            if " " in k:
                if k in q:
                    score += 6
            else:
                if re.search(rf"(?<![a-z0-9_]){re.escape(k)}(?![a-z0-9_])", q):
                    score += 4

        for it in self.intent:
            i = (it or "").strip().lower()
            if i and i in q:
                score += 2

        t = (self.topic or "").strip().lower().replace("_", " ")
        if t and t in q:
            score += 3

        return score


class PlantUMLKB:
    def __init__(self, *, cfg: Optional[KBConfig] = None) -> None:
        self.cfg = cfg or KBConfig.from_env()
        self._loaded = False
        self._docs: Dict[str, List[KBDoc]] = {"activity": [], "sequence": [], "state": []}

    def topics_from_structured(self, *, diagram_type: str, structured: str) -> List[str]:
        dt = (diagram_type or "").strip().lower()
        s = (structured or "").lower()
        topics: List[str] = []

        def add(*xs: str) -> None:
            for x in xs:
                v = (x or "").strip()
                if v and v not in topics:
                    topics.append(v)

        if dt == "activity":
            add("start_stop", "action_arrow")
            if "note" in s:
                add("note")
            if "partition" in s or "swimlane" in s:
                add("partition")
            if "fork" in s or "parallel" in s or "concurrent" in s:
                add("fork_join")
            if "repeat" in s:
                add("repeat_loop")
            if re.search(r"\bwhile\b", s):
                add("while_loop")
            if "elseif" in s or "else if" in s:
                add("elseif")
            elif re.search(r"\bif\b", s) or "endif" in s or re.search(r"\belse\b", s):
                add("if_else")
            if "merge" in s or "end merge" in s:
                add("end_merge")

        if dt == "sequence":
            if "participant" in s or "actor" in s:
                add("participants_messages")
            if "alt" in s or "opt" in s or "loop" in s:
                add("alt_opt_loop")
            if "note" in s:
                add("note")

        if dt == "state":
            if "[*]" in s or "initial" in s:
                add("basic_states_transitions")
            if "choice" in s:
                add("choice")
            if "fork" in s or "join" in s:
                add("fork_join")
            if "note" in s:
                add("note")

        return topics

    def query_from_structured(self, *, diagram_type: str, structured: str) -> str:
        dt = (diagram_type or "").strip().lower()
        s = (structured or "").lower()
        if not s:
            return dt

        tokens: List[str] = []
        tokens.append(dt)

        def add(*xs: str) -> None:
            for x in xs:
                v = (x or "").strip().lower()
                if v and v not in tokens:
                    tokens.append(v)

        if dt == "activity":
            if re.search(r"\bif\b", s):
                add("if")
            if re.search(r"\belse\b", s):
                add("else")
            if "endif" in s:
                add("endif")
            if "elseif" in s or "else if" in s:
                add("elseif")
            if "fork" in s or "parallel" in s or "concurrent" in s:
                add("fork", "fork again", "end fork", "parallel", "concurrency")
            if "end fork" in s:
                add("end fork")
            if "repeat" in s:
                add("repeat", "repeat while")
            if "while" in s:
                add("while")
            if "loop" in s:
                add("loop")
            if "partition" in s or "swimlane" in s:
                add("partition")
            if "note" in s:
                add("note")
            if "start" in s:
                add("start")
            if "stop" in s or "end" in s:
                add("stop")

        if dt == "sequence":
            if "alt" in s:
                add("alt", "end")
            if "opt" in s:
                add("opt", "end")
            if "loop" in s:
                add("loop", "end")
            if "par" in s:
                add("par", "end")
            if "participant" in s:
                add("participant")
            if "activate" in s or "deactivate" in s:
                add("activation")

        if dt == "state":
            if "[*]" in s:
                add("[*]")
            if "choice" in s:
                add("choice")
            if "state" in s:
                add("state")

        return " ".join(tokens[:60]).strip()

    def retrieve_coverage(self, *, diagram_type: str, structured: str) -> List[KBDoc]:
        self._load()
        dt = (diagram_type or "").strip().lower()
        docs = list(self._docs.get(dt, []))
        if not docs:
            return []

        wanted = set(self.topics_from_structured(diagram_type=dt, structured=structured))
        by_topic: Dict[str, KBDoc] = {}
        for d in docs:
            if d.topic in wanted and d.topic not in by_topic:
                by_topic[d.topic] = d

        ordered: List[KBDoc] = []
        for t in self.topics_from_structured(diagram_type=dt, structured=structured):
            d = by_topic.get(t)
            if d:
                ordered.append(d)

        if len(ordered) >= self.cfg.top_k:
            return ordered[: self.cfg.top_k]

        query = self.query_from_structured(diagram_type=dt, structured=structured)
        scored: List[Tuple[int, KBDoc]] = []
        for d in docs:
            if d in ordered:
                continue
            s = d.score(query)
            if s > 0:
                scored.append((s, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        for _, d in scored:
            ordered.append(d)
            if len(ordered) >= self.cfg.top_k:
                break

        return ordered

    def _load(self) -> None:
        if self._loaded:
            return
        root = Path(self.cfg.root_dir)
        if not root.exists():
            self._loaded = True
            return

        for path in root.rglob("*.yaml"):
            if path.name.startswith("_"):
                continue
            try:
                data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except Exception:
                continue

            diagram_type = str(data.get("diagram_type") or "").strip().lower()
            if diagram_type not in self._docs:
                continue

            doc = KBDoc(
                id=str(data.get("id") or path.stem).strip(),
                diagram_type=diagram_type,
                topic=str(data.get("topic") or path.stem).strip(),
                title=str(data.get("title") or path.stem).strip(),
                keywords=tuple(str(x).strip() for x in (data.get("keywords") or []) if str(x).strip()),
                intent=tuple(str(x).strip() for x in (data.get("intent") or []) if str(x).strip()),
                rules=tuple(str(x).strip() for x in (data.get("rules") or []) if str(x).strip()),
                syntax=str(data.get("syntax") or "").strip(),
                examples=tuple(str(x).strip() for x in (data.get("examples") or []) if str(x).strip()),
                anti_examples=tuple(str(x).strip() for x in (data.get("anti_examples") or []) if str(x).strip()),
            )

            if not doc.syntax:
                continue
            self._docs[diagram_type].append(doc)

        self._loaded = True

    def retrieve(self, *, diagram_type: str, query: str) -> List[KBDoc]:
        self._load()
        dt = (diagram_type or "").strip().lower()
        docs = list(self._docs.get(dt, []))

        scored: List[Tuple[int, KBDoc]] = []
        for d in docs:
            s = d.score(query)
            if s > 0:
                scored.append((s, d))

        scored.sort(key=lambda x: x[0], reverse=True)
        picked = [d for _, d in scored[: self.cfg.top_k]]
        if picked:
            return picked

        fallback = []
        for d in docs:
            if d.topic in {"start_stop", "action_arrow"}:
                fallback.append(d)
        return fallback[: min(2, len(fallback))]

    def format_for_prompt(self, *, diagram_type: str, query: str) -> str:
        docs = self.retrieve(diagram_type=diagram_type, query=query)
        if not docs:
            return ""

        parts: List[str] = []
        for d in docs:
            chunk: List[str] = []
            chunk.append(f"### {d.title} [{d.id}]")
            if d.rules:
                chunk.append("Rules:")
                chunk.extend([f"- {r}" for r in d.rules[:8]])
            chunk.append("Syntax:")
            chunk.append("```plantuml")
            chunk.append(d.syntax.strip())
            chunk.append("```")
            if d.anti_examples:
                chunk.append("Common mistakes:")
                chunk.extend([f"- {x}" for x in d.anti_examples[:6]])
            parts.append("\n".join(chunk))

        out = "\n\n".join(parts).strip()
        if len(out) <= self.cfg.max_chars:
            return out
        return out[: self.cfg.max_chars - 3] + "..."

    def format_for_prompt_from_structured(self, *, diagram_type: str, structured: str) -> str:
        docs = self.retrieve_coverage(diagram_type=diagram_type, structured=structured)
        if not docs:
            return ""
        parts: List[str] = []
        for d in docs:
            chunk: List[str] = []
            chunk.append(f"### {d.title} [{d.id}]")
            if d.rules:
                chunk.append("Rules:")
                chunk.extend([f"- {r}" for r in d.rules[:8]])
            chunk.append("Syntax:")
            chunk.append("```plantuml")
            chunk.append(d.syntax.strip())
            chunk.append("```")
            if d.anti_examples:
                chunk.append("Common mistakes:")
                chunk.extend([f"- {x}" for x in d.anti_examples[:6]])
            parts.append("\n".join(chunk))

        out = "\n\n".join(parts).strip()
        if len(out) <= self.cfg.max_chars:
            return out
        return out[: self.cfg.max_chars - 3] + "..."
