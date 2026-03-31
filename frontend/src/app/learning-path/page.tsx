"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  generateLearningPath,
  getConcepts,
  type LearningPath,
  type Concept,
} from "@/lib/api";
import { formatTime } from "@/lib/utils";

export default function LearningPathPage() {
  const [target, setTarget] = useState("");
  const [knownInput, setKnownInput] = useState("");
  const [path, setPath] = useState<LearningPath | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [concepts, setConcepts] = useState<Concept[]>([]);
  const [completed, setCompleted] = useState<Set<string>>(new Set());

  useEffect(() => {
    getConcepts(0, 100)
      .then(setConcepts)
      .catch(() => {});
  }, []);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!target.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const known = knownInput
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const result = await generateLearningPath(target.trim(), known);
      setPath(result);
      setCompleted(new Set());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate path");
    } finally {
      setLoading(false);
    }
  };

  const toggleComplete = (concept: string) => {
    setCompleted((prev) => {
      const next = new Set(prev);
      if (next.has(concept)) next.delete(concept);
      else next.add(concept);
      return next;
    });
  };

  const progress = path ? (completed.size / path.steps.length) * 100 : 0;

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-1">Learning Path</h1>
      <p className="text-text-muted text-sm mb-6">
        Generate an ordered learning path to master any concept
      </p>

      <form onSubmit={handleGenerate} className="mb-6 space-y-3">
        <div>
          <label className="block text-sm text-text-muted mb-1">Target Concept</label>
          <div className="flex gap-2">
            <input
              type="text"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              placeholder="e.g. Deep Learning"
              list="concept-suggestions"
              className="flex-1 bg-surface border border-border rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-primary placeholder:text-text-muted/50"
            />
            <button
              type="submit"
              disabled={loading}
              className="bg-primary hover:bg-primary-dark text-white px-6 py-2.5 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
            >
              {loading ? "Generating..." : "Generate"}
            </button>
          </div>
          <datalist id="concept-suggestions">
            {concepts.map((c) => (
              <option key={c.name} value={c.name} />
            ))}
          </datalist>
        </div>

        <div>
          <label className="block text-sm text-text-muted mb-1">
            Already Known (comma-separated, optional)
          </label>
          <input
            type="text"
            value={knownInput}
            onChange={(e) => setKnownInput(e.target.value)}
            placeholder="e.g. Linear Algebra, Statistics"
            className="w-full bg-surface border border-border rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:border-primary placeholder:text-text-muted/50"
          />
        </div>
      </form>

      {error && (
        <div className="bg-accent-red/10 border border-accent-red/30 rounded-lg p-3 text-sm text-accent-red mb-4">
          {error}
        </div>
      )}

      {path && (
        <div>
          {/* Stats */}
          <div className="flex items-center gap-4 mb-4 text-sm">
            <span className="text-text-muted">
              {path.concept_count} concepts
            </span>
            <span className="text-text-muted">
              ~{Math.round(path.total_duration / 60)} min total
            </span>
            <span className="text-text-muted">
              {completed.size}/{path.steps.length} completed
            </span>
          </div>

          {/* Progress bar */}
          <div className="h-2 bg-surface-lighter rounded-full mb-6 overflow-hidden">
            <div
              className="h-full bg-accent-green rounded-full transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>

          {/* Steps */}
          <div className="relative">
            {/* Vertical line */}
            <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-border" />

            <div className="space-y-4">
              {path.steps.map((step, i) => {
                const done = completed.has(step.concept);
                return (
                  <div key={step.concept} className="relative pl-10">
                    {/* Circle */}
                    <button
                      onClick={() => toggleComplete(step.concept)}
                      className={`absolute left-2 top-3 w-5 h-5 rounded-full border-2 transition-colors ${
                        done
                          ? "bg-accent-green border-accent-green"
                          : "border-border hover:border-primary bg-surface"
                      }`}
                    >
                      {done && (
                        <svg className="w-3 h-3 mx-auto text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                        </svg>
                      )}
                    </button>

                    <div
                      className={`bg-surface border border-border rounded-lg p-4 transition-opacity ${
                        done ? "opacity-50" : ""
                      }`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <span className="text-text-muted text-xs font-mono">#{i + 1}</span>
                          <Link
                            href={`/graph?concept=${encodeURIComponent(step.concept)}`}
                            className="font-medium hover:text-primary-light"
                          >
                            {step.concept}
                          </Link>
                        </div>
                        <span className="text-xs text-text-muted">
                          {Math.round(step.duration / 60)} min
                        </span>
                      </div>
                      <p className="text-sm text-text-muted mb-2">{step.definition}</p>
                      <Link
                        href={`/video/${step.video_id}?t=${Math.floor(step.start)}`}
                        className="inline-flex items-center gap-1.5 text-xs text-primary-light hover:underline"
                      >
                        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        {step.segment_title || step.video_title} at {formatTime(step.start)}
                      </Link>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
