"""
Elasticsearch integration for vehicle search
Based on Obsidian Vault documentation for Hub - Search
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from config import settings

try:
    from elasticsearch import Elasticsearch
    from elasticsearch.helpers import bulk
    ELASTICSEARCH_AVAILABLE = True
except ImportError:
    ELASTICSEARCH_AVAILABLE = False
    logging.warning("Elasticsearch not installed. Install with: pip install elasticsearch")

logger = logging.getLogger(__name__)


class ElasticsearchClient:
    """Elasticsearch client for vehicle search"""
    
    def __init__(
        self,
        hosts: Optional[List[str]] = None,
        index_name: str = "vehicles"
    ):
        if not ELASTICSEARCH_AVAILABLE:
            raise ImportError("Elasticsearch not installed")
        
        self.hosts = hosts or ["http://localhost:9200"]
        self.index_name = index_name
        self.client = Elasticsearch(self.hosts)
        
        self._create_index_if_not_exists()
    
    def _create_index_if_not_exists(self):
        """Create index with mapping if it doesn't exist"""
        if not self.client.indices.exists(index=self.index_name):
            mapping = {
                "mappings": {
                    "properties": {
                        "id": {"type": "integer"},
                        "source": {"type": "keyword"},
                        "source_id": {"type": "keyword"},
                        "url": {"type": "text", "index": False},
                        "vehicle_type": {"type": "keyword"},
                        "brand": {"type": "keyword"},
                        "model": {"type": "keyword"},
                        "version": {"type": "text"},
                        "year": {"type": "integer"},
                        "km": {"type": "integer"},
                        "price": {"type": "float"},
                        "location": {"type": "keyword"},
                        "district": {"type": "keyword"},
                        "fuel_type": {"type": "keyword"},
                        "transmission": {"type": "keyword"},
                        "title": {"type": "text", "analyzer": "standard"},
                        "description": {"type": "text", "analyzer": "standard"},
                        "deal_score": {"type": "float"},
                        "profit_potential": {"type": "float"},
                        "condition_score": {"type": "float"},
                        "first_seen": {"type": "date"},
                        "last_seen": {"type": "date"},
                        "is_active": {"type": "boolean"}
                    }
                },
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 1
                }
            }
            
            self.client.indices.create(index=self.index_name, body=mapping)
            logger.info(f"Created Elasticsearch index: {self.index_name}")
    
    def index_vehicle(self, vehicle: Dict[str, Any]) -> bool:
        """
        Index a single vehicle
        
        Args:
            vehicle: Vehicle dictionary
            
        Returns:
            True if successful
        """
        try:
            doc_id = f"{vehicle['source']}_{vehicle['source_id']}"
            self.client.index(
                index=self.index_name,
                id=doc_id,
                body=vehicle
            )
            return True
        except Exception as e:
            logger.error(f"Error indexing vehicle: {e}")
            return False
    
    def bulk_index_vehicles(self, vehicles: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Bulk index multiple vehicles
        
        Args:
            vehicles: List of vehicle dictionaries
            
        Returns:
            Dictionary with success/error counts
        """
        actions = []
        for vehicle in vehicles:
            doc_id = f"{vehicle['source']}_{vehicle['source_id']}"
            actions.append({
                "_index": self.index_name,
                "_id": doc_id,
                "_source": vehicle
            })
        
        try:
            success, failed = bulk(self.client, actions)
            logger.info(f"Bulk indexed {success} vehicles, {failed} failed")
            return {"success": success, "failed": failed}
        except Exception as e:
            logger.error(f"Bulk index failed: {e}")
            return {"success": 0, "failed": len(vehicles)}
    
    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        size: int = 20,
        from_: int = 0,
        sort: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Search vehicles with query and filters
        
        Args:
            query: Search query string
            filters: Dictionary of field filters
            size: Number of results
            from_: Offset for pagination
            sort: List of sort fields (e.g., ["price:asc", "deal_score:desc"])
            
        Returns:
            Search results
        """
        try:
            # Build query
            query_body = {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "multi_match": {
                                    "query": query,
                                    "fields": ["title^2", "description", "brand^3", "model^3"],
                                    "fuzziness": "AUTO"
                                }
                            }
                        ],
                        "filter": [
                            {"term": {"is_active": True}}
                        ]
                    }
                }
            }
            
            # Add filters
            if filters:
                for field, value in filters.items():
                    if isinstance(value, list):
                        query_body["query"]["bool"]["filter"].append({"terms": {field: value}})
                    elif isinstance(value, dict):
                        # Range filter
                        if "min" in value or "max" in value:
                            range_query = {}
                            if "min" in value:
                                range_query["gte"] = value["min"]
                            if "max" in value:
                                range_query["lte"] = value["max"]
                            query_body["query"]["bool"]["filter"].append({"range": {field: range_query}})
                    else:
                        query_body["query"]["bool"]["filter"].append({"term": {field: value}})
            
            # Add sorting
            if sort:
                query_body["sort"] = sort
            else:
                query_body["sort"] = [{"deal_score": {"order": "desc"}}, "_score"]
            
            # Execute search
            response = self.client.search(
                index=self.index_name,
                body=query_body,
                size=size,
                from_=from_
            )
            
            return {
                "total": response["hits"]["total"]["value"],
                "results": [hit["_source"] for hit in response["hits"]["hits"]],
                "max_score": response["hits"]["max_score"]
            }
            
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return {"total": 0, "results": [], "max_score": 0}
    
    def delete_vehicle(self, source: str, source_id: str) -> bool:
        """
        Delete a vehicle from index
        
        Args:
            source: Vehicle source
            source_id: Source vehicle ID
            
        Returns:
            True if successful
        """
        try:
            doc_id = f"{source}_{source_id}"
            self.client.delete(index=self.index_name, id=doc_id)
            return True
        except Exception as e:
            logger.error(f"Error deleting vehicle: {e}")
            return False
    
    def update_vehicle(self, source: str, source_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update a vehicle in index
        
        Args:
            source: Vehicle source
            source_id: Source vehicle ID
            updates: Dictionary of fields to update
            
        Returns:
            True if successful
        """
        try:
            doc_id = f"{source}_{source_id}"
            self.client.update(
                index=self.index_name,
                id=doc_id,
                body={"doc": updates}
            )
            return True
        except Exception as e:
            logger.error(f"Error updating vehicle: {e}")
            return False
    
    def get_aggregations(
        self,
        field: str,
        query: str = "*",
        size: int = 10
    ) -> Dict[str, Any]:
        """
        Get aggregations for a field
        
        Args:
            field: Field to aggregate
            query: Search query
            size: Number of aggregation buckets
            
        Returns:
            Aggregation results
        """
        try:
            query_body = {
                "query": {
                    "query_string": {
                        "query": query
                    }
                },
                "aggs": {
                    f"{field}_agg": {
                        "terms": {
                            "field": field,
                            "size": size
                        }
                    }
                },
                "size": 0
            }
            
            response = self.client.search(index=self.index_name, body=query_body)
            agg = response["aggregations"][f"{field}_agg"]
            
            return {
                "field": field,
                "buckets": [{"key": bucket["key"], "count": bucket["doc_count"]} for bucket in agg["buckets"]]
            }
            
        except Exception as e:
            logger.error(f"Aggregation failed: {e}")
            return {"field": field, "buckets": []}
    
    def health_check(self) -> bool:
        """Check Elasticsearch cluster health"""
        try:
            health = self.client.cluster.health()
            return health["status"] in ["yellow", "green"]
        except Exception as e:
            logger.error(f"Elasticsearch health check failed: {e}")
            return False


if __name__ == "__main__":
    # Test Elasticsearch client
    try:
        client = ElasticsearchClient()
        print(f"Elasticsearch client initialized")
        print(f"Health: {client.health_check()}")
    except ImportError:
        print("Elasticsearch not installed")
