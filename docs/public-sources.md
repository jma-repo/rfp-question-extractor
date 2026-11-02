# Public RFP files: sources, terms, what was fetched

**Status: downloaded on 2 November 2026, after the project owner approved exactly these six files by name, source and size.**
They are in `data/public/`, one folder per file, and that folder is git-ignored: the repository never contains them
(`tests/test_public_files_are_not_tracked.py` checks that). Only this page, with names, sizes and hashes, is committed.

The real files have no answer key, so they are not part of the precision/recall numbers. They show what the pipeline does on
documents nobody wrote for it: how many questions it finds, what lands in the review list, and where it goes wrong (see the README section *On real public files*).

## Terms

All six are Government of Canada tender documents published on [CanadaBuys](https://canadabuys.canada.ca) without a login.
The Government of Canada's [Terms and conditions](https://www.canada.ca/en/transparency/terms.html), section *Ownership and usage of content*, say:

- You may reproduce the materials in whole or in part for **non-commercial purposes**, in any format, without charge or further
  permission, provided you exercise due diligence on accuracy, give the full title and author where available, and say that the
  reproduction is a copy of the version available at the original URL.
- Commercial redistribution needs written permission; some content may belong to a third party.

This use is local, non-commercial testing. The files are not redistributed. Anything quoted from them in the README or in screenshots must name its source.

## What was fetched

English versions only. Sizes are the bytes on disk; they matched the `Content-Length` the server reported before the download.
The first attempt with PowerShell's `Invoke-WebRequest` got HTTP 403 from the server; `curl.exe` (its own, honest User-Agent) got the files.
Each file starts with the right signature (`%PDF-` or `PK`), and none was opened by anything but the extractor's readers.

| # | Local path under `data/public/` | Notice | Bytes | SHA-256 |
|---|---|---|---|---|
| 1 | `01-citt-rfi/citt-rfi-online-questionnaire-management-platform.pdf`, originally *Request For Information (RFI) - CITT Online Questionnaire Management Platform.pdf* | 2026-ATSSC-RFI-008, [notice](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-220-95575871) | 752,675 | `369B01856A01939B53EFF2FA280115CD2A4A99350B8F353C3DB75E630E1895A5` |
| 2 | `02-citt-annex-a-questions-to-industry/citt-annex-a-questions-to-industry.pdf`, originally *Annex A – Questions to Industry - CITT Online Questionnaire Management Platform .pdf* | same | 458,557 | `09DEEB598DA1ABAFAEA831D849218428213461F921F0588BFEEADDE61C25C887` |
| 3 | `03-citt-annex-c5-certification/citt-annex-c5-certification-attestation.xlsx`, originally *Annex C5 - Copy of NQ-2023-001_ Certification-Attestation.xlsx* | same | 115,088 | `1680F22BD259465FF779521E3170787A4ADC86EB37ECCEB4C8A8FAA30D765E57` |
| 4 | `04-bch2026-10-rfp/bch2026-10-request-for-proposals-heron-road.pdf`, originally *BCH2026-10 Request for Proposals - 1495 Heron Road - Mechanical and Electrical Engineer Services.pdf* | BCH2026-10, [notice](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-167-8734223) | 800,960 | `4CD01BCD579CA0BFC0162DBEFDE442F24843BADF72E2826C7260A48B4427767A` |
| 5 | `05-bch2026-10-schedule-10/bch2026-10-schedule-10-exhibit-1-en.xlsx`, originally *BCH2026-10 Heron ME Engineering RFP Schedule 10, Exhibit 1-EN V1.0.xlsx* | same | 24,846 | `DBBBC2286B8A5A101D2316A93B47EBFF2FD20A1D35981E25BFD5699D523B4B7F` |
| 6 | `06-ircc-cic-160038/cic-160038-ircc-mass-notification-system.pdf`, originally *CIC-160038 - IRCC Mass Notification System.pdf* | CIC-160038, [notice](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-487-11071191) | 1,375,998 | `4F8DFB9822713925D6F1051161EC8DD8EDB4D167CE263A5F5F39202D0A09134F` |

Direct file URLs are on the notice pages (`/sites/default/files/webform/tender_notice/...`). The notices close in November 2026;
CanadaBuys keeps closed notices for a while, but a link can disappear, so the file name, notice number and hash are the stable references.
No Word file turned up among the open notices checked, so the Word reader is exercised only by the synthetic set.

## To run the pipeline on them

```bash
uv run rfpx run data/public -r -o out/public-register.docx --extractor rules
```

`-r` reads the subfolders. Keep the downloaded files in their own folders and pass paths as arguments; do not run anything from inside them.

## Not used, and why

- **Alberta Purchasing Connection**: documents sit behind a free registration. Creating an account is not something to do for a test.
- **Q&A and amendment PDFs**: they answer bidders' questions rather than ask any.
- **French versions**: the pipeline and the prompts are English-only for now.
