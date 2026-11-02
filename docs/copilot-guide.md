# 用 Microsoft Copilot 复刻 RFP 问题汇总 agent

适用环境：只有 Microsoft 365 Copilot（Chat 或带许可证的 Copilot 里的 **Agent Builder**，早期文档里叫 Copilot Studio lite），
没有 Python，没有本地模型，也不能调外部 API。本指南把本仓库 PoC 的流水线逐步翻译成"Copilot + Word + Excel"能做到的版本，
并明说哪些做不到。提示词是英文的，可直接粘贴；说明是中文。

> **保密红线**：这个仓库和它的样例全是合成数据。你工作中的真实 RFP 只在公司批准的 Copilot 里处理，不要拿到仓库里，也不要上传到任何别的工具。
> 另见下面"先验证"第 9 条：嵌入 agent 的文件对所有能访问该 agent 的人可见。

图例：✅ = 我在 Microsoft Learn / Support 官方页面上读到了（2026-11-02 查阅，链接在文末）；🔍 = 文档没写或取决于租户/授权，**要在你的环境里先验证**；⛔ = 无代码做不到。

---

## 0. 结论先行

| PoC 里的步骤 | Copilot 里的替代 | 能做到吗 |
|---|---|---|
| 1 格式归一化（不用 LLM） | 让 Copilot 自己读 Word/PDF/Excel；或你手动拆成小文件/粘贴文本 | 部分：读文件 ✅（Word、Excel、PDF、CSV、TXT 可作输入），页码/行号是它"估"的 🔍 |
| 2 分块 | **你手动分块**（按章节/页/sheet），一块一次 | ✅ 官方也建议把长文档拆小：模型对长文档中间部分注意力低 |
| 3 JSON schema 约束 | 固定列的 Markdown 表格 + 提示词里的示例 | ⛔ 没有真正的约束解码，只能靠提示词和事后检查 |
| 逐字抄录 + 页码/行号 | 提示词约束 + "开头/结尾 6 个词"两列，供你 Ctrl+F | 部分：能大幅降低改写，**不能保证**；页码/行号要抽查 |
| 4 子串校验（代码） | Excel `FIND` 公式 / Word 查找；有代码解释器时让它跑 Python | 无代码：半自动；有代码解释器：可自动 🔍 |
| 5 第二遍"漏题/重复"检查 | 每块再问一次（提示词 P2） | ✅ 能做，召回有提升但**不保证没漏** |
| 6 合并去重 | **不要让 Copilot 合并**：把每块的表粘进 Excel，用"删除重复项"/条件格式 | ✅ 比让 Copilot 合并可靠 |
| 7 渲染成统一版式 Word | A. Word 模板样式 + 粘贴 Excel 表格；B. 把本仓库的固定脚本交给代码解释器 | A ✅（不依赖 AI）；B 🔍 |
| 汇总统计、"待人工确认"区 | Excel 透视表 / COUNTIFS；REVIEW 表单独一个 sheet | ✅ |

两条路线，按你环境的实际能力选：

- **路线 A（几乎一定可用，推荐起步）**：Copilot 只做"理解"（抽取成固定列表格），校验、合并、版式都交给 Excel 和 Word。每份 RFP 要你手动分块、粘贴、抽查。
- **路线 B（代码解释器可用时的增强）**：让代码解释器跑本仓库里的 [`copilot_snippets.py`](copilot_snippets.py)：自动做子串校验，并用固定代码生成版式一致的 Word。省掉 Excel 公式和手动排版。**前提是沙盒里有 `python-docx`，下面"先验证"第 4 条测一下。**

---

## 1. 先在你的环境里验证这 10 件事

每条都给了一句可粘贴的测试。**结果不满足时的退路**写在后面；不要在没验证前把这些当成肯定可用。

