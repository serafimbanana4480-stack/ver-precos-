"""
Queue configuration for AutoDeal IA Hunter.
"""
from pydantic import BaseModel
from typing import Optional


class QueueConfig(BaseModel):
    """Configuration for queue settings."""
    
    enabled: bool = True
    backend: str = "redis"  # redis, memory, rabbitmq
    
    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 1
    redis_password: Optional[str] = None
    
    # Queue settings
    max_queue_size: int = 1000
    max_retries: int = 3
    retry_delay_seconds: int = 60
    
    # Worker settings
    num_workers: int = 4
    worker_timeout_seconds: int = 300
    
    # Dead letter queue
    enable_dlq: bool = True
    dlq_ttl_seconds: int = 86400


queue_config = QueueConfig()
