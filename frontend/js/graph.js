/**
 * Interactive Cytoscape.js Graph Visualization Component.
 * Optimized for high-density graph readability, zero label collision, clear inspection,
 * and seamless full-screen inspection overlay.
 */

import { state } from "./state.js";

let cyInstance = null;
let cyFullscreenInstance = null;
let currentGraphData = null;
let currentHighlightedIds = [];

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

const CYTOSCAPE_STYLES = [
  {
    selector: "node",
    style: {
      label: "data(name)",
      color: "#f8fafc",
      "font-size": "10.5px",
      "font-family": "Inter, sans-serif",
      "font-weight": "600",
      "text-valign": "bottom",
      "text-margin-y": 6,
      "background-color": "data(color)",
      width: "30px",
      height: "30px",
      "border-width": 2.5,
      "border-color": "#090d16",
      "text-background-color": "#070a12",
      "text-background-opacity": 0.88,
      "text-background-padding": "3px",
      "text-background-shape": "roundrectangle",
      "text-border-color": "#1e293b",
      "text-border-width": 1,
      "text-border-opacity": 0.8,
      "text-max-width": "120px",
      "text-wrap": "ellipsis",
    },
  },
  {
    selector: "node:selected",
    style: {
      "border-width": 4,
      "border-color": "#3b82f6",
      "shadow-blur": 14,
      "shadow-color": "#3b82f6",
      "shadow-opacity": 0.9,
      "text-background-color": "#1e293b",
      "text-border-color": "#3b82f6",
      "text-border-width": 1.5,
    },
  },
  {
    selector: "node.highlighted",
    style: {
      "border-width": 3.5,
      "border-color": "#10b981",
      width: "36px",
      height: "36px",
      "shadow-blur": 12,
      "shadow-color": "#10b981",
      "shadow-opacity": 0.8,
    },
  },
  {
    selector: "edge",
    style: {
      width: 1.8,
      label: "data(type)",
      "font-size": "9px",
      "font-family": "Fira Code, monospace",
      "font-weight": "500",
      color: "#94a3b8",
      "line-color": "#283548",
      "target-arrow-color": "#3b4d66",
      "target-arrow-shape": "triangle",
      "arrow-scale": 1.1,
      "curve-style": "bezier",
      "text-rotation": "autorotate",
      "text-background-color": "#0b0f19",
      "text-background-opacity": 0.92,
      "text-background-padding": "2.5px",
      "text-background-shape": "roundrectangle",
      "text-border-color": "#1e293b",
      "text-border-width": 1,
      "text-border-opacity": 0.7,
      "edge-distances": "node-overhead",
      opacity: 0.85,
    },
  },
  {
    selector: "edge.highlighted",
    style: {
      width: 3.2,
      "line-color": "#10b981",
      "target-arrow-color": "#10b981",
      color: "#34d399",
      "text-background-color": "#064e3b",
      "text-border-color": "#10b981",
      opacity: 1,
    },
  },
];

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
    minZoom: 0.2,
    maxZoom: 3.5,
    style: CYTOSCAPE_STYLES,
    elements: [],
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
  currentGraphData = graphData;

  if (!cyInstance) {
    initGraphVisualization();
  }
  if (!cyInstance) return;

  if (!graphData || !graphData.nodes || graphData.nodes.length === 0) {
    cyInstance.elements().remove();
    if (cyFullscreenInstance) cyFullscreenInstance.elements().remove();
    return;
  }

  const cyNodes = graphData.nodes.map((n) => {
    const label = (Array.isArray(n.labels) && n.labels.length > 0)
      ? n.labels[0]
      : (n.label || n.symbol_type || "Node");
    const color = NODE_COLORS[label] || NODE_COLORS.default;
    const displayName = n.name || n.qualified_name || n.file_path || n.id || "Symbol";
    const truncatedName = displayName.length > 24 ? displayName.substring(0, 21) + "..." : displayName;

    return {
      data: {
        id: String(n.id || n.symbol_id || displayName),
        name: truncatedName,
        fullName: displayName,
        label: label,
        symbolType: n.symbol_type || label,
        qualifiedName: n.qualified_name || n.name || "",
        filePath: n.file_path || "",
        language: n.language || "",
        startLine: typeof n.start_line === "number" ? n.start_line : 1,
        endLine: typeof n.end_line === "number" ? n.end_line : 1,
        color: color,
        raw: n,
      },
    };
  });

  const validNodeIds = new Set(cyNodes.map((n) => n.data.id));

  const cyEdges = (graphData.relationships || [])
    .filter((r) => validNodeIds.has(String(r.source)) && validNodeIds.has(String(r.target)))
    .map((r, idx) => ({
      data: {
        id: String(r.id || `edge_${r.source}_${r.type || 'REL'}_${r.target}_${idx}`),
        source: String(r.source),
        target: String(r.target),
        type: r.type || "REL",
        raw: r,
      },
    }));

  const allElements = [...cyNodes, ...cyEdges];

  cyInstance.batch(() => {
    cyInstance.elements().remove();
    cyInstance.add(allElements);
  });

  const layout = cyInstance.layout({
    name: "cose",
    animate: false,
    padding: 35,
    nodeRepulsion: () => 900000,
    idealEdgeLength: () => 90,
    edgeElasticity: () => 80,
    nestingFactor: 1.2,
    gravity: 0.15,
    numIter: 1000,
  });
  layout.run();

  if (cyFullscreenInstance) {
    cyFullscreenInstance.batch(() => {
      cyFullscreenInstance.elements().remove();
      cyFullscreenInstance.add(allElements);
    });
    const fsLayout = cyFullscreenInstance.layout({
      name: "cose",
      animate: false,
      padding: 60,
      nodeRepulsion: () => 1200000,
      idealEdgeLength: () => 120,
      edgeElasticity: () => 80,
      nestingFactor: 1.2,
      gravity: 0.12,
      numIter: 1000,
    });
    fsLayout.run();
  }
}

