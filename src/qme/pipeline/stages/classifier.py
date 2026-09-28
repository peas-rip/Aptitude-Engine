"""QuestionClassifier stage (FE-002): taxonomy labels via structured output.

Implements the ``QuestionClassifier`` Protocol. The LLM may only choose from
the loaded taxonomy: every returned ID set is validated against it, and
rejected sets trigger a corrective retry (structured feedback, still no
free-form parsing) before an explicit failure.
"""

import json
import logging
from pathlib import Path

from qme.config.settings import Settings, get_settings
from qme.config.taxonomy_loader import Taxonomy, load_taxonomy
from qme.core.exceptions import LLMResponseFormatError
from qme.core.models import ClassificationInput, ClassificationResult
from qme.llm.gateway import LLMGateway
from qme.llm.prompt_manager import PromptManager

logger = logging.getLogger(__name__)

_PROMPT_NAME = "classifier_v1"


class Classifier:
    """Taxonomy-aware classifier implementing the QuestionClassifier Protocol."""

    def __init__(
        self,
        *,
        gateway: LLMGateway | None = None,
        taxonomy: Taxonomy | None = None,
        prompts: PromptManager | None = None,
        model: str | None = None,
        settings: Settings | None = None,
        prompt_dir: Path | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._gateway = gateway or LLMGateway(settings=self._settings)
        self._taxonomy = taxonomy or load_taxonomy()
        self._prompts = prompts or PromptManager(prompt_dir)
        self._model = model or self._settings.model_classifier

    async def classify(self, input: ClassificationInput) -> ClassificationResult:
        prompt = self._prompts.load(_PROMPT_NAME)
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": prompt.render(taxonomy=self._taxonomy.render_for_prompt()),
            },
            {
                "role": "user",
                # JSON-serialized data: braces are data, never template input.
                "content": json.dumps(
                    {
                        "question_text": input.question_text,
                        "options": input.options,
                        "correct_answer": input.correct_answer,
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        max_attempts = max(1, self._settings.max_retries)
        last_errors: list[str] = []
        for attempt in range(1, max_attempts + 1):
            response = await self._gateway.complete(
                messages=messages,
                schema=ClassificationResult,
                model=self._model,
                stage="classifier",
            )
            result = response.value
            logger.debug(
                "classifier LLM call | model=%s | tokens=%d+%d | attempts=%d",
                response.model,
                response.prompt_tokens,
                response.completion_tokens,
                response.attempts,
            )
            errors = self._taxonomy.validate_ids(
                result.category_id, result.topic_id, result.subtopic_id
            )
            if not errors:
                return result
            last_errors = errors
            logger.warning(
                "classifier rejected taxonomy ids | attempt=%d/%d | %s",
                attempt,
                max_attempts,
                "; ".join(errors),
            )
            messages = messages + [
                {"role": "assistant", "content": result.model_dump_json()},
                {
                    "role": "user",
                    "content": (
                        "These taxonomy IDs are invalid: "
                        + "; ".join(errors)
                        + ". Use only IDs copied exactly from the taxonomy. "
                        + "Return the corrected JSON object only."
                    ),
                },
            ]
        raise LLMResponseFormatError(
            "classification failed taxonomy validation after retries",
            context={
                "stage": "classifier",
                "model": self._model,
                "attempts": max_attempts,
                "errors": last_errors,
                "question": input.question_text[:200],
            },
        )

    def get_taxonomy_version(self) -> int:
        return self._taxonomy.version
