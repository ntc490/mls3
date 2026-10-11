#!/usr/bin/env python3
"""
Parser for the church "Member List" PDF report.

One row per person. Which columns are present depends on what was selected when
the report was printed, so columns are always derived from the report's own
header row rather than hardcoded.

Required columns:  Name, Gender, Birth Date
Used when present: Phone Number
Read as a check:   Age (compared against the age computed from Birth Date)
Ignored:           Address, Email

Usage:
    from utils.pdf_member_list import parse_member_list
    report = parse_member_list(Path('member-list.pdf'))
"""
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.pdf_tables import (
    Word, add_edge_bands, assign_to_cells, extract_rows, extract_words,
    fill_row_gaps, find_header_row, footer_top, join_cell, label_columns,
    normalize_name, normalize_phone, print_date,
)

# Header text (lowercased) -> internal field name.
COLUMN_ALIASES = {
    'name': 'name',
    'gender': 'gender',
    'age': 'age',
    'birth date': 'birth_date',
    'phone number': 'phone',
    'phone': 'phone',
    'email': 'email',
    'e-mail': 'email',
    'address': 'address',
}

REQUIRED_COLUMNS = ('name', 'gender', 'birth_date')

# Header labels shown to the user when a required column is missing.
COLUMN_DISPLAY = {'name': 'Name', 'gender': 'Gender', 'birth_date': 'Birth Date'}

_COUNT_RE = re.compile(r'Count:\s*(\d+)')


@dataclass
class MemberRecord:
    """One person as printed on the member list."""
    name: str                       # "Last, First [Middle]" as printed
    gender: str                     # 'M' or 'F'
    birth_date: str                 # ISO, YYYY-MM-DD
    phone: str = ''
    printed_age: Optional[int] = None
    raw_birth_date: str = ''        # as printed, e.g. "5 Dec 1953"

    @property
    def last_name(self) -> str:
        return self.name.split(',', 1)[0].strip() if ',' in self.name else self.name.strip()

    @property
    def first_name(self) -> str:
        return self.name.split(',', 1)[1].strip() if ',' in self.name else ''

    @property
    def key(self) -> str:
        return normalize_name(self.name)

    def computed_age(self, today: date = None) -> Optional[int]:
        if not self.birth_date:
            return None
        try:
            born = datetime.strptime(self.birth_date, '%Y-%m-%d').date()
        except ValueError:
            return None
        today = today or date.today()
        return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


@dataclass
class MemberListReport:
    """Everything read from one member-list PDF."""
    members: List[MemberRecord] = field(default_factory=list)
    declared_count: Optional[int] = None
    columns: List[str] = field(default_factory=list)
    print_date: str = ''
    warnings: List[str] = field(default_factory=list)

    @property
    def printed_on(self) -> Optional[date]:
        """
        The day the report was printed, as a date.

        Ages must be checked against this and not against today: the Age column
        was correct when the report was printed, and anyone with a birthday
        since then will legitimately disagree with the age computed now.
        """
        try:
            return datetime.strptime(self.print_date.strip(), '%d %b %Y').date()
        except ValueError:
            return None


def parse_birth_date(value: str) -> str:
    """Convert "5 Dec 1953" to ISO. Returns '' when unparseable."""
    value = (value or '').strip()
    if not value:
        return ''
    for fmt in ('%d %b %Y', '%d %B %Y', '%b %d, %Y', '%B %d, %Y'):
        try:
            return datetime.strptime(value, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return ''


def parse_gender(value: str) -> str:
    """Normalize the gender cell to 'M' / 'F'."""
    value = (value or '').strip().lower()
    if value.startswith('m'):
        return 'M'
    if value.startswith('f'):
        return 'F'
    return ''


def parse_member_list(pdf_path: Path) -> MemberListReport:
    """Parse a member-list PDF into MemberRecords."""
    pdf_path = Path(pdf_path)
    row_pages = extract_rows(pdf_path)
    word_pages = extract_words(pdf_path)

    if not row_pages:
        raise ValueError(
            f"{pdf_path.name} does not look like a church report - no table rows "
            f"were found. Make sure it was printed (saved as PDF) from the "
            f"member list page."
        )
    if len(row_pages) != len(word_pages):
        raise ValueError(
            f"{pdf_path.name}: found {len(row_pages)} table pages but "
            f"{len(word_pages)} text pages. The file may be damaged."
        )

    report = MemberListReport()
    columns = None
    pages: List[List[dict]] = []

    for page_no, (rows, words) in enumerate(zip(row_pages, word_pages), start=1):
        header = find_header_row(rows, words, 'Name')
        if header is None:
            raise ValueError(f"{pdf_path.name}: no column header found on page {page_no}.")

        if columns is None:
            columns = label_columns(header, words, COLUMN_ALIASES)
            report.columns = [label for _, _, label in columns]
            _check_required_columns(report.columns, pdf_path)

        foot = footer_top(words)
        table_top = header.bottom
        body = [w for w in words
                if w.mid_y > table_top + 1 and w.y0 < foot - 2 and w.x0 >= columns[0][0]]

        bands = fill_row_gaps([r for r in rows if r.bottom > table_top + 1])
        bands = add_edge_bands(bands, body, table_top, foot)

        page_rows = []
        for cell in assign_to_cells(body, bands, columns):
            row = {label: join_cell(words_in, label) for label, words_in in cell.items()}
            page_rows.append({k: v for k, v in row.items() if v})
        pages.append(page_rows)

    if not report.print_date and word_pages:
        report.print_date = print_date(word_pages[0])

    report.declared_count = _take_declared_count(pages)
    raw_rows = _stitch_page_breaks(pages)

    for raw in raw_rows:
        record = _build_record(raw, report.warnings)
        if record:
            report.members.append(record)

    _validate(report, pdf_path)
    return report


def _check_required_columns(columns: List[str], pdf_path: Path) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in columns]
    if missing:
        names = ', '.join(COLUMN_DISPLAY[c] for c in missing)
        raise ValueError(
            f"{pdf_path.name} is missing required column(s): {names}. "
            f"Turn those columns on when printing the member list, then print it again."
        )


