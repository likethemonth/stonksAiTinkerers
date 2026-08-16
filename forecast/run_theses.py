"""Run the for/against thesis pass over an existing forecast run.

    python -m forecast.run_theses

Reads submission/forecast-audit.json, argues both sides of all twelve numbers
against each company's evidence table, and writes the results back into the same
audit file. Kept separate from `forecast.run` on purpose: the workbooks are
written and validated before any model is called, so a slow or failing model can
never delay or damage a submission.

The twelve metrics are independent, so they run concurrently — the pass is
entirely latency-bound on the model, and serially it takes long enough that it
becomes a reason not to run it.
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from forecast.corpus import load
from forecast.extract import adi, deere, hays, home_depot
from forecast.metrics import display_name
from forecast.schema import Company
from forecast.thesis import outcome_payload, run_theses

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIT = REPO_ROOT / "submission" / "forecast-audit.json"

EXTRACTORS = {
    Company.HD: home_depot.extract,
    Company.ADI: adi.extract,
    Company.HAS: hays.extract,
    Company.DE: deere.extract,
}

#: One worker per metric would hammer the rate limit; this keeps the whole pass
#: under a couple of minutes without bunching every request into one instant.
MAX_WORKERS = 6


def _observations(company: Company, as_of: date | None):
    extractor = EXTRACTORS.get(company)
    if extractor is None:
        return []
    rows = extractor(load(company, as_of=as_of), [])
    rows.sort(key=lambda o: o.as_of, reverse=True)
    return rows


def main() -> int:
    if not AUDIT.is_file():
        print(f"no audit at {AUDIT} — run `python -m forecast.run` first")
        return 1

    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    as_of = None

    # Extract once per company, not once per metric.
    tables = {}
    for forecast in audit["forecasts"]:
        company = Company(forecast["company"])
        tables[company] = _observations(company, as_of)
        print(f"{forecast['ticker']}: {len(tables[company])} observations")

    jobs = []
    for forecast in audit["forecasts"]:
        company = Company(forecast["company"])
        for metric in forecast["metrics"]:
            jobs.append((forecast, company, metric))

    def work(job):
        forecast, company, metric = job
        sigma = metric.get("sigma") or abs(float(metric["value"])) * 0.02
        outcome = run_theses(
            label=metric["label"],
            company=display_name(company),
            period=forecast["period"],
            units=metric["units"],
            anchor=float(metric["value"]),
            sigma=float(sigma),
            reasoning=metric.get("reasoning", ""),
            observations=tables[company],
        )
        return forecast["ticker"], metric["label"], outcome

    print(f"\nrunning {len(jobs)} metrics across {MAX_WORKERS} workers...\n")
    results = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        for ticker, label, outcome in pool.map(work, jobs):
            results.setdefault(ticker, {})[label] = outcome_payload(outcome)
            counts: dict[str, int] = {}
            for thesis in outcome.theses:
                counts[thesis.direction] = counts.get(thesis.direction, 0) + 1
            shape = " ".join(f"{k}:{v}" for k, v in sorted(counts.items())) or "none"
            print(
                f"  {ticker:8s} {label:44s} {shape:28s} "
                f"computed {outcome.adjustment:+,.4g}"
            )
            for note in outcome.notes:
                print(f"      {note}")

    audit["theses"] = results
    AUDIT.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")
    print(f"\nwrote theses into {AUDIT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
