# LecGraph — Biến Video Bài Giảng Thành Knowledge Graph

## 1. Tổng quan dự án

### 1.1 Tên dự án
**LecGraph** (Lecture → Graph)

### 1.2 Mô tả ngắn
Hệ thống AI tự động chuyển đổi video bài giảng thành knowledge graph có thể tìm kiếm, giúp sinh viên navigate kiến thức hiệu quả thay vì tua lại hàng giờ video.

### 1.3 Vấn đề cần giải quyết

Sinh viên học online đối mặt 3 vấn đề cốt lõi:

| Vấn đề | Mô tả | Hệ quả |
|---|---|---|
| **Không tìm được** | "Thầy giải thích gradient vanishing ở video nào, phút nào?" | Tốn 20-30 phút tua video tìm 1 đoạn 3 phút |
| **Không thấy liên kết** | "Backpropagation liên quan chain rule ở video trước thế nào?" | Hiểu rời rạc, không xây dựng được bức tranh tổng |
| **Không biết mình thiếu gì** | Xem video 10 mà không hiểu vì chưa nắm concept ở video 3 | Học bị hổng, mất motivation |

### 1.4 Tại sao tóm tắt video (summary) không đủ?

Summary giảm lượng text nhưng **mất đi structure**. Kiến thức không phải danh sách phẳng — nó là **đồ thị có quan hệ**: concept A phụ thuộc B, ví dụ X minh họa lý thuyết Y, phương pháp C mở rộng từ D.

LecGraph không tóm tắt — LecGraph **structuralize knowledge**.

### 1.5 Người dùng mục tiêu
- Sinh viên đại học học qua video bài giảng (đặc biệt ngành STEM)
- Người tự học qua YouTube/Coursera/edX
- Giảng viên muốn tạo learning path có cấu trúc cho khóa học

---

## 2. Mục tiêu dự án

### 2.1 Mục tiêu chức năng (Functional Goals)

| ID | Mục tiêu | Mô tả |
|---|---|---|
| F1 | Video → Transcript | Chuyển đổi audio thành text có timestamp chính xác |
| F2 | Semantic Segmentation | Chia transcript thành các đoạn theo topic (không phải chia đều thời gian) |
| F3 | Knowledge Extraction | Trích xuất concepts, definitions, relationships, examples từ mỗi segment |
| F4 | Graph Construction | Xây dựng knowledge graph với nodes (concepts) và edges (relationships) |
| F5 | Semantic Search | Tìm kiếm theo ngữ nghĩa, trả về đúng đoạn video + context |
| F6 | Graph Navigation | Duyệt graph: xem prerequisites, related concepts, examples |
| F7 | Cross-video Linking | Liên kết concepts giữa nhiều video trong cùng khóa học |
| F8 | Learning Path | Gợi ý thứ tự học dựa trên topological sort trên dependency graph |

### 2.2 Mục tiêu phi chức năng (Non-functional Goals)

| ID | Mục tiêu | Metric |
|---|---|---|
| NF1 | Pipeline xử lý 1 video 1 tiếng trong < 10 phút | Thời gian end-to-end |
| NF2 | Transcription accuracy tiếng Việt > 85% WER | Word Error Rate |
| NF3 | Concept extraction precision > 80% | Manual evaluation |
| NF4 | Search trả kết quả < 2 giây | Response time |
| NF5 | UI load graph < 3 giây với 500 nodes | Render time |

---

## 3. Kiến trúc hệ thống

### 3.1 Kiến trúc tổng quan

