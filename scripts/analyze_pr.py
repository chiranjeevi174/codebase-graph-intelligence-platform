#!/usr/bin/env python3
"""CLI utility for executing Pull/Merge Request evidence-backed structural analysis."""

import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.pr.models import PRAnalysisRequest
from app.pr.service import PRAnalysisService
from app.utils.logger import logger


def main():
    parser = argparse.ArgumentParser(description="Codebase Graph Intelligence Platform - PR Analysis CLI")
    parser.add_argument(
        "--provider", type=str, default="github", choices=["github", "gitlab"], help="PR Provider platform"
    )
    parser.add_argument("--repository", type=str, required=True, help="Repository name or slug (e.g. owner/repo)")
    parser.add_argument("--pr", type=int, default=1, help="Pull/Merge Request number")
    parser.add_argument("--repo-path", type=str, default=".", help="Path to local Git repository")
    parser.add_argument("--base-ref", type=str, default="HEAD~1", help="Base Git reference")
    parser.add_argument("--target-ref", type=str, default="HEAD", help="Target Git reference")
    parser.add_argument(
        "--dry-run", action="store_true", default=True, help="Run analysis without posting platform comment"
    )
    parser.add_argument("--max-hops", type=int, default=3, help="Maximum graph traversal depth")
    parser.add_argument("--json", action="store_true", help="Output raw JSON analysis result")

    args = parser.parse_args()

    request = PRAnalysisRequest(
        provider=args.provider,
        repository=args.repository,
        pr_number=args.pr,
        repo_path=args.repo_path,
        base_ref=args.base_ref,
        target_ref=args.target_ref,
        dry_run=args.dry_run,
        max_hops=args.max_hops,
    )

    service = PRAnalysisService()
    try:
        result = service.analyze_pr(request)
        if args.json:
            print(json.dumps(result.model_dump(), indent=2))
        else:
            print("=" * 60)
            print(f"PR Analysis Complete for {result.repository} #{result.pr_number}")
            print("=" * 60)
            print(f"Run ID: {result.analysis_run_id}")
            print(f"Changed Files: {result.summary.changed_files_count}")
            print(f"Changed Symbols: {result.summary.changed_symbols_count}")
            print(f"Signature Changes: {result.summary.signature_changes_count}")
            print(f"API Changes: {result.summary.api_changes_count}")
            print(f"Affected Files: {result.summary.affected_files_count}")
            print(f"Validation Status: {'Validated' if result.validation_status else 'Review Suggested'}")
            print("\nExplanation Summary:")
            print(result.explanation)
    except Exception as e:  # noqa: BLE001 — Top-level CLI script entry point exception handler
        logger.error(f"PR Analysis CLI failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
