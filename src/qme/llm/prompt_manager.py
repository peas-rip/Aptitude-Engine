"""Versioned prompt templates (FE-008: ``prompt_version`` = hash of template).

Templates use ``$name`` placeholders (``string.Template``) so literal JSON
braces in prompt examples never collide with interpolation syntax.

Injection containment (FE-001 security): templates are trusted config files
and only ever substituted with other trusted values (taxonomy text).
Question text is NEVER interpolated — stages pass it as a separate user
message, so braces and instructions inside data cannot reach the template.
"""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from string import Template

from qme.core.exceptions import LLMError

_DEFAULT_DIR = Path(__file__).resolve().parents[1] / "config" / "prompts"


@dataclass(frozen=True)
class Prompt:
    """One loaded template: content, its content-hash version, and rendering."""

    name: str
    content: str
    version: str

    def render(self, **trusted_vars: str) -> str:
        """Substitute trusted variables only. Missing keys fail loudly."""
        try:
            return Template(self.content).substitute(**trusted_vars)
        except KeyError as exc:
            raise LLMError(
                f"prompt {self.name!r} references unknown placeholder {exc.args[0]!r}",
                context={"prompt": self.name, "provided": sorted(trusted_vars)},
            ) from exc
        except ValueError as exc:
            raise LLMError(
                f"prompt {self.name!r} has malformed placeholders",
                context={"prompt": self.name, "error": str(exc)},
            ) from exc


class PromptManager:
    """Loads ``{name}.txt`` templates from the prompts directory."""

    def __init__(self, prompt_dir: Path | None = None) -> None:
        self._dir = prompt_dir or _DEFAULT_DIR

    def load(self, name: str) -> Prompt:
        path = self._dir / f"{name}.txt"
        if not path.is_file():
            raise LLMError(
                f"prompt template {name!r} not found",
                context={"path": str(path)},
            )
        content = path.read_text(encoding="utf-8")
        version = sha256(content.encode("utf-8")).hexdigest()
        return Prompt(name=name, content=content, version=version)
