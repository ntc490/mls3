#!/usr/bin/env python3
"""
Low-level PDF table extraction for MLS3 imports.

Report-agnostic helpers shared by the member-list and household-list parsers.

Both church reports are produced by WeasyPrint, which draws the table's cell
rectangles into the page content stream. A group of rectangles sharing one y and
height is exactly one table row, which gives precise row boundaries without
guessing from text positions. Text itself comes from `pdftotext -bbox` (poppler),
which reports every word with a bounding box but does not report vector graphics
- hence the two sources.

Requires the `pdftotext` binary (Termux: `pkg install poppler`).
"""
import re
import subprocess
import xml.etree.ElementTree as ET
import zlib
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

# Content-stream coordinates are scaled by this factor relative to the
# coordinates pdftotext reports. Both reports set `0.75 0 0 0.75 0 0 cm`.
CONTENT_SCALE = 0.75

# Text below this y on a page is the footer, never table content.
FOOTER_MIN_Y = 600.0

_RECT_RE = re.compile(r'(-?[\d.]+) (-?[\d.]+) (-?[\d.]+) (-?[\d.]+) re')
_STREAM_RE = re.compile(rb'stream\r?\n(.*?)\r?\nendstream', re.S)


class PdfToolMissing(RuntimeError):
    """Raised when the pdftotext binary is not available."""


class Word(NamedTuple):
    """A word with its bounding box, in pdftotext page coordinates."""
    y0: float
    y1: float
    x0: float
    text: str

    @property
    def mid_y(self) -> float:
        return (self.y0 + self.y1) / 2


class Row(NamedTuple):
    """A drawn table row: vertical band plus its cell spans."""
    top: float
    bottom: float
    cells: List[Tuple[float, float]]   # (x0, x1) per cell, left to right


def require_pdftotext() -> None:
    """Raise PdfToolMissing with actionable advice if poppler is absent."""
    try:
        subprocess.run(['pdftotext', '-v'], capture_output=True, check=False)
    except FileNotFoundError:
        raise PdfToolMissing(
            "The 'pdftotext' command is required to import PDF reports but was "
            "not found. Install it with:  pkg install poppler   (Termux)  or  "
            "apt install poppler-utils / pacman -S poppler  (desktop)."
        )


