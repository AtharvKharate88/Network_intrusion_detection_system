from fastapi import FastAPI

from app.api.events import router as events_router
from app.api.predict import router as predict_router
app = FastAPI(
    title="NIDS API",
    description="Network Intrusion Detection System",
    version="0.1.0",
)

app.include_router(events_router)
app.include_router(predict_router)

@app.get("/")
def root():
    return {
        "message": "NIDS backend is running",
        "status": "ready",
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "service": "nids-backend",
    }