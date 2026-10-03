"""Unit tests for language detection and normalization."""

from app.parsing.language import Language, detect_language, normalize_language


def test_detect_language_by_extension():
    assert detect_language(".py") == Language.PYTHON.value
    assert detect_language(".js") == Language.JAVASCRIPT.value
    assert detect_language(".jsx") == Language.JAVASCRIPT.value
    assert detect_language(".ts") == Language.TYPESCRIPT.value
    assert detect_language(".tsx") == Language.TYPESCRIPT.value
    assert detect_language(".java") == Language.JAVA.value
    assert detect_language(".go") == Language.GO.value


def test_detect_language_by_filepath():
    assert detect_language("app/main.py") == Language.PYTHON.value
    assert detect_language("src/index.js") == Language.JAVASCRIPT.value
    assert detect_language("components/Button.jsx") == Language.JAVASCRIPT.value
    assert detect_language("src/service.ts") == Language.TYPESCRIPT.value
    assert detect_language("components/Header.tsx") == Language.TYPESCRIPT.value
    assert detect_language("com/example/Main.java") == Language.JAVA.value
    assert detect_language("cmd/server/main.go") == Language.GO.value


def test_normalize_language():
    assert normalize_language("Python") == Language.PYTHON.value
    assert normalize_language("JavaScript") == Language.JAVASCRIPT.value
    assert normalize_language("TypeScript") == Language.TYPESCRIPT.value
    assert normalize_language("Java") == Language.JAVA.value
    assert normalize_language("Go") == Language.GO.value
    assert normalize_language(".tsx") == Language.TYPESCRIPT.value
    assert normalize_language("unknown_ext.xyz") == Language.UNKNOWN.value
