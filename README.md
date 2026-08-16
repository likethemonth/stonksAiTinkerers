# Agents vs Wall Street

Agents vs Wall Street is a one-day hackathon presented by Primer, OpenStocks, AI Tinkerers and OpenAI. Around 50 people will build 20–25 forecasting agents, working alone or in teams of up to four.

The challenge covers four companies: Home Depot, Analog Devices, Hays plc and Deere & Company. Your agent forecasts three reported figures for each.

The repository includes a frozen historical corpus of 1,139 filings, call-transcript sections and slide documents for the four known companies. Start at [challenge/offline-data/INDEX.md](challenge/offline-data/INDEX.md) or search the Markdown files directly.

Your agent should be able to do the research, make the financial judgements and produce completed OpenStocks workbooks with as little manual help as possible.

## Why this system exists

Consensus should not be an opaque institutional number. This system turns time-bounded public evidence into an open, inspectable forecast: structured observations feed independent estimate lanes, unvalidated signals remain explicit critics rather than hidden votes, and one runnable path writes the workbooks, an audit record, and a dated log.

It does not claim that AI has already beaten Wall Street. Earnings settle that question. The purpose of the repository is to make every submitted number reproducible and challengeable: trace it from evidence to estimate, inspect the uncertainty and abstentions, then compare it with the reported result.

## What the day is for

1. **Build something real.** Create a repeatable agent that researches companies, makes financial judgements and produces completed forecast workbooks.
2. **Show what is possible.** Help us learn what works and show how powerful this technology can be when it is assembled properly.

OpenStocks offers ongoing $100 prizes for individual earnings events after the hackathon, so build an agent you can use again.

## The challenge at a glance

