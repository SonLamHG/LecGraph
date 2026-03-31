"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getVideos, getConcepts, type Video, type Concept } from "@/lib/api";

export default function DashboardPage() {
  const [videos, setVideos] = useState<Video[]>([]);
  const [concepts, setConcepts] = useState<Concept[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getVideos().catch(() => []),
      getConcepts(0, 10).catch(() => []),
    ]).then(([v, c]) => {
      setVideos(v);
      setConcepts(c);
      setLoading(false);
    });
  }, []);

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-text-muted text-sm mt-1">
          Lecture videos transformed into searchable knowledge graphs
        </p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard label="Videos" value={videos.length} href="/graph" />
        <StatCard label="Concepts" value={concepts.length + "+"} href="/graph" />
        <StatCard label="Search" value="Semantic" href="/search" />
      </div>

      {/* Videos */}
      <section>
        <h2 className="text-lg font-semibold mb-3">Videos</h2>
        {loading ? (
          <div className="text-text-muted text-sm">Loading...</div>
        ) : videos.length === 0 ? (
          <div className="bg-surface rounded-lg p-8 text-center text-text-muted">
            No videos yet. Process a video to get started.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {videos.map((v) => (
              <Link
                key={v.id}
                href={`/video/${v.id}`}
                className="bg-surface rounded-lg p-4 hover:bg-surface-light transition-colors border border-border"
              >
                <div className="font-medium truncate">{v.title}</div>
                <div className="text-text-muted text-xs mt-1 flex items-center gap-2">
                  <StatusBadge status={v.status} />
                  <span>{Math.round(v.duration)}s</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>

      {/* Top Concepts */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold">Top Concepts</h2>
          <Link href="/graph" className="text-primary-light text-sm hover:underline">
            View all
          </Link>
        </div>
        {loading ? (
          <div className="text-text-muted text-sm">Loading...</div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {concepts.map((c) => (
              <Link
                key={c.name}
                href={`/graph?concept=${encodeURIComponent(c.name)}`}
                className="bg-surface px-3 py-1.5 rounded-full text-sm border border-border hover:border-primary-light transition-colors"
              >
                {c.name}
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function StatCard({ label, value, href }: { label: string; value: string | number; href: string }) {
  return (
    <Link
      href={href}
      className="bg-surface rounded-lg p-4 border border-border hover:border-primary/50 transition-colors"
    >
      <div className="text-text-muted text-xs uppercase tracking-wider">{label}</div>
      <div className="text-2xl font-bold mt-1">{value}</div>
    </Link>
  );
}

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    completed: "bg-accent-green/20 text-accent-green",
    processing: "bg-accent-amber/20 text-accent-amber",
    pending: "bg-accent-blue/20 text-accent-blue",
    failed: "bg-accent-red/20 text-accent-red",
  };
  return (
    <span className={`px-2 py-0.5 rounded text-xs ${colors[status] || "bg-surface-lighter text-text-muted"}`}>
      {status}
    </span>
  );
}
