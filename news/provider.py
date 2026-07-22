from dataclasses import dataclass
from datetime import datetime
@dataclass(frozen=True)
class NewsEvent: title:str; source:str; published_at:datetime; impact:str; symbols:list[str]
class NewsFilter:
    def high_impact_for_symbols(self,events:list[NewsEvent],symbols:set[str])->list[NewsEvent]: return [e for e in events if e.impact.upper()=="HIGH" and bool(symbols.intersection(e.symbols))]
