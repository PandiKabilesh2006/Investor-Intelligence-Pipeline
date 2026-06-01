import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.investors import router as investors_router
from app.api.operations import router as operations_router
from app.api.pipeline import router as pipeline_router
from app.api.search import router as search_router
from app.config.settings import CORS_ORIGINS


app = FastAPI(
    title="Investor Intelligence Pipeline",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(investors_router)
app.include_router(operations_router)
app.include_router(search_router)
app.include_router(pipeline_router)

COMPAT_ROUTES_ENABLED = os.getenv("ENABLE_COMPAT_ROUTES", "true").lower() in {
    "1",
    "true",
    "yes",
}

if COMPAT_ROUTES_ENABLED:
    from app.api.compat import router as compat_router

    app.include_router(compat_router)


@app.get("/")
def home():
    return {
        "message": "Investor Intelligence Pipeline Running"
    }


@app.get("/health")
def legacy_health():
    return {
        "status": "healthy"
    }


@app.get("/debug/routes")
def debug_routes():
    return {
        "compat_routes_enabled": COMPAT_ROUTES_ENABLED,
        "enable_compat_routes_env": os.getenv("ENABLE_COMPAT_ROUTES"),
        "routes": sorted(
            [
                route.path
                for route in app.routes
                if hasattr(route, "path")
            ]
        ),
    }
