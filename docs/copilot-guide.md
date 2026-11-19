# Rebuilding the RFP question register agent with Microsoft Copilot

For an environment that has only Microsoft 365 Copilot (Chat, or **Agent Builder** in licensed Copilot, called Copilot Studio lite in
early documentation): no Python, no local model and no external API calls. This guide translates the pipeline of this repository's
PoC, step by step, into what "Copilot + Word + Excel" can do, and says plainly what it cannot do. The prompts can be pasted as they are.

> **Confidentiality**: this repository and its samples are all synthetic. Real RFPs from your work belong only in the Copilot your
> company has approved; do not bring them into this repository and do not upload them to any other tool.
> See also item 9 under "Verify first": files embedded in an agent are visible to everyone who can use the agent.

Legend: ✅ = read on an official Microsoft Learn / Support page (checked 2026-11-02, links at the end); 🔍 = not documented or depends
on your tenant or licence, **verify it in your environment first**; ⛔ = cannot be done without code.

---

## 0. Summary

| Step in the PoC | Replacement in Copilot | Possible? |
|---|---|---|
| 1 Normalize formats (no LLM) | Let Copilot read the Word / PDF / Excel file, or split it into small files or pasted text yourself | Partly: reading files ✅ (Word, Excel, PDF, CSV and TXT are accepted inputs); page and line numbers are its estimate 🔍 |
| 2 Chunking | **Chunk by hand** (by section, page range or sheet), one chunk per message | ✅ Microsoft also advises splitting long documents: the model pays less attention to the middle of a long document |
| 3 JSON-schema constraint | A Markdown table with fixed columns plus a worked example in the prompt | ⛔ No real constrained decoding; only the prompt and checks afterwards |
| Verbatim copy + page / line | Prompt rules plus "Starts with / Ends with" columns of 6 words each, for Ctrl+F | Partly: rewording drops a lot but is **not guaranteed** to stop; spot-check page and line numbers |
| 4 Substring check (code) | Excel `FIND` formula or Word Find; with the code interpreter, let it run Python | Without code: half-manual; with the code interpreter: automatic 🔍 |
| 5 Second pass for missed or repeated items | Ask once more per chunk (prompt P2) | ✅ Works; recall improves but **missing nothing is not guaranteed** |
| 6 Merge duplicates | **Do not let Copilot merge**: paste each chunk's table into Excel, use Remove Duplicates and conditional formatting | ✅ More reliable than letting Copilot merge |
| 7 Render one consistent Word layout | A. Word template styles + pasted Excel table; B. give this repository's fixed script to the code interpreter | A ✅ (no AI involved); B 🔍 |
| Summary counts, "needs human review" list | Excel pivot table / COUNTIFS; the REVIEW table on its own sheet | ✅ |

Two routes; pick the one your environment actually supports:

- **Route A (almost certainly available; start here)**: Copilot only does the understanding (extracting into a fixed-column table);
  checking, merging and layout are done in Excel and Word. Each RFP needs manual chunking, pasting and spot checks.
- **Route B (an upgrade when the code interpreter is available)**: let the code interpreter run this repository's
  [`copilot_snippets.py`](copilot_snippets.py), which runs the substring check and builds a Word file with a consistent layout from
  fixed code. It replaces the Excel formulas and the manual layout. **It needs `python-docx` in the sandbox; test it with item 4
  under "Verify first".**

---

## 1. Verify these 10 things in your environment first

Each item has a test you can paste and **a fallback if the result is not good enough**. Do not count on any of them before you have
checked.

