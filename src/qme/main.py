"""FastAPI application factory.

Run locally: ``uvicorn qme.main:app --reload`` (or ``make run-api``).
"""

import logging

from fastapi import FastAPI

from qme import __version__
from qme.api.exceptions import register_exception_handlers
from qme.api.routes.testgen import router as testgen_router
from qme.config.settings import get_settings

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Build the FastAPI application (separable for testing)."""
    settings = get_settings()
    if settings.environment == "production" and not settings.qme_api_key:
        raise RuntimeError(
            "QME_API_KEY must be set when ENVIRONMENT=production "
            "(API_CONTRACTS 1.7: the testgen API refuses to boot unauthenticated)"
        )
    if not settings.qme_api_key:
        logger.warning(
            "QME_API_KEY is unset - testgen endpoints are open (development only)"
        )
    application = FastAPI(
        title="Question Metadata Engine",
        description=(
            "Backend AI pipeline: raw question -> understand -> classify -> "
            "enrich -> solve if necessary -> validate -> structured metadata."
        ),
        version=__version__,
    )
    register_exception_handlers(application)
    application.include_router(testgen_router)

    @application.get("/api/v1/health")
    async def health() -> dict[str, str | bool]:
        """Liveness probe (API_CONTRACTS 1.6)."""
        return {
            "status": "ok",
            "version": __version__,
            "environment": settings.environment,
            "openai_configured": bool(settings.openai_api_key),
        }

    return application


app = create_app()
