"""For/against thesis generation over the observation table.

The deterministic pipeline produces a number and a reasoning trail. What it
cannot do is weigh competing readings of the same evidence — whether ADI's
record bookings outrun the guidance beat already priced into the anchor, whether
Hays' German hours-worked drag offsets the disposal effect. That is a judgement
task, and it is the one place in this system where a language model earns its
place.

Two constraints make it safe to let a model touch a submitted number:

1.  **It may reason, but it may not invent evidence.** Every thesis must cite
    observation IDs that exist in the table. A thesis citing an ID that is not
    there is dropped before it can move anything, so a hallucinated fact cannot
    reach a workbook cell — the model argues over facts the deterministic layer
    already extracted and range-checked.

2.  **Its influence is bounded.** The net adjustment is capped at a fraction of
    the anchor's own sigma. A thesis storm cannot run away with the forecast; at
    worst it nudges a number the deterministic layer already stands behind.

Fail-safe by construction: any error, timeout, missing credential, or malformed
response yields a zero adjustment and the deterministic anchor ships unchanged.
The model can only refine a working forecast, never block one.

Provider: OpenAI, via the credit supplied by the event organisers. The key is
read from OPENAI_API_KEY and is never written to the repository, the run log,
the audit file or entry.json.
"""

from __future__ import annotations

import json
import os
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from forecast.schema import MetricObservation

#: Reasoning model, so the effort setting matters more than the prompt length.
MODEL = os.environ.get("THESIS_MODEL", "gpt-5")
MAX_OUTPUT_TOKENS = 16_000
REASONING_EFFORT = "medium"

#: The net adjustment may not exceed this multiple of the anchor's sigma. The
#: deterministic estimate is backtested; the theses are not, so they get to nudge
#: rather than overrule.
ADJUSTMENT_CAP_SIGMAS = 0.75

#: A thesis surviving the adversarial pass needs at least this confidence to
#: count toward the net adjustment.
MIN_CONFIDENCE = 0.35

#: Whether a computed adjustment actually moves the submitted number.
#:
#: OFF by default, and that default is a finding rather than timidity. On the
#: first real run — Hays pre-exceptional operating profit — the model returned
#: three AGAINST theses and no FOR, netting -2.7 and pulling the forecast to
#: ~42.8. That is BELOW the 43.5 company-compiled consensus, on a metric where
#: management had explicitly stated they expect the TOP of a 37.0-46.0 range.
#: The model had that evidence in its table and reasoned past it.
#:
#: The theses remain valuable: they are recorded in the audit file and rendered
#: in the report, and the adversarial pass caught a genuine factual error in one
#: of them. But argument quality is not the same as calibration, and the
#: deterministic anchors are backtested where these are not. Set
#: THESIS_APPLY=1 to let them move numbers.
APPLY_ADJUSTMENTS = os.environ.get("THESIS_APPLY") == "1"


class Thesis(BaseModel):
    """One argument that the reported figure lands above or below the anchor."""

    model_config = ConfigDict(extra="forbid")

    direction: Literal["FOR", "AGAINST", "NEUTRAL"] = Field(
        ...,
        description=(
            "FOR = the reported figure lands ABOVE the anchor. "
            "AGAINST = it lands BELOW. "
            "NEUTRAL = the point is material context a reader should know, but "
            "does not push the figure either way (for example, an effect already "
            "reflected in the anchor, or a risk that cuts both ways)."
        ),
    )
    claim: str = Field(
        ..., min_length=1, description="The argument in one or two sentences."
    )
    observation_ids: list[int] = Field(
        ...,
        min_length=1,
        description=(
            "Indices of observations from the supplied table that support this "
            "claim. Every id must appear in the table; invented ids are rejected."
        ),
    )
    effect: float = Field(
        ...,
        description=(
            "Size of the effect on the metric, in the metric's own units, as a "
            "positive magnitude. Direction is carried by the direction field."
        ),
    )
    confidence: float = Field(..., ge=0.0, le=1.0)


class ThesisSet(BaseModel):
    """The model's full for/against reading of one metric."""

    model_config = ConfigDict(extra="forbid")

    theses: list[Thesis] = Field(default_factory=list, max_length=8)


