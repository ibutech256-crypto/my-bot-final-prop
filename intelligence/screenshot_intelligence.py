from __future__ import annotations
from pathlib import Path
from trading_engine.types import TradeSetup
class ScreenshotIntelligenceEngine:
    def render_svg_annotation(self, setup:TradeSetup, output_path:str)->str:
        path=Path(output_path); path.parent.mkdir(parents=True,exist_ok=True)
        svg=f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="700" viewBox="0 0 1200 700"><rect width="1200" height="700" fill="#050816"/><text x="40" y="60" fill="#e5eefb" font-size="28">{setup.symbol} {setup.direction.value} Trade Annotation</text><line x1="80" x2="1120" y1="220" y2="220" stroke="#22c55e" stroke-width="3"/><text x="90" y="205" fill="#22c55e">Entry {setup.entry}</text><line x1="80" x2="1120" y1="320" y2="320" stroke="#ef4444" stroke-width="3"/><text x="90" y="305" fill="#ef4444">SL {setup.stop_loss}</text><line x1="80" x2="1120" y1="130" y2="130" stroke="#38bdf8" stroke-width="3"/><text x="90" y="115" fill="#38bdf8">TP3 {setup.take_profit_3}</text><rect x="80" y="380" width="1040" height="160" fill="rgba(255,255,255,0.06)" stroke="#64748b"/><text x="100" y="420" fill="#e5eefb" font-size="18">CRT: {setup.crt_range.low} - {setup.crt_range.high}</text><text x="100" y="455" fill="#e5eefb" font-size="18">Liquidity: {setup.liquidity_event.kind}</text><text x="100" y="490" fill="#e5eefb" font-size="18">Score: {setup.score.total}</text></svg>"""
        path.write_text(svg)
        return str(path)
