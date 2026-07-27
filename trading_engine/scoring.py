"""v2.2 Scoring Engine - Properly weight KOD, cap non-KOD scores."""
from __future__ import annotations
from decimal import Decimal
from trading_engine.types import Direction, LiquidityEvent, NewsState, ScoreBreakdown, SessionState, StructureState

class ScoringEngine:
    weights = {
        "CRT": Decimal("12"),
        "Liquidity": Decimal("15"),
        "KOD": Decimal("18"),  # Increased from 12
        "CISD": Decimal("12"),
        "HTF Alignment": Decimal("15"),
        "Session": Decimal("8"),
        "Structure": Decimal("10"),
        "Risk": Decimal("5"),
        "Volatility": Decimal("3"),
        "News": Decimal("2"),
    }

    def score(self, direction, liquidity, kod, cisd, htf, session, structure, risk_ok, volatility_ok, news, minimum=Decimal("75")):
        c = {
            "CRT": self.weights["CRT"],
            "Liquidity": self.weights["Liquidity"] if liquidity and not liquidity.failed else Decimal("0"),
            "KOD": self.weights["KOD"] if kod else Decimal("0"),
            "CISD": self.weights["CISD"] if cisd else Decimal("0"),
            "HTF Alignment": self.weights["HTF Alignment"] if htf else Decimal("0"),
            "Session": self.weights["Session"] if session.liquid else Decimal("0"),
            "Structure": self.weights["Structure"] if structure.bias in {direction, Direction.NEUTRAL} else Decimal("0"),
            "Risk": self.weights["Risk"] if risk_ok else Decimal("0"),
            "Volatility": self.weights["Volatility"] if volatility_ok else Decimal("0"),
            "News": self.weights["News"] if news.trading_allowed else Decimal("0"),
        }
        total = sum(c.values(), Decimal("0"))
        # v2.2: Without KOD, max score is 70
        if not kod:
            total = min(total, Decimal("70"))
        passed = False
        if total >= Decimal("55") and liquidity and not liquidity.failed and kod:
            passed = True
        if total >= Decimal("70") and htf and kod:
            passed = True
        if total >= minimum and kod:
            passed = True
        return ScoreBreakdown(total, c, passed)
