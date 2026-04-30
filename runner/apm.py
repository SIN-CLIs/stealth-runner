"""OpenTelemetry APM – Traces über alle States."""
from __future__ import annotations
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, BatchSpanProcessor
trace.set_tracer_provider(TracerProvider())
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
tracer = trace.get_tracer("stealth-runner")

def start_trace(state: str) -> trace.Span: return tracer.start_as_current_span(f"state:{state}")