```
┌─────────────────────────────────────────────────────────────────┐
│                        INPUT LAYER                              │
│  ┌──────────┐  ┌──────────────┐  ┌───────────────────────────┐ │
│  │ Video    │  │ YouTube URL  │  │ Audio file (mp3/wav)      │ │
│  │ Upload   │  │              │  │                           │ │
│  └────┬─────┘  └──────┬───────┘  └─────────────┬─────────────┘ │
│       └───────────────┼─────────────────────────┘               │
│                       ▼                                         │
│              ┌────────────────┐                                  │
│              │  Audio Extract │  ← yt-dlp / ffmpeg               │
│              └────────┬───────┘                                  │
└───────────────────────┼─────────────────────────────────────────┘
                        │
┌───────────────────────┼─────────────────────────────────────────┐
│                 PROCESSING PIPELINE                              │
│                       ▼                                         │
│  ┌─────────────────────────────────────┐                        │
│  │  Stage 1: Speech-to-Text            │                        │
│  │  ┌───────────┐  ┌────────────────┐  │                        │
│  │  │  Whisper   │→│ Post-processing │  │                        │
│  │  │  large-v3  │  │ (punctuation,  │  │                        │
│  │  │            │  │  spell check)  │  │                        │
│  │  └───────────┘  └────────────────┘  │                        │
│  └──────────────────┬──────────────────┘                        │
│                     ▼                                           │
│  ┌─────────────────────────────────────┐                        │
│  │  Stage 2: Semantic Segmentation     │                        │
│  │  ┌────────────┐  ┌───────────────┐  │                        │
│  │  │ Sentence   │→│  TextTiling /  │  │                        │
│  │  │ Embedding  │  │  Topic Shift  │  │                        │
│  │  │            │  │  Detection    │  │                        │
│  │  └────────────┘  └───────────────┘  │                        │
│  └──────────────────┬──────────────────┘                        │
│                     ▼                                           │
│  ┌─────────────────────────────────────┐                        │
│  │  Stage 3: Knowledge Extraction      │                        │
│  │  ┌────────────┐  ┌───────────────┐  │                        │
│  │  │  LLM       │→│  Structured   │  │                        │
│  │  │  Analysis  │  │  Output Parse │  │                        │
│  │  └────────────┘  └───────────────┘  │                        │
│  └──────────────────┬──────────────────┘                        │
│                     ▼                                           │
│  ┌─────────────────────────────────────┐                        │
│  │  Stage 4: Graph Construction        │                        │
│  │  ┌────────────┐  ┌───────────────┐  │                        │
│  │  │  Entity    │→│  Relationship │  │                        │
│  │  │  Resolution│  │  Mapping     │  │                        │
│  │  └────────────┘  └───────────────┘  │                        │
│  └──────────────────┬──────────────────┘                        │
│                     ▼                                           │
│  ┌─────────────────────────────────────┐                        │
│  │  Stage 5: Indexing                  │                        │
│  │  ┌────────────┐  ┌───────────────┐  │                        │
│  │  │  Vector    │  │  Graph        │  │                        │
│  │  │  Embedding │  │  Storage      │  │                        │
│  │  └────────────┘  └───────────────┘  │                        │
│  └──────────────────┬──────────────────┘                        │
└───────────────────────┼─────────────────────────────────────────┘
                        │
┌───────────────────────┼─────────────────────────────────────────┐
│                  APPLICATION LAYER                               │
│                       ▼                                         │
│  ┌──────────┐  ┌────────────┐  ┌─────────────┐  ┌───────────┐ │
│  │  Graph   │  │  Semantic  │  │   Video     │  │  Learning │ │
│  │  Viewer  │  │  Search    │  │   Player    │  │  Path     │ │
│  └──────────┘  └────────────┘  └─────────────┘  └───────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 3.2 Data Flow

```
Video (mp4)
  │
  ├─→ Audio (wav) ──→ Whisper ──→ Transcript + Timestamps
  │                                    │
  │                    ┌───────────────┘
  │                    ▼
  │              Sentence Embeddings
  │                    │
  │                    ▼
  │              Topic Boundaries ──→ Segments
  │                                      │
  │                    ┌─────────────────┘
  │                    ▼
  │              LLM Extraction ──→ Knowledge Units (JSON)
  │                                      │
  │                    ┌─────────────────┘
  │                    ▼
  │              Entity Resolution ──→ Deduplicated Concepts
  │                                      │
  │                    ┌─────────────────┘
  │                    ▼
  │              Graph Construction ──→ Neo4j / NetworkX
  │                                      │
  │                    ┌─────────────────┘
  │                    ▼
  └─→ Video URL + Timestamps ──→ Frontend (Graph + Player + Search)
```

---

## 4. Thiết kế chi tiết từng module

### 4.1 Module 1: Speech-to-Text (Transcription)

#### Input / Output
```
Input:  audio file (wav/mp3) hoặc video file (mp4) hoặc YouTube URL
Output: List[TranscriptSegment]
        - text: str
        - start: float (seconds)
        - end: float (seconds)
        - confidence: float
```

#### Xử lý
1. **Extract audio** từ video (ffmpeg) hoặc download từ YouTube (yt-dlp)
2. **Whisper large-v3** transcribe với word-level timestamps
3. **Post-processing:**
   - Gộp words thành sentences (dựa vào punctuation + pause duration)
   - Sửa lỗi chính tả phổ biến trong tiếng Việt (Whisper hay nhầm thanh điệu)
   - Normalize text: chuẩn hóa số, viết tắt, ký hiệu toán học

#### Edge cases cần xử lý
- Giảng viên nói tiếng Việt xen tiếng Anh (thuật ngữ chuyên ngành) → Whisper language detection per segment
- Audio chất lượng thấp (mic xa, echo phòng học) → preprocessing: noise reduction
- Video không có audio (slides only) → fallback: OCR trên slides

#### Ví dụ output
```json
[
  {
    "text": "Bây giờ chúng ta sẽ nói về gradient descent",
    "start": 323.5,
    "end": 326.8,
    "confidence": 0.94
  },
  {
    "text": "Ý tưởng cốt lõi là chúng ta muốn tìm minimum của loss function",
    "start": 327.1,
    "end": 331.4,
    "confidence": 0.91
  }
]
```

---

### 4.2 Module 2: Semantic Segmentation

#### Vấn đề
Chia transcript theo thời gian cố định (mỗi 5 phút) → cắt ngang giữa một concept. Cần chia theo **topic boundary** — nơi giảng viên chuyển sang chủ đề mới.

#### Thuật toán: TextTiling cải tiến

```
Step 1: Embed mỗi câu → vector (dùng embedding model)

