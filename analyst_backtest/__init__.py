"""Point-in-time analyst claim backtesting and knowledge-base generation."""

from .scoring import BacktestError, run_backtest

__all__ = ["BacktestError", "run_backtest"]
