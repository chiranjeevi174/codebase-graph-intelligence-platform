"""CLI script for inspecting cross-language API flows in Neo4j graph data."""

import argparse

from app.graph.graph_queries import GraphQueryManager


def main():
    parser = argparse.ArgumentParser(description="Analyze cross-language API flow in codebase graph.")
    parser.add_argument("--path", required=True, help="API URL path or symbol identifier (e.g. /api/users)")
    parser.add_argument("--repository", help="Optional repository identifier")
    parser.add_argument("--hops", type=int, default=3, help="Max traversal depth (default 3)")

    args = parser.parse_args()

    qm = GraphQueryManager()
    paths = qm.find_api_flow(identifier=args.path, max_hops=args.hops)

    print(f"=== Cross-Language API Flow for '{args.path}' ===")
    print(f"Total Paths Found: {len(paths)}\n")

    for idx, p in enumerate(paths, 1):
        print(f"Path #{idx} (Hops: {p.get('hop_count')}):")
        nodes = p.get("path_nodes", [])
        rels = p.get("path_relationships", [])

        for i, n in enumerate(nodes):
            name = n.get("name")
            fpath = n.get("file_path")
            lines = f"{n.get('start_line', 1)}-{n.get('end_line', 1)}"
            labels = n.get("labels", [])
            print(f"  [{':'.join(labels)}] {name} ({fpath}:{lines})")
            if i < len(rels):
                print(f"      ↓ -[{rels[i]}]->")
        print()


if __name__ == "__main__":
    main()