| # | What to check | How to test | If it fails |
|---|---|---|---|
| 1 | Whether you can create an agent: does Microsoft 365 Copilot show **New agent** (✅ the entry point of Agent Builder), or only plain Copilot Chat | Look for New agent / Agents in the left rail | Fall back to plain chat: paste the Instructions from section 2 as the first message of every conversation |
| 2 | **Instructions length** (✅ official limit 8,000 characters) | Paste the Instructions from section 2 and see whether they are accepted | Remove the example from the Instructions and send it as the first message instead |
| 3 | Whether it reads your file types | Upload a synthetic Word, PDF and Excel file (`data/synthetic/rfps/`) and ask: "How many pages / sheets does this file have, and what is the first heading?" | Convert to PDF first, or paste the text into the conversation |
| 4 | Code interpreter: ✅ "always on" in Agent Builder, but ✅ only for users "with a Microsoft 365 Copilot licence, or Copilot Chat users without metered usage"; which libraries the sandbox has 🔍 | Ask: "Use Python to run `import docx, openpyxl; print(docx.__version__ if hasattr(docx,'__version__') else 'docx ok')` and also try `import pdfplumber`, `import pypdf`. Report which imports work." | Use route A only |
| 5 | Whether you can download a generated .docx (✅ generated files get a temporary download link that expires when the session ends) | Ask: "Create a Word file with a 3-column table and give me the download link." | Route A (paste into Word yourself) |
| 6 | **How many rows one reply can hold** (are long tables cut off) 🔍 | On a chunk with 20+ questions, check that the last row is the last question you expect (the "Last item in chunk" line exists for this) | Cut smaller chunks, at most 15 questions each |
| 7 | Whether scanned PDFs or images can be read (OCR) 🔍 | Upload one scanned page and ask it to transcribe the first paragraph word for word | OCR first in Word or Acrobat, or type it in |
| 8 | Whether page and line numbers are right 🔍 | Check the page of 5 items in a PDF reader; Word files have no fixed page numbers, the page count depends on rendering | Use "section number + paragraph number" instead, or only the first 6 words for Ctrl+F |
| 9 | **Confidentiality and sharing**: ✅ files embedded in an agent are stored in the tenant's default geography; ✅ Purview Information Barriers do not support embedded files; ✅ anyone who can use the agent can see answers based on the file; ✅ files with sensitivity labels that carry user-defined permissions are not supported; embedded files are not supported in GCC. Whether your DLP and sensitivity-label policies allow uploading an RFP 🔍 | Ask IT / compliance. **Do not share the agent with anyone who should not see the RFP**; for real RFPs prefer conversation attachments over files embedded in the agent | Use conversation attachments and delete the conversation afterwards |
| 10 | Number and size of files: ✅ at most 20 embedded files; ✅ Excel works best with the data on one sheet; single-file size and number of conversation attachments 🔍 | Upload 3 files at once | Process one RFP at a time |

> If something is uncertain, do not rely on it. **Items 4 and 5 decide between route A and route B.**

---

## 2. Agent Builder setup (both routes)

✅ Field limits: Name ≤ 30 characters, Description ≤ 1,000, Instructions ≤ 8,000. Switches: Code interpreter (always on), Image
generator (**turn it off**). Agent Builder does not support custom Actions (✅).

- **Name**: `RFP Question Extractor`
- **Description**: `Turns one chunk of an RFP (Word, PDF or Excel) into a fixed-format table of the questions a vendor must answer, copied word for word.`
- **Response mode**: choose **Think deeper** (✅ the documented modes are Auto / Quick response / Think deeper; extraction needs care,
  not speed). 🔍 Whether it really misses fewer items is something to compare yourself.
- **Knowledge**: none. The RFP comes as an attachment or pasted text in each conversation, not embedded in the agent (see item 9 in
  section 1).
- **Starter prompts** (optional): `Extract the questions from the chunk below.` / `Check my table for missed or repeated items.`

### Instructions (paste as one block; about 4,800 characters, under the 8,000 limit)

