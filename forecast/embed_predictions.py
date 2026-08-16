"""Inline the forecast explorer into the architecture page.

    .venv/bin/python -m forecast.embed_predictions

The architecture page is uploaded to the judges as one self-contained file, so
a link to ``architecture/predictions.html`` does not resolve for them: the file
simply is not there. Linking out to GitHub works but throws the reader out of
the document they were asked to review.

This inlines the whole explorer instead, as an ``iframe srcdoc``. The explorer
already ships its own CSS, data and vanilla JS with no external requests, and an
iframe gives it a separate document, so its styles and globals cannot collide
with the architecture page's own. The result stays a single file with no
network dependency.

Runs after ``forecast.build_predictions_page`` in the final command, and is
idempotent: it replaces whatever sits between the two marker comments.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX = REPO_ROOT / "architecture" / "index.html"
PREDICTIONS = REPO_ROOT / "architecture" / "predictions.html"

#: (marker name, source file, frame height, iframe title). Each entry is
#: inlined between its own pair of marker comments in the architecture page.
EMBEDS = (
    (
        "PREDICTIONS",
        REPO_ROOT / "architecture" / "predictions.html",
        1680,
        "Forecast explorer: stock by method",
    ),
    (
        "PRESENTATION",
        REPO_ROOT / "presentation" / "ml.html",
        820,
        "The machine learning lens: slide deck",
    ),
)


def _srcdoc(html: str) -> str:
    """Escape a whole document so it survives inside a double-quoted attribute."""
    return html.replace("&", "&amp;").replace('"', "&quot;")


def main() -> int:
    index = INDEX.read_text(encoding="utf-8")

    for name, source, height, title in EMBEDS:
        start, end = f"<!-- {name}-EMBED:START -->", f"<!-- {name}-EMBED:END -->"
        if not source.exists():
            print(f"  SKIP {source.name}: not built yet")
            continue
        if start not in index or end not in index:
            print(f"  SKIP {source.name}: no {name} markers in {INDEX.name}")
            continue
        frame = (
            f'<iframe title="{title}" '
            f'style="width:100%;height:{height}px;border:0;display:block" '
            f'srcdoc="{_srcdoc(source.read_text(encoding="utf-8"))}"></iframe>'
        )
        head, _, rest = index.partition(start)
        _, _, tail = rest.partition(end)
        index = f"{head}{start}\n{frame}\n{end}{tail}"
        print(f"  embedded {source.name}")

    INDEX.write_text(index, encoding="utf-8")
    print(f"  {INDEX.name} is {INDEX.stat().st_size / 1024:.0f} KB, self-contained")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
