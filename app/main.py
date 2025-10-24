from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
import logging

from app.models import HealthResponse
from app.routes import api
from app.simulator import CurveSimulator
from app.utils import load_positions, load_curve, compute_pnl

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


async def update_curve_task():
    """
    Background task to drift curve every 0.5 seconds
    
    This task runs continuously, applying random drifts to selected
    yield curve buckets (not all at once) and recalculating PnL.
    """
    logger.info("Starting background curve update task (0.5s interval)...")
    
    while True:
        try:
            await asyncio.sleep(0.5)
            
            if api.curve_simulator is None or not api.current_positions:
                logger.warning("Simulator or positions not initialized, skipping update")
                continue
            
            # Apply drift to random buckets (not all tenors at once)
            api.curve_simulator.apply_random_bucket_drift(volatility=0.0002)
            
            # Recalculate PnL
            tenors = ['3M', '6M', '1Y', '2Y', '5Y', '10Y', '30Y']
            delta_curve = api.curve_simulator.get_delta(tenors)
            api.current_positions = compute_pnl(api.current_positions, delta_curve)
            
            # Log summary
            from app.utils import aggregate_pnl
            total_pnl = aggregate_pnl(api.current_positions)
            max_delta = max(abs(d) for d in delta_curve.values())
            
            logger.info(f"Curve updated - Max delta: {max_delta:+.2f}bp, Total PnL: ${total_pnl:,.2f}")
            
        except asyncio.CancelledError:
            logger.info("Background curve update task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in background update: {e}", exc_info=True)
            # Continue running even if there's an error
            await asyncio.sleep(0.5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager
    
    Handles startup and shutdown events:
    - Startup: Initialize simulator, load data, start background task
    - Shutdown: Cancel background task and cleanup
    """
    # Startup
    logger.info("=" * 60)
    logger.info("Starting Trade Blotter API...")
    logger.info("=" * 60)
    
    try:
        # Initialize curve simulator
        logger.info("Initializing curve simulator...")
        curve_sim = CurveSimulator(
            beta0=0.055,
            beta1=-0.015,
            beta2=0.008,
            lambda_param=0.6
        )
        
        # Load positions
        logger.info("Loading positions...")
        positions = load_positions()
        
        if not positions:
            logger.warning("No positions loaded!")
        else:
            logger.info(f"Loaded {len(positions)} positions")
        
        # Calculate initial PnL (should be zero at SOD)
        tenors = ['3M', '6M', '1Y', '2Y', '5Y', '10Y', '30Y']
        delta_curve = curve_sim.get_delta(tenors)
        positions = compute_pnl(positions, delta_curve)
        
        # Set global state in api module
        api.curve_simulator = curve_sim
        api.current_positions = positions
        
        # Start background task
        logger.info("Starting background curve drift task (updates every 2 seconds)...")
        task = asyncio.create_task(update_curve_task())
        
        logger.info("=" * 60)
        logger.info("Trade Blotter API started successfully!")
        logger.info(f"API documentation: http://localhost:8000/docs")
        logger.info(f"Health check: http://localhost:8000/api/v1/health")
        logger.info("=" * 60)
        
        yield
        
        # Shutdown
        logger.info("=" * 60)
        logger.info("Shutting down Trade Blotter API...")
        logger.info("=" * 60)
        
        # Cancel background task
        logger.info("Cancelling background task...")
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            logger.info("Background task cancelled successfully")
        
        logger.info("Trade Blotter API shutdown complete")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Error during application lifecycle: {e}", exc_info=True)
        raise


app = FastAPI(
    title="Trade Blotter API",
    version="1.0.0",
    description="Real-time trade blotter with yield curve simulation and PnL tracking",
    lifespan=lifespan
)

# CORS configuration for React/Vite frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React default
        "http://localhost:5173",  # Vite default
        "http://localhost:5174",  # Vite alternative
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api.router, prefix="/api/v1", tags=["Trade Blotter"])


@app.get("/api/v1/health", response_model=HealthResponse)
async def health():
    """Health check endpoint"""
    return {"status": "ok"}
