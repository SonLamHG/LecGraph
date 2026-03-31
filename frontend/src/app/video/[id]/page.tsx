"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams, useSearchParams } from "next/navigation";
import dynamic from "next/dynamic";
import Link from "next/link";
import {
  getVideoSegments,
  getConceptDetail,
  type Segment,
  type ConceptDetail,
} from "@/lib/api";
import { formatTime, conceptTypeColor, importanceColor } from "@/lib/utils";

const ReactPlayer = dynamic(() => import("react-player"), { ssr: false });

export default function VideoPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const videoId = params.id as string;
  const startTime = Number(searchParams.get("t")) || 0;

  const [segments, setSegments] = useState<Segment[]>([]);
  const [activeSegment, setActiveSegment] = useState<Segment | null>(null);
  const [segmentConcepts, setSegmentConcepts] = useState<ConceptDetail[]>([]);
  const [videoSource, setVideoSource] = useState<string>("");
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const playerRef = useRef<{ seekTo: (t: number) => void } | null>(null);

  useEffect(() => {
    getVideoSegments(videoId)
      .then((segs) => {
        setSegments(segs);
        // Try to construct video source - for YouTube videos stored in Neo4j
        // The source is stored in the Video node
        fetch(`/api/videos`)
          .then((r) => r.json())
          .then((videos: { id: string; source: string }[]) => {
            const v = videos.find((v) => v.id === videoId);
            if (v) setVideoSource(v.source);
          })
          .catch(() => {});
      })
      .catch(() => {});
  }, [videoId]);

  useEffect(() => {
    if (startTime > 0 && playerRef.current) {
      playerRef.current.seekTo(startTime);
    }
  }, [startTime, videoSource]);

  // Update active segment based on current playback time
  const handleProgress = useCallback(
    (state: { playedSeconds: number }) => {
      setCurrentTime(state.playedSeconds);
      const seg = segments.find(
        (s) => state.playedSeconds >= s.start && state.playedSeconds < s.end
      );
      if (seg && seg.id !== activeSegment?.id) {
        setActiveSegment(seg);
      }
    },
    [segments, activeSegment]
  );

  // Load concepts when active segment changes
  useEffect(() => {
    if (!activeSegment) {
      setSegmentConcepts([]);
      return;
    }
    // Fetch concepts related to this segment via the graph API
    fetch(`/api/graph/concepts?skip=0&limit=200`)
      .then((r) => r.json())
      .then(async (concepts: { name: string }[]) => {
        // For each concept, check if it's in this segment
        const details: ConceptDetail[] = [];
        for (const c of concepts.slice(0, 20)) {
          try {
            const detail = await getConceptDetail(c.name);
            const inSegment = detail.segments.some(
              (s) => s.segment_id === activeSegment.id
            );
            if (inSegment) details.push(detail);
          } catch {
            /* skip */
          }
        }
        setSegmentConcepts(details);
      })
      .catch(() => {});
  }, [activeSegment]);

  const seekTo = (time: number) => {
    playerRef.current?.seekTo(time);
    setPlaying(true);
  };

  const totalDuration = segments.length > 0 ? segments[segments.length - 1].end : 0;

  return (
    <div className="flex flex-col lg:flex-row h-screen">
      {/* Left: Video Player + Segment Timeline */}
      <div className="flex-1 flex flex-col min-w-0">
        <div className="p-4 border-b border-border shrink-0">
          <h1 className="text-xl font-bold truncate">Video: {videoId}</h1>
        </div>

        {/* Player */}
        <div className="bg-black aspect-video w-full max-h-[60vh]">
          {videoSource ? (
            <ReactPlayer
              ref={(p: { seekTo: (t: number) => void } | null) => { playerRef.current = p; }}
              url={videoSource}
              width="100%"
              height="100%"
              playing={playing}
              onPlay={() => setPlaying(true)}
              onPause={() => setPlaying(false)}
              onProgress={handleProgress}
              controls
              config={{
                youtube: { playerVars: { start: startTime } },
              }}
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-text-muted">
              Video source not available
            </div>
          )}
        </div>

        {/* Segment Timeline */}
        <div className="p-4 border-t border-border">
          <h3 className="text-sm font-medium text-text-muted mb-2">Segments</h3>
          {totalDuration > 0 && (
            <div className="relative h-8 bg-surface-light rounded-lg overflow-hidden mb-3">
              {segments.map((seg, i) => {
                const left = (seg.start / totalDuration) * 100;
                const width = ((seg.end - seg.start) / totalDuration) * 100;
                const isActive = activeSegment?.id === seg.id;
                const colors = [
                  "bg-primary/40",
                  "bg-accent-blue/40",
                  "bg-accent-purple/40",
                  "bg-accent-green/40",
                  "bg-accent-amber/40",
                ];
                return (
                  <button
                    key={seg.id}
                    title={seg.title || `Segment ${i + 1}`}
                    onClick={() => seekTo(seg.start)}
                    className={`absolute top-0 h-full transition-all ${colors[i % colors.length]} hover:opacity-80 ${
                      isActive ? "ring-2 ring-primary z-10" : ""
                    }`}
                    style={{ left: `${left}%`, width: `${width}%` }}
                  />
                );
              })}
              {/* Playhead */}
              {totalDuration > 0 && (
                <div
                  className="absolute top-0 h-full w-0.5 bg-white z-20"
                  style={{ left: `${(currentTime / totalDuration) * 100}%` }}
                />
              )}
            </div>
          )}

          <div className="space-y-1 max-h-40 overflow-y-auto">
            {segments.map((seg, i) => (
              <button
                key={seg.id}
                onClick={() => seekTo(seg.start)}
                className={`w-full text-left px-3 py-1.5 rounded text-sm transition-colors ${
                  activeSegment?.id === seg.id
                    ? "bg-primary/20 text-primary-light"
                    : "hover:bg-surface-light text-text-muted"
                }`}
              >
                <span className="font-mono text-xs mr-2">{formatTime(seg.start)}</span>
                {seg.title || `Segment ${i + 1}`}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Right: Knowledge Panel */}
      <div className="w-full lg:w-80 bg-surface border-l border-border overflow-y-auto shrink-0">
        <div className="p-4 border-b border-border">
          <h2 className="font-semibold">Knowledge Panel</h2>
          {activeSegment ? (
            <p className="text-sm text-text-muted mt-1">{activeSegment.title}</p>
          ) : (
            <p className="text-sm text-text-muted mt-1">Play the video to see concepts</p>
          )}
        </div>

        {segmentConcepts.length > 0 ? (
          <div className="p-4 space-y-4">
            {segmentConcepts.map((c) => (
              <div key={c.name} className="bg-surface-light rounded-lg p-3">
                <div className="flex items-center gap-2 mb-1">
                  <Link
                    href={`/graph?concept=${encodeURIComponent(c.name)}`}
                    className="font-medium text-sm hover:text-primary-light"
                  >
                    {c.name}
                  </Link>
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ backgroundColor: conceptTypeColor(c.type) }}
                  />
                </div>
                <p className="text-xs text-text-muted">{c.definition}</p>

                {c.relationships.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {c.relationships
                      .filter((r) => r.type === "DEPENDS_ON")
                      .map((r) => (
                        <span
                          key={r.target}
                          className="px-1.5 py-0.5 bg-accent-amber/20 text-accent-amber rounded text-xs"
                        >
                          requires: {r.target}
                        </span>
                      ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : activeSegment ? (
          <div className="p-4 text-sm text-text-muted">
            No concepts found for this segment.
          </div>
        ) : null}
      </div>
    </div>
  );
}
