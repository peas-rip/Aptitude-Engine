"""FastAPI application factory.

Run locally: ``uvicorn qme.main:app --reload`` (or ``make run-api``).
"""

from fastapi import FastAPI

from qme import __version__
from qme.config.settings import get_settings


def create_app() -> FastAPI:
    """Build the FastAPI application (separable for testing)."""
    settings = get_settings()
    application = FastAPI(
        title="Question Metadata Engine",
        description=(
            "Backend AI pipeline: raw question -> understand -> classify -> "
            "enrich -> solve if necessary -> validate -> structured metadata."
        ),
        version=__version__,
    )

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
