import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(BACKEND_ROOT / ".env")
except Exception:
    pass

from src.core.plantuml_validator import validate_with_jar


@dataclass(frozen=True)
class Finding:
    level: str
    file: str
    kb_id: str
    message: str


def _read_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        obj = yaml.safe_load(f)
    if not isinstance(obj, dict):
        raise ValueError("YAML root is not a mapping")
    return obj


def _require_fields(obj: Dict[str, Any], fields: List[str]) -> List[str]:
    missing: List[str] = []
    for k in fields:
        if k not in obj or obj.get(k) in (None, ""):
            missing.append(k)
    return missing


def _get_str(obj: Dict[str, Any], key: str) -> str:
    v = obj.get(key)
    return v if isinstance(v, str) else ""


def _tokens(code: str) -> List[str]:
    return [ln.strip() for ln in (code or "").splitlines() if ln.strip()]


def _count_kw(lines: List[str], pattern: str) -> int:
    rx = re.compile(pattern, flags=re.IGNORECASE)
    return sum(1 for ln in lines if rx.search(ln))


def _check_wrapping(lines: List[str]) -> List[str]:
    errs: List[str] = []
    all_text = "\n".join(lines).lower()
    if "@startuml" not in all_text:
        errs.append("Missing @startuml")
    if "@enduml" not in all_text:
        errs.append("Missing @enduml")
    return errs


def _check_activity(lines: List[str]) -> Tuple[List[str], List[str]]:
    errs: List[str] = []
    warns: List[str] = []
    txt = "\n".join(lines).lower()
    if "start" not in txt:
        warns.append("Activity: missing start node")
    if "stop" not in txt and "end" not in txt:
        warns.append("Activity: missing stop/end node")
    if_count = _count_kw(lines, r"^\s*if\s*\(")
    endif_count = _count_kw(lines, r"^\s*endif\b")
    if if_count != endif_count:
        errs.append(f"Activity: if/endif mismatch ({if_count}/{endif_count})")
    fork_start_count = _count_kw(lines, r"^\s*fork\b(?!\s+again\b)")
    fork_again_count = _count_kw(lines, r"^\s*fork\s+again\b")
    end_fork_count = _count_kw(lines, r"^\s*end\s+fork\b")
    end_merge_count = _count_kw(lines, r"^\s*end\s+merge\b")
    if fork_start_count or fork_again_count or end_fork_count or end_merge_count:
        if fork_start_count != 1:
            errs.append(f"Activity: expected exactly 1 fork start, got {fork_start_count}")
        end_count = end_fork_count + end_merge_count
        if end_count != 1:
            errs.append(f"Activity: expected exactly 1 fork end (end fork/end merge), got {end_count}")
    while_count = _count_kw(lines, r"^\s*while\s*\(")
    endwhile_count = _count_kw(lines, r"^\s*endwhile\b")
    if while_count != endwhile_count:
        errs.append(f"Activity: while/endwhile mismatch ({while_count}/{endwhile_count})")
    repeat_count = _count_kw(lines, r"^\s*repeat\b")
    repeat_while_count = _count_kw(lines, r"^\s*repeat\s+while\s*\(")
    if repeat_count and not repeat_while_count:
        warns.append("Activity: repeat without repeat while")
    return errs, warns


def _check_sequence(lines: List[str]) -> Tuple[List[str], List[str]]:
    errs: List[str] = []
    warns: List[str] = []
    start_like = _count_kw(lines, r"^\s*start\b")
    stop_like = _count_kw(lines, r"^\s*stop\b")
    if start_like or stop_like:
        warns.append("Sequence: contains start/stop-like tokens (usually not needed)")
    end_count = _count_kw(lines, r"^\s*end\b")
    end_ref_count = _count_kw(lines, r"^\s*end\s+ref\b")

    end_required = 0
    for kw in ["alt", "opt", "loop", "par", "critical", "group", "break"]:
        end_required += _count_kw(lines, rf"^\s*{kw}\b")

    ref_multiline = 0
    for ln in lines:
        if re.match(r"^\s*ref\b", ln, flags=re.IGNORECASE):
            if ":" in ln:
                continue
            ref_multiline += 1

    if end_required and end_count == 0:
        errs.append("Sequence: blocks present but no end")
    if end_required and end_count < end_required:
        warns.append(f"Sequence: end count ({end_count}) < blocks count ({end_required})")
    if ref_multiline and end_ref_count == 0:
        errs.append("Sequence: ref blocks present but no end ref")
    if ref_multiline and end_ref_count < ref_multiline:
        warns.append(f"Sequence: end ref count ({end_ref_count}) < ref blocks count ({ref_multiline})")
    return errs, warns


