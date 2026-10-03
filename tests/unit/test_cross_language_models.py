"""Unit tests verifying cross-language common entity models."""

from app.models.entities import (
    CodeChunk,
    CodeSymbol,
    ExtractedCodeData,
    InheritanceRelation,
    SourceFile,
    SymbolType,
)


def test_cross_language_symbol_types():
    assert SymbolType.CLASS == "Class"
    assert SymbolType.INTERFACE == "Interface"
    assert SymbolType.STRUCT == "Struct"
    assert SymbolType.FUNCTION == "Function"
    assert SymbolType.METHOD == "Method"
    assert SymbolType.CONSTRUCTOR == "Constructor"
    assert SymbolType.TYPE_ALIAS == "TypeAlias"


def test_extracted_code_data_multi_language_aggregation():
    source_file = SourceFile(
        file_path="src/App.tsx",
        relative_path="src/App.tsx",
        language="typescript",
        size_bytes=120,
        lines_of_code=10,
        extension=".tsx",
    )
    sym = CodeSymbol(
        symbol_id="id123",
        symbol_name="AppProps",
        symbol_type=SymbolType.INTERFACE,
        file_path="src/App.tsx",
        start_line=1,
        end_line=5,
        qualified_name="src.App.AppProps",
    )
    inh = InheritanceRelation(
        child_qualified_name="src.App.AppClass",
        parent_name="AppProps",
        file_path="src/App.tsx",
        relationship_type="IMPLEMENTS",
    )
    chunk = CodeChunk(
        chunk_id="chk1",
        repository_id="repo1",
        file_path="src/App.tsx",
        language="typescript",
        symbol_name="AppProps",
        symbol_type="Interface",
        start_line=1,
        end_line=5,
        content="interface AppProps {}",
    )

    data = ExtractedCodeData(
        repository_id="repo1",
        file_info=source_file,
        symbols=[sym],
        inheritance=[inh],
        chunks=[chunk],
    )

    assert data.file_info.language == "typescript"
    assert data.symbols[0].symbol_type == SymbolType.INTERFACE
    assert data.inheritance[0].relationship_type == "IMPLEMENTS"
    assert data.chunks[0].language == "typescript"
