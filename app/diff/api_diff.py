"""API endpoint, contract, and breaking change structural diff analyzer."""

from typing import Any

from app.diff.diff_models import ApiChange, ChangeClassification, ChangeType, ContractChange
from app.diff.structural_diff import FileSnapshotPair
from app.models.entities import ApiClientCall, ApiContract, ApiEndpoint, SourceFile
from app.parsing.api_extractor import APIExtractor
from app.parsing.url_normalizer import normalize_url_path
from app.utils.logger import logger


class ApiDiffEngine:
    """Detects API endpoint changes, OpenAPI contract diffs, and assesses breaking change risk indicators."""

    def __init__(self, api_extractor: APIExtractor | None = None, git_service: Any = None):
        self.extractor = api_extractor or APIExtractor()
        self.git_service = git_service

    def diff_api_changes(
        self,
        snapshot_pairs: list[FileSnapshotPair],
        all_client_calls: list[ApiClientCall] | None = None,
        repository_id: str = "default",
        git_service: Any = None,
    ) -> tuple[list[ApiChange], list[ContractChange], str]:
        """Compute API endpoint and contract changes across file snapshots."""
        api_changes: list[ApiChange] = []
        contract_changes: list[ContractChange] = []

        g_svc = git_service or self.git_service

        base_endpoints: dict[str, ApiEndpoint] = {}
        target_endpoints: dict[str, ApiEndpoint] = {}

        base_contracts: dict[str, ApiContract] = {}
        target_contracts: dict[str, ApiContract] = {}

        for pair in snapshot_pairs:
            fc = pair.file_change

            # Extract base API elements
            if pair.base_data or fc.old_path:
                sf_base = SourceFile(
                    file_path=fc.old_path or fc.file_path,
                    relative_path=fc.old_path or fc.file_path,
                    language=fc.language,
                    extension=(fc.old_path or fc.file_path).split(".")[-1] if "." in (fc.old_path or fc.file_path) else "",
                )
                if g_svc and pair.file_change.old_commit and (fc.old_path or fc.file_path):
                    content = g_svc.get_file_content_at_ref(pair.file_change.old_commit, fc.old_path or fc.file_path)
                    if content:
                        eps, _, cnts = self.extractor.extract_from_content(sf_base, content, repository_id)
                        for ep in eps:
                            key = f"{ep.http_method}:{ep.path}"
                            base_endpoints[key] = ep
                        for c in cnts:
                            key = f"{c.http_method}:{c.path_template}"
                            base_contracts[key] = c

            # Extract target API elements
            if pair.target_data or fc.new_path:
                sf_target = SourceFile(
                    file_path=fc.new_path or fc.file_path,
                    relative_path=fc.new_path or fc.file_path,
                    language=fc.language,
                    extension=(fc.new_path or fc.file_path).split(".")[-1] if "." in (fc.new_path or fc.file_path) else "",
                )
                if g_svc and pair.file_change.new_commit and (fc.new_path or fc.file_path):
                    content = g_svc.get_file_content_at_ref(pair.file_change.new_commit, fc.new_path or fc.file_path)
                    if content:
                        eps, _, cnts = self.extractor.extract_from_content(sf_target, content, repository_id)
                        for ep in eps:
                            key = f"{ep.http_method}:{ep.path}"
                            target_endpoints[key] = ep
                        for c in cnts:
                            key = f"{c.http_method}:{c.path_template}"
                            target_contracts[key] = c

        # 1. Added API endpoints
        for key, t_ep in target_endpoints.items():
            if key not in base_endpoints:
                # Check if path changed from an old handler
                path_match_base = [b for b in base_endpoints.values() if b.controller_symbol == t_ep.controller_symbol]
                old_p = path_match_base[0].path if path_match_base else None
                old_m = path_match_base[0].http_method if path_match_base else None

                api_changes.append(
                    ApiChange(
                        endpoint_id=t_ep.endpoint_id,
                        http_method=t_ep.http_method,
                        path=t_ep.path,
                        old_path=old_p,
                        old_http_method=old_m,
                        change_type=ChangeType.ADDED if not old_p else ChangeType.MODIFIED,
                        endpoint_added=not old_p,
                        endpoint_removed=False,
                        method_changed=bool(old_m and old_m != t_ep.http_method),
                        path_changed=bool(old_p and old_p != t_ep.path),
                        operation_id_changed=False,
                        request_contract_changed=False,
                        response_contract_changed=False,
                        details={
                            "controller_symbol": t_ep.controller_symbol,
                            "file_path": t_ep.file_path,
                            "start_line": t_ep.start_line,
                        },
                    )
                )

        # 2. Removed API endpoints
        for key, b_ep in base_endpoints.items():
            if key not in target_endpoints:
                # Check if path moved or removed completely
                handler_still_exists = any(t.controller_symbol == b_ep.controller_symbol for t in target_endpoints.values())
                if not handler_still_exists:
                    api_changes.append(
                        ApiChange(
                            endpoint_id=b_ep.endpoint_id,
                            http_method=b_ep.http_method,
                            path=b_ep.path,
                            old_path=b_ep.path,
                            old_http_method=b_ep.http_method,
                            change_type=ChangeType.REMOVED,
                            endpoint_added=False,
                            endpoint_removed=True,
                            method_changed=False,
                            path_changed=False,
                            operation_id_changed=False,
                            request_contract_changed=False,
                            response_contract_changed=False,
                            details={
                                "controller_symbol": b_ep.controller_symbol,
                                "file_path": b_ep.file_path,
                                "start_line": b_ep.start_line,
                            },
                        )
                    )

        # 3. OpenAPI Contract changes
        for key, t_cnt in target_contracts.items():
            if key not in base_contracts:
                contract_changes.append(
                    ContractChange(
                        contract_id=t_cnt.contract_id,
                        file_path=t_cnt.file_path,
                        change_type=ChangeType.ADDED,
                        details={"http_method": t_cnt.http_method, "path_template": t_cnt.path_template},
                    )
                )
        for key, b_cnt in base_contracts.items():
            if key not in target_contracts:
                contract_changes.append(
                    ContractChange(
                        contract_id=b_cnt.contract_id,
                        file_path=b_cnt.file_path,
                        change_type=ChangeType.REMOVED,
                        details={"http_method": b_cnt.http_method, "path_template": b_cnt.path_template},
                    )
                )

        # 4. Assess Breaking Change Classification
        has_removed_ep = any(ac.endpoint_removed for ac in api_changes)
        has_changed_path = any(ac.path_changed or ac.method_changed for ac in api_changes)

        client_calls = all_client_calls or []
        client_matches = False
        for ac in api_changes:
            norm_old_path = normalize_url_path(ac.old_path or ac.path)
            for cc in client_calls:
                norm_call_url = normalize_url_path(cc.url)
                if norm_old_path and (norm_old_path == norm_call_url or norm_call_url in norm_old_path or norm_old_path in norm_call_url):
                    client_matches = True
                    break

        if has_removed_ep or (has_changed_path and client_matches):
            overall_classification = ChangeClassification.POTENTIALLY_BREAKING.value
        elif api_changes or contract_changes:
            overall_classification = ChangeClassification.STRUCTURAL_CHANGE.value
        else:
            overall_classification = ChangeClassification.NON_BREAKING_CHANGE.value

        return api_changes, contract_changes, overall_classification