| # | 要验证什么 | 怎么测 | 不行怎么办 |
|---|---|---|---|
| 1 | 你能不能新建 agent：Microsoft 365 Copilot 里有没有 **New agent**（✅ Agent Builder 的入口），还是只有普通 Copilot Chat | 左侧栏找 New agent / Agents | 退化为"普通对话"：把第 3 节的 Instructions 当作每次对话的第一条消息粘贴 |
| 2 | **Instructions 长度**（✅ 官方上限 8,000 字符） | 粘贴第 3 节的 Instructions，看是否被接受 | 删掉里面的示例，示例改放第一条消息 |
| 3 | 能不能读你的文件类型 | 上传一份合成 Word、PDF、Excel（`data/synthetic/rfps/`），问："How many pages / sheets does this file have, and what is the first heading?" | 先转成 PDF 或把文本粘贴进对话 |
| 4 | 代码解释器：✅ Agent Builder 里"始终启用"，但 ✅ 仅限"有 Microsoft 365 Copilot 许可证，或没有开 metered 用量的 Copilot Chat 用户"；沙盒里有哪些库 🔍 | 问："Use Python to run `import docx, openpyxl; print(docx.__version__ if hasattr(docx,'__version__') else 'docx ok')` and also try `import pdfplumber`, `import pypdf`. Report which imports work." | 只走路线 A |
| 5 | 能不能下载生成的 .docx（✅ 官方说生成的文件有临时下载链接，会话结束后失效） | 问："Create a Word file with a 3-column table and give me the download link." | 路线 A（Word 里自己粘贴） |
| 6 | **一次能输出多少行**（长表格会不会被截断） 🔍 | 对一块有 20+ 个问题的内容，看最后一行是不是你预期的最后一题（输出里的 "Last item in chunk" 行就是为此设计的） | 把块切得更小，每块 ≤ 15 题 |
| 7 | 扫描版 PDF / 图片能不能读（OCR） 🔍 | 上传一页扫描件，问它逐字转写第一段 | 先用 Word/Acrobat 做 OCR，或人工录入 |
| 8 | 页码/行号准不准 🔍 | 抽 5 个条目，用 PDF 阅读器对页码；Word 文件没有固定页码，页数取决于渲染 | 改用"章节号 + 段落序号"，或只写开头 6 个词让人 Ctrl+F |
| 9 | **保密与共享**：✅ 嵌入 agent 的文件存放在租户的默认地理位置；✅ Purview Information Barriers 不支持嵌入文件；✅ 任何能访问该 agent 的人都能看到基于该文件的回答；✅ 带用户自定义权限的敏感度标签的文件不受支持；GCC 环境不支持嵌入文件。你的 DLP/敏感度标签策略是否允许上传 RFP 🔍 | 问 IT/合规。**agent 不要共享给不该看这份 RFP 的人**；真实 RFP 优先用对话附件而不是嵌入 agent | 用对话附件，处理完删除对话 |
| 10 | 文件数量与大小：✅ 嵌入文件最多 20 个；✅ Excel 数据放在一个 sheet 里效果最好；单文件大小/对话附件数量 🔍 | 一次传 3 份 | 一次只处理一份 RFP |

> 不确定的就不要依赖。**第 4、5 条决定走路线 A 还是 B。**

---

## 2. Agent Builder 配置（路线 A 和 B 通用）

✅ 字段上限：Name ≤ 30 字符，Description ≤ 1,000，Instructions ≤ 8,000。开关：Code interpreter（始终开）、Image generator（**关掉**）。
Agent Builder 不支持自建 Actions（✅）。

- **Name**：`RFP Question Extractor`
- **Description**：`Turns one chunk of an RFP (Word, PDF or Excel) into a fixed-format table of the questions a vendor must answer, copied word for word.`
- **Response mode**：选 **Think deeper**（✅ 官方列出 Auto / Quick response / Think deeper；抽取要求细心，不求快）。🔍 是否真的减少漏题，要你对比测试。
- **Knowledge**：不加。RFP 作为每次对话的附件/粘贴文本，不嵌入 agent（见第 1 节第 9 条）。
- **Starter prompts**（可选）：`Extract the questions from the chunk below.` / `Check my table for missed or repeated items.`

### Instructions（整段粘贴，约 4,800 字符，低于 8,000 上限）

