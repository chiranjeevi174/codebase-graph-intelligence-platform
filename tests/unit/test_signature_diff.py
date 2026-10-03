"""Unit tests for signature change detection."""

from app.diff.signature_diff import compare_signatures
from app.models.entities import FunctionInfo, SymbolType


def test_signature_diff_parameter_added():
    old_fn = FunctionInfo(
        symbol_id="fn1",
        symbol_name="create_user",
        symbol_type=SymbolType.FUNCTION,
        file_path="user_service.py",
        start_line=1,
        end_line=5,
        qualified_name="create_user",
        parameters=["name: str", "email: str"],
        return_type="dict",
    )
    new_fn = FunctionInfo(
        symbol_id="fn1",
        symbol_name="create_user",
        symbol_type=SymbolType.FUNCTION,
        file_path="user_service.py",
        start_line=1,
        end_line=5,
        qualified_name="create_user",
        parameters=["name: str", "email: str", "role: str = 'user'"],
        return_type="dict",
    )

    sig_info = compare_signatures(old_fn, new_fn)
    assert sig_info is not None
    assert sig_info.signature_changed is True
    assert "role" in sig_info.parameter_added
    assert sig_info.parameter_removed == []
    assert sig_info.default_value_changed is False
    assert sig_info.return_annotation_changed is False


def test_signature_diff_no_change():
    fn1 = FunctionInfo(
        symbol_id="fn1",
        symbol_name="create_user",
        symbol_type=SymbolType.FUNCTION,
        file_path="user_service.py",
        start_line=1,
        end_line=5,
        qualified_name="create_user",
        parameters=["name: str", "email: str"],
        return_type="dict",
    )
    fn2 = FunctionInfo(
        symbol_id="fn1",
        symbol_name="create_user",
        symbol_type=SymbolType.FUNCTION,
        file_path="user_service.py",
        start_line=10,
        end_line=15,
        qualified_name="create_user",
        parameters=["name: str", "email: str"],
        return_type="dict",
    )

    sig_info = compare_signatures(fn1, fn2)
    assert sig_info is not None
    assert sig_info.signature_changed is False
