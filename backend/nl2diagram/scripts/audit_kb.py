import argparse
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml


BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from nl2diagram.scripts.coverage_report import _collect_kb_items, _load_constructs, _render_report
from nl2diagram.scripts.validate_kb import validate_file


@dataclass(frozen=True)
class KBRecord:
    file: str
    id: str
    diagram_type: str
    construct: str
    title: str
    source_page: Optional[int]


def _read_yaml(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        obj = yaml.safe_load(f)
    if not isinstance(obj, dict):
        raise ValueError("YAML root is not a mapping")
    return obj


def _as_str(v: Any) -> str:
    return v if isinstance(v, str) else ""


def _as_int(v: Any) -> Optional[int]:
    if isinstance(v, int):
        return v
    if isinstance(v, str) and v.strip().isdigit():
        return int(v.strip())
    return None


def _collect_records(kb_root: Path) -> List[KBRecord]:
    out: List[KBRecord] = []
    for p in sorted(kb_root.rglob("*.yaml")):
        if p.name == "_schema.yaml":
            continue
        obj = _read_yaml(p)
        source = obj.get("source") if isinstance(obj.get("source"), dict) else {}
        out.append(
            KBRecord(
                file=str(p),
                id=_as_str(obj.get("id")) or "<missing-id>",
                diagram_type=_as_str(obj.get("diagram_type")).lower(),
                construct=_as_str(obj.get("construct")),
                title=_as_str(obj.get("title")),
                source_page=_as_int(source.get("page") if isinstance(source, dict) else None),
            )
        )
    return out


def _pdf_page_count(pdf_path: Path) -> Optional[int]:
    try:
        from pypdf import PdfReader
    except Exception:
        return None
    try:
        reader = PdfReader(str(pdf_path))
        return len(reader.pages)
    except Exception:
        return None


def _duplicates(values: List[str]) -> List[Tuple[str, int]]:
    c = Counter(values)
    return sorted([(k, v) for k, v in c.items() if v > 1], key=lambda x: (-x[1], x[0]))


def _render_audit(
    *,
    constructs_cfg: Dict[str, Any],
    kb_root: Path,
    pdf_path: Optional[Path],
) -> str:
    lines: List[str] = []
    lines.append("# NL2Diagram KB Audit")
    lines.append("")

    doc = constructs_cfg.get("doc") if isinstance(constructs_cfg.get("doc"), dict) else {}
    lines.append("## Doc")
    lines.append(f"- title: {doc.get('title') or ''}".rstrip())
    lines.append(f"- version: {doc.get('version') or ''}".rstrip())
    lines.append(f"- path: {doc.get('path') or ''}".rstrip())
    if pdf_path:
        pc = _pdf_page_count(pdf_path)
        if pc is not None:
            lines.append(f"- page_count: {pc}")
    lines.append("")

    kb_items = _collect_kb_items(kb_root)
    records = _collect_records(kb_root)

    lines.append("## Stats")
    lines.append(f"- kb_files: {len(records)}")
    by_dt = Counter(r.diagram_type for r in records if r.diagram_type)
    for dt in ["activity", "sequence", "state"]:
        lines.append(f"- {dt}_files: {by_dt.get(dt, 0)}")
    lines.append(f"- unique_ids: {len(set(r.id for r in records))}")
    lines.append(f"- unique_constructs: {len(set(r.construct for r in records if r.construct))}")
    lines.append("")

    dup_ids = _duplicates([r.id for r in records])
    if dup_ids:
        lines.append("## Duplicates")
        for k, v in dup_ids[:50]:
            lines.append(f"- id duplicated ({v}): `{k}`")
        lines.append("")

    if pdf_path:
        page_count = _pdf_page_count(pdf_path)
    else:
        page_count = None
    bad_pages: List[str] = []
    if page_count is not None:
        for r in records:
            if r.source_page is None:
                continue
            if r.source_page < 1 or r.source_page > page_count:
                bad_pages.append(f"{Path(r.file).as_posix()}\t{r.id}\tp.{r.source_page}")
    if bad_pages:
        lines.append("## Source Page Issues")
        for row in bad_pages[:100]:
            lines.append(f"- {row}")
        lines.append("")

    lines.append("## Coverage")
    lines.append("")
    lines.append(_render_report(constructs_cfg, kb_items).rstrip())
    lines.append("")

    findings_by_level = Counter()
    findings_lines: List[str] = []
    for p in sorted(kb_root.rglob("*.yaml")):
        if p.name == "_schema.yaml":
            continue
        for f in validate_file(p):
            findings_by_level[f.level] += 1
            findings_lines.append(f"- {f.level}\t{Path(f.file).as_posix()}\t{f.kb_id}\t{f.message}")
    lines.append("## Validation Findings")
    lines.append(f"- errors: {findings_by_level.get('ERROR', 0)}")
    lines.append(f"- warns: {findings_by_level.get('WARN', 0)}")
    lines.append("")
    for ln in findings_lines[:300]:
        lines.append(ln)
    if len(findings_lines) > 300:
        lines.append(f"- ... truncated ({len(findings_lines) - 300} more)")
    lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--constructs", type=str, default=str(Path(__file__).resolve().parents[1] / "coverage" / "constructs.yaml"))
    ap.add_argument("--kb-root", type=str, default=str(Path(__file__).resolve().parents[1] / "kb" / "plantuml"))
    ap.add_argument("--pdf", type=str, default="")
    ap.add_argument("--out", type=str, default=str(Path(__file__).resolve().parents[1] / "coverage" / "audit.md"))
    args = ap.parse_args(argv[1:])

    cfg = _load_constructs(Path(args.constructs).resolve())
    kb_root = Path(args.kb_root).resolve()
    pdf_path = Path(args.pdf).resolve() if args.pdf else None

    report = _render_audit(constructs_cfg=cfg, kb_root=kb_root, pdf_path=pdf_path)
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