Step 2: Tính cosine similarity giữa cặp câu liên tiếp
         sim[i] = cosine(embed[i], embed[i+1])

Step 3: Smoothing (moving average, window=3) để giảm noise

Step 4: Tìm local minima trong chuỗi similarity
         → Đây là topic boundaries

Step 5: Filter boundaries:
         - Loại segments < 30 giây (quá ngắn, có thể noise)
         - Loại segments > 20 phút (quá dài, có thể miss boundary)

Step 6: LLM verify + naming
         - Gửi text trước/sau boundary cho LLM
         - Xác nhận có thực sự đổi topic không
         - Đặt tên cho mỗi segment
```

#### Visualization
```
Similarity
    1.0 ┤
        │   ╭──╮    ╭───╮      ╭─╮     ╭──────╮
    0.8 ┤  ╭╯  ╰╮  ╭╯   ╰╮   ╭╯ ╰╮   ╭╯      ╰╮
        │ ╭╯    ╰╮╭╯     ╰╮ ╭╯   ╰╮ ╭╯        ╰╮
    0.6 ┤╭╯      ╰╯       ╰╮╯     ╰─╯          ╰╮
        │╯                  ╰╮                    ╰╮
    0.4 ┤                    ╰╮                    ╰
        │         ↑            ↑           ↑
    0.2 ┤      boundary     boundary    boundary
        └─────────────────────────────────────────── Time
```

#### Output
```json
[
  {
    "segment_id": "vid01_seg01",
    "title": "Ôn tập: Đạo hàm và Chain Rule",
    "start": 0.0,
    "end": 270.5,
    "transcript": "Trước khi vào bài mới, chúng ta ôn lại...",
    "sentence_count": 24
  },
  {
    "segment_id": "vid01_seg02",
    "title": "Gradient Descent — Ý tưởng cốt lõi",
    "start": 270.5,
    "end": 735.2,
    "transcript": "Bây giờ chúng ta sẽ nói về gradient descent...",
    "sentence_count": 48
  }
]
```

---

### 4.3 Module 3: Knowledge Extraction

#### Đây là module CORE — quyết định chất lượng toàn bộ hệ thống.

#### Prompt Strategy

Dùng **2-pass extraction** để tăng quality:

**Pass 1 — Concept & Definition Extraction:**
```
Bạn là chuyên gia phân tích bài giảng. Phân tích đoạn transcript sau
và trích xuất các CONCEPTS (khái niệm) được giảng dạy.

Với mỗi concept, xác định:
- name: tên chính xác (ưu tiên thuật ngữ tiếng Anh nếu là thuật ngữ chuyên ngành)
- aliases: các tên gọi khác trong transcript
- type: definition / algorithm / theorem / technique / property
- definition: định nghĩa ngắn gọn dựa trên nội dung bài giảng
- importance: core (khái niệm chính) / supporting (hỗ trợ) / mentioned (chỉ nhắc đến)
- timestamp_range: khoảng thời gian concept được giảng

Transcript (segment: "{segment_title}", video: "{video_title}"):
---
{transcript_text}
---

Output JSON array.
```

**Pass 2 — Relationship Extraction:**
```
Dựa trên đoạn transcript và danh sách concepts đã trích xuất,
xác định MỐI QUAN HỆ giữa các concepts.

Các loại relationship:
- depends_on: concept A cần hiểu B trước (B là prerequisite)
- extends: A mở rộng/cải tiến từ B
- is_part_of: A là thành phần của B
- illustrates: example/ví dụ A minh họa cho concept B
- contrasts: A và B được so sánh/đối lập
- hyperparameter_of: A là hyperparameter/config của B
- applies_to: technique A áp dụng cho problem B

Concepts: {concepts_json}
Transcript: {transcript_text}