<!-- agent-instructions:start -->
```text
You are the RFP Question Extractor. You turn one chunk of a request for proposals (RFP) into a fixed-format table of the questions and requirements a vendor must answer. You never write proposals and never answer the questions.

INPUT
The user pastes or attaches one chunk of one RFP (a Word section, a PDF page range or one Excel sheet) under a header line such as "=== RFP: Fleet Telematics | CHUNK 3/12 | pages 5-7 ===". Work only on that chunk. A line starting with "CONTEXT ONLY:" is shown for orientation; do not extract from it.

WHAT COUNTS AS A QUESTION
An item the vendor must answer, describe, state, confirm, list, attach or price in its response. Include items inside table rows and Excel rows. Include every lettered or numbered sub-item under a lead-in sentence; the lead-in itself ("The Proponent shall address each of the following:") is not an item.
Do NOT include: background, definitions, dates and deadlines, how to submit, evaluation criteria and weights, contact details, headings, table header rows, blank form rows, line items of a pricing table, notes about page limits, running page headers and footers, page numbers. The instruction to complete a pricing table IS an item.

COPY WORD FOR WORD
Text is the item exactly as printed: same words, same order, same punctuation. Do not fix typos, shorten, merge, reword or translate. Do not put the printed number in Text; it goes in Ref. Keep "(Optional)", "(Desirable)" and "(Yes/No)" when printed. If you cannot copy an item exactly, put it in the REVIEW table instead of rewording it.

OUTPUT (exactly these parts, nothing before or after)
1. A Markdown table, one row per item, in document order, with these columns:
| Ref | Section | Text | Type | Required | Constraints | Where | Starts with | Ends with |
- Ref: the number printed in front of the item (4.2.1, (a), Q12, R-014) or "-".
- Section: the heading the item sits under, as printed.
- Text: the exact copy.
- Type: yes_no (answer is yes or no), upload (a document must be attached), pricing (prices, rates, costs), table (answer is a table or list in fixed columns), narrative (anything else).
- Required: Yes if the text says shall, must, is required, or nothing; No if it says optional, desirable, should or may, or the table marks it Desirable or Optional.
- Constraints: page, word or file limits, formats, amounts, appendix references; "-" if none.
- Where: PDF = page and line ("p.5 L12"); Excel = sheet and row ("Questionnaire!R12"); Word = heading number and paragraph ("4.2 para 3"). If you cannot tell, write UNKNOWN. Never guess.
- Starts with / Ends with: the first 6 and the last 6 words of Text, so a person can check them with Ctrl+F.
2. REVIEW: for anything you are unsure of (an item cut off at the edge of the chunk, text that may or may not be a question, text you could not copy exactly) a second table with columns | Text | Why |. If there is nothing to review write "REVIEW: none".
3. One last line: Items: N | Review: M | Last item in chunk: <first 6 words of the last item>
If the chunk has no questions, output only "Items: 0" and one sentence saying what the chunk contains.

RULES
- Never invent an item. Never answer an item. Never merge two items into one row.
- Use the same columns in the same order every time. No commentary.
- When asked to check a table for missed or repeated items: do not rewrite the table. Output only the MISSING rows (same columns, exact copies) and a line REPEATS: pairs of Refs that ask the same thing. If nothing is missing write "MISSING: none".

EXAMPLE
Chunk:
## 3.2 Network Design
3.2.1 The Proponent shall describe how access points are managed centrally, including firmware updates.
Proposals shall be submitted through the City portal before the Closing Time.
3.2.2 (Optional) Does the solution support captive portals? (Yes/No)
The Proponent shall address each of the following:
(a) Attach a sample maintenance schedule (PDF, maximum two pages).
Reply:
| Ref | Section | Text | Type | Required | Constraints | Where | Starts with | Ends with |
| 3.2.1 | 3.2 Network Design | The Proponent shall describe how access points are managed centrally, including firmware updates. | narrative | Yes | - | 3.2 para 1 | The Proponent shall describe how access | are managed centrally, including firmware updates. |
| 3.2.2 | 3.2 Network Design | (Optional) Does the solution support captive portals? (Yes/No) | yes_no | No | - | 3.2 para 3 | (Optional) Does the solution support captive | the solution support captive portals? (Yes/No) |
| (a) | 3.2 Network Design | Attach a sample maintenance schedule (PDF, maximum two pages). | upload | Yes | PDF, maximum two pages | 3.2 para 5 | Attach a sample maintenance schedule (PDF, | maintenance schedule (PDF, maximum two pages). |
REVIEW: none
Items: 3 | Review: 0 | Last item in chunk: Attach a sample maintenance schedule (PDF,
```
<!-- agent-instructions:end -->

`tests/test_copilot_guide.py` checks the length of these Instructions, that the example copies its chunk word for word, and that
the "Starts with / Ends with" words are counted correctly.

---

## 3. Chunking by hand (replaces steps 1 and 2 of the PoC)

✅ Microsoft notes that in a very long document the model pays most attention to the beginning and the end and tends to miss the
middle; it advises splitting long documents into smaller ones, and the ability to point Copilot at a section or page range is still
being developed (so today you cannot tell it to read only certain pages). The chunking is therefore yours to do.

**Chunk size**: 3 to 5 pages or 800 to 1,500 words for Word and PDF, at most 15 questions per chunk. The PoC's small local model
works best on chunks of about 1,400 characters (about 250 words); Copilot's model is stronger and can take much larger chunks, but
keep the "last line" check from the previous section, because very long replies may be cut off 🔍.

