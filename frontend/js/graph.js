/**
 * Interactive Cytoscape.js Graph Visualization Component.
 */

import { state } from "./state.js";

let cyInstance = null;

const NODE_COLORS = {
  File: "#60a5fa",
  Class: "#c084fc",
  Function: "#34d399",
  Method: "#34d399",
  ApiEndpoint: "#fbbf24",
  ApiClientCall: "#f472b6",
  ApiContract: "#38bdf8",
  Repository: "#a855f7",
  default: "#94a3b8",
};

export function initGraphVisualization(containerId = "cy-canvas") {
  const container = document.getElementById(containerId);
  if (!container) return;

  if (typeof window.cytoscape === "undefined") {
    container.innerHTML = `<div style="padding:20px; color:#94a3b8; text-align:center;">Cytoscape graph library loading...</div>`;
    return;
  }

  cyInstance = window.cytoscape({
    container: container,
    boxSelectionEnabled: false,
    autounselectify: false,
    style: [
      {
        selector: "node",
        style: {
          label: "data(name)",
          color: "#f1f5f9",
          "font-size": "11px",
          "font-weight": "600",
          "text-valign": "bottom",
          "text-margin-y": 5,
          "background-color": "data(color)",
          width: "28px",
          height: "28px",
          "border-width": 2,
          "border-color": "#1e293b",
          "overlay-padding": "4px",
        },
      },
      {
        selector: "node:selected",
        style: {
          "border-width": 4,
          "border-color": "#3b82f6",
          "shadow-blur": 10,
          "shadow-color": "#3b82f6",
          "shadow-opacity": 0.8,
        },
      },
      {
        selector: "node.highlighted",
        style: {
          "border-width": 3,
          "border-color": "#10b981",
          width: "34px",
          height: "34px",
        },
      },
      {
        selector: "edge",
        style: {
          width: 2,
          label: "data(type)",
          "font-size": "9px",
          color: "#64748b",
          "line-color": "#334155",
          "target-arrow-color": "#475569",
          "target-arrow-shape": "triangle",
          "curve-style": "bezier",
          "text-rotation": "autorotate",
          "opacity": 0.85,
        },
      },
      {
        selector: "edge.highlighted",
        style: {
          width: 3,
          "line-color": "#10b981",
          "target-arrow-color": "#10b981",
          opacity: 1,
        },
      },
    ],
    elements: [],
    layout: {
      name: "cose",
      animate: false,
      padding: 30,
    },
  });

  cyInstance.on("tap", "node", (evt) => {
    const node = evt.target;
    const nodeData = node.data();
    state.setSelectedNode(nodeData);
  });

  cyInstance.on("tap", (evt) => {
    if (evt.target === cyInstance) {
      state.setSelectedNode(null);
    }
  });

  return cyInstance;
}

export function updateGraphData(graphData) {
  if (!cyInstance) {
    initGraphVisualization();
  }
  if (!cyInstance) return;

  if (!graphData || !graphData.nodes || graphData.nodes.length === 0) {
    cyInstance.elements().remove();
    return;
  }

  const cyNodes = graphData.nodes.map((n) => {
    const label = n.label || n.symbol_type || "Node";
    const color = NODE_COLORS[label] || NODE_COLORS.default;
    const displayName = n.name || n.qualified_name || n.file_path || n.id;
    return {
      data: {
        id: String(n.id),
        name: displayName.length > 25 ? displayName.substring(0, 22) + "..." : displayName,
        fullName: displayName,
        label: label,
        qualifiedName: n.qualified_name || "",
        filePath: n.file_path || "",
        language: n.language || "",
        symbolType: n.symbol_type || label,
        startLine: n.start_line || 1,
        endLine: n.end_line || 1,
        color: color,
        raw: n,
      },
    };
  });

  const validNodeIds = new Set(cyNodes.map((n) => n.data.id));

  const cyEdges = (graphData.relationships || [])
    .filter((r) => validNodeIds.has(String(r.source)) && validNodeIds.has(String(r.target)))
    .map((r) => ({
      data: {
        id: String(r.id || `${r.source}_${r.type}_${r.target}`),
        source: String(r.source),
        target: String(r.target),
        type: r.type || "REL",
        raw: r,
      },
    }));

  cyInstance.batch(() => {
    cyInstance.elements().remove();
    cyInstance.add([...cyNodes, ...cyEdges]);
  });

  const layout = cyInstance.layout({
    name: "cose",
    animate: false,
    padding: 30,
    nodeRepulsion: () => 400000,
    idealEdgeLength: () => 60,
  });
  layout.run();
}

export function highlightPath(pathNodeIds = []) {
  if (!cyInstance) return;
  cyInstance.batch(() => {
    cyInstance.elements().removeClass("highlighted");
    if (!pathNodeIds || pathNodeIds.length === 0) return;

    const idStrs = pathNodeIds.map((id) => String(id));
    idStrs.forEach((id) => {
      const node = cyInstance.getElementById(id);
      if (node) node.addClass("highlighted");
    });

    for (let i = 0; i < idStrs.length - 1; i++) {
      const src = idStrs[i];
      const tgt = idStrs[i + 1];
      const edges = cyInstance.edges(`[source = "${src}"][target = "${tgt}"], [source = "${tgt}"][target = "${src}"]`);
      edges.addClass("highlighted");
    }
  });
}

export function resetGraphZoom() {
  if (cyInstance) {
    cyInstance.fit();
  }
}

export function zoomIn() {
  if (cyInstance) {
    cyInstance.zoom(cyInstance.zoom() * 1.2);
  }
}

export function zoomOut() {
  if (cyInstance) {
    cyInstance.zoom(cyInstance.zoom() * 0.8);
  }
}
