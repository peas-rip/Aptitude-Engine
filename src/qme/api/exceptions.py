"""Exception handlers mapping testgen errors to the API_CONTRACTS §4 envelope.

Every error body is ``{"error": {code, message, details, request_id}}`` with
a per-request UUID (API_CONTRACTS 4).
"""

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from qme.testgen.errors import ContractError, SelectionError, SubmissionError

logger = logging.getLogger(__name__)


class UnauthorizedError(Exception):
    """Missing or invalid ``X-API-Key`` (API_CONTRACTS 1.7)."""


class NotFoundError(Exception):
    """A named resource (e.g. a chapter) does not exist (API_CONTRACTS 1.7)."""


def _envelope(status_code: int, code: str, message: str, details: dict) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details,
                "request_id": str(uuid.uuid4()),
            }
        },
    )


def register_exception_handlers(application: FastAPI) -> None:
    """Attach API_CONTRACTS §4 handlers for testgen and validation failures."""

    @application.exception_handler(UnauthorizedError)
    async def _unauthorized(_request: Request, exc: UnauthorizedError) -> JSONResponse:
        logger.info("unauthorized request | %s", exc)
        return _envelope(401, "UNAUTHORIZED", str(exc), {})

    @application.exception_handler(SelectionError)
    async def _selection_error(_request: Request, exc: SelectionError) -> JSONResponse:
        logger.info("selection rejected | %s", exc)
        return _envelope(422, "INVALID_INPUT", str(exc), exc.details)

    @application.exception_handler(SubmissionError)
    async def _submission_error(_request: Request, exc: SubmissionError) -> JSONResponse:
        logger.info("submission rejected | %s", exc)
        return _envelope(422, "ANSWER_MISMATCH", str(exc), exc.details)

    @application.exception_handler(NotFoundError)
    async def _not_found(_request: Request, exc: NotFoundError) -> JSONResponse:
        logger.info("resource not found | %s", exc)
        return _envelope(404, "NOT_FOUND", str(exc), {})

    @application.exception_handler(ContractError)
    async def _contract_error(_request: Request, exc: ContractError) -> JSONResponse:
        logger.error("bank contract violated | %s", exc)
        return _envelope(
            503,
            "SERVICE_UNAVAILABLE",
            "question bank violates its contract; the service cannot serve requests",
            {"issues": exc.issues},
        )

    @application.exception_handler(RequestValidationError)
    async def _validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        fields = [
            {
                "location": ".".join(str(p) for p in err["loc"]),
                "message": err["msg"],
            }
            for err in exc.errors()
        ]
        return _envelope(
            422,
            "VALIDATION_ERROR",
            "request body failed validation",
            {"fields": fields},
        )