<!-- agent-instructions:start -->
```text
You are the RFP Question Extractor. You turn one chunk of a request for proposals (RFP) into a fixed-format table of the questions and requirements a vendor must answer. You never write proposals and never answer the questions.

INPUT
The user pastes or attaches one chunk of one RFP (a Word section, a PDF page range or one Excel sheet) under a header line such as "=== RFP: Fleet Telematics | CHUNK 3/12 | pages 5-7 ===". Work only on that chunk. A line starting with "CONTEXT ONLY:" is shown for orientation; do not extract from it.

WHAT COUNTS AS A QUESTION
An item the vendor must answer, describe, state, confirm, list, attach or price in its response. Include items inside table rows and Excel rows. Include every lettered or numbered sub-item under a lead-in sentence; the lead-in itself ("The Proponent shall address each of the following:") is not an item.
Do NOT include: background, definitions, dates and deadlines, how to submit, evaluation criteria and weights, contact details, headings, table header rows, blank form rows, line items of a pricing table, notes about page limits. The instruction to complete a pricing table IS an item.

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

这段 Instructions 的长度、示例是否逐字取自示例原文、"开头/结尾 6 词"是否数对，都由 `tests/test_copilot_guide.py` 检查。

---

## 3. 手动分块（替代 PoC 的第 1、2 步）

✅ 官方说明：对很长的文档，模型更关注开头和结尾，中间的内容容易被忽略；建议把长文档拆成小文档分别给它，并且"指定章节/页码范围"的功能还在开发中（也就是现在不能让它只读第几页）。所以分块要你自己做。

**块有多大**：Word/PDF 约 3 到 5 页或 800 到 1,500 个词；一块里问题 ≤ 15 个。本 PoC 的本地小模型在约 1,400 字符（约 250 词）的块上效果最好；Copilot 的模型更强，块可以大得多，但上一节的"最后一行"检查要保留，因为超长输出可能被截断 🔍。

| 文件类型 | 怎么拆 | 注意 |
|---|---|---|
| **Word** | 视图 → 导航窗格，按标题选中到下一个同级标题，复制，**粘贴为纯文本**到对话（或粘贴进新文档再上传） | 自动编号（Word 列表）复制出来后编号可能丢失，Ref 会变成 `-` 🔍。需要保留编号时，把这一节另存为 PDF（文件 → 另存为 → PDF）再上传，编号就成了页面上的文字；或者接受 Ref 为 `-` |
| **PDF（文本型）** | 打印 → "Microsoft Print to PDF"，在"页面范围"里填 `5-7`，得到只含这几页的小 PDF，再上传 | 页眉页脚、页码会混进文本：Instructions 已要求忽略标题表头；页眉重复行你可以在抽样时忽略 |
| **PDF（扫描版）** | 先做 OCR，或手工录入 | 见第 1 节第 7 条 🔍 |
| **Excel** | 一个 sheet 一块：右键 sheet → 移动或复制 → 新工作簿。行数 > 60 就按行拆，**每块都带表头行** | ✅ "数据放在一个 sheet 里效果最好"。先把合并单元格取消合并并向下填充：选中该列 → 取消合并 → F5 → 定位条件 → 空值 → 输入 `=` 再按 ↑ → Ctrl+Enter |
| **跨块的题** | 在下一块开头加一行 `CONTEXT ONLY: <上一块最后 1 个编号题的前 10 个词>` | Instructions 已规定 CONTEXT ONLY 不抽取 |

每块的第一行写：`=== RFP: <文件名> | CHUNK 3/12 | pages 5-7 ===`。再建一个 Excel 台账 sheet `Log`：文件 / 块号 / 页码 / 返回条数 / Review 条数 / 已核对。块号连续、条数合计，是你发现"整块漏掉"的唯一办法。

---

## 4. 提示词库（可直接粘贴）

### P1 抽取（每块一次）
agent 里已有 Instructions，每次对话只需要粘贴块：

```text
=== RFP: Fleet Telematics | CHUNK 3/12 | pages 5-7 ===
<paste the chunk here>
```

没有 agent（普通对话）时，先粘贴第 2 节的 Instructions，再粘贴块。

### P2 漏题与重复检查（每块再问一次）
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
把 MISSING 行追加到该块的表里，**再核对一次**（第 5 节）。这一遍的价值是提高召回，不是保证。

### P3 自检（想让 Copilot 自己找出处）
```text
For each row of the table, quote the sentence from the chunk it was copied from, with the 8 words before and after it. If you cannot find it in the chunk, write NOT FOUND for that row. Do not change any row.
```
⛔ 这仍是模型在"自查"，它给出的出处可能错得很自信。当作提示，不当证据；证据是第 5 节的 Ctrl+F / 公式。

### P4 Excel 问卷（每行已是一道题）
```text
Each row of the attached sheet is one question. Do not extract anything new. For every row, output the table with Text copied exactly from the Question column, Ref from the Ref column, Required from the Mandatory column, and Type chosen from the Response type column (Free text = narrative, Yes/No = yes_no, Attachment = upload, Table = table, Pricing = pricing). Where = "<sheet>!R<row number>".
```

### P5 代码解释器：校验（路线 B）
先粘贴 `docs/copilot_snippets.py` 全文，然后：
```text
Run the code above. Then, using the function verify(rows, source): rows is the JSON list I give you and source is the chunk text I give you. Print every row whose text is not a verbatim piece of the source. Do not edit rows.
ROWS: <paste JSON>
SOURCE: <paste chunk>
```
JSON 字段：`rfp, section, ref, text, type, required, constraints, source`。让 Copilot 把第 2 节的表转成这个 JSON（附一个示例，小模型和大模型都会照着学）：

<!-- json-example:start -->
```text
Convert the table to a JSON list with the keys rfp, section, ref, text, type, required (true or false), constraints, source (the Where value). Copy text exactly. Reply with the JSON only.
Example row:  | 3.2.2 | 3.2 Network Design | (Optional) Does the solution support captive portals? (Yes/No) | yes_no | No | - | 3.2 para 3 | ... | ... |
Example JSON: [{"rfp": "Fleet Telematics", "section": "3.2 Network Design", "ref": "3.2.2", "text": "(Optional) Does the solution support captive portals? (Yes/No)", "type": "yes_no", "required": false, "constraints": "", "source": "3.2 para 3"}]
```
<!-- json-example:end -->

JSON 的好处是代码解释器（P5、P6）可以直接读；坏处是 Copilot 偶尔会在 JSON 前后加解释，所以最后一句 `Reply with the JSON only.` 不能删。

### P6 代码解释器：生成固定版式 Word（路线 B）
```text
Run build_register(rows) from the code above on the JSON below, save as rfp_register.docx and give me the download link. Do not change the layout, the column names or the fonts.
ROWS: <paste the full JSON list, all chunks>
```
版式由代码固定（横向、每节一张表、8 列固定宽度），每次一致。🔍 沙盒里要有 `python-docx`（第 1 节第 4 条）。

---

## 5. 没有代码时怎么做"子串校验"

PoC 里的规则：`question_text` 必须是原文的一段连续文字。没有代码时，用下面任一办法，**越靠上越自动**。

**办法 1：Excel 公式（推荐，批量）**

1. 新建工作簿，sheet `Source`：把这一块的原文**粘贴进 `A2` 一个单元格**（一块 ≤ 约 3,000 字符，在单元格 32,767 字符上限内）。
2. sheet `Rows`：把 Copilot 的表粘贴到 `A1`（列：A Ref，B Section，C Text，D Type，E Required，F Constraints，G Where，H Starts with，I Ends with）。
3. `J2` 填（一行，粘贴即可）：
```text
=IF(AND(ISNUMBER(FIND(LEFT(C2,100),TRIM(SUBSTITUTE(SUBSTITUTE(Source!$A$2,CHAR(10)," "),CHAR(13)," ")))),ISNUMBER(FIND(RIGHT(C2,100),TRIM(SUBSTITUTE(SUBSTITUTE(Source!$A$2,CHAR(10)," "),CHAR(13)," "))))),"ok","CHECK")
```
下拉到所有行。`CHECK` 的行：开头 100 个字符或结尾 100 个字符不在原文里，多半是被改写了。
- `FIND` 区分大小写、不当通配符，所以比 `SEARCH` 更接近 PoC 的"逐字"。
- 开头和结尾都命中但中间被改写的情况，这个公式查不出来。要查全文：把 `LEFT(C2,100)` 换成 `C2`；如果出现 `#VALUE!`，说明你的 Excel 版本对查找文本有长度限制 🔍，回到 LEFT/RIGHT 版本。
- 原文里的弯引号、长破折号和不间断空格，Copilot 可能换成直引号和普通空格，会造成"误报 CHECK"：先在 Source 里用查找替换把 `’ “ ” – —` 换成直引号和 `-`。
4. 条件格式：`J` 列等于 `CHECK` 的整行标红。**不要删除这些行**，把它们移到 `REVIEW` sheet（PoC 里叫"待人工确认"区）。

