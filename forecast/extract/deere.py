"""Deere earnings-release extractor for group and PPA quarterly actuals."""

from __future__ import annotations

import re

from forecast.corpus import Document, load
from forecast.schema import Company, DocType, Kind, MetricObservation, Period, Unit

_PERIOD_RE = re.compile(r"Q(?P<quarter>[1-4])\s+(?P<year>20\d{2})", re.IGNORECASE)
_NUMBER = re.compile(r"\(?-?\d[\d,]*(?:\.\d+)?\)?")
_WORLDWIDE_REVENUE_RE = re.compile(
    r"Worldwide net sales and revenues[^.]{0,180}?to \$(?P<current>[\d,.]+)\s*"
    r"(?P<current_scale>billion|million)[^.]{0,120}?compared with \$(?P<prior>[\d,.]+)\s*"
    r"(?P<prior_scale>billion|million)",
    re.IGNORECASE,
)
_WORLDWIDE_CURRENT_RE = re.compile(
    r"Worldwide net sales and revenues[^.]{0,180}?to \$(?P<current>[\d,.]+)\s*"
    r"(?P<current_scale>billion|million)",
    re.IGNORECASE,
)
_HEADLINE_EPS_RE = re.compile(
    r"Net income attributable to Deere & Company was \$[\d,.]+\s*(?:million|billion),\s*"
    r"or \$(?P<current>[\d.]+) per share[^.]{0,120}?compared with \$[\d,.]+\s*"
    r"(?:million|billion),\s*or \$(?P<prior>[\d.]+) per share",
    re.IGNORECASE,
)

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
    if match is not None and "Quarter" in doc.title:
        return Period(year=int(match.group("year")), quarter=int(match.group("quarter")))
    # Deere's Q4 earnings releases are filed with an annual frontmatter hint
    # ("FY 2025"), while the title and the result tables explicitly identify
    # the fourth quarter. Deere labels fiscal years by their ending year, which
    # is also the publication year for these November releases.
    if re.search(r"\b(?:Fourth|4th) Quarter\b", doc.title, re.IGNORECASE):
        return Period(year=doc.published_at.year, quarter=4)
    return None


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


def _headline_actuals(doc: Document, period: Period) -> list[MetricObservation]:
    """Recover older result headlines whose tables predate the current layout."""
    rows: list[MetricObservation] = []
    revenue = _WORLDWIDE_REVENUE_RE.search(doc.text)
    if revenue is not None:
        for offset, field in enumerate(("current", "prior")):
            value = float(revenue.group(field).replace(",", ""))
            if revenue.group(f"{field}_scale").lower() == "billion":
                value *= 1000.0
            rows.append(
                MetricObservation(
                    company=Company.DE,
                    metric_key="worldwide_net_sales_revenues",
                    period=period if offset == 0 else period.prior_year(),
                    value=value,
                    units=Unit.USD_M,
                    kind=Kind.ACTUAL,
                    as_of=doc.published_at,
                    source_file=doc.rel_path,
                    doc_type=doc.doc_type,
                    excerpt=revenue.group(0),
                    extractor="deere.legacy_result_headline",
                    note=None if offset == 0 else "prior-year comparative",
                )
            )
    else:
        current_revenue = _WORLDWIDE_CURRENT_RE.search(doc.text)
        if current_revenue is not None:
            value = float(current_revenue.group("current").replace(",", ""))
            if current_revenue.group("current_scale").lower() == "billion":
                value *= 1000.0
            rows.append(
                MetricObservation(
                    company=Company.DE,
                    metric_key="worldwide_net_sales_revenues",
                    period=period,
                    value=value,
                    units=Unit.USD_M,
                    kind=Kind.ACTUAL,
                    as_of=doc.published_at,
                    source_file=doc.rel_path,
                    doc_type=doc.doc_type,
                    excerpt=current_revenue.group(0),
                    extractor="deere.legacy_result_headline",
                    note="quarterly worldwide total; prior-year comparison not stated in the headline",
                )
            )
    eps = _HEADLINE_EPS_RE.search(doc.text)
    if eps is not None:
        for offset, field in enumerate(("current", "prior")):
            rows.append(
                MetricObservation(
                    company=Company.DE,
                    metric_key="diluted_eps_gaap",
                    period=period if offset == 0 else period.prior_year(),
                    value=float(eps.group(field)),
                    units=Unit.USD_PER_SHARE,
                    kind=Kind.ACTUAL,
                    as_of=doc.published_at,
                    source_file=doc.rel_path,
                    doc_type=doc.doc_type,
                    excerpt=eps.group(0),
                    extractor="deere.legacy_result_headline",
                    note=(
                        "headline GAAP per-share result"
                        if offset == 0
                        else "prior-year headline GAAP per-share comparative"
                    ),
                )
            )
    return rows


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
                if line.lstrip().startswith(
                    ("| Production & Precision Agriculture", "| Production & Precision Ag")
                )
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
        candidates.extend(_headline_actuals(doc, period))
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
