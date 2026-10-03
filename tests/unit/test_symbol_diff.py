"""Unit tests for symbol diff engine."""

from app.diff.diff_models import ChangeType, FileChange
from app.diff.structural_diff import FileSnapshotPair
from app.diff.symbol_diff import SymbolDiffEngine
from app.models.entities import ExtractedCodeData, FunctionInfo, SourceFile, SymbolType


def test_symbol_diff_engine():
    old_sf = SourceFile(
        file_path="user_service.py",
        relative_path="user_service.py",
        language="python",
        extension="py",
    )
    new_sf = SourceFile(
        file_path="user_service.py",
        relative_path="user_service.py",
        language="python",
        extension="py",
    )

    fn_v1 = FunctionInfo(
        symbol_id="fn1",
        symbol_name="create_user",
        symbol_type=SymbolType.FUNCTION,
        file_path="user_service.py",
        start_line=1,
        end_line=4,
        qualified_name="user_service.create_user",
        parameters=["name", "email"],
    )

    fn_v2 = FunctionInfo(
        symbol_id="fn1",
        symbol_name="create_user",
        symbol_type=SymbolType.FUNCTION,
        file_path="user_service.py",
        start_line=1,
        end_line=5,
        qualified_name="user_service.create_user",
        parameters=["name", "email", "role"],
    )

    fn_added = FunctionInfo(
        symbol_id="fn2",
        symbol_name="audit_user_signup",
        symbol_type=SymbolType.FUNCTION,
        file_path="user_service.py",
        start_line=10,
        end_line=15,
        qualified_name="user_service.audit_user_signup",
        parameters=["name"],
    )

    base_data = ExtractedCodeData(
        repository_id="test_repo",
        file_info=old_sf,
        symbols=[fn_v1],
        imports=[],
        calls=[],
        inheritance=[],
        chunks=[],
    )

    target_data = ExtractedCodeData(
        repository_id="test_repo",
        file_info=new_sf,
        symbols=[fn_v2, fn_added],
        imports=[],
        calls=[],
        inheritance=[],
        chunks=[],
    )

    fc = FileChange(
        repository_id="test_repo",
        file_path="user_service.py",
        status=ChangeType.MODIFIED,
        language="python",
    )

    pair = FileSnapshotPair(file_change=fc, base_data=base_data, target_data=target_data)

    engine = SymbolDiffEngine()
    changes = engine.diff_symbols([pair], repository_id="test_repo")

    assert len(changes) == 2
    mod_chg = next(c for c in changes if c.qualified_name == "user_service.create_user")
    assert mod_chg.change_type == ChangeType.MODIFIED
    assert mod_chg.signature_change is not None
    assert mod_chg.signature_change.signature_changed is True

    add_chg = next(c for c in changes if c.qualified_name == "user_service.audit_user_signup")
    assert add_chg.change_type == ChangeType.ADDED