**办法 2：Word / PDF 里 Ctrl+F（抽查）**
用表里的 `Starts with` 列到原文里 Ctrl+F。每块抽 5 行，**优先抽最长的、中间有逗号和括号的**（改写通常发生在这里）。找不到就看 `Ends with`；两个都找不到，这一行是改写的或编造的。

**办法 3：代码解释器（路线 B）**：提示词 P5，`verify` 对全部行做和 PoC 一样的子串检查。

**怎么抽查"漏题"**（子串校验查不了漏题）：
- 题号连续性：`4.2.1, 4.2.2, 4.2.4` 少了 4.2.3 就是漏了。
- `Last item in chunk` 行必须等于你肉眼看到的这一块最后一道题。
- 每块在原文里数 `shall`、`must`、`should`、`?` 出现的次数（Word 导航窗格里搜索会显示匹配数），和返回条数大致对得上；差得多就重跑这一块。
- 跑 P2。

---

## 6. 统一版式（替代 PoC 的 docxtpl 模板）

**路线 A（不依赖 AI，版式一定一致）**
1. Excel 里把各块的表追加到 sheet `All`；"数据 → 删除重复项"按 `Text` 列去重（只删完全相同的；近似重复用条件格式标出，**让人决定**，对应 PoC 的"flag, never merge"）。
2. 加两列 `Owner`、`Status`（留给团队填）。
3. 版式一次性做好，保存为模板：新建 Word 文档，页面设为横向，设置好 标题 1 / 标题 2 / 表格文字 样式，把表头行设成"在各页顶端以标题行形式重复出现"，列宽固定，另存为 `RFP-register.dotx`。
4. 每次：新建基于 `.dotx` 的文档，把 Excel 的 `All` 区域复制 → 粘贴为表格（"保留目标样式"）。样式来自模板，所以每次一致。
5. 汇总统计放在文首：用 Excel 透视表（行 = RFP，列 = Type，值 = 计数）或 `COUNTIFS`，粘贴为表格。
6. **按 RFP、再按章节分组**：先按 `RFP`、`Section` 排序，再分别粘贴；分节数多时手工很累，这是路线 A 的真实成本，也是路线 B 值得验证的原因。

