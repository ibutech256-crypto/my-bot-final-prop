"""Central Event Bus - all system events flow through this."""
import os, sys, json, time, threading
from datetime import datetime, timezone
from collections import deque

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

class EventBus:
    """Singleton event bus for all system events."""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.events = deque(maxlen=1000)
        self.listeners = []
        self.event_count = 0
    
    def emit(self, event_type, module, severity="INFO", **kwargs):
        """Emit an event to all listeners."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_id": self.event_count + 1,
            "type": event_type,
            "module": module,
            "severity": severity,
            **kwargs
        }
        self.events.append(event)
        self.event_count += 1
        
        # Log to file
        log_line = json.dumps(event)
        try:
            log_path = os.path.join(os.path.dirname(__file__), "..", "logs", "events.jsonl")
            with open(log_path, "a") as f:
                f.write(log_line + "\n")
        except:
            pass
        
        # Notify listeners
        for listener in self.listeners:
            try:
                listener(event)
            except:
                pass
    
    def subscribe(self, callback):
        self.listeners.append(callback)
    
    def get_events(self, since_id=0, limit=50, severity=None, module=None):
        filtered = []
        for e in list(self.events)[-limit:]:
            if e["event_id"] <= since_id:
                continue
            if severity and e["severity"] != severity:
                continue
            if module and e["module"] != module:
                continue
            filtered.append(e)
        return filtered
    
    def get_stats(self):
        severities = {"INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 0}
        for e in self.events:
            severities[e["severity"]] = severities.get(e["severity"], 0) + 1
        return {
            "total_events": self.event_count,
            "recent_events": len(self.events),
            "severities": severities,
        }

# Global instance
bus = EventBus()
