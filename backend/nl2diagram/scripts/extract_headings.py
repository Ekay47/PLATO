import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass(frozen=True)
class Heading:
    page: int
    text: str
    chapter: Optional[str]


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


def _normalize_line(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip())
    return s


def _extract_numbered_headings(page_text: str) -> List[str]:
    out: List[str] = []
    for raw in (page_text or "").splitlines():
        ln = _normalize_line(raw)
        if not ln:
            continue
        if re.match(r"^\d+\.\d+\s+\S+", ln):
            out.append(ln)
        elif re.match(r"^\d+\.\d+\.\d+\s+\S+", ln):
            out.append(ln)
    return out


def _guess_chapter(line: str) -> Optional[str]:
    m = re.match(r"^(\d+)\.\d+(\.\d+)?\s+", line)
    if not m:
        return None
    return m.group(1)


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", type=str)
    ap.add_argument("--out", type=str, default="")
    ap.add_argument("--min-page", type=int, default=1)
    ap.add_argument("--max-page", type=int, default=10_000)
    ap.add_argument("--chapters", type=str, default="1,6,9")
    args = ap.parse_args(argv[1:])

    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}", file=sys.stderr)
        return 2

    wanted = {c.strip() for c in (args.chapters or "").split(",") if c.strip()}
    pages = _load_pages(pdf_path)

    headings: List[Heading] = []
    for idx in range(max(1, args.min_page), min(len(pages), args.max_page) + 1):
        hs = _extract_numbered_headings(pages[idx - 1])
        for h in hs:
            ch = _guess_chapter(h)
            if wanted and (ch not in wanted):
                continue
            headings.append(Heading(page=idx, text=h, chapter=ch))

    payload: Dict[str, object] = {
        "pdf": str(pdf_path),
        "chapters": sorted(wanted),
        "count": len(headings),
        "headings": [{"page": h.page, "chapter": h.chapter, "text": h.text} for h in headings],
    }

    if args.out:
        out_path = Path(args.out).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(str(out_path))
        return 0

    for h in headings[:500]:
        print(f"{h.page}\t{h.text}")
    if len(headings) > 500:
        print(f"... truncated ({len(headings) - 500} more)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

