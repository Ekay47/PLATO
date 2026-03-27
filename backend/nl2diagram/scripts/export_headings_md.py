import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _load(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _group(headings: List[Dict[str, Any]]) -> Dict[str, List[Tuple[int, str]]]:
    out: Dict[str, List[Tuple[int, str]]] = {}
    for h in headings:
        if not isinstance(h, dict):
            continue
        ch = str(h.get("chapter") or "").strip()
        if not ch:
            continue
        page = int(h.get("page") or 0)
        text = str(h.get("text") or "").strip()
        if not text:
            continue
        out.setdefault(ch, []).append((page, text))
    for ch in out:
        out[ch] = sorted(set(out[ch]), key=lambda x: (x[0], x[1]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("headings_json", type=str)
    ap.add_argument("--out-dir", type=str, required=True)
    args = ap.parse_args()

    data = _load(Path(args.headings_json).resolve())
    headings = data.get("headings", [])
    if not isinstance(headings, list):
        raise SystemExit(2)

    grouped = _group(headings)
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    for ch, items in grouped.items():
        lines: List[str] = []
        lines.append(f"# Chapter {ch} headings")
        lines.append("")
        for page, text in items:
            lines.append(f"- p.{page}: {text}")
        lines.append("")
        (out_dir / f"chapter_{ch}.md").write_text("\n".join(lines), encoding="utf-8")
    print(str(out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

