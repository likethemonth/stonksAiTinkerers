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

assert.doesNotMatch(html, /manim/i, "Manim must not return to the terminal");
assert.doesNotMatch(js, /playCinematicTrace|manim/i, "fixed cinematic playback must not return");
assert.match(html, /id="company-tabs"/, "four-company tab bar is missing");
assert.match(html, /id="universe-list"/, "active-company metric selector is missing");
assert.match(html, /id="history-chart"/, "five-year history chart is missing");
assert.match(html, /id="engine-table"/, "engine monitor is missing");
assert.match(html, /id="method-tabs"/, "Uri method explorer controls are missing");
assert.doesNotMatch(html, /id="reasoning-tape"|id="coverage-monitor"/, "persistent reasoning and coverage panels must not crowd the graph");
assert.match(html, /id="cinematic-reason"/, "cinematic reasoning card is missing");
assert.match(html, /id="cinematic-calculation"/, "trace calculation field is missing");
assert.match(html, /id="cinematic-sources"/, "trace evidence list is missing");
assert.match(html, /CLICK CARD OR NEXT TO ADVANCE/, "trace card does not expose its click progression");
assert.doesNotMatch(html, /control-rail|universe-columns/, "the old left control rail must not crowd the graph");
assert.doesNotMatch(html, /id="validation-summary"/, "duplicate validation summary must not crowd the graph");
assert.doesNotMatch(html, /id="history-ledger"|id="error-chart"/, "ledger and error panels must not crowd the main screen");
assert.match(html, /id="trace-control"/, "single trace control is missing");
assert.doesNotMatch(html, /id="trace-status"/, "persistent trace status pill must not cover the graph");
assert.match(html, /assets\/storm-clouds-2066\.mp4/, "licensed storm field is not wired");
assert.ok(cloudVideo.size > 1_000_000, "storm footage asset is unexpectedly small");

assert.equal(replay.companies.length, 4, "replay must cover four companies");
assert.equal(replay.summary.requestedCompanyPeriods, 80, "replay must expose 80 company-periods");
assert.equal(replay.summary.requestedMetricSlots, 240, "replay must expose 240 metric slots");
assert.equal(replay.summary.actualAvailable, 195, "replay actual coverage changed unexpectedly");
assert.ok(replay.companies.every(company => company.periods.length === 20), "every company must expose 20 requested periods");
assert.deepEqual(Object.keys(methods).sort(), ["ADI", "DE", "HD", "Hays"], "method explorer must cover Uri's four-stock model");
assert.equal(audit.forecasts.length, 4, "submission audit must cover four companies");

assert.equal((js.match(/^\s+metric\("/gm) || []).length, 12, "terminal must represent twelve current metric forecasts");
assert.match(js, /fetch\("data\/five-year-backtest\.json"\)/, "audited replay data is not loaded");
assert.match(js, /function renderMainChart/, "prediction and actual renderer is missing");
assert.match(js, /function runTrace/, "live lightning trace is missing");
assert.match(js, /function electrifyPolyline/, "prediction path is not divided into electric segments");
assert.match(js, /const offset = 0/, "forecast path must remain geometrically straight");
assert.match(js, /const boundaryIndices = Array\.from\(\{ length: 5 \}/, "prediction path is not divided into four reasoning segments");
assert.match(js, /function straightenLightning/, "lightning does not settle into the exact path");
assert.match(js, /const speeds = \[170, 235, 205, 310\]/, "lightning impulse timing is missing");
assert.match(js, /setAttribute\("d", interpolatePath/, "lightning geometry does not physically resolve");
assert.match(js, /function showCinematicReason/, "focused reasoning trace is missing");
assert.match(js, /function traceExplanation/, "source-level trace explanation is missing");
assert.match(js, /estimate\?\.citations \|\| \[\]/, "audited citations are not preserved for the trace");
assert.match(js, /contribution\.source_families \|\| \[\]/, "source families are not preserved for the trace");
assert.match(js, /Precision weighting scales 1\/σ²/, "meta-forecast calculation is not explained");
assert.match(js, /absolute \/ Math\.max\(Math\.abs\(actual\)/, "missing period errors are not derived from prediction and actual");
assert.match(js, /function activeFinal/, "interactive meta-forecast recalculation is missing");
assert.match(js, /renderMainChart\(previousFinal\)/, "lens toggles do not animate the live forecast path to its new value");
assert.match(js, /function hydrateForecasts/, "Uri forecast explorer is not joined to the themed terminal");
assert.match(js, /data-engine-toggle/, "engine contribution controls are missing");
assert.match(js, /meta-source-dot/, "three engine forecast nodes are missing");
assert.match(js, /traceStepIndex/, "click-to-advance reasoning state is missing");
assert.match(js, /classList\.add\("trace-active"\)/, "trace does not compact the forecast controls while playing");
assert.match(js, /hideCinematicReason\(\);\s*await straightenLightning/, "Finish must dismiss the reasoning card before resolving the trace");
assert.match(js, /pointLeft - chartScroll\.clientWidth \/ 2/, "active reasoning node is not centred in the history scroller");
assert.doesNotMatch(js, /classList\.add\("trace-mode"\)|classList\.add\("trace-zoom"\)/, "trace must not zoom or black out the terminal");

assert.match(css, /html \{[^}]*height: 100%;[^}]*overflow: hidden/s, "single-viewport page is not enforced");
assert.match(css, /height: calc\(100vh - 48px\)/, "workspace does not fit below the header");
assert.match(css, /\.workbench \{ display: block/, "full-width graph workspace is missing");
assert.match(css, /\.forecast-deck/, "compact full-width forecast controls are missing");
assert.match(css, /\.terminal\.trace-active \.forecast-deck/, "trace-time compact layout is missing");
assert.match(css, /\.terminal\.trace-active \.cinematic-reason/, "reasoning card does not use the recovered trace space");
assert.match(css, /\.lightning-core/, "electric prediction styling is missing");
assert.match(css, /#lightning-series \.drawing/, "lightning animation must target the SVG layer id");
assert.match(css, /\.cinematic-reason\.visible/, "reasoning card reveal is missing");
assert.match(css, /\.meta-source-dot\.active-source/, "active three-lens source is not highlighted");
assert.match(css, /font: 400 15px\/1\.55 var\(--sans\)/, "reasoning copy is below the readable type contract");
assert.match(css, /\.chart-scroll/, "full-history graph scroller is missing");
assert.match(css, /\.method-inspector/, "complete Uri method data inspector is missing");
assert.match(css, /prefers-reduced-motion/, "reduced-motion behavior is missing");

assert.match(agents, /TraceEvent/, "deferred backend trace contract is undocumented");
assert.match(agents, /illustrative UI data/, "prototype trace limitation is undocumented");

console.log("dashboard contract OK — light full-width history, labeled errors, click-stepped lightning trace");
