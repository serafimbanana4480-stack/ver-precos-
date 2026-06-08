"""
Search analytics and metrics
Based on Obsidian Vault documentation for Hub - Search
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class SearchAnalytics:
    """Track and analyze search patterns"""
    
    def __init__(self):
        self.search_history = []
        self.query_counts = defaultdict(int)
        self.filter_usage = defaultdict(int)
        self.zero_result_queries = []
    
    def log_search(
        self,
        query: str,
        results_count: int,
        filters: Optional[Dict[str, Any]] = None,
        execution_time: Optional[float] = None
    ):
        """
        Log a search event
        
        Args:
            query: Search query
            results_count: Number of results returned
            filters: Filters used
            execution_time: Query execution time in seconds
        """
        event = {
            'query': query,
            'results_count': results_count,
            'filters': filters or {},
            'execution_time': execution_time,
            'timestamp': datetime.now()
        }
        
        self.search_history.append(event)
        self.query_counts[query.lower()] += 1
        
        # Track zero results
        if results_count == 0:
            self.zero_result_queries.append(event)
        
        # Track filter usage
        if filters:
            for key in filters.keys():
                self.filter_usage[key] += 1
        
        logger.debug(f"Logged search: {query} -> {results_count} results")
    
    def get_popular_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get most popular search queries
        
        Args:
            limit: Number of queries to return
            
        Returns:
            List of popular queries with counts
        """
        sorted_queries = sorted(
            self.query_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        return [
            {'query': query, 'count': count}
            for query, count in sorted_queries[:limit]
        ]
    
    def get_zero_result_queries(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get queries that returned zero results
        
        Args:
            limit: Number of queries to return
            
        Returns:
            List of zero-result queries
        """
        return self.zero_result_queries[-limit:]
    
    def get_filter_usage_stats(self) -> Dict[str, int]:
        """Get statistics on filter usage"""
        return dict(self.filter_usage)
    
    def get_average_results_per_query(self) -> float:
        """Calculate average number of results per query"""
        if not self.search_history:
            return 0.0
        
        total_results = sum(event['results_count'] for event in self.search_history)
        return total_results / len(self.search_history)
    
    def get_average_execution_time(self) -> float:
        """Calculate average query execution time"""
        execution_times = [
            event['execution_time']
            for event in self.search_history
            if event['execution_time'] is not None
        ]
        
        if not execution_times:
            return 0.0
        
        return sum(execution_times) / len(execution_times)
    
    def get_search_volume_over_time(
        self,
        hours: int = 24
    ) -> Dict[str, int]:
        """
        Get search volume over time
        
        Args:
            hours: Number of hours to look back
            
        Returns:
            Dictionary with hourly search counts
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        recent_searches = [
            event for event in self.search_history
            if event['timestamp'] >= cutoff
        ]
        
        hourly_counts = defaultdict(int)
        for event in recent_searches:
            hour_key = event['timestamp'].strftime("%Y-%m-%d %H:00")
            hourly_counts[hour_key] += 1
        
        return dict(hourly_counts)
    
    def get_query_suggestions(self, partial_query: str, limit: int = 5) -> List[str]:
        """
        Get query suggestions based on search history
        
        Args:
            partial_query: Partial query to match
            limit: Number of suggestions
            
        Returns:
            List of suggested queries
        """
        partial_lower = partial_query.lower()
        matching_queries = [
            query for query in self.query_counts.keys()
            if partial_lower in query
        ]
        
        # Sort by frequency
        sorted_matches = sorted(
            matching_queries,
            key=lambda x: self.query_counts[x],
            reverse=True
        )
        
        return sorted_matches[:limit]
    
    def generate_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive search analytics report
        
        Returns:
            Analytics report
        """
        return {
            'total_searches': len(self.search_history),
            'unique_queries': len(self.query_counts),
            'popular_queries': self.get_popular_queries(10),
            'zero_result_queries': len(self.zero_result_queries),
            'top_zero_result_queries': self.get_zero_result_queries(10),
            'average_results': self.get_average_results_per_query(),
            'average_execution_time': self.get_average_execution_time(),
            'filter_usage': self.get_filter_usage_stats(),
            'search_volume_24h': self.get_search_volume_over_time(24)
        }
    
    def clear_old_history(self, days: int = 30):
        """
        Clear search history older than specified days
        
        Args:
            days: Number of days to keep
        """
        cutoff = datetime.now() - timedelta(days=days)
        self.search_history = [
            event for event in self.search_history
            if event['timestamp'] >= cutoff
        ]
        
        logger.info(f"Cleared search history older than {days} days")


# Global analytics instance
search_analytics = SearchAnalytics()


if __name__ == "__main__":
    # Test search analytics
    analytics = SearchAnalytics()
    
    # Log some test searches
    analytics.log_search("golf diesel", 15, {"fuel_type": "diesel"}, 0.5)
    analytics.log_search("polo gasolina", 8, {"fuel_type": "gasolina"}, 0.3)
    analytics.log_search("golf diesel", 15, {"fuel_type": "diesel"}, 0.4)
    analytics.log_search("passat", 0, {}, 0.6)
    analytics.log_search("focus", 12, {}, 0.4)
    
    # Generate report
    report = analytics.generate_report()
    print("Search Analytics Report:")
    print(f"Total searches: {report['total_searches']}")
    print(f"Unique queries: {report['unique_queries']}")
    print(f"Popular queries: {report['popular_queries']}")
    print(f"Zero result queries: {report['zero_result_queries']}")
    print(f"Average results: {report['average_results']:.2f}")
