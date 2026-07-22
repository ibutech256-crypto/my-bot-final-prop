from celery import shared_task
from intelligence.vps_health import VPSHealthEngine
@shared_task
def vps_health_snapshot() -> dict:
    h=VPSHealthEngine(); checks=[h.disk('/'), h.process_running('redis'), h.process_running('postgres'), h.process_running('celery')]
    return {c.component:{'healthy':c.healthy,'message':c.message} for c in checks}


@shared_task
def cleanup_resampler_cache() -> dict:
    from intelligence.resampling_cache import GLOBAL_RESAMPLER_CACHE
    stats = GLOBAL_RESAMPLER_CACHE.cleanup()
    return {"entries": stats.entries, "bytes_estimate": stats.bytes_estimate, "oldest_entry": stats.oldest_entry.isoformat() if stats.oldest_entry else None}
