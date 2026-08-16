/**
 * Cross-checks architecture/index.html against the artefacts of the last run.
 *
 * The architecture page locks at 17:15 while the final run happens after it, so
 * every number quoted on the page is a claim that can silently go stale the
 * moment the pipeline is re-run. This has already happened twice: a Hays net
 * fees fix and a batch of extractor repairs both moved figures the page still
 * asserted. A judge cross-referencing the page against forecast-audit.json is
 * the worst way to discover that.
 *
 * Checked against submission/forecast-audit.json and the observation store:
 *   - every one of the 12 forecast rows: value and realized engine weights
 *   - the headline counts (documents, observations, tests, abstentions)
 *
 * Run after `npm run forecast` and before the page is uploaded.
 */
import fs from "node:fs/promises";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const htmlPath = path.join(root, "architecture", "index.html");
const auditPath = path.join(root, "submission", "forecast-audit.json");

const TICKER_LABEL = { HD: "HD", ADI: "ADI", "LSE:HAS": "Hays", DE: "DE" };
const ENGINE_LABEL = { street: "Street", fundamental: "Fundamental", prediction_market: "Market" };

const problems = [];
const fail = (message) => problems.push(message);

const html = await fs.readFile(htmlPath, "utf8");
const audit = JSON.parse(await fs.readFile(auditPath, "utf8"));

/** Strip tags and decode the few entities the page actually uses. */
const text = (fragment) =>
  fragment
    .replace(/<[^>]+>/g, "")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&nbsp;/g, " ")
    .trim();

// --- the forecast table -----------------------------------------------------

// Scope to the "Forecast outputs" table: the 03b ensemble table reuses the
// same Company/Metric leading cells and must not shadow the submitted rows.
const forecastStart = html.indexOf('aria-label="Forecast outputs"');
const forecastTable = html.slice(forecastStart, html.indexOf("</table>", forecastStart));
const tableRows = new Map();
for (const row of forecastTable.match(/<tr[^>]*>[\s\S]*?<\/tr>/g) ?? []) {
  const cells = [...row.matchAll(/<td[^>]*>([\s\S]*?)<\/td>/g)].map((m) => text(m[1]));
  if (cells.length >= 5) tableRows.set(`${cells[0]}|${cells[1]}`, { value: cells[2], weights: cells[4] });
}

// The final combination is the four-lens ensemble, so the weights column is
// rebuilt from research/lens-ensemble.json — same rule as forecast/ensemble.py.
const LENS_LABEL = { anchor: "Anchor", driver: "Driver", ml: "ML", market: "Market" };
const ensembleRows = new Map();
try {
  const lensEnsemble = JSON.parse(
    await fs.readFile(path.join(root, "research", "lens-ensemble.json"), "utf8"));
  for (const row of lensEnsemble.rows) ensembleRows.set(`${row.ticker}|${row.label}`, row);
} catch (error) {
  fail(`cannot read research/lens-ensemble.json: ${error.message}`);
}

function expectedWeights(row) {
  const voted = new Map(row.lenses.map((lens) => [lens.lens, lens]));
  const segments = [];
  for (const key of ["anchor", "driver", "ml", "market"]) {
    if (voted.has(key)) segments.push(`${LENS_LABEL[key]} ${Math.round(voted.get(key).weight * 100)}%`);
  }
  const absent = ["anchor", "driver", "ml", "market"].filter((key) => !voted.has(key)).map((key) => LENS_LABEL[key]);
  if (absent.length) segments.push(`${absent.join(" / ")} abstained`);
  return segments.join(" · ");
}

let checked = 0;
for (const forecast of audit.forecasts) {
  for (const metric of forecast.metrics) {
    checked += 1;
    const key = `${TICKER_LABEL[forecast.ticker]}|${metric.label}`;
    const row = tableRows.get(key);
    if (!row) {
      fail(`table is missing a row for ${key.replace("|", " · ")}`);
      continue;
    }
    const expectedValue = metric.value.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    if (row.value !== expectedValue) {
      fail(`${key.replace("|", " · ")}: page says ${row.value}, audit says ${expectedValue}`);
    }
    const ensembleRow = ensembleRows.get(key);
    if (!ensembleRow) {
      fail(`ensemble artifact is missing ${key.replace("|", " · ")}`);
      continue;
    }
    // The audit's submitted value must BE the ensemble final (forecast.run's
    // last stage), and the audit must say so explicitly.
    if (Math.abs(metric.value - ensembleRow.final) > 0.005) {
      fail(`${key.replace("|", " · ")}: audit value ${metric.value} != ensemble final ${ensembleRow.final}`);
    }
    if (metric.final_combination !== "four_lens_ensemble") {
      fail(`${key.replace("|", " · ")}: audit does not record the four-lens final combination`);
    }
    const weights = expectedWeights(ensembleRow);
    if (row.weights !== weights) {
      fail(`${key.replace("|", " · ")} weights: page says "${row.weights}", ensemble says "${weights}"`);
    }
  }
}
if (checked !== 12) fail(`audit holds ${checked} metrics, expected 12`);

// --- the headline counts ----------------------------------------------------

/** Assert that `value` appears in the page, formatted the way the page formats it. */
function claim(label, value) {
  const formatted = value.toLocaleString("en-US");
  const found = html.includes(`>${formatted}<`) || html.includes(`${formatted} `);
  if (!found) fail(`page never states the current ${label} (${formatted})`);
}

