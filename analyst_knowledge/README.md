# Analyst source knowledge base

This repository mirrors the useful structure of the reference archive: immutable captures in `raw/`, normalized records in `dataset/`, regenerated facet trails in `generated/`, and evidence-led interpretation in `knowledge/`.

Build and test:

```bash
python3 -m unittest discover -s analyst_backtest -p 'test_*.py'
python3 -m analyst_backtest.build --as-of 2026-08-16T23:59:59Z
```

Candidate JSONL is deliberately retained separately from canonical output. Corrections belong in `dataset/overrides.tsv`; raw captures must not be silently rewritten.

The generated manifest hashes every evidence and derived file. Begin with `knowledge/00-OVERVIEW.md`. Person-first company research is in `knowledge/07-THOUGHT-LEADERS.md`; near-term accounting-source selection remains separate in `knowledge/05-SOURCE-SELECTION.md`.
