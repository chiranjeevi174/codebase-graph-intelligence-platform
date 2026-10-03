"""Signature change comparison module."""

import re
from typing import Any

from app.diff.diff_models import SignatureChangeInfo
from app.models.entities import CodeSymbol, FunctionInfo, MethodInfo


def _parse_param_parts(param_str: str) -> tuple[str, str | None, str | None]:
    """Parse parameter string into (name, type_annotation, default_value)."""
    p = param_str.strip()
    if not p:
        return ("", None, None)

    # Check default value
    default_val = None
    if "=" in p:
        parts = p.split("=", 1)
        p = parts[0].strip()
        default_val = parts[1].strip()

    # Check type annotation
    type_ann = None
    if ":" in p:
        parts = p.split(":", 1)
        name = parts[0].strip()
        type_ann = parts[1].strip()
    else:
        # Handle space separated types in Java/Go (e.g., "String name", "name string")
        tokens = p.split()
        if len(tokens) >= 2:
            # Simple heuristic
            name = tokens[-1]
            type_ann = " ".join(tokens[:-1])
        else:
            name = p

    # Clean name (remove self, cls, *args, **kwargs prefixes if any)
    name = re.sub(r"^[\*\&]+", "", name)
    return (name, type_ann, default_val)


def compare_signatures(
    old_symbol: CodeSymbol | None,
    new_symbol: CodeSymbol | None,
) -> SignatureChangeInfo | None:
    """Compare parameter lists, type annotations, and return types between base and target symbol versions."""
    if not old_symbol or not new_symbol:
        return None

    # Only compare functions and methods
    if old_symbol.symbol_type not in ("Function", "Method") or new_symbol.symbol_type not in ("Function", "Method"):
        return None

    old_params = getattr(old_symbol, "parameters", []) or []
    new_params = getattr(new_symbol, "parameters", []) or []

    old_return = getattr(old_symbol, "return_type", None)
    new_return = getattr(new_symbol, "return_type", None)

    old_param_parsed = [_parse_param_parts(p) for p in old_params]
    new_param_parsed = [_parse_param_parts(p) for p in new_params]

    # Filter out 'self' and 'cls' for method comparison consistency
    old_filtered = [p for p in old_param_parsed if p[0] not in ("self", "cls")]
    new_filtered = [p for p in new_param_parsed if p[0] not in ("self", "cls")]

    old_names = [p[0] for p in old_filtered if p[0]]
    new_names = [p[0] for p in new_filtered if p[0]]

    param_added = [n for n in new_names if n not in old_names]
    param_removed = [n for n in old_names if n not in new_names]

    # Order check on common params
    common_old = [n for n in old_names if n in new_names]
    common_new = [n for n in new_names if n in old_names]
    order_changed = (common_old != common_new)

    # Check defaults and type annotations for common parameters
    old_dict = {p[0]: p for p in old_filtered if p[0]}
    new_dict = {p[0]: p for p in new_filtered if p[0]}

    default_changed = False
    type_changed = False

    for name in common_old:
        op = old_dict[name]
        np = new_dict[name]
        if op[2] != np[2]:
            default_changed = True
        if op[1] != np[1] and (op[1] is not None or np[1] is not None):
            type_changed = True

    return_changed = (old_return != new_return)

    sig_changed = (
        bool(param_added)
        or bool(param_removed)
        or order_changed
        or default_changed
        or type_changed
        or return_changed
    )

    old_sig_str = f"({', '.join(old_params)})" + (f" -> {old_return}" if old_return else "")
    new_sig_str = f"({', '.join(new_params)})" + (f" -> {new_return}" if new_return else "")

    return SignatureChangeInfo(
        signature_changed=sig_changed,
        parameter_added=param_added,
        parameter_removed=param_removed,
        parameter_order_changed=order_changed,
        default_value_changed=default_changed,
        type_annotation_changed=type_changed,
        return_annotation_changed=return_changed,
        old_signature=old_sig_str if sig_changed else None,
        new_signature=new_sig_str if sig_changed else None,
    )