def _check_state(lines: List[str]) -> Tuple[List[str], List[str]]:
    errs: List[str] = []
    warns: List[str] = []
    txt = "\n".join(lines)
    if txt.count("{") != txt.count("}"):
        errs.append("State: brace mismatch")
    if "[*]" not in txt and "[*] " not in txt:
        warns.append("State: no [*] initial/final node found")
    return errs, warns


def _jar_check(code: str) -> Tuple[Optional[List[str]], List[str]]:
    jar_errors = validate_with_jar(code)
    if jar_errors is None:
        return None, ["Jar syntax check skipped (PLATO_PLANTUML_JAR not configured)"]
    if jar_errors:
        return jar_errors, []
    return [], []


def validate_file(path: Path) -> List[Finding]:
    obj = _read_yaml(path)
    kb_id = _get_str(obj, "id") or "<missing-id>"
    findings: List[Finding] = []

    missing = _require_fields(obj, ["id", "diagram_type", "topic", "title", "syntax", "keywords"])
    for k in missing:
        findings.append(Finding("ERROR", str(path), kb_id, f"Missing required field: {k}"))

    diagram_type = _get_str(obj, "diagram_type").strip().lower()
    syntax = _get_str(obj, "syntax")
    lines = _tokens(syntax)

    missing_meta = _require_fields(obj, ["construct", "complexity", "version"])
    for k in missing_meta:
        findings.append(Finding("ERROR", str(path), kb_id, f"Missing required metadata field: {k}"))

    if "requires_closure" not in obj:
        findings.append(Finding("WARN", str(path), kb_id, "Missing metadata field: requires_closure"))

    source = obj.get("source")
    if not isinstance(source, dict):
        findings.append(Finding("ERROR", str(path), kb_id, "Missing required field: source"))
    else:
        if not isinstance(source.get("doc"), str) or not str(source.get("doc")).strip():
            findings.append(Finding("ERROR", str(path), kb_id, "Missing source.doc"))
        if "page" not in source or source.get("page") in (None, ""):
            findings.append(Finding("ERROR", str(path), kb_id, "Missing source.page"))
        elif not isinstance(source.get("page"), int):
            findings.append(Finding("WARN", str(path), kb_id, "source.page should be integer"))

    keywords = obj.get("keywords")
    if keywords is not None and not isinstance(keywords, list):
        findings.append(Finding("ERROR", str(path), kb_id, "keywords must be a list"))

    for e in _check_wrapping(lines):
        findings.append(Finding("ERROR", str(path), kb_id, e))

    if diagram_type == "activity":
        errs, warns = _check_activity(lines)
    elif diagram_type == "sequence":
        errs, warns = _check_sequence(lines)
    elif diagram_type == "state":
        errs, warns = _check_state(lines)
    else:
        errs, warns = [f"Unknown diagram_type: {diagram_type}"], []

    for e in errs:
        findings.append(Finding("ERROR", str(path), kb_id, e))
    for w in warns:
        findings.append(Finding("WARN", str(path), kb_id, w))

    jar_errors, jar_warns = _jar_check(syntax)
    for w in jar_warns:
        findings.append(Finding("WARN", str(path), kb_id, w))
    if jar_errors is not None:
        for e in jar_errors:
            findings.append(Finding("ERROR", str(path), kb_id, f"Jar: {e}"))

    return findings


def main(argv: List[str]) -> int:
    root = Path(__file__).resolve().parents[1] / "kb" / "plantuml"
    targets = [Path(a).resolve() for a in argv[1:]] if len(argv) > 1 else [root]

    yaml_files: List[Path] = []
    for t in targets:
        if t.is_file() and t.suffix.lower() in (".yaml", ".yml") and t.name != "_schema.yaml":
            yaml_files.append(t)
        elif t.is_dir():
            yaml_files.extend([p for p in t.rglob("*.yaml") if p.name != "_schema.yaml"])
            yaml_files.extend([p for p in t.rglob("*.yml") if p.name != "_schema.yaml"])

    yaml_files = sorted({p.resolve() for p in yaml_files})
    if not yaml_files:
        print("No YAML files found")
        return 2

    all_findings: List[Finding] = []
    for p in yaml_files:
        try:
            all_findings.extend(validate_file(p))
        except Exception as e:
            all_findings.append(Finding("ERROR", str(p), "<unknown>", f"Failed to validate YAML: {e}"))

    errors = [f for f in all_findings if f.level == "ERROR"]
    warns = [f for f in all_findings if f.level == "WARN"]

    for f in (errors + warns):
        print(f"{f.level}\t{Path(f.file).as_posix()}\t{f.kb_id}\t{f.message}")

    print(f"\nSummary: files={len(yaml_files)} errors={len(errors)} warns={len(warns)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
