"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { GraphExplorer } from "@/components/graph/GraphExplorer";

function GraphContent() {
  const searchParams = useSearchParams();
  const concept = searchParams.get("concept") || undefined;

  return (
    <div className="h-screen flex flex-col">
      <div className="p-4 border-b border-border shrink-0">
        <h1 className="text-xl font-bold">Knowledge Graph</h1>
        <p className="text-text-muted text-sm">
          Explore concepts and their relationships. Click a node to see details.
        </p>
      </div>
      <div className="flex-1 min-h-0">
        <GraphExplorer initialConcept={concept} />
      </div>
    </div>
  );
}

export default function GraphPage() {
  return (
    <Suspense fallback={<div className="p-6 text-text-muted">Loading...</div>}>
      <GraphContent />
    </Suspense>
  );
}
