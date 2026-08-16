let companies = [
  company("HD", "Home Depot", "FY2026 Q2", [
    metric("net_sales", "Net sales", "USDm", 46939.12, 46570, 47080, null, ["Category demand", "Calendar challenge", "Model reconciliation"]),
    metric("adj_eps", "Adjusted diluted EPS", "USD / share", 4.59, 4.73, 4.56, 4.77, ["Margin bridge", "Market signal", "Overlap discount"]),
    metric("comp_sales_pct", "Comparable sales", "%", 1.03, 0.4, 1.11, null, ["Category acceleration", "Overlap removal", "Historical wedge"]),
  ]),
  company("ADI", "Analog Devices", "FY2026 Q3", [
    metric("revenue", "Revenue", "USDm", 3964.71, 3910, 3980, null, ["Guidance position", "Bookings read-through", "Range calibration"]),
    metric("adj_eps", "Adjusted diluted EPS", "USD / share", 3.42, 3.33, 3.41, 3.47, ["Revenue bridge", "Market probability", "Margin validation"]),
    metric("adj_gross_margin_pct", "Adjusted gross margin", "%", 73.16, 72.8, 73.22, null, ["Utilisation recovery", "Mix challenge", "Peer validation"]),
  ]),
  company("LSE:HAS", "Hays plc", "FY2026", [
    metric("net_fees", "Net fees", "GBPm", 933.5, 902.3, 936.1, null, ["Published consensus", "Regional mix", "Analyst reliability"]),
    metric("pre_exc_basic_eps", "Pre-exceptional basic EPS", "GBp", 1.28, 1.09, 1.30, null, ["Profit conversion", "Tax bridge", "Reliability weighting"]),
    metric("pre_exc_operating_profit", "Pre-exceptional operating profit", "GBPm", 45.5, 43.5, 46.0, null, ["Fee sensitivity", "Cost challenge", "Analyst dispersion"]),
  ]),
  company("DE", "Deere & Company", "FY2026 Q3", [
    metric("worldwide_net_sales_revenues", "Worldwide net sales & revenue", "USDm", 11417.1, 10840, 11550, null, ["Industry cycle", "Price / currency", "Dealer inventory"]),
    metric("diluted_eps_gaap", "Diluted EPS (GAAP)", "USD / share", 4.71, 4.72, 4.63, 5.19, ["Operating leverage", "Market probability", "Tariff challenge"]),
    metric("ppa_operating_profit", "P&PA operating profit", "USDm", 592.88, 570, 601.4, null, ["Large-ag volume", "Mix and pricing", "Incremental margin"]),
  ]),
];

function company(id, name, period, metrics) { return { id, name, period, metrics }; }

function metric(key, name, unit, final, street, fundamental, market, factors) {
  const intermediate = market == null ? final + (fundamental - final) * 0.35 : (fundamental * 0.72 + market * 0.28);
  const steps = [
    traceStep("STREET", "Reconstruct Street", "Public estimates establish the benchmark.", street, street, "Public consensus · company guidance"),
    traceStep("RESEARCH", factors[0], `Independent evidence revises ${name.toLowerCase()}.`, street, fundamental, "Filings · drivers · peer read-through"),
    traceStep(market == null ? "CRITIC" : "MARKET", factors[1], "The strongest competing explanation is tested.", fundamental, intermediate, market == null ? "Historical counterfactual" : "Prediction-market macro prior"),
    traceStep("VALIDATE", factors[2], "Reliability and shared evidence determine the weight.", intermediate, final, "Point-in-time replay · estimator dispersion"),
    traceStep("SUBMIT", "Forecast accepted", "Units, range, citations and schema pass validation.", final, final, "Submission audit gate"),
  ];
  return { key, name, unit, final, street, fundamental, market, steps };
}

function traceStep(stage, title, claim, before, after, evidence, detail = {}) { return { stage, title, claim, before, after, evidence, ...detail }; }

const $ = selector => document.querySelector(selector);
const $$ = selector => [...document.querySelectorAll(selector)];
const svgNS = "http://www.w3.org/2000/svg";
let replay = null;
let selectedCompany = 0;
let selectedMetric = 0;
let detailPageIndex = 0;
let detailPages = [];
let currentLightning = [];
let chartRenderToken = 0;
let enabledEngines = new Set(["street", "fundamental", "market"]);
let selectedMethod = "ensemble";
const methodLabels = { ensemble: "ENSEMBLE", market: "PREDICTION MARKET", expert: "EXPERT", aggregate: "AGGREGATE FINAL" };

function formatValue(value, unit, compact = false) {
  if (value == null || Number.isNaN(value)) return "—";
  if (unit === "USDm") {
    if (Math.abs(value) >= 1000) return `$${(value / 1000).toFixed(compact ? 1 : 2)}bn`;
    return `$${value.toFixed(compact ? 0 : 1)}m`;
  }
  if (unit === "GBPm") return `£${value.toFixed(compact ? 0 : 1)}m`;
  if (unit === "USD / share") return `$${value.toFixed(2)}`;
  if (unit === "GBp") return `${value.toFixed(2)}p`;
  if (unit === "%") return `${value.toFixed(2)}%`;
  return value.toFixed(2);
}

