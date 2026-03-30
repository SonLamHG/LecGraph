"""Video management routes."""

from fastapi import APIRouter, BackgroundTasks, HTTPException

from src.api.models import SegmentResponse, StatusResponse, VideoCreate, VideoResponse
from src.db.neo4j_client import run_query, run_write

router = APIRouter()


@router.post("", response_model=VideoResponse)
async def create_video(body: VideoCreate):
    """Add a video to the system."""
    import hashlib
    video_id = "vid_" + hashlib.md5(body.source.encode()).hexdigest()[:8]

    run_write(
        """
        MERGE (v:Video {id: $id})
        SET v.title = $source,
            v.source = $source,
            v.duration = 0,
            v.status = 'pending'
        """,
        {"id": video_id, "source": body.source},
    )

    return VideoResponse(
        id=video_id,
        title=body.source,
        source=body.source,
        duration=0.0,
        status="pending",
    )


@router.get("", response_model=list[VideoResponse])
async def list_videos():
    """List all videos."""
    rows = run_query(
        "MATCH (v:Video) RETURN v.id AS id, v.title AS title, v.source AS source, "
        "v.duration AS duration, v.status AS status ORDER BY v.title"
    )
    return [
        VideoResponse(
            id=r["id"],
            title=r.get("title", ""),
            source=r.get("source", ""),
            duration=r.get("duration", 0.0),
            status=r.get("status", "completed"),
        )
        for r in rows
    ]


@router.get("/{video_id}/segments", response_model=list[SegmentResponse])
async def get_video_segments(video_id: str):
    """Get all segments of a video."""
    rows = run_query(
        """
        MATCH (s:Segment)-[:BELONGS_TO]->(v:Video {id: $video_id})
        RETURN s.id AS id, s.video_id AS video_id, s.title AS title,
               s.start AS start, s.end AS end
        ORDER BY s.start
        """,
        {"video_id": video_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found or has no segments")

    return [
        SegmentResponse(
            id=r["id"],
            video_id=r.get("video_id", video_id),
            title=r.get("title", ""),
            start=r.get("start", 0.0),
            end=r.get("end", 0.0),
        )
        for r in rows
    ]


@router.post("/{video_id}/process", response_model=StatusResponse)
async def process_video(video_id: str, background_tasks: BackgroundTasks):
    """Trigger pipeline processing for a video."""
    # Check video exists
    rows = run_query(
        "MATCH (v:Video {id: $id}) RETURN v.source AS source, v.status AS status",
        {"id": video_id},
    )
    if not rows:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")

    source = rows[0]["source"]

    def _run_pipeline(vid_id: str, src: str):
        try:
            run_write(
                "MATCH (v:Video {id: $id}) SET v.status = 'processing'",
                {"id": vid_id},
            )
            # Import here to avoid circular imports at module load
            from scripts.process_video import _run_full_pipeline
            _run_full_pipeline(src, vid_id)
            run_write(
                "MATCH (v:Video {id: $id}) SET v.status = 'completed'",
                {"id": vid_id},
            )
        except Exception as e:
            run_write(
                "MATCH (v:Video {id: $id}) SET v.status = 'failed'",
                {"id": vid_id},
            )

    background_tasks.add_task(_run_pipeline, video_id, source)

    return StatusResponse(status="processing", message=f"Pipeline started for {video_id}")
