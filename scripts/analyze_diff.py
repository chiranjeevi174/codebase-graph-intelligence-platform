"""CLI script for running Structural Git Diff and Change Impact Analysis."""

import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.diff.diff_analyzer import StructuralDiffAnalyzer
from app.diff.diff_models import DiffRequest


def main():
    parser = argparse.ArgumentParser(description="Analyze structural Git diff and static change impact.")
    parser.add_argument("--repo", type=str, default=".", help="Path to Git repository root")
    parser.add_argument("--base", type=str, required=True, help="Base Git ref (e.g. HEAD~1, main, commit SHA)")
    parser.add_argument("--target", type=str, required=True, help="Target Git ref (e.g. HEAD, feature branch, commit SHA)")
    parser.add_argument("--repo-id", type=str, default="default", help="Repository identifier")
    parser.add_argument("--max-hops", type=int, default=3, help="Maximum graph traversal depth")
    parser.add_argument("--max-nodes", type=int, default=50, help="Maximum nodes in impact subgraph")
    parser.add_argument("--json", action="store_true", help="Output raw JSON result")

    args = parser.parse_args()

    request = DiffRequest(
        repository_id=args.repo_id,
        repo_path=args.repo,
        base_ref=args.base,
        target_ref=args.target,
        max_hops=args.max_hops,
        max_nodes=args.max_nodes,
    )

    analyzer = StructuralDiffAnalyzer()
    result = analyzer.analyze_diff(request)

    if args.json:
        print(json.dumps(result.model_dump(), indent=2))
    else:
        print("=" * 60)
        print("STRUCTURAL GIT DIFF & CHANGE IMPACT ANALYSIS")
        print("=" * 60)
        print(f"Repository: {result.repository_id}")
        print(f"Base Ref: {result.base_ref} ({result.structural_diff.base_commit_hash[:8]})")
        print(f"Target Ref: {result.target_ref} ({result.structural_diff.target_commit_hash[:8]})")
        print(f"Risk Classification: {result.classification}")
        print("-" * 60)
        print(f"Files Changed: {len(result.structural_diff.files_changed)}")
        print(f"Symbols Changed: {len(result.structural_diff.symbols_changed)}")
        print(f"Graph Relationships Changed: {len(result.structural_diff.relationships_changed)}")
        print(f"API Changes: {len(result.structural_diff.api_changes)}")
        print(f"Affected Files Count: {len(result.affected_files)}")
        print("-" * 60)
        if result.explanation:
            print("EXPLANATION:")
            print(result.explanation)
        print("=" * 60)


if __name__ == "__main__":
    main()
