#!/usr/bin/env python3
"""
Parser for the church household ("Member List" with Household Members) PDF report.

Each household is a block: its name, phone and address lines run down the left
column, and its people are listed beside them.

The people column is indented at two levels, and that indent is the whole point
of this report - heads of household sit at the outer level, dependents at the
inner one. That distinction cannot be recovered from ages: 44 dependents in the
sample ward are adults (grown children still at home, up to 33 years old).

A person is written as a bare first name, inheriting the household's surname, or
as "Surname, First [Middle]" when their surname differs.

Usage:
    from utils.pdf_household_list import parse_household_list
    report = parse_household_list(Path('household-list.pdf'))
"""
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.pdf_tables import (
    Word, extract_rows, extract_words, find_header_row, footer_top,
    normalize_name, normalize_phone, print_date,
)

# The household-name line sits a few points above its first member line, so rows
# must be clustered with a tolerance. Without it, the first person of every
# household is attributed to the previous one.
ROW_TOLERANCE = 5.0

# Smallest gap that counts as a real change of indent level. The two levels sit
# about 15pt apart in a 133pt-wide column, so the split has to be derived from
# the indents actually present rather than from a fraction of the column width.
INDENT_MIN_GAP = 6.0

HOUSEHOLD_NAME_RE = re.compile(r"^[A-Z][A-Za-z.'\- ]*,\s")
PHONE_RE = re.compile(r'^\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}$')

HEAD = 'head'
DEPENDENT = 'dependent'


@dataclass
class HouseholdMember:
    """One person as listed inside a household block."""
    raw_name: str                # as printed: "Coral" or "Savage, Landon Scott"
    role: str                    # HEAD or DEPENDENT
    gender: str = ''             # 'M' or 'F'
    printed_age: Optional[int] = None
    full_name: str = ''          # "Last, First", surname resolved
    indent: float = 0.0          # x of the line's leftmost word; sets the role

    @property
    def key(self) -> str:
        return normalize_name(self.full_name)


@dataclass
class HouseholdRecord:
    """One household block."""
    name: str                              # "Anderson, Bryan & Barbara"
    # Captured but not stored anywhere by the import: MLS3 keeps contact details
    # on the member, not the household. It still has to be recognised here,
    # because the phone shares a column with the address lines and would
    # otherwise be read as part of the address.
    phone: str = ''
    address: str = ''                      # newline-joined, as printed
    members: List[HouseholdMember] = field(default_factory=list)

    @property
    def surname(self) -> str:
        return self.name.split(',', 1)[0].strip() if ',' in self.name else self.name.strip()

    @property
    def heads(self) -> List[HouseholdMember]:
        return [m for m in self.members if m.role == HEAD]

    @property
    def head_keys(self) -> frozenset:
        """Identity of the household across imports - see pdf_import."""
        return frozenset(m.key for m in self.heads)


@dataclass
class HouseholdListReport:
    households: List[HouseholdRecord] = field(default_factory=list)
    print_date: str = ''
    warnings: List[str] = field(default_factory=list)

    @property
    def all_members(self) -> List[HouseholdMember]:
        return [m for h in self.households for m in h.members]


def parse_household_list(pdf_path: Path) -> HouseholdListReport:
    """Parse a household-report PDF into HouseholdRecords."""
    pdf_path = Path(pdf_path)
    row_pages = extract_rows(pdf_path, min_cells=3)
    word_pages = extract_words(pdf_path)

    if not row_pages:
        raise ValueError(
            f"{pdf_path.name} does not look like a church report - no table rows "
            f"were found."
        )

    report = HouseholdListReport()
    if word_pages:
        report.print_date = print_date(word_pages[0])

    columns = None
    current: Optional[HouseholdRecord] = None
    address_lines: List[str] = []

    for page_no, (rows, words) in enumerate(zip(row_pages, word_pages), start=1):
        header = find_header_row(rows, words, 'Name')
        if header is None:
            raise ValueError(f"{pdf_path.name}: no column header found on page {page_no}.")

        if columns is None:
            columns = _column_bounds(header, words, pdf_path)

        foot = footer_top(words)
        body = [w for w in words if w.mid_y > header.bottom + 1 and w.y0 < foot - 2]

        for line in _cluster_lines(body):
            household_text, member_words, gender, age = _split_line(line, columns)

            if household_text and HOUSEHOLD_NAME_RE.match(household_text) \
                    and not household_text[0].isdigit():
                if current is not None:
                    current.address = '\n'.join(address_lines)
                current = HouseholdRecord(name=household_text)
                address_lines = []
                report.households.append(current)
            elif household_text and current is not None:
                if not current.phone and PHONE_RE.match(household_text):
                    current.phone = normalize_phone(household_text)
                else:
                    address_lines.append(household_text)

            if current is None or not member_words:
                continue

            # The indent level is taken from the line's leftmost word, never
            # per word: a two-word head-level name ("Samantha Charlene") has its
            # second word past the dependent indent and would otherwise be
            # counted as an extra person.
            raw_name = ' '.join(w.text for w in sorted(member_words, key=lambda w: w.x0))
            member = HouseholdMember(raw_name=raw_name,
                                     role=HEAD,
                                     gender=_gender(gender),
                                     printed_age=_age(age))
            member.indent = min(w.x0 for w in member_words)
            current.members.append(member)

    if current is not None:
        current.address = '\n'.join(address_lines)

    _assign_roles(report)
    _resolve_names(report)
    _validate(report, pdf_path)
    return report


