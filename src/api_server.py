"""FastAPI entrypoint for the style agent."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .style_editor import apply_style

app = FastAPI(title="Style Agent API", version="0.1.0")


class StyleRequest(BaseModel):
    project_id: str = Field(min_length=1)
    draft_markdown: str
    style: str | None = None
    tone: str | None = None
    voice_profile: dict[str, Any] | None = None
    voice_profile_id: str | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "style_agent"}


@app.post("/api/v1/styles")
def create_style(request: StyleRequest) -> dict[str, Any]:
    return {"project_id": request.project_id, **apply_style(request.model_dump())}
