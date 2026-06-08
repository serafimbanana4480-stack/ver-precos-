"""
WebSocket Manager for Real-time Updates
Handles WebSocket connections for streaming vehicle updates
"""
from __future__ import annotations
import logging
import asyncio
from typing import Dict, Set
from datetime import datetime, timedelta
from fastapi import WebSocket, WebSocketDisconnect

from database.db import get_db_context
from database.models import Vehicle

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections"""
    
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Group connections by filter criteria
    
    async def connect(self, websocket: WebSocket, client_id: str):
        """Accept and register a WebSocket connection"""
        await websocket.accept()
        if client_id not in self.active_connections:
            self.active_connections[client_id] = set()
        self.active_connections[client_id].add(websocket)
        logger.info(f"WebSocket connected: {client_id} (total: {len(self.active_connections[client_id])})")
    
    def disconnect(self, websocket: WebSocket, client_id: str):
        """Remove a WebSocket connection"""
        if client_id in self.active_connections:
            self.active_connections[client_id].discard(websocket)
            if not self.active_connections[client_id]:
                del self.active_connections[client_id]
            logger.info(f"WebSocket disconnected: {client_id}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send a message to a specific WebSocket"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
    
    async def broadcast(self, message: dict, client_id: Optional[str] = None):
        """Broadcast a message to all connected clients"""
        if client_id and client_id in self.active_connections:
            for connection in self.active_connections[client_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to {client_id}: {e}")
        else:
            # Broadcast to all connections
            for client_id, connections in self.active_connections.items():
                for connection in connections:
                    try:
                        await connection.send_json(message)
                    except Exception as e:
                        logger.error(f"Error broadcasting to {client_id}: {e}")
    
    def get_connection_count(self) -> int:
        """Get total number of active connections"""
        return sum(len(conns) for conns in self.active_connections.values())


# Global connection manager
manager = ConnectionManager()


async def stream_vehicle_updates(websocket: WebSocket, client_id: str, poll_interval: int = 5):
    """
    Stream vehicle updates in real-time
    
    Args:
        websocket: WebSocket connection
        client_id: Unique client identifier
        poll_interval: Polling interval in seconds (default: 5)
    """
    await manager.connect(websocket, client_id)
    
    try:
        last_update = datetime.utcnow()
        
        while True:
            try:
                # Get new vehicles from database
                with get_db_context() as db:
                    new_vehicles = db.query(Vehicle).filter(
                        Vehicle.is_active == True,
                        Vehicle.last_seen > last_update
                    ).order_by(Vehicle.last_seen.desc()).limit(10).all()
                
                if new_vehicles:
                    # Send updates to client
                    updates = []
                    for v in new_vehicles:
                        updates.append({
                            "id": v.id,
                            "source": v.source,
                            "source_id": v.source_id,
                            "title": v.title,
                            "brand": v.brand,
                            "model": v.model,
                            "year": v.year,
                            "price": v.price,
                            "deal_score": v.deal_score,
                            "estimated_value": v.estimated_value,
                            "last_seen": v.last_seen.isoformat() if v.last_seen else None
                        })
                    
                    await manager.send_personal_message({
                        "type": "vehicle_update",
                        "count": len(updates),
                        "vehicles": updates,
                        "timestamp": datetime.utcnow().isoformat()
                    }, websocket)
                    
                    logger.info(f"Sent {len(updates)} vehicle updates to {client_id}")
                
                # Update last_seen for next poll
                last_update = datetime.utcnow()
                
                # Wait before next poll
                await asyncio.sleep(poll_interval)
                
            except WebSocketDisconnect:
                manager.disconnect(websocket, client_id)
                break
            except Exception as e:
                logger.error(f"Error streaming updates for {client_id}: {e}")
                await manager.send_personal_message({
                    "type": "error",
                    "message": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }, websocket)
                await asyncio.sleep(poll_interval)
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, client_id)
    except Exception as e:
        logger.error(f"WebSocket error for {client_id}: {e}")
        manager.disconnect(websocket, client_id)
