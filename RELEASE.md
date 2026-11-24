---
release type: minor
---

This release adds a `record_exception_filter` option to `OpenTelemetryExtension`
and `OpenTelemetryExtensionSync`.

The filter receives an exception raised by a resolver and returns whether it
should be recorded on the resolver span. When it returns `False`, the span has no
`exception` event and its status is not set to `ERROR`, while the exception is
still raised and returned in the GraphQL response. This lets you keep expected
errors, such as permission denials, out of your tracing backend's error reports.

```python
from strawberry.exceptions import StrawberryGraphQLError
from strawberry.extensions.tracing import OpenTelemetryExtension
from strawberry.permission import BasePermission


class PermissionDeniedError(StrawberryGraphQLError):
    pass


class IsAdmin(BasePermission):
    error_class = PermissionDeniedError
    ...


def record_exception_filter(exception: Exception) -> bool:
    return not isinstance(exception, PermissionDeniedError)


schema = strawberry.Schema(
    Query,
    extensions=[
        lambda: OpenTelemetryExtension(
            record_exception_filter=record_exception_filter,
        )
    ],
)
```

By default all exceptions are recorded, as before.
