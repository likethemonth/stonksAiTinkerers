"""Render the run into a self-contained HTML report.

    python -m forecast.report

Reads submission/forecast-audit.json (written by the run) plus any thesis output,
and produces submission/report.html: the twelve numbers, what each rests on, the
sources behind them, and the for/against arguments where the thesis pass ran.

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
--paper:#fff;--wash:#f8fafc;--up:#067647;--down:#b42318;--tint:#eef4ff}
*{box-sizing:border-box}
body{margin:0;background:var(--wash);color:var(--ink);
font:15px/1.6 Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
main{width:min(1040px,calc(100% - 32px));margin:32px auto 64px}
h1{font-size:clamp(30px,5vw,44px);letter-spacing:-.03em;margin:0 0 4px;text-wrap:balance}
.sub{color:var(--muted);margin:0 0 28px}
.co{background:var(--paper);border:1px solid var(--line);border-radius:14px;
padding:22px 24px;margin-bottom:20px;box-shadow:0 1px 2px rgb(16 24 40/.05)}
.co>h2{margin:0;font-size:19px;letter-spacing:-.01em}
.co>.per{color:var(--muted);font-size:13px;margin:2px 0 18px}
.m{border-top:1px solid var(--line);padding:18px 0 4px}
.m:first-of-type{border-top:0;padding-top:0}
.mh{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}
.lbl{font-weight:600}
.val{margin-left:auto;font-size:26px;font-weight:700;letter-spacing:-.02em;
font-variant-numeric:tabular-nums}
.un{color:var(--muted);font-size:13px;font-weight:500}
.why{color:var(--muted);font-size:13.5px;margin:8px 0 0;max-width:76ch}
.tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
.tag{font-size:11.5px;padding:2px 8px;border-radius:999px;background:var(--tint);
color:var(--blue);font-weight:600}
.tag.warn{background:#fef6ee;color:#b54708}
details{margin-top:12px}
summary{cursor:pointer;font-size:13px;color:var(--blue);font-weight:600}
summary::marker{color:var(--muted)}
.srcs{margin:10px 0 0;padding-left:18px}
.srcs li{font-size:12.5px;color:var(--muted);font-family:ui-monospace,SFMono-Regular,
Menlo,monospace;word-break:break-all}
.args{display:grid;gap:10px;margin-top:12px}
@media(min-width:760px){.args{grid-template-columns:1fr 1fr}}
.arg{border:1px solid var(--line);border-radius:10px;padding:12px 14px;background:var(--wash)}
.arg .d{font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}
.arg.for .d{color:var(--up)}
.arg.against .d{color:var(--down)}
.arg p{margin:6px 0 0;font-size:13px}
.arg .meta{margin-top:8px;font-size:11.5px;color:var(--muted)}
.arg.dead{opacity:.55}
.arg.dead .claim{text-decoration:line-through}
.note{background:#fffaf5;border:1px solid var(--line);border-radius:10px;
padding:12px 14px;margin-top:14px;font-size:13px}
.note b{display:block;font-size:11px;letter-spacing:.08em;text-transform:uppercase;
color:#b54708;margin-bottom:4px}
"""


def _esc(v: object) -> str:
    return html.escape(str(v))


def _fmt(value: float, units: str) -> str:
    if units in {"USDm", "GBPm"}:
        return f"{value:,.0f}"
    return f"{value:,.2f}"


def _argument(index: int, thesis: dict, rebuttal: str | None) -> str:
    direction = thesis.get("direction", "FOR")
    dead = rebuttal is not None and "incorrect" in rebuttal.lower()
    cls = f"arg {direction.lower()}{' dead' if dead else ''}"
    cites = ", ".join(str(i) for i in thesis.get("observation_ids", []))
    parts = [
        f'<div class="{cls}">',
        f'<div class="d">{_esc(direction)}</div>',
        f'<p class="claim">{_esc(thesis.get("claim", ""))}</p>',
        f'<div class="meta">effect {thesis.get("effect", 0):+,.2f} · '
        f'confidence {thesis.get("confidence", 0):.0%} · cites [{_esc(cites)}]</div>',
    ]
    if rebuttal:
        parts.append(f'<div class="meta"><em>Audit: {_esc(rebuttal)}</em></div>')
    parts.append("</div>")
    return "".join(parts)


def _metric(metric: dict, thesis: dict | None) -> str:
    units = metric.get("units", "")
    tags = []
    if metric.get("needs_review"):
        tags.append('<span class="tag warn">needs review</span>')
    for est in metric.get("estimates", []) or []:
        tags.append(f'<span class="tag">{_esc(est.get("estimator", ""))}</span>')
    for engine in metric.get("engine_contributions", []) or []:
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

    for warning in metric.get("warnings", []) or []:
        out.append(f'<div class="note"><b>Warning</b>{_esc(warning)}</div>')

    citations = metric.get("citations") or []
    if citations:
        out.append(
            f"<details><summary>{len(citations)} source"
            f"{'s' if len(citations) != 1 else ''}</summary><ul class='srcs'>"
            + "".join(f"<li>{_esc(c)}</li>" for c in citations)
            + "</ul></details>"
        )

    if thesis and thesis.get("theses"):
        rebuttals = {int(k): v for k, v in (thesis.get("rebuttals") or {}).items()}
        args = "".join(
            _argument(i, t, rebuttals.get(i))
            for i, t in enumerate(thesis["theses"])
        )
        out.append(
            "<details open><summary>Arguments for and against</summary>"
            f'<div class="args">{args}</div>'
        )
        for note in thesis.get("notes", []) or []:
            out.append(f'<div class="note"><b>Note</b>{_esc(note)}</div>')
        out.append("</details>")

    out.append("</div>")
    return "".join(out)


def build(audit_path: Path = AUDIT, out_path: Path = OUT) -> Path:
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    theses = audit.get("theses") or {}

    companies = []
    for forecast in audit.get("forecasts", []):
        metrics = "".join(
            _metric(m, (theses.get(forecast["ticker"]) or {}).get(m["label"]))
            for m in forecast.get("metrics", [])
        )
        companies.append(
            f'<section class="co"><h2>{_esc(forecast.get("company", ""))}</h2>'
            f'<p class="per">{_esc(forecast.get("ticker", ""))} · '
            f'{_esc(forecast.get("period", ""))} · '
            f'{_esc(forecast.get("output_file", ""))}</p>{metrics}</section>'
        )

    page = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>Forecast report</title><style>" + _CSS + "</style></head><body><main>"
        "<h1>Twelve forecasts</h1>"
        f"<p class='sub'>Generated {_esc(audit.get('generated_at', ''))} · "
        f"as of {_esc(audit.get('as_of') or 'full frozen corpus')}</p>"
        + "".join(companies)
        + "</main></body></html>"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(page, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    path = build()
    print(f"wrote {path.relative_to(REPO_ROOT)}")
