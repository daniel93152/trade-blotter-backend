from fastapi import FastAPI
import logging

from app.models import HealthResponse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

app = FastAPI(title="Trade Blotter API", version="1.0.0")

@app.get("/api/v1/health", response_model=HealthResponse)
async def health():
    return {"status": "ok"}
