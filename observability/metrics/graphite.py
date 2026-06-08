"""
Graphite metrics client for AutoDeal IA Hunter.
"""
import socket
from typing import Optional


class GraphiteMetrics:
    """Graphite metrics client."""
    
    def __init__(self, host: str = "localhost", port: int = 2003, prefix: str = "autodeal"):
        self.host = host
        self.port = port
        self.prefix = prefix
    
    def send(self, metric_name: str, value: float, timestamp: Optional[int] = None) -> bool:
        """Send metric to Graphite."""
        try:
            metric_path = f"{self.prefix}.{metric_name}"
            message = f"{metric_path} {value} {timestamp or ''}\n"
            
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect((self.host, self.port))
                sock.send(message.encode())
            
            return True
        except Exception:
            return False
    
    def increment(self, metric_name: str, value: int = 1) -> None:
        """Increment counter."""
        self.send(metric_name, value)
    
    def gauge(self, metric_name: str, value: float) -> None:
        """Set gauge."""
        self.send(metric_name, value)
    
    def timing(self, metric_name: str, duration_ms: float) -> None:
        """Record timing."""
        self.send(metric_name, duration_ms)
