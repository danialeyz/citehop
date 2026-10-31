"use client";
// React Flow surface. Positions come from the deterministic layout in lib/graph/model;
// nothing here moves, creates, or deletes nodes or edges.
import { Background, BackgroundVariant, Controls, MarkerType, MiniMap, Panel, ReactFlow, ReactFlowProvider, useReactFlow } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useEffect, useMemo, useState } from "react";

import { NODE_SIZE, degreeTier, isMaintenanceCategory, neighborhoodOf, viewDegree, type GEdge, type GNode, type Pos } from "@/lib/graph/model";

import { edgeTypes, nodeTypes, type FlowEdge, type FlowNode } from "./flow-parts";

export type Selection = { kind: "node"; id: string } | { kind: "edge"; id: string } | null;

type Props = {
  nodes: GNode[];
  edges: GEdge[];
  positions: Record<string, Pos>;
  seed: string;
  selection: Selection;
  sourceRanks: Map<number, number>;
  pathNodes: string[];
  pathEdges: Set<string>;
  fitKey: string; // changes when the view should be refitted (new seed, reset, back)
  onSelect: (selection: Selection) => void;
};

export function GraphCanvas(props: Props) {
  return (
    <ReactFlowProvider>
      <Canvas {...props} />
    </ReactFlowProvider>
  );
}

const ACCENT = "#77e4f0";
const AMBER = "#f0c674";
const LINE = "#4d6b8c";
const MAX_LABELS = 12;