export function highlightPath(pathNodeIds = []) {
  currentHighlightedIds = pathNodeIds || [];
  applyHighlight(cyInstance, currentHighlightedIds);
  if (cyFullscreenInstance) {
    applyHighlight(cyFullscreenInstance, currentHighlightedIds);
  }
}

function applyHighlight(instance, pathNodeIds) {
  if (!instance) return;
  instance.batch(() => {
    instance.elements().removeClass("highlighted");
    if (!pathNodeIds || pathNodeIds.length === 0) return;

    const idStrs = pathNodeIds.map((id) => String(id));
    idStrs.forEach((id) => {
      const node = instance.getElementById(id);
      if (node) node.addClass("highlighted");
    });

    for (let i = 0; i < idStrs.length - 1; i++) {
      const src = idStrs[i];
      const tgt = idStrs[i + 1];
      const edges = instance.edges(`[source = "${src}"][target = "${tgt}"], [source = "${tgt}"][target = "${src}"]`);
      edges.addClass("highlighted");
    }
  });
}

export function resetGraphZoom() {
  if (cyInstance) {
    cyInstance.fit(undefined, 30);
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

/* Fullscreen Graph Modal Controller */
export function openGraphFullscreen() {
  const overlay = document.getElementById("graph-fullscreen-overlay");
  const fsCanvas = document.getElementById("cy-canvas-fullscreen");
  if (!overlay || !fsCanvas) return;

  overlay.style.display = "flex";

  if (!cyFullscreenInstance) {
    cyFullscreenInstance = window.cytoscape({
      container: fsCanvas,
      boxSelectionEnabled: false,
      autounselectify: false,
      minZoom: 0.15,
      maxZoom: 4.0,
      style: CYTOSCAPE_STYLES,
      elements: [],
    });

    cyFullscreenInstance.on("tap", "node", (evt) => {
      const node = evt.target;
      const nodeData = node.data();
      state.setSelectedNode(nodeData);
    });

    cyFullscreenInstance.on("tap", (evt) => {
      if (evt.target === cyFullscreenInstance) {
        state.setSelectedNode(null);
      }
    });
  }

  // Populate fullscreen elements from current graph data or cyInstance
  if (currentGraphData) {
    updateGraphData(currentGraphData);
  } else if (cyInstance) {
    const json = cyInstance.json();
    cyFullscreenInstance.json(json);
  }

  setTimeout(() => {
    if (cyFullscreenInstance) {
      cyFullscreenInstance.resize();
      cyFullscreenInstance.fit(undefined, 50);
      if (currentHighlightedIds.length > 0) {
        applyHighlight(cyFullscreenInstance, currentHighlightedIds);
      }
    }
  }, 50);

  window.addEventListener("keydown", handleFullscreenEsc);
}

export function closeGraphFullscreen() {
  const overlay = document.getElementById("graph-fullscreen-overlay");
  if (overlay) {
    overlay.style.display = "none";
  }
  window.removeEventListener("keydown", handleFullscreenEsc);
  if (cyInstance) {
    setTimeout(() => {
      cyInstance.resize();
      cyInstance.fit(undefined, 30);
    }, 50);
  }
}

function handleFullscreenEsc(e) {
  if (e.key === "Escape") {
    closeGraphFullscreen();
  }
}

export function fsZoomIn() {
  if (cyFullscreenInstance) {
    cyFullscreenInstance.zoom(cyFullscreenInstance.zoom() * 1.2);
  }
}

export function fsZoomOut() {
  if (cyFullscreenInstance) {
    cyFullscreenInstance.zoom(cyFullscreenInstance.zoom() * 0.8);
  }
}

export function fsResetZoom() {
  if (cyFullscreenInstance) {
    cyFullscreenInstance.fit(undefined, 50);
  }
}
