"""Home Depot extractor.

HD differs from the other two in a way that shapes the estimators: it guides the
**full year**, never the quarter. So there is no quarterly guidance midpoint to
correct, and the forecast has to come from a full-year anchor divided by the
quarter's historical share of the year.

Three shapes are extracted:

1.  Quarterly actuals from the results tables, which carry the current and
    prior-year quarter and are exact to the million:

        | Net sales | $ 41,765 | $ 39,856 | 4.8% |

    The press release also states these in prose ("sales of $41.8 billion"), but
    only to three significant figures — a 50m ambiguity on a 46,000 forecast — so
    the tables are preferred and the prose is used only for comparable sales,
    which has no table row.

2.  Comparable sales, from prose, with the direction word carrying the sign.

3.  Full-year guidance bullets, including the prior-year base they are quoted
    against:

        - Total sales growth of approximately 2.5% to 4.5%
        - Adjusted diluted earnings-per-share to grow approximately flat to
          4.0% from $14.69 in fiscal 2025

    "flat" is a real bound meaning 0%, and is parsed as such.

HD's fiscal year is labelled by its START year (fiscal 2026 runs Feb 2026 to Jan
2027), the opposite of ADI, Hays and Deere. The period is always read from the
document text rather than inferred from the publication date.
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

#: Which fiscal quarter a results document reports. Present in every HD earnings
#: release, and trustworthy in a way the frontmatter `period` field is not.
_REPORTED_PERIOD_RE = re.compile(
    r"(?:sales|net sales|comparable sales|adjusted diluted earnings per share)"
    r"[^.]{0,80}?for the (?P<qword>first|second|third|fourth) quarter of fiscal "
    r"(?P<fy>\d{4})",
    re.IGNORECASE,
)

#: Comparable sales, total company. No table row exists, so prose it is.
_COMPS_RE = re.compile(
    r"[Cc]omparable sales for the (?P<qword>first|second|third|fourth) quarter of "
    r"fiscal (?P<fy>\d{4}) (?P<dir>increased|decreased) (?P<value>[\d.]+)\s*"
    r"(?:%|percent)"
)

#: (metric_key, exact table label, unit). Matched against the whole first cell.
#: Older releases label GAAP EPS without the "(GAAP)" suffix, which only appeared
#: once HD began reporting an adjusted figure alongside it. Both are listed; the
#: deduplication in extract() collapses the overlap in documents carrying both.
_ACTUAL_ROWS: tuple[tuple[str, str, Unit], ...] = (
    ("net_sales", "Net sales", Unit.USD_M),
    ("adj_eps", "Adjusted diluted earnings per share (Non-GAAP)", Unit.USD_PER_SHARE),
    ("diluted_eps_gaap", "Diluted earnings per share (GAAP)", Unit.USD_PER_SHARE),
    ("diluted_eps_gaap", "Diluted earnings per share", Unit.USD_PER_SHARE),
    ("diluted_eps_gaap", "Diluted Earnings per Share", Unit.USD_PER_SHARE),
)

#: Full-year guidance bullets. "flat" is a bound meaning zero, not an absence.
_BOUND = r"(?:flat|\(?-?[\d.]+\)?\s*%?)"
_GUIDANCE_RES: tuple[tuple[str, re.Pattern[str], Unit], ...] = (
    (
        "total_sales_growth_pct",
        re.compile(
            rf"Total sales growth of approximately (?P<low>{_BOUND}) to "
            rf"(?P<high>{_BOUND})",
            re.IGNORECASE,
        ),
        Unit.PERCENT,
    ),
    (
        "comp_sales_pct",
        re.compile(
            rf"Comparable sales growth of approximately (?P<low>{_BOUND}) to "
            rf"(?P<high>{_BOUND})",
            re.IGNORECASE,
        ),
        Unit.PERCENT,
    ),
    (
        "adj_eps_growth_pct",
        re.compile(
            rf"Adjusted diluted earnings-per-share to grow approximately "
            rf"(?P<low>{_BOUND}) to (?P<high>{_BOUND}) from \$(?P<base>[\d.]+)",
            re.IGNORECASE,
        ),
        Unit.PERCENT,
    ),
)

_MAGNITUDE: dict[Unit, tuple[float, float]] = {
    Unit.USD_M: (1_000.0, 250_000.0),
    Unit.USD_PER_SHARE: (-50.0, 50.0),
    Unit.PERCENT: (-100.0, 100.0),
}

_NUMBER_IN_CELL = re.compile(r"\(?-?\d[\d,]*(?:\.\d+)?\)?")


def _row_cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _to_float(raw: str) -> float:
    text = raw.strip().replace(",", "")
    negative = text.startswith("(") and text.endswith(")")
    return -float(text.strip("()")) if negative else float(text.strip("()"))


def _bound_to_float(raw: str) -> float:
    """'flat' is zero; everything else is a signed percentage."""
    text = raw.strip().rstrip("%").strip()
    if text.lower() == "flat":
        return 0.0
    return _to_float(text)


def _find_row(text: str, label: str) -> str | None:
    wanted = label.casefold()
    for line in text.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = _row_cells(line)
        if cells and cells[0].casefold() == wanted:
            return line
    return None


def _reported_period(doc: Document) -> Period | None:
    match = _REPORTED_PERIOD_RE.search(doc.text)
    if match is None:
        return None
    return Period(
        year=int(match.group("fy")), quarter=QUARTER_WORDS[match.group("qword").lower()]
    )


def _quarterly_actuals(
    doc: Document, period: Period, rejected: list[str]
) -> list[MetricObservation]:
    """Current and prior-year quarter from each results-table row."""
    rows: list[MetricObservation] = []
    for metric_key, label, units in _ACTUAL_ROWS:
        line = _find_row(doc.text, label)
        if line is None:
            continue
        numbers = [
            _to_float(m.group(0))
            for cell in _row_cells(line)[1:3]
            if (m := _NUMBER_IN_CELL.search(cell))
        ]
        if len(numbers) < 2:
            continue

        lo, hi = _MAGNITUDE[units]
        for offset, value in enumerate(numbers[:2]):
            target = period if offset == 0 else period.prior_year()
            if not (lo <= value <= hi):
                rejected.append(
                    f"{target.key} {metric_key}: {value} outside [{lo}, {hi}] "
                    f"({doc.rel_path})"
                )
                continue
            rows.append(
                MetricObservation(
                    company=Company.HD,
                    metric_key=metric_key,
                    period=target,
                    value=value,
                    units=units,
                    kind=Kind.ACTUAL,
                    as_of=doc.published_at,
                    source_file=doc.rel_path,
                    doc_type=doc.doc_type,
                    excerpt=line,
                    extractor="hd.results_table",
                    note=None if offset == 0 else "prior-year comparative",
                )
            )
    return rows


def _comparable_sales(doc: Document) -> list[MetricObservation]:
    """Comparable sales, total company — prose only, sign from the direction word."""
    rows: list[MetricObservation] = []
    seen: set[str] = set()
    for match in _COMPS_RE.finditer(doc.text):
        period = Period(
            year=int(match.group("fy")),
            quarter=QUARTER_WORDS[match.group("qword").lower()],
        )
        if period.key in seen:
            continue
        seen.add(period.key)
        value = float(match.group("value"))
        if match.group("dir").lower() == "decreased":
            value = -value
        rows.append(
            MetricObservation(
                company=Company.HD,
                metric_key="comp_sales_pct",
                period=period,
                value=value,
                units=Unit.PERCENT,
                kind=Kind.ACTUAL,
                as_of=doc.published_at,
                source_file=doc.rel_path,
                doc_type=doc.doc_type,
                excerpt=match.group(0),
                extractor="hd.comps_prose",
            )
        )
    return rows


def _fy_guidance(doc: Document) -> list[MetricObservation]:
    """Full-year guidance ranges, recorded as LOW/MID/HIGH.

    The fiscal year guided is the one named in the surrounding text; HD reaffirms
    or updates the same year's guidance at each quarterly release.
    """
    fy_match = re.search(r"[Ff]iscal (?P<fy>\d{4}) [Gg]uidance", doc.text)
    if fy_match is None:
        return []
    fy = int(fy_match.group("fy"))
    period = Period(year=fy, quarter=None)

    rows: list[MetricObservation] = []
    for metric_key, regex, units in _GUIDANCE_RES:
        match = regex.search(doc.text)
        if match is None:
            continue
        low = _bound_to_float(match.group("low"))
        high = _bound_to_float(match.group("high"))
        excerpt = re.sub(r"\s+", " ", match.group(0))

        for kind, value in (
            (Kind.GUIDE_LOW, low),
            (Kind.GUIDE_MID, (low + high) / 2.0),
            (Kind.GUIDE_HIGH, high),
        ):
            rows.append(
                MetricObservation(
                    company=Company.HD,
                    metric_key=metric_key,
                    period=period,
                    value=round(value, 4),
                    units=units,
                    kind=kind,
                    as_of=doc.published_at,
                    source_file=doc.rel_path,
                    doc_type=doc.doc_type,
                    excerpt=excerpt,
                    extractor="hd.fy_guidance",
                )
            )

        # The EPS bullet quotes the prior-year base it grows from, which is the
        # level the growth rate has to be applied to.
        if "base" in regex.groupindex and match.group("base"):
            rows.append(
                MetricObservation(
                    company=Company.HD,
                    metric_key="adj_eps",
                    period=Period(year=fy - 1, quarter=None),
                    value=float(match.group("base")),
                    units=Unit.USD_PER_SHARE,
                    kind=Kind.ACTUAL,
                    as_of=doc.published_at,
                    source_file=doc.rel_path,
                    doc_type=doc.doc_type,
                    excerpt=excerpt,
                    extractor="hd.fy_guidance_base",
                    note="prior-year full-year base quoted in the guidance bullet",
                )
            )
    return rows


def extract(
    docs: list[Document], rejected: list[str] | None = None
) -> list[MetricObservation]:
    """All Home Depot observations from a point-in-time document set."""
    sink = rejected if rejected is not None else []
    rows: list[MetricObservation] = []
    seen: set[tuple[str, str, str, float]] = set()

    for doc in docs:
        if doc.doc_type is not DocType.FILING:
            continue
        candidates: list[MetricObservation] = []
        period = _reported_period(doc)
        if period is not None:
            candidates.extend(_quarterly_actuals(doc, period, sink))
        candidates.extend(_comparable_sales(doc))
        candidates.extend(_fy_guidance(doc))

        # HD files the same release two or three times on results day; dedupe on
        # the value itself so repeats do not inflate the calibration sample.
        for row in candidates:
            key = (row.metric_key, row.period.key, row.kind.value, round(row.value, 4))
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)
    return rows


if __name__ == "__main__":  # pragma: no cover - manual inspection
    dropped: list[str] = []
    for row in sorted(
        extract(load(Company.HD), dropped),
        key=lambda r: (r.period.sort_key, r.metric_key),
        reverse=True,
    )[:30]:
        print(
            f"{row.period.key:9s} {row.metric_key:24s} {row.kind.value:11s} "
            f"{row.value:10.2f} as_of={row.as_of}"
        )
    for reason in dropped:
        print("DROPPED", reason)
