from typing import Any
from unittest.mock import Mock

import pytest
from opentelemetry.sdk.trace import TracerProvider as SdkTracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import Span, StatusCode, TracerProvider

import strawberry
from strawberry.exceptions import StrawberryGraphQLError
from strawberry.extensions import LifecycleStep
from strawberry.extensions.tracing.opentelemetry import (
    OpenTelemetryExtension,
    OpenTelemetryExtensionSync,
)
from strawberry.permission import BasePermission


def test_span_holder_initialization():
    extension = OpenTelemetryExtension()
    assert extension._span_holder == {}
    extension._span_holder[LifecycleStep.OPERATION] = Mock(spec=Span)
    extension = OpenTelemetryExtension()
    assert extension._span_holder == {}
    tracer_provider = Mock(spec=TracerProvider)
    extension = OpenTelemetryExtension(tracer_provider=tracer_provider)
    assert tracer_provider.get_tracer.called


def test_span_holder_initialization_sync():
    extension = OpenTelemetryExtensionSync()
    assert extension._span_holder == {}
    extension._span_holder[LifecycleStep.OPERATION] = Mock(spec=Span)
    extension = OpenTelemetryExtensionSync()
    assert extension._span_holder == {}
    tracer_provider = Mock(spec=TracerProvider)
    extension = OpenTelemetryExtension(tracer_provider=tracer_provider)
    assert tracer_provider.get_tracer.called


class PermissionDeniedError(StrawberryGraphQLError):
    pass


class IsAdmin(BasePermission):
    message = "Not allowed"
    error_class = PermissionDeniedError

    def has_permission(self, source, info, **kwargs: Any) -> bool:
        return False


@strawberry.type
class Query:
    @strawberry.field(permission_classes=[IsAdmin])
    def secret(self) -> str:
        return "secret"

    @strawberry.field(permission_classes=[IsAdmin])
    async def async_secret(self) -> str:
        return "secret"

    @strawberry.field
    def broken(self) -> str:
        raise ValueError("boom")

    @strawberry.field
    async def async_broken(self) -> str:
        raise ValueError("boom")


def _ignore_permission_errors(exception: Exception) -> bool:
    return not isinstance(exception, PermissionDeniedError)


def _make_exporter() -> tuple[SdkTracerProvider, InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    provider = SdkTracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider, exporter


def _resolver_span(exporter: InMemorySpanExporter, field_name: str):
    (span,) = [
        s
        for s in exporter.get_finished_spans()
        if s.name == f"GraphQL Resolving: {field_name}"
    ]
    return span


@pytest.mark.parametrize("filtered", [False, True])
async def test_record_exception_filter_async(filtered: bool):
    provider, exporter = _make_exporter()
    schema = strawberry.Schema(
        query=Query,
        extensions=[
            lambda: OpenTelemetryExtension(
                tracer_provider=provider,
                record_exception_filter=(
                    _ignore_permission_errors if filtered else None
                ),
            )
        ],
    )

    result = await schema.execute("{ asyncSecret }")

    assert result.errors is not None
    assert result.errors[0].message == "Not allowed"
    span = _resolver_span(exporter, "asyncSecret")
    if filtered:
        assert span.status.status_code == StatusCode.UNSET
        assert span.events == ()
    else:
        assert span.status.status_code == StatusCode.ERROR
        assert [e.name for e in span.events] == ["exception"]


@pytest.mark.parametrize("filtered", [False, True])
def test_record_exception_filter_sync(filtered: bool):
    provider, exporter = _make_exporter()
    schema = strawberry.Schema(
        query=Query,
        extensions=[
            lambda: OpenTelemetryExtensionSync(
                tracer_provider=provider,
                record_exception_filter=(
                    _ignore_permission_errors if filtered else None
                ),
            )
        ],
    )

    result = schema.execute_sync("{ secret }")

    assert result.errors is not None
    assert result.errors[0].message == "Not allowed"
    span = _resolver_span(exporter, "secret")
    if filtered:
        assert span.status.status_code == StatusCode.UNSET
        assert span.events == ()
    else:
        assert span.status.status_code == StatusCode.ERROR
        assert [e.name for e in span.events] == ["exception"]


async def test_record_exception_filter_still_records_other_errors_async():
    provider, exporter = _make_exporter()
    schema = strawberry.Schema(
        query=Query,
        extensions=[
            lambda: OpenTelemetryExtension(
                tracer_provider=provider,
                record_exception_filter=_ignore_permission_errors,
            )
        ],
    )

    result = await schema.execute("{ asyncBroken }")

    assert result.errors is not None
    span = _resolver_span(exporter, "asyncBroken")
    assert span.status.status_code == StatusCode.ERROR
    assert [e.name for e in span.events] == ["exception"]


def test_record_exception_filter_still_records_other_errors_sync():
    provider, exporter = _make_exporter()
    schema = strawberry.Schema(
        query=Query,
        extensions=[
            lambda: OpenTelemetryExtensionSync(
                tracer_provider=provider,
                record_exception_filter=_ignore_permission_errors,
            )
        ],
    )

    result = schema.execute_sync("{ broken }")

    assert result.errors is not None
    span = _resolver_span(exporter, "broken")
    assert span.status.status_code == StatusCode.ERROR
    assert [e.name for e in span.events] == ["exception"]
