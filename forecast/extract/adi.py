"""Analog Devices extractor.

ADI is the cleanest of the four: every quarterly 8-K carries an outlook sentence
whose wording has been stable for years, and a highlights table with the reported
result. That gives a matched (guidance, actual) pair per quarter going back to
FY2023 — which is exactly the input the calibration needs.

Two traps handled here:

1.  The financial-statement tables later in the same 8-K repeat the highlight
    labels in *thousands* rather than millions. We take the first occurrence and
    then range-check the magnitude, rather than trusting position alone.
2.  The outlook sentence names the quarter being *guided*, not the quarter being
    *reported*. ADI always guides the immediately following quarter, so the
    reported period is derived by stepping back one quarter.
"""

from __future__ import annotations

import re

from forecast.corpus import Document, load
from forecast.schema import (
    Company,
    DocType,
    Kind,
    MetricObservation,
    Period,
    Unit,
)

QUARTER_WORDS = {"first": 1, "second": 2, "third": 3, "fourth": 4}

#: The outlook sentence. Stable wording across every quarterly 8-K in the corpus.
#: Captures the range half-widths too — they become GUIDE_LOW/GUIDE_HIGH rows.
#: `\d+(?:\.\d+)?` rather than `[\d.]+` throughout: the latter swallows the
#: sentence-ending full stop after "+/- $0.15." and fails to parse.
_NUM = r"\d+(?:\.\d+)?"

_OUTLOOK_RE = re.compile(
    rf"For the (?P<qword>first|second|third|fourth) quarter of fiscal (?P<fy>\d{{4}}),"
    rf"\s*we are forecasting revenue of \$(?P<rev>{_NUM})\s*billion,"
    rf"\s*\+/-\s*\$(?P<rev_pm>{_NUM})\s*million"
    rf".*?adjusted operating margin of approximately (?P<aom>{_NUM})%,"
    rf"\s*\+/-\s*(?P<aom_pm>{_NUM})\s*bps"
    rf".*?adjusted EPS to be \$(?P<eps>{_NUM}),\s*\+/-\s*\$(?P<eps_pm>{_NUM})",
    re.DOTALL | re.IGNORECASE,
)

#: (metric_key, exact table label, unit).
#: Labels are matched against the whole first cell, not as a substring: "Gross
#: margin" and "Gross margin percentage" are different rows carrying different
#: units, and a substring match silently returns the wrong one.
_ACTUAL_ROWS: tuple[tuple[str, str, Unit], ...] = (
    ("revenue", "Revenue", Unit.USD_M),
    ("gross_margin_pct", "Gross margin percentage", Unit.PERCENT),
    ("adj_gross_margin_pct", "Adjusted gross margin percentage", Unit.PERCENT),
    ("adj_operating_margin_pct", "Adjusted operating margin", Unit.PERCENT),
    ("diluted_eps_gaap", "Diluted earnings per share", Unit.USD_PER_SHARE),
    ("adj_eps", "Adjusted diluted earnings per share", Unit.USD_PER_SHARE),
)

#: A number, optionally in accounting parentheses. Searched *within* a cell
#: rather than matched against the whole of it: some documents in the corpus have
#: mangled table markup that merges columns, e.g.
#:     | Revenue | $ | 3,623 $ 2,640 | 37 % |
#: where requiring a whole-cell match falls through to the YoY percentage and
#: silently reports revenue of 37.
_NUMBER_IN_CELL = re.compile(r"\(?-?\d[\d,]*(?:\.\d+)?\)?")

#: Plausible magnitude per unit, used to catch a thousands/millions scale slip.
_MAGNITUDE: dict[Unit, tuple[float, float]] = {
    Unit.USD_M: (500.0, 20_000.0),
    Unit.PERCENT: (-100.0, 100.0),
    Unit.USD_PER_SHARE: (-50.0, 50.0),
}


def _prev_quarter(p: Period) -> Period:
    """The quarter immediately before `p`, crossing the fiscal year boundary."""
    if p.quarter is None:
        raise ValueError(f"{p} is a full year, not a quarter")
    if p.quarter == 1:
        return Period(year=p.year - 1, quarter=4)
    return Period(year=p.year, quarter=p.quarter - 1)


def _row_cells(line: str) -> list[str]:
    """Split a markdown pipe-table row into trimmed cells."""
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _first_number(line: str) -> str | None:
    """The first numeric cell after the label — always the current period.

    Currency and percent markers occupy their own cells in this corpus's tables
    (`| Revenue | $ | 3,623 | ... |`), so they are skipped rather than stripped
    out of the number itself.
    """
    for cell in _row_cells(line)[1:]:
        match = _NUMBER_IN_CELL.search(cell)
        if match is not None:
            return match.group(0)
    return None


def _find_row(text: str, label: str) -> str | None:
    """First table row whose leading cell is exactly `label`."""
    wanted = label.casefold()
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = _row_cells(line)
        if cells and cells[0].casefold() == wanted:
            return line
    return None


