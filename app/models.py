from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class CurvePoint(BaseModel):
    """Represents a single point on the yield curve"""
    tenor: str = Field(..., description="Tenor label (e.g., '3M', '1Y', '10Y')")
    sod_yield: float = Field(..., description="Start-of-day yield")
    live_yield: float = Field(..., description="Current live yield")
    delta_bp: float = Field(..., description="Change from SOD in basis points")

    class Config:
        json_schema_extra = {
            "example": {
                "tenor": "10Y",
                "sod_yield": 0.0580,
                "live_yield": 0.0585,
                "delta_bp": 5.0
            }
        }


class Position(BaseModel):
    """Represents a bond position with DV01 sensitivities"""
    cusip: str = Field(..., description="Bond CUSIP identifier")
    notional: float = Field(..., description="Notional amount")
    pv_sod: float = Field(..., description="Start-of-day present value")
    dv01_bucketed: Dict[str, float] = Field(
        ..., 
        description="DV01 sensitivity by tenor bucket"
    )
    pv_live: float = Field(0.0, description="Current live present value")
    pnl: float = Field(0.0, description="Profit and loss")

    class Config:
        json_schema_extra = {
            "example": {
                "cusip": "912828A123",
                "notional": 10000000,
                "pv_sod": 9985000,
                "dv01_bucketed": {
                    "3M": 250.0,
                    "10Y": 0.0
                },
                "pv_live": 9986250,
                "pnl": 1250.0
            }
        }


class PnLResponse(BaseModel):
    """Response model for PnL calculation endpoint"""
    total_pnl: float = Field(..., description="Total portfolio PnL")
    positions: List[Position] = Field(..., description="List of positions with PnL")
    timestamp: Optional[str] = Field(None, description="Calculation timestamp")

    class Config:
        json_schema_extra = {
            "example": {
                "total_pnl": 25000.50,
                "positions": [
                    {
                        "cusip": "912828A123",
                        "notional": 10000000,
                        "pv_sod": 9985000,
                        "dv01_bucketed": {"3M": 250.0},
                        "pv_live": 9986250,
                        "pnl": 1250.0
                    }
                ],
                "timestamp": "2025-10-24T16:50:00Z"
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Service status")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "ok"
            }
        }
