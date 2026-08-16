## NIIA

> *To know what you don't know — that is the origin of being.*
> *不知爲不知 是源也*

NIIA CLI is installed. Run `niia` in the terminal. Start from there.

## Forecast dashboard trace contract

The dashboard visualizes four company storms with three metric strikes per company. Each strike ends at one of the twelve final submitted workbook values.

The forecasting backend currently emits observations, estimates, engine contributions, reasoning text, citations, uncertainty, meta-weights, warnings, and final values. It does **not** yet emit a chronological replay of forecast revisions.

A later backend pass must add an ordered `TraceEvent` representation containing at least: sequence, stage, engine, title, claim, before value, delta, after value, uncertainty, calculation, evidence, citations, status (`accepted`, `rejected`, `warning`, or `abstained`), and parent event IDs. Until that exists, prototype trace events must be clearly identified as illustrative UI data and must not be presented as recorded agent actions or hidden chain-of-thought.
