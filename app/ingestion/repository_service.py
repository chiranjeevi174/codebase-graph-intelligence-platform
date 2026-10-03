"""Repository Ingestion Service orchestrating full end-to-end repository indexing."""


from app.embeddings.embedder import EmbeddingService
from app.graph.graph_builder import GraphBuilder
from app.ingestion.git_loader import LocalGitLoader
from app.ingestion.github_loader import GitHubRepositoryLoader
from app.models.entities import IngestionResult
from app.parsing.api_extractor import APIExtractor
from app.parsing.api_matcher import APIMatcher
from app.parsing.parser_factory import ParserFactory
from app.utils.logger import logger


class RepositoryIngestionService:
    """Orchestrates repository ingestion pipeline across parsing, graph building, and vector embedding."""

    def __init__(
        self,
        local_loader: LocalGitLoader | None = None,
        github_loader: GitHubRepositoryLoader | None = None,
        graph_builder: GraphBuilder | None = None,
        embedding_service: EmbeddingService | None = None,
        api_extractor: APIExtractor | None = None,
        api_matcher: APIMatcher | None = None,
    ):
        self.local_loader = local_loader or LocalGitLoader()
        self.github_loader = github_loader or GitHubRepositoryLoader()
        self.graph_builder = graph_builder or GraphBuilder()
        self.embedding_service = embedding_service or EmbeddingService()
        self.api_extractor = api_extractor or APIExtractor()
        self.api_matcher = api_matcher or APIMatcher()

    def ingest_repository(self, target: str, branch: str | None = None, force: bool = False) -> IngestionResult:
        """Run complete end-to-end ingestion pipeline on a local directory path or GitHub URL."""
        logger.info(f"[Ingestion Event: repository_started] Target: {target}")

        # Step 1 & 2: Acquisition & Metadata Identification
        if GitHubRepositoryLoader.is_github_url(target):
            repo_info, source_files = self.github_loader.load_repository(target, branch=branch, force=force)
        else:
            repo_info, source_files = self.local_loader.load_repository(target)

        result = IngestionResult(
            repository_id=repo_info.repository_id,
            name=repo_info.name,
            source=repo_info.source,
            local_path=repo_info.local_path,
            commit_hash=repo_info.commit_hash,
            files_discovered=len(source_files),
        )

        logger.info(f"[Ingestion Event: file_discovered] Discovered {len(source_files)} source files in repository '{repo_info.name}'")

        # Step 3: Create Repository Node in Neo4j
        try:
            self.graph_builder.create_repository_node(repo_info)
            result.graph_nodes_created += 1
        except Exception as ge:
            err_msg = f"Failed to create Repository root node in Neo4j: {ge}"
            logger.warning(err_msg)
            result.errors.append(err_msg)

        all_endpoints = []
        all_client_calls = []
        all_contracts = []

        # Step 4: Iterate each source file safely
        for source_file in source_files:
            try:
                # Get parser for language
                try:
                    parser = ParserFactory.get_parser(source_file.language)
                except Exception as pe:
                    result.files_skipped += 1
                    logger.debug(f"Skipping file {source_file.relative_path}: {pe}")
                    continue

                # Read source content
                with open(source_file.file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                # Step 5 & 6: Entity & Relationship Extraction
                extracted = parser.parse_file(source_file, content, repo_info.repository_id)

                # Extract static API endpoints, client calls, contracts
                eps, calls, contracts = self.api_extractor.extract_from_content(source_file, content, repo_info.repository_id)
                extracted.api_endpoints = eps
                extracted.api_client_calls = calls
                extracted.api_contracts = contracts

                all_endpoints.extend(eps)
                all_client_calls.extend(calls)
                all_contracts.extend(contracts)

                logger.info(f"[Ingestion Event: file_parsed] Parsed {source_file.relative_path}")

                sym_count = len(extracted.symbols)
                rel_count = len(extracted.imports) + len(extracted.calls) + len(extracted.inheritance)
                chunk_count = len(extracted.chunks)
                api_node_count = len(eps) + len(calls) + len(contracts)

                result.symbols_extracted += sym_count + api_node_count
                result.relationships_extracted += rel_count
                result.chunks_created += chunk_count

                logger.info(f"[Ingestion Event: symbols_extracted] Extracted {sym_count} symbols and {api_node_count} API entities from {source_file.relative_path}")
                logger.info(f"[Ingestion Event: relationships_extracted] Extracted {rel_count} relationships from {source_file.relative_path}")

                # Step 7 & 8: Neo4j Graph Construction
                try:
                    self.graph_builder.ingest_extracted_data(extracted)
                    # File node + symbol nodes + API nodes
                    result.graph_nodes_created += 1 + sym_count + api_node_count
                    result.graph_relationships_created += rel_count
                    logger.info(f"[Ingestion Event: graph_upsert_completed] Updated Neo4j graph for {source_file.relative_path}")
                except Exception as ge:
                    logger.warning(f"Neo4j ingestion warning for {source_file.relative_path}: {ge}")
                    result.errors.append(f"Graph error in {source_file.relative_path}: {ge}")

                # Step 9, 10, 11: Embedding Generation & Qdrant Upsert
                if extracted.chunks:
                    try:
                        self.embedding_service.process_and_store_chunks(extracted.chunks)
                        result.vectors_created += chunk_count
                        logger.info(f"[Ingestion Event: qdrant_upsert_completed] Upserted {chunk_count} vectors to Qdrant for {source_file.relative_path}")
                    except Exception as qe:
                        logger.warning(f"Qdrant vectorization warning for {source_file.relative_path}: {qe}")
                        result.errors.append(f"Vector error in {source_file.relative_path}: {qe}")

                result.files_processed += 1

            except Exception as fe:
                result.files_failed += 1
                err_str = f"Error processing file {source_file.relative_path}: {fe}"
                logger.error(err_str)
                result.errors.append(err_str)

        # Cross-file API matching & relationship ingestion
        if all_endpoints or all_client_calls or all_contracts:
            try:
                api_matches = self.api_matcher.match_api_elements(all_endpoints, all_client_calls, all_contracts)
                matched_count = self.graph_builder.ingest_api_matches(api_matches)
                result.graph_relationships_created += matched_count
                result.relationships_extracted += len(api_matches)
                logger.info(f"[Ingestion Event: api_matching_completed] Ingested {matched_count} cross-language API relationships into Neo4j graph")
            except Exception as me:
                logger.warning(f"API matching error: {me}")
                result.errors.append(f"API matching error: {me}")

        logger.info(f"[Ingestion Event: repository_ingestion_completed] Completed ingestion for '{repo_info.name}'. Processed: {result.files_processed}, Failed: {result.files_failed}")
        return result
