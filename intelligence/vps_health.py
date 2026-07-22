from __future__ import annotations
from dataclasses import dataclass
import shutil, subprocess, urllib.request, os
@dataclass(frozen=True)
class HealthCheckResult:
    component:str; healthy:bool; message:str
class VPSHealthEngine:
    def disk(self,path:str="/")->HealthCheckResult:
        total,used,free=shutil.disk_usage(path); pct=used/total*100
        return HealthCheckResult("disk",pct<90,f"disk used {pct:.1f}%")
    def process_running(self,name:str)->HealthCheckResult:
        try:
            out=subprocess.run(["pgrep","-f",name],capture_output=True,text=True,timeout=5)
            return HealthCheckResult(name,out.returncode==0,"running" if out.returncode==0 else "not running")
        except Exception as exc: return HealthCheckResult(name,False,str(exc))
    def http(self,name:str,url:str,timeout:int=5)->HealthCheckResult:
        try:
            with urllib.request.urlopen(url,timeout=timeout) as r: return HealthCheckResult(name,200<=r.status<500,f"HTTP {r.status}")
        except Exception as exc: return HealthCheckResult(name,False,str(exc))
    def restart_service(self,service:str)->HealthCheckResult:
        if os.name == "nt": cmd=["powershell","Restart-Service",service]
        else: cmd=["systemctl","restart",service]
        try:
            r=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
            return HealthCheckResult(service,r.returncode==0,r.stderr or r.stdout or "restart command executed")
        except Exception as exc: return HealthCheckResult(service,False,str(exc))
