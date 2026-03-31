"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import cytoscape, { type Core, type EventObject } from "cytoscape";
import { type ConceptDetail, getGraphData, getConceptDetail } from "@/lib/api";
import { conceptTypeColor, importanceColor } from "@/lib/utils";

const PAGE_SIZE = 50;

interface GraphExplorerProps {
  initialConcept?: string;
  onConceptSelect?: (concept: ConceptDetail) => void;
}

export function GraphExplorer({ initialConcept, onConceptSelect }: GraphExplorerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [selectedConcept, setSelectedConcept] = useState<ConceptDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadedCount, setLoadedCount] = useState(0);
  const [hasMore, setHasMore] = useState(true);
  const loadedNamesRef = useRef<Set<string>>(new Set());

  const addElementsToGraph = useCallback((
    concepts: { name: string; type: string; importance: string; definition: string }[],
    relationships: { source: string; target: string; type: string }[],
  ) => {
    const cy = cyRef.current;
    if (!cy) return;

    const newNodes = concepts
      .filter((c) => !loadedNamesRef.current.has(c.name))
      .map((c) => ({
        group: "nodes" as const,
        data: {
          id: c.name,
          label: c.name,
          type: c.type,
          importance: c.importance,
          definition: c.definition,
        },
      }));

    for (const c of concepts) {
      loadedNamesRef.current.add(c.name);
    }

    const edgeSet = new Set<string>();
    cy.edges().forEach((e) => edgeSet.add(e.id()));

    const newEdges = relationships
      .filter((r) => {
        const edgeId = `${r.source}-${r.type}-${r.target}`;
        if (edgeSet.has(edgeId)) return false;
        return loadedNamesRef.current.has(r.source) && loadedNamesRef.current.has(r.target);
      })
      .map((r) => ({
        group: "edges" as const,
        data: {
          id: `${r.source}-${r.type}-${r.target}`,
          source: r.source,
          target: r.target,
          label: r.type.replace(/_/g, " ").toLowerCase(),
        },
      }));

    if (newNodes.length > 0 || newEdges.length > 0) {
      cy.add([...newNodes, ...newEdges]);
      cy.layout({
        name: "cose",
        animate: true,
        animationDuration: 500,
        nodeRepulsion: () => 8000,
        idealEdgeLength: () => 120,
        gravity: 0.3,
        padding: 40,
        fit: newNodes.length > 10,
      } as cytoscape.CoseLayoutOptions).run();
    }
  }, []);

  const loadMore = useCallback(async () => {
    if (!hasMore) return;
    try {
      const data = await getGraphData(loadedCount, PAGE_SIZE);
      if (data.concepts.length < PAGE_SIZE) {
        setHasMore(false);
      }
      addElementsToGraph(data.concepts, data.relationships);
      setLoadedCount((prev) => prev + data.concepts.length);
    } catch (e) {
      console.error("Failed to load more concepts:", e);
    }
  }, [loadedCount, hasMore, addElementsToGraph]);

  const initGraph = useCallback(async () => {
    try {
      if (!containerRef.current) {
        setLoading(false);
        return;
      }

      // Initial load
      const data = await getGraphData(0, PAGE_SIZE);
      if (data.concepts.length === 0) {
        setLoading(false);
        return;
      }
      if (data.concepts.length < PAGE_SIZE) {
        setHasMore(false);
      }

      if (cyRef.current) {
        cyRef.current.destroy();
      }

      const nodes = data.concepts.map((c) => ({
        data: {
          id: c.name,
          label: c.name,
          type: c.type,
          importance: c.importance,
          definition: c.definition,
        },
      }));

      for (const c of data.concepts) {
        loadedNamesRef.current.add(c.name);
      }

      const edges = data.relationships
        .filter((r) => loadedNamesRef.current.has(r.source) && loadedNamesRef.current.has(r.target))
        .map((r) => ({
          data: {
            id: `${r.source}-${r.type}-${r.target}`,
            source: r.source,
            target: r.target,
            label: r.type.replace(/_/g, " ").toLowerCase(),
          },
        }));

      cyRef.current = cytoscape({
        container: containerRef.current,
        elements: [...nodes, ...edges],
        style: [
          {
            selector: "node",
            style: {
              label: "data(label)",
              "text-valign": "bottom",
              "text-halign": "center",
              "font-size": "11px",
              color: "#e2e8f0",
              "text-margin-y": 6,
              "background-color": (ele) => conceptTypeColor(ele.data("type")),
              width: (ele) => {
                const imp = ele.data("importance");
                return imp === "high" ? 40 : imp === "medium" ? 30 : 22;
              },
              height: (ele) => {
                const imp = ele.data("importance");
                return imp === "high" ? 40 : imp === "medium" ? 30 : 22;
              },
              "border-width": 2,
              "border-color": (ele) => importanceColor(ele.data("importance")),
              "text-outline-color": "#11111b",
              "text-outline-width": 2,
            } as cytoscape.Css.Node,
          },
          {
            selector: "node:selected",
            style: {
              "border-width": 3,
              "border-color": "#818cf8",
              "background-color": "#6366f1",
            },
          },
          {
            selector: "edge",
            style: {
              width: 1.5,
              "line-color": "#3a3a52",
              "target-arrow-color": "#3a3a52",
              "target-arrow-shape": "triangle",
              "curve-style": "bezier",
              label: "data(label)",
              "font-size": "9px",
              color: "#64748b",
              "text-rotation": "autorotate",
              "text-outline-color": "#11111b",
              "text-outline-width": 1.5,
            } as cytoscape.Css.Edge,
          },
          {
            selector: "edge:selected",
            style: {
              "line-color": "#818cf8",
              "target-arrow-color": "#818cf8",
              width: 2.5,
            },
          },
        ],
        layout: {
          name: "cose",
          animate: true,
          animationDuration: 800,
          nodeRepulsion: () => 8000,
          idealEdgeLength: () => 120,
          gravity: 0.3,
          padding: 40,
        } as cytoscape.CoseLayoutOptions,
        minZoom: 0.2,
        maxZoom: 4,
      });

      setLoadedCount(data.concepts.length);

      cyRef.current.on("tap", "node", async (evt: EventObject) => {
        const name = evt.target.data("id");
        try {
          const detail = await getConceptDetail(name);
          setSelectedConcept(detail);
          onConceptSelect?.(detail);
        } catch {
          /* ignore */
        }
      });

      cyRef.current.on("tap", (evt: EventObject) => {
        if (evt.target === cyRef.current) {
          setSelectedConcept(null);
        }
      });

      // Focus on initial concept
      if (initialConcept) {
        const node = cyRef.current.getElementById(initialConcept);
        if (node.length) {
          cyRef.current.animate({
            center: { eles: node },
            zoom: 2,
          });
          node.select();
          const detail = await getConceptDetail(initialConcept).catch(() => null);
          if (detail) {
            setSelectedConcept(detail);
            onConceptSelect?.(detail);
          }
        }
      }
    } catch (e) {
      console.error("Failed to load graph:", e);
    } finally {
      setLoading(false);
    }
  }, [initialConcept, onConceptSelect]);

  useEffect(() => {
    initGraph();
    return () => {
      cyRef.current?.destroy();
    };
  }, [initGraph]);

  return (
    <div className="flex h-full">
      {/* Graph Canvas */}
      <div className="flex-1 relative">
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-surface/80 z-10">
            <div className="text-text-muted">Loading graph...</div>
          </div>
        )}
        <div ref={containerRef} className="cy-container h-full" />

        {/* Load More button */}
        {hasMore && !loading && (
          <button
            onClick={loadMore}
            className="absolute top-4 right-4 bg-primary/90 hover:bg-primary text-white text-xs px-3 py-1.5 rounded-lg transition-colors z-10"
          >
            Load more ({loadedCount} loaded)
          </button>
        )}

        {/* Legend */}
        <div className="absolute bottom-4 left-4 bg-surface/90 backdrop-blur rounded-lg p-3 text-xs space-y-1.5 border border-border">
          <div className="font-medium text-text-muted mb-1">Node Types</div>
          {[
            ["Theory", "#a78bfa"],
            ["Technique", "#60a5fa"],
            ["Tool", "#34d399"],
            ["Application", "#fbbf24"],
          ].map(([label, color]) => (
            <div key={label} className="flex items-center gap-2">
              <span className="w-3 h-3 rounded-full inline-block" style={{ backgroundColor: color }} />
              {label}
            </div>
          ))}
        </div>
      </div>

      {/* Concept Detail Panel */}
      {selectedConcept && (
        <div className="w-80 bg-surface border-l border-border p-4 overflow-y-auto">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-lg">{selectedConcept.name}</h3>
            <button
              onClick={() => setSelectedConcept(null)}
              className="text-text-muted hover:text-text"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div className="flex gap-2 mb-3">
            <span className="px-2 py-0.5 rounded text-xs" style={{ backgroundColor: conceptTypeColor(selectedConcept.type) + "33", color: conceptTypeColor(selectedConcept.type) }}>
              {selectedConcept.type || "unknown"}
            </span>
            <span className="px-2 py-0.5 rounded text-xs" style={{ backgroundColor: importanceColor(selectedConcept.importance) + "33", color: importanceColor(selectedConcept.importance) }}>
              {selectedConcept.importance || "unknown"}
            </span>
          </div>

          <p className="text-sm text-text-muted mb-4">{selectedConcept.definition}</p>

          {selectedConcept.aliases.length > 0 && (
            <div className="mb-4">
              <h4 className="text-xs font-medium text-text-muted uppercase tracking-wider mb-1">Aliases</h4>
              <div className="flex flex-wrap gap-1">
                {selectedConcept.aliases.map((a) => (
                  <span key={a} className="px-2 py-0.5 bg-surface-lighter rounded text-xs">{a}</span>
                ))}
              </div>
            </div>
          )}

          {selectedConcept.relationships.length > 0 && (
            <div className="mb-4">
              <h4 className="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">Relationships</h4>
              <div className="space-y-1.5">
                {selectedConcept.relationships.map((r, i) => (
                  <div key={i} className="text-sm flex items-center gap-1.5">
                    <span className="text-primary-light">{r.type.replace(/_/g, " ")}</span>
                    <span className="text-text-muted">&rarr;</span>
                    <button
                      onClick={async () => {
                        const node = cyRef.current?.getElementById(r.target);
                        if (node?.length) {
                          cyRef.current?.animate({ center: { eles: node }, zoom: 2 });
                          node.select();
                        }
                        const detail = await getConceptDetail(r.target).catch(() => null);
                        if (detail) setSelectedConcept(detail);
                      }}
                      className="text-accent-blue hover:underline"
                    >
                      {r.target}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {selectedConcept.segments.length > 0 && (
            <div>
              <h4 className="text-xs font-medium text-text-muted uppercase tracking-wider mb-2">Appears In</h4>
              <div className="space-y-2">
                {selectedConcept.segments.map((s) => (
                  <a
                    key={s.segment_id}
                    href={`/video/${s.video_id}?t=${Math.floor(s.start)}`}
                    className="block bg-surface-light rounded p-2 text-sm hover:bg-surface-lighter transition-colors"
                  >
                    <div className="font-medium truncate">{s.title || s.segment_id}</div>
                    <div className="text-text-muted text-xs">{s.video_title}</div>
                  </a>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