**路线 B**：P6。固定代码 = 固定版式。限制：只生成 8 列的简单表格，没有 PoC 里那种可在 Word 里直接改样式的模板，也没有汇总表和"待人工确认"区；这些要你在 Word 里补，或者把 `copilot_snippets.py` 里的 `build_register` 改一版再粘贴（每次粘贴同一份代码，不要让 Copilot 重写）。

**不推荐**：直接让 Copilot "把这些问题整理成一份格式漂亮的 Word 文档"。每次排版会不一样，这正是你要解决的问题。

---

## 7. 做不到的事（明说）

- ⛔ **保证不漏题、不改写。** 只能降低概率并让它可发现：逐字抄录约束、开头/结尾 6 词、`Last item` 行、P2 第二遍、Excel 公式、人工抽查。
- ⛔ **真正的 JSON schema 约束。** Copilot 没有约束解码；它可能多一列、少一列、改列名。固定列的 Markdown 表 + 示例是最接近的，出错时你在 Excel 里会立刻看到列错位。
- ⛔ **批量无人值守。** 10 份 RFP × 每份十几块，是上百次手工粘贴。Agent Builder 不支持自建 Actions（✅），也没有 API 可调。
- 🔍 **页码/行号。** Word 没有固定页码；PDF 的页码和行号是模型"估"的。可靠的定位是章节号、编号、`Starts with`。
- 🔍 **长输出被截断**、**超长文档中间被忽略**（✅ 官方提示）。靠小块和 `Last item` 行发现。
- 🔍 **数据治理。** 见第 1 节第 9 条；你的租户可能禁用文件上传或代码解释器。
- ⛔ **Jev 之类的外部判断模型**用不上：Copilot 里不能调外部 API，数据也不该出你的租户。

