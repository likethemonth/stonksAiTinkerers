"""Structured, validated, traceable forecast ontology for Agents vs Wall Street.

Three layers, deliberately separated:

    MetricObservation   one (metric, period, value) fact lifted from one document,
                        carrying the as-of date that makes point-in-time replay
                        possible. This is the *only* thing extraction produces.

    Estimate            one estimator's opinion about a target: a value, a sigma,
                        the reasoning, and the observations it consumed.

    MetricForecast      the reconciled number that goes in the workbook, plus the
                        estimates behind it.

Pure Pydantic v2 — no FastAPI, no DB, no I/O. Importable by the extractors, the
estimators, the workbook writer and the tests alike.

Design note on failure policy: a MISSING forecast scores 5.0 (the worst possible
score) under the accuracy rubric, so validation here never refuses to produce a
number. Unit errors hard-fail because they are always bugs; implausible values are
clamped and warned about. See MetricForecast.finalise().
"""

from __future__ import annotations

import re
from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# --------------------------------------------------------------------------- #
# Vocabulary
# --------------------------------------------------------------------------- #


class Unit(str, Enum):
    """Units exactly as the OpenStocks workbooks expect them."""

    USD_M = "USDm"
    GBP_M = "GBPm"
    USD_PER_SHARE = "USD / share"
    GBP_PENCE = "GBp"  # Hays EPS — entered in pence, e.g. 6.2 means 6.2p
    PERCENT = "%"  # entered as points, e.g. 4.5 means 4.5%
    RATIO = "ratio"  # internal only: never submitted, used for shares/tax rates
    COUNT_M = "millions"  # internal only: diluted share counts


#: Units that may appear in a submitted workbook cell.
SUBMITTABLE_UNITS = frozenset(
    {Unit.USD_M, Unit.GBP_M, Unit.USD_PER_SHARE, Unit.GBP_PENCE, Unit.PERCENT}
)


class DocType(str, Enum):
    FILING = "FILING"
    CALL_TRANSCRIPT = "CALL_TRANSCRIPT"
    SLIDE = "SLIDE"


class Kind(str, Enum):
    """What *sort* of number an observation is.

    The distinction drives everything downstream: a GUIDE_MID published before a
    period and the ACTUAL published after it are the two halves of one
    guidance-realisation ratio, which is how the estimators get calibrated.
    """

    ACTUAL = "ACTUAL"  # reported result for a closed period
    GUIDE_MID = "GUIDE_MID"  # midpoint of a guided range
    GUIDE_LOW = "GUIDE_LOW"
    GUIDE_HIGH = "GUIDE_HIGH"
    GUIDE_POINT = "GUIDE_POINT"  # "approximately X", no range given
    CONSENSUS = "CONSENSUS"  # company-compiled analyst consensus (Hays)
    CONSENSUS_LOW = "CONSENSUS_LOW"
    CONSENSUS_HIGH = "CONSENSUS_HIGH"
    GROWTH_PCT = "GROWTH_PCT"  # a disclosed YoY change, not a level


#: Kinds that describe a period *before* it closed. Their as_of must precede the
#: period end; an ACTUAL's must not.
FORWARD_KINDS = frozenset(
    {
        Kind.GUIDE_MID,
        Kind.GUIDE_LOW,
        Kind.GUIDE_HIGH,
        Kind.GUIDE_POINT,
        Kind.CONSENSUS,
        Kind.CONSENSUS_LOW,
        Kind.CONSENSUS_HIGH,
    }
)


class Company(str, Enum):
    """Corpus directory slugs — the canonical company key everywhere."""

    HD = "home-depot"
    ADI = "analog-devices"
    HAS = "hays"
    DE = "deere"


class Engine(str, Enum):
    """Independent top-level estimates and explicitly unweighted critics."""

    STREET = "street"
    FUNDAMENTAL = "fundamental"
    PREDICTION_MARKET = "prediction_market"
    NUMINOUS = "numinous"


