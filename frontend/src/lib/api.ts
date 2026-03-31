const API_BASE = "/api";

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`API error ${res.status}: ${detail}`);
  }
  return res.json();
}

// --- Types ---

export interface Video {
  id: string;
  title: string;
  source: string;
  duration: number;
  status: string;
}

export interface Segment {
  id: string;
  video_id: string;
  title: string;
  start: number;
  end: number;
}

export interface Concept {
  name: string;
  aliases: string[];
  type: string;
  definition: string;
  importance: string;
}

export interface ConceptDetail extends Concept {
  relationships: { type: string; target: string; evidence: string }[];
  segments: {
    segment_id: string;
    title: string;
    video_id: string;
    video_title: string;
    start: number;
    end: number;
  }[];
}

export interface SearchResult {
  segment_id: string;
  video_id: string;
  title: string;
  text: string;
  start: number;
  end: number;
  score: number;
  concepts: string[];
  prerequisites: string[];
  related: string[];
  examples: string[];
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
}

export interface LearningStep {
  concept: string;
  definition: string;
  video_id: string;
  video_title: string;
  segment_id: string;
  segment_title: string;
  start: number;
  end: number;
  duration: number;
}

export interface LearningPath {
  target: string;
  steps: LearningStep[];
  total_duration: number;
  concept_count: number;
}

export interface StatusResponse {
  status: string;
  message: string;
}

// --- API Functions ---

export async function getVideos(): Promise<Video[]> {
  return fetchAPI<Video[]>("/videos");
}

export async function addVideo(source: string): Promise<Video> {
  return fetchAPI<Video>("/videos", {
    method: "POST",
    body: JSON.stringify({ source }),
  });
}

export async function processVideo(videoId: string): Promise<StatusResponse> {
  return fetchAPI<StatusResponse>(`/videos/${videoId}/process`, {
    method: "POST",
  });
}

export async function getVideoSegments(videoId: string): Promise<Segment[]> {
  return fetchAPI<Segment[]>(`/videos/${videoId}/segments`);
}

export async function getConcepts(skip = 0, limit = 50): Promise<Concept[]> {
  return fetchAPI<Concept[]>(`/graph/concepts?skip=${skip}&limit=${limit}`);
}

export async function getConceptDetail(name: string): Promise<ConceptDetail> {
  return fetchAPI<ConceptDetail>(`/graph/concepts/${encodeURIComponent(name)}`);
}

export async function getPrerequisites(name: string, maxDepth = 10) {
  return fetchAPI<{ concept: string; prerequisites: { name: string; depth: number }[] }>(
    `/graph/concepts/${encodeURIComponent(name)}/prerequisites?max_depth=${maxDepth}`
  );
}

export async function semanticSearch(
  query: string,
  videoId?: string,
  limit = 10
): Promise<SearchResponse> {
  return fetchAPI<SearchResponse>("/search", {
    method: "POST",
    body: JSON.stringify({ query, video_id: videoId || null, limit }),
  });
}

export async function generateLearningPath(
  targetConcept: string,
  knownConcepts: string[] = []
): Promise<LearningPath> {
  return fetchAPI<LearningPath>("/learning-path", {
    method: "POST",
    body: JSON.stringify({ target_concept: targetConcept, known_concepts: knownConcepts }),
  });
}
