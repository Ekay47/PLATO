import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("headings_json", type=str)
    ap.add_argument("--contains", action="append", default=[])
    ap.add_argument("--regex", action="append", default=[])
    args = ap.parse_args(argv[1:])

    path = Path(args.headings_json).resolve()
    data: Dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    headings = data.get("headings", [])
    if not isinstance(headings, list):
        print("Invalid headings format", file=sys.stderr)
        return 2

    contains = [c for c in (args.contains or []) if c]
    regexes = [re.compile(r, flags=re.IGNORECASE) for r in (args.regex or []) if r]

    results: List[Dict[str, Any]] = []
    for h in headings:
        if not isinstance(h, dict):
            continue
        text = str(h.get("text") or "")
        ok = True
        for c in contains:
            if c.lower() not in text.lower():
                ok = False
                break
        if not ok:
            continue
        for rx in regexes:
            if not rx.search(text):
                ok = False
                break
        if not ok:
            continue
        results.append(h)

    for h in results[:200]:
        print(f"{h.get('page')}\t{h.get('text')}")
    if len(results) > 200:
        print(f"... truncated ({len(results) - 200} more)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