class ContributionStatus(str, Enum):
    AVAILABLE = "available"
    SIGNAL_ONLY = "signal_only"
    ABSTAINED = "abstained"


# --------------------------------------------------------------------------- #
# Fiscal periods
# --------------------------------------------------------------------------- #

_PERIOD_RE = re.compile(r"^FY(?P<year>\d{4})(?:Q(?P<q>[1-4]))?$")


class Period(BaseModel):
    """A fiscal period: FY2026Q2, or FY2026 for a full year.

    Ordering is by (year, quarter) with a full year sorting after its Q4, which is
    what you want when walking a history forward.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    year: int = Field(..., ge=2000, le=2100, description="Fiscal year label.")
    quarter: int | None = Field(
        None, ge=1, le=4, description="1-4, or None for a full year."
    )

    @classmethod
    def parse(cls, raw: str) -> "Period":
        """Parse the canonical 'FY2026Q2' / 'FY2026' form."""
        m = _PERIOD_RE.match(raw.strip().upper().replace(" ", ""))
        if m is None:
            raise ValueError(f"unparseable fiscal period: {raw!r}")
        q = m.group("q")
        return cls(year=int(m.group("year")), quarter=int(q) if q else None)

    @property
    def key(self) -> str:
        return f"FY{self.year}" + (f"Q{self.quarter}" if self.quarter else "")

    @property
    def is_full_year(self) -> bool:
        return self.quarter is None

    @property
    def sort_key(self) -> tuple[int, int]:
        # Full year sorts after Q4 of the same year.
        return (self.year, self.quarter if self.quarter else 5)

    def prior_year(self) -> "Period":
        """Same quarter, one fiscal year earlier — the YoY comparison base."""
        return Period(year=self.year - 1, quarter=self.quarter)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.key


# --------------------------------------------------------------------------- #
# Layer 1 — observations
# --------------------------------------------------------------------------- #


class MetricObservation(BaseModel):
    """One fact about one metric in one period, lifted from one document.

    Everything the system knows lives in a list of these. Estimators query them;
    nothing else reads the corpus directly.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    company: Company
    metric_key: str = Field(
        ...,
        min_length=1,
        description="Canonical internal metric name, e.g. 'adj_eps'. See metrics.py.",
    )
    period: Period = Field(..., description="The fiscal period the value describes.")
    value: float
    units: Unit
    kind: Kind

    as_of: date = Field(
        ...,
        description=(
            "published_at of the source document. The point-in-time axis: a replay "
            "with --as-of D must see only observations with as_of <= D."
        ),
    )
    source_file: str = Field(
        ..., min_length=1, description="Path relative to challenge/offline-data/."
    )
    doc_type: DocType
    excerpt: str = Field(
        ..., min_length=1, description="Verbatim text the value was read from."
    )
    extractor: str = Field(
        ...,
        min_length=1,
        description="Rule/extractor id that produced this row, for debugging.",
    )
    note: str | None = Field(None, description="Why this observation matters.")

    @field_validator("excerpt")
    @classmethod
    def _tidy_excerpt(cls, v: str) -> str:
        """Corpus text is PDF-derived: collapse the ragged whitespace."""
        return re.sub(r"\s+", " ", v).strip()

    @model_validator(mode="after")
    def _sanity(self) -> "MetricObservation":
        if self.units == Unit.PERCENT and not (-100.0 <= self.value <= 100.0):
            raise ValueError(
                f"{self.metric_key} {self.period}: {self.value} implausible as "
                "percentage points (4.5 means 4.5%, not 0.045 and not 450)"
            )
        if self.units == Unit.GBP_PENCE and 0 < abs(self.value) < 1:
            raise ValueError(
                f"{self.metric_key} {self.period}: {self.value} looks like pounds; "
                "Hays EPS is pence (6.2 means 6.2p)"
            )
        return self