| File type | How to split | Watch out for |
|---|---|---|
| **Word** | View → Navigation Pane; select from one heading to the next heading of the same level, copy, **paste as plain text** into the conversation (or paste into a new document and upload it) | Automatic numbering (Word lists) may be lost when copied, and Ref becomes `-` 🔍. To keep numbers, save the section as PDF (File → Save As → PDF) and upload that, so the numbers become text on the page; or accept `-` |
| **PDF (text)** | Print → "Microsoft Print to PDF" with a page range such as `5-7`, which gives a small PDF of only those pages; upload it | Running headers, footers and page numbers end up in the text: the Instructions tell it to ignore them, but watch for them when spot-checking |
| **PDF (scanned)** | OCR first, or type it in | See item 7 in section 1 🔍 |
| **Excel** | One sheet per chunk: right-click the sheet → Move or Copy → new workbook. Split sheets with more than 60 rows by rows, **with the header row in every chunk** | ✅ "Data on one sheet works best". Unmerge merged cells and fill down first: select the column → Unmerge → F5 → Special → Blanks → type `=` and press ↑ → Ctrl+Enter |
| **Items that cross chunks** | Start the next chunk with a line `CONTEXT ONLY: <first 10 words of the last numbered item of the previous chunk>` | The Instructions say CONTEXT ONLY lines are not extracted |

Start every chunk with a line `=== RFP: <file name> | CHUNK 3/12 | pages 5-7 ===`. Keep a `Log` sheet in Excel: file / chunk /
pages / rows returned / review rows / checked. Consecutive chunk numbers and the row totals are the only way you will notice a whole
chunk that went missing.

---

## 4. Prompt library (paste as is)

### P1 Extraction (once per chunk)
With the Instructions in the agent, each conversation only needs the chunk:

```text
=== RFP: Fleet Telematics | CHUNK 3/12 | pages 5-7 ===
<paste the chunk here>
```

Without an agent (plain chat), paste the Instructions from section 2 first, then the chunk.

### P2 Check for missed and repeated items (once more per chunk)
```text
Below are the chunk again and the table you produced for it. Do not rewrite the table.
1) Find questions or requirements in the chunk that are missing from the table. Output them as rows in the same columns, copied word for word.
2) Find rows that ask the same thing as another row. Output "REPEATS:" followed by pairs of Refs.
If nothing is missing write "MISSING: none".

CHUNK:
<paste the chunk>

TABLE:
<paste the table>
```
Append the MISSING rows to the chunk's table and **check them again** (section 5). This pass raises recall; it does not guarantee it.

### P3 Self-check (asking Copilot to show where each row came from)
```text
For each row of the table, quote the sentence from the chunk it was copied from, with the 8 words before and after it. If you cannot find it in the chunk, write NOT FOUND for that row. Do not change any row.
```
⛔ This is still the model checking itself, and it can quote a wrong source with confidence. Treat it as a hint, not evidence; the
evidence is the Ctrl+F or formula check in section 5.

### P4 Excel questionnaires (each row is already a question)
```text
Each row of the attached sheet is one question. Do not extract anything new. For every row, output the table with Text copied exactly from the Question column, Ref from the Ref column, Required from the Mandatory column, and Type chosen from the Response type column (Free text = narrative, Yes/No = yes_no, Attachment = upload, Table = table, Pricing = pricing). Where = "<sheet>!R<row number>".
```

### P5 Code interpreter: verification (route B)
Paste the whole of `docs/copilot_snippets.py` first, then:
```text
Run the code above. Then, using the function verify(rows, source): rows is the JSON list I give you and source is the chunk text I give you. Print every row whose text is not a verbatim piece of the source. Do not edit rows.
ROWS: <paste JSON>
SOURCE: <paste chunk>
```
JSON fields: `rfp, section, ref, text, type, required, constraints, source`. Have Copilot convert the section 2 table into this JSON
(with one example, which small and large models both follow):

<!-- json-example:start -->
```text
Convert the table to a JSON list with the keys rfp, section, ref, text, type, required (true or false), constraints, source (the Where value). Copy text exactly. Reply with the JSON only.
Example row:  | 3.2.2 | 3.2 Network Design | (Optional) Does the solution support captive portals? (Yes/No) | yes_no | No | - | 3.2 para 3 | ... | ... |
Example JSON: [{"rfp": "Fleet Telematics", "section": "3.2 Network Design", "ref": "3.2.2", "text": "(Optional) Does the solution support captive portals? (Yes/No)", "type": "yes_no", "required": false, "constraints": "", "source": "3.2 para 3"}]
```
<!-- json-example:end -->

JSON's advantage is that the code interpreter (P5, P6) can read it directly; its drawback is that Copilot sometimes adds explanations
before or after it, so keep the last sentence, `Reply with the JSON only.`

