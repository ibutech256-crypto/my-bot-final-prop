from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from trading_engine.analytics_engine import AnalyticsEngine, ClosedTradeMetric
@dataclass(frozen=True)
class BacktestResult:
    trades: list[ClosedTradeMetric]
    metrics: dict
class BacktestingEngine:
    def summarize_closed_trades(self, trades:list[ClosedTradeMetric])->BacktestResult:
        return BacktestResult(trades, AnalyticsEngine().calculate(trades))
class MonteCarloEngine:
    def deterministic_resamples(self, profits:list[Decimal], paths:int=100)->list[Decimal]:
        if not profits: return []
        out=[]
        for p in range(paths):
            bal=Decimal(0)
            for i in range(len(profits)):
                bal += profits[(i*37+p*17) % len(profits)]
            out.append(bal)
        return out
class WalkForwardEngine:
    def split(self, items:list, train_size:int, test_size:int)->list[tuple[list,list]]:
        windows=[]; i=0
        while i+train_size+test_size <= len(items): windows.append((items[i:i+train_size], items[i+train_size:i+train_size+test_size])); i+=test_size
        return windows
class StressTestingEngine:
    def apply_slippage_and_commission(self, profits:list[Decimal], slippage_cost:Decimal, commission:Decimal)->list[Decimal]:
        return [p - abs(slippage_cost) - abs(commission) for p in profits]
