# LecGraph - Nhat ky trien khai du an

## Tong quan

| Thong tin | Chi tiet |
|---|---|
| Ten du an | LecGraph - Bien video bai giang thanh Knowledge Graph |
| Ngay bat dau | 2026-03-15 |
| Trang thai hien tai | Phase 3 hoan thanh, dang chuyen sang Phase 4 |
| Tech stack | Python 3.12, Whisper, OpenAI API, sentence-transformers, Neo4j, ChromaDB, FastAPI, Next.js 15, Cytoscape.js, React Player, Tailwind CSS v4 |
| Repository | D:\code\repo_cv |

---

## Phase 1 — Foundation Pipeline (Tuan 1-2)

### Muc tieu
Xay dung pipeline xu ly end-to-end: Video -> Audio -> Transcript -> Segments -> Knowledge Units.

### Cong viec da thuc hien

#### 1.1 Khoi tao du an
- **Trang thai:** Hoan thanh
- **Mo ta:** Setup project structure, dependencies, configuration
- **Chi tiet:**
  - Tao `pyproject.toml` voi dependencies: faster-whisper, yt-dlp, sentence-transformers, google-generativeai, pydantic, click, rich
  - Tao `.env` / `.env.example` cho cau hinh (API keys, model settings)
  - Tao `src/config/settings.py` dung Pydantic Settings de load config tu .env
  - Tao `.gitignore`
- **Files:**
  - `pyproject.toml`
  - `.env.example`
  - `src/config/__init__.py`
  - `src/config/settings.py`

#### 1.2 Data Models
- **Trang thai:** Hoan thanh
- **Mo ta:** Dinh nghia cac Pydantic models cho data flow qua pipeline
- **Models:**
  - `Word` — mot tu voi timestamp tu Whisper
  - `Sentence` — cau da group tu words, co start/end timestamps
  - `Segment` — doan transcript co tinh topic-coherent
  - `Concept` — khai niem duoc extract tu segment
  - `Relationship` — moi quan he giua 2 concepts
  - `Example`, `KeyQuote` — vi du va cau noi dang chu y
  - `KnowledgeUnit` — ket qua extract day du cho 1 segment
  - `PipelineResult` — ket qua toan bo pipeline cho 1 video
- **File:** `src/pipeline/models.py`

#### 1.3 Audio Extraction Module
- **Trang thai:** Hoan thanh
- **Mo ta:** Extract audio tu nhieu nguon khac nhau
- **Chuc nang:**
  - Download audio tu YouTube URL (dung `yt-dlp`)
  - Extract audio tu local video file (dung `ffmpeg`)
  - Su dung truc tiep local audio file
  - Auto detect nguon (URL vs file path)
  - Convert sang WAV 16kHz mono (toi uu cho Whisper)
- **Bug da fix:**
  - Windows encoding issue: subprocess output bi loi `cp1252` khi yt-dlp tra ve tieng Viet -> fix bang `encoding="utf-8"` va `errors="replace"` trong subprocess calls
- **File:** `src/pipeline/audio_extractor.py`

#### 1.4 Transcription Module (Whisper)
- **Trang thai:** Hoan thanh
- **Mo ta:** Chuyen audio thanh text voi timestamps chinh xac
- **Chuc nang:**
  - Load Whisper model (configurable: base -> large-v3)
  - Auto detect device (CPU/CUDA)
  - Word-level timestamps tu faster-whisper
  - VAD filter (Voice Activity Detection) de loai bo khoang lang
  - Group words thanh sentences dua tren:
    - Dau cham cau (. ? !)
    - Khoang dung dai (> 1 giay giua cac tu)
    - Gioi han so tu toi da/cau (50 tu)
- **Ket qua test:**
  - Video tieng Viet ~5 phut: 1220+ words, 42-45 sentences
  - Detected language: Vietnamese (probability: 1.00)
  - Model `base` chay nhanh tren CPU nhung accuracy thap (nham thanh dieu)
  - Model `large-v3` accuracy tot hon nhung can GPU hoac chay lau tren CPU
