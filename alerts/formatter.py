"""
Alert formatter for AutoDeal IA Hunter.
"""
from typing import Dict, Any


class AlertFormatter:
    """Formatter for alert messages."""
    
    @staticmethod
    def format_deal_found(deal: Dict[str, Any]) -> str:
        """Format deal found alert."""
        return f"""
🚗 **New Deal Found!**

**Vehicle:** {deal.get('brand')} {deal.get('model')}
**Price:** €{deal.get('price')}
**Deal Score:** {deal.get('deal_score')}/10
**Profit Potential:** €{deal.get('profit_potential')}
**Location:** {deal.get('location')}
**Source:** {deal.get('source')}
**URL:** {deal.get('url')}
"""
    
    @staticmethod
    def format_error(error: Dict[str, Any]) -> str:
        """Format error alert."""
        return f"""
❌ **Error Occurred**

**Type:** {error.get('type')}
**Message:** {error.get('message')}
**Component:** {error.get('component')}
**Timestamp:** {error.get('timestamp')}
"""
    
    @staticmethod
    def format_scraping_complete(summary: Dict[str, Any]) -> str:
        """Format scraping complete alert."""
        return f"""
✅ **Scraping Complete**

**Source:** {summary.get('source')}
**Listings Found:** {summary.get('listings_count')}
**Success Rate:** {summary.get('success_rate')}%
**Duration:** {summary.get('duration')}s
**Timestamp:** {summary.get('timestamp')}
"""
