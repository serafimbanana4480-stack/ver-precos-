"""
PostgreSQL pool sizing and optimization
Based on Obsidian Vault documentation for PostgreSQL pool sizing
"""
import logging
from typing import Optional
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool, NullPool
from config import settings

logger = logging.getLogger(__name__)


class PoolSizer:
    """Calculate optimal pool size based on system resources and workload"""
    
    # Formula: pool_size = (total_memory - shared_buffers - OS_cache) / (work_mem * 3)
    # Conservative estimate: pool_size = (total_memory_gb * 1024) / (work_mem_mb * 3)
    
    @staticmethod
    def calculate_pool_size(
        total_memory_gb: float = 8.0,
        max_connections: int = 100,
        expected_concurrent_queries: int = 20
    ) -> dict:
        """
        Calculate optimal pool configuration
        
        Args:
            total_memory_gb: Total system memory in GB
            max_connections: Maximum connections PostgreSQL allows
            expected_concurrent_queries: Expected concurrent queries
            
        Returns:
            Dictionary with pool configuration
        """
        # Conservative memory allocation per connection
        memory_per_connection_mb = 10  # 10MB per connection
        
        # Calculate pool size
        pool_size = min(
            int((total_memory_gb * 1024) / memory_per_connection_mb),
            expected_concurrent_queries
        )
        
        # Ensure minimum pool size
        pool_size = max(5, pool_size)
        
        # Max overflow for peak loads
        max_overflow = min(pool_size * 2, max_connections - pool_size)
        
        config = {
            'pool_size': pool_size,
            'max_overflow': max_overflow,
            'pool_timeout': 30,  # seconds
            'pool_recycle': 3600,  # 1 hour
            'pool_pre_ping': True,
            'explanation': {
                'total_memory_gb': total_memory_gb,
                'memory_per_connection_mb': memory_per_connection_mb,
                'calculated_pool_size': pool_size,
                'max_overflow': max_overflow,
                'max_total_connections': pool_size + max_overflow
            }
        }
        
        logger.info(f"Pool configuration: {config}")
        return config
    
    @staticmethod
    def get_pool_config_for_workload(workload_type: str = 'standard') -> dict:
        """
        Get pool configuration based on workload type
        
        Args:
            workload_type: 'standard', 'high_concurrency', 'batch', 'analytics'
            
        Returns:
            Pool configuration dictionary
        """
        configs = {
            'standard': {
                'pool_size': 5,
                'max_overflow': 10,
                'pool_timeout': 30,
                'pool_recycle': 3600,
                'pool_pre_ping': True
            },
            'high_concurrency': {
                'pool_size': 10,
                'max_overflow': 20,
                'pool_timeout': 30,
                'pool_recycle': 3600,
                'pool_pre_ping': True
            },
            'batch': {
                'pool_size': 3,
                'max_overflow': 5,
                'pool_timeout': 60,
                'pool_recycle': 1800,  # 30 minutes
                'pool_pre_ping': True
            },
            'analytics': {
                'pool_size': 2,
                'max_overflow': 3,
                'pool_timeout': 120,
                'pool_recycle': 7200,  # 2 hours
                'pool_pre_ping': True
            }
        }
        
        return configs.get(workload_type, configs['standard'])


def create_optimized_engine(
    database_url: str,
    workload_type: str = 'standard',
    pool_config: Optional[dict] = None
):
    """
    Create database engine with optimized pool configuration
    
    Args:
        database_url: Database connection URL
        workload_type: Type of workload
        pool_config: Optional custom pool configuration
        
    Returns:
        SQLAlchemy engine
    """
    if pool_config is None:
        pool_config = PoolSizer.get_pool_config_for_workload(workload_type)
    
    engine = create_engine(
        database_url,
        poolclass=QueuePool,
        **pool_config,
        echo=False
    )
    
    logger.info(f"Created engine with pool config: {pool_config}")
    return engine


def monitor_pool_health(engine) -> dict:
    """
    Monitor pool health and return statistics
    
    Args:
        engine: SQLAlchemy engine
        
    Returns:
        Dictionary with pool health statistics
    """
    pool = engine.pool
    
    stats = {
        'pool_size': pool.size(),
        'checked_in': pool.checkedin(),
        'checked_out': pool.checkedout(),
        'overflow': pool.overflow(),
        'status': 'healthy' if pool.checkedout() < pool.size() + pool.max_overflow else 'under_pressure'
    }
    
    logger.info(f"Pool health: {stats}")
    return stats


if __name__ == "__main__":
    # Test pool sizing
    config = PoolSizer.calculate_pool_size(total_memory_gb=16.0)
    print(f"Calculated pool config: {config}")
    
    # Test workload-based config
    standard_config = PoolSizer.get_pool_config_for_workload('standard')
    print(f"Standard workload config: {standard_config}")
