import assert from "node:assert/strict";
import { readFile, stat } from "node:fs/promises";

const [html, css, js, agents, replayText, methodText, auditText] = await Promise.all([
  readFile(new URL("../dashboard/index.html", import.meta.url), "utf8"),
  readFile(new URL("../dashboard/styles.css", import.meta.url), "utf8"),
  readFile(new URL("../dashboard/app.js", import.meta.url), "utf8"),
  readFile(new URL("../AGENTS.md", import.meta.url), "utf8"),
  readFile(new URL("../dashboard/data/five-year-backtest.json", import.meta.url), "utf8"),
  readFile(new URL("../dashboard/data/method-explorer.json", import.meta.url), "utf8"),
  readFile(new URL("../dashboard/data/forecast-audit.json", import.meta.url), "utf8"),
]);
const cloudVideo = await stat(new URL("../dashboard/assets/storm-clouds-2066.mp4", import.meta.url));
const replay = JSON.parse(replayText);
const methods = JSON.parse(methodText);
const audit = JSON.parse(auditText);

assert.doesNotMatch(html, /manim/i, "Manim must not return");
assert.match(html, /id="company-tabs"/, "four-company tabs are missing");
assert.match(html, /id="universe-list"/, "company metrics are missing");
assert.match(html, /id="history-chart"/, "history chart is missing");
assert.match(html, /id="engine-table"/, "three-lens controls are missing");
assert.match(html, /id="method-tabs"/, "method controls are missing");
assert.match(html, /id="details-control"[^>]*>DETAILS</, "Details must be the single reasoning entry point");
assert.doesNotMatch(html, /id="trace-control"|RUN TRACE/, "the separate Run Trace control must be removed");
assert.match(html, /id="cinematic-reason"[^>]*role="dialog"[^>]*hidden/, "Details dialog must start hidden");
assert.match(html, /id="trace-close"[^>]*aria-label="Close reasoning details"/, "Details dialog needs a close control");
assert.match(html, /id="details-back"/, "Details Back control is missing");
assert.match(html, /id="details-next"/, "Details Next control is missing");
assert.match(html, /id="chart-empty"[^>]*hidden/, "source-specific no-chart state is missing");
assert.doesNotMatch(html, /id="method-inspector"|id="reasoning-tape"|id="coverage-monitor"/, "duplicate reasoning panels must not crowd the graph");
assert.match(html, /assets\/storm-clouds-2066\.mp4/, "storm footage is not wired");
assert.ok(cloudVideo.size > 1_000_000, "storm footage is unexpectedly small");

assert.equal(replay.companies.length, 4, "replay must cover four companies");
assert.equal(replay.summary.requestedCompanyPeriods, 80, "replay must expose 80 company-periods");
assert.equal(replay.summary.requestedMetricSlots, 240, "replay must expose 240 metric slots");
assert.equal(replay.summary.actualAvailable, 195, "replay actual coverage changed unexpectedly");
assert.ok(replay.companies.every(company => company.periods.length === 20), "every company must expose 20 requested periods");
assert.deepEqual(Object.keys(methods).sort(), ["ADI", "DE", "HD", "Hays"], "method data must cover all four companies");
assert.equal(audit.forecasts.length, 4, "audit must cover all four companies");

