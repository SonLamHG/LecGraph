"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  getVideos,
  getConcepts,
  addVideo,
  processVideo,
  type Video,
  type Concept,
} from "@/lib/api";

export default function DashboardPage() {
  const [videos, setVideos] = useState<Video[]>([]);
  const [concepts, setConcepts] = useState<Concept[]>([]);
  const [loading, setLoading] = useState(true);

  // Add video form
  const [source, setSource] = useState("");
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const refresh = useCallback(() => {
    Promise.all([
      getVideos().catch(() => []),
      getConcepts(0, 10).catch(() => []),
    ]).then(([v, c]) => {
      setVideos(v);
      setConcepts(c);
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Poll for status updates while any video is processing
  useEffect(() => {
    const hasProcessing = videos.some((v) => v.status === "processing");
    if (!hasProcessing) return;
    const interval = setInterval(() => {
      getVideos()
        .then(setVideos)
        .catch(() => {});
    }, 5000);
    return () => clearInterval(interval);
  }, [videos]);

  const handleAddVideo = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!source.trim()) return;
    setAdding(true);
    setError(null);
    setSuccess(null);
    try {
      const video = await addVideo(source.trim());
      setSource("");
      setSuccess(`Video added: ${video.id}`);

      // Auto-start processing
      await processVideo(video.id);
      setSuccess(`Pipeline started for ${video.id}. This may take a few minutes.`);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add video");
    } finally {
      setAdding(false);
    }
  };

  const handleProcess = async (videoId: string) => {
    try {
      await processVideo(videoId);
      setSuccess(`Pipeline started for ${videoId}`);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start processing");
    }
  };

  return (
    <div className="p-6 max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-text-muted text-sm mt-1">
          Lecture videos transformed into searchable knowledge graphs
        </p>
      </div>

      {/* Add Video */}
      <section className="bg-surface border border-border rounded-lg p-5">
        <h2 className="text-lg font-semibold mb-3">Add Video</h2>
        <form onSubmit={handleAddVideo}>
          <div className="flex gap-2">
            <input
              type="text"
              value={source}
              onChange={(e) => setSource(e.target.value)}
              placeholder="YouTube URL or local file path (e.g. https://youtube.com/watch?v=...)"
              className="flex-1 bg-surface-light border border-border rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-primary placeholder:text-text-muted/50"
            />
            <button
              type="submit"
              disabled={adding || !source.trim()}
              className="bg-primary hover:bg-primary-dark text-white px-5 py-2.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50 shrink-0"
            >
              {adding ? (
                <span className="flex items-center gap-2">
                  <Spinner /> Processing...
                </span>
              ) : (
                "Add & Process"
              )}
            </button>
          </div>
          <p className="text-text-muted text-xs mt-2">
            Paste a YouTube URL to automatically download, transcribe, extract knowledge, and build the graph.
          </p>
        </form>

        {error && (
          <div className="mt-3 bg-accent-red/10 border border-accent-red/30 rounded-lg p-3 text-sm text-accent-red">
            {error}
          </div>
        )}
        {success && (
          <div className="mt-3 bg-accent-green/10 border border-accent-green/30 rounded-lg p-3 text-sm text-accent-green">
            {success}
          </div>
        )}
      </section>

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
            No videos yet. Add a YouTube URL above to get started.
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {videos.map((v) => (
              <div
                key={v.id}
                className="bg-surface rounded-lg p-4 border border-border"
              >
                <div className="flex items-start justify-between gap-2">
                  <Link
                    href={`/video/${v.id}`}
                    className="font-medium truncate hover:text-primary-light transition-colors"
                  >
                    {v.title}
                  </Link>
                  <StatusBadge status={v.status} />
                </div>
                <div className="text-text-muted text-xs mt-1">
                  {v.duration > 0 && <span>{Math.round(v.duration)}s</span>}
                </div>
                <div className="mt-2 flex gap-2">
                  {v.status === "completed" && (
                    <Link
                      href={`/video/${v.id}`}
                      className="text-xs text-primary-light hover:underline"
                    >
                      Watch &amp; Explore
                    </Link>
                  )}
                  {(v.status === "pending" || v.status === "failed") && (
                    <button
                      onClick={() => handleProcess(v.id)}
                      className="text-xs bg-primary/20 text-primary-light px-2 py-1 rounded hover:bg-primary/30 transition-colors"
                    >
                      {v.status === "failed" ? "Retry Processing" : "Start Processing"}
                    </button>
                  )}
                  {v.status === "processing" && (
                    <span className="text-xs text-accent-amber flex items-center gap-1.5">
                      <Spinner /> Pipeline running...
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Top Concepts */}
      <section>
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-semibold">Top Concepts</h2>
          {concepts.length > 0 && (
            <Link href="/graph" className="text-primary-light text-sm hover:underline">
              View all
            </Link>
          )}
        </div>
        {loading ? (
          <div className="text-text-muted text-sm">Loading...</div>
        ) : concepts.length === 0 ? (
          <div className="text-text-muted text-sm">
            Concepts will appear here after processing a video.
          </div>
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

function Spinner() {
  return (
    <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
      />
    </svg>
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
    <span className={`px-2 py-0.5 rounded text-xs shrink-0 ${colors[status] || "bg-surface-lighter text-text-muted"}`}>
      {status}
    </span>
  );
}
