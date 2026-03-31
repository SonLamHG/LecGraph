"use client";

import { useState } from "react";
import Link from "next/link";
import { semanticSearch, type SearchResult, type SearchResponse } from "@/lib/api";
import { formatTime } from "@/lib/utils";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await semanticSearch(query.trim());
      setResults(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-1">Semantic Search</h1>
      <p className="text-text-muted text-sm mb-6">
        Search across all lecture content using natural language
      </p>

      <form onSubmit={handleSearch} className="mb-6">
        <div className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. What is the difference between supervised and unsupervised learning?"
            className="flex-1 bg-surface border border-border rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-primary placeholder:text-text-muted/50"
          />
          <button
            type="submit"
            disabled={loading}
            className="bg-primary hover:bg-primary-dark text-white px-6 py-2.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
          >
            {loading ? "Searching..." : "Search"}
          </button>
        </div>
      </form>

      {error && (
        <div className="bg-accent-red/10 border border-accent-red/30 rounded-lg p-3 text-sm text-accent-red mb-4">
          {error}
        </div>
      )}

      {results && (
        <div>
          <div className="text-text-muted text-sm mb-4">
            {results.results.length} results for &ldquo;{results.query}&rdquo;
          </div>
          <div className="space-y-3">
            {results.results.map((r, i) => (
              <SearchResultCard key={r.segment_id + i} result={r} />
            ))}
            {results.results.length === 0 && (
              <div className="bg-surface rounded-lg p-8 text-center text-text-muted">
                No results found. Try a different query.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function SearchResultCard({ result }: { result: SearchResult }) {
  return (
    <div className="bg-surface border border-border rounded-lg p-4 hover:border-primary/30 transition-colors">
      <div className="flex items-start justify-between gap-3 mb-2">
        <Link
          href={`/video/${result.video_id}?t=${Math.floor(result.start)}`}
          className="font-medium hover:text-primary-light transition-colors"
        >
          {result.title || result.segment_id}
        </Link>
        <span className="text-xs text-text-muted bg-surface-lighter px-2 py-0.5 rounded shrink-0">
          {formatTime(result.start)} - {formatTime(result.end)}
        </span>
      </div>

      <p className="text-sm text-text-muted mb-3 line-clamp-3">{result.text}</p>

      <div className="flex flex-wrap gap-3 text-xs">
        {result.concepts.length > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="text-text-muted">Concepts:</span>
            <div className="flex gap-1 flex-wrap">
              {result.concepts.map((c) => (
                <Link
                  key={c}
                  href={`/graph?concept=${encodeURIComponent(c)}`}
                  className="px-1.5 py-0.5 bg-primary/20 text-primary-light rounded hover:bg-primary/30"
                >
                  {c}
                </Link>
              ))}
            </div>
          </div>
        )}
        {result.prerequisites.length > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="text-text-muted">Prerequisites:</span>
            <div className="flex gap-1 flex-wrap">
              {result.prerequisites.map((p) => (
                <span key={p} className="px-1.5 py-0.5 bg-accent-amber/20 text-accent-amber rounded">
                  {p}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {result.examples.length > 0 && (
        <div className="mt-2 text-xs text-text-muted">
          <span className="font-medium">Examples: </span>
          {result.examples.join(", ")}
        </div>
      )}

      <div className="mt-2 flex items-center gap-2">
        <div className="h-1 flex-1 bg-surface-lighter rounded-full overflow-hidden">
          <div
            className="h-full bg-primary rounded-full"
            style={{ width: `${Math.round(result.score * 100)}%` }}
          />
        </div>
        <span className="text-xs text-text-muted">{Math.round(result.score * 100)}%</span>
      </div>
    </div>
  );
}
