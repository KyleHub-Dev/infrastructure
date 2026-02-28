import { useState, useEffect, useRef, useCallback, Component, type ReactNode, type ErrorInfo } from "react";
import cytoscape, { type Core, type ElementDefinition, type StylesheetJsonBlock } from "cytoscape";
import type { GraphData } from "../lib/api";
import { entityColors } from "../lib/constants";
import { Panel, Heading } from "./Panel";

/* ------------------------------------------------------------------ */
/*  Graph-local error boundary (crashes stay in the panel)            */
/* ------------------------------------------------------------------ */

class GraphErrorBoundary extends Component<
  { children: ReactNode },
  { error: Error | null; key: number }
> {
  state = { error: null as Error | null, key: 0 };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Graph render error:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
          <span className="text-xs text-error">Graph failed to render</span>
          <button
            className="text-xs px-3 py-1.5 bg-secondary border border-border rounded-md text-foreground hover:bg-secondary/80 transition-colors"
            onClick={() => this.setState((s) => ({ error: null, key: s.key + 1 }))}
          >
            Retry
          </button>
        </div>
      );
    }
    return <div key={this.state.key} className="absolute inset-0">{this.props.children}</div>;
  }
}

/* ------------------------------------------------------------------ */
/*  Cytoscape stylesheet                                              */
/* ------------------------------------------------------------------ */

const DEFAULT_NODE_COLOR = "#7a7a8e";

const cytoscapeStyle: StylesheetJsonBlock[] = [
  {
    selector: "node",
    style: {
      "background-color": DEFAULT_NODE_COLOR,
      label: "",
      width: "data(size)",
      height: "data(size)",
      "font-size": 10,
      color: "#8a92a8",
      "text-valign": "bottom",
      "text-halign": "center",
      "text-margin-y": 4,
      "text-outline-width": 2,
      "text-outline-color": "#18181b",
    },
  },
  {
    selector: "node[color]",
    style: {
      "background-color": "data(color)",
    },
  },
  {
    selector: "node.show-label",
    style: {
      label: "data(label)",
    },
  },
  {
    selector: "node.highlighted",
    style: {
      label: "data(label)",
      "border-width": 2,
      "border-color": "#8b5cf6",
    },
  },
  {
    selector: ".dimmed",
    style: {
      opacity: 0.12,
    },
  },
  {
    selector: "edge",
    style: {
      width: 1,
      "line-color": "#4c5366",
      "target-arrow-color": "#4c5366",
      "target-arrow-shape": "triangle",
      "curve-style": "bezier",
      label: "",
      "font-size": 8,
      color: "#7a8299",
      "text-rotation": "autorotate",
      "text-outline-width": 2,
      "text-outline-color": "#18181b",
    },
  },
  {
    selector: "edge.show-label",
    style: {
      label: "data(label)",
    },
  },
];

/* ------------------------------------------------------------------ */
/*  Build Cytoscape elements from API graph data                      */
/* ------------------------------------------------------------------ */

function buildElements(data: GraphData): ElementDefinition[] {
  const elements: ElementDefinition[] = [];

  for (const node of data.nodes) {
    elements.push({
      data: {
        id: node.id,
        label: node.label,
        color: entityColors[node.type] ?? DEFAULT_NODE_COLOR,
        size: (node.size || 6) * 3,
        type: node.type,
        tool_source: node.tool_source ?? "",
      },
    });
  }

  for (const edge of data.edges) {
    elements.push({
      data: {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        label: edge.label,
      },
    });
  }

  return elements;
}

/* ------------------------------------------------------------------ */
/*  Selected node info type                                           */
/* ------------------------------------------------------------------ */

interface SelectedNodeInfo {
  label: string;
  type: string;
  tool_source: string;
  neighbors: number;
}

/* ------------------------------------------------------------------ */
/*  CytoscapeGraph – imperative wrapper with interactions             */
/* ------------------------------------------------------------------ */

function CytoscapeGraph({
  data,
  onCyReady,
  onNodeSelect,
}: {
  data: GraphData;
  onCyReady: (cy: Core) => void;
  onNodeSelect: (info: SelectedNodeInfo | null) => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    cyRef.current?.destroy();

    const cy = cytoscape({
      container: containerRef.current,
      elements: buildElements(data),
      style: cytoscapeStyle,
      layout: { name: "preset" },
    });

    // Run COSE layout after init so the container has dimensions
    cy.layout({
      name: "cose",
      animate: true,
      animationDuration: 800,
      fit: true,
      padding: 50,
      nodeRepulsion: () => 4500,
      idealEdgeLength: () => 100,
      gravity: 0.4,
      numIter: 1500,
      randomize: true,
      componentSpacing: 80,
      nestingFactor: 1.2,
      edgeElasticity: () => 100,
    } as cytoscape.LayoutOptions).run();

    // Show labels when zoomed in
    cy.on("zoom", () => {
      const zoom = cy.zoom();
      if (zoom > 1.5) {
        cy.nodes().addClass("show-label");
        cy.edges().addClass("show-label");
      } else {
        cy.nodes().removeClass("show-label");
        cy.edges().removeClass("show-label");
      }
    });

    // Click node → highlight neighborhood
    cy.on("tap", "node", (evt) => {
      const node = evt.target;
      cy.elements().removeClass("dimmed highlighted show-label");

      const neighborhood = node.closedNeighborhood();
      cy.elements().not(neighborhood).addClass("dimmed");
      neighborhood.addClass("highlighted");
      neighborhood.nodes().addClass("show-label");
      neighborhood.edges().addClass("show-label");

      onNodeSelect({
        label: node.data("label"),
        type: node.data("type") ?? "Observable",
        tool_source: node.data("tool_source") ?? "",
        neighbors: node.neighborhood("node").length,
      });
    });

    // Click background → clear selection
    cy.on("tap", (evt) => {
      if (evt.target === cy) {
        cy.elements().removeClass("dimmed highlighted show-label");
        onNodeSelect(null);
      }
    });

    cyRef.current = cy;
    onCyReady(cy);

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [data, onCyReady, onNodeSelect]);

  return (
    <div
      ref={containerRef}
      style={{ position: "absolute", inset: 0, backgroundColor: "#18181b" }}
    />
  );
}

