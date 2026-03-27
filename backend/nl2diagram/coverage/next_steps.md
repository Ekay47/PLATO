# Next steps: full structural syntax coverage

This knowledge base currently covers a validated core subset of behavioral-diagram syntax.
To reach "full structural syntax coverage" for Activity / Sequence / State diagrams (as defined by the PlantUML Language Reference Guide), use the workflow below.

## 1) Use chapter heading inventories as the ground truth index

The extracted chapter heading inventories are generated from the reference PDF and stored here:
- coverage/chapters/chapter_1.md (Sequence diagram chapter)
- coverage/chapters/chapter_6.md (Activity diagram chapter)
- coverage/chapters/chapter_9.md (State diagram chapter)

They are the starting point for enumerating *all* structural constructs.

## 2) Expand coverage/constructs.yaml into a complete structural construct checklist

For each heading that corresponds to structural syntax:
- add a normalized `construct` entry (stable identifier)
- add 2-5 `queries` to locate the exact evidence in the PDF
- set `required: true` for structural syntax, `required: false` for styling-only features

## 3) Implement missing KB chunks iteratively

For each missing `construct`, create a YAML chunk under kb/plantuml/{activity|sequence|state}/:
- include minimal runnable `syntax` and at least 1 `example`
- add 2+ `rules` focused on correctness and block closure
- set `source.section` and `source.page` to the PDF evidence

## 4) Enforce correctness gates

Run:
- scripts/validate_kb.py (includes PlantUML jar `-syntax` validation)
- scripts/audit_kb.py --pdf <path-to-pdf> (coverage + validation findings)

Keep `errors=0` as the hard gate.

