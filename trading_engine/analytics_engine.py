"""
Institutional Analytics Engine v2.0
Calculates all performance metrics in real-time from trade data.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Tuple
import math
import numpy as np


@dataclass
class TradeRecord:
    symbol: str
    asset_class: str
    strategy: str
    direction: str
    entry_price: Decimal
    exit_price: Decimal
    volume: Decimal
    profit: Decimal
    rr: Decimal
    duration_minutes: int
    opened_at: datetime
    closed_at: datetime
    exit_reason: str  # TP, SL, MANUAL, EXPIRY


@dataclass
class PerformanceMetrics:
    # Risk-adjusted returns
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    profit_factor: float = 0.0
    recovery_factor: float = 0.0
    
    # Trade statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    loss_rate: float = 0.0
    
    # Average values
    avg_win: float = 0.0
    avg_loss: float = 0.0
    avg_rr: float = 0.0
    expectancy: float = 0.0
    avg_r_multiple: float = 0.0
    
    # Extremes
    largest_winner: float = 0.0
    largest_loser: float = 0.0
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    
    # P&L
    net_profit: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    max_drawdown: float = 0.0
    
    # Time-based
    daily_pnl: Dict[str, float] = field(default_factory=dict)
    weekly_pnl: Dict[str, float] = field(default_factory=dict)
    monthly_pnl: Dict[str, float] = field(default_factory=dict)
    yearly_pnl: Dict[str, float] = field(default_factory=dict)
    
    # Equity curve data points
    equity_curve: List[float] = field(default_factory=list)
    balance_curve: List[float] = field(default_factory=list)
    drawdown_curve: List[float] = field(default_factory=list)
    equity_dates: List[str] = field(default_factory=list)


class AnalyticsEngine:
    """Computes full institutional performance analytics."""
    
    @staticmethod
    def compute(trades: List[TradeRecord], initial_balance: Decimal = Decimal("0")) -> PerformanceMetrics:
        m = PerformanceMetrics()
        if not trades:
            return m
        
        m.total_trades = len(trades)
        profits = [float(t.profit) for t in trades]
        winning = [p for p in profits if p > 0]
        losing = [p for p in profits if p < 0]
        rr_values = [float(t.rr) for t in trades if t.rr > 0]
        
        m.winning_trades = len(winning)
        m.losing_trades = len(losing)
        m.win_rate = (m.winning_trades / m.total_trades * 100) if m.total_trades > 0 else 0
        m.loss_rate = 100 - m.win_rate
        
        # Averages
        m.avg_win = float(np.mean(winning)) if winning else 0
        m.avg_loss = float(abs(np.mean(losing))) if losing else 0
        m.avg_rr = float(np.mean(rr_values)) if rr_values else 0
        m.net_profit = float(np.sum(profits))
        m.gross_profit = float(np.sum(winning)) if winning else 0
        m.gross_loss = float(abs(np.sum(losing))) if losing else 0
        
        # Profit Factor
        m.profit_factor = m.gross_profit / m.gross_loss if m.gross_loss > 0 else (m.gross_profit if m.gross_profit > 0 else 0)
        
        # Expectancy
        m.expectancy = (m.win_rate / 100 * m.avg_win) - (m.loss_rate / 100 * m.avg_loss) if m.avg_win and m.avg_loss else 0
        m.avg_r_multiple = m.avg_rr if m.avg_rr else 0
        
        # Extremes
        m.largest_winner = max(winning) if winning else 0
        m.largest_loser = min(profits) if losing else 0
        
        # Consecutive
        cons_wins, cons_losses = 0, 0
        max_cons_wins, max_cons_losses = 0, 0
        for p in profits:
            if p > 0:
                cons_wins += 1; cons_losses = 0
                max_cons_wins = max(max_cons_wins, cons_wins)
            elif p < 0:
                cons_losses += 1; cons_wins = 0
                max_cons_losses = max(max_cons_losses, cons_losses)
        m.consecutive_wins = max_cons_wins
        m.consecutive_losses = max_cons_losses
        
        # Build equity curve
        balance = float(initial_balance)
        peak = balance
        m.equity_curve = [balance]
        m.balance_curve = [balance]
        m.equity_dates = ["START"]
        
        for i, t in enumerate(trades):
            balance += float(t.profit)
            m.balance_curve.append(float(initial_balance) + sum(profits[:i+1]))
            m.equity_curve.append(balance)
            m.equity_dates.append(t.closed_at.strftime("%Y-%m-%d %H:%M") if hasattr(t, 'closed_at') else str(i))
            peak = max(peak, balance)
            dd = ((peak - balance) / peak * 100) if peak > 0 else 0
            m.drawdown_curve.append(dd)
        
        m.max_drawdown = max(m.drawdown_curve) if m.drawdown_curve else 0
        
        # Risk-adjusted ratios
        returns = np.diff(m.equity_curve) / m.equity_curve[:-1] if len(m.equity_curve) > 1 else [0]
        if len(returns) > 1 and np.std(returns) > 0:
            m.sharpe_ratio = float(np.mean(returns) / np.std(returns) * np.sqrt(252))
            downside = [r for r in returns if r < 0]
            if downside and np.std(downside) > 0:
                m.sortino_ratio = float(np.mean(returns) / np.std(downside) * np.sqrt(252))
        
        # Calmar Ratio
        if m.max_drawdown > 0:
            m.calmar_ratio = m.net_profit / m.max_drawdown if m.net_profit != 0 else 0
        
        # Recovery Factor
        if abs(m.max_drawdown) > 0 and initial_balance > 0:
            m.recovery_factor = m.net_profit / (m.max_drawdown * float(initial_balance) / 100) if m.max_drawdown > 0 else 0
        
        # Time-based PnL
        for t in trades:
            date_key = t.closed_at.strftime("%Y-%m-%d")
            week_key = t.closed_at.strftime("%Y-W%W")
            month_key = t.closed_at.strftime("%Y-%m")
            year_key = t.closed_at.strftime("%Y")
            p = float(t.profit)
            m.daily_pnl[date_key] = m.daily_pnl.get(date_key, 0) + p
            m.weekly_pnl[week_key] = m.weekly_pnl.get(week_key, 0) + p
            m.monthly_pnl[month_key] = m.monthly_pnl.get(month_key, 0) + p
            m.yearly_pnl[year_key] = m.yearly_pnl.get(year_key, 0) + p
        
        return m
    
    @staticmethod
    def asset_performance(trades: List[TradeRecord]) -> Dict[str, PerformanceMetrics]:
        assets = {}
        for t in trades:
            cls = t.asset_class
            if cls not in assets:
                assets[cls] = []
            assets[cls].append(t)
        return {k: AnalyticsEngine.compute(v) for k, v in assets.items()}
    
    @staticmethod
    def strategy_performance(trades: List[TradeRecord]) -> Dict[str, PerformanceMetrics]:
        strategies = {}
        for t in trades:
            s = t.strategy
            if s not in strategies:
                strategies[s] = []
            strategies[s].append(t)
        return {k: AnalyticsEngine.compute(v) for k, v in strategies.items()}
