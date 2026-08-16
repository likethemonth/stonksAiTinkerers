"""Render the run into a self-contained HTML report.

    python -m forecast.report

Reads submission/forecast-audit.json and produces submission/report.html: the
twelve numbers, what each rests on, the sources behind them, and the arguments
for and against each figure.

Arguments are shown in side-by-side FOR / AGAINST columns rather than behind
tabs, because the thing a reader needs to see first is the balance — how many
arguments push each way and how strong they are. Filter chips let you narrow to
one group, or to the ones the adversarial pass refuted, without losing that
first read.

Self-contained by design — no network, no build step, no server. It opens from
the filesystem, which is what makes it usable in a judging conversation.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDIT = REPO_ROOT / "submission" / "forecast-audit.json"
OUT = REPO_ROOT / "submission" / "report.html"

_CSS = """
:root{color-scheme:light;--ink:#101828;--muted:#667085;--line:#e4e7ec;--blue:#155eef;
--paper:#fff;--wash:#f8fafc;--for:#067647;--against:#b42318;--neutral:#667085;
--tint:#eef4ff;--warn:#b54708}
*{box-sizing:border-box}
body{margin:0;background:var(--wash);color:var(--ink);
font:15px/1.6 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
main{width:min(1100px,calc(100% - 32px));margin:32px auto 64px}
h1{font-size:clamp(30px,5vw,44px);letter-spacing:-.03em;margin:0 0 4px;text-wrap:balance}
.sub{color:var(--muted);margin:0 0 28px}
.co{background:var(--paper);border:1px solid var(--line);border-radius:14px;
padding:22px 24px;margin-bottom:20px;box-shadow:0 1px 2px rgb(16 24 40/.05)}
.co>h2{margin:0;font-size:19px;letter-spacing:-.01em}
.co>.per{color:var(--muted);font-size:13px;margin:2px 0 18px}
.m{border-top:1px solid var(--line);padding:20px 0 6px}
.m:first-of-type{border-top:0;padding-top:0}
.mh{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}
.lbl{font-weight:600;font-size:16px}
.val{margin-left:auto;font-size:27px;font-weight:700;letter-spacing:-.02em;
font-variant-numeric:tabular-nums}
.un{color:var(--muted);font-size:13px;font-weight:500}
.why{color:var(--muted);font-size:13.5px;margin:8px 0 0;max-width:78ch}
.tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
.tag{font-size:11.5px;padding:2px 8px;border-radius:999px;background:var(--tint);
color:var(--blue);font-weight:600}
.tag.warn{background:#fef6ee;color:var(--warn)}
details{margin-top:12px}
summary{cursor:pointer;font-size:13px;color:var(--blue);font-weight:600;
padding:4px 0}
summary:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
.srcs{margin:10px 0 0;padding-left:18px}
.srcs li{font-size:12.5px;color:var(--muted);font-family:ui-monospace,SFMono-Regular,
Menlo,monospace;word-break:break-all}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin:12px 0 4px}
.chip{font:600 12px/1 inherit;padding:6px 11px;border-radius:999px;cursor:pointer;
border:1px solid var(--line);background:var(--paper);color:var(--muted)}
.chip[aria-pressed="true"]{background:var(--ink);border-color:var(--ink);color:#fff}
.chip:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
.cols{display:grid;gap:12px;margin-top:12px}
@media(min-width:820px){.cols{grid-template-columns:1fr 1fr}}
.col>h4{margin:0 0 8px;font:800 11px/1 inherit;letter-spacing:.09em;
text-transform:uppercase}
.col.for>h4{color:var(--for)}
.col.against>h4{color:var(--against)}
.col.neutral>h4{color:var(--neutral)}
.col.neutral{grid-column:1/-1}
.arg{border:1px solid var(--line);border-left-width:3px;border-radius:8px;
padding:11px 13px;background:var(--wash);margin-bottom:8px}
.arg.for{border-left-color:var(--for)}
.arg.against{border-left-color:var(--against)}
.arg.neutral{border-left-color:var(--neutral)}
.arg p{margin:0;font-size:13.5px}
.arg .meta{margin-top:7px;font-size:11.5px;color:var(--muted);
font-variant-numeric:tabular-nums}
.arg .rule{margin-top:7px;font-size:12px;color:var(--muted);
border-top:1px dashed var(--line);padding-top:6px}
.arg.dead{opacity:.5}
.arg.dead p{text-decoration:line-through}
.arg.dead .rule{text-decoration:none}
.empty{color:var(--muted);font-size:12.5px;font-style:italic}
.note{background:#fffaf5;border:1px solid var(--line);border-radius:9px;
padding:10px 13px;margin-top:10px;font-size:12.5px;color:#7a4a12}
.hidden{display:none}
"""

_JS = """
document.querySelectorAll('[data-filters]').forEach(function (bar) {
  var scope = bar.closest('[data-args]');
  bar.addEventListener('click', function (event) {
    var chip = event.target.closest('.chip');
    if (!chip) return;
    var want = chip.dataset.filter;
    bar.querySelectorAll('.chip').forEach(function (c) {
      c.setAttribute('aria-pressed', String(c === chip));
    });
    scope.querySelectorAll('.arg').forEach(function (arg) {
      var show =
        want === 'all' ? true :
        want === 'refuted' ? arg.classList.contains('dead') :
        arg.dataset.direction === want;
      arg.classList.toggle('hidden', !show);
    });
    scope.querySelectorAll('.col').forEach(function (col) {
      var any = col.querySelector('.arg:not(.hidden)');
      col.classList.toggle('hidden', !any);
    });
  });
});
"""


def _esc(v: object) -> str:
    return html.escape(str(v))


def _period(value: object) -> str:
    """Period serialises as {'year': 2026, 'quarter': 2}; render it as FY2026Q2."""
    if isinstance(value, dict):
        year, quarter = value.get("year"), value.get("quarter")
        return f"FY{year}" + (f"Q{quarter}" if quarter else "")
    return str(value)


def _fmt(value: float, units: str) -> str:
    return f"{value:,.0f}" if units in {"USDm", "GBPm"} else f"{value:,.2f}"


def _argument(thesis: dict, rebuttal: str | None) -> str:
    direction = thesis.get("direction", "NEUTRAL")
    # The auditor writes prose, so treat an explicit refutation marker as the
    # signal rather than trying to parse the sentence.
    dead = bool(rebuttal) and any(
        w in rebuttal.lower() for w in ("incorrect", "does not support", "not survive")
    )
    cites = ", ".join(str(i) for i in thesis.get("observation_ids", []))
    parts = [
        f'<div class="arg {direction.lower()}{" dead" if dead else ""}"'
        f' data-direction="{_esc(direction.lower())}">',
        f'<p>{_esc(thesis.get("claim", ""))}</p>',
        '<div class="meta">',
    ]
    if direction != "NEUTRAL":
        parts.append(f'effect {thesis.get("effect", 0):+,.2f} · ')
    parts.append(
        f'confidence {thesis.get("confidence", 0):.0%} · cites [{_esc(cites)}]</div>'
    )
    if rebuttal:
        parts.append(f'<div class="rule">Audit: {_esc(rebuttal)}</div>')
    parts.append("</div>")
    return "".join(parts)


def _arguments(thesis_data: dict, key: str) -> str:
    theses = thesis_data.get("theses") or []
    if not theses:
        return ""
    rebuttals = {int(k): v for k, v in (thesis_data.get("rebuttals") or {}).items()}

    groups: dict[str, list[str]] = {"FOR": [], "AGAINST": [], "NEUTRAL": []}
    counts: dict[str, int] = {"FOR": 0, "AGAINST": 0, "NEUTRAL": 0}
    refuted = 0
    for i, thesis in enumerate(theses):
        direction = thesis.get("direction", "NEUTRAL")
        rendered = _argument(thesis, rebuttals.get(i))
        groups.setdefault(direction, []).append(rendered)
        counts[direction] = counts.get(direction, 0) + 1
        if 'class="arg' in rendered and " dead" in rendered.split(">", 1)[0]:
            refuted += 1

    chips = [
        ("all", f"All {len(theses)}"),
        ("for", f"For {counts['FOR']}"),
        ("against", f"Against {counts['AGAINST']}"),
    ]
    if counts["NEUTRAL"]:
        chips.append(("neutral", f"Neutral {counts['NEUTRAL']}"))
    if refuted:
        chips.append(("refuted", f"Refuted {refuted}"))

    chip_html = "".join(
        f'<button type="button" class="chip" data-filter="{k}" '
        f'aria-pressed="{"true" if k == "all" else "false"}">{_esc(t)}</button>'
        for k, t in chips
    )

    cols = []
    for direction, title in (
        ("FOR", "Argues higher"),
        ("AGAINST", "Argues lower"),
        ("NEUTRAL", "Context — does not move the number"),
    ):
        if not groups.get(direction):
            if direction == "NEUTRAL":
                continue
            cols.append(
                f'<div class="col {direction.lower()}"><h4>{title}</h4>'
                f'<p class="empty">No argument in this direction survived.</p></div>'
            )
            continue
        cols.append(
            f'<div class="col {direction.lower()}"><h4>{title}</h4>'
            + "".join(groups[direction])
            + "</div>"
        )

    notes = "".join(
        f'<div class="note">{_esc(n)}</div>'
        for n in (thesis_data.get("notes") or [])
    )
    return (
        f'<div data-args="{_esc(key)}">'
        f'<div class="chips" data-filters>{chip_html}</div>'
        f'<div class="cols">{"".join(cols)}</div>{notes}</div>'
    )


def _metric(metric: dict, thesis_data: dict | None, key: str) -> str:
    units = metric.get("units", "")
    tags: list[str] = []
    if metric.get("needs_review"):
        tags.append('<span class="tag warn">needs review</span>')
    for est in metric.get("estimates") or []:
        tags.append(f'<span class="tag">{_esc(est.get("estimator", ""))}</span>')
    for engine in metric.get("engine_contributions") or []:
        if engine.get("status") == "available":
            tags.append(f'<span class="tag">{_esc(engine.get("engine", ""))}</span>')

    out = [
        '<div class="m"><div class="mh">',
        f'<span class="lbl">{_esc(metric.get("label", ""))}</span>',
        f'<span class="val">{_fmt(float(metric.get("value", 0)), units)}'
        f' <span class="un">{_esc(units)}</span></span></div>',
        f'<p class="why">{_esc(metric.get("reasoning", ""))}</p>',
    ]
    if tags:
        out.append(f'<div class="tags">{"".join(dict.fromkeys(tags))}</div>')
    for warning in metric.get("warnings") or []:
        out.append(f'<div class="note">{_esc(warning)}</div>')

    citations = metric.get("citations") or []
    if citations:
        out.append(
            f"<details><summary>{len(citations)} source"
            f"{'s' if len(citations) != 1 else ''}</summary><ul class='srcs'>"
            + "".join(f"<li>{_esc(c)}</li>" for c in citations)
            + "</ul></details>"
        )

    if thesis_data and thesis_data.get("theses"):
        out.append(_arguments(thesis_data, key))
    elif thesis_data:
        for note in thesis_data.get("notes") or []:
            out.append(f'<div class="note">{_esc(note)}</div>')

    out.append("</div>")
    return "".join(out)


def build(audit_path: Path = AUDIT, out_path: Path = OUT) -> Path:
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    theses = audit.get("theses") or {}

    total_args = sum(
        len(m.get("theses") or []) for c in theses.values() for m in c.values()
    )

    companies = []
    for forecast in audit.get("forecasts", []):
        ticker = forecast.get("ticker", "")
        per_metric = theses.get(ticker) or {}
        metrics = "".join(
            _metric(m, per_metric.get(m["label"]), f"{ticker}-{i}")
            for i, m in enumerate(forecast.get("metrics", []))
        )
        companies.append(
            f'<section class="co"><h2>{_esc(forecast.get("company", ""))}</h2>'
            f'<p class="per">{_esc(ticker)} · {_esc(_period(forecast.get("period")))}'
            f' · {_esc(forecast.get("output_file", ""))}</p>{metrics}</section>'
        )

    subtitle = (
        f"Generated {_esc(audit.get('generated_at', ''))} · "
        f"as of {_esc(audit.get('as_of') or 'full frozen corpus')}"
    )
    if total_args:
        subtitle += f" · {total_args} arguments across 12 forecasts"

    page = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Forecast report</title><style>" + _CSS + "</style></head><body><main>"
        "<h1>Twelve forecasts</h1>"
        f"<p class='sub'>{subtitle}</p>"
        + "".join(companies)
        + "</main><script>" + _JS + "</script></body></html>"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    path = build()
    print(f"wrote {path.relative_to(REPO_ROOT)}")
