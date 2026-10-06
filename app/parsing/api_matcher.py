"""API Route and Contract Matcher for cross-language evidence linking."""

from app.models.entities import (
    ApiClientCall,
    ApiContract,
    ApiEndpoint,
    ApiMatch,
)
from app.parsing.url_normalizer import match_urls
from app.utils.logger import logger


class APIMatcher:
    """Matches API client calls, backend endpoints, and OpenAPI contracts."""

    def match_api_elements(
        self,
        endpoints: list[ApiEndpoint],
        client_calls: list[ApiClientCall],
        contracts: list[ApiContract],
    ) -> list[ApiMatch]:
        """Perform deterministic matching between client calls, endpoints, and OpenAPI contracts."""
        matches: list[ApiMatch] = []
        seen_matches: set[tuple[str, str]] = set()
        matched_call_ids: set[str] = set()

        # 1. Match ApiClientCall -> ApiEndpoint
        for call in client_calls:
            for ep in endpoints:
                is_match, reason = match_urls(
                    client_url=call.url,
                    client_method=call.http_method,
                    endpoint_path=ep.path,
                    endpoint_method=ep.http_method,
                )
                if is_match:
                    key = (call.call_id, ep.endpoint_id)
                    if key not in seen_matches:
                        seen_matches.add(key)
                        matched_call_ids.add(call.call_id)
                        match_obj = ApiMatch(
                            source_id=call.call_id,
                            target_id=ep.endpoint_id,
                            match_reason=reason,
                            confidence_basis=f"Static match between {call.language} client call and {ep.language} {ep.framework} endpoint",
                            file_path=call.file_path,
                            line_number=call.start_line,
                        )
                        matches.append(match_obj)
                        logger.info(
                            f"[api_match_created] Matched client call {call.http_method} {call.url} -> {ep.http_method} {ep.path} ({reason})"
                        )
                        if call.language != ep.language:
                            logger.info(
                                f"[cross_language_link_created] Linked cross-language API relation between {call.language} ({call.file_path}) and {ep.language} ({ep.file_path})"
                            )

        # Log unresolved client calls
        for call in client_calls:
            if call.call_id not in matched_call_ids:
                logger.info(
                    f"[api_match_unresolved] Unresolved client call {call.http_method} {call.url} in {call.file_path}:{call.start_line}"
                )

        # 2. Match ApiEndpoint -> ApiContract
        for ep in endpoints:
            for c in contracts:
                is_match, reason = match_urls(
                    client_url=ep.path,
                    client_method=ep.http_method,
                    endpoint_path=c.path_template,
                    endpoint_method=c.http_method,
                )
                if is_match or (ep.operation_id and ep.operation_id == c.operation_id):
                    key = (ep.endpoint_id, c.contract_id)
                    if key not in seen_matches:
                        seen_matches.add(key)
                        matches.append(
                            ApiMatch(
                                source_id=ep.endpoint_id,
                                target_id=c.contract_id,
                                match_reason="IMPLEMENTS_CONTRACT",
                                confidence_basis="OpenAPI contract specification match",
                                file_path=ep.file_path,
                                line_number=ep.start_line,
                            )
                        )
                        logger.info(
                            f"[api_match_created] Matched endpoint {ep.qualified_name} -> contract {c.path_template} (IMPLEMENTS_CONTRACT)"
                        )

        # 3. Match ApiClientCall -> ApiContract
        for call in client_calls:
            for c in contracts:
                is_match, reason = match_urls(
                    client_url=call.url,
                    client_method=call.http_method,
                    endpoint_path=c.path_template,
                    endpoint_method=c.http_method,
                )
                if is_match:
                    key = (call.call_id, c.contract_id)
                    if key not in seen_matches:
                        seen_matches.add(key)
                        matches.append(
                            ApiMatch(
                                source_id=call.call_id,
                                target_id=c.contract_id,
                                match_reason="MATCHES_CONTRACT",
                                confidence_basis="OpenAPI contract specification match",
                                file_path=call.file_path,
                                line_number=call.start_line,
                            )
                        )
                        logger.info(
                            f"[api_match_created] Matched client call {call.http_method} {call.url} -> contract {c.path_template} (MATCHES_CONTRACT)"
                        )

        return matches
