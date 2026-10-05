"""Boundary schemas: permit new event metadata, strictly validate predictions."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Asset(BaseModel):
    model_config = ConfigDict(extra="allow")
    identifier_type: str
    identifier_value: str


class Event(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    event_id: str
    event_type: str
    focal_assets: list[Asset] = Field(min_length=1)
    knowledge_cutoff: datetime | None = None
    event_datetime: datetime | None = None
    information_url: str | None = None
    prediction_deadline: datetime | None = None

    @field_validator("knowledge_cutoff", "event_datetime", "prediction_deadline")
    @classmethod
    def aware_time(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Timezone required")
        return value


class Prediction(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    identifier_value: str
    # SOURCE: competition prediction interval; not a probability of winning a trade.
    predicted_percentile: Annotated[float, Field(ge=0, le=1)]


class SubmissionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str
    predictions: list[Prediction] = Field(min_length=1)


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # SOURCE: only these official text materials can supply verbatim evidence.
    item_id: Literal["earnings-call-facts", "earnings-preview"]
    quote: str = Field(min_length=1)


# SOURCE: structured score range explicitly requested in the mission.
SubScore = Annotated[int, Field(ge=-2, le=2, strict=True)]


class LLMAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    beat_vs_buyside_bar: SubScore
    guidance_change: SubScore
    tone: SubScore
    new_risks: SubScore
    surprise_vs_preview: SubScore
    confidence: Annotated[float, Field(ge=0, le=1)]
    evidence: list[Evidence] = Field(min_length=1)

    def validate_quotes(self, items: dict[str, Any]) -> None:
        for evidence in self.evidence:
            content = items.get(evidence.item_id)
            if isinstance(content, list):
                source = "\n".join(str(x) for x in content)
            elif isinstance(content, str):
                source = content
            else:
                raise ValueError("Evidence item is not supplied text")
            if evidence.quote not in source:
                raise ValueError("Evidence quote absent from source")