# --------------------------------------------------------------------------- #
# Layer 2 — estimates
# --------------------------------------------------------------------------- #


class Estimate(BaseModel):
    """One estimator's opinion, with the uncertainty that earns it its weight.

    `sigma` is not decoration — the reconciler weights estimators by 1/sigma^2, so
    an estimator that cannot honestly state its dispersion cannot be combined.
    """

    model_config = ConfigDict(extra="forbid")

    estimator: str = Field(
        ..., min_length=1, description="e.g. 'guidance_realisation', 'seasonal_share'."
    )
    value: float
    sigma: float = Field(
        ...,
        gt=0.0,
        description=(
            "Predictive standard deviation in the metric's own units, from the "
            "historical dispersion of this estimator's correction ratio."
        ),
    )
    n_observations: int = Field(
        ...,
        ge=0,
        description="History depth behind the correction. Drives Bayes shrinkage.",
    )
    anchor: float | None = Field(
        None, description="The disclosed number the correction was applied to."
    )
    correction: float | None = Field(
        None, description="Shrunk multiplicative or additive correction applied."
    )
    reasoning: str = Field(
        ..., min_length=1, description="How anchor + correction produced value."
    )
    observation_ids: list[int] = Field(
        default_factory=list,
        description="Indices into the observation table this estimate consumed.",
    )
    citations: list[str] = Field(
        default_factory=list, description="source_file paths backing the estimate."
    )


class ProbabilityConstraint(BaseModel):
    """One event-probability constraint, deliberately not a point estimate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: Literal["polymarket", "numinous"] = "polymarket"
    relation: Literal["greater_than"] = "greater_than"
    threshold: float
    probability: float = Field(..., ge=0.0, le=1.0)
    volume: float | None = Field(
        None,
        ge=0.0,
        description="Traded volume when the provider is a market; absent for AI forecasts.",
    )
    source_snapshot: str = Field(..., min_length=1)
    citation: str = Field(..., min_length=1)


class EngineContribution(BaseModel):
    """One top-level engine's estimate, research signal, or abstention.

    `source_families` identifies shared information such as management guidance
    or a Street-consensus strike. The meta-forecaster uses it to reduce the
    weight of apparently independent estimates that actually reuse evidence.
    """

    model_config = ConfigDict(extra="forbid")

    engine: Engine
    status: ContributionStatus
    estimate: Estimate | None = None
    signal: ProbabilityConstraint | None = None
    reliability: float = Field(1.0, gt=0.0, le=1.0)
    source_families: list[str] = Field(default_factory=list)
    note: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def _estimate_xor_abstention(self) -> "EngineContribution":
        if self.status is ContributionStatus.AVAILABLE:
            if self.estimate is None or self.signal is not None:
                raise ValueError(
                    f"{self.engine.value}: available contribution needs only an estimate"
                )
        elif self.status is ContributionStatus.SIGNAL_ONLY:
            if self.signal is None or self.estimate is not None:
                raise ValueError(
                    f"{self.engine.value}: signal_only needs a constraint, not an estimate"
                )
        elif self.estimate is not None or self.signal is not None:
            raise ValueError(
                f"{self.engine.value}: abstention cannot carry an estimate or signal"
            )
        return self


class EngineWeight(BaseModel):
    """Auditable meta-forecast weight after reliability and overlap penalties."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    engine: Engine
    raw_weight: float = Field(..., ge=0.0)
    overlap_penalty: float = Field(..., gt=0.0, le=1.0)
    normalized_weight: float = Field(..., ge=0.0, le=1.0)


# --------------------------------------------------------------------------- #
# Layer 3 — the submitted forecast
# --------------------------------------------------------------------------- #


