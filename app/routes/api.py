"""
API Routes for Trade Blotter
"""

from fastapi import APIRouter, HTTPException
from typing import List
from datetime import datetime
import logging

from app.models import CurvePoint, Position, PnLResponse

logger = logging.getLogger(__name__)

router = APIRouter()

# Global state (will be initialized at startup)
curve_simulator = None
current_positions = []
sod_curve = {}


@router.get("/curve", response_model=List[CurvePoint])
async def get_curve():
    """
    Get current yield curve with SOD comparison
    
    Returns curve points showing:
    - Start-of-day yields
    - Current live yields
    - Delta in basis points
    """
    try:
        if curve_simulator is None:
            raise HTTPException(status_code=500, detail="Curve simulator not initialized")
        
        tenors = ['3M', '6M', '1Y', '2Y', '5Y', '10Y', '30Y']
        
        # Get current and SOD curves
        current_curve = curve_simulator.get_curve(tenors)
        sod_curve_data = curve_simulator.get_sod_curve(tenors)
        delta_curve = curve_simulator.get_delta(tenors)
        
        # Build response
        curve_points = []
        for tenor in tenors:
            curve_points.append({
                'tenor': tenor,
                'sod_yield': sod_curve_data[tenor],
                'live_yield': current_curve[tenor],
                'delta_bp': delta_curve[tenor]
            })
        
        return curve_points
        
    except Exception as e:
        logger.error(f"Error getting curve: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions", response_model=List[Position])
async def get_positions():
    """
    Get all bond positions with current PnL
    
    Returns positions with:
    - CUSIP and notional
    - Start-of-day PV
    - Bucketed DV01 sensitivities
    - Current live PV
    - Current PnL
    """
    try:
        if not current_positions:
            raise HTTPException(status_code=500, detail="Positions not loaded")
        
        return current_positions
        
    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pnl", response_model=PnLResponse)
async def get_pnl():
    """
    Get comprehensive PnL report
    
    Returns:
    - Total portfolio PnL
    - All positions with individual PnL
    - Timestamp of calculation
    """
    try:
        if not current_positions:
            raise HTTPException(status_code=500, detail="Positions not loaded")
        
        # Calculate total PnL
        from app.utils import aggregate_pnl
        total_pnl = aggregate_pnl(current_positions)
        
        return {
            'total_pnl': total_pnl,
            'positions': current_positions,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        
    except Exception as e:
        logger.error(f"Error calculating PnL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset")
async def reset_curve():
    """
    Reset yield curve to start-of-day values
    
    This will:
    - Reset curve parameters to SOD
    - Recalculate all positions with zero deltas
    - Return updated PnL (should be zero)
    """
    try:
        if curve_simulator is None:
            raise HTTPException(status_code=500, detail="Curve simulator not initialized")
        
        # Reset curve
        curve_simulator.reset_to_sod()
        
        # Recalculate PnL (should be zero)
        from app.utils import compute_pnl
        tenors = ['3M', '6M', '1Y', '2Y', '5Y', '10Y', '30Y']
        delta_curve = curve_simulator.get_delta(tenors)
        
        global current_positions
        current_positions = compute_pnl(current_positions, delta_curve)
        
        logger.info("Curve reset to SOD, PnL recalculated")
        
        return {
            "status": "success",
            "message": "Curve reset to start-of-day",
            "timestamp": datetime.utcnow().isoformat() + 'Z'
        }
        
    except Exception as e:
        logger.error(f"Error resetting curve: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_summary():
    """
    Get a comprehensive summary of system state
    
    Returns:
    - Curve parameters
    - Position count and totals
    - Total PnL
    - Timestamp
    """
    try:
        if curve_simulator is None or not current_positions:
            raise HTTPException(status_code=500, detail="System not initialized")
        
        from app.utils import aggregate_pnl
        
        summary = curve_simulator.get_curve_summary()
        total_pnl = aggregate_pnl(current_positions)
        total_notional = sum(p['notional'] for p in current_positions)
        total_pv_sod = sum(p['pv_sod'] for p in current_positions)
        total_pv_live = sum(p['pv_live'] for p in current_positions)
        
        return {
            'curve_parameters': summary['parameters'],
            'sod_curve_parameters': summary['sod_parameters'],
            'position_count': len(current_positions),
            'total_notional': total_notional,
            'total_pv_sod': total_pv_sod,
            'total_pv_live': total_pv_live,
            'total_pnl': total_pnl,
            'timestamp': datetime.utcnow().isoformat() + 'Z'
        }
        
    except Exception as e:
        logger.error(f"Error getting summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))
