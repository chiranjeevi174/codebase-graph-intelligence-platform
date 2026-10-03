"""Centralized language detection and normalization utilities."""

from enum import Enum


class Language(str, Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    JAVA = "java"
    GO = "go"
    YAML = "yaml"
    JSON = "json"
    UNKNOWN = "unknown"


EXTENSION_MAP: dict[str, str] = {
    ".py": Language.PYTHON.value,
    ".js": Language.JAVASCRIPT.value,
    ".jsx": Language.JAVASCRIPT.value,
    ".ts": Language.TYPESCRIPT.value,
    ".tsx": Language.TYPESCRIPT.value,
    ".java": Language.JAVA.value,
    ".go": Language.GO.value,
    ".yaml": Language.YAML.value,
    ".yml": Language.YAML.value,
    ".json": Language.JSON.value,
}

LANGUAGE_NAME_ALIASES: dict[str, str] = {
    "py": Language.PYTHON.value,
    "python": Language.PYTHON.value,
    "js": Language.JAVASCRIPT.value,
    "jsx": Language.JAVASCRIPT.value,
    "javascript": Language.JAVASCRIPT.value,
    "ts": Language.TYPESCRIPT.value,
    "tsx": Language.TYPESCRIPT.value,
    "typescript": Language.TYPESCRIPT.value,
    "java": Language.JAVA.value,
    "go": Language.GO.value,
    "golang": Language.GO.value,
    "yaml": Language.YAML.value,
    "yml": Language.YAML.value,
    "json": Language.JSON.value,
}


def detect_language(extension_or_path: str) -> str:
    """Detect language identifier from a file extension or filepath.

    Args:
        extension_or_path: File extension (e.g. '.py', '.ts') or path (e.g. 'src/app.tsx').

    Returns:
        Canonical language string (e.g. 'python', 'javascript', 'typescript', 'java', 'go').
    """
    clean = extension_or_path.lower().strip()
    if "." in clean:
        ext = f".{clean.rsplit('.', 1)[-1]}"
        if ext in EXTENSION_MAP:
            return EXTENSION_MAP[ext]

    return LANGUAGE_NAME_ALIASES.get(clean, Language.UNKNOWN.value)


def normalize_language(language_input: str) -> str:
    """Normalize language string or extension to canonical language name."""
    return detect_language(language_input)