- **File:** `src/pipeline/transcriber.py`

#### 1.5 Semantic Segmentation Module (TextTiling)
- **Trang thai:** Hoan thanh
- **Mo ta:** Chia transcript thanh cac doan theo topic, khong phai chia deu thoi gian
- **Thuat toan:**
  1. Embed moi cau bang sentence-transformers (`paraphrase-multilingual-MiniLM-L12-v2`)
  2. Tinh cosine similarity giua cac cau lien tiep
  3. Smoothing (moving average) de giam noise
  4. Tim local minima trong chuoi similarity -> topic boundaries
  5. Tinh depth score cho moi boundary (do sut similarity so voi peaks xung quanh)
  6. Greedy selection: chon boundaries respect min/max duration constraints
  7. Force split segments qua dai (> max_duration)
- **Cau hinh:**
  - `SEGMENT_MIN_DURATION=30` (giay)
  - `SEGMENT_MAX_DURATION=1200` (giay)
  - `SIMILARITY_SMOOTHING_WINDOW=3`
- **Ket qua test:**
  - Video 5 phut -> 6-7 segments, moi segment 26-77 giay
  - Topic boundaries hop ly (phan biet duoc phan noi ve AI, ML, DL)
- **File:** `src/pipeline/segmenter.py`

#### 1.6 Knowledge Extraction Module (LLM)
- **Trang thai:** Hoan thanh
- **Mo ta:** Extract concepts, relationships, examples tu moi segment bang LLM
- **Thiet ke:**
  - 3-pass extraction cho moi segment:
    - Pass 0: Segment naming + key quotes + examples
    - Pass 1: Concept extraction (name, type, definition, importance)
    - Pass 2: Relationship extraction (from, to, type, evidence)
  - Prompt templates luu trong `src/config/prompts/`
  - Structured JSON output tu LLM
  - Parse JSON co xu ly markdown code blocks
- **LLM Provider:** Google Gemini API
  - Ban dau thiet ke cho Claude API (Anthropic)
  - Chuyen sang Gemini vi chi phi thap hon (free tier)
  - Model: `gemini-2.5-flash`
- **Rate Limit Handling:**
  - Smart retry: phan biet rate limit tam thoi vs quota het hoan toan
  - `_is_quota_truly_exhausted()`: kiem tra tat ca limits = 0 -> give up ngay
  - Rate limit per minute -> wait + retry (toi da 5 lan)
  - `QuotaExhaustedError` -> dung pipeline ngay, luu partial results
- **Bug da fix:**
  - Ban dau dung `"quota" in error_msg` de detect quota het -> SAI vi moi 429 error cua Gemini deu chua tu "quota"
  - Fix: chi detect quota het khi ALL limits trong error message = 0
- **Ket qua test:**
  - 2/6 segments da extract thanh cong truoc khi het quota:
    - Segment 1: 2 concepts (Computer Science, AI), 1 relationship
    - Segment 2: 4 concepts (AI, ML, Explicit Programming, Fraud Detection), 3 relationships
  - Concepts va relationships chinh xac so voi noi dung video
- **Files:**
  - `src/pipeline/extractor.py`
  - `src/config/prompts/concept_extraction.txt`
  - `src/config/prompts/relationship_extraction.txt`
  - `src/config/prompts/segment_naming.txt`

#### 1.7 CLI Entry Point
- **Trang thai:** Hoan thanh
- **Mo ta:** Command-line interface de chay pipeline
- **Commands:**
  - `python scripts/process_video.py process <SOURCE>` — chay full pipeline
    - `--skip-extraction` — bo qua LLM extraction (chi transcribe + segment)
    - `--output / -o` — chi dinh output file path
  - `python scripts/process_video.py inspect <JSON_PATH>` — xem ket qua da xu ly
- **Output:**
  - JSON file trong `output/` directory
  - Rich console output: progress bars, tables, summary
