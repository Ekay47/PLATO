## nl2diagram

This directory contains a PlantUML behavioral-diagram (Activity / Sequence / State) knowledge base and NL2Model (NL2Diagram) deliverables.

Directory structure:
- kb/: YAML knowledge chunks extracted from the PlantUML Language Reference Guide
- prompts/: prompt assembly templates for NL2Model
- eval/: minimal evaluation skeleton (regression cases and reports)
- coverage/: coverage and audit reports

Recommended workflow:
1. Add/maintain knowledge chunks under kb/ (prioritize high-frequency constructs first)
2. Assemble prompts using prompts/ (retrieval results + rules + examples)
3. Run eval/ and coverage/ for regression (renderability, structural coverage, consistency)
