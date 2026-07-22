from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib, platform
@dataclass(frozen=True)
class License:
    key:str; customer_id:str; plan:str; expires_at:datetime; features:dict; machine_hash:str
class CommercialManagementEngine:
    def machine_fingerprint(self)->str:
        raw=f"{platform.node()}|{platform.system()}|{platform.machine()}|{platform.processor()}"
        return hashlib.sha256(raw.encode()).hexdigest()
    def validate(self,license:License, required_feature:str)->tuple[bool,str]:
        if license.expires_at.astimezone(timezone.utc) < datetime.now(timezone.utc): return False,"License expired"
        if license.machine_hash and license.machine_hash != self.machine_fingerprint(): return False,"Machine binding mismatch"
        if not license.features.get(required_feature,False): return False,f"Feature not enabled: {required_feature}"
        return True,"License valid"
    def feature_flags(self,license:License)->dict: return dict(license.features)|{"plan":license.plan,"customer_id":license.customer_id}
