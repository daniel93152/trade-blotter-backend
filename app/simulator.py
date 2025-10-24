"""
Yield Curve Simulator using Nelson-Siegel Model

The Nelson-Siegel model represents the yield curve as:
y(τ) = β₀ + β₁ * [(1 - e^(-λτ)) / (λτ)] + β₂ * [(1 - e^(-λτ)) / (λτ) - e^(-λτ)]

Where:
- β₀: level (long-term interest rate)
- β₁: slope (short-term component)
- β₂: curvature (medium-term component)
- λ: decay parameter (controls where curvature peaks)
- τ: time to maturity in years
"""

import numpy as np
from typing import Dict, List, Tuple
import logging

logger = logging.getLogger(__name__)


class CurveSimulator:
    """Simulates yield curve evolution using Nelson-Siegel model with drift"""
    
    # Tenor mapping to years
    TENOR_MAP = {
        '3M': 0.25,
        '6M': 0.5,
        '1Y': 1.0,
        '2Y': 2.0,
        '5Y': 5.0,
        '10Y': 10.0,
        '30Y': 30.0
    }
    
    def __init__(
        self, 
        beta0: float = 0.05, 
        beta1: float = -0.02, 
        beta2: float = 0.01, 
        lambda_param: float = 0.5
    ):
        """
        Initialize the curve simulator with Nelson-Siegel parameters
        
        Args:
            beta0: Level parameter (long-term rate)
            beta1: Slope parameter (short-term component)
            beta2: Curvature parameter (medium-term component)
            lambda_param: Decay parameter (controls curvature peak)
        """
        self.beta0 = beta0
        self.beta1 = beta1
        self.beta2 = beta2
        self.lambda_param = lambda_param
        
        # Store start-of-day parameters for delta calculation
        self.sod_params = (beta0, beta1, beta2)
        
        logger.info(
            f"CurveSimulator initialized: β₀={beta0:.4f}, β₁={beta1:.4f}, "
            f"β₂={beta2:.4f}, λ={lambda_param:.4f}"
        )
    
    def nelson_siegel(self, tenor_years: float) -> float:
        """
        Calculate yield for a given tenor using Nelson-Siegel formula
        
        Args:
            tenor_years: Time to maturity in years
            
        Returns:
            Yield as a decimal (e.g., 0.05 for 5%)
        """
        t = tenor_years
        lam = self.lambda_param
        
        # Avoid division by zero
        if t < 1e-10:
            return self.beta0 + self.beta1
        
        # Nelson-Siegel formula components
        factor1 = (1 - np.exp(-lam * t)) / (lam * t)
        factor2 = factor1 - np.exp(-lam * t)
        
        yield_value = self.beta0 + self.beta1 * factor1 + self.beta2 * factor2
        
        return yield_value
    
    def apply_drift(self, volatility: float = 0.0001):
        """
        Apply random drift to Nelson-Siegel parameters
        
        This simulates market movement by adding small random changes
        to the curve parameters.
        
        Args:
            volatility: Standard deviation of the random drift
        """
        # Add random normal drift to each parameter
        self.beta0 += np.random.normal(0, volatility)
        self.beta1 += np.random.normal(0, volatility)
        self.beta2 += np.random.normal(0, volatility)
        
        logger.debug(
            f"Applied drift: β₀={self.beta0:.4f}, β₁={self.beta1:.4f}, "
            f"β₂={self.beta2:.4f}"
        )
    
    def get_curve(self, tenors: List[str] = None) -> Dict[str, float]:
        """
        Generate current yield curve for standard tenors
        
        Args:
            tenors: List of tenor strings (e.g., ['3M', '1Y', '10Y'])
                   If None, uses all standard tenors
                   
        Returns:
            Dictionary mapping tenor to yield (as decimal)
        """
        if tenors is None:
            tenors = list(self.TENOR_MAP.keys())
        
        curve = {}
        for tenor in tenors:
            if tenor not in self.TENOR_MAP:
                logger.warning(f"Unknown tenor: {tenor}, skipping")
                continue
            
            tenor_years = self.TENOR_MAP[tenor]
            curve[tenor] = self.nelson_siegel(tenor_years)
        
        return curve
    
    def get_sod_curve(self, tenors: List[str] = None) -> Dict[str, float]:
        """
        Generate start-of-day yield curve using SOD parameters
        
        Args:
            tenors: List of tenor strings
                   
        Returns:
            Dictionary mapping tenor to SOD yield (as decimal)
        """
        if tenors is None:
            tenors = list(self.TENOR_MAP.keys())
        
        # Temporarily use SOD parameters
        beta0_sod, beta1_sod, beta2_sod = self.sod_params
        beta0_current, beta1_current, beta2_current = self.beta0, self.beta1, self.beta2
        
        self.beta0, self.beta1, self.beta2 = beta0_sod, beta1_sod, beta2_sod
        sod_curve = self.get_curve(tenors)
        self.beta0, self.beta1, self.beta2 = beta0_current, beta1_current, beta2_current
        
        return sod_curve
    
    def get_delta(self, tenors: List[str] = None) -> Dict[str, float]:
        """
        Calculate change from start-of-day in basis points
        
        Args:
            tenors: List of tenor strings
                   
        Returns:
            Dictionary mapping tenor to change in basis points (bps)
        """
        if tenors is None:
            tenors = list(self.TENOR_MAP.keys())
        
        current_curve = self.get_curve(tenors)
        sod_curve = self.get_sod_curve(tenors)
        
        # Calculate delta in basis points (1 bp = 0.0001 or 0.01%)
        delta = {
            tenor: (current_curve[tenor] - sod_curve[tenor]) * 10000
            for tenor in tenors
        }
        
        return delta
    
    def reset_to_sod(self):
        """Reset curve parameters to start-of-day values"""
        self.beta0, self.beta1, self.beta2 = self.sod_params
        logger.info("Curve reset to SOD parameters")
    
    def get_curve_summary(self) -> Dict:
        """
        Get a summary of current curve state
        
        Returns:
            Dictionary with parameters and curve points
        """
        tenors = list(self.TENOR_MAP.keys())
        current = self.get_curve(tenors)
        sod = self.get_sod_curve(tenors)
        delta = self.get_delta(tenors)
        
        return {
            'parameters': {
                'beta0': self.beta0,
                'beta1': self.beta1,
                'beta2': self.beta2,
                'lambda': self.lambda_param
            },
            'sod_parameters': {
                'beta0': self.sod_params[0],
                'beta1': self.sod_params[1],
                'beta2': self.sod_params[2]
            },
            'curves': {
                tenor: {
                    'sod': sod[tenor],
                    'current': current[tenor],
                    'delta_bp': delta[tenor]
                }
                for tenor in tenors
            }
        }


