import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Tuple


def _load_pages(pdf_path: Path) -> List[str]:
    try:
        from pypdf import PdfReader
    except Exception as e:
        raise RuntimeError(f"Missing dependency pypdf: {e}")

    reader = PdfReader(str(pdf_path))
    pages: List[str] = []
    for p in reader.pages:
        pages.append(p.extract_text() or "")
    return pages


def _compile_pattern(q: str, *, regex: bool) -> re.Pattern:
    if regex:
        return re.compile(q, flags=re.IGNORECASE)
    return re.compile(re.escape(q), flags=re.IGNORECASE)


def _find_pages(pages: List[str], rx: re.Pattern) -> List[int]:
    out: List[int] = []
    for i, t in enumerate(pages):
        if rx.search(t or ""):
            out.append(i + 1)
    return out


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", type=str)
    ap.add_argument("--query", required=True)
    ap.add_argument("--regex", action="store_true")
    ap.add_argument("--out", default="")
    ap.add_argument("--limit", type=int, default=200)
    args = ap.parse_args(argv[1:])

    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}", file=sys.stderr)
        return 2

    pages = _load_pages(pdf_path)
    rx = _compile_pattern(args.query, regex=args.regex)
    hits = _find_pages(pages, rx)

    payload = {
        "pdf": str(pdf_path),
        "query": args.query,
        "regex": bool(args.regex),
        "page_count": len(pages),
        "hit_pages": hits,
    }

    if args.out:
        out_path = Path(args.out).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(str(out_path))
        return 0

    shown = hits[: max(0, args.limit)]
    print(",".join(map(str, shown)) if shown else "-")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

