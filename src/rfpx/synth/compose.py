"""Turns the wording bank into ten invented RFPs: section structure, numbering, wording, noise and duplicates.

Everything is seeded, so the gold labels are reproducible. The gold is written at the moment each question is placed,
from the same string the writer prints; there is no second pass that could drift from the document.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass

from rfpx.synth import bank
from rfpx.synth.spec import Break, Gold, H, Item, P, Rfp, Tbl, Toc

GROUPS = {
    "experience": ["company_profile", "similar_projects", "references", "team_structure", "key_personnel", "litigation",
                   "conflict", "social_procurement", "alberta_office"],
    "technical": ["integration", "reporting", "scalability", "sso", "audit_log", "licensing", "roadmap", "accessibility"],
    "security": ["security_controls", "iso27001", "data_residency", "privacy_law", "disaster_recovery", "sla_availability"],
    "delivery": ["methodology", "work_plan", "timeline", "risks", "testing", "data_migration", "training",
                 "change_management", "support_model", "warranty", "exit", "subcontractors"],
    "attachments": ["insurance", "wcb", "financials", "soc2"],
    "pricing": ["pricing_schedule", "pricing_assumptions", "rate_card", "price_hold", "escalation"],
}
BY_KEY = {item.key: item for item in bank.GENERAL}
_LEADING_VERB = re.compile(r"^(Describe|Provide|State|List|Identify|Explain|Disclose|Confirm|Attach|Complete)\b")

BACKGROUND = (
    "{issuer_c} is seeking proposals from qualified organizations to supply and implement a {solution}. The current arrangements "
    "have been in place for more than ten years and no longer meet operational needs.",
    "The selected Proponent will work with a project team drawn from several departments. The estimated budget for the first "
    "three years, including licences, implementation and support, is between $1.2 million and $2.4 million.",
    "This RFP was prepared for testing document-processing software. It is not a real solicitation and no contract will be awarded.",
    "{issuer_c} operates in a mixed urban and rural region and serves approximately 180,000 residents. Services are delivered from "
    "six locations and, increasingly, online.",
    "The successful Proponent will be expected to begin work within 30 days of contract award. A phased implementation is preferred.",
    "Responses from consortia and joint ventures are welcome, provided that one organization accepts overall responsibility.",
)
PROCEDURAL = (
    "Proposals shall be submitted electronically through the procurement portal no later than the Closing Time.",
    "Proponents must not contact any member of the evaluation committee while this procurement is under way.",
    "{issuer_c} reserves the right to reject any or all Proposals without giving reasons.",
    "Proposals received after the Closing Time will not be considered and will be returned unopened.",
    "Proponents should read this RFP in its entirety before preparing a response.",
    "All prices shall be quoted in Canadian dollars and shall exclude GST.",
    "Questions about this RFP must be submitted in writing to the Procurement Contact before the Question Deadline.",
    "The Proponent shall be responsible for all costs incurred in preparing and submitting a Proposal.",
    "Responses should follow the order and numbering used in this RFP.",
    "Proposals must remain valid for a period of 120 days after the Closing Time.",
    "Addenda will be posted on the portal, and Proponents should check the portal regularly for updates.",
    "This RFP does not commit {issuer} to award a contract.",
    "A Proposal shall not exceed 40 pages, excluding appendices and attachments.",
)
NOTES = (
    "Note: responses to this section should not exceed 15 pages.",
    "Note: a Proponent that does not respond to a mandatory item may be disqualified.",
    "Note: where an item asks for an attachment, the attachment must be named after the item number.",
    "Note: terms in bold have the meanings given in section 1.3.",
)
DEFINITIONS = (
    "\"Closing Time\" means 2:00 p.m. Mountain Time on the closing date shown on the cover page.",
    "\"Proponent\" means an organization that submits a Proposal in response to this RFP.",
    "\"Contractor\" means the Proponent with which {issuer} enters into a contract.",
    "\"Services\" means the services, software and deliverables described in this RFP.",
)
FUNCTIONAL = (
    ("support role-based access control with at least five configurable roles", True),
    ("enforce multi-factor authentication for all administrative users", True),
    ("record every create, update and delete action with the user and time stamp", True),
    ("allow authorized users to export any report to Excel and PDF", True),
    ("provide a documented REST API covering every function available in the user interface", True),
    ("support full-text search across all records the user is permitted to see", True),
    ("send an email notification when a workflow step is assigned to a user", True),
    ("work on current versions of Chrome, Edge, Safari and Firefox without plug-ins", True),
    ("offer a French-language user interface", False),
    ("allow documents of up to 100 MB to be attached to a record", True),
    ("retain deleted records for 30 days before permanent removal", True),
    ("provide bulk import of records from CSV files, listing validation errors by row", True),
    ("allow business users to configure workflow steps without vendor assistance", False),
    ("support electronic signatures that are legally binding in Alberta", False),
    ("mask personal information in non-production environments", True),
    ("allow administrators to define fields and pick lists without code changes", True),
    ("take a daily backup that can be restored to any point within the previous 14 days", True),
    ("support single sign-on with the identity provider used by {issuer}", True),
    ("provide a test environment for trying upgrades before they reach production", True),
    ("support at least 500 named users at the same time without degradation", True),
    ("provide an administrator dashboard showing system health and usage", True),
    ("allow all data to be extracted in a documented, non-proprietary format at any time", True),
    ("support retention rules that can be set by record type", True),
    ("provide read-only access for auditors", True),
    ("provision users automatically from Microsoft Entra ID", False),
    ("include an in-application help system", False),
    ("validate Canadian postal codes and street addresses", True),
    ("allow users to save and share filtered views", False),
    ("provide a mobile application for iOS and Android", False),
)
COMPOSITES = (
    ("In its response to this section, the Proponent shall address each of the following:", (
        ("Describe how administrative access to production systems is controlled and logged.", "narrative"),
        ("Describe how security events are monitored and who responds outside business hours.", "narrative"),
        ("State whether penetration testing is performed by an independent party. (Yes/No)", "yes_no"),
    )),
    ("The implementation plan must cover the following:", (
        ("Provide a high-level schedule showing the main phases and their durations.", "table"),
        ("Identify the tasks that need the participation of staff of {issuer}.", "narrative"),
        ("Describe how scope changes will be handled during implementation.", "narrative"),
        ("Attach a sample status report from a comparable project.", "upload"),
    )),
    ("Support for the {solution} is to be described as follows:", (
        ("Describe the channels through which users can request support.", "narrative"),
        ("State the target response and resolution times for each severity level.", "narrative"),
        ("Confirm that support is available on statutory holidays. (Yes/No)", "yes_no"),
    )),
)
EVALUATION = (("Corporate experience", "15"), ("Technical approach", "35"), ("Implementation and support", "15"),
              ("Security and privacy", "15"), ("Price", "20"))
TIMELINE = (("RFP issued", "{y}-10-05"), ("Question deadline", "{y}-10-23"), ("Addendum issued", "{y}-10-28"),
            ("Closing Time", "{y}-11-06"), ("Contract award (target)", "{y}-12-15"))
PRICING_ROWS = (("Software licences (annual)", "1"), ("Implementation services", "1"), ("Data migration", "1"),
                ("Training (per day)", "10"), ("Annual support and maintenance", "5"), ("Optional: additional environments", "2"))


@dataclass(frozen=True)
class Plan:
    slug: str
    title: str
    theme: str
    fmt: str
    layout: str            # outline | matrix | alpha | flat | security | xmatrix
    numbering: str         # legal | flat | alpha | req
    style: str             # modal | mixed | plain
    split: str
    seed: int
    number: str
    issuer_name: str
    running_header: bool = True
    body_page_noise: bool = False
    messy: float = 0.0                       # share of items worded in the indirect register (passive, nominal, "Please ...")
    matrix_header: tuple[str, ...] | None = None


PLANS: tuple[Plan, ...] = (
    Plan("northfield-fleet-telematics", "Fleet Telematics Services", "fleet", "docx", "outline", "legal", "modal", "dev", 101,
         "RFP-2026-017", "City of Northfield", messy=0.3),
    Plan("prairie-health-scheduling", "Patient Scheduling and Reminder System", "scheduling", "docx", "outline", "legal", "mixed",
         "test", 102, "PHA-2026-044", "Prairie Health Authority", body_page_noise=True, messy=0.4),
    Plan("lakeshore-billing-modernization", "Customer Billing Modernization", "billing", "docx", "matrix", "req", "mixed",
         "test", 103, "LU-2026-009", "Lakeshore Utilities", messy=0.3),
    Plan("mountain-view-records", "Electronic Records Management", "records", "docx", "flat", "none", "plain", "test", 104,
         "MVC-2026-031", "Mountain View County", messy=0.45),
    Plan("foothills-student-information-system", "Student Information System", "sis", "pdf", "outline", "legal", "mixed",
         "dev", 105, "FSD-2026-006", "Foothills School Division", messy=0.3),
    Plan("westland-cloud-hosting", "Managed Cloud Hosting", "cloud", "pdf", "matrix", "req", "modal", "test", 106,
         "GW-ITS-2026-122", "Government of Westland", messy=0.25,
         matrix_header=("No.", "Service capability", "M/D", "Compliance", "Vendor comments")),
    Plan("capital-library-digital-content", "Digital Content Lending Platform", "library", "pdf", "alpha", "bullet", "plain",
         "test", 107, "CRLC-2026-003", "Capital Region Library Consortium", messy=0.4),
    Plan("bow-river-fare-questionnaire", "Fare Payment Platform", "fare", "xlsx", "flat", "flat", "plain", "dev", 108,
         "BRT-2026-012", "Bow River Transit", messy=0.35),
    Plan("northern-lights-security-assessment", "Vendor Security Assessment", "energy", "xlsx", "security", "flat", "plain",
         "test", 109, "NLE-VSA-2026", "Northern Lights Energy"),
    Plan("tri-valley-housing-requirements", "Property Management System", "housing", "xlsx", "xmatrix", "req", "plain", "test", 110,
         "TVH-2026-021", "Tri-Valley Housing Corporation"),
)


class Builder:
    def __init__(self, plan: Plan, theme: bank.Theme):
        self.plan, self.theme = plan, theme
        self.rng = random.Random(plan.seed)
        self.elements: list = []
        self.section = ""                # heading text as printed, used as the gold `section`
        self._sec_no = ""
        self._counter = 0
        self._global = 0
        self._used: set[str] = set()
        self._negatives: set[str] = set()
        self.matrix_used: set[str] = set()
        self.golds: dict[str, list[Gold]] = {}

    # --- text ---------------------------------------------------------------------------------
    def fill(self, text: str, **extra: str) -> str:
        return text.format(solution=self.theme.solution, data=self.theme.data, issuer=self.theme.issuer,
                           issuer_c=self.theme.issuer[0].upper() + self.theme.issuer[1:], y=2026, **extra)

    def indirect(self, item: bank.Item) -> list[str]:
        """Wordings with no leading verb or modal: hand-written passives where they read naturally, else 'Please ...'."""
        if item.key in bank.ALT:
            return [self.fill(f) for f in bank.ALT[item.key]]
        base = self.fill(item.plain[0])
        match = _LEADING_VERB.match(base)
        if not match:
            return []
        lowered = base[0].lower() + base[1:]
        forms = [f"Please {lowered}"]
        if match.group(1) not in ("Attach", "Complete") and not re.search(r"\byou(r)?\b", base):
            forms.append(f"Proponent to {lowered}")
        return forms

    def wording(self, item: bank.Item, required: bool, style: str | None = None) -> str:
        style = style or self.plan.style
        if style == self.plan.style and self.plan.messy and self.rng.random() < self.plan.messy:
            forms = self.indirect(item)
            if forms:
                text = self.rng.choice(forms)
                return text if required else f"(Optional) {text}"
        use_modal = style == "modal" or (style == "mixed" and self.rng.random() < 0.55)
        if use_modal:
            modal = self.rng.choice(["shall", "must"]) if required else "should"
            return self.fill(item.modal, M=modal)
        text = self.fill(self.rng.choice(item.plain))
        return text if required else f"({self.rng.choice(['Optional', 'Desirable'])}) {text}"

    # --- structure ----------------------------------------------------------------------------
    def head(self, level: int, title: str, number: str | None = None) -> None:
        text = f"{number} {title}" if number else title
        self.elements.append(H(level, text))
        if level <= 2:
            self.section = text
            self._sec_no = number.rstrip(".") if number else ""
            self._counter = 0

    def para(self, text: str, role: str = "background") -> None:
        self.elements.append(P(self.fill(text), role))

    def label(self) -> tuple[str | None, str | None]:
        """(what is printed in front of the item, the id the answer key expects)."""
        self._counter += 1
        self._global += 1
        scheme = self.plan.numbering
        if scheme == "none":
            return None, None
        if scheme == "bullet":
            return "•", None
        if scheme == "legal":
            printed = f"{self._sec_no}.{self._counter}" if self._sec_no else str(self._counter)
        elif scheme == "flat":
            printed = f"Q{self._global}"
        elif scheme == "alpha":
            printed = f"{self._sec_no or 'A'}.{self._counter}"
        else:
            printed = f"R-{self._global:03d}"
        return printed, printed

    def item(self, item: bank.Item, required: bool = True, text: str | None = None, type_: str | None = None,
             dup: str | None = None, constraints: str | None = None) -> Gold:
        wording = text or self.wording(item, required)
        printed, ident = self.label()
        gold = Gold(ident, self.section, wording, type_ or item.type, required,
                    item.constraint if constraints is None else constraints, dup)
        self.elements.append(Item(gold, printed))
        self.golds.setdefault(item.key, []).append(gold)
        return gold

    def hard_negative(self) -> None:
        """A procedural sentence that borrows the wording of a question but asks the vendor for no answer."""
        pool = [t for t in bank.HARD_NEGATIVES if t not in self._negatives]
        text = self.rng.choice(pool)
        self._negatives.add(text)
        self.elements.append(P(text, "procedural"))

    def sub_items(self, rows: list[tuple[str, str]], required: bool = True) -> None:
        for letter, (raw, kind) in zip("abcdefgh", rows, strict=False):
            self._global += 1
            text = self.fill(raw)
            if not required and not text.startswith("("):
                text = f"(Optional) {text}"
            gold = Gold(f"({letter})", self.section, text, kind, required, "", None)
            self.elements.append(Item(gold, gold.id, level=1))

    def take(self, group: str, count: int, exclude: set[str] | None = None) -> list[bank.Item]:
        pool = [BY_KEY[k] for k in GROUPS[group] if k not in self._used and k not in (exclude or set())]
        self.rng.shuffle(pool)
        chosen = pool[:count]
        self._used.update(i.key for i in chosen)
        return chosen


def _intro(b: Builder, plan: Plan) -> None:
    b.head(1, "Introduction", "1.")
    b.head(2, "Background", "1.1")
    b.para(b.rng.choice(BACKGROUND))
    b.para(BACKGROUND[2])
    b.head(2, "Purpose of this RFP", "1.2")
    b.para("The purpose of this RFP is to select a Contractor to supply, implement and support a {solution}.")
    b.head(2, "Definitions", "1.3")
    for d in DEFINITIONS[: 3 + b.rng.randint(0, 1)]:
        b.para(d, "definition")


def _instructions(b: Builder, plan: Plan) -> None:
    b.head(1, "Instructions to Proponents", "2.")
    b.head(2, "Submission of Proposals", "2.1")
    for text in b.rng.sample(PROCEDURAL, 4):
        b.para(text, "procedural")
    b.head(2, "Questions and Addenda", "2.2")
    for text in b.rng.sample(PROCEDURAL[6:12], 2):
        b.para(text, "procedural")
    b.head(2, "Evaluation", "2.3")
    b.para("Proposals will be evaluated against the criteria and weights below.")
    b.elements.append(Tbl("evaluation", ["Evaluation criteria", "Weight (%)"], [list(r) for r in EVALUATION]))
    b.head(2, "Timeline", "2.4")
    b.elements.append(Tbl("timeline", ["Event", "Date"], [[e, b.fill(d)] for e, d in TIMELINE]))


def _scope(b: Builder) -> None:
    b.head(1, "Scope of Services", "3.")
    b.para("The Contractor will supply a {solution} and the services needed to implement it, train staff and support it after go-live.")
    b.para("The Services are described in more detail in the requirements that follow. {issuer_c} may change the scope before award.")


def _pricing_table() -> Tbl:
    rows = [[str(i + 1), name, qty, "", ""] for i, (name, qty) in enumerate(PRICING_ROWS)]
    rows.append(["", "Total (CAD, excluding GST)", "", "", ""])
    return Tbl("pricing", ["Item", "Description", "Qty", "Unit price (CAD)", "Extended price (CAD)"], rows)


def _duplicates(b: Builder) -> None:
    """Ask a few things twice, later in the document: the first word for word, the others reworded."""
    candidates = [k for k in ("references", "support_model", "security_controls", "key_personnel", "data_migration", "training",
                              "methodology", "disaster_recovery") if k in b.golds]
    b.rng.shuffle(candidates)
    for n, key in enumerate(candidates[:3]):
        original = b.golds[key][0]
        item = BY_KEY[key]
        text = original.question_text if n == 0 else _paraphrase(b, item, original)
        b.item(item, original.required, text=text, type_=original.type, dup=key)
        original.dup_group = key


def _paraphrase(b: Builder, item: bank.Item, original: Gold) -> str:
    """The same ask in the other register: the modal sentence becomes the imperative and the imperative the modal sentence."""
    if re.search(r"\b(shall|must|should)\b", original.question_text):
        text = b.fill(item.plain[0])
        return text if original.required else f"(Optional) {text}"
    return b.fill(item.modal, M="shall" if original.required else "should")


def outline(plan: Plan, theme: bank.Theme) -> Rfp:
    b = Builder(plan, theme)
    b.elements.append(Toc())
    _intro(b, plan)
    _instructions(b, plan)
    _scope(b)
    b.elements.append(Break())
    b.head(1, "Proposal Requirements", "4.")
    b.para("Proponents shall respond to every item in this section, in the order shown.", "procedural")
    b.hard_negative()
    b.head(2, "Corporate Experience", "4.1")
    for it in b.take("experience", 5):
        b.item(it, True)
    b.head(2, "Technical Approach", "4.2")
    for it in b.take("technical", 3):
        b.item(it, True)
    for it in theme.specific:
        b.item(it, required=b.rng.random() < 0.75)
    b.para(NOTES[0], "note")
    b.head(2, "Security and Privacy", "4.3")
    for it in b.take("security", 4):
        b.item(it, True)
    lead, rows = COMPOSITES[0]
    b.para(lead, "lead")
    b.sub_items(list(rows))
    b.head(2, "Implementation and Support", "4.4")
    for it in b.take("delivery", 6):
        b.item(it, True)
    lead, rows = COMPOSITES[1]
    b.para(lead, "lead")
    b.sub_items(list(rows))
    b.head(2, "Value-Added Services (Desirable)", "4.5")
    b.para("The following items are desirable. Responses to them will be scored but are not mandatory.", "note")
    for it in b.take("delivery", 2) + b.take("technical", 1):
        b.item(it, False)
    b.head(2, "Required Attachments", "4.6")
    for it in b.take("attachments", 3):
        b.item(it, True)
    b.hard_negative()
    b.head(1, "Pricing", "5.")
    b.para(NOTES[3], "note")
    b.head(2, "Pricing Requirements", "5.1")
    for it in b.take("pricing", 4):
        b.item(it, True)
    b.hard_negative()
    b.elements.append(_pricing_table())
    b.head(1, "Appendices", "6.")
    b.head(2, "Appendix A - Mandatory Requirements Checklist", "6.1")
    b.para("Mark each requirement Yes or No. A No against a mandatory requirement may result in disqualification.", "note")
    _matrix(b, 6, prefix="A-")
    _duplicates(b)
    b.head(2, "Appendix B - Reference Form", "6.2")
    b.elements.append(Tbl("form", ["Reference", "Organization", "Contact name", "Telephone", "Project and value"],
                          [["1", "", "", "", ""], ["2", "", "", "", ""], ["3", "", "", "", ""]]))
    return _finish(b, plan, "outline")


def _matrix(b: Builder, count: int, prefix: str = "R-", header: list[str] | None = None,
            labels: tuple[str, str] = ("Mandatory", "Desirable")) -> Tbl:
    """A compliance matrix: one requirement per row, with a Mandatory/Desirable column and empty response columns."""
    pool = [row for row in FUNCTIONAL if b.fill(row[0]) not in b.matrix_used]
    b.rng.shuffle(pool)
    rows, golds = [], []
    for text, required in pool[:count]:
        b._global += 1
        b.matrix_used.add(b.fill(text))
        statement = f"The {b.theme.solution} {'shall' if required else 'should'} {b.fill(text)}."
        ident = f"{prefix}{b._global:03d}"
        golds.append(Gold(ident, b.section, statement, "yes_no", required))
        rows.append([ident, statement, labels[0] if required else labels[1], "", ""])
    header = header or list(b.plan.matrix_header or ("Req #", "Requirement", "Mandatory / Desirable", "Complies (Yes/No)", "Comments"))
    table = Tbl("matrix", header, rows, golds, qcol=1)
    b.elements.append(table)
    return table


def matrix_layout(plan: Plan, theme: bank.Theme) -> Rfp:
    """Requirement matrices carry most of the questions; a narrative section and an attachments list carry the rest."""
    b = Builder(plan, theme)
    b.elements.append(Toc())
    b.head(1, "Introduction", "1.")
    b.para(b.rng.choice(BACKGROUND))
    b.para(BACKGROUND[2])
    b.head(1, "Instructions to Proponents", "2.")
    for text in b.rng.sample(PROCEDURAL, 4):
        b.para(text, "procedural")
    b.elements.append(Tbl("timeline", ["Event", "Date"], [[e, b.fill(d)] for e, d in TIMELINE]))
    b.elements.append(Break())
    b.head(1, "Functional Requirements", "3.")
    b.para("Complete the Complies column for every requirement. Mandatory requirements must be met at go-live.", "note")
    b.head(2, "General Functionality", "3.1")
    _matrix(b, 8)
    b.head(2, "Administration and Security", "3.2")
    _matrix(b, 8)
    b.head(1, "Vendor Information", "4.")
    b.para("Provide the following information in narrative form. Responses to this section should not exceed 15 pages.", "note")
    b.head(2, "Experience and Delivery", "4.1")
    for it in b.take("experience", 3) + list(theme.specific[:3]):
        b.item(it, required=True)
    b.head(2, "Attachments and Pricing", "4.2")
    for it in b.take("attachments", 2) + b.take("pricing", 2):
        b.item(it, required=True)
    b.hard_negative()
    b.elements.append(_pricing_table())
    _duplicates(b)
    return _finish(b, plan, "matrix")


def alpha_layout(plan: Plan, theme: bank.Theme) -> Rfp:
    b = Builder(plan, theme)
    b.elements.append(Toc())
    b.head(1, "General Information", "A.")
    b.para(b.rng.choice(BACKGROUND))
    for text in b.rng.sample(PROCEDURAL, 4):
        b.para(text, "procedural")
    b.head(1, "Proponent Qualifications", "B.")
    for it in b.take("experience", 5):
        b.item(it, True)
    b.head(1, "Solution Description", "C.")
    for it in b.take("technical", 3):
        b.item(it, True)
    for it in theme.specific:
        b.item(it, required=b.rng.random() < 0.8)
    lead, rows = COMPOSITES[2]
    b.para(lead, "lead")
    b.sub_items(list(rows))
    b.head(1, "Security and Hosting", "D.")
    for it in b.take("security", 5):
        b.item(it, True)
    lead, rows = COMPOSITES[0]
    b.para(lead, "lead")
    b.sub_items(list(rows))
    b.head(1, "Delivery and Support", "E.")
    for it in b.take("delivery", 5):
        b.item(it, True)
    b.head(1, "Commercial", "F.")
    for it in b.take("pricing", 4) + b.take("attachments", 2):
        b.item(it, True)
    b.hard_negative()
    b.elements.append(_pricing_table())
    _duplicates(b)
    return _finish(b, plan, "alpha")


def flat_layout(plan: Plan, theme: bank.Theme) -> Rfp:
    """One numbered list of questions under a few headings (Word/PDF), or one questionnaire sheet (Excel)."""
    b = Builder(plan, theme)
    if plan.fmt != "xlsx":
        b.elements.append(Toc())
    b.head(1, "About this Request", None)
    b.para(b.rng.choice(BACKGROUND))
    for text in b.rng.sample(PROCEDURAL, 3):
        b.para(text, "procedural")
    for title, group, count in (("Company and Experience", "experience", 5), ("Solution", "technical", 3),
                                ("Security, Privacy and Hosting", "security", 4), ("Delivery and Support", "delivery", 5),
                                ("Pricing and Attachments", "pricing", 4)):
        b.head(1, title, None)
        chosen = b.take(group, count)
        if group == "technical":
            chosen += list(theme.specific)
        if group == "pricing":
            chosen += b.take("attachments", 2)
        for it in chosen:
            b.item(it, required=b.rng.random() < 0.85)
        if group in ("delivery", "pricing"):
            b.hard_negative()
    if plan.fmt != "xlsx":
        b.elements.append(_pricing_table())
    _duplicates(b)
    return _finish(b, plan, "flat")


def security_layout(plan: Plan, theme: bank.Theme) -> Rfp:
    """Excel security questionnaire: categories as banner rows, mostly Yes/No, one repeated and one reworded question."""
    b = Builder(plan, theme)
    first_of: dict[str, Gold] = {}
    b.para("Vendors must answer every question. An answer of N/A must be explained in the comments column.", "procedural")
    b.para("Responses form part of the contract and the vendor shall notify {issuer} of any material change to them.", "procedural")
    b.para(b.rng.choice(PROCEDURAL), "procedural")

    def add(text: str, kind: str, required: bool, dup: str | None = None) -> None:
        b._global += 1
        gold = Gold(f"S{b._global}", b.section, text, kind, required, "", dup)
        b.elements.append(Item(gold, gold.id))
        first_of.setdefault(text, gold)

    for category, rows in bank.SECURITY.items():
        b.head(2, category, None)
        for text, kind in rows:
            add(text, kind, kind != "upload" or b.rng.random() < 0.5)
    b.head(2, "Additional questions", None)
    encryption = bank.SECURITY["Encryption"][0][0]
    first_of[encryption].dup_group = "encryption_at_rest"
    add(encryption, "yes_no", True, "encryption_at_rest")
    mfa = bank.SECURITY["Access control"][0][0]
    first_of[mfa].dup_group = "mfa"
    add("Is multi-factor authentication enforced for every administrator account?", "yes_no", True, "mfa")
    return _finish(b, plan, "security")


def xmatrix_layout(plan: Plan, theme: bank.Theme) -> Rfp:
    """Excel requirements matrix with category banner rows, M/D column and a pricing sheet."""
    b = Builder(plan, theme)
    for title, count in (("Core functionality", 8), ("Administration", 6), ("Integration and reporting", 6)):
        b.head(2, title, None)
        _matrix(b, count, header=["Req ID", "Requirement", "M/D", "Compliance (Y/P/N)", "Comments"], labels=("M", "D"))
    b.head(2, "Vendor questions", None)
    for it in list(theme.specific) + b.take("delivery", 3) + b.take("pricing", 2):
        b.item(it, required=True)
    b.elements.append(_pricing_table())
    return _finish(b, plan, "xmatrix")


def _finish(b: Builder, plan: Plan, layout: str) -> Rfp:
    return Rfp(plan.slug, plan.title, plan.issuer_name, plan.number, plan.fmt, plan.split, layout, "2026-11-06 14:00 MT",
               elements=b.elements, running_header=plan.running_header, body_page_noise=plan.body_page_noise)


COMPOSERS = {"outline": outline, "matrix": matrix_layout, "alpha": alpha_layout, "flat": flat_layout,
             "security": security_layout, "xmatrix": xmatrix_layout}


def compose(plan: Plan) -> Rfp:
    theme = next(t for t in bank.THEMES if t.slug == plan.theme)
    return COMPOSERS[plan.layout](plan, theme)
