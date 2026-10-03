"""CLI script for running repository ingestion pipeline."""

import argparse
import sys

from app.ingestion.repository_service import RepositoryIngestionService
from app.utils.logger import logger


def main():
    parser = argparse.ArgumentParser(description="Codebase Graph Intelligence Platform - Repository Ingestion")
    parser.add_argument(
        "--repo",
        type=str,
        required=True,
        help="Local repository path or remote GitHub URL (e.g. https://github.com/owner/repo)",
    )
    parser.add_argument(
        "--branch",
        type=str,
        default=None,
        help="Optional branch name if cloning a remote GitHub repository",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-cloning if GitHub target directory already exists locally",
    )

    args = parser.parse_args()

    logger.info(f"Starting ingestion for repository target: {args.repo}")
    service = RepositoryIngestionService()
    try:
        res = service.ingest_repository(target=args.repo, branch=args.branch, force=args.force)

        print("\n" + "=" * 50)
        print(" REPOSITORY INGESTION SUMMARY REPORT")
        print("=" * 50)
        print(f"Repository Name:            {res.name}")
        print(f"Repository ID:              {res.repository_id}")
        print(f"Source:                     {res.source}")
        print(f"Local Path:                 {res.local_path}")
        print(f"Commit Hash:                {res.commit_hash or 'N/A'}")
        print(f"Status:                     {res.status.upper()}")
        print("-" * 50)
        print(f"Files Discovered:           {res.files_discovered}")
        print(f"Files Processed:            {res.files_processed}")
        print(f"Files Skipped:              {res.files_skipped}")
        print(f"Files Failed:               {res.files_failed}")
        print("-" * 50)
        print(f"Symbols Extracted:          {res.symbols_extracted}")
        print(f"Relationships Extracted:    {res.relationships_extracted}")
        print(f"Code Chunks Created:        {res.chunks_created}")
        print(f"Neo4j Nodes Created:        {res.graph_nodes_created}")
        print(f"Neo4j Rels Created:         {res.graph_relationships_created}")
        print(f"Qdrant Vectors Created:     {res.vectors_created}")
        print("=" * 50)

        if res.errors:
            print("\nWarnings / Errors Encountered:")
            for err in res.errors[:10]:
                print(f" - {err}")
            if len(res.errors) > 10:
                print(f" ... and {len(res.errors) - 10} more errors.")
        print()

    except Exception as e:
        logger.error(f"Repository ingestion failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