def extract_words(pdf_path: Path) -> List[List[Word]]:
    """Return the words of each page, via `pdftotext -bbox`."""
    require_pdftotext()
    result = subprocess.run(
        ['pdftotext', '-bbox', str(pdf_path), '-'],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        raise ValueError(f"pdftotext failed on {pdf_path.name}: {result.stderr.strip()}")

    # Drop the default namespace so plain tag names work with ElementTree.
    xml = re.sub(r'\sxmlns="[^"]+"', '', result.stdout, count=1)
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        raise ValueError(f"Could not read text from {pdf_path.name}: {e}")

    pages = []
    for page in root.iter('page'):
        words = []
        for w in page.iter('word'):
            text = (w.text or '').strip()
            if not text:
                continue
            words.append(Word(
                y0=float(w.get('yMin')),
                y1=float(w.get('yMax')),
                x0=float(w.get('xMin')),
                text=text,
            ))
        pages.append(words)
    return pages


def extract_rows(pdf_path: Path, min_cells: int = 5) -> List[List[Row]]:
    """
    Return the drawn table rows of each page, from the content streams.

    Only rows with at least `min_cells` distinct cell rectangles are kept, which
    excludes rules, borders and other incidental shapes.
    """
    data = pdf_path.read_bytes()
    pages = []
    for raw in _STREAM_RE.findall(data):
        try:
            stream = zlib.decompress(raw).decode('latin1')
        except (zlib.error, UnicodeDecodeError):
            continue
        if ' re' not in stream:
            continue

        groups: Dict[Tuple[float, float], set] = defaultdict(set)
        for match in _RECT_RE.finditer(stream):
            x, y, w, h = map(float, match.groups())
            groups[(round(y, 2), round(h, 2))].add(
                (round(x * CONTENT_SCALE, 2), round(w * CONTENT_SCALE, 2))
            )

        rows = []
        for (y, h), cells in sorted(groups.items()):
            if len(cells) < min_cells:
                continue
            rows.append(Row(
                top=y * CONTENT_SCALE,
                bottom=(y + h) * CONTENT_SCALE,
                cells=_cell_spans(cells),
            ))
        if rows:
            pages.append(rows)
    return pages


def _cell_spans(cells) -> List[Tuple[float, float]]:
    """
    Convert (x, width) rectangles into (x0, x1) column spans.

    Discards any rectangle that fully contains another - the row-wide background
    is drawn alongside the individual cells and would otherwise swallow every
    column.
    """
    boxes = sorted(cells)
    spans = []
    for x, w in boxes:
        contains_another = any(
            x <= ox and x + w >= ox + ow and (ox, ow) != (x, w)
            for ox, ow in boxes
        )
        if not contains_another:
            spans.append((x, x + w))
    return sorted(set(spans))


def footer_top(words: List[Word]) -> float:
    """
    Y of the page footer, or the page height if there is none.

    The footer is the only text that starts left of the table, but the report
    title block on page 1 does too - so only text low on the page counts.
    """
    candidates = [w.y0 for w in words if w.x0 < 38 and w.y0 > FOOTER_MIN_Y]
    return min(candidates) if candidates else 792.0


def find_header_row(rows: List[Row], words: List[Word], label: str = 'Name') -> Optional[Row]:
    """Return the drawn row holding the given header word in its first cell."""
    for row in rows:
        if not row.cells:
            continue
        first_x0, first_x1 = row.cells[0]
        for w in words:
            if (row.top - 1 <= w.mid_y <= row.bottom + 1
                    and w.text == label
                    and first_x0 <= w.x0 < first_x1):
                return row
    return None


def label_columns(header: Row, words: List[Word], aliases: Dict[str, str]) -> List[Tuple[float, float, str]]:
    """
    Name each column span using the header words that fall inside it.

    Handles multi-word headers ("Birth Date") and headers that wrap onto two
    lines ("Phone" above "Number"), because the grouping is positional. Column
    positions differ between reports depending on which columns were printed, so
    they are always derived here rather than hardcoded.
    """
    per_span: Dict[int, List[Word]] = defaultdict(list)
    for w in words:
        if not (header.top - 1 <= w.mid_y <= header.bottom + 1):
            continue
        for i, (x0, x1) in enumerate(header.cells):
            if x0 <= w.x0 < x1:
                per_span[i].append(w)
                break

    columns = []
    for i, (x0, x1) in enumerate(header.cells):
        ordered = sorted(per_span.get(i, []), key=lambda w: (w.y0, w.x0))
        raw = ' '.join(w.text for w in ordered).strip().lower()
        columns.append((x0, x1, aliases.get(raw, raw or f'col{i}')))
    return columns


def fill_row_gaps(rows: List[Row]) -> List[Tuple[float, float]]:
    """
    Expand drawn rows into every row band, including the undrawn ones.

    The member list is zebra-striped: only alternating rows are painted. Rows are
    contiguous, so each gap between two drawn rows is exactly one undrawn row.
    """
    bands: List[Tuple[float, float]] = []
    for i, row in enumerate(rows):
        if i and row.top - bands[-1][1] > 1.0:
            bands.append((bands[-1][1], row.top))
        bands.append((row.top, row.bottom))
    return bands


def add_edge_bands(bands: List[Tuple[float, float]], words: List[Word],
                   table_top: float, foot: float) -> List[Tuple[float, float]]:
    """
    Recover undrawn rows at the very top or bottom of a page.

    An unpainted row between two painted ones shows up as a gap, but one at a
    page edge has no neighbour on one side and must be found from its text.
    """
    if not bands:
        return [(table_top, foot)] if words else []

    lead = [w for w in words if table_top < w.mid_y < bands[0][0] - 1]
    if lead:
        bands.insert(0, (table_top, bands[0][0]))

    trail = [w for w in words if bands[-1][1] + 1 < w.mid_y and w.y0 < foot - 2]
    if trail:
        bands.append((bands[-1][1], max(w.y1 for w in trail) + 2))
    return bands


def assign_to_cells(words: List[Word], bands: List[Tuple[float, float]],
                    columns: List[Tuple[float, float, str]]) -> List[Dict[str, List[Word]]]:
    """Bucket words into (row band, column) cells."""
    cells: List[Dict[str, List[Word]]] = [defaultdict(list) for _ in bands]
    for w in words:
        for i, (top, bottom) in enumerate(bands):
            if top - 1 <= w.mid_y <= bottom + 1:
                for x0, x1, label in columns:
                    if x0 <= w.x0 < x1:
                        cells[i][label].append(w)
                        break
                break
    return cells


def join_cell(words: List[Word], label: str = '') -> str:
    """
    Join a cell's words into one string, respecting how values wrap.

    Words are grouped into lines by y, then the lines are joined:

    - emails are concatenated with no separator, because they wrap mid-token
      ("...@comcast.ne" + "t");
    - a line ending in a hyphen joins the next with no space, so a hyphenated
      name broken across lines ("Joe-" + "Courage") is put back together;
    - everything else joins with a single space.
    """
    lines: Dict[float, List[Word]] = defaultdict(list)
    for w in words:
        lines[round(w.y0, 1)].append(w)

    parts = [
        ' '.join(w.text for w in sorted(group, key=lambda w: w.x0))
        for _, group in sorted(lines.items())
    ]
    if not parts:
        return ''
    if label == 'email':
        return ''.join(parts)

    joined = parts[0]
    for part in parts[1:]:
        joined = joined + part if joined.endswith('-') else joined + ' ' + part
    return joined.strip()


def sniff_report_type(pdf_path: Path) -> str:
    """
    Identify a report from its first page: 'household', 'member' or 'unknown'.

    Both reports are titled "Member List"; only the household report has a
    "Household Members" column. Reads one page so the import page can tell the
    user which file is which without parsing everything.
    """
    require_pdftotext()
    result = subprocess.run(
        ['pdftotext', '-f', '1', '-l', '1', '-layout', str(pdf_path), '-'],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return 'unknown'

    text = result.stdout
    if 'Household Members' in text:
        return 'household'
    if re.search(r'\bName\b.*\bGender\b', text):
        return 'member'
    return 'unknown'


def normalize_name(name: str) -> str:
    """Casefolded, whitespace-collapsed name, for joining across reports."""
    return re.sub(r'\s+', ' ', name).strip().lower()


def print_date(words: List[Word]) -> str:
    """
    The report's generation date, printed at the bottom-left of every page.

    Used to warn when the two uploaded reports were not printed together.
    """
    foot = footer_top(words)
    if foot >= 792.0:
        return ''
    line = [w for w in words if abs(w.y0 - foot) < 3 and w.x0 < 120]
    text = ' '.join(w.text for w in sorted(line, key=lambda w: w.x0))
    match = re.match(r'(\d{1,2}\s+\w{3}\s+\d{4})', text)
    return match.group(1) if match else ''
