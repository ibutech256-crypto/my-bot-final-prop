from __future__ import annotations
from datetime import datetime, time, timezone
from intelligence.config import IntelligenceConfig, KillZoneDefinition
class HardKillZoneEngine:
    def __init__(self, config:IntelligenceConfig=IntelligenceConfig()): self.config=config
    def _inside(self,t:time,start:time,end:time)->bool: return start<=t<=end if start<=end else t>=start or t<=end
    def evaluate(self, dt:datetime)->tuple[bool,str]:
        t=dt.astimezone(timezone.utc).time()
        active=[z.name for z in self.config.kill_zones if z.enabled and self._inside(t,z.start_utc,z.end_utc)]
        return (True, active[0]) if active else (False,"Execution blocked outside approved institutional kill zones")