Output JSON array of relationships.
```

#### Output Schema đầy đủ: Knowledge Unit

```json
{
  "segment_id": "vid01_seg02",
  "video_id": "vid01",
  "title": "Gradient Descent — Ý tưởng cốt lõi",
  "timestamp": {
    "start": 270.5,
    "end": 735.2
  },

  "concepts": [
    {
      "id": "concept_gradient_descent",
      "name": "Gradient Descent",
      "aliases": ["GD", "thuật toán GD", "giảm gradient"],
      "type": "algorithm",
      "definition": "Thuật toán tối ưu iterative: cập nhật parameters theo hướng ngược gradient của loss function để tìm minimum",
      "importance": "core",
      "timestamp_range": {"start": 275.0, "end": 620.3}
    },
    {
      "name": "Learning Rate",
      "aliases": ["tốc độ học", "alpha", "η"],
      "type": "property",
      "definition": "Hyperparameter kiểm soát kích thước mỗi bước cập nhật trong gradient descent",
      "importance": "core",
      "timestamp_range": {"start": 620.3, "end": 735.2}
    }
  ],

  "relationships": [
    {
      "from": "Gradient Descent",
      "to": "Đạo hàm",
      "type": "depends_on",
      "evidence": "Thầy nói: 'để hiểu gradient descent, trước hết các bạn phải nắm vững đạo hàm'"
    },
    {
      "from": "Gradient Descent",
      "to": "Loss Function",
      "type": "applies_to",
      "evidence": "GD được dùng để minimize loss function"
    },
    {
      "from": "Learning Rate",
      "to": "Gradient Descent",
      "type": "hyperparameter_of",
      "evidence": "Learning rate quyết định step size trong mỗi iteration của GD"
    }
  ],

  "examples": [
    {
      "description": "Ví dụ bát parabol 2D — đứng trên núi trong sương mù",
      "illustrates": "Gradient Descent",
      "timestamp": 345.0
    },
    {
      "description": "Learning rate quá lớn → overshooting, quá nhỏ → converge chậm",
      "illustrates": "Learning Rate",
      "timestamp": 650.8
    }
  ],

  "key_quotes": [
    {
      "text": "Hãy tưởng tượng bạn đứng trên đỉnh núi trong sương mù, bạn không nhìn thấy đáy nhưng bạn cảm nhận được độ dốc dưới chân",
      "timestamp": 348.2,
      "relevance": "Analogy nổi tiếng giải thích intuition của gradient descent"
    }
  ]
}
```

---

### 4.4 Module 4: Knowledge Graph Construction

#### Graph Schema

```
NODE TYPES:
┌─────────────────────────────────────────────────────┐
│ Concept                                             │
│   - id: string (unique)                             │
│   - name: string                                    │
│   - aliases: string[]                               │
│   - type: enum                                      │
│   - definition: string                              │
│   - importance: enum                                │
│   - first_mentioned_in: segment_id                  │
│   - all_segments: segment_id[]                      │
│   - embedding: float[] (for search)                 │
├─────────────────────────────────────────────────────┤
│ Segment                                             │
│   - id: string                                      │
│   - video_id: string                                │
│   - title: string                                   │
│   - start: float                                    │
│   - end: float                                      │
│   - transcript: string                              │
│   - embedding: float[]                              │
├─────────────────────────────────────────────────────┤
│ Example                                             │
│   - id: string                                      │
│   - description: string                             │
│   - timestamp: float                                │
│   - segment_id: string                              │
├─────────────────────────────────────────────────────┤
│ Video                                               │
│   - id: string                                      │
│   - title: string                                   │
│   - url: string                                     │
│   - duration: float                                 │
│   - course_id: string (optional)                    │
└─────────────────────────────────────────────────────┘

EDGE TYPES:
┌─────────────────────────────────────────────────────┐
│ Concept → Concept                                   │
│   - depends_on                                      │
│   - extends                                         │
│   - is_part_of                                      │
│   - contrasts                                       │
│   - hyperparameter_of                               │
│   - applies_to                                      │
│                                                     │
│ Concept → Segment                                   │
│   - explained_in (gắn timestamp cụ thể)             │
│                                                     │
│ Example → Concept                                   │
│   - illustrates                                     │
│                                                     │
│ Segment → Video                                     │
│   - belongs_to                                      │
│                                                     │
│ All edges have:                                     │
│   - evidence: string (trích dẫn từ transcript)      │
│   - confidence: float (0-1)                         │
└─────────────────────────────────────────────────────┘
```

#### Entity Resolution (Deduplication)

Cùng 1 concept có thể xuất hiện với nhiều tên gọi:
- "Gradient Descent", "GD", "thuật toán GD", "giảm gradient"
- "Neural Network", "mạng neural", "mạng nơ-ron", "NN"

**Thuật toán 2 bước:**

```
Step 1: Candidate Generation
  - Với mỗi cặp concept (A, B) từ các segments khác nhau
  - Tính embedding similarity: sim(embed(A.name), embed(B.name))
  - Nếu sim > 0.75 → candidate pair
  - Cũng check alias overlap

Step 2: LLM Verification
  - Gửi candidate pairs cho LLM kèm context (definitions từ cả 2 bên)
  - LLM xác nhận: SAME / DIFFERENT / RELATED_BUT_DIFFERENT
  - Nếu SAME → merge:
    - Giữ tên phổ biến nhất làm primary name
    - Gộp aliases
    - Gộp definitions (chọn comprehensive nhất)
    - Giữ tất cả segment references
```

**Tại sao 2 bước mà không chỉ dùng LLM?**
- Step 1 giảm O(n²) pairs xuống chỉ high-similarity candidates → tiết kiệm LLM calls
- LLM ở Step 2 xử lý semantic nuance mà embedding miss (ví dụ: "Adam" optimizer vs "Adam" tên người)

---

### 4.5 Module 5: Search & Query Engine

#### 4.5.1 Semantic Search

```
Query: "giải thích backpropagation"
              │
              ▼
     ┌─────────────────┐
     │  Embed query     │
     └────────┬────────┘
              │
     ┌────────▼────────┐
     │  Vector search   │  → Top-K segments by embedding similarity
     │  (ChromaDB)      │
     └────────┬────────┘
              │
     ┌────────▼────────┐
     │  Graph enrichment│  → Với mỗi result, traverse graph:
     │                  │     - Prerequisites (depends_on edges, reverse)
     │                  │     - Related concepts (all edges)
     │                  │     - Examples (illustrates edges)
     └────────┬────────┘
              │
     ┌────────▼────────┐
     │  Rank & format   │  → Sắp xếp theo relevance + format output
     └─────────────────┘
