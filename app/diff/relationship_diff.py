"""Relationship-level structural diff engine."""

from typing import Any

from app.diff.diff_models import ChangeType, RelationshipChange
from app.diff.structural_diff import FileSnapshotPair


class RelationshipDiffEngine:
    """Compares call graph, import graph, and inheritance relationships between base and target snapshots."""

    def diff_relationships(self, snapshot_pairs: list[FileSnapshotPair]) -> list[RelationshipChange]:
        """Compute relationship changes (added, removed) across all snapshot pairs."""
        rel_changes: list[RelationshipChange] = []

        for pair in snapshot_pairs:
            base_data = pair.base_data
            target_data = pair.target_data

            base_rels: set[tuple[str, str, str]] = set()
            target_rels: set[tuple[str, str, str]] = set()

            base_rel_meta: dict[tuple[str, str, str], dict[str, Any]] = {}
            target_rel_meta: dict[tuple[str, str, str], dict[str, Any]] = {}

            if base_data:
                # Calls
                for call in base_data.calls:
                    callee = call.callee_qualified_name or call.callee_name
                    key = ("CALLS", call.caller_qualified_name, callee)
                    base_rels.add(key)
                    base_rel_meta[key] = dict(call.model_dump() if hasattr(call, 'model_dump') else call.__dict__)

                # Imports
                for imp in base_data.imports:
                    target_sym = imp.imported_symbol or imp.module_name
                    key = ("IMPORTS", imp.file_path, target_sym)
                    base_rels.add(key)
                    base_rel_meta[key] = dict(imp.model_dump() if hasattr(imp, 'model_dump') else imp.__dict__)

                # Inheritance
                for inh in base_data.inheritance:
                    parent = inh.parent_qualified_name or inh.parent_name
                    rel_t = inh.relationship_type or "INHERITS"
                    key = (rel_t, inh.child_qualified_name, parent)
                    base_rels.add(key)
                    base_rel_meta[key] = dict(inh.model_dump() if hasattr(inh, 'model_dump') else inh.__dict__)

            if target_data:
                # Calls
                for call in target_data.calls:
                    callee = call.callee_qualified_name or call.callee_name
                    key = ("CALLS", call.caller_qualified_name, callee)
                    target_rels.add(key)
                    target_rel_meta[key] = dict(call.model_dump() if hasattr(call, 'model_dump') else call.__dict__)

                # Imports
                for imp in target_data.imports:
                    target_sym = imp.imported_symbol or imp.module_name
                    key = ("IMPORTS", imp.file_path, target_sym)
                    target_rels.add(key)
                    target_rel_meta[key] = dict(imp.model_dump() if hasattr(imp, 'model_dump') else imp.__dict__)

                # Inheritance
                for inh in target_data.inheritance:
                    parent = inh.parent_qualified_name or inh.parent_name
                    rel_t = inh.relationship_type or "INHERITS"
                    key = (rel_t, inh.child_qualified_name, parent)
                    target_rels.add(key)
                    target_rel_meta[key] = dict(inh.model_dump() if hasattr(inh, 'model_dump') else inh.__dict__)

            # Added relationships
            for key in target_rels - base_rels:
                rel_type, src, tgt = key
                rel_changes.append(
                    RelationshipChange(
                        relationship_type=rel_type,
                        change_type=ChangeType.ADDED,
                        source_symbol=src,
                        target_symbol=tgt,
                        old_relationship=None,
                        new_relationship=target_rel_meta.get(key),
                    )
                )

            # Removed relationships
            for key in base_rels - target_rels:
                rel_type, src, tgt = key
                rel_changes.append(
                    RelationshipChange(
                        relationship_type=rel_type,
                        change_type=ChangeType.REMOVED,
                        source_symbol=src,
                        target_symbol=tgt,
                        old_relationship=base_rel_meta.get(key),
                        new_relationship=None,
                    )
                )

        return rel_changes
