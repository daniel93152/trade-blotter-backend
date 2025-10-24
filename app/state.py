"""
Shared Market State

This module provides a centralized state manager that holds the current
market data (curve, positions, PnL) which is shared between:
- Background simulation task
- REST API endpoints
- WebSocket streaming endpoint

This ensures all clients (REST and WebSocket) see consistent data.
"""

from typing import List, Dict, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class MarketState:
    """
    Centralized state manager for market data
    
    Holds current curve simulator, positions, and computed PnL data
    that is updated by the background task and consumed by API endpoints.
    """
    
    def __init__(self):
        """Initialize empty market state"""
        self.curve_simulator = None  # CurveSimulator instance
        self.current_positions: List[Dict] = []  # List of position dicts with PnL
        self.last_update: Optional[datetime] = None
        
        logger.info("MarketState initialized")
    
    def update(self, positions: List[Dict]):
        """
        Update market state with new position data
        
        Args:
            positions: List of position dictionaries with computed PnL
        """
        self.current_positions = positions
        self.last_update = datetime.utcnow()
    
    def get_curve_data(self, tenors: List[str]) -> List[Dict]:
        """
        Get current curve data with SOD comparison
        
        Args:
            tenors: List of tenor strings
            
        Returns:
            List of dicts with tenor, sod_yield, live_yield, delta_bp
        """
        if not self.curve_simulator:
            return []
        
        sod_curve = self.curve_simulator.get_sod_curve(tenors)
        live_curve = self.curve_simulator.get_curve(tenors)
        delta_curve = self.curve_simulator.get_delta(tenors)
        
        curve_data = []
        for tenor in tenors:
            curve_data.append({
                'tenor': tenor,
                'sod_yield': sod_curve[tenor],
                'live_yield': live_curve[tenor],
                'delta_bp': delta_curve[tenor]
            })
        
        return curve_data
    
    def get_positions_data(self) -> List[Dict]:
        """
        Get current positions with PnL
        
        Returns:
            List of position dictionaries
        """
        return self.current_positions
    
    def get_pnl_summary(self) -> Dict:
        """
        Get aggregated PnL summary
        
        Returns:
            Dictionary with total_pnl, total_pv_sod, total_pv_live, position_count
        """
        if not self.current_positions:
            return {
                'total_pnl': 0.0,
                'total_pv_sod': 0.0,
                'total_pv_live': 0.0,
                'position_count': 0
            }
        
        from app.utils import aggregate_pnl
        total_pnl = aggregate_pnl(self.current_positions)
        total_pv_sod = sum(pos.get('pv_sod', 0) for pos in self.current_positions)
        total_pv_live = sum(pos.get('pv_live', 0) for pos in self.current_positions)
        
        return {
            'total_pnl': total_pnl,
            'total_pv_sod': total_pv_sod,
            'total_pv_live': total_pv_live,
            'position_count': len(self.current_positions)
        }
    
    def get_full_snapshot(self, tenors: List[str]) -> Dict:
        """
        Get complete market snapshot for streaming
        
        Args:
            tenors: List of tenor strings
            
        Returns:
            Dictionary with curve, positions, pnl_summary, timestamp
        """
        return {
            'curve': self.get_curve_data(tenors),
            'positions': self.get_positions_data(),
            'pnl_summary': self.get_pnl_summary(),
            'timestamp': self.last_update.isoformat() if self.last_update else None
        }


# Global singleton instance
market_state = MarketState()
