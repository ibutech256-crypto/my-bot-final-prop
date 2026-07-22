from __future__ import annotations
import re
class SmartSymbolMappingEngine:
    def canonical(self,symbol:str)->str:
        s=symbol.upper().replace(".PRO","").replace(".CASH","").replace("_","").replace("-","")
        s=re.sub(r"(M|A|ECN|RAW|STD)$","",s)
        return s
    def map(self, requested:str, available:list[str])->str|None:
        target=self.canonical(requested)
        scored=sorted(((self._score(target,self.canonical(a)),a) for a in available), reverse=True)
        return scored[0][1] if scored and scored[0][0]>=80 else None
    def _score(self,a:str,b:str)->int:
        if a==b: return 100
        if a in b or b in a: return 90
        common=sum(1 for x,y in zip(a,b) if x==y)
        return int(common/max(len(a),len(b))*100) if a and b else 0
