from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.events import router as events_router
from app.api.predict import router as predict_router
app = FastAPI(
    title="NIDS API",
    description="Network Intrusion Detection System",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
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


@app.get("/api/model")
def model_contract():
    from app.services.predictor import model_info

    return model_info()