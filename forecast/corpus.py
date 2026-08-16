"""Point-in-time corpus access.

The single rule this module exists to enforce: **nothing downstream may see a
document published after the as-of cutoff.** Every estimator reads the corpus
through `load()`, so a replay with `--as-of 2026-02-17` genuinely reproduces what
the system would have forecast that morning — which is what makes the historical
backtest honest rather than decorative.

The frontmatter `period` field is a *hint only*. It is demonstrably unreliable
(an AGM transcript published 2026-05-21 is tagged "Q2 2027"), so extractors read
the fiscal period out of the document text and use the frontmatter only to
narrow candidates. `published_at` is trustworthy and is what the cutoff uses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

from forecast.schema import Company, DocType, Period

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_ROOT = REPO_ROOT / "challenge" / "offline-data"

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*\n", re.DOTALL)
_KV_RE = re.compile(r"^(?P<key>[a-z_]+):\s*(?P<value>.*)$")
_SKIP_FILES = {"INDEX.md", "README.md"}

#: Days a 13-week fiscal quarter end may drift past its nominal month boundary.
_DRIFT_DAYS = 5


# --------------------------------------------------------------------------- #
# Fiscal calendars
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class FiscalCalendar:
    """Maps calendar dates to fiscal periods for one company.

    Each of the four runs a different fiscal year, and two of them label it in
    opposite directions, which is a rich source of off-by-one-year errors:

        Home Depot     FY ends late Jan/early Feb, labelled by the START year.
                       FY2026 runs Feb 2026 -> Jan 2027.
        Analog Devices FY ends late Oct/early Nov, labelled by the END year.
                       FY2026 runs Nov 2025 -> Oct 2026.
        Hays           FY ends 30 June, labelled by the END year.
                       FY2026 runs Jul 2025 -> Jun 2026.
        Deere          FY ends late Oct/early Nov, labelled by the END year.
                       FY2026 runs Nov 2025 -> Oct 2026.

    Quarter ends are approximate (all four use 13-week retail-style quarters that
    drift by a few days). That is fine: this is used to order events and to check
    that guidance precedes the period it guides, never to compute a value.
    """

    fy_end_month: int
    label_by_start_year: bool

    def fiscal_year_of(self, d: date) -> int:
        """Fiscal year label containing calendar date `d`."""
        # A date at or before the FY-end month belongs to the FY ending that year.
        fy_ending = d.year if d.month <= self.fy_end_month else d.year + 1
        return fy_ending - 1 if self.label_by_start_year else fy_ending

    def fy_start(self, fiscal_year: int) -> date:
        """Approximate first day of the fiscal year."""
        end_year = fiscal_year + 1 if self.label_by_start_year else fiscal_year
        start_month = self.fy_end_month % 12 + 1
        start_year = end_year - 1 if start_month != 1 else end_year
        return date(start_year, start_month, 1)

    def fy_end(self, fiscal_year: int) -> date:
        """Approximate last day of the fiscal year."""
        end_year = fiscal_year + 1 if self.label_by_start_year else fiscal_year
        # Last day of fy_end_month, close enough for ordering.
        if self.fy_end_month == 12:
            return date(end_year, 12, 31)
        first_of_next = date(end_year, self.fy_end_month + 1, 1)
        return date.fromordinal(first_of_next.toordinal() - 1)

    def period_end(self, period: Period) -> date:
        """Approximate last day of a fiscal period."""
        if period.is_full_year:
            return self.fy_end(period.year)
        start = self.fy_start(period.year)
        # Quarter ends land on the month boundary 3*q months in, give or take the
        # few days of 13-week drift that _DRIFT_DAYS absorbs in period_of().
        months = 3 * period.quarter
        year, month = divmod(start.month - 1 + months, 12)
        first_of_next = date(start.year + year, month + 1, 1)
        return date.fromordinal(first_of_next.toordinal() - 1)

    def period_of(self, d: date) -> Period:
        """The fiscal quarter containing calendar date `d`.

        All four companies use 13-week quarters ending on the weekend nearest a
        month end, so a quarter end can fall a few days *into* the next calendar
        month (ADI's Q2 FY2026 ended 2 May). Month arithmetic on a date nudged
        back by _DRIFT_DAYS absorbs that without needing exact period tables.
        """
        fy = self.fiscal_year_of(d)
        start = self.fy_start(fy)
        nudged = date.fromordinal(d.toordinal() - _DRIFT_DAYS)
        months = (nudged.year - start.year) * 12 + (nudged.month - start.month)
        quarter = min(4, max(1, months // 3 + 1))
        return Period(year=fy, quarter=quarter)


CALENDARS: dict[Company, FiscalCalendar] = {
    Company.HD: FiscalCalendar(fy_end_month=1, label_by_start_year=True),
    Company.ADI: FiscalCalendar(fy_end_month=10, label_by_start_year=False),
    Company.HAS: FiscalCalendar(fy_end_month=6, label_by_start_year=False),
    Company.DE: FiscalCalendar(fy_end_month=10, label_by_start_year=False),
}

#: The period each company is being forecast for, from challenge/companies.json.
TARGET_PERIOD: dict[Company, Period] = {
    Company.HD: Period(year=2026, quarter=2),
    Company.ADI: Period(year=2026, quarter=3),
    Company.HAS: Period(year=2026, quarter=None),
    Company.DE: Period(year=2026, quarter=3),
}


# --------------------------------------------------------------------------- #
# Documents
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Document:
    """One corpus document: trusted frontmatter plus the full frozen text."""

    path: Path
    company: Company
    ticker: str
    published_at: date
    doc_type: DocType
    period_hint: str
    title: str
    text: str

    @property
    def rel_path(self) -> str:
        """Path relative to the corpus root — what citations record."""
        return str(self.path.relative_to(CORPUS_ROOT))

    def contains(self, *needles: str) -> bool:
        low = self.text.lower()
        return any(n.lower() in low for n in needles)


def _parse_frontmatter(raw: str) -> tuple[dict[str, str], str]:
    m = _FRONTMATTER_RE.match(raw)
    if m is None:
        return {}, raw
    fields: dict[str, str] = {}
    for line in m.group("body").splitlines():
        kv = _KV_RE.match(line.strip())
        if kv is None:
            continue
        value = kv.group("value").strip().strip('"')
        # `null` is the corpus's empty marker; resolve the sentinel at the boundary
        # so no downstream code ever compares against the string "null".
        fields[kv.group("key")] = "" if value in {"null", ""} else value
    return fields, raw[m.end() :]


def _title_of(body: str, fallback: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


@lru_cache(maxsize=8)
def _load_all(company: Company) -> tuple[Document, ...]:
    """Parse every document for a company once, newest first. Cached per process."""
    root = CORPUS_ROOT / company.value
    if not root.is_dir():
        raise FileNotFoundError(f"corpus missing for {company.value}: {root}")

    docs: list[Document] = []
    for path in sorted(root.rglob("*.md")):
        if path.name in _SKIP_FILES:
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        fields, body = _parse_frontmatter(raw)
        if not fields.get("published_at"):
            # Without a date we cannot place it in time, so it cannot be used
            # safely in a point-in-time replay. Skip loudly rather than guess.
            continue
        docs.append(
            Document(
                path=path,
                company=company,
                ticker=fields.get("ticker", ""),
                published_at=date.fromisoformat(fields["published_at"]),
                doc_type=DocType(fields.get("document_type", "FILING")),
                period_hint=fields.get("period", ""),
                title=_title_of(body, path.stem),
                text=body,
            )
        )
    docs.sort(key=lambda d: (d.published_at, d.path.name), reverse=True)
    return tuple(docs)


def load(
    company: Company,
    *,
    as_of: date | None = None,
    doc_types: frozenset[DocType] | None = None,
) -> list[Document]:
    """Documents for `company`, newest first, published on or before `as_of`.

    Args:
        company: Corpus slug to load.
        as_of: Point-in-time cutoff. None means the full frozen corpus. This is
            the only lever the backtest needs: it makes the pipeline blind to
            everything published after the given date.
        doc_types: Optional restriction, e.g. filings only.
    """
    docs = _load_all(company)
    if as_of is not None:
        docs = tuple(d for d in docs if d.published_at <= as_of)
    if doc_types is not None:
        docs = tuple(d for d in docs if d.doc_type in doc_types)
    return list(docs)


def load_all_companies(
    *, as_of: date | None = None
) -> dict[Company, list[Document]]:
    """The whole corpus, point-in-time filtered, keyed by company."""
    return {c: load(c, as_of=as_of) for c in Company}