---

## 8. 用本仓库的合成数据在 Copilot 里做一次评测（10 分钟）

目的：知道你的 Copilot 在这类文件上大概是什么水平，再决定要不要信它。数据是合成的，可以放心上传。

1. 取 `data/synthetic/rfps/` 里的 `northfield-fleet-telematics.docx`、`foothills-student-information-system.pdf`、`bow-river-fare-questionnaire.xlsx`（这三份是开发集；测试集见 `data/synthetic/manifest.json`）。
2. 按第 3 节分块，P1 抽取，把所有块的表粘到 Excel 的 sheet `Pred`（`C` 列是 Text）。
3. 把 `data/synthetic/gold_all.csv` 打开，复制到 sheet `Gold`（`E` 列是 question_text）。
4. 召回（按前 100 个字符近似，不区分大小写，比 PoC 的逐字匹配宽松）：在 `Gold` 的 `K2` 填 `=IF(COUNTIF(Pred!$C:$C,LEFT(E2,100)&"*")>0,1,0)`，下拉，`=AVERAGE(K:K)`。精确率：在 `Pred` 的 `K2` 填 `=IF(COUNTIF(Gold!$E:$E,LEFT(C2,100)&"*")>0,1,0)`，下拉，`=AVERAGE(K:K)`。
   - `COUNTIF` 会把 `?` `*` 当通配符，所以问号结尾的题可能有少量误判；对一次粗评够用。
5. 和 PoC 的数字比（README 里的表）：同一批文件，规则基线 F1 约 0.93，3B 本地模型约 0.9 到 0.95。**你的 Copilot 如果明显低于规则基线，就别用在真实 RFP 上，或者只用来做"第二意见"。**

---

## 9. 推荐的最小工作流（路线 A）

1. 第 1 节验证清单跑一遍（15 分钟），确定路线。
2. 建 agent（第 2 节）。
3. 对每份 RFP：分块（第 3 节）→ P1 → 把表粘进 Excel `All` → J 列公式（第 5 节）→ `CHECK` 的行移到 `REVIEW` → P2 → 追加 MISSING 行并核对 → 填台账 `Log`。
4. 去重、排序、加 Owner/Status，粘进 `.dotx` 模板（第 6 节）。
5. 交给团队前，对每份 RFP 随机抽 10 行对原文，记下改写率；超过 5% 就缩小块再来。

---

### 官方出处（2026-11-02 查阅）

- Agent Builder 字段与限制、响应模式、能力开关：<https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/agent-builder-build-agents>
- 知识来源与上限、嵌入文件的存放与权限、Excel 单 sheet 建议：<https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/agent-builder-add-knowledge>
- 代码解释器（输入格式、可生成可下载文件、仅会话内有效、许可证条件）：<https://learn.microsoft.com/en-us/microsoft-365/copilot/extensibility/code-interpreter>
- 文档长度与注意力：<https://support.microsoft.com/en-us/microsoft-365-copilot/how-reference-and-document-lengths-affect-copilot-responses>

这些页面会更新；其中没写的（沙盒库、输出长度、扫描件、单文件大小）就是上面标 🔍 的项。
