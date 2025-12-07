from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import app as app_router
from .routers import quickset as quickset_router
from .routers import sessions as sessions_router
from .routers import timeline as timeline_router
from .routers import fw as fw_router
from .routers import debug_quickset as debug_quickset_router


app = FastAPI(
    title="QA Automation Backend",
    version="0.1.0",
    description="Backend for QA Automation UI: apps, QuickSet runs, timelines and analyzers.",
)

# =========================
# CORS
# =========================
allowed_origins = [
    "http://localhost:5174",
    "http://127.0.0.1:5174",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# Routers registration
# (no prefixes added here)
# =========================
app.include_router(app_router.router, prefix="/api")
app.include_router(quickset_router.router, prefix="/api")
app.include_router(sessions_router.router, prefix="/api")
app.include_router(timeline_router.router, prefix="/api")
app.include_router(fw_router.router, prefix="/api")
app.include_router(debug_quickset_router.router, prefix="/api")

# =========================
# Health endpoint
# =========================
@app.get("/health")
def health():
    return {"status": "ok"}
