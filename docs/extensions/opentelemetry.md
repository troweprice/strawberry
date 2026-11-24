---
title: Open Telemetry
summary: Add Open Telemetry tracing to your GraphQL server.
tags: tracing
---

# `OpenTelemetryExtension`

This extension adds tracing information that is compatible with
[Open Telemetry](https://opentelemetry.io/).

<Note>

This extension requires additional requirements:

```shell
pip install 'strawberry-graphql[opentelemetry]'
```

</Note>

## Usage example:

```python
import strawberry
from strawberry.extensions.tracing import OpenTelemetryExtension


@strawberry.type
class Query:
    @strawberry.field
    def hello(self) -> str:
        return "Hello, world!"


schema = strawberry.Schema(
    Query,
    extensions=[
        OpenTelemetryExtension,
    ],
)
```

<Note>

If you are not running in an Async context then you'll need to use the sync
version:

```python
import strawberry
from strawberry.extensions.tracing import OpenTelemetryExtensionSync


@strawberry.type
class Query:
    @strawberry.field
    def hello(self) -> str:
        return "Hello, world!"


schema = strawberry.Schema(
    Query,
    extensions=[
        OpenTelemetryExtensionSync,
    ],
)
```

</Note>

## API reference:

```python
class OpenTelemetryExtension(arg_filter=None, record_exception_filter=None): ...
```

#### `arg_filter: Optional[ArgFilter]`

A function to filter certain field arguments from being included in the tracing
data.

```python
ArgFilter = Callable[[Dict[str, Any], GraphQLResolveInfo], Dict[str, Any]]
```

#### `record_exception_filter: Optional[RecordExceptionFilter]`

A function that decides whether an exception raised by a resolver is recorded on
its span. It receives the exception and returns `True` to record it (an
`exception` event is added and the span status is set to `ERROR`) or `False` to
leave the span untouched. The exception is still raised and reported in the
GraphQL response. By default every exception is recorded.

```python
RecordExceptionFilter = Callable[[Exception], bool]
```

## More examples:

<details>
  <summary>Using `arg_filter`</summary>

```python
import strawberry
from strawberry.extensions.tracing import OpenTelemetryExtensionSync


@strawberry.type
class Query:
    @strawberry.field
    def hello(self) -> str:
        return "Hello, world!"


def arg_filter(kwargs, info):
    filtered_kwargs = {}
    for name, value in kwargs.items():
        # Never include any arguments called "password"
        if name == "password":
            continue
        filtered_kwargs[name] = value

    return filtered_kwargs


schema = strawberry.Schema(
    Query,
    extensions=[
        OpenTelemetryExtensionSync(
            arg_filter=arg_filter,
        ),
    ],
)
```

</details>

<details>
  <summary>Using `tracer_provider`</summary>

```python
import strawberry
from opentelemetry.trace import TracerProvider
from strawberry.extensions.tracing import OpenTelemetryExtension


@strawberry.type
class Query:
    @strawberry.field
    def hello(self) -> str:
        return "Hello, world!"


class MyTracerProvider(TracerProvider):
    def get_tracer(self, name, version=None, schema_url=None):
        return super().get_tracer(name, version, schema_url)


schema = strawberry.Schema(
    Query,
    extensions=[
        OpenTelemetryExtension(
            tracer_provider=MyTracerProvider(),
        ),
    ],
)
```

</details>

<details>
  <summary>Using `record_exception_filter`</summary>

Permission denials are an expected outcome rather than a server fault. This
keeps them from being reported as errors in your tracing backend.

You may want to match on an exception class that only your permission checks
raise. Matching a broad class such as `StrawberryGraphQLError` would also hide
other errors that you may want to see.

```python
import strawberry
from strawberry.exceptions import StrawberryGraphQLError
from strawberry.extensions.tracing import OpenTelemetryExtension
from strawberry.permission import BasePermission


class PermissionDeniedError(StrawberryGraphQLError):
    pass


class IsAdmin(BasePermission):
    message = "Not allowed"
    error_class = PermissionDeniedError

    def has_permission(self, source, info, **kwargs):
        return False


@strawberry.type
class Query:
    @strawberry.field(permission_classes=[IsAdmin])
    def secret(self) -> str:
        return "secret"


def record_exception_filter(exception: Exception) -> bool:
    return not isinstance(exception, PermissionDeniedError)


schema = strawberry.Schema(
    Query,
    extensions=[
        lambda: OpenTelemetryExtension(
            record_exception_filter=record_exception_filter,
        ),
    ],
)
```

</details>