def _take_declared_count(pages: List[List[dict]]) -> Optional[int]:
    """
    Pull the "Count: N" total off the end of the report.

    It is printed in the last row's name cell, so it must be stripped before the
    row is read as a person.
    """
    for page in pages:
        for row in page:
            match = _COUNT_RE.search(row.get('name', ''))
            if match:
                row['name'] = row['name'][:match.start()].strip()
                if not row['name']:
                    row.pop('name')
                return int(match.group(1))
    return None


def _stitch_page_breaks(pages: List[List[dict]]) -> List[dict]:
    """
    Rejoin rows split across a page break.

    A tall row can have its cells land on different pages - the name on one page
    and the address on the next, or the reverse. Direction matters: a fragment
    with no name at the BOTTOM of a page belongs to the next page's first row,
    while one at the TOP belongs to the previous page's last row.

    Merging the wrong way silently fuses two people into a single record with
    doubled fields and raises no error, so this is covered by tests.
    """
    out: List[dict] = []
    carry: Optional[dict] = None

    for page in pages:
        for index, row in enumerate(page):
            if not row:
                continue

            if carry is not None:
                for key, value in carry.items():
                    row[key] = _merge_values(value, row.get(key, ''), key)
                carry = None

            if not row.get('name'):
                if index == len(page) - 1:
                    carry = row          # continues onto the next page
                    continue
                if out:
                    for key, value in row.items():
                        out[-1][key] = _merge_values(out[-1].get(key, ''), value, key)
                    continue
            out.append(row)

    if carry:
        out.append(carry)
    return [row for row in out if row.get('name')]


def _merge_values(first: str, second: str, key: str) -> str:
    if not first:
        return second
    if not second:
        return first
    return (first + second) if key == 'email' else (first + ' ' + second).strip()


def _build_record(raw: dict, warnings: List[str]) -> Optional[MemberRecord]:
    name = raw.get('name', '').strip()
    if not name:
        return None

    birth_raw = raw.get('birth_date', '').strip()
    birth_iso = parse_birth_date(birth_raw)
    if birth_raw and not birth_iso:
        warnings.append(f"{name}: could not read birth date \"{birth_raw}\".")

    printed_age = None
    age_raw = raw.get('age', '').strip()
    if age_raw:
        try:
            printed_age = int(age_raw)
        except ValueError:
            warnings.append(f"{name}: could not read age \"{age_raw}\".")

    record = MemberRecord(
        name=name,
        gender=parse_gender(raw.get('gender', '')),
        birth_date=birth_iso,
        phone=normalize_phone(raw.get('phone', '')),
        printed_age=printed_age,
        raw_birth_date=birth_raw,
    )
    if not record.gender:
        warnings.append(f"{name}: no gender on the report.")
    return record


def _validate(report: MemberListReport, pdf_path: Path) -> None:
    """Check the parse against what the report says about itself."""
    if report.declared_count is not None and len(report.members) != report.declared_count:
        raise ValueError(
            f"{pdf_path.name}: read {len(report.members)} people but the report "
            f"says there are {report.declared_count}. Nothing was imported. "
            f"Please re-print the report and try again."
        )

    duplicates = _duplicate_keys(report.members)
    if duplicates:
        raise ValueError(
            f"{pdf_path.name}: the same name appears more than once "
            f"({', '.join(duplicates[:3])}). Nothing was imported."
        )

    # Printed age is redundant with birth date; disagreement means a misread
    # row. Compared as of the print date, so an old report does not light up
    # with a warning for everyone who has had a birthday since.
    as_of = report.printed_on
    for member in report.members:
        if member.printed_age is None:
            continue
        computed = member.computed_age(as_of)
        if computed is not None and computed != member.printed_age:
            report.warnings.append(
                f"{member.name}: report says age {member.printed_age} but the "
                f"birth date gives {computed}."
            )


def _duplicate_keys(members: List[MemberRecord]) -> List[str]:
    seen, dupes = set(), []
    for member in members:
        if member.key in seen:
            dupes.append(member.name)
        seen.add(member.key)
    return dupes


if __name__ == '__main__':
    for arg in sys.argv[1:]:
        result = parse_member_list(Path(arg))
        print(f"{Path(arg).name}: {len(result.members)} people "
              f"(report says {result.declared_count}), printed {result.print_date}")
        print(f"  columns: {', '.join(result.columns)}")
        for warning in result.warnings:
            print(f"  warning: {warning}")
