"""Symbol-level structural diff engine."""

from typing import Any

from app.diff.diff_models import ChangeType, SignatureChangeInfo, SymbolChange
from app.diff.signature_diff import compare_signatures
from app.diff.structural_diff import FileSnapshotPair
from app.models.entities import CodeSymbol, FunctionInfo, MethodInfo


class SymbolDiffEngine:
    """Compares symbols extracted from base and target source snapshots."""

    def diff_symbols(
        self,
        snapshot_pairs: list[FileSnapshotPair],
        repository_id: str = "default",
    ) -> list[SymbolChange]:
        """Compute symbol changes (added, removed, modified, renamed) across all file snapshot pairs."""
        symbol_changes: list[SymbolChange] = []

        for pair in snapshot_pairs:
            fc = pair.file_change
            base_symbols = pair.base_data.symbols if pair.base_data else []
            target_symbols = pair.target_data.symbols if pair.target_data else []

            # Map by qualified_name / symbol_name
            base_map: dict[str, CodeSymbol] = {s.qualified_name: s for s in base_symbols}
            target_map: dict[str, CodeSymbol] = {s.qualified_name: s for s in target_symbols}

            # 1. Added symbols
            for qn, t_sym in target_map.items():
                if qn not in base_map:
                    # Check if renamed symbol or genuinely new
                    sig_info = compare_signatures(None, t_sym)
                    symbol_changes.append(
                        SymbolChange(
                            repository_id=repository_id,
                            file_path=fc.file_path,
                            language=fc.language,
                            symbol_name=t_sym.symbol_name,
                            qualified_name=t_sym.qualified_name,
                            symbol_type=str(t_sym.symbol_type.value if hasattr(t_sym.symbol_type, 'value') else t_sym.symbol_type),
                            change_type=ChangeType.ADDED,
                            start_line=t_sym.start_line,
                            end_line=t_sym.end_line,
                            new_file_path=t_sym.file_path,
                            new_start_line=t_sym.start_line,
                            new_end_line=t_sym.end_line,
                            signature_change=sig_info,
                        )
                    )

            # 2. Removed symbols
            for qn, b_sym in base_map.items():
                if qn not in target_map:
                    sig_info = compare_signatures(b_sym, None)
                    symbol_changes.append(
                        SymbolChange(
                            repository_id=repository_id,
                            file_path=fc.file_path,
                            language=fc.language,
                            symbol_name=b_sym.symbol_name,
                            qualified_name=b_sym.qualified_name,
                            symbol_type=str(b_sym.symbol_type.value if hasattr(b_sym.symbol_type, 'value') else b_sym.symbol_type),
                            change_type=ChangeType.REMOVED,
                            start_line=b_sym.start_line,
                            end_line=b_sym.end_line,
                            old_file_path=b_sym.file_path,
                            old_start_line=b_sym.start_line,
                            old_end_line=b_sym.end_line,
                            signature_change=sig_info,
                        )
                    )

            # 3. Modified or Renamed symbols
            for qn in set(base_map.keys()).intersection(target_map.keys()):
                b_sym = base_map[qn]
                t_sym = target_map[qn]

                sig_info = compare_signatures(b_sym, t_sym)
                has_sig_change = sig_info.signature_changed if sig_info else False

                # Check if lines, docstrings, parameters, decorators or body changed
                lines_changed = (b_sym.start_line != t_sym.start_line or b_sym.end_line != t_sym.end_line)
                doc_changed = (b_sym.docstring != t_sym.docstring)

                is_modified = has_sig_change or lines_changed or doc_changed
                
                # Check decorators or base_classes if class/func
                b_decs = getattr(b_sym, "decorators", [])
                t_decs = getattr(t_sym, "decorators", [])
                if b_decs != t_decs:
                    is_modified = True

                b_bases = getattr(b_sym, "base_classes", [])
                t_bases = getattr(t_sym, "base_classes", [])
                if b_bases != t_bases:
                    is_modified = True

                if is_modified:
                    chg_type = ChangeType.RENAMED if fc.status == ChangeType.RENAMED else ChangeType.MODIFIED
                    symbol_changes.append(
                        SymbolChange(
                            repository_id=repository_id,
                            file_path=t_sym.file_path,
                            language=fc.language,
                            symbol_name=t_sym.symbol_name,
                            qualified_name=t_sym.qualified_name,
                            symbol_type=str(t_sym.symbol_type.value if hasattr(t_sym.symbol_type, 'value') else t_sym.symbol_type),
                            change_type=chg_type,
                            start_line=t_sym.start_line,
                            end_line=t_sym.end_line,
                            old_file_path=b_sym.file_path,
                            old_start_line=b_sym.start_line,
                            old_end_line=b_sym.end_line,
                            new_file_path=t_sym.file_path,
                            new_start_line=t_sym.start_line,
                            new_end_line=t_sym.end_line,
                            signature_change=sig_info,
                            details={
                                "lines_changed": lines_changed,
                                "docstring_changed": doc_changed,
                                "signature_changed": has_sig_change,
                            },
                        )
                    )

        return symbol_changes