assert.equal((js.match(/^\s+metric\("/gm) || []).length, 12, "dashboard must represent twelve forecasts");
assert.match(js, /const methodLabels = \{ ensemble: "ENSEMBLE", market: "PREDICTION MARKET", expert: "EXPERT", aggregate: "AGGREGATE FINAL" \}/, "required method navigation is missing");
assert.match(js, /selectedMethod = "ensemble"/, "Ensemble must remain the default");
assert.match(js, /if \(selectedMethod !== "aggregate"\) return \[\];/, "source views must not silently borrow the aggregate replay");
assert.match(js, /selectedMethod === "aggregate"[\s\S]*AGGREGATE REPLAY/, "Aggregate Final must expose the audited replay");
assert.match(js, /const noSeries = !aggregateMode && !methodMetric\?\.series\?\.length/, "exact missing-series state is not detected");
assert.match(js, /chartScroll\.hidden = true;[\s\S]*chartEmpty\.hidden = false;/, "missing-series state must replace the graph explicitly");
assert.match(js, /methodMetric\.chartType === "prob"/, "prediction-market probability charts are not detected");
assert.match(js, /forecast: \{ value: point\.p \}/, "market probabilities are not normalized");
assert.match(js, /class: "prediction-line"/, "dashed prediction path is not rendered");
assert.match(js, /class: "actual-line"/, "actual path is not rendered");
assert.match(js, /if \(aggregateMode\) engineEntries\(item\)/, "source contribution dots must remain aggregate-only");
assert.match(js, /path\.classList\.add\("resolved"\)/, "lightning forecast path must remain visible");
assert.match(js, /function sourceDetailPages/, "source-specific Details pages are missing");
for (const stage of ["OVERVIEW", "EVIDENCE", "DERIVATION", "VALIDATION", "OUTPUT"]) {
  assert.match(js, new RegExp(`stage: "${stage}"`), `${stage} Details page is missing`);
}
assert.match(js, /function openDetails\(\)[\s\S]*sourceDetailPages\(\)/, "Details must open the selected source narrative");
assert.match(js, /function advanceDetails\(\)/, "Details pagination is missing");
assert.match(js, /detailPageIndex >= detailPages\.length - 1\) return closeDetails\(\)/, "Finish must close Details");
assert.match(js, /event\.key === "Escape"[\s\S]*closeDetails\(\)/, "Escape must close Details");
assert.match(js, /control\.dataset\.engineAvailable !== "true"[\s\S]*selectedMethod = "market"[\s\S]*openDetails\(\)/, "an unavailable market lens must open its evidence");
assert.match(js, /selectedMethod = "aggregate";[\s\S]*renderMainChart\(previousFinal\)/, "lens toggles must switch to and move Aggregate Final");
assert.match(js, /let chartRenderToken = 0/, "chart endpoint animation needs independent cancellation state");

assert.match(css, /html \{[^}]*height: 100%;[^}]*overflow: hidden/s, "single-page viewport is not enforced");
assert.match(css, /\.forecast-deck \{[^}]*padding: 6px 10px/s, "forecast strip is not vertically compact");
assert.match(css, /\.engine-row \{[^}]*min-height: 44px/s, "source controls are too tall");
assert.match(css, /\.cinematic-reason \{[^}]*inset: 0;[^}]*grid-template-rows/s, "Details must cover the complete chart canvas");
assert.match(css, /\.cinematic-reason\.visible/, "Details reveal state is missing");
assert.match(css, /\.street-key\[hidden\] \{ display: none; \}/, "Street legend needs a reliable hidden state for incompatible charts");
assert.match(js, /const showStreetReference = !probabilityMode && !noSeries/, "Street benchmark must remain visible on compatible financial charts");
assert.match(js, /\$\("#street-key"\)\.hidden = !showStreetReference/, "Street legend must follow benchmark compatibility");
assert.match(js, /if \(showStreetReference\) \{[\s\S]*class: "street-line"/, "Street benchmark must render outside Aggregate Final");
assert.match(js, /class: "street-line", x1: left/, "Street benchmark must span the full aggregate chart");
assert.match(css, /\.engine-row\.off \{[^}]*opacity: 1/s, "disabled source controls must remain visible and reversible");
assert.match(css, /\.prediction-line \{[^}]*stroke-dasharray: 6 5/s, "prediction series must be dashed");
assert.match(css, /\.actual-line \{[^}]*stroke: #1c1f1d/s, "actual series must remain near-black");
assert.match(css, /\.method-tabs button\.active[^}]*background: #e7f5fc/s, "selected method highlight must persist");
assert.match(css, /#lightning-series \.resolved\.lightning-core \{ opacity: 1; \}/, "lightning path must remain highlighted");
assert.match(css, /\.error-period\.passed[^}]*var\(--pass\)/s, "passing errors need a green indicator");
assert.match(css, /\.error-period\.failed[^}]*var\(--fail\)/s, "failing errors need a red indicator");
assert.match(css, /\.storm-field \{[^}]*opacity: \.18/s, "storm footage strength changed unexpectedly");
assert.match(css, /prefers-reduced-motion/, "reduced-motion behavior is missing");

assert.match(agents, /TraceEvent/, "deferred backend trace contract is undocumented");
assert.match(agents, /illustrative UI data/, "prototype trace limitation is undocumented");

console.log("dashboard contract OK — compact forecast strip, exact source charts, full-canvas paged Details");