function engineEntries(item) {
  if (item.sourceEngines) return item.sourceEngines;
  const hasMarket = item.market != null;
  return [
    { key: "street", name: "Street reconstruction", note: "PUBLIC CONSENSUS", value: item.street, weight: hasMarket ? 25 : 31 },
    { key: "fundamental", name: "Fundamental research", note: "FILINGS + DRIVERS", value: item.fundamental, weight: hasMarket ? 60 : 69 },
    { key: "market", name: "Prediction market", note: hasMarket ? "MACRO PRIOR" : "ABSTAINED", value: item.market, weight: hasMarket ? 15 : 0 },
  ];
}

function activeFinal(item) {
  const available = engineEntries(item).filter(engine => engine.value != null && engine.weight > 0);
  const active = available.filter(engine => enabledEngines.has(engine.key));
  if (!active.length) return item.final;
  const weightedMean = engines => engines.reduce((sum, engine) => sum + engine.value * engine.weight, 0) / engines.reduce((sum, engine) => sum + engine.weight, 0);
  return item.final + weightedMean(active) - weightedMean(available);
}

function edgePct(item, final = activeFinal(item)) { return item.street ? ((final - item.street) / Math.abs(item.street)) * 100 : 0; }
function signedPct(value) { return `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`; }
function escapeHtml(value) { return String(value).replace(/[&<>"]/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[char]); }
function current() { return { company: companies[selectedCompany], item: companies[selectedCompany].metrics[selectedMetric] }; }
function replayCompany() { return replay.companies.find(entry => entry.ticker === current().company.id); }
function normalizeMethodKey(key) { return ["anchor", "driver", "ml"].includes(key) ? "ensemble" : key; }

function metricHistory() {
  const { item } = current();
  const methodMetric = item.methodMetrics?.[selectedMethod];
  const normaliseRecord = record => {
    if (!record) return record;
    const forecast = record.forecast?.value;
    const actual = record.actual?.value;
    if (Number.isFinite(record.error) || !Number.isFinite(forecast) || !Number.isFinite(actual)) return record;
    const absolute = Math.abs(forecast - actual);
    const gateKind = methodMetric?.gate?.kind;
    return { ...record, error: gateKind === "mae" || item.unit === "%" ? absolute : (absolute / Math.max(Math.abs(actual), Number.EPSILON)) * 100 };
  };
  if (methodMetric?.series?.length) {
    if (methodMetric.chartType === "prob") {
      return methodMetric.series.map(point => ({
        period: point.period,
        record: normaliseRecord({
          forecast: { value: point.p },
          actual: Number.isFinite(point.outcome) ? { value: point.outcome * 100 } : null,
          actualMatch: "exact",
          error: Number.isFinite(point.outcome) ? Math.abs(point.p - point.outcome * 100) : null,
        }),
      }));
    }
    return methodMetric.series.map(point => ({
      period: point.period,
      record: normaliseRecord({
        forecast: { value: point.predicted },
        actual: { value: point.actual },
        actualMatch: "exact",
        error: point.err,
      }),
    }));
  }
  if (selectedMethod !== "aggregate") return [];
  return replayCompany().periods.map(period => ({
    period: period.period,
    record: normaliseRecord(period.metrics.find(candidate => candidate.metricKey === item.key)),
  }));
}

function metricIdentity(label) {
  return String(label).toLowerCase().replace(", total company", "").replace(/[^a-z0-9]+/g, " ").trim();
}

function hydrateForecasts(audit, explorer) {
  const explorerKey = { HD: "HD", ADI: "ADI", "LSE:HAS": "Hays", DE: "DE" };
  companies.forEach(company => {
    const forecast = audit.forecasts.find(entry => entry.ticker === company.id);
    const methodModel = explorer[explorerKey[company.id]];
    if (!forecast || !methodModel) return;
    company.name = methodModel.name;
    company.period = methodModel.period;
    const expert = methodModel.methods.driver;
    const aggregateCitations = [...new Set(forecast.metrics.flatMap(metricEntry => metricEntry.engine_contributions.flatMap(contribution => contribution.estimate?.citations || [])))];
    company.methods = {
      ensemble: {
        ...methodModel.methods.ml,
        label: methodModel.methods.ml.label.replace(/^ML\s*[—-]\s*/, "Ensemble — "),
      },
      market: methodModel.methods.market,
      expert: {
        ...expert,
        label: expert.label.replace(/^Driver\s*[—-]\s*/, "Expert — "),
      },
      aggregate: {
        label: "Aggregate Final — submitted meta-forecast",
        summary: "The audited final combines the available Street, Fundamental and Prediction Market estimates using reliability, uncertainty and overlap-aware weights.",
        metrics: forecast.metrics.map(metricEntry => ({
          label: metricEntry.label,
          unit: metricEntry.units,
          value: metricEntry.value,
          final: metricEntry.value,
          why: metricEntry.reasoning,
          series: [],
          seriesLabel: "Audited point-in-time aggregate replay",
        })),
        derivation: ["Reconstruct each eligible source independently.", "Apply declared reliability and uncertainty weights.", "Penalise shared evidence before normalising weights.", "Validate units, provenance and schema before submission."],
        data: aggregateCitations.map(source => ({ name: "Audited source", published: "Point-in-time", source })),
      },
    };
    company.metrics.forEach((item, index) => {
      const audited = forecast.metrics[index];
      if (!audited) return;
      item.name = audited.label;
      item.unit = audited.units;
      item.final = audited.value;
      item.methodMetrics = Object.fromEntries(Object.entries(company.methods).map(([key, method]) => [
        key,
        method.metrics?.find(metricEntry => metricIdentity(metricEntry.label) === metricIdentity(audited.label)) || null,
      ]));
      item.sourceEngines = audited.engine_contributions.map(contribution => {
        const key = contribution.engine === "prediction_market" ? "market" : contribution.engine;
        const weight = audited.meta_weights.find(entry => entry.engine === contribution.engine)?.normalized_weight || 0;
        const estimate = contribution.estimate;
        return {
          key,
          name: key === "street" ? "Street" : key === "fundamental" ? "Fundamental" : "Prediction market",
          note: contribution.status === "available" ? contribution.note : "ABSTAINED",
          status: contribution.status,
          value: estimate?.value ?? null,
          weight: weight * 100,
          sigma: estimate?.sigma ?? null,
          reliability: contribution.reliability * 100,
          nObservations: estimate?.n_observations ?? 0,
          reasoning: estimate?.reasoning || contribution.note,
          citations: estimate?.citations || [],
          sourceFamilies: contribution.source_families || [],
        };
      });
      item.sigma = audited.sigma;
      item.metaReasoning = audited.reasoning;
      item.warnings = audited.warnings || [];
      item.needsReview = Boolean(audited.needs_review);
      const [street, fundamental, market] = ["street", "fundamental", "market"].map(key => item.sourceEngines.find(engine => engine.key === key));
      item.street = street?.value ?? item.final;
      item.fundamental = fundamental?.value ?? item.final;
      item.market = market?.value ?? null;
      item.steps = [
        traceStep("STREET", "Street reconstruction", street?.reasoning || "Reconstruct the public benchmark.", item.street, item.street, "Public estimates", { engineKey: "street" }),
        traceStep("FUNDAMENTAL", "Fundamental research", fundamental?.reasoning || "Build the company from its operating drivers.", item.street, item.fundamental, "Filings and drivers", { engineKey: "fundamental" }),
        traceStep("MARKET", market?.value == null ? "Market abstained" : "Prediction market", market?.reasoning || "No direct, point-in-time market has a defensible mapping to this metric.", item.fundamental, market?.value ?? item.fundamental, "Market prior", { engineKey: "market" }),
        traceStep("WEIGHT", "Meta-forecaster", audited.reasoning || "Reliability-weight the available engines.", market?.value ?? item.fundamental, item.final, "Reliability blend", { engineKey: "meta" }),
        traceStep("SUBMIT", "Forecast accepted", "Units, source provenance, uncertainty and schema passed the submission audit.", item.final, item.final, "Submission audit", { engineKey: "submit" }),
      ];
    });
  });
}

function renderCompanyTabs() {
  $("#company-tabs").innerHTML = companies.map((entry, companyIndex) => `<button class="${companyIndex === selectedCompany ? "active" : ""}" data-company-tab="${companyIndex}" type="button">
    <b>${escapeHtml(entry.id.replace("LSE:", ""))}</b>${escapeHtml(entry.name)} <small>03</small>
  </button>`).join("");
}

function renderMethodTabs() {
  const { item } = current();
  $("#method-tabs").innerHTML = Object.keys(methodLabels).map(key => {
    const metric = item.methodMetrics?.[key];
    const hasSeries = Boolean(metric?.series?.length);
    return `<button type="button" data-method="${key}" class="${key === selectedMethod ? "active" : ""} ${hasSeries ? "" : "no-series"}" title="${hasSeries ? `${metric.series.length} validated periods` : "Reasoning and sources available; no method-specific backtest"}">${methodLabels[key]}</button>`;
  }).join("");
  const series = item.methodMetrics?.[selectedMethod]?.series;
  $(".range-switch span").textContent = series?.length
    ? `${series.length} VALIDATED PERIODS · EXACT SOURCE`
    : selectedMethod === "aggregate"
      ? `${replayCompany().periods.length} PERIODS · AGGREGATE REPLAY`
      : "NO VALIDATION SERIES · REASONING ONLY";
}

function renderUniverse() {
  const entry = current().company;
  $("#universe-list").innerHTML = entry.metrics.map((item, metricIndex) => {
      const final = metricIndex === selectedMetric ? activeFinal(item) : item.final;
      const edge = edgePct(item, final);
      return `<button class="metric-tab ${metricIndex === selectedMetric ? "active" : ""}" data-metric="${metricIndex}" type="button">
        <span>${escapeHtml(item.name)}<small>${escapeHtml(item.unit)}</small></span>
        <strong>${formatValue(final, item.unit, true)}</strong>
        <em class="${edge < 0 ? "negative" : ""}">${signedPct(edge)} VS STREET</em>
      </button>`;
    }).join("");
}

function makeSvg(tag, attributes = {}, text = "") {
  const node = document.createElementNS(svgNS, tag);
  Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
  if (text) node.textContent = text;
  return node;
}

function addSvg(parent, tag, attributes, text) {
  const node = makeSvg(tag, attributes, text);
  parent.appendChild(node);
  return node;
}

function pathFrom(points) { return points.length ? `M ${points.map(point => `${point.x.toFixed(2)} ${point.y.toFixed(2)}`).join(" L ")}` : ""; }

function electrifyPolyline(points, seed) {
  void seed;
  const jagged = [];
  const straight = [];
  points.slice(0, -1).forEach((start, segmentIndex) => {
    const end = points[segmentIndex + 1];
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const length = Math.hypot(dx, dy) || 1;
    for (let division = segmentIndex === 0 ? 0 : 1; division <= 4; division += 1) {
      const progress = division / 4;
      const exact = { x: start.x + dx * progress, y: start.y + dy * progress };
      const offset = 0;
      straight.push(exact);
      jagged.push({ x: exact.x - (dy / length) * offset, y: exact.y + (dx / length) * offset });
    }
  });
  return { jagged, straight };
}

function renderMainChart(previousFinal = null) {
  const renderToken = ++chartRenderToken;
  const { company, item } = current();
  const final = activeFinal(item);
  const methodMetric = item.methodMetrics?.[selectedMethod];
  const probabilityMode = methodMetric?.chartType === "prob";
  const aggregateMode = selectedMethod === "aggregate";
  const noSeries = !aggregateMode && !methodMetric?.series?.length;
  const history = metricHistory();
  const chartScroll = $("#chart-scroll");
  const chartEmpty = $("#chart-empty");
  chartScroll.hidden = false;
  chartEmpty.hidden = true;
  const pointSpacing = 76;
  const left = 54;
  const submissionWidth = 118;
  const viewWidth = Math.max(980, left + Math.max(history.length - 1, 1) * pointSpacing + submissionWidth + 28);
  const viewHeight = Math.max(420, chartScroll.clientHeight - 7);
  const chartWidth = Math.max(chartScroll.clientWidth, viewWidth);
  $("#history-chart").setAttribute("viewBox", `0 0 ${viewWidth} ${viewHeight}`);
  chartScroll.style.setProperty("--chart-width", `${chartWidth}px`);
  requestAnimationFrame(() => { chartScroll.scrollLeft = 0; });
  const grid = $("#chart-grid");
  const axes = $("#chart-axes");
  const actualLayer = $("#actual-series");
  const predictionLayer = $("#prediction-series");
  const streetLayer = $("#street-series");
  const lightningLayer = $("#lightning-series");
  const errorLayer = $("#error-series");
  const labels = $("#chart-labels");
  [grid, axes, actualLayer, predictionLayer, streetLayer, lightningLayer, errorLayer, labels].forEach(layer => layer.replaceChildren());
  $("#prediction-key-label").textContent = probabilityMode ? "MARKET P(YES)" : methodMetric?.predLabel || "MODEL / PREDICTION";
  $("#actual-key-label").textContent = probabilityMode ? "RESOLVED OUTCOME" : "ACTUAL";
  $("#street-key").hidden = !aggregateMode;
  if (noSeries) {
    const method = company.methods[selectedMethod];
    chartScroll.hidden = true;
    chartEmpty.hidden = false;
    $("#chart-empty-title").textContent = `${methodLabels[selectedMethod]} has no validation graph for ${item.name}`;
    $("#chart-empty-copy").textContent = methodMetric?.why || `${method.summary} The source still has reasoning and dated evidence, but no exact per-period series for this metric.`;
    currentLightning = Array.from({ length: 4 }, () => ({ jagged: [], straight: [], paths: [] }));
    return;
  }
  const validForecasts = history.filter(row => row.record?.forecast).map(row => row.record.forecast.value);
  const validActuals = history.filter(row => row.record?.actual).map(row => row.record.actual.value);
  const chartFinal = probabilityMode ? validForecasts.at(-1) : aggregateMode ? final : methodMetric?.value;
  const hasLiveForecast = Number.isFinite(chartFinal);
  const values = probabilityMode
    ? [...validForecasts, ...validActuals]
    : [
        ...validForecasts,
        ...validActuals,
        ...(hasLiveForecast ? [chartFinal] : []),
        ...(aggregateMode ? [item.street, final, ...engineEntries(item).flatMap(engine => engine.value == null ? [] : [engine.value]), ...item.steps.map(step => step.after)] : []),
      ];
  let min = probabilityMode ? 0 : Math.min(...values);
  let max = probabilityMode ? 100 : Math.max(...values);
  if (!probabilityMode) {
    const padding = Math.max((max - min) * 0.14, Math.abs(max) * 0.025, item.unit === "%" ? 0.3 : 0.08);
    min -= padding;
    max += padding;
  }

  const liveEnd = viewWidth - 28;
  const historyEnd = liveEnd - submissionWidth;
  const top = 38;
  const bottom = viewHeight - 174;
  const periodY = bottom + 25;
  const xHistory = index => left + index * ((historyEnd - left) / Math.max(history.length - 1, 1));
  const y = value => bottom - ((value - min) / (max - min || 1)) * (bottom - top);

  for (let index = 0; index < 5; index += 1) {
    const yy = top + index * ((bottom - top) / 4);
    addSvg(grid, "line", { class: `grid-line ${index === 4 ? "major" : ""}`, x1: left, y1: yy, x2: liveEnd, y2: yy });
    addSvg(axes, "text", { class: "axis-label", x: 4, y: yy + 3 }, formatValue(max - index * ((max - min) / 4), probabilityMode ? "%" : item.unit, true));
  }
  history.forEach((row, index) => {
    if (index % 4 === 0) {
      const xx = xHistory(index);
      addSvg(grid, "line", { class: "grid-line", x1: xx, y1: top, x2: xx, y2: bottom });
      addSvg(labels, "text", { class: "period-label", x: xx, y: periodY }, row.period.replace("FY", "FY ").replace("Q", " Q"));
    }
  });
  addSvg(axes, "line", { class: "terminal-marker", x1: liveEnd, y1: top - 5, x2: liveEnd, y2: bottom + 4 });
  addSvg(labels, "text", { class: "period-label", x: liveEnd, y: periodY }, company.period.toUpperCase());

  const forecastPoints = history.flatMap((row, index) => row.record?.forecast ? [{ x: xHistory(index), y: y(row.record.forecast.value), value: row.record.forecast.value }] : []);
  const actualPoints = history.flatMap((row, index) => row.record?.actual ? [{ x: xHistory(index), y: y(row.record.actual.value), value: row.record.actual.value, match: row.record.actualMatch }] : []);
  if (actualPoints.length) {
    addSvg(actualLayer, "path", { class: "actual-line", d: pathFrom(actualPoints) });
    actualPoints.forEach(point => addSvg(actualLayer, "circle", { class: "actual-dot", cx: point.x, cy: point.y, r: point.match === "proxy" ? 2.2 : 2.7 }));
  }
  const errors = history.map(row => row.record?.error).filter(value => Number.isFinite(value));
  if (errors.length) {
    const gate = item.methodMetrics?.[selectedMethod]?.gate;
    const errorUnit = probabilityMode || gate?.kind === "mae" || item.unit === "%" ? "PP" : "%";
    const errorTop = bottom + 50;
    const errorBottom = viewHeight - 58;
    const errorMax = Math.max(...errors, gate?.threshold || 0, 1) * 1.2;
    history.forEach((row, index) => {
      if (!Number.isFinite(row.record?.error)) return;
      const height = Math.max(2, (row.record.error / errorMax) * (errorBottom - errorTop));
      const validationState = gate ? (row.record.error <= gate.threshold ? "passed" : "failed") : "neutral";
      addSvg(errorLayer, "rect", { class: `error-period ${validationState}`, x: xHistory(index) - 9, y: errorBottom - height, width: 18, height });
      addSvg(labels, "text", { class: `error-value-label ${validationState}`, x: xHistory(index), y: errorBottom + 17 }, `${row.record.error.toFixed(row.record.error >= 10 ? 1 : 2)}${errorUnit === "PP" ? "pp" : "%"}`);
    });
    if (gate?.threshold) {
      const gateY = errorBottom - (gate.threshold / errorMax) * (errorBottom - errorTop);
      addSvg(errorLayer, "line", { class: "error-gate", x1: left, x2: historyEnd, y1: gateY, y2: gateY });
      addSvg(labels, "text", { class: "error-gate-label", x: historyEnd, y: gateY - 4 }, `GATE ${gate.threshold}${gate.kind === "mae" ? "PP" : "%"}`);
    }
    addSvg(labels, "text", { class: "error-strip-label", x: left, y: errorTop - 10 }, `ABSOLUTE ERROR BY PERIOD · ${errorUnit}`);
  }
  const latestHistoryX = xHistory(history.length - 1);
  if (aggregateMode) {
    addSvg(streetLayer, "line", { class: "street-line", x1: left, y1: y(item.street), x2: liveEnd, y2: y(item.street) });
    addSvg(labels, "text", { class: "terminal-label street-label", x: left + 7, y: y(item.street) - 8 }, `STREET ${formatValue(item.street, item.unit, true)}`);
  }
  if (actualPoints.length && hasLiveForecast) addSvg(labels, "text", { class: "axis-label", x: latestHistoryX + 5, y: actualPoints.at(-1).y + 15 }, "ACTUAL PENDING");

  const predictionPoints = [...forecastPoints, ...(hasLiveForecast ? [{ x: liveEnd, y: y(chartFinal), value: chartFinal }] : [])];
  let predictionPath = null;
  let livePredictionDot = null;
  if (predictionPoints.length) {
    predictionPath = addSvg(predictionLayer, "path", { class: "prediction-line", d: pathFrom(predictionPoints) });
    predictionPoints.forEach((point, index) => {
      const dot = addSvg(predictionLayer, "circle", {
      class: `prediction-dot ${hasLiveForecast && index === predictionPoints.length - 1 ? "live" : ""}`,
      cx: point.x,
      cy: point.y,
      r: hasLiveForecast && index === predictionPoints.length - 1 ? 4 : 3,
      });
      if (hasLiveForecast && index === predictionPoints.length - 1) livePredictionDot = dot;
    });
  }
  const boundaryIndices = Array.from({ length: 5 }, (_, index) => Math.round(index * (predictionPoints.length - 1) / 4));
  currentLightning = [];
  for (let index = 0; index < 4; index += 1) {
    const exactSection = predictionPoints.slice(boundaryIndices[index], boundaryIndices[index + 1] + 1);
    const { jagged, straight } = electrifyPolyline(exactSection, 5000 + selectedCompany * 200 + selectedMetric * 30 + index);
    const segment = { jagged, straight, paths: [] };
    ["lightning-bloom", "lightning-body", "lightning-core"].forEach(className => {
      const path = addSvg(lightningLayer, "path", { class: className, d: pathFrom(jagged), "data-segment": index });
      path.classList.add("resolved");
      segment.paths.push(path);
    });
    currentLightning.push(segment);
  }
  if (aggregateMode && Number.isFinite(previousFinal) && previousFinal !== final) {
    const fromPrediction = predictionPoints.map((point, index, points) => index === points.length - 1 ? { ...point, y: y(previousFinal) } : point);
    const lastSegment = currentLightning.at(-1);
    const fromLightning = lastSegment.straight.map((point, index, points) => index === points.length - 1 ? { ...point, y: y(previousFinal) } : point);
    predictionPath?.setAttribute("d", pathFrom(fromPrediction));
    livePredictionDot?.setAttribute("cy", y(previousFinal));
    lastSegment.paths.forEach(path => path.setAttribute("d", pathFrom(fromLightning)));
    const started = performance.now();
    const animateShift = now => {
      if (renderToken !== chartRenderToken) return;
      const progress = Math.min(1, (now - started) / 520);
      const eased = 1 - Math.pow(1 - progress, 3);
      predictionPath?.setAttribute("d", interpolatePath(fromPrediction, predictionPoints, eased));
      livePredictionDot?.setAttribute("cy", y(previousFinal) + (y(final) - y(previousFinal)) * eased);
      lastSegment.paths.forEach(path => path.setAttribute("d", interpolatePath(fromLightning, lastSegment.straight, eased)));
      if (progress < 1) requestAnimationFrame(animateShift);
    };
    requestAnimationFrame(animateShift);
  }
  boundaryIndices.forEach((pointIndex, index) => {
    const point = predictionPoints[pointIndex];
    addSvg(grid, "line", { class: "segment-divider", x1: point.x, y1: top, x2: point.x, y2: bottom });
    addSvg(lightningLayer, "circle", { class: "trace-node", cx: point.x, cy: point.y, r: index === 4 ? 4 : 3, "data-trace-node": index });
  });
  const sourceX = [liveEnd - 90, liveEnd - 60, liveEnd - 30];
  if (aggregateMode) engineEntries(item).forEach((engine, index) => {
    if (engine.value == null) {
      addSvg(predictionLayer, "circle", { class: "meta-source-dot unavailable", cx: sourceX[index], cy: bottom - 9, r: 4.5, "data-engine-node": engine.key });
      addSvg(labels, "text", { class: "source-dot-label unavailable", x: sourceX[index], y: bottom + 7 }, "M×");
      return;
    }
    if (!enabledEngines.has(engine.key)) return;
    addSvg(predictionLayer, "line", { class: "meta-connector", x1: sourceX[index], y1: y(engine.value), x2: liveEnd, y2: y(final) });
    addSvg(predictionLayer, "circle", { class: "meta-source-dot", cx: sourceX[index], cy: y(engine.value), r: 5, "data-engine-node": engine.key });
    addSvg(labels, "text", { class: "source-dot-label", x: sourceX[index], y: y(engine.value) + (index === 1 ? 16 : -10) }, engine.key[0].toUpperCase());
  });
  if (hasLiveForecast) {
    const finalText = probabilityMode
      ? `MARKET ${formatValue(chartFinal, "%")}`
      : aggregateMode
        ? `FINAL ${formatValue(final, item.unit)}`
        : `${methodLabels[selectedMethod]} ${formatValue(chartFinal, item.unit)}`;
    addSvg(labels, "text", { class: "terminal-label final-label", x: liveEnd, y: y(chartFinal) - 27 }, finalText);
  } else {
    addSvg(labels, "text", { class: "terminal-label final-label", x: liveEnd, y: top + 14 }, `${methodLabels[selectedMethod]} ABSTAINED`);
  }
}

function renderQuoteAndHeader() {
  const { company, item } = current();
  const final = activeFinal(item);
  const edge = edgePct(item, final);
  const method = company.methods?.[selectedMethod];
  $("#instrument-title").textContent = `${company.name} · ${item.name}`;
  $("#instrument-method").textContent = `${methodLabels[selectedMethod]} · ${method?.label || "SOURCE VIEW"}`;
  $("#quote-value").textContent = formatValue(final, item.unit);
  $("#quote-change").textContent = signedPct(edge);
  $("#quote-change").className = edge < 0 ? "negative" : "positive";
}

function renderEngineTable() {
  const { item } = current();
  $("#engine-table").innerHTML = engineEntries(item).map(engine => {
    const available = engine.value != null && engine.weight > 0;
    const active = available && enabledEngines.has(engine.key);
    const unavailableTitle = engine.key === "market" ? "No direct market contribution for this metric. Click to inspect the market evidence." : "No contribution is available for this metric.";
    return `<button class="engine-row ${active ? "active" : "off"} ${available ? "" : "unavailable"}" data-engine-toggle="${engine.key}" type="button" aria-pressed="${active}" data-engine-available="${available}" title="${available ? `Toggle ${engine.name}` : unavailableTitle}">
      <span class="engine-switch" aria-hidden="true">${active ? "●" : "○"}</span>
      <span class="engine-name">${engine.name.replace(" reconstruction", "").replace(" research", "")}</span>
      <span class="engine-value">${available ? formatValue(engine.value, item.unit, true) : "NO SIGNAL"}</span>
      <span class="engine-weight" style="--weight:${active ? engine.weight : 0}%"><i></i><span>${available ? `${active ? engine.weight.toFixed(0) : 0}%` : engine.key === "market" ? "VIEW EVIDENCE" : "UNAVAILABLE"}</span></span>
    </button>`;
  }).join("");
}

function shortSource(source) {
  try {
    const url = new URL(source);
    return `${url.hostname.replace(/^www\./, "")}${url.pathname === "/" ? "" : url.pathname}`;
  } catch {
    return String(source).replace(/^.*?(?=(?:home-depot|analog-devices|hays|deere|agent|data)\/)/, "");
  }
}

function sourceDetailPages() {
  const { company, item } = current();
  const method = company.methods[selectedMethod];
  const metric = item.methodMetrics?.[selectedMethod];
  const aggregateMode = selectedMethod === "aggregate";
  const data = method.data || [];
  const derivation = method.derivation || [];
  const seriesCount = aggregateMode ? replayCompany().periods.length : metric?.series?.length || 0;
  const sourceValue = aggregateMode ? activeFinal(item) : metric?.value;
  const valueText = Number.isFinite(sourceValue) ? formatValue(sourceValue, item.unit) : "ABSTAINED";
  const coverage = seriesCount ? `${seriesCount} validated period${seriesCount === 1 ? "" : "s"}` : "No per-period validation series";
  const gate = metric?.gate;
  const validationValue = method.brier
    ? method.brier.market.toFixed(4)
    : gate
      ? `${gate.score}${gate.kind === "mae" ? "pp" : "%"}`
      : seriesCount
        ? String(seriesCount)
        : "—";
  const validationMeta = method.brier ? "BRIER SCORE" : gate ? (gate.passed ? "GATE PASSED" : "GATE FAILED") : "VALIDATION";
  const evidence = data.length
    ? data.map(source => `${source.name}${source.published ? ` · ${source.published}` : ""}${source.source ? ` · ${shortSource(source.source)}` : ""}`)
    : ["No external dataset is recorded for this source view."];
  const metricCoverage = (method.metrics || []).map(entry => `${entry.label}: ${entry.value == null ? "abstained" : formatValue(entry.value, entry.unit, true)}`);
  const validationLines = method.brier
    ? [`Market Brier ${method.brier.market}`, `Base-rate Brier ${method.brier.baseRate}`, `${method.brier.n} resolved markets`]
    : gate
      ? [`Error ${gate.score}${gate.kind === "mae" ? "pp" : "%"}`, `Gate ${gate.threshold}${gate.kind === "mae" ? "pp" : "%"}`, `${gate.n} validated periods`, gate.passed ? "Number offered" : "Source abstains"]
      : [coverage, "No accuracy claim is made without a declared gate."];
  return [
    {
      stage: "OVERVIEW",
      title: method.label,
      claim: method.summary || "No source summary supplied.",
      value: valueText,
      meta: `${methodLabels[selectedMethod]} · ${item.name}`,
      calculation: coverage,
      label: "METRICS COVERED",
      sources: metricCoverage.length ? metricCoverage : ["This source produced no company metrics."],
    },
    {
      stage: "EVIDENCE",
      title: "Evidence used",
      claim: data.length ? `This source uses ${data.length} dated input${data.length === 1 ? "" : "s"}.` : "This source records no external input for the selected company.",
      value: String(data.length),
      meta: "DATED SOURCES",
      calculation: evidence[0],
      label: "DATA + PUBLICATION DATES",
      sources: evidence,
    },
    {
      stage: "DERIVATION",
      title: "How the number was reached",
      claim: derivation[0] || "No derivation steps were supplied for this source.",
      value: String(derivation.length),
      meta: "MODEL STEPS",
      calculation: derivation[1] || method.summary || "No additional model logic supplied.",
      label: "REASONING STEPS",
      sources: derivation.length ? derivation : ["No derivation steps recorded."],
    },
    {
      stage: "VALIDATION",
      title: gate ? (gate.passed ? "Validation gate passed" : "Validation gate failed") : method.brier ? "Probability calibration" : "Validation coverage",
      claim: metric?.seriesLabel || coverage,
      value: validationValue,
      meta: validationMeta,
      calculation: gate ? `The declared threshold is ${gate.threshold}${gate.kind === "mae" ? "pp" : "%"} across ${gate.n} periods.` : method.brier ? "Lower Brier scores indicate better-calibrated probabilities." : "Reasoning remains visible even when no exact graph exists.",
      label: "VALIDATION RESULT",
      sources: validationLines,
    },
    {
      stage: "OUTPUT",
      title: item.name,
      claim: metric?.why || `This source has no defensible direct mapping to ${item.name}.`,
      value: valueText,
      meta: Number.isFinite(sourceValue) ? "SOURCE OUTPUT" : "SOURCE ABSTAINED",
      calculation: aggregateMode ? `Submitted final after active contribution weights: ${formatValue(activeFinal(item), item.unit)}.` : Number.isFinite(sourceValue) ? `Independent ${methodLabels[selectedMethod].toLowerCase()} estimate before aggregation.` : "No value enters the aggregate from this source for the selected metric.",
      label: "RELATION TO FINAL FORECAST",
      sources: [`Aggregate final: ${formatValue(activeFinal(item), item.unit)}`, `Street reference: ${formatValue(item.street, item.unit)}`, coverage],
    },
  ];
}

function renderDetailPage() {
  const page = detailPages[detailPageIndex];
  if (!page) return;
  $("#cinematic-stage").textContent = page.stage;
  $("#cinematic-count").textContent = `${String(detailPageIndex + 1).padStart(2, "0")} / ${String(detailPages.length).padStart(2, "0")}`;
  $("#cinematic-title").textContent = page.title;
  $("#cinematic-claim").textContent = page.claim;
  $("#cinematic-value").textContent = page.value;
  $("#cinematic-weight").textContent = page.meta;
  $("#cinematic-calculation").textContent = page.calculation;
  $("#cinematic-source-label").textContent = page.label;
  $("#cinematic-sources").innerHTML = page.sources.slice(0, 6).map(source => `<li>${escapeHtml(source)}</li>`).join("");
  $("#details-progress").textContent = page.stage;
  $("#details-back").disabled = detailPageIndex === 0;
  $("#details-next").textContent = detailPageIndex === detailPages.length - 1 ? "FINISH ✓" : "NEXT →";
}

function openDetails() {
  detailPages = sourceDetailPages();
  detailPageIndex = 0;
  const modal = $("#cinematic-reason");
  modal.hidden = false;
  delete modal.dataset.side;
  renderDetailPage();
  requestAnimationFrame(() => {
    modal.classList.add("visible");
    $("#details-next").focus({ preventScroll: true });
  });
}

function closeDetails() {
  const modal = $("#cinematic-reason");
  modal.classList.remove("visible");
  modal.hidden = true;
  $("#details-control")?.focus({ preventScroll: true });
}

function advanceDetails() {
  if (detailPageIndex >= detailPages.length - 1) return closeDetails();
  detailPageIndex += 1;
  renderDetailPage();
}

function previousDetails() {
  if (detailPageIndex === 0) return;
  detailPageIndex -= 1;
  renderDetailPage();
}

function interpolatePath(from, to, progress) {
  return pathFrom(from.map((point, index) => ({ x: point.x + (to[index].x - point.x) * progress, y: point.y + (to[index].y - point.y) * progress })));
}

function renderSelection() {
  renderCompanyTabs();
  renderUniverse();
  renderQuoteAndHeader();
  renderMethodTabs();
  renderMainChart();
  renderEngineTable();
  closeDetails();
}

function resetEngineSelection() {
  enabledEngines = new Set(["street", "fundamental", "market"]);
}

function chooseDefaultMethod() {
  selectedMethod = "ensemble";
}

async function init() {
  const [replayData, audit, explorer] = await Promise.all([
    fetch("data/five-year-backtest.json").then(response => response.json()),
    fetch("data/forecast-audit.json").then(response => response.json()),
    fetch("data/method-explorer.json").then(response => response.json()),
  ]);
  replay = replayData;
  hydrateForecasts(audit, explorer);
  selectedMethod = normalizeMethodKey(new URLSearchParams(window.location.search).get("method") || "ensemble");
  if (!methodLabels[selectedMethod]) selectedMethod = "ensemble";
  $("#global-coverage").textContent = `${replay.summary.actualAvailable} / ${replay.summary.requestedMetricSlots} ACTUALS`;
  renderSelection();
}

$("#universe-list").addEventListener("click", event => {
  const row = event.target.closest("[data-metric]");
  if (!row) return;
  selectedMetric = Number(row.dataset.metric);
  resetEngineSelection();
  chooseDefaultMethod();
  renderSelection();
});
$("#company-tabs").addEventListener("click", event => {
  const tab = event.target.closest("[data-company-tab]");
  if (!tab) return;
  selectedCompany = Number(tab.dataset.companyTab);
  selectedMetric = 0;
  resetEngineSelection();
  chooseDefaultMethod();
  renderSelection();
});
$("#method-tabs").addEventListener("click", event => {
  const control = event.target.closest("[data-method]");
  if (!control || control.disabled) return;
  selectedMethod = control.dataset.method;
  closeDetails();
  renderMethodTabs();
  renderQuoteAndHeader();
  renderMainChart();
});
$("#details-control").addEventListener("click", openDetails);
$("#chart-empty-details").addEventListener("click", openDetails);
$("#engine-table").addEventListener("click", event => {
  const control = event.target.closest("[data-engine-toggle]");
  if (!control) return;
  const key = control.dataset.engineToggle;
  const { item } = current();
  if (control.dataset.engineAvailable !== "true") {
    if (key === "market") {
      selectedMethod = "market";
      renderMethodTabs();
      renderQuoteAndHeader();
      renderMainChart();
      openDetails();
    }
    return;
  }
  const previousFinal = activeFinal(item);
  const activeAvailable = engineEntries(item).filter(engine => engine.value != null && enabledEngines.has(engine.key));
  if (enabledEngines.has(key) && activeAvailable.length === 1) return;
  if (enabledEngines.has(key)) enabledEngines.delete(key); else enabledEngines.add(key);
  selectedMethod = "aggregate";
  closeDetails();
  renderUniverse();
  renderQuoteAndHeader();
  renderMethodTabs();
  renderMainChart(previousFinal);
  renderEngineTable();
  const nextFinal = activeFinal(item);
  if (previousFinal !== nextFinal) $("#quote-value").animate([{ transform: "translateY(2px)", opacity: .55 }, { transform: "translateY(0)", opacity: 1 }], { duration: 260, easing: "ease-out" });
});
$("#trace-close").addEventListener("click", closeDetails);
$("#details-back").addEventListener("click", previousDetails);
$("#details-next").addEventListener("click", advanceDetails);
document.addEventListener("keydown", event => {
  if (event.key === "Escape" && !$("#cinematic-reason").hidden) closeDetails();
});

if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) $("#storm-video")?.pause();
init().catch(error => {
  $("#details-control").textContent = "DATA ERROR";
  $("#details-control").disabled = true;
  console.error(error);
});