function useDesktop() {
  const [desktop, setDesktop] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(min-width: 768px)");
    const update = () => setDesktop(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return desktop;
}

function Canvas({ nodes, edges, positions, seed, selection, sourceRanks, pathNodes, pathEdges, fitKey, onSelect }: Props) {
  const { fitView } = useReactFlow();
  const desktop = useDesktop();
  const [hoverEdge, setHoverEdge] = useState<string | null>(null);

  const flowNodes = useMemo<FlowNode[]>(() => {
    const degree = viewDegree(edges);
    const selectedNode = selection?.kind === "node" ? selection.id : null;
    const selectedEdge = selection?.kind === "edge" ? edges.find((e) => e.id === selection.id) : undefined;
    const focus = selectedNode ? neighborhoodOf(selectedNode, edges) : selectedEdge ? new Set([selectedEdge.source, selectedEdge.target]) : null;
    const categoriesOf = new Map<string, number>();
    for (const e of edges) if (e.type === "IN_CATEGORY") categoriesOf.set(e.source, (categoriesOf.get(e.source) ?? 0) + 1);
    return nodes.map((node) => {
      const size = NODE_SIZE[node.kind];
      const pos = positions[node.id] ?? { x: 0, y: 0 };
      const d = degree.get(node.id) ?? 0;
      const step = pathNodes.indexOf(node.id);
      return {
        id: node.id,
        type: node.kind,
        position: { x: pos.x - size.width / 2, y: pos.y - size.height / 2 },
        width: size.width,
        height: size.height,
        draggable: false,
        connectable: false,
        selectable: false,
        ariaLabel: node.kind === "article" ? `Article ${node.title}` : `Category ${node.name}`,
        data: {
          node,
          degree: d,
          tier: degreeTier(d),
          isSeed: node.id === seed,
          sourceRank: node.kind === "article" ? (sourceRanks.get(node.article_id) ?? null) : null,
          pathStep: step >= 0 ? step : null,
          categories: categoriesOf.get(node.id) ?? 0,
          maintenance: node.kind === "category" && isMaintenanceCategory(node.name),
          dimmed: focus !== null && !focus.has(node.id),
          active: node.id === selectedNode,
        },
      };
    });
  }, [nodes, edges, positions, seed, selection, sourceRanks, pathNodes]);

  const flowEdges = useMemo<FlowEdge[]>(() => {
    const selectedNode = selection?.kind === "node" ? selection.id : null;
    const selectedEdge = selection?.kind === "edge" ? selection.id : null;
    // Label every edge of the selected node only while that stays readable.
    const labelTouching = selectedNode !== null && edges.filter((e) => e.source === selectedNode || e.target === selectedNode).length <= MAX_LABELS;
    return edges.map((edge) => {
      const touches = selectedNode !== null && (edge.source === selectedNode || edge.target === selectedNode);
      const onPath = pathEdges.has(edge.id);
      const isCategory = edge.type === "IN_CATEGORY";
      const emphasized = touches || onPath || edge.id === selectedEdge || edge.id === hoverEdge;
      const dimmed = (selectedNode !== null || selectedEdge !== null) && !emphasized;
      const color = onPath ? ACCENT : isCategory ? AMBER : emphasized ? ACCENT : LINE;
      return {
        id: edge.id,
        source: edge.source,
        target: edge.target,
        type: "floating",
        selectable: false,
        focusable: false,
        zIndex: emphasized ? 1 : 0,
        markerEnd: { type: MarkerType.ArrowClosed, color, width: 16, height: 16 },
        style: {
          stroke: color,
          strokeWidth: onPath ? 3 : emphasized ? 2 : 1.2,
          strokeDasharray: isCategory && !onPath ? "4 4" : undefined,
          opacity: dimmed ? 0.12 : isCategory && !emphasized ? 0.55 : 0.85,
        },
        data: {
          label: isCategory ? "in category" : "links to",
          showLabel: onPath || edge.id === selectedEdge || edge.id === hoverEdge || (touches && labelTouching),
          onPath,
          dimmed,
          kind: edge.type,
        },
      };
    });
  }, [edges, selection, pathEdges, hoverEdge]);

  // Refit only on a new exploration, reset, or back; expansion keeps the viewport still.
  useEffect(() => {
    const frame = requestAnimationFrame(() => fitView({ padding: 0.15, duration: 0, maxZoom: 1.2 }));
    return () => cancelAnimationFrame(frame);
  }, [fitKey, fitView]);

  return (
    <ReactFlow
      nodes={flowNodes}
      edges={flowEdges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      onNodeClick={(_, node) => onSelect({ kind: "node", id: node.id })}
      onEdgeClick={(_, edge) => onSelect({ kind: "edge", id: edge.id })}
      onEdgeMouseEnter={(_, edge) => setHoverEdge(edge.id)}
      onEdgeMouseLeave={() => setHoverEdge(null)}
      onPaneClick={() => onSelect(null)}
      nodesDraggable={false}
      nodesConnectable={false}
      nodesFocusable={false}
      edgesFocusable={false}
      edgesReconnectable={false}
      elementsSelectable={false}
      deleteKeyCode={null}
      selectionKeyCode={null}
      multiSelectionKeyCode={null}
      minZoom={0.1}
      maxZoom={2}
      fitView
      fitViewOptions={{ padding: 0.15, maxZoom: 1.2 }}
      proOptions={{ hideAttribution: false }}
      colorMode="dark"
      style={{ background: "var(--color-page)" }}
      aria-label="Knowledge graph canvas"
    >
      <Background variant={BackgroundVariant.Dots} gap={24} size={1} color="#1f3248" />
      <Controls showInteractive={false} position="bottom-left" aria-label="Zoom and fit controls" />
      {desktop && (
        <MiniMap
          pannable
          zoomable
          position="bottom-right"
          ariaLabel="Graph overview"
          bgColor="#0c1524"
          maskColor="rgba(8,15,28,0.7)"
          nodeColor={(n) => ((n as FlowNode).data.node.kind === "category" ? AMBER : (n as FlowNode).data.isSeed ? ACCENT : "#34506e")}
          nodeStrokeWidth={0}
        />
      )}
      <Panel position="top-left" className="!m-2 rounded-md border border-line bg-page/85 px-2 py-1 font-mono text-[11px] text-muted">
        {nodes.length} nodes · {edges.length} edges
      </Panel>
    </ReactFlow>
  );
}
