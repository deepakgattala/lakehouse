from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import intelligence, auth, dashboard, settings as settings_api, audit, monitoring, metrics, knowledge, operations, maintenance
from app.core.config import settings
app = FastAPI(title=settings.app_name, version="0.3.5")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(dashboard.router, prefix=settings.api_v1_prefix)
app.include_router(settings_api.router, prefix=settings.api_v1_prefix)
app.include_router(audit.router, prefix=settings.api_v1_prefix)
app.include_router(monitoring.router, prefix=settings.api_v1_prefix)
app.include_router(metrics.router, prefix=settings.api_v1_prefix)
app.include_router(knowledge.router, prefix=settings.api_v1_prefix)
app.include_router(operations.router, prefix=settings.api_v1_prefix)
app.include_router(maintenance.router, prefix=settings.api_v1_prefix)
@app.get("/health")
def health():
    return {"status": "healthy", "service": settings.app_name, "environment": settings.app_env}

app.include_router(intelligence.router, prefix=settings.api_v1_prefix)
