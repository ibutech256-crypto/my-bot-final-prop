from __future__ import annotations
from datetime import datetime, time, timezone
from trading_engine.types import SessionState
class SessionEngine:
    def __init__(self):
        self.sessions={"Sydney":(time(21,0),time(6,0)),"Tokyo":(time(0,0),time(9,0)),"London":(time(7,0),time(16,0)),"New York":(time(12,0),time(21,0))}
        self.kill_zones={"London Open":(time(7,0),time(10,0)),"New York Open":(time(12,0),time(15,0)),"Power Hour":(time(19,0),time(20,0))}
    def _inside(self,t:time,start:time,end:time)->bool: return start<=t<=end if start<=end else t>=start or t<=end
    def evaluate(self, dt: datetime) -> SessionState:
        _u=dt.astimezone(timezone.utc)
        # Forex weekend: closes Fri 21:00 UTC, reopens Sun 21:00 UTC.
        _wd=_u.weekday()  # Mon=0 .. Sat=5, Sun=6
        if _wd==5 or (_wd==4 and _u.hour>=21) or (_wd==6 and _u.hour<21):
            return SessionState("Weekend/Closed", False, False, "Forex market closed for the weekend.")
        utc=dt.astimezone(timezone.utc).time(); active=[n for n,(s,e) in self.sessions.items() if self._inside(utc,s,e)]; kill=[n for n,(s,e) in self.kill_zones.items() if self._inside(utc,s,e)]
        if kill: return SessionState(kill[0], True, True, "High-liquidity institutional kill zone.")
        if active and active[0] in {"London","New York"}: return SessionState(active[0], False, True, "Major liquid session.")
        if active: return SessionState(active[0], False, False, "Session active but below preferred liquidity window.")
        return SessionState("Closed/Transition", False, False, "Avoiding low-liquidity transition period.")
