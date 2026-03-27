import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple


def _load_pages(pdf_path: Path) -> List[str]:
    try:
        from pypdf import PdfReader
    except Exception as e:
        raise RuntimeError(f"Missing dependency pypdf: {e}")

    reader = PdfReader(str(pdf_path))
    pages: List[str] = []
    for p in reader.pages:
        t = p.extract_text() or ""
        pages.append(t)
    return pages


def _find_hits(pages: List[str], queries: List[Tuple[str, re.Pattern]]) -> Dict[str, List[int]]:
    hits: Dict[str, List[int]] = {q: [] for q, _ in queries}
    for i, text in enumerate(pages):
        for q, rx in queries:
            if rx.search(text or ""):
                hits[q].append(i + 1)
    return hits


def _extract_context(text: str, rx: re.Pattern, *, max_lines: int) -> List[str]:
    lines = (text or "").splitlines()
    out: List[str] = []
    for idx, ln in enumerate(lines):
        if rx.search(ln):
            lo = max(0, idx - max_lines)
            hi = min(len(lines), idx + max_lines + 1)
            chunk = lines[lo:hi]
            out.extend(chunk)
            out.append("----")
            if len(out) > 400:
                break
    return [x.rstrip() for x in out if x.strip()]


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", type=str)
    ap.add_argument("--query", action="append", default=[])
    ap.add_argument("--regex", action="store_true")
    ap.add_argument("--context", type=int, default=0)
    ap.add_argument("--max-lines", type=int, default=3)
    ap.add_argument("--page", action="append", type=int, default=[])
    ap.add_argument("--out", type=str, default="")
    args = ap.parse_args(argv[1:])

    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}", file=sys.stderr)
        return 2

    queries_raw: List[str] = args.query or []
    if not queries_raw:
        queries_raw = ["Activity Diagram", "Sequence Diagram", "State Diagram", "fork", "end fork", "activate", "entry", "while", "endif", "alt", "opt", "loop"]

    queries: List[Tuple[str, re.Pattern]] = []
    for q in queries_raw:
        if args.regex:
            queries.append((q, re.compile(q, flags=re.IGNORECASE)))
        else:
            queries.append((q, re.compile(re.escape(q), flags=re.IGNORECASE)))
    pages = _load_pages(pdf_path)
    hits = _find_hits(pages, queries)

    out_lines: List[str] = []
    for q in queries_raw:
        pages_hit = hits.get(q, [])
        out_lines.append(f"QUERY\t{q}\tPAGES\t{','.join(map(str, pages_hit)) if pages_hit else '-'}")
        if args.context and pages_hit:
            rx = re.compile(q if args.regex else re.escape(q), flags=re.IGNORECASE)
            if args.page:
                chosen_pages = [p for p in args.page if 1 <= p <= len(pages)]
            else:
                chosen_pages = pages_hit[: max(1, args.context)]
            for pno in chosen_pages:
                ctx = _extract_context(pages[pno - 1], rx, max_lines=args.max_lines)
                out_lines.append(f"CONTEXT\t{q}\tPAGE\t{pno}")
                for ln in ctx[:120]:
                    out_lines.append(ln)

    if args.out:
        out_path = Path(args.out).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text("\n".join(out_lines).rstrip() + "\n", encoding="utf-8")
        print(str(out_path))
        return 0

    for ln in out_lines:
        print(ln)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
