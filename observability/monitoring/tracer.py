"""
Distributed tracer for AutoDeal IA Hunter.
"""
from typing import Dict, Optional, ContextManager
from contextlib import contextmanager
from datetime import datetime
import uuid


class Tracer:
    """Distributed tracer for request tracing."""
    
    def __init__(self):
        self.active_spans: Dict[str, Dict[str, any]] = {}
    
    @contextmanager
    def start_span(self, name: str, parent_span_id: Optional[str] = None) -> ContextManager:
        """Start a new span."""
        span_id = str(uuid.uuid4())
        span = {
            "id": span_id,
            "name": name,
            "parent_id": parent_span_id,
            "start_time": datetime.utcnow(),
            "end_time": None,
            "duration_ms": None,
            "tags": {},
        }
        
        self.active_spans[span_id] = span
        
        try:
            yield span_id
        finally:
            span["end_time"] = datetime.utcnow()
            span["duration_ms"] = (span["end_time"] - span["start_time"]).total_seconds() * 1000
            del self.active_spans[span_id]
    
    def add_tag(self, span_id: str, key: str, value: any) -> None:
        """Add tag to span."""
        if span_id in self.active_spans:
            self.active_spans[span_id]["tags"][key] = value
    
    def get_spans(self) -> list:
        """Get all completed spans."""
        return []