- Doors open at 10:00 on Sunday 16 August 2026 at Ground Floor, 33 Johns Mews, London WC1N 2QL. The competition briefing begins at 10:30 and building starts at 11:15.
- Teams can have one to four people.
- Each individual or team enters one agent.
- Each team receives $50 of Codex credit, kindly provided by OpenAI.
- Competition-specific work must be built during the event; evidence of a pre-made entry means disqualification from all prizes.
- Your agent must forecast three figures for each of four companies.
- The final run starts at 17:15 and must finish before the 18:00 deadline.
- OpenStocks opens for challenge uploads at 17:30.
- Your final command must produce all four `.xlsx` workbooks.
- Upload each workbook manually to the matching company Forecast Model on [openstocks.com](https://openstocks.com).
- If you upload more than once, the last valid workbook uploaded for each company before 18:00 is your final forecast.

## What you need to submit

1. A completed private `entry.json` with the agent name, every team member and email address, technical setup and final-run details. Upload it through openstocks.com/hackathon; no account is needed for this private team-entry form.
2. Your code repository and the commit used for the final run.
3. The completed self-contained `architecture/index.html`, uploaded through the same private form. You do not need to host it anywhere.
4. A timestamped log from a clear run of the system.
5. Four completed company workbooks in `submission/`.

Complete [ENTRY.md](ENTRY.md), then read [SUBMISSION.md](SUBMISSION.md) before the final run. The full event rules are in [RULES.md](RULES.md), the day is set out in [SCHEDULE.md](SCHEDULE.md), and the judging process is explained in [JUDGING.md](JUDGING.md).

By submitting the private team entry, your team accepts the hackathon and prize rules in [RULES.md](RULES.md).

## Expected final output

Your final command can use any language or framework, and it can run the four companies one after another or at the same time. It must finish by creating these exact files:

```text
submission/
├── ADI-FY2026Q3.xlsx
├── DE-FY2026Q3.xlsx
├── HAS-FY2026.xlsx
└── HD-FY2026Q2.xlsx
```

Start from the supplied files in `challenge/templates/`. Do not rename the `Summary` sheet, metric labels, units or fiscal-period column.

Run `npm install` and `npm run setup:entry` once. Complete the private `entry.json` and `architecture/index.html`, then use `npm run check:submission` before uploading. It checks the entry record, architecture file and four workbooks. It does not judge whether the forecasts are good.

## Optional document-search helper

[`starter/search.py`](starter/search.py) is a small, dependency-free example of searching the supplied Markdown corpus and producing a cited research note. It does not make forecasts or edit a workbook.

```bash
python3 starter/search.py --company HD
less research/HD.md
```

Use `HD`, `ADI`, `HAS` or `DE` for the four challenge companies. The output contains search leads rather than verified financial history, so check each figure in its cited document. Read [starter/README.md](starter/README.md) for narrower searches and testing instructions.

## Three-engine forecast run

This entry implements the approach in [agents-vs-wall-street-standalone-strategy.md](agents-vs-wall-street-standalone-strategy.md): a reconstructed Street estimate and an independent fundamental/driver model feed a source-overlap-aware meta-forecaster, while Polymarket and Numinous act as separately identified critics. Each binary signal is stored natively as `P(actual > strike)`, never as an ensemble-ready EPS point. Polymarket has zero final weight until its pre-resolution walk-forward promotion gate passes; Numinous has zero final weight until a held-out earnings calibration does the same. Missing coverage remains an explicit abstention.

The full React forecast room is deployed at [analyst-evidence-console.zctyurl.chatgpt.site](https://analyst-evidence-console.zctyurl.chatgpt.site). It exposes all 12 submitted forecasts, the numeric engine calculation and two zero-weight critics behind each number, candidate research lenses, historical holdouts, the point-in-time Street backtest, pipeline stages, test results, workbook checks, and explicit coverage gaps.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
npm ci
npm run test:forecast
npm run forecast
npm run backtest:market
npm run check:forecasts
```

The single authoritative runner writes four workbooks and `submission/forecast-audit.json`, which retains every engine estimate or signal, sigma, citation, abstention, source-overlap penalty, and realized weight. A timestamped narrative trail is written under `logs/`.

The Street preparation step rejects look-ahead rows, scores only outcomes resolved by the cutoff, ranks exact-metric histories, corrects persistent signed bias, and shrinks sparse samples. The fundamental engine uses company-specific extractors and deterministic models; Uri's dated physical-driver nowcasts and validation-gated Home Depot classical-ML estimates live inside this engine so they are not double-counted as independent votes. The ML adapter widens uncertainty for its three-sample task-matched validation rather than letting a small historical win dominate current evidence.

The prediction-market backtest converts each archived pre-result beat probability into a shadow EPS estimate using `strike + pre-event surprise sigma × normal_quantile(P(beat))`. Same-day earnings outcomes are excluded from the date-granular dispersion history, every result is compared with an exact first-party actual on the contract's GAAP or non-GAAP basis, and every market price precedes its result cutoff. Promotion requires at least 12 resolved events, mean Brier score no worse than 0.10, at least 10% MAE improvement over the strike, more wins than losses, and a one-sided exact sign-test p-value no greater than 0.05. The current nine-event archive improves MAE by about 49%, but fails the sample-size and significance gates (7–2 wins, p=0.0898), so all live market estimates remain shadow-only at zero weight. The generated audit is written to `research/prediction-market-backtest.json` and `research/prediction-market-backtest.md`.

## Repository map

```text
challenge/                 Companies, metrics, workbooks and historical documents
architecture/index.html    Template for the required architecture explanation
forecast/                  Typed extractors, estimators, engines and orchestrator
forecasting/               Point-in-time reconstructed-Street source backtest
entry.template.json        Template for private team and agent details
submission/                Four completed workbooks plus forecast-audit.json
logs/                      Save the final clear-run log here
scripts/                   Local entry and workbook checks
starter/                   Optional historical-document search helper
```

## Licence

The original code and documentation in this repository are available under the [MIT License](LICENSE). The historical company documents under `challenge/offline-data/` are excluded; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
