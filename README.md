# LecGraph

**Transform lecture videos into interactive knowledge graphs.**

LecGraph automatically processes lecture videos — transcribing speech, extracting key concepts, discovering relationships, and building a searchable knowledge graph that helps students learn more efficiently.

<!-- TODO: Add demo GIF here -->
<!-- ![Demo](docs/assets/demo.gif) -->

## Features

- **Automatic Transcription** — Whisper-powered speech-to-text with word-level timestamps
- **Semantic Segmentation** — TextTiling algorithm splits lectures into meaningful topics
- **Knowledge Extraction** — LLM extracts concepts, relationships, examples, and key quotes
- **Interactive Knowledge Graph** — Cytoscape.js visualization with click-to-explore
- **Semantic Search** — Vector search (ChromaDB) enriched with graph context (Neo4j)
- **Learning Paths** — Auto-generated prerequisite chains for any concept
- **Batch Processing** — Process entire YouTube playlists/courses in one command

## Architecture

```
┌─── Frontend (Next.js 15, React 19, Cytoscape.js) ────────┐
│  /             Dashboard + Video Upload                  │
│  /graph        Knowledge Graph Visualization             │
│  /search       Semantic Search                           │
│  /learning-path Learning Path Generator                  │
│  /video/[id]   Video Player + Transcript                 │
└──────────────────────────────────────────────────────────┘
                         │ API Rewrite
                         ▼
┌─── Backend (FastAPI, Python 3.12) ───────────────────────┐
│  Pipeline:                                               │
│    1. Audio Extraction (yt-dlp)                          │
│    2. Transcription (faster-whisper)                     │
│    3. Semantic Segmentation (TextTiling + embeddings)    │
│    4. Knowledge Extraction (OpenAI GPT-4o-mini)          │
│    5. Post-processing (dedup, normalization)             │
│    6. Graph Building (Neo4j)                             │
│    7. Vector Indexing (ChromaDB)                         │
└──────────────────────────────────────────────────────────┘
          │                          │
          ▼                          ▼
   ┌──────────────┐          ┌──────────────┐
   │    Neo4j     │          │   ChromaDB   │
   │  Knowledge   │          │   Vector     │
   │    Graph     │          │    Store     │
   └──────────────┘          └──────────────┘
```

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 22+
- Docker & Docker Compose (recommended)
- OpenAI API key

### Option 1: Docker Compose (recommended)

```bash
# Clone and configure
cp .env.example .env
# Edit .env — set OPENAI_API_KEY

# Start all services
docker compose up --build

# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
# Neo4j:    http://localhost:7474
```

### Option 2: Local Development

```bash
# Backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e .

# Start Neo4j (via Docker)
docker run -d --name neo4j -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/lecgraph123 neo4j:5-community

# Start backend
cp .env.example .env  # edit with your API key
python -m scripts.process_video serve

# Frontend
cd frontend
npm install
npm run dev
```

## Usage

### Web UI

1. Open http://localhost:3000
2. Paste a YouTube URL and click "Add & Process"
3. Wait for the pipeline to complete (a few minutes per video)
4. Explore the knowledge graph, search concepts, or generate learning paths

### CLI

```bash
# Process a single video
python -m scripts.process_video process "https://youtube.com/watch?v=..."

# Process an entire YouTube playlist
python -m scripts.process_video process-course --playlist "https://youtube.com/playlist?list=..."

# Process from a file of URLs
python -m scripts.process_video process-course --file urls.txt --skip-errors

# Inspect pipeline output
python -m scripts.process_video inspect output/vid_abc12345.json

# Build graph from existing pipeline output
python -m scripts.process_video build-graph output/vid_abc12345.json
```

## Deployment

### Frontend (Vercel)

```bash
cd frontend
vercel deploy
# Set env var: BACKEND_URL=https://your-backend-url.com
```

### Backend (Railway)

```bash
railway init
railway up
# Set env vars in Railway dashboard (see .env.example)
```

### Backend (Render)

Deploy using the `render.yaml` blueprint — push to GitHub and connect to Render.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, React 19, Tailwind CSS, Cytoscape.js |
| Backend | FastAPI, Python 3.12 |
| Transcription | faster-whisper (large-v3) |
| Embeddings | sentence-transformers (MiniLM) |
| LLM | OpenAI GPT-4o-mini |
| Graph DB | Neo4j 5 Community |
| Vector DB | ChromaDB |
| Containerization | Docker, Docker Compose |

## Project Structure

```
├── src/
│   ├── api/              # FastAPI routes (videos, graph, search, learning-path)
│   ├── config/           # Settings + LLM prompt templates
│   ├── db/               # Neo4j + ChromaDB clients
│   ├── pipeline/         # Core pipeline (transcribe, segment, extract, build)
│   └── search/           # Semantic search engine + learning path generation
├── frontend/             # Next.js app
│   ├── src/app/          # Pages (dashboard, graph, search, video player)
│   ├── src/components/   # Reusable components (GraphExplorer, Sidebar)
│   └── src/lib/          # API client + utilities
├── scripts/              # CLI entry point
├── tests/                # Unit tests
├── docker-compose.yml    # Full stack orchestration
├── Dockerfile            # Backend container
├── render.yaml           # Render deployment blueprint
└── railway.json          # Railway deployment config
```

<!-- ## Screenshots -->
<!-- TODO: Add screenshots -->
<!-- ![Dashboard](docs/assets/screenshot-dashboard.png) -->
<!-- ![Knowledge Graph](docs/assets/screenshot-graph.png) -->
<!-- ![Search](docs/assets/screenshot-search.png) -->
<!-- ![Learning Path](docs/assets/screenshot-learning-path.png) -->

## License

MIT
