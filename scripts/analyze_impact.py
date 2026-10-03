"""CLI script to run Code Impact Analysis on target symbols."""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path for direct CLI execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.analysis.impact_service import CodeImpactAnalysisService
from app.models.entities import ImpactAnalysisRequest
from app.utils.logger import logger


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Codebase Graph Intelligence - Code Impact Analysis CLI")
    parser.add_argument("--symbol", "-s", required=True, help="Target symbol name or qualified name to analyze")
    parser.add_argument("--repository", "-r", default=None, help="Target repository identifier or filter")
    parser.add_argument("--max-hops", type=int, default=2, help="Maximum graph traversal depth (default: 2)")
    parser.add_argument("--max-nodes", type=int, default=50, help="Maximum total nodes to evaluate (default: 50)")

    args = parser.parse_args()

    logger.info(f"Running Code Impact Analysis for symbol: '{args.symbol}'")

    service = CodeImpactAnalysisService()
    request = ImpactAnalysisRequest(
        symbol=args.symbol,
        repository_id=args.repository,
        max_hops=args.max_hops,
        max_nodes=args.max_nodes,
    )

    result = service.analyze_impact(request)

    print("\n" + "=" * 60)
    print("CODE IMPACT ANALYSIS REPORT")
    print("=" * 60)
    print(f"Target Symbol : {result.target.qualified_name}")
    print(f"Target File   : {result.target.file_path}:{result.target.start_line or 1}-{result.target.end_line or 1}")
    print(f"Symbol Type   : {result.target.symbol_type}")
    print("-" * 60)
    print("STRUCTURAL IMPACT METRICS:")
    print(f"  - Direct Upstream Dependents   : {result.summary.direct_dependents_count}")
    print(f"  - Transitive Upstream Dependents: {result.summary.transitive_dependents_count}")
    print(f"  - Direct Downstream Dependencies : {result.summary.direct_dependencies_count}")
    print(f"  - Transitive Dependencies      : {result.summary.transitive_dependencies_count}")
    print(f"  - Total Affected Files        : {result.summary.affected_files_count}")
    print(f"  - Total Affected Symbols      : {result.summary.affected_symbols_count}")
    print(f"  - Analysis Truncated          : {result.summary.analysis_truncated}")
    print("-" * 60)
    print("AFFECTED FILES:")
    for f in result.affected_files:
        print(f"  - {f}")
    print("-" * 60)
    print("DIRECT UPSTREAM DEPENDENTS (Who relies on target?):")
    for dep in result.direct_dependents:
        print(f"  - {dep.name} ({dep.symbol_type}) in {dep.file_path}:{dep.start_line or 1} [{dep.relationship_type}]")
    print("-" * 60)
    print("LLM GROUNDED EXPLANATION:")
    print(result.explanation)
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
