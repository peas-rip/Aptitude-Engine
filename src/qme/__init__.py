"""Question Metadata Engine (QME).

Transforms raw aptitude questions into structured, validated, metadata-rich
question objects for downstream consumption by the Deduplication Engine.
"""

import warnings

# BatchConfig.validate is mandated by docs/API_CONTRACTS.md 3.2 and shadows
# BaseModel.validate (unused in pydantic v2) — a deliberate, documented
# contract choice (see core/models.py and pyproject filterwarnings).
warnings.filterwarnings(
    "ignore",
    message='Field name "validate"',
    category=UserWarning,
)

__version__ = "0.1.0"