def generate_sod_curve_csv(filepath: str = "data/sod_curve.csv"):
    """
    Generate and save a start-of-day yield curve to CSV
    
    Args:
        filepath: Path to save the CSV file
    """
    import pandas as pd
    
    # Create simulator with reasonable parameters
    simulator = CurveSimulator(
        beta0=0.055,    # 5.5% long-term rate
        beta1=-0.015,   # Slight downward slope
        beta2=0.008,    # Small curvature
        lambda_param=0.6
    )
    
    # Generate curve
    curve = simulator.get_curve()
    
    # Create DataFrame
    df = pd.DataFrame([
        {'tenor': tenor, 'yield': yield_val}
        for tenor, yield_val in curve.items()
    ])
    
    # Save to CSV
    df.to_csv(filepath, index=False)
    logger.info(f"Generated SOD curve and saved to {filepath}")
    
    return df


if __name__ == "__main__":
    # Test the simulator
    logging.basicConfig(level=logging.INFO)
    
    print("Testing Nelson-Siegel Curve Simulator\n")
    print("=" * 60)
    
    # Create simulator
    sim = CurveSimulator()
    
    # Get initial curve
    print("\nInitial Curve:")
    curve = sim.get_curve()
    for tenor, yield_val in curve.items():
        print(f"  {tenor:>4}: {yield_val*100:6.3f}% ({yield_val:.6f})")
    
    # Apply drift
    print("\nApplying drift 10 times...")
    for i in range(10):
        sim.apply_drift(volatility=0.0002)
    
    # Get new curve and delta
    print("\nCurve after drift:")
    new_curve = sim.get_curve()
    delta = sim.get_delta()
    for tenor in curve.keys():
        print(f"  {tenor:>4}: {new_curve[tenor]*100:6.3f}% (Δ {delta[tenor]:+6.2f} bps)")
    
    # Generate CSV
    print("\n" + "=" * 60)
    print("\nGenerating SOD curve CSV...")
    df = generate_sod_curve_csv()
    print("\nGenerated curve:")
    print(df.to_string(index=False))
