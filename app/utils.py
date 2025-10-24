"""
Utility functions for loading and processing data files
"""

import pandas as pd
import logging
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


def load_positions(filepath: str = "data/positions.csv") -> List[Dict]:
    """
    Load bond positions from CSV with validation and error handling
    
    The positions CSV should have columns:
    - cusip: Bond identifier
    - notional: Notional amount
    - pv_sod: Start-of-day present value
    - dv01_<tenor>: DV01 sensitivity for each tenor (e.g., dv01_3M, dv01_10Y)
    
    Args:
        filepath: Path to positions CSV file
        
    Returns:
        List of position dictionaries with bucketed DV01
        
    Example return format:
        [
            {
                'cusip': '912828A123',
                'notional': 10000000.0,
                'pv_sod': 9985000.0,
                'dv01_bucketed': {'3M': 250.0, '10Y': 0.0, ...},
                'pv_live': 0.0,
                'pnl': 0.0
            },
            ...
        ]
    """
    try:
        # Check if file exists
        if not Path(filepath).exists():
            logger.error(f"Positions file not found: {filepath}")
            return []
        
        # Load CSV
        df = pd.read_csv(filepath)
        
        # Validate required columns
        required_cols = ['cusip', 'notional', 'pv_sod']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            logger.error(f"Missing required columns in positions CSV: {missing_cols}")
            return []
        
        # Find DV01 columns (columns starting with 'dv01_')
        dv01_cols = [col for col in df.columns if col.startswith('dv01_')]
        
        if not dv01_cols:
            logger.warning("No DV01 columns found in positions CSV")
        
        # Convert to list of dictionaries with bucketed DV01
        positions = []
        for _, row in df.iterrows():
            try:
                # Extract DV01 sensitivities by tenor
                dv01_bucketed = {}
                for col in dv01_cols:
                    # Extract tenor from column name (e.g., 'dv01_3M' -> '3M')
                    tenor = col.replace('dv01_', '')
                    dv01_bucketed[tenor] = float(row[col])
                
                position = {
                    'cusip': str(row['cusip']),
                    'notional': float(row['notional']),
                    'pv_sod': float(row['pv_sod']),
                    'dv01_bucketed': dv01_bucketed,
                    'pv_live': 0.0,  # Will be calculated
                    'pnl': 0.0       # Will be calculated
                }
                
                positions.append(position)
                
            except (ValueError, KeyError) as e:
                logger.warning(f"Error processing position row: {e}, skipping")
                continue
        
        logger.info(f"Loaded {len(positions)} positions from {filepath}")
        
        # Log summary
        total_notional = sum(p['notional'] for p in positions)
        total_pv = sum(p['pv_sod'] for p in positions)
        logger.info(f"Total notional: ${total_notional:,.0f}, Total PV: ${total_pv:,.0f}")
        
        return positions
        
    except FileNotFoundError:
        logger.error(f"Positions file not found: {filepath}")
        return []
    except pd.errors.EmptyDataError:
        logger.error(f"Positions file is empty: {filepath}")
        return []
    except Exception as e:
        logger.error(f"Error loading positions: {e}")
        return []


def load_curve(filepath: str = "data/sod_curve.csv") -> Dict[str, float]:
    """
    Load start-of-day yield curve from CSV
    
    The curve CSV should have columns:
    - tenor: Tenor label (e.g., '3M', '1Y', '10Y')
    - yield: Yield as decimal (e.g., 0.05 for 5%)
    
    Args:
        filepath: Path to curve CSV file
        
    Returns:
        Dictionary mapping tenor to yield
        
    Example return format:
        {
            '3M': 0.0450,
            '1Y': 0.0490,
            '10Y': 0.0580,
            ...
        }
    """
    try:
        # Check if file exists
        if not Path(filepath).exists():
            logger.error(f"Curve file not found: {filepath}")
            return {}
        
        # Load CSV
        df = pd.read_csv(filepath)
        
        # Validate required columns
        if 'tenor' not in df.columns or 'yield' not in df.columns:
            logger.error(f"Curve CSV must have 'tenor' and 'yield' columns. Found: {df.columns.tolist()}")
            return {}
        
        # Convert to dictionary
        curve = {}
        for _, row in df.iterrows():
            try:
                tenor = str(row['tenor']).strip()
                yield_val = float(row['yield'])
                
                # Validate yield is reasonable (between 0% and 20%)
                if not (0.0 <= yield_val <= 0.20):
                    logger.warning(f"Unusual yield value for {tenor}: {yield_val*100:.2f}%")
                
                curve[tenor] = yield_val
                
            except (ValueError, KeyError) as e:
                logger.warning(f"Error processing curve row: {e}, skipping")
                continue
        
        if not curve:
            logger.error("No valid curve points loaded")
            return {}
        
        logger.info(f"Loaded curve with {len(curve)} tenors from {filepath}")
        
        # Log curve summary
        min_yield = min(curve.values()) * 100
        max_yield = max(curve.values()) * 100
        logger.info(f"Yield range: {min_yield:.2f}% to {max_yield:.2f}%")
        
        return curve
        
    except FileNotFoundError:
        logger.error(f"Curve file not found: {filepath}")
        return {}
    except pd.errors.EmptyDataError:
        logger.error(f"Curve file is empty: {filepath}")
        return {}
    except Exception as e:
        logger.error(f"Error loading curve: {e}")
        return {}


