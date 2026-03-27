import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml


@dataclass(frozen=True)
class KBItem:
    file: str
    id: str
    diagram_type: str
    topic: str
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


def _collect_kb_items(kb_root: Path) -> List[KBItem]:
    items: List[KBItem] = []
    for p in sorted(kb_root.rglob("*.yaml")):
        if p.name == "_schema.yaml":
            continue
        obj = _read_yaml(p)
        diagram_type = _as_str(obj.get("diagram_type")).strip().lower()
        if not diagram_type:
            continue
        source = obj.get("source") if isinstance(obj.get("source"), dict) else {}
        page = _as_int(source.get("page") if isinstance(source, dict) else None)
        items.append(
            KBItem(
                file=str(p),
                id=_as_str(obj.get("id")) or "<missing-id>",
                diagram_type=diagram_type,
                topic=_as_str(obj.get("topic")),
                construct=_as_str(obj.get("construct")),
                title=_as_str(obj.get("title")),
                source_page=page,
            )
        )
    return items


def _load_constructs(cfg_path: Path) -> Dict[str, Any]:
    cfg = _read_yaml(cfg_path)
    if "constructs" not in cfg or not isinstance(cfg["constructs"], dict):
        raise ValueError("constructs.yaml missing 'constructs' mapping")
    return cfg


def _pdf_scan_pages(pdf_path: Path, queries: List[str]) -> Dict[str, List[int]]:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    pages_text: List[str] = [(p.extract_text() or "") for p in reader.pages]
    hits: Dict[str, List[int]] = {}
    for q in queries:
        rx = re.compile(re.escape(q), flags=re.IGNORECASE)
        hits[q] = [i + 1 for i, t in enumerate(pages_text) if rx.search(t)]
    return hits


def _unique_queries(cfg: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    constructs = cfg.get("constructs", {})
    for dt, arr in constructs.items():
        if not isinstance(arr, list):
            continue
        for row in arr:
            if not isinstance(row, dict):
                continue
            qs = row.get("queries")
            if isinstance(qs, list):
                for q in qs:
                    if isinstance(q, str) and q.strip():
                        out.append(q.strip())
    seen: Set[str] = set()
    uniq: List[str] = []
    for q in out:
        if q in seen:
            continue
        seen.add(q)
        uniq.append(q)
    return uniq


def _render_report(
    cfg: Dict[str, Any],
    kb_items: List[KBItem],
    *,
    pdf_hits: Optional[Dict[str, List[int]]] = None,
) -> str:
    by_dt: Dict[str, List[KBItem]] = {}
    for it in kb_items:
        by_dt.setdefault(it.diagram_type, []).append(it)

    lines: List[str] = []
    doc = cfg.get("doc") if isinstance(cfg.get("doc"), dict) else {}
    lines.append("# NL2Diagram Coverage Report")
    lines.append("")
    lines.append("## Doc")
    lines.append(f"- title: {doc.get('title') or ''}".rstrip())
    lines.append(f"- version: {doc.get('version') or ''}".rstrip())
    lines.append(f"- path: {doc.get('path') or ''}".rstrip())
    lines.append("")

    constructs = cfg.get("constructs", {})
    totals: Dict[str, Tuple[int, int]] = {}

    for dt in ["activity", "sequence", "state"]:
        expected = constructs.get(dt, [])
        if not isinstance(expected, list):
            expected = []
        lines.append(f"## {dt}")
        lines.append("")
        required_total = sum(1 for r in expected if isinstance(r, dict) and bool(r.get("required")))
        required_hit = 0

        present_constructs: Dict[str, List[KBItem]] = {}
        for it in by_dt.get(dt, []):
            if it.construct:
                present_constructs.setdefault(it.construct, []).append(it)

        for row in expected:
            if not isinstance(row, dict):
                continue
            c = _as_str(row.get("construct"))
            required = bool(row.get("required"))
            status = "MISSING"
            matched = present_constructs.get(c, [])
            if matched:
                status = "OK"
                if required:
                    required_hit += 1

            meta = []
            if required:
                meta.append("required")
            qs = row.get("queries") if isinstance(row.get("queries"), list) else []
            if qs and pdf_hits is not None:
                pages: Set[int] = set()
                for q in qs:
                    if isinstance(q, str):
                        for pno in pdf_hits.get(q.strip(), []):
                            pages.add(pno)
                if pages:
                    meta.append("pdf_pages=" + ",".join(map(str, sorted(pages)[:12])))

            lines.append(f"- {status} `{c}`" + (f" ({'; '.join(meta)})" if meta else ""))
            if matched:
                it = sorted(matched, key=lambda x: (x.source_page or 10**9, x.file))[0]
                src = f"p.{it.source_page}" if it.source_page else "p.?"
                lines.append(f"  - kb: {Path(it.file).as_posix()} ({src})")
        lines.append("")

        totals[dt] = (required_hit, required_total)

    lines.append("## Summary")
    lines.append("")
    for dt, (hit, total) in totals.items():
        pct = (hit / total * 100.0) if total else 0.0
        lines.append(f"- {dt}: required_coverage={hit}/{total} ({pct:.1f}%)")
    lines.append(f"- kb_files={len(kb_items)}")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--constructs", type=str, default=str(Path(__file__).resolve().parents[1] / "coverage" / "constructs.yaml"))
    ap.add_argument("--kb-root", type=str, default=str(Path(__file__).resolve().parents[1] / "kb" / "plantuml"))
    ap.add_argument("--out", type=str, default=str(Path(__file__).resolve().parents[1] / "coverage" / "coverage.md"))
    ap.add_argument("--pdf", type=str, default="")
    ap.add_argument("--pdf-scan", action="store_true")
    ap.add_argument("--json-out", type=str, default="")
    args = ap.parse_args(argv[1:])

    cfg_path = Path(args.constructs).resolve()
    kb_root = Path(args.kb_root).resolve()
    out_path = Path(args.out).resolve()

    cfg = _load_constructs(cfg_path)
    kb_items = _collect_kb_items(kb_root)

    pdf_hits: Optional[Dict[str, List[int]]] = None
    if args.pdf_scan:
        pdf_path = Path(args.pdf).resolve() if args.pdf else None
        if not pdf_path or not pdf_path.exists():
            print("pdf-scan enabled but --pdf is missing or not found", file=sys.stderr)
            return 2
        queries = _unique_queries(cfg)
        pdf_hits = _pdf_scan_pages(pdf_path, queries)

    report = _render_report(cfg, kb_items, pdf_hits=pdf_hits)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")

    if args.json_out:
        payload = {
            "constructs_file": str(cfg_path),
            "kb_root": str(kb_root),
            "kb_files": len(kb_items),
            "pdf_scanned": bool(pdf_hits is not None),
        }
        Path(args.json_out).resolve().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(str(out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

