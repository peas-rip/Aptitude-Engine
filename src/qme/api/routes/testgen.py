"""Testgen HTTP endpoints (API_CONTRACTS 1.7).

Stateless JSON only — no file writes, no client-supplied paths. The bank is
cached by blueprint path + mtime, so a regenerated bank file is picked up on
the next request without a restart; any contract violation surfaces as a 503
with the full field report (never silently tolerated).
"""

import logging
import secrets
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Header

from qme.api.exceptions import UnauthorizedError
from qme.config.settings import get_settings
from qme.testgen import generate_practice, generate_test, load_bank
from qme.testgen.bank import Bank
from qme.testgen.errors import ContractError
from qme.testgen.schemas import GeneratedTest, PracticeRequest, PracticeSet, TestRequest

logger = logging.getLogger(__name__)

_cache: dict = {"path": None, "mtime": None, "bank": None}


def _require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    """Validate ``X-API-Key`` against ``QME_API_KEY`` (empty key = open, dev only)."""
    expected = get_settings().qme_api_key
    if not expected:
        return
    if x_api_key is None or not secrets.compare_digest(x_api_key, expected):
        raise UnauthorizedError("missing or invalid X-API-Key header")


def get_bank() -> Bank:
    """Serve the validated bank, revalidating whenever the blueprint changes."""
    path: Path = get_settings().qme_blueprint_path
    try:
        mtime = path.stat().st_mtime_ns
    except OSError as exc:
        raise ContractError(f"blueprint not readable: {path} ({exc.strerror})") from exc
    if _cache["bank"] is None or _cache["path"] != path or _cache["mtime"] != mtime:
        bank = load_bank(path)
        _cache.update(path=path, mtime=mtime, bank=bank)
        logger.info("bank loaded | path=%s | questions=%d", path, len(bank.questions))
    return _cache["bank"]


router = APIRouter(
    prefix="/api/v1",
    tags=["testgen"],
    dependencies=[Depends(_require_api_key)],
)


@router.get("/bank/meta")
def bank_meta(bank: Annotated[Bank, Depends(get_bank)]) -> dict:
    """Discovery: valid filter values and the blueprint contract."""
    return {
        "chapters": bank.chapters,
        "topics": bank.topics,
        "difficulties": bank.difficulties,
        "question_count": len(bank.questions),
        "buckets": bank.blueprint.buckets,
        "contract": bank.blueprint.test_generation_contract.model_dump(),
    }


@router.post("/tests", response_model=GeneratedTest)
def create_test(
    request: TestRequest, bank: Annotated[Bank, Depends(get_bank)]
) -> GeneratedTest:
    """Assemble a blueprint-conformant test (deterministic per seed)."""
    return generate_test(bank, request)


@router.post("/practice", response_model=PracticeSet)
def create_practice(
    request: PracticeRequest, bank: Annotated[Bank, Depends(get_bank)]
) -> PracticeSet:
    """Build a practice set (progressive or mixed order)."""
    return generate_practice(bank, request)
