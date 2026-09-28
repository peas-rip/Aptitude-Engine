"""Schema enforcement for LLM outputs (hard rule: structured outputs only).

``strict_schema`` transforms a Pydantic JSON schema into the strict-mode
requirements shared by OpenAI and Groq constrained decoding:

- every property is listed in ``required`` (properties with Python defaults
  included — the model must always emit them)
- nullable fields stay as ``anyOf: [..., {type: null}]``
- ``additionalProperties: false`` on every object
- cosmetic keywords (``title``, ``default``) stripped

``parse_model`` validates the returned text into the Pydantic model — even
strict-mode output passes validation here (belt and suspenders).
"""

from typing import Any

from pydantic import BaseModel

from qme.core.exceptions import LLMResponseFormatError

_STRIP_KEYS = frozenset({"title", "default"})


def strict_schema(model_cls: type[BaseModel]) -> dict[str, Any]:
    """JSON schema ready for ``response_format.type=json_schema, strict=True``."""
    schema = model_cls.model_json_schema()
    return _transform(schema)


def parse_model(model_cls: type[BaseModel], content: str) -> BaseModel:
    """Validate raw LLM text against ``model_cls``; never returns invalid data."""
    try:
        return model_cls.model_validate_json(content)
    except Exception as exc:  # pydantic raises ValidationError; JSON errors subclass it
        raise LLMResponseFormatError(
            f"output did not match schema {model_cls.__name__}",
            context={"model": model_cls.__name__, "raw": content[:500], "error": str(exc)[:500]},
        ) from exc


def _transform(node: Any) -> Any:
    if isinstance(node, list):
        return [_transform(item) for item in node]
    if not isinstance(node, dict):
        return node

    # Children first ($defs, properties, items, anyOf branches all recurse),
    # then object-level rules apply at this node.
    cleaned = {key: _transform(value) for key, value in node.items() if key not in _STRIP_KEYS}

    if cleaned.get("type") == "object" and "properties" in cleaned:
        cleaned["additionalProperties"] = False
        cleaned["required"] = list(cleaned["properties"].keys())
    return cleaned
