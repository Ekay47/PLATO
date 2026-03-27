import json
import os
import re
from dataclasses import dataclass
from typing import Any, Dict


def _default_assets_root() -> str:
    src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(src_dir, "lato")


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _find_first_codeblock_after(text: str, start_index: int) -> str:
    fence = "```"
    i = text.find(fence, start_index)
    if i < 0:
        return ""
    j = text.find(fence, i + len(fence))
    if j < 0:
        return ""
    content = text[i + len(fence) : j]
    content = re.sub(r"^\s*[a-zA-Z0-9_-]+\s*\n", "", content)
    return content.strip()


def _extract_section_codeblock(md: str, header_regex: str) -> str:
    m = re.search(header_regex, md, flags=re.IGNORECASE | re.MULTILINE)
    if not m:
        return ""
    return _find_first_codeblock_after(md, m.end())


@dataclass(frozen=True)
class LatoAssets:
    prompts_dir: str
    examples_md_path: str

    @staticmethod
    def from_env() -> "LatoAssets":
        root = _default_assets_root()
        prompts_dir = os.path.join(root, "prompts")
        examples_md = os.path.join(root, "examples_in_prompt.md")
        return LatoAssets(prompts_dir=prompts_dir, examples_md_path=examples_md)

    def load_prompt(self, name: str) -> Dict[str, Any]:
        path = os.path.join(self.prompts_dir, f"{name}.json")
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_examples(self, stage: str) -> str:
        md = _read_text(self.examples_md_path)
        stage_lower = stage.strip().lower()

        if stage_lower in {"identify", "identification"}:
            return _extract_section_codeblock(md, r"^###\s+Key Activity Identification\s*$")
        if stage_lower in {"decompose", "decomposition", "extract"}:
            return _extract_section_codeblock(md, r"^###\s+Layerwise Relation Extraction\s*$")
        if stage_lower in {"reconstruct", "integration"}:
            return _extract_section_codeblock(md, r"^###\s+Behaviroal Model Constructor\s*$")
        if stage_lower in {"generate", "regenerate"}:
            block = _extract_section_codeblock(md, r"^###\s+Behaviroal Model Constructor\s*$")
            if block:
                return block
            return _extract_section_codeblock(md, r"^##\s+Few-shot\s*$")
        if stage_lower in {"verify", "calibrate"}:
            return _extract_section_codeblock(md, r"^###\s+Layerwise Relation Extraction\s*$")

        return ""