/* ------------------------------------------------------------------ */
/*  Zoom control buttons                                              */
/* ------------------------------------------------------------------ */

const zoomBtnClass =
  "w-7 h-7 bg-card/90 border border-border/50 rounded text-xs text-foreground hover:bg-secondary transition-colors flex items-center justify-center";

function ZoomControls({ cy }: { cy: Core | null }) {
  return (
    <div className="absolute top-2 right-2 flex flex-col gap-1 z-10">
      <button
        className={zoomBtnClass}
        onClick={() => cy?.zoom({ level: (cy.zoom() ?? 1) * 1.3, renderedPosition: { x: (cy.width() ?? 0) / 2, y: (cy.height() ?? 0) / 2 } })}
        title="Zoom in"
      >+</button>
      <button
        className={zoomBtnClass}
        onClick={() => cy?.zoom({ level: (cy.zoom() ?? 1) / 1.3, renderedPosition: { x: (cy.width() ?? 0) / 2, y: (cy.height() ?? 0) / 2 } })}
        title="Zoom out"
      >&ndash;</button>
      <button
        className={zoomBtnClass}
        onClick={() => cy?.fit(undefined, 50)}
        title="Fit to view"
      >&#x2922;</button>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  GraphPanel                                                        */
/* ------------------------------------------------------------------ */

interface GraphPanelProps {
  graphData: GraphData | null;
  graphLoading: boolean;
  selectedInv: string | null;
  selectedStatus: string | undefined;
}

export function GraphPanel({ graphData, graphLoading, selectedInv, selectedStatus }: GraphPanelProps) {
  const [cyInstance, setCyInstance] = useState<Core | null>(null);
  const [selectedNode, setSelectedNode] = useState<SelectedNodeInfo | null>(null);

  const handleCyReady = useCallback((cy: Core) => setCyInstance(cy), []);
  const handleNodeSelect = useCallback((info: SelectedNodeInfo | null) => setSelectedNode(info), []);

  // Clear selection when data changes
  useEffect(() => { setSelectedNode(null); }, [graphData]);

  return (
    <div className="p-3 flex flex-col overflow-hidden">
      <Panel className="flex-1 flex flex-col overflow-hidden">
        <Heading>Network Graph</Heading>
        <div className="flex-1 relative min-h-0 bg-background/50 rounded-md border border-border/30">
          {graphLoading ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-xs text-muted-foreground animate-pulse">Loading graph...</span>
            </div>
          ) : !selectedInv ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-xs text-muted-foreground">Select an investigation</span>
            </div>
          ) : !graphData || graphData.nodes.length === 0 ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-xs text-muted-foreground">
                {selectedStatus === "pending" ? "Waiting for workers..." : "No graph data"}
              </span>
            </div>
          ) : (
            <>
              <GraphErrorBoundary>
                <CytoscapeGraph
                  data={graphData}
                  onCyReady={handleCyReady}
                  onNodeSelect={handleNodeSelect}
                />
              </GraphErrorBoundary>
              <ZoomControls cy={cyInstance} />
            </>
          )}
        </div>

        {selectedNode && (
          <div className="flex items-center gap-3 px-3 py-2 mt-2 bg-secondary/50 border border-border/30 rounded-md text-xs">
            <span
              className="w-3 h-3 rounded-full shrink-0"
              style={{ backgroundColor: entityColors[selectedNode.type] ?? DEFAULT_NODE_COLOR }}
            />
            <span className="font-mono font-medium text-foreground truncate max-w-[40%]">{selectedNode.label}</span>
            <span className="text-muted-foreground">{selectedNode.type}</span>
            {selectedNode.tool_source && (
              <span className="text-muted-foreground">via {selectedNode.tool_source}</span>
            )}
            <span className="text-muted-foreground ml-auto shrink-0">{selectedNode.neighbors} connections</span>
          </div>
        )}

        <div className="flex flex-wrap gap-3 pt-3 border-t border-border/50 mt-3">
          {Object.entries(entityColors).map(([type, color]) => (
            <div key={type} className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: color }} />
              <span className="text-[10px] text-muted-foreground">{type}</span>
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
