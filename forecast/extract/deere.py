"""Deere earnings-release extractor for group and PPA quarterly actuals."""

from __future__ import annotations

import re

from forecast.corpus import Document, load
from forecast.schema import Company, DocType, Kind, MetricObservation, Period, Unit

_PERIOD_RE = re.compile(r"Q(?P<quarter>[1-4])\s+(?P<year>20\d{2})", re.IGNORECASE)
_NUMBER = re.compile(r"\(?-?\d[\d,]*(?:\.\d+)?\)?")

_ROWS = (
    ("worldwide_net_sales_revenues", "Net sales and revenues", Unit.USD_M),
    ("diluted_eps_gaap", "Fully diluted EPS", Unit.USD_PER_SHARE),
)
_PPA_ROWS = (
    ("ppa_net_sales", "Net sales", Unit.USD_M),
    ("ppa_operating_profit", "Operating profit", Unit.USD_M),
)


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _numbers(line: str) -> list[float]:
    values: list[float] = []
    for cell in _cells(line)[1:]:
        match = _NUMBER.search(cell)
        if match is None:
            continue
        raw = match.group(0).replace(",", "")
        negative = raw.startswith("(") and raw.endswith(")")
        value = float(raw.strip("()"))
        values.append(-value if negative else value)
    return values


def _find(lines: list[str], label: str) -> str | None:
    wanted = label.casefold()
    for line in lines:
        if not line.lstrip().startswith("|"):
            continue
        cells = _cells(line)
        if cells and cells[0].casefold() == wanted:
            return line
    return None


def _period(doc: Document) -> Period | None:
    match = _PERIOD_RE.search(doc.period_hint)
    if match is None or "Quarter" not in doc.title:
        return None
    return Period(year=int(match.group("year")), quarter=int(match.group("quarter")))


def _observations(
    doc: Document,
    period: Period,
    rows: tuple[tuple[str, str, Unit], ...],
    lines: list[str],
    extractor: str,
) -> list[MetricObservation]:
    result: list[MetricObservation] = []
    for key, label, units in rows:
        line = _find(lines, label)
        if line is None:
            continue
        values = _numbers(line)
        if len(values) < 2:
            continue
        for offset, value in enumerate(values[:2]):
            target = period if offset == 0 else period.prior_year()
            result.append(
                MetricObservation(
                    company=Company.DE,
                    metric_key=key,
                    period=target,
                    value=value,
                    units=units,
                    kind=Kind.ACTUAL,
                    as_of=doc.published_at,
                    source_file=doc.rel_path,
                    doc_type=doc.doc_type,
                    excerpt=line,
                    extractor=extractor,
                    note=None if offset == 0 else "prior-year comparative",
                )
            )
    return result


def extract(
    docs: list[Document], rejected: list[str] | None = None
) -> list[MetricObservation]:
    """Extract and deduplicate Deere quarterly actuals from earnings releases."""
    rows: list[MetricObservation] = []
    seen: set[tuple[str, str, float]] = set()
    for doc in docs:
        if doc.doc_type is not DocType.FILING:
            continue
        period = _period(doc)
        if period is None:
            continue
        lines = doc.text.splitlines()
        summary_start = next(
            (index for index, line in enumerate(lines) if line.startswith("| Deere & Company")),
            None,
        )
        ppa_start = next(
            (
                index
                for index, line in enumerate(lines)
                if line.lstrip().startswith("| Production & Precision Agriculture")
            ),
            None,
        )
        candidates: list[MetricObservation] = []
        if summary_start is not None:
            candidates.extend(
                _observations(
                    doc,
                    period,
                    _ROWS,
                    lines[summary_start : summary_start + 12],
                    "deere.summary_table",
                )
            )
        if ppa_start is not None:
            candidates.extend(
                _observations(
                    doc,
                    period,
                    _PPA_ROWS,
                    lines[ppa_start : ppa_start + 12],
                    "deere.ppa_table",
                )
            )
        for row in candidates:
            identity = (row.metric_key, row.period.key, round(row.value, 4))
            if identity in seen:
                continue
            seen.add(identity)
            rows.append(row)
    return rows


if __name__ == "__main__":  # pragma: no cover
    for row in extract(load(Company.DE))[:30]:
        print(row.period.key, row.metric_key, row.value)
