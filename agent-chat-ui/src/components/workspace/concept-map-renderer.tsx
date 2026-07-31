"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import dagre from "@dagrejs/dagre";
import {
  Background,
  BaseEdge,
  Controls,
  EdgeLabelRenderer,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  type Edge,
  type EdgeProps,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import { ListTree, MessageCircle, Network, Volume2 } from "lucide-react";
import type {
  ConceptMapArtifact,
  ConceptMapNode,
} from "@/lib/visual/jasper-response.generated";
import { Button } from "@/components/ui/button";
import { useTTS } from "@/hooks/useTTS";

const NODE_WIDTH = 240;
const NODE_HEIGHT = 104;
const FEEDBACK_LANE_GAP = 56;
const FEEDBACK_LANE_SEPARATION = 36;

type ConceptNodeData = {
  label: string;
  detail?: string | null;
  kind: string;
  claimStatus: string;
  evidenceLabels: string[];
  active?: boolean;
};

const NODE_KIND_STYLES: Record<string, string> = {
  input: "border-blue-500/60 bg-blue-500/12",
  output: "border-emerald-500/60 bg-emerald-500/12",
  code: "border-violet-500/60 bg-violet-500/12",
  group: "border-amber-500/60 bg-amber-500/12",
  concept: "border-primary/60 bg-primary/10",
};

function ConceptNode({ data }: NodeProps<Node<ConceptNodeData>>) {
  const kindStyle = NODE_KIND_STYLES[data.kind] ?? NODE_KIND_STYLES.concept;
  return (
    <div
      className={`text-card-foreground w-60 rounded-xl border-2 px-4 py-3 shadow-md transition-[box-shadow,transform] ${kindStyle} ${data.active ? "ring-primary scale-[1.03] shadow-xl ring-4" : ""}`}
      data-active-node={data.active ? "true" : "false"}
    >
      <Handle
        type="target"
        position={Position.Left}
        className="!border-background !bg-foreground"
      />
      <div className="text-muted-foreground mb-1 text-[10px] font-semibold tracking-wider uppercase">
        {data.kind} · {data.claimStatus.replace("_", " ")}
      </div>
      <div className="text-sm font-semibold">{data.label}</div>
      {data.detail && (
        <div className="text-muted-foreground mt-1 line-clamp-3 text-xs">
          {data.detail}
        </div>
      )}
      <div className="text-muted-foreground mt-2 text-[10px]">
        Sources {data.evidenceLabels.join(", ")}
      </div>
      <Handle
        type="source"
        position={Position.Right}
        className="!border-background !bg-foreground"
      />
      <Handle
        id="feedback-target-top"
        type="target"
        position={Position.Top}
        className="!border-background !bg-foreground"
      />
      <Handle
        id="feedback-source-top"
        type="source"
        position={Position.Top}
        className="!border-background !bg-foreground"
      />
      <Handle
        id="feedback-target-bottom"
        type="target"
        position={Position.Bottom}
        className="!border-background !bg-foreground"
      />
      <Handle
        id="feedback-source-bottom"
        type="source"
        position={Position.Bottom}
        className="!border-background !bg-foreground"
      />
    </div>
  );
}

const nodeTypes = { concept: ConceptNode };

type FeedbackEdgeData = { laneY: number };

function FeedbackEdge({
  sourceX,
  sourceY,
  targetX,
  targetY,
  markerEnd,
  style,
  label,
  data,
}: EdgeProps) {
  const laneY = (data as FeedbackEdgeData | undefined)?.laneY ?? sourceY;
  const edgePath = [
    `M ${sourceX} ${sourceY}`,
    `L ${sourceX} ${laneY}`,
    `L ${targetX} ${laneY}`,
    `L ${targetX} ${targetY}`,
  ].join(" ");

  return (
    <>
      <BaseEdge
        path={edgePath}
        markerEnd={markerEnd}
        style={style}
        className="concept-map-feedback-edge"
      />
      {label && (
        <EdgeLabelRenderer>
          <div
            className="border-border bg-card text-foreground pointer-events-none absolute rounded-md border px-1.5 py-1 text-[11px] font-semibold shadow-sm"
            style={{
              transform: `translate(-50%, -50%) translate(${(sourceX + targetX) / 2}px, ${laneY}px)`,
            }}
          >
            {label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

const edgeTypes = { feedback: FeedbackEdge };

function createsCycle(
  adjacency: Map<string, Set<string>>,
  source: string,
  target: string,
): boolean {
  const pending = [target];
  const visited = new Set<string>();
  while (pending.length > 0) {
    const current = pending.pop();
    if (!current || visited.has(current)) continue;
    if (current === source) return true;
    visited.add(current);
    for (const next of adjacency.get(current) ?? []) pending.push(next);
  }
  return false;
}

function layoutArtifact(artifact: ConceptMapArtifact): {
  nodes: Node<ConceptNodeData>[];
  edges: Edge[];
} {
  const graph = new dagre.graphlib.Graph();
  graph.setDefaultEdgeLabel(() => ({}));
  graph.setGraph({
    rankdir: artifact.payload.direction === "top_to_bottom" ? "TB" : "LR",
    ranksep: 120,
    nodesep: 72,
    marginx: 24,
    marginy: 24,
    ranker: "network-simplex",
  });

  for (const node of artifact.payload.nodes) {
    graph.setNode(node.id, { width: NODE_WIDTH, height: NODE_HEIGHT });
  }
  const layoutAdjacency = new Map<string, Set<string>>();
  const feedbackEdgeIndexes = new Set<number>();
  for (const [index, edge] of (artifact.payload.edges ?? []).entries()) {
    if (createsCycle(layoutAdjacency, edge.source, edge.target)) {
      feedbackEdgeIndexes.add(index);
      continue;
    }
    graph.setEdge(edge.source, edge.target);
    const targets = layoutAdjacency.get(edge.source) ?? new Set<string>();
    targets.add(edge.target);
    layoutAdjacency.set(edge.source, targets);
  }
  dagre.layout(graph);

  const nodes = artifact.payload.nodes.map((node) => {
    const position = graph.node(node.id);
    return {
      id: node.id,
      type: "concept",
      position: {
        x: position.x - NODE_WIDTH / 2,
        y: position.y - NODE_HEIGHT / 2,
      },
      data: {
        label: node.label,
        detail: node.detail,
        kind: node.kind ?? "concept",
        claimStatus: node.claim_status,
        evidenceLabels: node.evidence_refs.map((ref) => {
          const index = artifact.payload.sources.findIndex(
            (source) => source.id === ref,
          );
          return index >= 0 ? `[${index + 1}]` : "[?]";
        }),
      },
      ariaLabel: `${node.kind ?? "concept"}: ${node.label}`,
      draggable: false,
      selectable: true,
    } satisfies Node<ConceptNodeData>;
  });
  const nodeKinds = new Map(
    artifact.payload.nodes.map((node) => [node.id, node.kind ?? "concept"]),
  );
  const positions = new Map(nodes.map((node) => [node.id, node.position]));
  let topLaneCount = 0;
  let bottomLaneCount = 0;
  const edges = (artifact.payload.edges ?? []).map((edge, index) => {
    const isToolBranch =
      edge.label?.trim().toLowerCase() === "executes" ||
      (edge.relation === "calls" && nodeKinds.get(edge.target) === "output");
    const stroke = isToolBranch ? "var(--muted-foreground)" : "var(--primary)";
    const sourcePosition = positions.get(edge.source);
    const targetPosition = positions.get(edge.target);
    const isFeedback =
      feedbackEdgeIndexes.has(index) ||
      (sourcePosition &&
        targetPosition &&
        targetPosition.x <= sourcePosition.x);
    let feedbackProps = {};
    if (isFeedback && sourcePosition && targetPosition) {
      const left = Math.min(sourcePosition.x, targetPosition.x);
      const right = Math.max(sourcePosition.x, targetPosition.x) + NODE_WIDTH;
      const blockers = nodes.filter((node) => {
        const centerX = node.position.x + NODE_WIDTH / 2;
        return centerX >= left && centerX <= right;
      });
      const topBoundary = Math.min(...blockers.map((node) => node.position.y));
      const bottomBoundary = Math.max(
        ...blockers.map((node) => node.position.y + NODE_HEIGHT),
      );
      const topLane =
        topBoundary -
        FEEDBACK_LANE_GAP -
        topLaneCount * FEEDBACK_LANE_SEPARATION;
      const bottomLane =
        bottomBoundary +
        FEEDBACK_LANE_GAP +
        bottomLaneCount * FEEDBACK_LANE_SEPARATION;
      const topCost =
        Math.abs(sourcePosition.y - topLane) +
        Math.abs(targetPosition.y - topLane);
      const bottomCost =
        Math.abs(sourcePosition.y + NODE_HEIGHT - bottomLane) +
        Math.abs(targetPosition.y + NODE_HEIGHT - bottomLane);
      const useTopLane = topCost <= bottomCost;
      const side = useTopLane ? "top" : "bottom";
      const laneY = useTopLane ? topLane : bottomLane;
      if (useTopLane) topLaneCount += 1;
      else bottomLaneCount += 1;
      feedbackProps = {
        type: "feedback",
        sourceHandle: `feedback-source-${side}`,
        targetHandle: `feedback-target-${side}`,
        data: { laneY },
      };
    }
    return {
      id: `${edge.source}-${edge.target}-${index}`,
      source: edge.source,
      target: edge.target,
      label: edge.label ?? undefined,
      type: "smoothstep",
      ...feedbackProps,
      markerEnd: { type: MarkerType.ArrowClosed, color: stroke },
      style: {
        stroke,
        strokeWidth: isToolBranch ? 1.75 : 2.5,
        strokeDasharray: isToolBranch ? "6 5" : undefined,
      },
      labelStyle: {
        fill: "var(--foreground)",
        fontSize: 11,
        fontWeight: 600,
      },
      labelBgStyle: {
        fill: "var(--card)",
        fillOpacity: 0.98,
        stroke: "var(--border)",
        strokeWidth: 1,
      },
      labelBgPadding: [6, 4],
      labelBgBorderRadius: 5,
      ariaLabel: `${edge.source} ${edge.relation ?? "relates to"} ${edge.target}`,
    } satisfies Edge;
  });
  return { nodes, edges };
}

function OutlineNode({
  node,
  sourceNumbers,
}: {
  node: ConceptMapNode;
  sourceNumbers: Map<string, number>;
}) {
  return (
    <li className="rounded-md border p-3">
      <div className="flex items-baseline justify-between gap-3">
        <span className="font-medium">{node.label}</span>
        <span className="text-muted-foreground text-xs uppercase">
          {node.kind ?? "concept"} · {node.claim_status.replace("_", " ")}
        </span>
      </div>
      {node.detail && (
        <p className="text-muted-foreground mt-1 text-sm">{node.detail}</p>
      )}
      <p className="text-muted-foreground mt-2 text-xs">
        Sources:{" "}
        {node.evidence_refs
          .map((ref) => `[${sourceNumbers.get(ref) ?? "?"}]`)
          .join(", ")}
      </p>
    </li>
  );
}

export function ConceptMapRenderer({
  artifact,
  selectedVoice,
}: {
  artifact: ConceptMapArtifact;
  selectedVoice?: string;
}) {
  const [showOutline, setShowOutline] = useState(false);
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const { speak, stop: stopTts, speaking } = useTTS();
  const graph = useMemo(() => layoutArtifact(artifact), [artifact]);
  const displayedNodes = useMemo(
    () =>
      graph.nodes.map((node) => ({
        ...node,
        data: { ...node.data, active: node.id === activeNodeId },
      })),
    [activeNodeId, graph.nodes],
  );
  const sourceNumbers = useMemo(
    () =>
      new Map(
        artifact.payload.sources.map((source, index) => [source.id, index + 1]),
      ),
    [artifact],
  );
  const nodeLabels = useMemo(
    () => new Map(artifact.payload.nodes.map((node) => [node.id, node.label])),
    [artifact],
  );
  const selectedNode = artifact.payload.nodes.find(
    (node) => node.id === selectedNodeId,
  );

  useEffect(() => {
    const handleNarration = (event: Event) => {
      const detail = (event as CustomEvent).detail as {
        artifactId?: string;
        nodeId?: string;
      } | null;
      if (!detail) {
        setActiveNodeId(null);
      } else if (detail.artifactId === artifact.artifact_id) {
        setActiveNodeId(detail.nodeId ?? null);
      }
    };
    const stopNodeAudio = () => {
      stopTts();
      setActiveNodeId(null);
    };
    window.addEventListener("visual:narration-node", handleNarration);
    window.addEventListener("jasper:stop-node-audio", stopNodeAudio);
    return () => {
      window.removeEventListener("visual:narration-node", handleNarration);
      window.removeEventListener("jasper:stop-node-audio", stopNodeAudio);
    };
  }, [artifact.artifact_id, stopTts]);

  const playNode = useCallback(
    async (nodeId: string) => {
      const node = artifact.payload.nodes.find((item) => item.id === nodeId);
      if (!node) return;
      window.dispatchEvent(new Event("jasper:stop-message-narration"));
      setSelectedNodeId(nodeId);
      setActiveNodeId(nodeId);
      await speak(node.narration, selectedVoice || undefined);
      setActiveNodeId(null);
    },
    [artifact.payload.nodes, selectedVoice, speak],
  );

  const discussNode = useCallback(() => {
    if (!selectedNode) return;
    const sourceLocators = artifact.payload.sources
      .filter((source) => selectedNode.evidence_refs.includes(source.id))
      .map((source) => source.locator);
    const prompt = [
      `Let’s explore the “${selectedNode.label}” node from “${artifact.title}” more deeply.`,
      `Its status is ${selectedNode.claim_status.replace("_", " ")}.`,
      `Use its existing evidence (${sourceLocators.join(", ")}) and gather more grounded evidence if needed.`,
      "Explain what it does, why it matters, and how it connects to the surrounding nodes. Preserve the distinction between observed, researched, user-defined, proposed, and inferred claims.",
    ].join(" ");
    window.dispatchEvent(
      new CustomEvent("jasper:discuss-node", { detail: { prompt } }),
    );
  }, [artifact, selectedNode]);

  return (
    <section
      className="bg-muted/20 relative h-full min-h-0"
      aria-label={artifact.title}
    >
      <div className="absolute top-3 right-3 z-10">
        <Button
          size="sm"
          variant="secondary"
          onClick={() => setShowOutline((value) => !value)}
          aria-pressed={showOutline}
        >
          {showOutline ? (
            <Network className="size-4" />
          ) : (
            <ListTree className="size-4" />
          )}
          {showOutline ? "Map" : "Outline"}
        </Button>
      </div>

      {showOutline ? (
        <div className="h-full overflow-y-auto p-6 pt-14">
          <p className="text-muted-foreground mb-4 text-sm">
            {artifact.alt_text}
          </p>
          <ol className="space-y-2">
            {artifact.payload.nodes.map((node) => (
              <OutlineNode
                key={node.id}
                node={node}
                sourceNumbers={sourceNumbers}
              />
            ))}
          </ol>
          {(artifact.payload.edges?.length ?? 0) > 0 && (
            <>
              <h3 className="mt-6 mb-2 font-semibold">Relationships</h3>
              <ol className="space-y-2">
                {artifact.payload.edges?.map((edge, index) => (
                  <li
                    key={`${edge.source}-${edge.target}-${index}`}
                    className="rounded-md border p-3 text-sm"
                  >
                    <div>
                      {nodeLabels.get(edge.source)} →{" "}
                      {nodeLabels.get(edge.target)}
                    </div>
                    <div className="text-muted-foreground mt-1 text-xs">
                      {(edge.label || edge.relation || "relates to").replaceAll(
                        "_",
                        " ",
                      )}{" "}
                      · {edge.claim_status.replace("_", " ")} · Sources{" "}
                      {edge.evidence_refs
                        .map((ref) => `[${sourceNumbers.get(ref) ?? "?"}]`)
                        .join(", ")}
                    </div>
                  </li>
                ))}
              </ol>
            </>
          )}
          <h3 className="mt-6 mb-2 font-semibold">Sources</h3>
          <ol className="space-y-2">
            {artifact.payload.sources.map((source, index) => (
              <li
                key={source.id}
                className="rounded-md border p-3 text-sm"
              >
                <div className="font-medium">
                  [{index + 1}] {source.title}
                </div>
                {source.kind === "web_url" ? (
                  <a
                    href={source.locator}
                    target="_blank"
                    rel="noreferrer"
                    className="text-primary mt-1 block text-xs break-all underline"
                  >
                    {source.locator}
                  </a>
                ) : (
                  <div className="text-muted-foreground mt-1 text-xs break-all">
                    {source.locator}
                  </div>
                )}
              </li>
            ))}
          </ol>
        </div>
      ) : (
        <ReactFlow
          nodes={displayedNodes}
          edges={graph.edges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          fitViewOptions={{ padding: 0.16, minZoom: 0.35, maxZoom: 1 }}
          minZoom={0.25}
          maxZoom={1.5}
          nodesConnectable={false}
          elementsSelectable
          proOptions={{ hideAttribution: false }}
          aria-label={artifact.alt_text}
          className="concept-map-flow"
          onNodeClick={(_event, node) => void playNode(node.id)}
        >
          <Background
            gap={20}
            size={1}
          />
          <Controls
            showInteractive={false}
            className="!border-border !overflow-hidden !rounded-lg !border !shadow-md"
          />
        </ReactFlow>
      )}
      {selectedNode && !showOutline && (
        <aside className="bg-background/95 absolute right-3 bottom-3 z-20 w-80 rounded-lg border p-3 shadow-lg backdrop-blur">
          <div className="pr-2 text-sm font-semibold">{selectedNode.label}</div>
          <div className="text-muted-foreground mt-1 text-xs uppercase">
            {selectedNode.claim_status.replace("_", " ")} · Sources{" "}
            {selectedNode.evidence_refs
              .map((ref) => `[${sourceNumbers.get(ref) ?? "?"}]`)
              .join(", ")}
          </div>
          <p className="mt-2 line-clamp-3 text-sm">{selectedNode.narration}</p>
          <div className="mt-3 flex gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                if (speaking) {
                  stopTts();
                  setActiveNodeId(null);
                } else {
                  void playNode(selectedNode.id);
                }
              }}
            >
              <Volume2 className="size-4" />
              {speaking ? "Stop" : "Replay"}
            </Button>
            <Button
              size="sm"
              onClick={discussNode}
            >
              <MessageCircle className="size-4" />
              Discuss with Jasper
            </Button>
          </div>
        </aside>
      )}
    </section>
  );
}
