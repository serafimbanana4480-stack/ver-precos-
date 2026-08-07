"""
Proxy Monitoring and Alerting
Monitors proxy pool health and sends alerts on issues
"""
from __future__ import annotations
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from utils.proxy_manager import get_proxy_pool

logger = logging.getLogger(__name__)


class ProxyMonitor:
    """Monitors proxy pool health and performance"""
    
    def __init__(self):
        self.proxy_pool = get_proxy_pool()
        self.alert_threshold_exhaustion = 1  # Alert when only 1 proxy available
        self.alert_threshold_degraded = 0.5  # Alert when 50% of proxies are degraded
    
    def check_pool_health(self) -> Dict[str, Any]:
        """
        Check proxy pool health and generate alerts
        
        Returns:
            Dictionary with health status and alerts
        """
        stats = self.proxy_pool.get_stats()
        alerts = []
        
        # Check for pool exhaustion
        available = stats['available_proxies']
        if available <= self.alert_threshold_exhaustion:
            alerts.append({
                'type': 'critical',
                'message': f'Proxy pool nearly exhausted: only {available} proxies available',
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            logger.critical(f"[PROXY ALERT] Proxy pool nearly exhausted: only {available} proxies available")
        
        # Check for degraded proxies
        degraded_count = sum(1 for p in stats['proxy_details'] if p['status'] == 'degraded')
        total = stats.get('total_proxies') or 0
        if total > 0 and degraded_count / total >= self.alert_threshold_degraded:
            alerts.append({
                'type': 'warning',
                'message': f'High number of degraded proxies: {degraded_count}/{stats["total_proxies"]}',
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            logger.warning(
                "[PROXY ALERT] High number of degraded proxies: %s/%s",
                degraded_count, stats['total_proxies'],
            )
        
        # Check for blacklisted proxies
        blacklisted_count = stats['blacklisted_proxies']
        if blacklisted_count > 0:
            alerts.append({
                'type': 'info',
                'message': f'{blacklisted_count} proxies blacklisted',
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            logger.info(f"[PROXY] {blacklisted_count} proxies blacklisted")
        
        # Calculate overall health score
        if stats['total_proxies'] > 0:
            avg_health_score = sum(p['health_score'] for p in stats['proxy_details']) / stats['total_proxies']
        else:
            avg_health_score = 0.0
        
        # Determine overall status
        if available == 0:
            overall_status = 'critical'
        elif avg_health_score < 50 or available <= self.alert_threshold_exhaustion:
            overall_status = 'warning'
        else:
            overall_status = 'healthy'
        
        return {
            'overall_status': overall_status,
            'avg_health_score': avg_health_score,
            'alerts': alerts,
            'stats': stats,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
    
    def get_summary(self) -> str:
        """Get a human-readable summary of proxy pool status"""
        health = self.check_pool_health()
        stats = health['stats']
        
        summary = f"Proxy Pool Status: {health['overall_status'].upper()}\n"
        summary += f"Total Proxies: {stats['total_proxies']}\n"
        summary += f"Available: {stats['available_proxies']}\n"
        summary += f"Blacklisted: {stats['blacklisted_proxies']}\n"
        summary += f"Rotation Strategy: {stats['rotation_strategy']}\n"
        summary += f"Average Health Score: {health['avg_health_score']:.1f}/100\n"
        
        if health['alerts']:
            summary += f"\nAlerts ({len(health['alerts'])}):\n"
            for alert in health['alerts']:
                summary += f"  [{alert['type'].upper()}] {alert['message']}\n"
        
        return summary


# Global proxy monitor instance
_proxy_monitor: Optional[ProxyMonitor] = None


def get_proxy_monitor() -> ProxyMonitor:
    """Get the global proxy monitor instance"""
    global _proxy_monitor
    
    if _proxy_monitor is None:
        _proxy_monitor = ProxyMonitor()
    
    return _proxy_monitor
