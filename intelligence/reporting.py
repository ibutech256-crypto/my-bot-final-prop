from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
@dataclass(frozen=True)
class Report:
    period:str; generated_at:datetime; sections:dict
class ReportingEngine:
    def generate(self, period:str, performance:dict, symbol_stats:dict, strategy_stats:dict, portfolio_stats:dict, broker_stats:dict)->Report:
        return Report(period, datetime.utcnow(), {"performance":performance,"equity_curve":performance.get("equity_curve",[]),"drawdown":performance.get("drawdown"),"profit_factor":performance.get("profit_factor"),"expectancy":performance.get("expectancy"),"win_rate":performance.get("win_rate"),"symbol_statistics":symbol_stats,"strategy_statistics":strategy_stats,"portfolio_statistics":portfolio_stats,"broker_statistics":broker_stats})
    def markdown(self, report:Report)->str:
        lines=[f"# {report.period.title()} Institutional Trading Report",f"Generated: {report.generated_at.isoformat()}Z"]
        for k,v in report.sections.items(): lines += [f"\n## {k.replace('_',' ').title()}", str(v)]
        return "\n".join(lines)