def compute_pnl(positions: List[Dict], delta_curve: Dict[str, float]) -> List[Dict]:
    """
    Compute PnL for each position using DV01 sensitivity
    
    PnL = sum(DV01[tenor] * Δy[tenor]) where Δy is in basis points
    
    Args:
        positions: List of position dictionaries
        delta_curve: Dictionary of yield changes by tenor in basis points
        
    Returns:
        Updated list of positions with pnl and pv_live calculated
    """
    try:
        for pos in positions:
            pnl = 0.0
            dv01_bucketed = pos.get('dv01_bucketed', {})
            
            for tenor, dv01 in dv01_bucketed.items():
                delta_bp = delta_curve.get(tenor, 0.0)
                # DV01 is dollar change per 1bp, delta_bp is change in bps
                pnl += dv01 * delta_bp
            
            pos['pnl'] = round(pnl, 2)
            pos['pv_live'] = round(pos['pv_sod'] + pnl, 2)
        
        return positions
        
    except Exception as e:
        logger.error(f"Error computing PnL: {e}")
        return positions


def aggregate_pnl(positions: List[Dict]) -> float:
    """
    Calculate total portfolio PnL
    
    Args:
        positions: List of positions with pnl calculated
        
    Returns:
        Total PnL across all positions
    """
    try:
        total = sum(pos.get('pnl', 0.0) for pos in positions)
        return round(total, 2)
    except Exception as e:
        logger.error(f"Error aggregating PnL: {e}")
        return 0.0


def validate_positions_data(positions: List[Dict]) -> bool:
    """
    Validate that positions data is properly formatted
    
    Args:
        positions: List of position dictionaries
        
    Returns:
        True if valid, False otherwise
    """
    if not positions:
        logger.warning("No positions to validate")
        return False
    
    required_fields = ['cusip', 'notional', 'pv_sod', 'dv01_bucketed']
    
    for i, pos in enumerate(positions):
        for field in required_fields:
            if field not in pos:
                logger.error(f"Position {i} missing field: {field}")
                return False
        
        if not isinstance(pos['dv01_bucketed'], dict):
            logger.error(f"Position {i} dv01_bucketed is not a dictionary")
            return False
    
    logger.info(f"Validated {len(positions)} positions successfully")
    return True


if __name__ == "__main__":
    # Test the loaders
    logging.basicConfig(level=logging.INFO)
    
    print("Testing Data Loaders")
    print("=" * 60)
    
    # Load curve
    print("\nLoading SOD curve...")
    curve = load_curve()
    if curve:
        print(f"\nLoaded {len(curve)} curve points:")
        for tenor, yield_val in curve.items():
            print(f"  {tenor:>4}: {yield_val*100:6.3f}%")
    
    # Load positions
    print("\nLoading positions...")
    positions = load_positions()
    if positions:
        print(f"\nLoaded {len(positions)} positions:")
        for pos in positions:
            active_dv01 = {k: v for k, v in pos['dv01_bucketed'].items() if v != 0}
            print(f"  {pos['cusip']}: ${pos['notional']:,.0f}, DV01: {active_dv01}")
    
    # Validate
    print("\nValidating positions data...")
    is_valid = validate_positions_data(positions)
    print(f"Validation result: {'✓ PASS' if is_valid else '✗ FAIL'}")
    
    # Test PnL calculation with sample deltas
    print("\nTesting PnL calculation with sample +5bp across all tenors...")
    sample_delta = {tenor: 5.0 for tenor in curve.keys()}
    positions = compute_pnl(positions, sample_delta)
    total_pnl = aggregate_pnl(positions)
    
    print(f"\nPnL results:")
    for pos in positions:
        print(f"  {pos['cusip']}: ${pos['pnl']:,.2f}")
    print(f"\nTotal Portfolio PnL: ${total_pnl:,.2f}")
