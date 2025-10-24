"""
WebSocket Streaming Router

Provides real-time streaming of market data (curve, positions, PnL)
via WebSocket connections. Data is pushed from the server every 0.5 seconds.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Set
import asyncio
import logging
import json

from app.state import market_state

logger = logging.getLogger(__name__)

router = APIRouter()

# Track connected WebSocket clients
active_connections: Set[WebSocket] = set()


@router.websocket("/ws/stream")
async def stream_market_data(websocket: WebSocket):
    """
    WebSocket endpoint for streaming market data
    
    Accepts WebSocket connections and continuously streams:
    - Yield curve (current, SOD, deltas)
    - Positions with live PnL
    - Aggregated PnL summary
    - Timestamp of last update
    
    Data is pushed every 0.5 seconds to match the backend update frequency.
    """
    await websocket.accept()
    active_connections.add(websocket)
    
    client_id = id(websocket)
    logger.info(f"WebSocket client connected: {client_id} (total clients: {len(active_connections)})")
    
    try:
        # Define tenors for curve data
        tenors = ['3M', '6M', '1Y', '2Y', '5Y', '10Y', '30Y']
        
        while True:
            try:
                # Get full market snapshot from shared state
                snapshot = market_state.get_full_snapshot(tenors)
                
                # Send to client
                await websocket.send_json(snapshot)
                
                # Wait 0.5 seconds before next update
                await asyncio.sleep(0.5)
                
            except WebSocketDisconnect:
                logger.info(f"WebSocket client disconnected normally: {client_id}")
                break
            except Exception as e:
                logger.error(f"Error sending data to client {client_id}: {e}", exc_info=True)
                break
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: {client_id}")
    except Exception as e:
        logger.error(f"WebSocket error for client {client_id}: {e}", exc_info=True)
    finally:
        # Clean up connection
        if websocket in active_connections:
            active_connections.remove(websocket)
        logger.info(f"WebSocket client removed: {client_id} (remaining clients: {len(active_connections)})")


async def broadcast_to_all(data: dict):
    """
    Broadcast data to all connected clients
    
    This function can be used for targeted broadcasts triggered by events.
    Currently, each client has its own update loop, but this is available
    for future use cases where broadcast is needed.
    
    Args:
        data: Dictionary to broadcast as JSON
    """
    if not active_connections:
        return
    
    # Create list copy to avoid modification during iteration
    connections = list(active_connections)
    
    for websocket in connections:
        try:
            await websocket.send_json(data)
        except Exception as e:
            logger.error(f"Error broadcasting to client: {e}")
            # Remove failed connection
            if websocket in active_connections:
                active_connections.remove(websocket)


def get_connection_count() -> int:
    """
    Get the number of active WebSocket connections
    
    Returns:
        Number of active connections
    """
    return len(active_connections)