const observations = (
  await Promise.all(
    ["analog-devices", "deere", "hays", "home-depot"].map(async (company) =>
      JSON.parse(await fs.readFile(path.join(root, "data", "observations", `${company}.json`), "utf8"))
    )
  )
).reduce((total, store) => total + store.observations.length, 0);
claim("observation count", observations);

const abstentions = audit.forecasts
  .flatMap((forecast) => forecast.metrics)
  .flatMap((metric) => metric.engine_contributions)
  .filter((contribution) => contribution.status === "abstained").length;
if (!html.includes(`${abstentions} OF 12`) && !html.includes(`>${abstentions}<`)) {
  fail(`page never states the current market-abstention count (${abstentions})`);
}

if (audit.failures.length) fail(`the audit records ${audit.failures.length} run failure(s)`);

// --- the system backtest ----------------------------------------------------

// The validation section quotes the replay's own scores. Those move whenever an
// extractor is repaired, so they are re-derived here for the same reason the
// forecast rows are: a judge should not be the one to find the page has drifted.
const backtestPath = path.join(root, "research", "system-backtest.json");
let backtest = null;
try {
  backtest = JSON.parse(await fs.readFile(backtestPath, "utf8"));
} catch {
  fail("research/system-backtest.json is missing; run npm run forecast before uploading");
}

if (backtest) {
  const overall = backtest.summary.overall;
  if (!overall) {
    fail("the system backtest scored no cells");
  } else {
    claim("system backtest cell count", overall.n);
    for (const [label, value] of [
      ["mean score", overall.meanScore.toFixed(2)],
      ["median score", overall.medianScore.toFixed(2)],
    ]) {
      if (!html.includes(value)) fail(`page never states the current system backtest ${label} (${value})`);
    }
    if (!html.includes(`beat the benchmark on ${overall.beat}`)) {
      fail(`page never states the current system backtest win count (${overall.beat})`);
    }
  }

  for (const [key, block] of Object.entries(backtest.summary.byMetric)) {
    const [ticker, metric] = key.split(" · ");
    const rowLabel = `${TICKER_LABEL[ticker] ?? ticker} · ${metric}`;
    const pattern = new RegExp(
      `<td>${rowLabel.replace(/[.*+?^${}()|[\]\\]/g, "\\$&").replace(/&/g, "&amp;")}</td>` +
        `\\s*<td class="num">(\\d+)</td>` +
        `\\s*<td class="num">([\\d.]+)</td>` +
        `\\s*<td class="num">(\\d+) / (\\d+)</td>`
    );
    const match = html.match(pattern);
    if (!match) {
      fail(`validation table is missing a row for ${rowLabel}`);
      continue;
    }
    const [, n, mean, beat] = match;
    if (Number(n) !== block.n) fail(`${rowLabel}: page says ${n} cells, backtest says ${block.n}`);
    if (mean !== block.meanScore.toFixed(2)) {
      fail(`${rowLabel}: page says mean ${mean}, backtest says ${block.meanScore.toFixed(2)}`);
    }
    if (Number(beat) !== block.beat) {
      fail(`${rowLabel}: page says beat ${beat}, backtest says ${block.beat}`);
    }
  }
}

// --- the four-lens ensemble (section 03b) ------------------------------------
// The injected table must match research/lens-ensemble.json, and the artifact
// must be internally consistent: weights sum to 1, the final is the weighted
// mean, and it sits inside the participating lenses' range.

const ensemblePath = path.join(root, "research", "lens-ensemble.json");
try {
  const ensemble = JSON.parse(await fs.readFile(ensemblePath, "utf8"));
  for (const row of ensemble.rows) {
    const weightSum = row.lenses.reduce((sum, lens) => sum + lens.weight, 0);
    if (Math.abs(weightSum - 1) > 0.005) {
      fail(`ensemble ${row.ticker} · ${row.label}: weights sum to ${weightSum.toFixed(4)}`);
    }
    const mean = row.lenses.reduce((sum, lens) => sum + lens.weight * lens.value, 0);
    if (Math.abs(mean - row.final) > Math.max(0.02, Math.abs(row.final) * 0.001)) {
      fail(`ensemble ${row.ticker} · ${row.label}: final ${row.final} != weighted mean ${mean.toFixed(2)}`);
    }
    const values = row.lenses.map((lens) => lens.value);
    if (row.final < Math.min(...values) - 0.01 || row.final > Math.max(...values) + 0.01) {
      fail(`ensemble ${row.ticker} · ${row.label}: final ${row.final} outside lens range`);
    }
    const finalText = row.final.toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    if (!html.includes(`<strong>${finalText}</strong>`)) {
      fail(`ensemble table is missing the final ${finalText} for ${row.ticker} · ${row.label}`);
    }
  }
  if (ensemble.rows.length !== 12) fail(`ensemble artifact has ${ensemble.rows.length} rows, expected 12`);
  if (!html.includes('id="ensemble"')) fail("page is missing the 03b ensemble section");
} catch (error) {
  fail(`ensemble check failed: ${error.message}`);
}

// --- report -----------------------------------------------------------------

if (problems.length) {
  for (const problem of problems) console.error(`FAIL architecture/index.html: ${problem}`);
  console.error(`\n${problems.length} claim(s) on the architecture page no longer match the run.`);
  process.exitCode = 1;
} else {
  console.log(`PASS architecture/index.html: 12 forecast rows, weights and headline counts match the run`);
}