- **Bug da fix:**
  - Windows Unicode encoding: Rich console khong hien thi duoc Unicode chars (box-drawing, arrows) -> fix bang `Console(force_terminal=True)` va thay Unicode chars bang ASCII
  - Module import error -> fix `pyproject.toml` build-backend
- **File:** `scripts/process_video.py`

#### 1.8 Unit Tests
- **Trang thai:** Hoan thanh
- **Ket qua:** 18/18 tests passed
- **Test coverage:**
  - `test_models.py` — Pydantic model creation, serialization roundtrip
  - `test_segmenter.py` — Cosine similarity, smoothing, boundary detection, min duration constraint
  - `test_extractor.py` — JSON parsing (plain, code block, whitespace, object)
- **Files:** `tests/test_models.py`, `tests/test_segmenter.py`, `tests/test_extractor.py`

### Van de gap phai trong Phase 1

| # | Van de | Nguyen nhan | Giai phap |
|---|---|---|---|
| 1 | `ModuleNotFoundError: No module named 'src'` | Chua install project dang editable | `pip install -e .` |
| 2 | `setuptools.backends._legacy` not found | Sai build-backend trong pyproject.toml | Doi thanh `setuptools.build_meta` |
| 3 | `UnicodeEncodeError: charmap cp1252` | Windows console khong ho tro Unicode | `Console(force_terminal=True)` + `sys.stdout.reconfigure(encoding="utf-8")` |
| 4 | `UnicodeDecodeError` trong subprocess | yt-dlp output tieng Viet bi decode sai | Them `encoding="utf-8"`, `errors="replace"` vao subprocess calls |
| 5 | Pipeline bi treo khi het quota | `"quota" in error_msg` match ca rate limit tam thoi | Chi detect quota het khi ALL `limit: N` trong error co N=0 |
| 6 | Whisper accuracy thap voi tieng Viet | Dung model `base` (nho) | Dung `large-v3` khi co GPU, hoac chap nhan accuracy thap cho demo |

### Ket qua test Phase 1

**Video test:** "Tong quan ve AI, Machine Learning, Deep Learning va Data Science"
- URL: https://www.youtube.com/watch?v=LScZ2o1Sclg
- Duration: 4:47

| Metric | Ket qua |
|---|---|
| Audio extraction | OK (yt-dlp download + convert WAV) |
| Transcription | 1220+ words, 42-45 sentences |
| Language detection | Vietnamese (100% confidence) |
| Segmentation | 6-7 segments (topic boundaries hop ly) |
| Concept extraction (2 segments) | 6 concepts (chinh xac) |
| Relationship extraction (2 segments) | 4 relationships (chinh xac) |
| Unit tests | 18/18 passed |

---

## Phase 2 — Graph & Search (Tuan 3-4)

### Muc tieu
Xay dung Knowledge Graph tu extracted data, implement semantic search va prerequisite query.

### Cong viec da thuc hien

#### 2.0 Shared Infrastructure (Refactoring)
- **Trang thai:** Hoan thanh
- **Mo ta:** Refactor code de tai su dung embedding model va LLM client across modules
- **Cong viec:**
  - [x] Tao `src/pipeline/embeddings.py` — shared embedding singleton (get_embedding_model, embed_texts)
  - [x] Tao `src/pipeline/llm_utils.py` — shared LLM client (get_client, call_llm, parse_json_response, QuotaExhaustedError)
  - [x] Refactor `segmenter.py` de import tu `embeddings.py`
  - [x] Refactor `extractor.py` de import tu `llm_utils.py`
  - [x] Update `settings.py` voi Neo4j, ChromaDB, API settings
  - [x] Update `pyproject.toml` voi dependencies: neo4j, chromadb, fastapi, uvicorn