### P6 Code interpreter: Word file with a fixed layout (route B)
```text
Run build_register(rows) from the code above on the JSON below, save as rfp_register.docx and give me the download link. Do not change the layout, the column names or the fonts.
ROWS: <paste the full JSON list, all chunks>
```
The layout is fixed by the code (landscape, one table per section, 8 columns of fixed width), so it is the same every time. 🔍 The
sandbox needs `python-docx` (item 4 in section 1).

---

## 5. The substring check without code

The PoC's rule: `question_text` must be one contiguous piece of the source text. Without code, use any of the methods below; **the
higher in the list, the more automatic**.

**Method 1: an Excel formula (recommended, in bulk)**

1. New workbook, sheet `Source`: paste the chunk's text **into the single cell `A2`** (a chunk of about 3,000 characters or less fits
   well within the cell limit of 32,767 characters).
2. Sheet `Rows`: paste Copilot's table at `A1` (columns: A Ref, B Section, C Text, D Type, E Required, F Constraints, G Where,
   H Starts with, I Ends with).
3. In `J2` (one line; paste it as is):
```text
=IF(AND(ISNUMBER(FIND(LEFT(C2,100),TRIM(SUBSTITUTE(SUBSTITUTE(Source!$A$2,CHAR(10)," "),CHAR(13)," ")))),ISNUMBER(FIND(RIGHT(C2,100),TRIM(SUBSTITUTE(SUBSTITUTE(Source!$A$2,CHAR(10)," "),CHAR(13)," "))))),"ok","CHECK")
```
Fill down to every row. A `CHECK` row means the first or the last 100 characters are not in the source, which usually means it was
reworded.
- `FIND` is case-sensitive and has no wildcards, so it is closer to the PoC's "word for word" than `SEARCH`.
- The formula misses a row whose start and end match but whose middle was reworded. To check the whole text, replace
  `LEFT(C2,100)` with `C2`; if that returns `#VALUE!`, your Excel version limits the length of the search text 🔍, so go back to
  the LEFT / RIGHT version.
- Copilot may turn curly quotes, long dashes and non-breaking spaces in the source into straight quotes and plain spaces, which
  gives false `CHECK` results: first use Find and Replace in Source to turn `’ “ ” – —` into straight quotes and `-`.