class MetricForecast(BaseModel):
    """One of the three numbers submitted for a company, with its full trail."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    label: str = Field(
        ..., min_length=1, description="EXACT metric label from companies.json."
    )
    units: Unit
    value: float = Field(..., description="The number written into the workbook.")
    sigma: float | None = Field(
        None, gt=0.0, description="Combined predictive sd, for the write-up."
    )
    reasoning: str = Field(
        ..., min_length=1, description="How the estimates reconciled to this value."
    )
    estimates: list[Estimate] = Field(
        default_factory=list, description="Every estimator that ran for this metric."
    )
    engine_contributions: list[EngineContribution] = Field(
        default_factory=list,
        description="The three top-level engine estimates, including abstentions.",
    )
    meta_weights: list[EngineWeight] = Field(
        default_factory=list,
        description="Weights used when this forecast was produced by the meta-forecaster.",
    )
    citations: list[str] = Field(
        default_factory=list, description="Deduplicated source files behind the value."
    )
    plausible_low: float | None = None
    plausible_high: float | None = None
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal problems. Surfaced in the run log, never suppressed.",
    )
    needs_review: bool = Field(
        False, description="Estimators disagreed by more than their stated sigma."
    )

    @model_validator(mode="after")
    def _hard_checks(self) -> "MetricForecast":
        """Only unit errors hard-fail here: they are always bugs, never judgements.

        Plausibility is handled by finalise(), which clamps rather than raises so a
        late surprise can never turn into an empty cell.
        """
        if self.units not in SUBMITTABLE_UNITS:
            raise ValueError(f"{self.label}: {self.units} is not a submittable unit")
        if self.units == Unit.PERCENT and not (-100.0 <= self.value <= 100.0):
            raise ValueError(
                f"{self.label}: {self.value} implausible as percentage points "
                "(enter 4.5 for 4.5%, not 0.045 and not 450)"
            )
        if self.units == Unit.GBP_PENCE and 0 < abs(self.value) < 1:
            raise ValueError(
                f"{self.label}: {self.value} looks like pounds; Hays EPS is pence "
                "(enter 6.2 for 6.2p)"
            )
        if not self.citations and not self.warnings:
            # Never silently ship an uncited number; degrade loudly instead.
            raise ValueError(f"{self.label}: no citations and no warning explaining why")
        return self

    def finalise(self) -> "MetricForecast":
        """Clamp into the plausibility band, recording why. Never raises.

        A number outside its historical band is usually an extraction slip, but it
        might be a genuine surprise — so we clamp to the edge, keep the original in
        a warning, and let a human overrule it before 18:00.
        """
        lo, hi = self.plausible_low, self.plausible_high
        if lo is not None and hi is not None and lo > hi:
            self.warnings.append(f"band inverted ({lo} > {hi}); band ignored")
            return self
        original = self.value
        if lo is not None and original < lo:
            self.value = lo
            self.warnings.append(
                f"clamped {original} up to band floor {lo} — re-check evidence"
            )
        elif hi is not None and original > hi:
            self.value = hi
            self.warnings.append(
                f"clamped {original} down to band ceiling {hi} — re-check evidence"
            )
        return self


class CompanyForecast(BaseModel):
    """The three metrics for one company, ready to write to its workbook."""

    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(..., min_length=1)
    company: Company
    period: Period
    output_file: str = Field(
        ..., min_length=1, description="Exact filename, e.g. HD-FY2026Q2.xlsx."
    )
    as_of: date = Field(
        ..., description="Point-in-time cutoff this forecast was produced under."
    )
    metrics: list[MetricForecast] = Field(..., min_length=3, max_length=3)

    @model_validator(mode="after")
    def _three_distinct(self) -> "CompanyForecast":
        labels = [m.label for m in self.metrics]
        if len(set(labels)) != 3:
            raise ValueError(f"{self.ticker}: expected 3 distinct metrics, got {labels}")
        if not self.output_file.endswith(".xlsx"):
            raise ValueError(f"{self.ticker}: output_file must be .xlsx")
        return self

    @property
    def needs_review(self) -> bool:
        return any(m.needs_review for m in self.metrics)