#### 2.1 Graph Database Setup
- **Trang thai:** Hoan thanh
- **Mo ta:** Setup Neo4j, tao schema, import data tu KnowledgeUnits
- **Cong viec:**
  - [x] Implement `src/db/neo4j_client.py` — singleton driver, run_query, run_write, ensure_constraints
  - [x] Implement `src/pipeline/graph_builder.py` — tao Video, Segment, Concept, Example nodes + edges (BELONGS_TO, EXPLAINED_IN, ILLUSTRATES, DEPENDS_ON, etc.)
  - [x] Tao Cypher constraints va indexes (concept_name, segment_id, video_id unique)
  - [x] Dung MERGE de idempotent
- **Files:** `src/db/__init__.py`, `src/db/neo4j_client.py`, `src/pipeline/graph_builder.py`

#### 2.2 Entity Resolution
- **Trang thai:** Hoan thanh
- **Mo ta:** Merge duplicate concepts tu nhieu segments/videos bang embedding similarity + LLM verification
- **Cong viec:**
  - [x] Candidate generation: pairwise cosine similarity > threshold (0.75) + alias overlap
  - [x] LLM verification: SAME / DIFFERENT / RELATED_BUT_DIFFERENT (batch 10 pairs/call)
  - [x] Merge logic: union-find, gop aliases, chon best definition/importance
  - [x] Prompt template `entity_resolution.txt`
- **Files:** `src/pipeline/entity_resolver.py`, `src/config/prompts/entity_resolution.txt`

#### 2.3 Cross-video Concept Linking
- **Trang thai:** Hoan thanh
- **Mo ta:** Lien ket concepts giua nhieu video trong cung khoa hoc
- **Cong viec:**
  - [x] Collect all concepts across multiple PipelineResults
  - [x] Run entity resolution tren combined concept set
  - [x] Tao EXPLAINED_IN edges tu resolved concepts -> segments across videos
- **File:** `src/pipeline/cross_linker.py`

#### 2.4 Vector Store Setup
- **Trang thai:** Hoan thanh
- **Mo ta:** Setup ChromaDB de index embeddings cho semantic search
- **Cong viec:**
  - [x] Implement `src/db/chroma_client.py` — singleton PersistentClient, 2 collections (segments, concepts)
  - [x] Implement `src/pipeline/indexer.py` — embed va upsert segments + concepts voi metadata
  - [x] Dung shared `embeddings.embed_texts()` (khong dung ChromaDB built-in embedding)
- **Files:** `src/db/chroma_client.py`, `src/pipeline/indexer.py`

#### 2.5 Semantic Search Engine
- **Trang thai:** Hoan thanh
- **Mo ta:** Tim kiem theo ngu nghia, ket hop voi graph enrichment
- **Cong viec:**
  - [x] Vector search tren ChromaDB segments collection -> top-K
  - [x] Graph enrichment: query Neo4j de tim concepts, prerequisites, related, examples cho moi segment
  - [x] Graceful degradation khi Neo4j khong available
  - [x] Pydantic response models (SearchResult, SearchResponse)
- **Files:** `src/search/__init__.py`, `src/search/engine.py`, `src/search/models.py`