class Verdict(BaseModel):
    """One adversarial ruling on one thesis."""

    model_config = ConfigDict(extra="forbid")

    index: int = Field(..., ge=0, description="Position of the thesis being judged.")
    survives: bool = Field(
        ...,
        description=(
            "False if the cited evidence does not support the claim, or if the "
            "effect is already reflected in the anchor."
        ),
    )
    rebuttal: str = Field(..., min_length=1, description="Why it survives or not.")


class VerdictSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdicts: list[Verdict] = Field(default_factory=list)


class ThesisOutcome(BaseModel):
    """What the thesis pass concluded for one metric."""

    model_config = ConfigDict(extra="forbid")

    adjustment: float = 0.0
    theses: list[Thesis] = Field(default_factory=list)
    rebuttals: dict[int, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    ran: bool = False


_GENERATE_PROMPT = """\
You are reviewing a financial forecast. The forecast is {anchor:,.4g} \
{units} for {label}, {company} {period}, produced by a deterministic pipeline \
with a standard deviation of {sigma:,.4g}.

Its reasoning was:
{reasoning}

Below is the complete table of facts extracted from the company's own filings. \
Each row is numbered. These are the only facts available to you.

{table}

Argue both sides. Give the strongest arguments that the reported figure will \
land ABOVE this forecast (direction FOR), and the strongest that it will land \
BELOW (direction AGAINST). Aim for two to three of each where the evidence \
supports them; give fewer rather than padding with weak arguments.

Where a point is genuinely material for a reader but does not push the figure \
either way — an effect already reflected in the anchor, a risk that cuts both \
ways, a caveat about the evidence itself — mark it NEUTRAL with an effect of 0 \
rather than forcing it into a direction.

Rules:
- Cite only observation ids that appear in the table above. Do not introduce \
figures, events, or context that are not in it.
- State each effect as a positive magnitude in {units}, sized to what the cited \
evidence actually supports.
- Do not argue for an effect already reflected in the anchor's reasoning.
- If the evidence genuinely supports no argument in a direction, return none \
for that direction rather than inventing one."""

_REFUTE_PROMPT = """\
You are auditing arguments made about a financial forecast of {anchor:,.4g} \
{units} for {label}. Assume each argument is wrong and try to refute it.

The facts available are:
{table}

The arguments:
{theses}

For each argument, judge whether it survives. Mark it as not surviving if the \
cited observations do not actually support the claim, if the effect is already \
reflected in the forecast, or if the magnitude is not supported by the evidence. \
Default to not surviving when uncertain."""


def _format_table(observations: list[MetricObservation], limit: int = 60) -> str:
    """Number the observations so a thesis can cite them by index."""
    rows = []
    for i, o in enumerate(observations[:limit]):
        excerpt = o.excerpt[:200]
        rows.append(
            f"[{i}] {o.period.key} {o.metric_key} {o.kind.value} = "
            f"{o.value:,.4g} {o.units.value} (as of {o.as_of}) — \"{excerpt}\""
        )
    return "\n".join(rows)


def _client():
    """The OpenAI client, or None when no credential is configured.

    A missing key is a normal, expected state — the deterministic pipeline is
    the product, and this layer is an optional refinement on top of it. The run
    simply reports that the thesis pass was skipped.
    """
    try:
        import openai
    except ImportError:
        return None
    if not os.environ.get("OPENAI_API_KEY"):
        return None
    return openai.OpenAI(timeout=120.0, max_retries=2)


def _ask(client, prompt: str, text_format):
    """One structured call. Returns the parsed object, or None if unusable.

    Structured outputs constrain the response to the Pydantic schema, so a
    malformed reply is a parse failure rather than a number that silently
    misreads. A refusal or an incomplete response yields None.
    """
    response = client.responses.parse(
        model=MODEL,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        reasoning={"effort": REASONING_EFFORT},
        text_format=text_format,
        input=[{"role": "user", "content": prompt}],
    )
    if getattr(response, "status", None) == "incomplete":
        return None
    return getattr(response, "output_parsed", None)


def run_theses(
    *,
    label: str,
    company: str,
    period: str,
    units: str,
    anchor: float,
    sigma: float,
    reasoning: str,
    observations: list[MetricObservation],
) -> ThesisOutcome:
    """Generate, adversarially test, and adjudicate theses for one metric.

    Never raises: every failure path returns a zero adjustment so the caller
    ships the deterministic anchor unchanged.
    """
    outcome = ThesisOutcome()

    client = _client()
    if client is None:
        outcome.notes.append(
            "no OPENAI_API_KEY configured; deterministic anchor used unchanged"
        )
        return outcome
    if not observations:
        outcome.notes.append("no observations to reason over")
        return outcome

    table = _format_table(observations)
    try:
        generated = _ask(
            client,
            _GENERATE_PROMPT.format(
                anchor=anchor,
                units=units,
                label=label,
                company=company,
                period=period,
                sigma=sigma,
                reasoning=reasoning,
                table=table,
            ),
            ThesisSet,
        )
    except Exception as exc:  # noqa: BLE001 - never let this break a run
        outcome.notes.append(f"thesis generation failed: {type(exc).__name__}: {exc}")
        return outcome

    if generated is None or not generated.theses:
        outcome.notes.append("no theses returned")
        return outcome

    # Anti-hallucination gate: a thesis may only rest on observations that exist.
    valid_ids = range(min(len(observations), 60))
    grounded: list[Thesis] = []
    for thesis in generated.theses:
        bad = [i for i in thesis.observation_ids if i not in valid_ids]
        if bad:
            outcome.notes.append(
                f"dropped thesis citing non-existent observations {bad}: "
                f"{thesis.claim[:80]}"
            )
            continue
        grounded.append(thesis)

    if not grounded:
        outcome.notes.append("every thesis cited evidence that does not exist")
        return outcome

    # Adversarial pass. If it fails, keep the theses but trust them less by
    # requiring the confidence floor to carry the whole decision.
    try:
        listing = "\n".join(
            f"[{i}] {t.direction}: {t.claim} (effect {t.effect:,.4g}, "
            f"cites {t.observation_ids})"
            for i, t in enumerate(grounded)
        )
        judged = _ask(
            client,
            _REFUTE_PROMPT.format(
                anchor=anchor, units=units, label=label, table=table, theses=listing
            ),
            VerdictSet,
        )
    except Exception as exc:  # noqa: BLE001
        outcome.notes.append(f"adversarial pass failed: {type(exc).__name__}: {exc}")
        judged = None

    survivors: list[Thesis] = []
    if judged is None:
        survivors = [t for t in grounded if t.confidence >= MIN_CONFIDENCE]
        outcome.notes.append("no adversarial verdicts; kept theses on confidence alone")
    else:
        refuted = {v.index for v in judged.verdicts if not v.survives}
        outcome.rebuttals = {v.index: v.rebuttal for v in judged.verdicts}
        for i, thesis in enumerate(grounded):
            if i in refuted or thesis.confidence < MIN_CONFIDENCE:
                continue
            survivors.append(thesis)

    outcome.theses = grounded
    outcome.ran = True

    # Net the survivors, weighting each by its own confidence, then cap.
    # NEUTRAL theses are recorded and displayed but never move the number —
    # that is what makes them a useful place to put "already priced in".
    net = sum(
        (t.effect if t.direction == "FOR" else -t.effect) * t.confidence
        for t in survivors
        if t.direction in ("FOR", "AGAINST")
    )
    cap = ADJUSTMENT_CAP_SIGMAS * abs(sigma)
    if abs(net) > cap:
        outcome.notes.append(
            f"net thesis effect {net:,.4g} capped to {cap:,.4g} "
            f"({ADJUSTMENT_CAP_SIGMAS} sigma)"
        )
        net = cap if net > 0 else -cap
    outcome.adjustment = net
    if not APPLY_ADJUSTMENTS:
        outcome.notes.append(
            f"advisory only: computed adjustment {net:,.4g} recorded but NOT "
            "applied (set THESIS_APPLY=1 to enable)"
        )
    return outcome


def effective_adjustment(outcome: ThesisOutcome) -> float:
    """The adjustment the writer should actually apply — zero in advisory mode."""
    return outcome.adjustment if APPLY_ADJUSTMENTS else 0.0


def outcome_payload(outcome: ThesisOutcome) -> dict[str, object]:
    """JSON-serialisable form, for the audit file and the report page."""
    return json.loads(outcome.model_dump_json())