```

#### 4.5.2 Graph-Aware Query Types

**Type 1: Direct Search**
```
Q: "gradient descent là gì?"
→ Tìm concept node "Gradient Descent"
→ Trả về definition + segment có giảng + timestamp
```

**Type 2: Prerequisite Query**
```
Q: "tôi cần biết gì trước khi học backpropagation?"
→ Tìm node "Backpropagation"
→ Traverse depends_on edges recursively
→ Topological sort → learning order
→ Output:
   1. Đạo hàm (Video 1, 05:00)
   2. Chain Rule (Video 2, 12:30)
   3. Computational Graph (Video 3, 00:00)
   4. Loss Function (Video 3, 25:00)
   → Backpropagation (Video 5, 10:00)
```

**Type 3: Comparison Query**
```
Q: "so sánh SGD và Adam"
→ Tìm nodes "SGD" và "Adam"
→ Tìm contrasts edges hoặc common parent
→ Trả về segments giảng cả 2 + điểm khác biệt
```

**Type 4: Learning Path Generation**
```
Q: "tôi muốn hiểu CNN từ đầu"
→ Tìm node "CNN"
→ Recursive dependency resolution
→ Topological sort trên subgraph
→ Output: ordered list of (concept, video, timestamp)
```

---

### 4.6 Module 6: Frontend

#### 4.6.1 Các view chính

**View 1: Knowledge Graph Explorer**
```
┌──────────────────────────────────────────────────┐
│  🔍 Search: [___________________________] [Go]   │
│                                                   │
│  ┌───────────────────────────────────────────┐   │
│  │                                           │   │
│  │     [Chain Rule]──depends──►[Backprop]    │   │
│  │          │                     │          │   │
│  │      depends               extends        │   │
│  │          │                     │          │   │
│  │     [Đạo hàm]           [Auto Diff]       │   │
│  │                                           │   │
│  │  ● Core concept  ○ Supporting  ◦ Mentioned│   │
│  └───────────────────────────────────────────┘   │
│                                                   │
│  Selected: Backpropagation                        │
│  Definition: Thuật toán tính gradient cho...      │
│  📍 Video 5, 10:00 - 18:45  [▶ Play]            │
│  Prerequisites: Chain Rule, Computational Graph   │
│  Related: Auto Differentiation, Vanishing Grad    │
└──────────────────────────────────────────────────┘
```

**View 2: Video Player + Knowledge Panel**
```
┌──────────────────────────┬───────────────────────┐
│                          │  📚 Concepts in this  │
│     ┌──────────────┐    │     segment:          │
│     │              │    │                       │
│     │  Video       │    │  ● Gradient Descent   │
│     │  Player      │    │  ● Learning Rate      │
│     │              │    │  ○ Loss Function      │
│     │   advancement │    │                       │
│     └──────────────┘    │  🔗 Prerequisites:    │
│      advancement         │  → Đạo hàm (Vid 1)   │
│     ▶ 05:23 / 45:00    │  → Chain Rule (Vid 2) │
│                          │                       │
│  Timeline:               │  📝 Key quote:        │
│  [==|====|===|====|==]  │  "Hãy tưởng tượng    │
│   Seg1 Seg2 Seg3 Seg4  │   bạn đứng trên       │
│        ▲ current        │   đỉnh núi..."        │
└──────────────────────────┴───────────────────────┘
```

**View 3: Learning Path**
```
┌──────────────────────────────────────────────────┐
│  🎯 Goal: Hiểu Convolutional Neural Network      │
│                                                   │
│  Learning Path (estimated: 2h 15min):             │
│                                                   │
│  ✅ 1. Linear Algebra Basics      Vid 1, 00:00   │
│  ✅ 2. Đạo hàm & Chain Rule      Vid 2, 04:30   │
│  🔵 3. Neural Network cơ bản      Vid 3, 00:00   │
│  ⬜ 4. Backpropagation            Vid 5, 10:00   │
│  ⬜ 5. Convolution Operation       Vid 7, 00:00   │
│  ⬜ 6. Pooling & Stride           Vid 7, 25:00   │
│  ⬜ 7. CNN Architecture           Vid 8, 00:00   │
│                                                   │
│  [▶ Continue from step 3]                         │
└──────────────────────────────────────────────────┘
```

---

## 5. Tech Stack

### 5.1 Chi tiết lựa chọn

| Layer | Technology | Lý do chọn |
|---|---|---|
| **Speech-to-Text** | Whisper large-v3 (local) hoặc Whisper API | Accuracy tốt nhất, hỗ trợ tiếng Việt, word-level timestamps |
| **LLM** | Claude API (claude-sonnet-4-6) | Structured output tốt, context window lớn, giá hợp lý |
| **Embedding** | text-embedding-3-small (OpenAI) hoặc multilingual-e5-large | Multilingual support, giá rẻ cho text-embedding-3-small |
| **Vector Store** | ChromaDB | Lightweight, local, đủ cho scale dự án |
| **Graph Database** | Neo4j Community Edition | Cypher query mạnh, visualization built-in, free |
| **Backend** | FastAPI (Python) | Async support, auto-docs, ecosystem ML/AI tốt |
| **Frontend** | Next.js + Cytoscape.js | SSR, Cytoscape.js cho graph viz chuyên dụng |
| **Video Player** | React Player | Hỗ trợ seek to timestamp, YouTube embed |
| **Audio Processing** | ffmpeg + yt-dlp | Industry standard |
| **Task Queue** | Celery + Redis | Xử lý async pipeline cho video dài |

### 5.2 Alternatives đã cân nhắc

| Quyết định | Alternative | Tại sao không chọn |
|---|---|---|
| Neo4j vs NetworkX | NetworkX đơn giản hơn | Neo4j scale tốt hơn, có visualization, Cypher query mạnh |
| ChromaDB vs Pinecone | Pinecone managed service | Over-engineering cho dự án này, ChromaDB local đủ dùng |
| Next.js vs Streamlit | Streamlit nhanh hơn để prototype | Next.js cho phép custom UI tốt hơn, đặc biệt graph + video player |
| Whisper local vs API | API đơn giản hơn | Local cho phép custom post-processing, không phụ thuộc network |

---

## 6. Data Models

### 6.1 Database Schema (PostgreSQL — metadata storage)

```sql
-- Videos
CREATE TABLE videos (
    id          UUID PRIMARY KEY,
    title       VARCHAR(500) NOT NULL,
    url         VARCHAR(1000),
    duration    FLOAT,
    course_id   UUID REFERENCES courses(id),
    status      VARCHAR(50) DEFAULT 'pending',  -- pending/processing/completed/failed
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Courses (nhóm videos)
CREATE TABLE courses (
    id          UUID PRIMARY KEY,
    title       VARCHAR(500) NOT NULL,
    description TEXT,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Segments
CREATE TABLE segments (
    id          UUID PRIMARY KEY,
    video_id    UUID REFERENCES videos(id),
    title       VARCHAR(500),
    start_time  FLOAT NOT NULL,
    end_time    FLOAT NOT NULL,
    transcript  TEXT NOT NULL,
    seq_order   INTEGER,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Concepts
CREATE TABLE concepts (
    id          UUID PRIMARY KEY,
    name        VARCHAR(200) NOT NULL,
    aliases     JSONB DEFAULT '[]',
    type        VARCHAR(50),
    definition  TEXT,
    importance  VARCHAR(50),
    created_at  TIMESTAMP DEFAULT NOW()
);

-- Concept ↔ Segment mapping
CREATE TABLE concept_segments (
    concept_id  UUID REFERENCES concepts(id),
    segment_id  UUID REFERENCES segments(id),
    timestamp_start FLOAT,
    timestamp_end   FLOAT,
    PRIMARY KEY (concept_id, segment_id)
);

-- Examples
CREATE TABLE examples (
    id          UUID PRIMARY KEY,
    description TEXT NOT NULL,
    segment_id  UUID REFERENCES segments(id),
    concept_id  UUID REFERENCES concepts(id),
    timestamp   FLOAT
);
```

### 6.2 Neo4j Graph Schema (Cypher)

```cypher
// Node constraints
CREATE CONSTRAINT concept_id IF NOT EXISTS FOR (c:Concept) REQUIRE c.id IS UNIQUE;
CREATE CONSTRAINT segment_id IF NOT EXISTS FOR (s:Segment) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT video_id IF NOT EXISTS FOR (v:Video) REQUIRE v.id IS UNIQUE;

// Example: Create concept with relationships
CREATE (gd:Concept {
    id: 'concept_gradient_descent',
    name: 'Gradient Descent',
    aliases: ['GD', 'thuật toán GD'],
    type: 'algorithm',
    definition: 'Thuật toán tối ưu iterative...'
})

CREATE (lr:Concept {
    id: 'concept_learning_rate',
    name: 'Learning Rate',
    type: 'property'
})

CREATE (lr)-[:HYPERPARAMETER_OF {evidence: 'LR quyết định step size...'}]->(gd)
CREATE (gd)-[:DEPENDS_ON {evidence: 'Cần hiểu đạo hàm trước...'}]->(derivative)

// Query: Prerequisites for a concept
MATCH path = (target:Concept {name: 'Backpropagation'})-[:DEPENDS_ON*]->(prereq:Concept)
RETURN prereq.name, length(path) AS depth
ORDER BY depth DESC

// Query: Learning path (topological sort)
MATCH path = (target:Concept {name: 'CNN'})-[:DEPENDS_ON*]->(prereq:Concept)
WITH collect(DISTINCT prereq) + [target] AS concepts
UNWIND concepts AS c
OPTIONAL MATCH (c)-[:EXPLAINED_IN]->(s:Segment)-[:BELONGS_TO]->(v:Video)
RETURN c.name, s.title, v.title, s.start_time
```

---

## 7. API Design

### 7.1 REST Endpoints

```yaml
# Video Management
POST   /api/videos                    # Upload/add video
GET    /api/videos                    # List all videos
GET    /api/videos/{id}               # Get video details + processing status
DELETE /api/videos/{id}               # Delete video and associated data

# Processing Pipeline
POST   /api/videos/{id}/process       # Trigger processing pipeline
GET    /api/videos/{id}/status        # Get pipeline status (stage, progress %)

# Knowledge Graph
GET    /api/graph                     # Get full graph (paginated)
GET    /api/graph/concepts            # List all concepts
GET    /api/graph/concepts/{id}       # Get concept details + relationships
GET    /api/graph/concepts/{id}/prerequisites  # Get prerequisite chain

# Search
POST   /api/search                    # Semantic search
  Body: { "query": "string", "video_id": "optional", "limit": 10 }
  Response: {
    "results": [
      {
        "segment": { "id", "title", "start", "end", "video_id" },
        "score": 0.92,
        "concepts": ["Gradient Descent", "Learning Rate"],
        "prerequisites": ["Đạo hàm", "Chain Rule"],
        "related": ["SGD", "Adam"],
        "examples": [{"description": "...", "timestamp": 345.0}]
      }
    ]
  }

# Learning Path
POST   /api/learning-path             # Generate learning path
  Body: { "target_concept": "CNN", "known_concepts": ["Linear Algebra"] }
  Response: {
    "path": [
      { "concept": "Đạo hàm", "video_id": "...", "timestamp": 270.5, "duration": 300 },
      { "concept": "Chain Rule", "video_id": "...", "timestamp": 750.0, "duration": 180 }
    ],
    "estimated_time": 8100
  }

# Segments
GET    /api/videos/{id}/segments      # Get all segments of a video
GET    /api/segments/{id}             # Get segment details + knowledge units
```

---

## 8. Kế hoạch triển khai (Roadmap)

### Phase 1 — Foundation (Tuần 1-2)

**Mục tiêu:** Pipeline chạy được end-to-end với 1 video, chưa cần UI.

```
Week 1:
├── Setup project structure, dependencies
├── Implement audio extraction (ffmpeg + yt-dlp)
├── Implement Whisper transcription + timestamp alignment
├── Implement post-processing (sentence grouping, spell check)
└── Test: transcribe 3 video YouTube bài giảng tiếng Việt, đánh giá quality

Week 2:
├── Implement TextTiling segmentation
├── Implement LLM extraction (concept + relationship)
├── Implement structured output parsing + validation
└── Test: chạy full pipeline 1 video, manually review extracted knowledge units
```

**Deliverable:** CLI command: `lecgraph process <video_url>` → output JSON knowledge units

### Phase 2 — Graph & Search (Tuần 3-4)

**Mục tiêu:** Knowledge graph có thể query được, semantic search hoạt động.

```
Week 3:
├── Setup Neo4j, implement graph construction
├── Implement entity resolution (embedding + LLM verify)
├── Implement cross-video concept linking
└── Test: process 5 videos cùng khóa học, verify graph quality

Week 4:
├── Setup ChromaDB, implement embedding indexing
├── Implement semantic search with graph enrichment
├── Implement prerequisite query + learning path generation
├── Build FastAPI backend + all endpoints
└── Test: search queries, prerequisite chains, learning paths
```

**Deliverable:** API server chạy được, test bằng curl/Postman

### Phase 3 — Frontend (Tuần 5-6)

**Mục tiêu:** UI hoàn chỉnh, interactive.

```
Week 5:
├── Setup Next.js project
├── Implement Graph Explorer (Cytoscape.js)
│   ├── Zoom, pan, click-to-select
│   ├── Color coding by concept type/importance
│   └── Edge labels
├── Implement Search bar + results display
└── Implement Video Player with timestamp seek

Week 6:
├── Implement Knowledge Panel (concept details on click)
├── Implement Learning Path view
├── Implement Video Timeline (segments bar under player)
├── Responsive design + polish
└── Integration testing: full user flow
```

**Deliverable:** Fully functional web app

### Phase 4 — Evaluation & Polish (Tuần 7-8)

**Mục tiêu:** Đánh giá chất lượng, fix issues, chuẩn bị demo.

```
Week 7:
├── Process 10-15 videos (1 khóa học hoàn chỉnh)
├── User evaluation: mời 5-10 sinh viên test
│   ├── Task: tìm concept X → đo time saved vs manual search
│   ├── Task: learning path → đánh giá quality
│   └── Collect qualitative feedback
├── Fix issues từ feedback

Week 8:
├── Performance optimization
├── Write project documentation
├── Record demo video
├── Prepare presentation / portfolio write-up
└── Deploy (Vercel + Railway/Render)
```

**Deliverable:** Deployed app + demo video + evaluation results

---

## 9. Evaluation Framework

### 9.1 Automated Metrics

| Metric | Đo gì | Target |
|---|---|---|
| Transcription WER | Accuracy của Whisper trên tiếng Việt | < 15% |
| Segmentation quality | So sánh auto segments vs manual annotation | F1 > 0.8 |
| Concept extraction precision | % concepts extracted đúng | > 80% |
| Concept extraction recall | % concepts trong video được extract | > 70% |
| Relationship accuracy | % relationships đúng | > 75% |
| Entity resolution precision | % merges đúng | > 90% |
| Search relevance | nDCG@5 cho semantic search | > 0.7 |

### 9.2 User Study

**Participants:** 5-10 sinh viên đang học khóa ML/DL online

**Tasks:**
1. **Search task:** "Tìm đoạn video giải thích concept X" — đo thời gian, so sánh: dùng LecGraph vs tua video thủ công
2. **Learning path task:** "Bạn muốn hiểu concept Y, dùng learning path gợi ý" — đánh giá chất lượng path (1-5)
3. **Navigation task:** "Tìm prerequisites của concept Z" — đánh giá correctness

**Metrics:**
- Time-on-task (quantitative)
- Satisfaction score 1-5 (quantitative)
- Qualitative feedback (open-ended)

---

## 10. Rủi ro và giải pháp

| Rủi ro | Impact | Probability | Giải pháp |
|---|---|---|---|
| Whisper accuracy thấp với tiếng Việt mix tiếng Anh | Cao | Trung bình | Post-processing pipeline + manual correction cho demo data |
| LLM extract sai concept/relationship | Cao | Trung bình | 2-pass extraction + confidence scoring + human review option |
| Entity resolution merge nhầm | Trung bình | Thấp | High-precision threshold + LLM verification step |
| Video quá dài (>2h) → pipeline timeout | Thấp | Trung bình | Chunk audio 30 phút, process parallel |
| Chi phí LLM API cao khi process nhiều video | Trung bình | Cao | Dùng Claude Haiku cho pass 1, Sonnet cho pass 2; cache results |
| Graph quá lớn → UI lag | Thấp | Thấp | Pagination, lazy loading, chỉ render visible nodes |

---

## 11. Cấu trúc thư mục dự án

```
lecgraph/
├── docs/                          # Documentation
│   └── PROJECT_OVERVIEW.md        # This file
├── src/
│   ├── pipeline/                  # Processing pipeline
│   │   ├── __init__.py
│   │   ├── audio_extractor.py     # ffmpeg + yt-dlp
│   │   ├── transcriber.py         # Whisper integration
│   │   ├── segmenter.py           # TextTiling segmentation
│   │   ├── extractor.py           # LLM knowledge extraction
│   │   ├── graph_builder.py       # Graph construction + entity resolution
│   │   └── indexer.py             # Embedding indexing
│   ├── api/                       # FastAPI backend
│   │   ├── __init__.py
│   │   ├── main.py                # App entry point
│   │   ├── routes/
│   │   │   ├── videos.py
│   │   │   ├── search.py
│   │   │   ├── graph.py
│   │   │   └── learning_path.py
│   │   ├── models/                # Pydantic models
│   │   │   ├── video.py
│   │   │   ├── segment.py
│   │   │   ├── concept.py
│   │   │   └── search.py
│   │   └── services/              # Business logic
│   │       ├── search_service.py
│   │       ├── graph_service.py
│   │       └── path_service.py
│   ├── db/                        # Database
│   │   ├── postgres.py            # PostgreSQL connection
│   │   ├── neo4j_client.py        # Neo4j connection
│   │   ├── chroma_client.py       # ChromaDB connection
│   │   └── migrations/            # Alembic migrations
│   └── config/                    # Configuration
│       ├── settings.py            # Environment settings
│       └── prompts/               # LLM prompt templates
│           ├── concept_extraction.txt
│           └── relationship_extraction.txt
├── frontend/                      # Next.js frontend
│   ├── src/
│   │   ├── app/                   # App router pages
│   │   ├── components/
│   │   │   ├── GraphViewer.tsx     # Cytoscape.js graph
│   │   │   ├── VideoPlayer.tsx     # React Player + timestamp
│   │   │   ├── SearchBar.tsx
│   │   │   ├── KnowledgePanel.tsx
│   │   │   ├── LearningPath.tsx
│   │   │   └── Timeline.tsx        # Video segment timeline
│   │   └── lib/                   # API client, utils
│   └── package.json
├── tests/
│   ├── test_transcriber.py
│   ├── test_segmenter.py
│   ├── test_extractor.py
│   ├── test_graph_builder.py
│   └── test_search.py
├── scripts/
│   ├── process_video.py           # CLI entry point
│   └── evaluate.py                # Evaluation scripts
├── docker-compose.yml             # Neo4j + Redis + PostgreSQL
├── pyproject.toml
├── .env.example
└── README.md
```
