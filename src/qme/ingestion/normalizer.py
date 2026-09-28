"""Normalizer: raw parsed records -> validated ``NormalizedQuestion`` (FE-001).

Rules implemented from FE-001 validation requirements:

- ``question_text``: trimmed, whitespace collapsed, non-empty, <= 10KB UTF-8
- ``options``: keys become single uppercase letters (A-Z), values trimmed and
  whitespace-collapsed; empty values or duplicate keys are explicit errors
- ``correct_answer``: resolved against options — a key (``B``, ``b)``, ``B)``,
  ``(B)``), an option value (text or numeric), or a multi-key answer
  (``A,C`` / ``AC``). With no options (numeric entry) the answer must contain
  a digit, per the contract's "match option key or be numeric".
- Every violation raises :class:`NormalizationError` with field context.
"""

import re
from typing import NoReturn

from qme.core.exceptions import NormalizationError
from qme.core.models import NormalizedQuestion, SourceInfo
from qme.ingestion.parsers.base import RawRecord

_WHITESPACE = re.compile(r"\s+")
_KEY = re.compile(r"^[\(\[]?([A-Za-z])[\)\]\.]?$")
_LETTERS = re.compile(r"[A-Za-z]+")
_MAX_QUESTION_BYTES = 10 * 1024  # FE-001: question text < 10KB


class Normalizer:
    """Stateless normalizer; every rejection carries location + field context."""

    def normalize(self, record: RawRecord, source: SourceInfo) -> NormalizedQuestion:
        raw = record.question
        text = self._question_text(raw.question_text, record.location)
        options = self._options(raw.options, record.location)
        answer = self._answer(raw.correct_answer, options, record.location)
        return NormalizedQuestion(
            question_text=text,
            options=options,
            correct_answer=answer,
            source=source,
        )

    @staticmethod
    def _collapse(value: str) -> str:
        return _WHITESPACE.sub(" ", value.replace("\xa0", " ")).strip()

    def _question_text(self, value: str, location: str) -> str:
        text = self._collapse(value)
        if not text:
            self._fail("question_text", "question_text is empty after normalization", location)
        size = len(text.encode("utf-8"))
        if size > _MAX_QUESTION_BYTES:
            self._fail(
                "question_text",
                f"question_text is {size} bytes, limit is {_MAX_QUESTION_BYTES}",
                location,
            )
        return text

    def _options(self, raw: dict[str, str], location: str) -> dict[str, str]:
        if not raw:
            return {}
        options: dict[str, str] = {}
        for key, value in raw.items():
            clean_key = str(key).strip().upper()
            if not re.fullmatch(r"[A-Z]", clean_key):
                self._fail(
                    "options",
                    f"option key {key!r} must be a single letter after normalization",
                    location,
                )
            clean_value = self._collapse(str(value))
            if not clean_value:
                self._fail("options", f"option {clean_key} has empty text", location)
            if clean_key in options:
                self._fail("options", f"duplicate option key {clean_key} after normalization", location)
            options[clean_key] = clean_value
        return options

    def _answer(self, raw: str, options: dict[str, str], location: str) -> str:
        answer = self._collapse(str(raw))
        if not answer:
            self._fail("correct_answer", "correct_answer is empty after normalization", location)

        if not options:
            if not any(ch.isdigit() for ch in answer):
                self._fail(
                    "correct_answer",
                    f"correct_answer {answer!r} must be numeric for a question without options",
                    location,
                )
            return answer

        bare = answer.strip("()[]{}")
        if match := _KEY.match(answer):
            key = match.group(1).upper()
            if key in options:
                return key
        if match := _KEY.match(bare):
            key = match.group(1).upper()
            if key in options:
                return key

        target = self._fold(bare)
        if matches := [k for k, v in options.items() if self._fold(v) == target]:
            if len(matches) > 1:
                self._fail(
                    "correct_answer",
                    f"correct_answer {answer!r} matches option values of {', '.join(sorted(matches))}",
                    location,
                )
            return matches[0]

        tokens = [t for t in re.split(r"[\s,;]+", bare) if t]
        token_keys = [_KEY.match(t) for t in tokens]
        if token_keys and all(m is not None for m in token_keys):
            keys = [m.group(1).upper() for m in token_keys if m is not None]
            if all(k in options for k in keys):
                return ",".join(dict.fromkeys(keys))

        if _LETTERS.fullmatch(bare) and all(ch.upper() in options for ch in bare):
            return ",".join(dict.fromkeys(ch.upper() for ch in bare))

        self._fail(
            "correct_answer",
            f"correct_answer {answer!r} does not match any option key or option value",
            location,
        )

    @classmethod
    def _fold(cls, value: str) -> str:
        return cls._collapse(value).casefold()

    @staticmethod
    def _fail(field: str, message: str, location: str) -> NoReturn:
        raise NormalizationError(message, context={"location": location, "field": field})
