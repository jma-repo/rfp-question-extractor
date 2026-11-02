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

## The 27B model: a run that was an integration bug, not a model result

`07_qwen3.8-27b_noThinkSuffix_3files_test.json`: qwen3.8-27b on three test files (capital-library, mountain-view, northern-lights), with the
`/no_think` suffix the client used at the time. Precision 1.000, **recall 0.600**, 35 items in review, about 11 minutes per file. Five of the 12 chunks
came back empty or unreadable and fell back to the rules (`fallback_chunks: 5`): the model was still reasoning, the reasoning used up `max_tokens`,
and the answer field was empty.

A probe on a one-line copy task (LM Studio, `max_tokens` 400) showed what actually switches the reasoning off:

| Request | Time | Reasoning characters |
|---|---|---|
| plain | 5.2 s | 154 |
| `/no_think` at the end of the message | 7.7 s | 380 |
| `/no_think` at the start | 5.8 s | 216 |
| `chat_template_kwargs: {enable_thinking: false}` | 4.7 s | 154 |
| **`reasoning_effort: "none"`** | **2.5 s** | **0** |

The client now sends `reasoning_effort: none` to qwen3 models. One 1,467-character chunk went from 301 s (two calls, one retry) to 38 s (one call).
The full 27B run in the README was made after the fix.
