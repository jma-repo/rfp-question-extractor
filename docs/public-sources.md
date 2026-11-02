# Public RFP files: sources and terms

**Status: nothing has been downloaded.** These are candidates found on 2 November 2026, waiting for explicit approval.
If approved, the files go into `data/public/` (git-ignored; the repository never contains them) and this page records what was fetched and when.

The real files have no answer key, so they are not part of the precision/recall numbers. They show what the pipeline does on
documents nobody wrote for it: how many questions it finds, how many fail the verbatim check, and what lands in the review list.

## Terms

All candidates are Government of Canada tender documents published on [CanadaBuys](https://canadabuys.canada.ca) without a login.
The Government of Canada's [Terms and conditions](https://www.canada.ca/en/transparency/terms.html), section *Ownership and usage of content*, say:

- You may reproduce the materials in whole or in part for **non-commercial purposes**, in any format, without charge or further
  permission, provided you exercise due diligence on accuracy, give the full title and author where available, and say that the
  reproduction is a copy of the version available at the original URL.
- Commercial redistribution needs written permission; some content may belong to a third party.

Local, non-commercial testing fits these terms. The files are not redistributed here.

## Candidates (English versions; sizes from the server's `Content-Length` header, files not fetched)

| # | File | Notice | Size | Why it is useful |
|---|---|---|---|---|
| 1 | `Request For Information (RFI) - CITT Online Questionnaire Management Platform.pdf` | 2026-ATSSC-RFI-008, [notice](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-220-95575871) | 735 KB | Request for information with numbered sections and response instructions |
| 2 | `Annex A – Questions to Industry - CITT Online Questionnaire Management Platform .pdf` | same | 448 KB | A list of questions the respondent must answer |
| 3 | `Annex C5 - Copy of NQ-2023-001_ Certification-Attestation.xlsx` | same | 112 KB | A real Excel questionnaire: merged cells, formatting, hidden structure |
| 4 | `BCH2026-10 Request for Proposals - 1495 Heron Road - Mechanical and Electrical Engineer Services.pdf` | BCH2026-10, [notice](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-167-8734223) | 782 KB | A full RFP: mandatory and rated criteria, instructions to proponents, forms |
| 5 | `BCH2026-10 Heron ME Engineering RFP Schedule 10, Exhibit 1-EN V1.0.xlsx` | same | 24 KB | Excel schedule that belongs to the RFP |
| 6 | `CIC-160038 - IRCC Mass Notification System.pdf` | CIC-160038, [notice](https://canadabuys.canada.ca/en/tender-opportunities/tender-notice/cb-487-11071191) | 1,344 KB | An IT bid solicitation: technical requirements, mandatory criteria, pricing tables |

Total about 3.4 MB. No Word files turned up among the open notices checked, so the Word reader is only exercised by the synthetic set.

Direct file URLs are on the notice pages above (`/sites/default/files/webform/tender_notice/...`). The notices are open until
mid-November 2026; CanadaBuys keeps closed notices for a while, but a link can disappear, so the file name and notice number are the stable reference.

## Not used, and why

- **Alberta Purchasing Connection**: documents sit behind a free registration. Creating an account is not something to do for a test.
- **Q&A and amendment PDFs**: they answer bidders' questions rather than ask any.
- **French versions**: the pipeline and the prompts are English-only for now.
