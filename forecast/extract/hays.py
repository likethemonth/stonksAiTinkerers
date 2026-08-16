"""Hays plc extractor.

Hays is the most information-rich company in the set and the only one where a
real analyst benchmark exists in the corpus. UK-listed companies routinely
publish *company-compiled consensus*, and Hays does so in its quarterly trading
statements, naming the figure, the range and the number of contributing
analysts. Nothing comparable exists for the three US companies: grepping all
1,139 documents finds only macroeconomic commentary and governance boilerplate.

Three shapes are extracted:

1.  Annual results tables. Each carries the current AND prior fiscal year, so one
    document yields two years of history:

        | Net fees (1) | 972.4 | 1,113.6 | (13)% | (11)% |

2.  Company-compiled consensus, with the as-of date that decides how much it is
    worth. This matters more than it looks: consensus published 11 days *before*
    the FY2025 year end was GBP 56.4m against an actual of GBP 45.6m, a 19%
    overshoot, whereas the FY2026 figure was published 10 days *after* the year
    closed and is far better informed. The extractor records the timing so the
    estimator can distinguish them rather than pooling them.

3.  Quarterly net fee growth, both like-for-like and actual. The workbook wants
    reported net fees, so the *actual* basis is the one that reconciles; the
    headline LFL number is the trap.

Hays' fiscal year ends 30 June and is labelled by the ending year, so an annual
results statement published in August reports the fiscal year of that calendar
year.
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

_NUM = r"-?[\d,]+(?:\.\d+)?"

#: Summary-table rows. Hays footnotes labels inconsistently across years
#: (`(1)`, `{(1)}`, or nothing), so the marker is optional and tolerated
#: anywhere after the label text.
_ROWS: tuple[tuple[str, str, Unit], ...] = (
    ("net_fees", r"Net fees", Unit.GBP_M),
    (
        "pre_exc_operating_profit",
        r"(?:Operating profit \(before exceptional items\)|Pre-exceptional operating profit|Operating profit from continuing operations|Operating profit)",
        Unit.GBP_M,
    ),
    (
        "pre_exc_basic_eps",
        r"(?:Basic earnings per share \(before exceptional items\)|Basic earnings per share)",
        Unit.GBP_PENCE,
    ),
)

#: Company-compiled consensus. Corpus text is PDF-derived and sprays stray spaces
#: inside words and numbers ("pre -exceptional", "£4 3.5 m"), so whitespace is
#: permitted between essentially every character of the numbers.
#: `(?<!H1 )` guards the half-year case: "consensus operating profit for H1 FY25"
#: names a half-year target, and without the guard the FY branch matches the FY25
#: inside it and files a half-year number as a full-year one.
#: The fiscal year appears on EITHER side of "operating profit" depending on the
#: year the statement was written:
#:     "consensus pre-exceptional operating profit for FY25 is GBP 56.4m"
#:     "consensus for FY26 pre-exceptional operating profit is GBP 43.5m"
#: Both orders are matched; `fy_before` and `fy_after` capture whichever fired.
_CONSENSUS_RE = re.compile(
    r"consensus\s*(?:for\s+FY\s*(?P<fy_before>\d{2,4})\s*)?"
    r"[^.]{0,40}?(?:pre\s*-?\s*exceptional\s+)?operating\s+profit"
    r"(?:[^.]{0,80}?FY\s*(?P<fy_after>\d{2,4}))?"
    r"[^.]{0,80}?is\s*£\s*(?P<value>\d[\d\s,]*(?:\.\s*\d)?)",
    re.IGNORECASE,
)

#: Anything naming a half-year anywhere near the match is not a full-year figure.
_HALF_YEAR_RE = re.compile(r"\bH1\b|half[- ]year|first half", re.IGNORECASE)

#: The range that accompanies a consensus figure, e.g. "£37.0-46.0m range".
#: The corpus text is PDF-derived and sprays spaces inside numbers, so the real
#: string is "£37 .0-46 .0m range" rather than "£37.0-46.0m range".
_SPACED_NUM = r"\d[\d\s,]*(?:\.\s*\d+)?"
_RANGE_RE = re.compile(
    rf"£\s*(?P<low>{_SPACED_NUM})\s*-\s*(?P<high>{_SPACED_NUM})\s*m\s*"
    r"(?:consensus\s*)?rang",
    re.IGNORECASE,
)

#: Group net fee growth in a quarterly trading statement, LFL and actual basis.
_LFL_RE = re.compile(
    r"Group net fees\s+(?P<dir>up|down)\s+(?P<value>\d+(?:\.\d+)?)\s*%", re.IGNORECASE
)
_ACTUAL_BASIS_RE = re.compile(
    r"On an actual basis,?\s*net fees\s+(?P<dir>increased|decreased)\s+by\s+"
    r"(?P<value>\d+(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)

_DISPOSED_FEES_RE = re.compile(
    r"contributed\s+c\.\s*£\s*(?P<value>\d+(?:\.\d+)?)\s*m\s+to\s+reported\s+"
    r"group\s+net\s+fees\s+in\s+FY\s*(?P<fy>\d{2,4})",
    re.IGNORECASE,
)

_MAGNITUDE: dict[Unit, tuple[float, float]] = {
    Unit.GBP_M: (1.0, 5_000.0),
    Unit.GBP_PENCE: (-100.0, 100.0),
    Unit.PERCENT: (-100.0, 100.0),
}


def _clean_number(raw: str) -> float:
    """Parse a figure, tolerating PDF spacing and accounting parentheses."""
    text = re.sub(r"\s+", "", raw).replace(",", "").replace("p", "")
    negative = text.startswith("(") and text.endswith(")")
    value = float(text.strip("()"))
    return -value if negative else value


def _row_cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _normalise_fy(raw: str) -> int:
    """'26' and '2026' both mean fiscal 2026."""
    n = int(re.sub(r"\D", "", raw))
    return 2000 + n if n < 100 else n


#: Divisional sections repeat the group's row labels with divisional numbers
#: ("Net fees | 308.9 | 351.8" is Germany, not the group). Everything from the
#: first such heading onward is discarded before the group table is read.
_DIVISION_HEADING_RE = re.compile(
    r"^#{1,4}\s*(Germany|United Kingdom|UK\s*&|Australia|ANZ|Rest of World|"
    r"Americas|Asia\b|EMEA)",
    re.IGNORECASE | re.MULTILINE,
)


def _group_section(text: str) -> str:
    """The part of an annual-results document that describes the group."""
    summary = re.search(
        r"^#{1,4}\s+SUMMARY INCOME STATEMENT\s*$",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    if summary is not None:
        tail = text[summary.end() :]
        next_heading = re.search(r"^#{1,4}\s+", tail, re.MULTILINE)
        return tail[: next_heading.start()] if next_heading else tail
    operating_sections = list(
        re.finditer(
            r"^#{1,4}\s+Operating performance\s*$",
            text,
            re.IGNORECASE | re.MULTILINE,
        )
    )
    for heading in reversed(operating_sections):
        tail = text[heading.end() :]
        next_heading = re.search(r"^#{1,4}\s+", tail, re.MULTILINE)
        section = tail[: next_heading.start()] if next_heading else tail
        if "Basic earnings per share" in section and "Net fees" in section:
            return section
    heading = _DIVISION_HEADING_RE.search(text)
    return text[: heading.start()] if heading else text


def _annual_results(doc: Document, rejected: list[str]) -> list[MetricObservation]:
    """FY actuals for the reported year and the comparative prior year.

    Hays reports its full year in August for the year ended the previous 30 June,
    so the fiscal year is the calendar year of publication.
    """
    if doc.published_at.month < 7:
        return []  # not an annual results statement
    fy = doc.published_at.year
    group_text = _group_section(doc.text)

    rows: list[MetricObservation] = []
    for metric_key, label_pattern, units in _ROWS:
        pattern = re.compile(
            rf"^\|\s*{label_pattern}\s*(?:\{{?\([^|]*\)\}}?)?\s*\|",
            re.IGNORECASE,
        )
        line = next(
            (ln for ln in group_text.splitlines() if pattern.match(ln.strip())), None
        )
        if line is None:
            continue

        cells = _row_cells(line)[1:]
        figures: list[float] = []
        for cell in cells[:2]:  # current year, then prior year
            token = re.search(rf"\(?{_NUM}\)?", cell.replace(" ", ""))
            if token is None:
                break
            figures.append(_clean_number(token.group(0)))
        if len(figures) < 2:
            continue

        lo, hi = _MAGNITUDE[units]
        for offset, value in enumerate(figures):
            if not (lo <= value <= hi):
                rejected.append(
                    f"FY{fy - offset} {metric_key}: {value} outside "
                    f"[{lo}, {hi}] ({doc.rel_path})"
                )
                continue
            rows.append(
                MetricObservation(
                    company=Company.HAS,
                    metric_key=metric_key,
                    period=Period(year=fy - offset, quarter=None),
                    value=value,
                    units=units,
                    kind=Kind.ACTUAL,
                    as_of=doc.published_at,
                    source_file=doc.rel_path,
                    doc_type=doc.doc_type,
                    excerpt=line,
                    extractor="hays.annual_results",
                    note=None if offset == 0 else "prior-year comparative",
                )
            )
    return rows


def _half_year_net_fees(doc: Document) -> list[MetricObservation]:
    """H1 reported net fees for the current and comparative fiscal years."""
    if doc.published_at.month not in {2, 3} or "H1" not in doc.text[:2_000]:
        return []
    fy = doc.published_at.year
    group_text = _group_section(doc.text)
    pattern = re.compile(r"^\|\s*Net fees\s*(?:\{?\(\d\)\}?)?\s*\|", re.IGNORECASE)
    line = next((ln for ln in group_text.splitlines() if pattern.match(ln.strip())), None)
    if line is None:
        return []
    figures: list[float] = []
    for cell in _row_cells(line)[1:3]:
        token = re.search(rf"\(?{_NUM}\)?", cell.replace(" ", ""))
        if token is None:
            return []
        figures.append(_clean_number(token.group(0)))
    return [
        MetricObservation(
            company=Company.HAS,
            metric_key="net_fees_h1",
            period=Period(year=fy - offset, quarter=None),
            value=value,
            units=Unit.GBP_M,
            kind=Kind.ACTUAL,
            as_of=doc.published_at,
            source_file=doc.rel_path,
            doc_type=doc.doc_type,
            excerpt=line,
            extractor="hays.half_year_net_fees",
            note=None if offset == 0 else "prior-year H1 comparative",
        )
        for offset, value in enumerate(figures)
    ]


def _disposed_country_fees(doc: Document) -> list[MetricObservation]:
    match = _DISPOSED_FEES_RE.search(doc.text)
    if match is None:
        return []
    return [
        MetricObservation(
            company=Company.HAS,
            metric_key="disposed_country_net_fees",
            period=Period(year=_normalise_fy(match.group("fy")), quarter=None),
            value=float(match.group("value")),
            units=Unit.GBP_M,
            kind=Kind.ACTUAL,
            as_of=doc.published_at,
            source_file=doc.rel_path,
            doc_type=doc.doc_type,
            excerpt=re.sub(r"\s+", " ", match.group(0)),
            extractor="hays.disposed_country_fees",
            note="removed to align the challenge target with continuing operations",
        )
    ]


def _consensus(doc: Document) -> list[MetricObservation]:
    """Company-compiled consensus for pre-exceptional operating profit."""
    rows: list[MetricObservation] = []
    for match in _CONSENSUS_RE.finditer(doc.text):
        # Half-year consensus is a different target; skip it. Checked twice: the
        # regex guards the immediate "H1 FY25" form, and this catches the looser
        # phrasings ("first half", "half-year") that appear in the same sentence.
        if _HALF_YEAR_RE.search(match.group(0)):
            continue
        raw_fy = match.group("fy_before") or match.group("fy_after")
        if raw_fy is None:
            continue
        fy = _normalise_fy(raw_fy)
        value = _clean_number(match.group("value"))
        if not (1.0 <= value <= 5_000.0):
            continue

        excerpt = re.sub(r"\s+", " ", match.group(0))
        rows.append(
            MetricObservation(
                company=Company.HAS,
                metric_key="pre_exc_operating_profit",
                period=Period(year=fy, quarter=None),
                value=value,
                units=Unit.GBP_M,
                kind=Kind.CONSENSUS,
                as_of=doc.published_at,
                source_file=doc.rel_path,
                doc_type=doc.doc_type,
                excerpt=excerpt,
                extractor="hays.consensus",
                note="company-compiled analyst consensus",
            )
        )

        # A range often accompanies the figure; capture its bounds too.
        window = doc.text[match.start() : match.start() + 600]
        bounds = _RANGE_RE.search(window)
        if bounds:
            for kind, group in (
                (Kind.CONSENSUS_LOW, "low"),
                (Kind.CONSENSUS_HIGH, "high"),
            ):
                rows.append(
                    MetricObservation(
                        company=Company.HAS,
                        metric_key="pre_exc_operating_profit",
                        period=Period(year=fy, quarter=None),
                        value=_clean_number(bounds.group(group)),
                        units=Unit.GBP_M,
                        kind=kind,
                        as_of=doc.published_at,
                        source_file=doc.rel_path,
                        doc_type=doc.doc_type,
                        excerpt=re.sub(r"\s+", " ", bounds.group(0)),
                        extractor="hays.consensus_range",
                    )
                )
    return rows


def _net_fee_growth(doc: Document) -> list[MetricObservation]:
    """Group net fee growth from a quarterly trading statement.

    Both bases are recorded. The workbook asks for reported net fees, so the
    actual basis is what converts a prior-year level into this year's; the
    like-for-like headline excludes currency and the country exits and would
    overstate the decline.
    """
    # Hays' fiscal year ends 30 June, labelled by the ending year. The Q1
    # statement lands in October and is the only one that reports on the fiscal
    # year *ahead* of its calendar year; Q2 (January), Q3 (April) and Q4 (early
    # July, just after the year closes) all report the fiscal year matching their
    # calendar year. September is the cutover.
    fy = (
        doc.published_at.year + 1
        if doc.published_at.month >= 9
        else doc.published_at.year
    )
    period = Period(year=fy, quarter=None)
    rows: list[MetricObservation] = []

    for regex, metric_key, negative_words in (
        (_LFL_RE, "net_fees_growth_lfl_pct", {"down"}),
        (_ACTUAL_BASIS_RE, "net_fees_growth_actual_pct", {"decreased"}),
    ):
        match = regex.search(doc.text)
        if match is None:
            continue
        value = float(match.group("value"))
        if match.group("dir").lower() in negative_words:
            value = -value
        rows.append(
            MetricObservation(
                company=Company.HAS,
                metric_key=metric_key,
                period=period,
                value=value,
                units=Unit.PERCENT,
                kind=Kind.GROWTH_PCT,
                as_of=doc.published_at,
                source_file=doc.rel_path,
                doc_type=doc.doc_type,
                excerpt=re.sub(r"\s+", " ", match.group(0)),
                extractor="hays.net_fee_growth",
            )
        )
    return rows


def _consolidate(
    rows: list[MetricObservation], rejected: list[str]
) -> list[MetricObservation]:
    """Resolve actuals that several documents report differently.

    Hays repeats its headline figures across several filings on results day, and
    also repeats the same row labels inside each divisional section. That makes
    disagreement a free cross-check: if two documents state a different number
    for the same thing, one came from a divisional table.

    Resolution is by document frequency — the group figure appears in every
    results filing, a divisional one in a single section — with the larger
    magnitude breaking ties, since a division is by construction a subset of the
    group. Every conflict is logged either way, because a silent winner would
    hide the parse error rather than record it.
    """
    grouped: dict[tuple[str, str], list[MetricObservation]] = {}
    others: list[MetricObservation] = []
    for row in rows:
        if row.kind is Kind.ACTUAL:
            grouped.setdefault((row.period.key, row.metric_key), []).append(row)
        else:
            others.append(row)

    resolved: list[MetricObservation] = []
    for (period_key, metric_key), candidates in sorted(grouped.items()):
        tally: dict[float, list[MetricObservation]] = {}
        for row in candidates:
            tally.setdefault(round(row.value, 4), []).append(row)

        if len(tally) > 1:
            winner = max(tally.items(), key=lambda kv: (len(kv[1]), abs(kv[0])))
            rejected.append(
                f"DISAGREEMENT {period_key} {metric_key}: documents report "
                f"{sorted(tally)} — kept {winner[0]} "
                f"(reported by {len(winner[1])} of {len(candidates)} extractions)"
            )
            resolved.append(winner[1][0])
        else:
            resolved.append(candidates[0])

    return resolved + others


def extract(
    docs: list[Document], rejected: list[str] | None = None
) -> list[MetricObservation]:
    """All Hays observations from a point-in-time document set."""
    sink = rejected if rejected is not None else []
    rows: list[MetricObservation] = []
    for doc in docs:
        if doc.doc_type is not DocType.FILING:
            continue
        rows.extend(_annual_results(doc, sink))
        rows.extend(_half_year_net_fees(doc))
        rows.extend(_disposed_country_fees(doc))
        rows.extend(_consensus(doc))
        rows.extend(_net_fee_growth(doc))
    return _consolidate(rows, sink)


if __name__ == "__main__":  # pragma: no cover - manual inspection
    dropped: list[str] = []
    for row in extract(load(Company.HAS), dropped):
        print(
            f"{row.period.key:9s} {row.metric_key:28s} {row.kind.value:14s} "
            f"{row.value:9.2f} as_of={row.as_of}"
        )
    for reason in dropped:
        print("DROPPED", reason)
