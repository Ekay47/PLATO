## eval

cases.jsonl: one case per line for regression checks (renderability and structural requirements).

Fields:
- id: unique case id
- diagram_type: activity / sequence / state
- nl: natural-language input
- must_include: required tokens that must appear in the generated PlantUML (coarse constraint)
- notes: extra notes
