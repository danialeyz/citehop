"use client";
// Custom React Flow node and edge renderers for the read-only explorer.
import { BaseEdge, EdgeLabelRenderer, Handle, Position, useInternalNode, type Edge, type EdgeProps, type InternalNode, type Node, type NodeProps } from "@xyflow/react";

import { NODE_SIZE, type GNode } from "@/lib/graph/model";

export type NodeData = {
  node: GNode;
  degree: number;
  tier: 0 | 1 | 2;
  isSeed: boolean;
  sourceRank: number | null; // best rank in the current search highlight
  pathStep: number | null;
  categories: number; // category memberships visible in this view
  maintenance: boolean;
  dimmed: boolean;
  active: boolean;
};
export type FlowNode = Node<NodeData, "article" | "category">;

export type EdgeData = { label: string; showLabel: boolean; onPath: boolean; dimmed: boolean; kind: "LINKS_TO" | "IN_CATEGORY" };
export type FlowEdge = Edge<EdgeData, "floating">;

// Edges attach to the card border, so handles are only anchors React Flow requires.
const hiddenHandle = { opacity: 0, width: 1, height: 1, minWidth: 0, minHeight: 0, border: 0, top: "50%", left: "50%", pointerEvents: "none" as const };

function Handles() {
  return (
    <>
      <Handle type="target" position={Position.Top} isConnectable={false} style={hiddenHandle} />
      <Handle type="source" position={Position.Bottom} isConnectable={false} style={hiddenHandle} />
    </>
  );
}

const TIER_BORDER = ["border", "border-2", "border-[3px]"] as const;

export function ArticleNodeView({ data }: NodeProps<FlowNode>) {
  const node = data.node;
  if (node.kind !== "article") return null;
  const ring = data.active
    ? "border-accent shadow-[0_0_0_4px_rgba(119,228,240,0.25)]"
    : data.pathStep !== null
      ? "border-accent"
      : data.isSeed
        ? "border-accent/80"
        : data.sourceRank !== null
          ? "border-source"
          : "border-line-strong";
  return (
    <div
      className={`relative flex h-full w-full cursor-pointer flex-col justify-center gap-0.5 rounded-xl bg-card px-3 py-1.5 transition-opacity ${TIER_BORDER[data.tier]} ${ring} ${data.dimmed ? "opacity-25" : ""}`}
      style={{ width: NODE_SIZE.article.width, height: NODE_SIZE.article.height }}
      title={`${node.title} · ${data.degree} connections in this view`}
    >
      <Handles />
      <div className="absolute -top-2.5 left-2 flex gap-1">
        {data.isSeed && <Badge tone="accent">Seed</Badge>}
        {data.sourceRank !== null && <Badge tone="source">Source #{data.sourceRank}</Badge>}
        {data.pathStep !== null && <Badge tone="accent">Path {data.pathStep}</Badge>}
      </div>
      <p className="flex items-start gap-1.5 text-[12.5px] font-medium leading-tight text-ink">
        <span aria-hidden className="mt-px text-accent">▤</span>
        <span className="line-clamp-2 [overflow-wrap:anywhere]">{node.title}</span>
      </p>
      <p className="pl-[18px] font-mono text-[10px] text-muted">
        {data.degree} in view{data.categories ? ` · ${data.categories} cat.` : ""}
      </p>
    </div>
  );
}

export function CategoryNodeView({ data }: NodeProps<FlowNode>) {
  const node = data.node;
  if (node.kind !== "category") return null;
  return (
    <div
      className={`flex h-full w-full cursor-pointer items-center gap-1.5 rounded-full bg-amber-tint px-3 text-amber transition-opacity ${TIER_BORDER[data.tier]} ${
        data.active ? "border-amber shadow-[0_0_0_4px_rgba(240,198,116,0.25)]" : data.maintenance ? "border-dashed border-amber/40" : "border-amber/60"
      } ${data.dimmed ? "opacity-25" : ""}`}
      style={{ width: NODE_SIZE.category.width, height: NODE_SIZE.category.height }}
      title={`Category: ${node.name}${data.maintenance ? " (likely Wikipedia maintenance)" : ""} · ${data.degree} connections in this view`}
    >
      <Handles />
      <span aria-hidden className="text-[11px]">◆</span>
      <span className="truncate text-[11.5px]">{node.name}</span>
    </div>
  );
}

function Badge({ tone, children }: { tone: "accent" | "source"; children: React.ReactNode }) {
  const tones = { accent: "bg-accent text-page", source: "bg-source text-page" };
  return <span className={`rounded px-1.5 py-px font-mono text-[9.5px] font-semibold uppercase tracking-wide ${tones[tone]}`}>{children}</span>;
}

export const nodeTypes = { article: ArticleNodeView, category: CategoryNodeView };

// --- floating edge: straight line between card borders, arrow at the target ---------------

function borderPoint(from: InternalNode, to: InternalNode) {
  const w = (from.measured.width ?? 0) / 2;
  const h = (from.measured.height ?? 0) / 2;
  const cx = from.internals.positionAbsolute.x + w;
  const cy = from.internals.positionAbsolute.y + h;
  const tx = to.internals.positionAbsolute.x + (to.measured.width ?? 0) / 2;
  const ty = to.internals.positionAbsolute.y + (to.measured.height ?? 0) / 2;
  const dx = tx - cx;
  const dy = ty - cy;
  if (dx === 0 && dy === 0) return { x: cx, y: cy };
  const scale = 1 / Math.max(Math.abs(dx) / (w + 4), Math.abs(dy) / (h + 4));
  return { x: cx + dx * scale, y: cy + dy * scale };
}

export function FloatingEdge({ id, source, target, markerEnd, style, data }: EdgeProps<FlowEdge>) {
  const from = useInternalNode(source);
  const to = useInternalNode(target);
  if (!from || !to || !data) return null;
  const s = borderPoint(from, to);
  const t = borderPoint(to, from);
  const path = `M ${s.x},${s.y} L ${t.x},${t.y}`;
  const labelX = (s.x + t.x) / 2;
  const labelY = (s.y + t.y) / 2;
  // Keep the label upright; the arrow in it always points at the target.
  const angle = (Math.atan2(t.y - s.y, t.x - s.x) * 180) / Math.PI;
  const flipped = angle > 90 || angle < -90;
  const text = flipped ? `← ${data.label}` : `${data.label} →`;
  return (
    <>
      <BaseEdge id={id} path={path} markerEnd={markerEnd} style={style} className={data.onPath ? "citehop-path-edge" : undefined} />
      {data.showLabel && (
        <EdgeLabelRenderer>
          <div
            className={`nodrag nopan pointer-events-none absolute rounded border px-1.5 py-px font-mono text-[10px] ${
              data.kind === "IN_CATEGORY" ? "border-amber/40 bg-page text-amber" : "border-accent/40 bg-page text-accent-soft"
            }`}
            style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px) rotate(${flipped ? angle + 180 : angle}deg)` }}
          >
            {text}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

export const edgeTypes = { floating: FloatingEdge };
