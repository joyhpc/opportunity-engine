"""FastAPI app for the optional local ODE web UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from web.bridge import command_catalog, run_command


WEB_ROOT = Path(__file__).resolve().parent
STATIC_DIR = WEB_ROOT / "static"


class CommandRequest(BaseModel):
    """Request body for running a registered ODE command."""

    params: dict[str, Any] = Field(default_factory=dict)


app = FastAPI(
    title="ODE Local Web",
    description="Optional local browser UI for Opportunity Discovery Engine.",
    version="0.1.0",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "data": {"service": "ode-web", "mode": "local"}, "message": ""}


@app.get("/api/commands")
async def commands() -> dict[str, Any]:
    return {"ok": True, "data": {"commands": command_catalog()}, "message": ""}


@app.post("/api/commands/{command}")
async def execute_command(command: str, request: CommandRequest | None = None) -> dict[str, Any]:
    params = request.params if request else {}
    return await run_command(command, params)

