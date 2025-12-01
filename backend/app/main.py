"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import app as app_router
from .routers import fw as fw_router
from .routers import quickset as quickset_router
from .routers import sessions as sessions_router

app = FastAPI(title="QA Automation Backend", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["infra"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


api_prefix = "/api"
app.include_router(fw_router.router, prefix=api_prefix)
app.include_router(app_router.router, prefix=api_prefix)
app.include_router(sessions_router.router, prefix=api_prefix)
app.include_router(quickset_router.router, prefix=api_prefix)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
