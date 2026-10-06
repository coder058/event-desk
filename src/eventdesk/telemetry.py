"""Manual local OpenTelemetry spans with an explicit metadata allowlist; no network exporter."""
from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import Span, Status, StatusCode

LOG = logging.getLogger("eventdesk.telemetry")
STAGES = frozenset({"eventdesk.job", "eventdesk.materials", "eventdesk.local_inference", "eventdesk.submit"})


def safe_attributes(attributes: dict[str, Any]) -> dict[str, str | bool | int]:
    result: dict[str, str | bool | int] = {}
    for key, value in attributes.items():
        if key == "eventdesk.job_id" and isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            result[key] = value
        elif key == "eventdesk.slot" and isinstance(value, str) and value in {"s1", "s2", "s3", "s4", "s5"}:
            result[key] = value
        elif key == "eventdesk.fixture" and isinstance(value, bool):
            result[key] = value
        elif key in {"eventdesk.model_sha256", "eventdesk.configuration_sha256"} and isinstance(value, str):
            if re.fullmatch(r"[0-9a-f]{64}", value):
                result[key] = value
        elif key == "error.type" and isinstance(value, str) and re.fullmatch(r"[A-Za-z_]+", value):
            result[key] = value
        elif key == "http.response.status_code" and isinstance(value, int) and 100 <= value <= 599:
            # SOURCE: HTTP status-code range; headers, URLs and bodies are never exported.
            result[key] = value
    return result


class LocalSpanExporter(SpanExporter):
    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        for span in spans:
            if span.name not in STAGES:
                continue
            context = span.context
            record = {"kind": "otel_span", "stage": span.name,
                "trace_id": format(context.trace_id, "032x") if context else None,
                "span_id": format(context.span_id, "016x") if context else None,
                "parent_span_id": format(span.parent.span_id, "016x") if span.parent else None,
                "start_ns": span.start_time, "end_ns": span.end_time,
                "attributes": safe_attributes(dict(span.attributes or {})),
                "status": span.status.status_code.name}
            # No exception events, resource/environment values, URL, raw text or status descriptions.
            LOG.info("%s", json.dumps(record, sort_keys=True))
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None


class Telemetry:
    def __init__(self, exporter: SpanExporter | None = None) -> None:
        self.provider = TracerProvider(resource=Resource({"service.name": "eventdesk-worker"}))
        # GUESS: SDK default-sized bounded batch queue; never an external submission prerequisite.
        # UNCALIBRATED GUESS: five-second local flush cadence requires operational observation.
        self.provider.add_span_processor(BatchSpanProcessor(exporter or LocalSpanExporter(),
            max_queue_size=2048, schedule_delay_millis=5000, max_export_batch_size=512))
        self.tracer = self.provider.get_tracer("eventdesk.manual")

    @contextmanager
    def stage(self, name: str, **attributes: Any) -> Iterator[Span]:
        if name not in STAGES:
            raise ValueError("Undeclared telemetry stage")
        with self.tracer.start_as_current_span(name, attributes=safe_attributes(attributes),
                record_exception=False, set_status_on_exception=False) as span:
            try:
                yield span
            except BaseException as exc:
                # Exception type only; message/traceback can contain signed material URLs or credentials.
                span.set_attribute("error.type", type(exc).__name__)
                span.set_status(Status(StatusCode.ERROR))
                raise

    def shutdown(self) -> None:
        self.provider.shutdown()