#### 2.6 Prerequisite Query & Learning Path
- **Trang thai:** Hoan thanh
- **Mo ta:** Truy van prerequisites va tao learning path
- **Cong viec:**
  - [x] Prerequisite query: recursive DEPENDS_ON traversal voi max_depth, deduplication
  - [x] Learning path: topological sort (Kahn's algorithm) tren dependency subgraph
  - [x] Known concepts pruning
  - [x] Estimated time tinh tu segment durations
- **Files:** `src/search/prerequisites.py`, `src/search/learning_path.py`

#### 2.7 FastAPI Backend
- **Trang thai:** Hoan thanh
- **Mo ta:** REST API cho frontend
- **Cong viec:**
  - [x] Setup FastAPI app (`src/api/main.py`) voi lifespan (startup: ensure_constraints, shutdown: close_driver)
  - [x] CORS middleware cho frontend (localhost:3000)
  - [x] Routes: videos (CRUD + process), graph (concepts + prerequisites), search, learning_path
  - [x] Pydantic request/response models
  - [x] Pipeline trigger via BackgroundTasks
- **Files:** `src/api/main.py`, `src/api/models.py`, `src/api/routes/videos.py`, `src/api/routes/graph.py`, `src/api/routes/search.py`, `src/api/routes/learning_path.py`
- **Endpoints:**
  - `POST /api/videos` — them video
  - `GET /api/videos` — list videos
  - `GET /api/videos/{id}/segments` — segments cua video
  - `POST /api/videos/{id}/process` — trigger pipeline (async)
  - `GET /api/graph/concepts` — list concepts (pagination)
  - `GET /api/graph/concepts/{name}` — chi tiet concept + relationships + segments
  - `GET /api/graph/concepts/{name}/prerequisites` — prerequisite chain
  - `POST /api/search` — semantic search
  - `POST /api/learning-path` — tao learning path
  - `GET /api/health` — health check

#### 2.8 CLI Updates
- **Trang thai:** Hoan thanh
- **Cong viec:**
  - [x] `lecgraph build-graph <JSON_PATH>` — build Neo4j graph + index ChromaDB
  - [x] `lecgraph serve` — start FastAPI server

### Ket qua test Phase 2

| Metric | Ket qua |
|---|---|
| Tests moi (Phase 2) | 56 tests |
| Tests cu (Phase 1) | 53 tests |
| Tong cong | 109/109 passed |
| Thoi gian chay | ~2 giay |

---

## Phase 3 — Frontend (Tuan 5-6)

### Muc tieu
Xay dung web UI: graph visualization, semantic search, video player voi timestamp navigation.

### Cong viec da thuc hien

#### 3.1 Project Setup
- **Trang thai:** Hoan thanh
- **Mo ta:** Init Next.js 15 project voi TypeScript, Tailwind CSS v4, Cytoscape.js, React Player
- **Cong viec:**
  - [x] Init Next.js 15 project trong `frontend/` (App Router, TypeScript)
  - [x] Setup Tailwind CSS v4 voi custom dark theme (Catppuccin-inspired)
  - [x] Setup Cytoscape.js cho graph visualization
  - [x] Setup React Player cho video playback (dynamic import, SSR-safe)
  - [x] API client (`src/lib/api.ts`) voi type-safe functions cho moi endpoint
  - [x] Next.js rewrites proxy `/api/*` -> `localhost:8000/api/*` (khong can CORS config rieng)
  - [x] Sidebar navigation voi active state highlighting
- **Files:** `frontend/package.json`, `frontend/next.config.ts`, `frontend/src/lib/api.ts`, `frontend/src/lib/utils.ts`, `frontend/src/components/layout/Sidebar.tsx`, `frontend/src/app/layout.tsx`, `frontend/src/app/globals.css`

#### 3.2 Graph Explorer View
- **Trang thai:** Hoan thanh
- **Mo ta:** Interactive knowledge graph visualization voi Cytoscape.js
- **Cong viec:**
  - [x] Render knowledge graph voi Cytoscape.js (cose layout, animated)
  - [x] Zoom, pan, click-to-select nodes
  - [x] Color coding theo concept type (Theory=purple, Technique=blue, Tool=green, Application=amber)
  - [x] Node size theo importance level (high/medium/low)
  - [x] Edge labels (depends_on, extends, ...) voi auto-rotate
  - [x] Click node -> hien thi concept detail panel (definition, aliases, relationships, segments)
  - [x] Click relationship target -> navigate graph den node do
  - [x] Legend overlay hien thi node type colors
  - [x] URL parameter `?concept=X` de deep-link den concept
- **Files:** `frontend/src/components/graph/GraphExplorer.tsx`, `frontend/src/app/graph/page.tsx`

#### 3.3 Search Interface
- **Trang thai:** Hoan thanh
- **Mo ta:** Semantic search voi rich results display
- **Cong viec:**
  - [x] Search bar voi semantic search (POST /api/search)
  - [x] Hien thi results voi context: concepts (link to graph), prerequisites, examples
  - [x] Score bar hien thi relevance percentage
  - [x] Timestamp display (start-end) cho moi result
  - [x] Click result -> navigate den video player tai timestamp
  - [x] Error handling va empty state
- **File:** `frontend/src/app/search/page.tsx`

#### 3.4 Video Player + Knowledge Panel
- **Trang thai:** Hoan thanh
- **Mo ta:** Video player voi timestamp navigation va real-time knowledge panel
- **Cong viec:**
  - [x] React Player voi seek-to-timestamp (URL param `?t=seconds`)
  - [x] Segment timeline bar ben duoi player (color-coded, clickable segments)
  - [x] Playhead indicator tren timeline
  - [x] Auto-detect active segment theo current playback time
  - [x] Knowledge panel: concepts voi definitions, type indicators, prerequisites
  - [x] Click concept -> navigate to graph view
  - [x] YouTube video support (auto-start at timestamp)
  - [x] Segment list voi timestamps (click to seek)
- **File:** `frontend/src/app/video/[id]/page.tsx`

#### 3.5 Learning Path View
- **Trang thai:** Hoan thanh
- **Mo ta:** Generate va track learning path cho target concept
- **Cong viec:**
  - [x] Input: target concept voi datalist suggestions tu existing concepts
  - [x] Input: known concepts (comma-separated) de prune path
  - [x] Output: ordered list voi step numbers, definitions, video timestamps
  - [x] Progress tracking: click circle de toggle da hoc / chua hoc
  - [x] Progress bar hien thi % completed
  - [x] Estimated total time va per-step duration
  - [x] Links to video player tai dung timestamp va graph view
  - [x] Timeline UI voi vertical connector line
- **File:** `frontend/src/app/learning-path/page.tsx`

### Ket qua build Phase 3

| Metric | Ket qua |
|---|---|
| Framework | Next.js 15.5, React 19, TypeScript |
| Styling | Tailwind CSS v4 (dark theme) |
| Graph | Cytoscape.js 3.30 (cose layout) |
| Video | React Player 2.16 (YouTube support) |
| Build | 7 routes, all compiled successfully |
| Bundle size | 103 kB shared + per-page chunks |

---

## Phase 4 — Evaluation & Polish (Tuan 7-8)

### Muc tieu
Danh gia chat luong, fix issues, deploy va chuan bi portfolio.

### Cong viec can lam

#### 4.1 Process Full Course
- [ ] Chon 1 khoa hoc 10-15 videos (ML/DL tren YouTube)
- [ ] Chay pipeline cho tat ca videos
- [ ] Review va fix extraction quality

#### 4.2 User Evaluation
- [ ] Moi 5-10 sinh vien test
- [ ] Task 1: Tim concept X -> do time saved vs manual search
- [ ] Task 2: Learning path -> danh gia quality (1-5)
- [ ] Task 3: Prerequisites -> danh gia correctness
- [ ] Thu thap qualitative feedback

#### 4.3 Performance Optimization
- [ ] Cache Whisper model va embedding model (khong load lai moi video)
- [ ] Batch LLM calls khi co the
- [ ] Lazy loading graph nodes tren frontend
- [ ] Optimize Neo4j queries

#### 4.4 Deployment
- [ ] Docker Compose (backend + Neo4j + ChromaDB)
- [ ] Frontend deploy len Vercel
- [ ] Backend deploy len Railway/Render
- [ ] Environment variables / secrets config

#### 4.5 Documentation & Portfolio
- [ ] README.md voi screenshots va demo GIF
- [ ] Architecture diagram
- [ ] Blog post / write-up cho portfolio
- [ ] Record demo video
- [ ] Evaluation results summary

---

## Tong ket tien do

| Phase | Trang thai | Hoan thanh |
|---|---|---|
| Phase 1 — Foundation Pipeline | Hoan thanh | 100% |
| Phase 2 — Graph & Search | Hoan thanh | 100% |
| Phase 3 — Frontend | Hoan thanh | 100% |
| Phase 4 — Evaluation & Polish | Chua bat dau | 0% |
