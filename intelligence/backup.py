from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import shutil, tarfile
@dataclass(frozen=True)
class BackupResult:
    path:str; files:int; bytes:int
class BackupEngine:
    def create_archive(self, sources:list[str], destination_dir:str, label:str="platform")->BackupResult:
        dest=Path(destination_dir); dest.mkdir(parents=True,exist_ok=True); archive=dest/f"{label}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.tar.gz"; count=0
        with tarfile.open(archive,"w:gz") as tar:
            for src in sources:
                p=Path(src)
                if p.exists(): tar.add(p,arcname=p.name); count+=sum(1 for _ in p.rglob('*')) if p.is_dir() else 1
        return BackupResult(str(archive),count,archive.stat().st_size)
    def enforce_retention(self,destination_dir:str,retention_days:int)->list[str]:
        cutoff=datetime.utcnow()-timedelta(days=retention_days); removed=[]
        for p in Path(destination_dir).glob("*.tar.gz"):
            if datetime.utcfromtimestamp(p.stat().st_mtime)<cutoff: p.unlink(); removed.append(str(p))
        return removed
