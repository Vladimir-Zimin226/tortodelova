from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, constr, ConfigDict


class PredictionCreateRequest(BaseModel):
    prompt: constr(min_length=1)
    # Если None или <= 0 — берём первую активную image-модель
    model_id: Optional[int] = None


class PredictionOut(BaseModel):
    id: int
    prompt_ru: str
    prompt_en: str
    s3_key: str
    public_url: str
    credits_spent: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PredictionEnqueueResponse(BaseModel):
    task_id: str
    queued: bool = True
    cost_credits: int
    message: str


class DemoClaimRequest(BaseModel):
    task_id: str


class MessageResponse(BaseModel):
    message: str
