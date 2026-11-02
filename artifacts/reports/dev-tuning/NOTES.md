# Prompt and chunk-size tuning on the dev split

Three files (`northfield-fleet-telematics.docx`, `foothills-student-information-system.pdf`, `bow-river-fare-questionnaire.xlsx`),
qwen2.5-3b-instruct, in the order the runs were made. The test split was not run during this tuning. The reports are the raw output of
`rfpx eval --split dev`; later reports also carry `by_split`, these do not.

| File | Prompt | Chunk | Section gate | Dev F1 |
|---|---|---|---|---|
| `01_v1_3examples_chunk2400_nogate.json` | v1: 3 worked examples, 8 rules | 2,400 chars | no (not built yet) | 0.905 |
| `02_v2_chunk1400_nogate.json` | v2: + "every item under a lead-in is still an item", "do not stop early", a `should` example | 1,400 | no | 0.914 |
| `03_v3_4examples_chunk1400_nogate.json` | v3: v2 + a fourth example showing an excerpt with nothing to extract | 1,400 | no | 0.854 |
| `04_v3_4examples_chunk1400_recheck_nogate.json` | v3 with the second pass | 1,400 | no | 0.858 |
| `05_v2_chunk2400_gate.json` | v2 (the fourth example dropped again) | 2,400 | yes | 0.893 |
| `06_v2_chunk1400_gate.json` | v2 | 1,400 | yes | 0.951 |

What changed the result: smaller chunks, the section gate, and *not* adding the empty-excerpt example (it made the model reword text,
which the verbatim check then rejected). v2 with 1,400-character chunks and the gate is the configuration in `configs/rfpx.yaml`.