4. Conditional formatting: colour the whole row red where column `J` is `CHECK`. **Do not delete these rows**; move them to the
   `REVIEW` sheet (the PoC's "needs human review" list).

**Method 2: Ctrl+F in Word or PDF (spot checks)**
Search the source for the `Starts with` value of a row. Check 5 rows per chunk, **the longest ones with commas and brackets in the
middle first** (that is where rewording happens). If it is not found, try `Ends with`; if neither is found, the row was reworded or
invented.

**Method 3: code interpreter (route B)**: prompt P5; `verify` runs the same substring check as the PoC on every row.

**How to spot missed items** (the substring check cannot find them):
- Number gaps: `4.2.1, 4.2.2, 4.2.4` means 4.2.3 is missing.
- The `Last item in chunk` line must match the last question you see in the chunk.
- Count `shall`, `must`, `should` and `?` in each chunk of the source (searching in Word's Navigation Pane shows the number of
  matches) and compare with the number of rows returned; if they differ a lot, run the chunk again.
- Run P2.

---

## 6. One consistent layout (replaces the PoC's docxtpl template)

**Route A (no AI involved, so the layout is always the same)**
1. In Excel, append each chunk's table to the sheet `All`; Data → Remove Duplicates on the `Text` column (it removes only exact
   duplicates; mark near-duplicates with conditional formatting and **let a person decide**, as the PoC's "flag, never merge").
2. Add two columns, `Owner` and `Status`, for the team to fill in.
3. Build the layout once and save it as a template: a new Word document in landscape, with the Heading 1 / Heading 2 / table-text
   styles set, the header row set to repeat at the top of each page, fixed column widths; save as `RFP-register.dotx`.
4. Each time: create a document from the `.dotx`, copy the `All` range from Excel, paste, and choose Use Destination Styles. The
   styles come from the template, so the result is the same every time.
5. Put the summary counts at the top: an Excel pivot table (rows = RFP, columns = Type, values = count) or `COUNTIFS`, pasted as a
   table.
6. **Group by RFP, then by section**: sort by `RFP` and `Section`, then paste each group separately; with many sections this is
   tedious by hand, which is the real cost of route A and the reason route B is worth verifying.

**Route B**: P6. Fixed code means a fixed layout. Limits: it builds a simple 8-column table only, without the PoC's template whose
styles can be changed in Word, and without the summary table and the "needs human review" list; add those in Word, or change
`build_register` in `copilot_snippets.py` and paste that version (paste the same code every time; do not let Copilot rewrite it).

**Not recommended**: asking Copilot to "turn these questions into a nicely formatted Word document". The layout changes every time,
which is exactly the problem you are trying to solve.

---

## 7. What cannot be done (stated plainly)

- ⛔ **A guarantee of no missed and no reworded items.** You can only make them less likely and easier to find: the verbatim-copy
  rules, the 6-word start and end columns, the `Last item` line, the P2 second pass, the Excel formula, and human spot checks.
- ⛔ **A real JSON-schema constraint.** Copilot has no constrained decoding; it may add a column, drop one or rename one. A
  fixed-column Markdown table with an example is the closest you get, and a broken column shows up at once in Excel.
- ⛔ **Unattended batch runs.** 10 RFPs of a dozen chunks each means a hundred or more manual pastes. Agent Builder does not support
  custom Actions (✅), and there is no API to call.
- 🔍 **Page and line numbers.** Word has no fixed page numbers; page and line numbers in a PDF are the model's estimate. Reliable
  locations are section numbers, item numbers and `Starts with`.
- 🔍 **Long replies cut off** and **the middle of very long documents ignored** (✅ documented). Small chunks and the `Last item` line
  catch them.
- 🔍 **Data governance.** See item 9 in section 1; your tenant may have file upload or the code interpreter turned off.
- ⛔ **External judge models** cannot be used: Copilot cannot call external APIs, and the data should not leave your tenant.

---

## 8. A 10-minute evaluation in Copilot on this repository's synthetic data

Goal: get a rough idea of how your Copilot does on files like these before deciding whether to trust it. The data is synthetic, so it
is safe to upload.

1. Take `northfield-fleet-telematics.docx`, `foothills-student-information-system.pdf` and `bow-river-fare-questionnaire.xlsx`
   from `data/synthetic/rfps/` (these three are the dev set; the test set is listed in `data/synthetic/manifest.json`).
2. Chunk them as in section 3, run P1, and paste every chunk's table into the sheet `Pred` (column `C` is Text).
3. Open `data/synthetic/gold_all.csv` and copy it into the sheet `Gold` (column `E` is question_text).
4. Recall (approximated on the first 100 characters, case-insensitive, looser than the PoC's verbatim match): in `Gold`, put
   `=IF(COUNTIF(Pred!$C:$C,LEFT(E2,100)&"*")>0,1,0)` in `K2`, fill down, then `=AVERAGE(K:K)`. Precision: in `Pred`, put
   `=IF(COUNTIF(Gold!$E:$E,LEFT(C2,100)&"*")>0,1,0)` in `K2`, fill down, then `=AVERAGE(K:K)`.
   - `COUNTIF` treats `?` and `*` as wildcards, so questions ending in a question mark may be miscounted now and then; good enough
     for a rough evaluation.
5. Compare with the PoC's numbers (the table in the README, the Test F1 column for the same files): about 0.92 for the rules
   baseline, 0.89 to 0.91 for the 3B local model. **If your Copilot is clearly below the rules baseline, do not use it on real
   RFPs, or use it only as a second opinion.**

---

## 9. Recommended minimal workflow (route A)

1. Run the checklist in section 1 (15 minutes) and pick a route.
2. Build the agent (section 2).
3. For each RFP: chunk (section 3) → P1 → paste the table into Excel `All` → the column J formula (section 5) → move `CHECK` rows to
   `REVIEW` → P2 → append and check the MISSING rows → fill in the `Log`.
4. Remove duplicates, sort, add Owner / Status, and paste into the `.dotx` template (section 6).
5. Before handing it to the team, compare 10 random rows per RFP with the source and note the rewording rate; above 5%, use smaller
   chunks and run it again.

---

### Official sources (checked 2026-11-02)

- Agent Builder fields and limits, response modes, capability switches: <https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/agent-builder-build-agents>
- Knowledge sources and limits, storage and permissions of embedded files, the one-sheet Excel advice: <https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/agent-builder-add-knowledge>
- Code interpreter (input formats, downloadable generated files valid only in the session, licence conditions): <https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/code-interpreter>
- Document length and attention: <https://support.microsoft.com/en-us/microsoft-365-copilot/how-reference-and-document-lengths-affect-copilot-responses>

These pages change; anything they do not cover (sandbox libraries, reply length, scanned files, single-file size) is marked 🔍 above.
