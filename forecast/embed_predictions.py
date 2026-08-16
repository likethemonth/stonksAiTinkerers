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

START = "<!-- PREDICTIONS-EMBED:START -->"
END = "<!-- PREDICTIONS-EMBED:END -->"

#: Tall enough for the explorer's own layout; it scrolls internally beyond this.
FRAME_HEIGHT = 1680


def _srcdoc(html: str) -> str:
    """Escape a whole document so it survives inside a double-quoted attribute."""
    return html.replace("&", "&amp;").replace('"', "&quot;")


def main() -> int:
    if not PREDICTIONS.exists():
        print(f"  SKIP: {PREDICTIONS.relative_to(REPO_ROOT)} not built yet")
        return 0

    index = INDEX.read_text(encoding="utf-8")
    if START not in index or END not in index:
        print(f"  FAIL: markers missing from {INDEX.relative_to(REPO_ROOT)}")
        return 1

    frame = (
        f'<iframe title="Forecast explorer: stock by method" '
        f'style="width:100%;height:{FRAME_HEIGHT}px;border:0;display:block" '
        f'srcdoc="{_srcdoc(PREDICTIONS.read_text(encoding="utf-8"))}"></iframe>'
    )

    head, _, rest = index.partition(START)
    _, _, tail = rest.partition(END)
    INDEX.write_text(f"{head}{START}\n{frame}\n{END}{tail}", encoding="utf-8")

    size = INDEX.stat().st_size
    print(
        f"  embedded {PREDICTIONS.name} into {INDEX.name} "
        f"({size / 1024:.0f} KB, self-contained)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