def _column_bounds(header, words: List[Word], pdf_path: Path) -> dict:
    """
    Work out the column boundaries from the header row's cells.

    Expected cells, left to right: Name | Household Members | Gender | Age.
    """
    spans = header.cells
    if len(spans) < 3:
        raise ValueError(
            f"{pdf_path.name}: expected a household report with Name, Household "
            f"Members, Gender and Age columns, but found {len(spans)} columns. "
            f"This looks like the plain member list - upload the household "
            f"report instead."
        )

    labels = []
    for x0, x1 in spans:
        text = ' '.join(
            w.text for w in sorted(
                (w for w in words
                 if header.top - 1 <= w.mid_y <= header.bottom + 1 and x0 <= w.x0 < x1),
                key=lambda w: w.x0)
        ).strip().lower()
        labels.append(text)

    if not any('household' in label for label in labels):
        raise ValueError(
            f"{pdf_path.name} has no 'Household Members' column, so it is the "
            f"plain member list rather than the household report."
        )

    member_span = spans[1]
    return {
        'household': spans[0],
        'member': member_span,
        'gender': spans[2],
        'age': spans[3] if len(spans) > 3 else (spans[2][1], spans[2][1] + 100),
    }


def _cluster_lines(words: List[Word]) -> List[List[Word]]:
    """
    Group words into visual lines, allowing a few points of slack.

    The household name and its first member share a row but sit on slightly
    different baselines, so an exact y match would split them apart.
    """
    clusters: List[List[Word]] = []
    for w in sorted(words, key=lambda w: (w.mid_y, w.x0)):
        if clusters and w.mid_y - clusters[-1][0].mid_y <= ROW_TOLERANCE:
            clusters[-1].append(w)
        else:
            clusters.append([w])
    return clusters


def _split_line(line: List[Word], columns: dict):
    """Split one clustered line into its household / member / gender / age parts."""
    buckets = {'household': [], 'member': [], 'gender': [], 'age': []}
    for w in line:
        for name in ('household', 'member', 'gender', 'age'):
            x0, x1 = columns[name]
            if x0 <= w.x0 < x1:
                buckets[name].append(w)
                break

    household_text = ' '.join(
        w.text for w in sorted(buckets['household'], key=lambda w: w.x0)
    ).strip()
    gender = ' '.join(w.text for w in buckets['gender']).strip()
    age = ' '.join(w.text for w in buckets['age']).strip()
    return household_text, buckets['member'], gender, age


def _gender(value: str) -> str:
    value = value.strip().lower()
    if value.startswith('m'):
        return 'M'
    if value.startswith('f'):
        return 'F'
    return ''


def _age(value: str) -> Optional[int]:
    try:
        return int(value.strip())
    except (TypeError, ValueError):
        return None


def _assign_roles(report: HouseholdListReport) -> None:
    """
    Split members into heads and dependents by their indent.

    The two indent levels are only about 15pt apart, so the boundary is derived
    from the indents the report actually uses: the outer level is the smallest
    indent seen anywhere, and anything meaningfully right of it is a dependent.
    A report with a single level (every household a lone adult) leaves everyone
    a head, which is correct.
    """
    indents = [m.indent for m in report.all_members]
    if not indents:
        return

    outer = min(indents)
    inner = min((i for i in indents if i > outer + INDENT_MIN_GAP), default=None)
    split = (outer + inner) / 2 if inner is not None else outer + INDENT_MIN_GAP

    for member in report.all_members:
        member.role = HEAD if member.indent < split else DEPENDENT


def _resolve_names(report: HouseholdListReport) -> None:
    """
    Give every member a full "Last, First" name.

    A comma in the printed entry means the surname is stated outright (a
    dependent with a different surname, or a head who married in); otherwise the
    household's surname applies.
    """
    for household in report.households:
        for member in household.members:
            if ',' in member.raw_name:
                member.full_name = member.raw_name.strip()
            else:
                member.full_name = f"{household.surname}, {member.raw_name}".strip()


def _validate(report: HouseholdListReport, pdf_path: Path) -> None:
    if not report.households:
        raise ValueError(f"{pdf_path.name}: no households were found in the report.")

    seen = set()
    for household in report.households:
        if not household.members:
            report.warnings.append(f"Household \"{household.name}\" has nobody listed in it.")
        if not household.heads:
            report.warnings.append(
                f"Household \"{household.name}\" has no head of household listed."
            )
        for member in household.members:
            if member.key in seen:
                raise ValueError(
                    f"{pdf_path.name}: {member.full_name} is listed in more than one "
                    f"household. Nothing was imported."
                )
            seen.add(member.key)
            if not member.gender:
                report.warnings.append(f"{member.full_name}: no gender on the report.")


if __name__ == '__main__':
    for arg in sys.argv[1:]:
        result = parse_household_list(Path(arg))
        people = result.all_members
        heads = sum(1 for m in people if m.role == HEAD)
        print(f"{Path(arg).name}: {len(result.households)} households, "
              f"{len(people)} people ({heads} heads, {len(people) - heads} dependents), "
              f"printed {result.print_date}")
        for warning in result.warnings:
            print(f"  warning: {warning}")
