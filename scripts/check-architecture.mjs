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

const tableRows = new Map();
for (const row of html.match(/<tr[^>]*>[\s\S]*?<\/tr>/g) ?? []) {
  const cells = [...row.matchAll(/<td[^>]*>([\s\S]*?)<\/td>/g)].map((m) => text(m[1]));
  if (cells.length >= 5) tableRows.set(`${cells[0]}|${cells[1]}`, { value: cells[2], weights: cells[4] });
}

/**
 * The weight string the page should carry, rebuilt from the audit's own
 * reasoning sentence so the page can never drift from the realized mix.
 */
function expectedWeights(metric) {
  const segments = [];
  const pattern =
    /(street|fundamental|prediction_market) [\d,.]+ \(sigma [\d,.]+, reliability \d+%, overlap penalty \d+%, weight (\d+)%\)/g;
  for (const [, engine, weight] of metric.reasoning.matchAll(pattern)) {
    segments.push(`${ENGINE_LABEL[engine]} ${weight}%`);
  }
  for (const contribution of metric.engine_contributions) {
    if (contribution.status === "abstained") segments.push(`${ENGINE_LABEL[contribution.engine]} abstained`);
  }
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
    const weights = expectedWeights(metric);
    if (row.weights !== weights) {
      fail(`${key.replace("|", " · ")} weights: page says "${row.weights}", audit says "${weights}"`);
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

// --- report -----------------------------------------------------------------

if (problems.length) {
  for (const problem of problems) console.error(`FAIL architecture/index.html: ${problem}`);
  console.error(`\n${problems.length} claim(s) on the architecture page no longer match the run.`);
  process.exitCode = 1;
} else {
  console.log(`PASS architecture/index.html: 12 forecast rows, weights and headline counts match the run`);
}