def _to_float(raw: str) -> float:
    """Parse a table number, honouring accounting parentheses for negatives."""
    text = raw.strip().replace(",", "")
    negative = text.startswith("(") and text.endswith(")")
    value = float(text.strip("()"))
    return -value if negative else value


def _rescale(value: float, units: Unit) -> tuple[float | None, str | None]:
    """Correct a thousands-for-millions slip, or reject an implausible value.

    Returns (None, reason) when the number cannot be salvaged. Dropping the row is
    right for actuals: a mis-parsed magnitude poisons the calibration it feeds,
    and a missing historical observation only widens sigma, which is honest.
    """
    lo, hi = _MAGNITUDE[units]
    if units is Unit.USD_M and value > hi:
        rescaled = value / 1000.0
        if lo <= rescaled <= hi:
            return rescaled, "rescaled from thousands to millions"
    if not (lo <= value <= hi):
        return None, f"rejected: {value} outside plausible range [{lo}, {hi}]"
    return value, None


def _guidance(doc: Document) -> list[MetricObservation]:
    """GUIDE_MID/LOW/HIGH rows from the outlook sentence."""
    match = _OUTLOOK_RE.search(doc.text)
    if match is None:
        return []

    period = Period(
        year=int(match.group("fy")), quarter=QUARTER_WORDS[match.group("qword")]
    )
    excerpt = match.group(0)

    # Revenue is quoted in billions with a +/- in millions; normalise to USDm.
    rev_mid = float(match.group("rev")) * 1000.0
    rev_pm = float(match.group("rev_pm"))
    eps_mid, eps_pm = float(match.group("eps")), float(match.group("eps_pm"))
    aom_mid, aom_pm = float(match.group("aom")), float(match.group("aom_pm")) / 100.0

    triples = (
        ("revenue", Unit.USD_M, rev_mid, rev_pm),
        ("adj_eps", Unit.USD_PER_SHARE, eps_mid, eps_pm),
        ("adj_operating_margin_pct", Unit.PERCENT, aom_mid, aom_pm),
    )

    rows: list[MetricObservation] = []
    for key, units, mid, half_width in triples:
        for kind, value in (
            (Kind.GUIDE_MID, mid),
            (Kind.GUIDE_LOW, mid - half_width),
            (Kind.GUIDE_HIGH, mid + half_width),
        ):
            rows.append(
                MetricObservation(
                    company=Company.ADI,
                    metric_key=key,
                    period=period,
                    value=round(value, 4),
                    units=units,
                    kind=kind,
                    as_of=doc.published_at,
                    source_file=doc.rel_path,
                    doc_type=doc.doc_type,
                    excerpt=excerpt,
                    extractor="adi.outlook_sentence",
                    note="Management outlook issued with the prior quarter's results.",
                )
            )
    return rows


def _actuals(
    doc: Document, guided: Period | None, rejected: list[str]
) -> list[MetricObservation]:
    """ACTUAL rows from the highlights table.

    The reported period is the one before the guided period. Without a guidance
    sentence we cannot pin the fiscal year reliably, so we decline to guess.
    Rows that fail the magnitude check are appended to `rejected` so the run log
    records what was thrown away and why.
    """
    if guided is None:
        return []
    period = _prev_quarter(guided)

    rows: list[MetricObservation] = []
    for key, label, units in _ACTUAL_ROWS:
        line = _find_row(doc.text, label)
        if line is None:
            continue
        raw = _first_number(line)
        if raw is None:
            continue
        value, warning = _rescale(_to_float(raw), units)
        if value is None:
            rejected.append(f"{period.key} {key}: {warning} ({doc.rel_path})")
            continue
        rows.append(
            MetricObservation(
                company=Company.ADI,
                metric_key=key,
                period=period,
                value=value,
                units=units,
                kind=Kind.ACTUAL,
                as_of=doc.published_at,
                source_file=doc.rel_path,
                doc_type=doc.doc_type,
                excerpt=line,
                extractor="adi.highlights_table",
                note=warning,
            )
        )
    return rows


def extract(
    docs: list[Document], rejected: list[str] | None = None
) -> list[MetricObservation]:
    """All ADI observations from a point-in-time document set.

    Args:
        docs: Documents already filtered to the as-of cutoff by corpus.load().
        rejected: Optional sink for dropped-row explanations, surfaced in the log.
    """
    sink = rejected if rejected is not None else []
    rows: list[MetricObservation] = []
    for doc in docs:
        if doc.doc_type is not DocType.FILING:
            continue
        guidance = _guidance(doc)
        guided = guidance[0].period if guidance else None
        rows.extend(guidance)
        rows.extend(_actuals(doc, guided, sink))
    return rows


if __name__ == "__main__":  # pragma: no cover - manual inspection
    dropped: list[str] = []
    for row in extract(load(Company.ADI), dropped)[:20]:
        print(f"{row.period.key:9s} {row.metric_key:26s} {row.kind.value:12s} {row.value}")
    for reason in dropped:
        print("DROPPED", reason)
