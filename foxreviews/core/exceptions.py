from typing import Any, Optional

from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.response import Response
from rest_framework import status


def api_exception_handler(
    exc: Exception, context: dict[str, Any]
) -> Optional[Response]:
    """Return a uniform JSON error response structure.

    Structure:
    {
        "success": false,
        "code": <HTTP status code>,
        "detail": <primary error message>,
        "errors": <original DRF errors if available>
    }
    """
    response = drf_exception_handler(exc, context)

    if response is not None:
        detail = None
        # Try to extract a concise detail string
        if isinstance(response.data, dict):
            detail = response.data.get("detail")
        if detail is None:
            # Fallback to stringified response data
            detail = str(response.data)

        return Response(
            {
                "success": False,
                "code": response.status_code,
                "detail": detail,
                "errors": response.data,
            },
            status=response.status_code,
            headers=response.headers,
        )

    # Non-DRF exceptions fallback (500)
    return Response(
        {
            "success": False,
            "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "detail": str(exc) or "Internal Server Error",
            "errors": None,
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
