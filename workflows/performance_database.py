#!/usr/bin/env python3
"""
Cogitator Performance Database
Tracks scripts, clips, and YouTube performance metrics for learning.
"""
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pathlib import Path

from workflows.constants import TTS_VOICES, TTS_STYLE_OPTIONS, calculate_performance_score

from workflows.constants import WORKSPACE
DB_DIR = os.path.join(WORKSPACE, ".cogitator")
DB_PATH = os.path.join(DB_DIR, "performance.db")

os.makedirs(DB_DIR, exist_ok=True)


def get_db() -> sqlite3.Connection:
    """Get database connection with WAL mode for better concurrency."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def init_db():
    """Initialize database tables."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scripts (
            id TEXT PRIMARY KEY,
            video_name TEXT NOT NULL,
            title TEXT,
            content_type TEXT,
            script_text TEXT,
            features TEXT,  -- JSON blob for script features
            variants TEXT,  -- JSON array of alternative variants
            selected_variant INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            phase INTEGER DEFAULT 4,
            ab_test_id TEXT,  -- Links to ab_tests.id for A/B test tracking
            ab_variant TEXT,  -- 'a' or 'b' which variant this script belongs to
            FOREIGN KEY (ab_test_id) REFERENCES ab_tests(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clips (
            id TEXT PRIMARY KEY,
            script_id TEXT,
            source_file TEXT,
            start_time REAL,
            end_time REAL,
            duration REAL,
            features TEXT,  -- JSON blob for clip features
            virality_score REAL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (script_id) REFERENCES scripts(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            id TEXT PRIMARY KEY,
            script_id TEXT,
            clip_id TEXT,
            video_url TEXT,
            youtube_id TEXT,
            title TEXT,
            created_at TEXT NOT NULL,
            metrics_fetched_at TEXT,
            FOREIGN KEY (script_id) REFERENCES scripts(id),
            FOREIGN KEY (clip_id) REFERENCES clips(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metrics (
            id TEXT PRIMARY KEY,
            video_id TEXT NOT NULL,
            fetched_at TEXT NOT NULL,
            views INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            favorites INTEGER DEFAULT 0,
            engagement_ratio REAL,
            performance_score REAL,
            raw_data TEXT,  -- Full API response
            FOREIGN KEY (video_id) REFERENCES videos(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learnings (
            id TEXT PRIMARY KEY,
            feature_name TEXT NOT NULL,
            feature_value TEXT,
            metric_type TEXT,  -- views, engagement, combined
            impact_score REAL,
            sample_count INTEGER,
            confidence REAL,
            variance REAL DEFAULT 0,
            sum_squared_diff REAL DEFAULT 0,
            updated_at TEXT NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tts_learning (
            id TEXT PRIMARY KEY,
            voice TEXT NOT NULL,
            style TEXT NOT NULL,
            content_type TEXT,
            avg_engagement REAL DEFAULT 0,
            avg_views INTEGER DEFAULT 0,
            sample_count INTEGER DEFAULT 0,
            avg_performance_score REAL DEFAULT 0,
            updated_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS generation_params (
            id TEXT PRIMARY KEY,
            param_name TEXT UNIQUE NOT NULL,
            param_value TEXT,
            based_on_samples INTEGER DEFAULT 0,
            updated_at TEXT NOT NULL
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ab_tests (
            id TEXT PRIMARY KEY,
            test_name TEXT NOT NULL,
            test_type TEXT NOT NULL,  -- script_variant, voice, content_type, etc.
            variant_a TEXT NOT NULL,  -- JSON config for variant A
            variant_b TEXT NOT NULL,  -- JSON config for variant B
            status TEXT DEFAULT 'running',  -- running, completed, cancelled
            winner TEXT,  -- 'a', 'b', or 'tie'
            confidence_score REAL,
            samples_a INTEGER DEFAULT 0,
            samples_b INTEGER DEFAULT 0,
            avg_performance_a REAL DEFAULT 0,
            avg_performance_b REAL DEFAULT 0,
            created_at TEXT NOT NULL,
            completed_at TEXT
        )
    """)
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scripts_video ON scripts(video_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_youtube ON videos(youtube_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_video ON metrics(video_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_learnings_feature ON learnings(feature_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tts_learning_voice ON tts_learning(voice)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tts_learning_content ON tts_learning(content_type)")
    
    # Migrate existing scripts table: add title column if missing
    cursor.execute("PRAGMA table_info(scripts)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'title' not in columns:
        cursor.execute("ALTER TABLE scripts ADD COLUMN title TEXT")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scripts_title ON scripts(title)")

    # Migrate scripts table: add metadata columns for description, hashtags, tags
    if 'description' not in columns:
        cursor.execute("ALTER TABLE scripts ADD COLUMN description TEXT")
    if 'hashtags' not in columns:
        cursor.execute("ALTER TABLE scripts ADD COLUMN hashtags TEXT")
    if 'tags' not in columns:
        cursor.execute("ALTER TABLE scripts ADD COLUMN tags TEXT")

    cursor.execute("PRAGMA table_info(learnings)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'variance' not in columns:
        cursor.execute("ALTER TABLE learnings ADD COLUMN variance REAL DEFAULT 0")
    if 'sum_squared_diff' not in columns:
        cursor.execute("ALTER TABLE learnings ADD COLUMN sum_squared_diff REAL DEFAULT 0")

    # Migrate scripts table: add A/B test tracking columns
    cursor.execute("PRAGMA table_info(scripts)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'ab_test_id' not in columns:
        cursor.execute("ALTER TABLE scripts ADD COLUMN ab_test_id TEXT")
    if 'ab_variant' not in columns:
        cursor.execute("ALTER TABLE scripts ADD COLUMN ab_variant TEXT")
    
    conn.commit()
    conn.close()


def _extract_title_from_script(script_text: str) -> Optional[str]:
    """Extract TITLE: line from a script's raw text. Returns None if not found."""
    if not script_text:
        return None
    match = re.search(r'^TITLE:\s*(.+)$', script_text, re.MULTILINE)
    return match.group(1).strip() if match else None


def store_script(
    video_name: str,
    content_type: str,
    script_text: str,
    features: Dict[str, Any],
    variants: List[Dict] = None,
    selected_variant: int = 0,
    title: Optional[str] = None,
    description: Optional[str] = None,
    hashtags: Optional[str] = None,
    tags: Optional[str] = None,
    ab_test_id: Optional[str] = None,
    ab_variant: Optional[str] = None,
) -> str:
    """Store a generated script."""
    conn = get_db()
    cursor = conn.cursor()
    
    script_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    
    # Auto-extract title from script text if not provided
    script_title = title or _extract_title_from_script(script_text)

    cursor.execute("""
        INSERT INTO scripts (id, video_name, title, content_type, script_text, features, variants, selected_variant, created_at, description, hashtags, tags, ab_test_id, ab_variant)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        script_id,
        video_name,
        script_title,
        content_type,
        script_text,
        json.dumps(features),
        json.dumps(variants or []),
        selected_variant,
        created_at,
        description,
        hashtags,
        tags,
        ab_test_id,
        ab_variant,
    ))
    
    conn.commit()
    conn.close()
    return script_id


def store_clip(
    script_id: str,
    source_file: str,
    start_time: float,
    end_time: float,
    duration: float,
    features: Dict[str, Any],
    virality_score: float = 0.0,
) -> str:
    """Store a generated clip."""
    conn = get_db()
    cursor = conn.cursor()
    
    clip_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    
    cursor.execute("""
        INSERT INTO clips (id, script_id, source_file, start_time, end_time, duration, features, virality_score, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        clip_id,
        script_id,
        source_file,
        start_time,
        end_time,
        duration,
        json.dumps(features),
        virality_score,
        created_at,
    ))
    
    conn.commit()
    conn.close()
    return clip_id


def get_best_clips(clip_paths: list, limit: int = 1) -> list:
    """
    Get the best clips from a list of file paths based on virality score.
    
    Args:
        clip_paths: List of clip file paths (e.g., ['/path/to/shorts/video-Short001_0.mp4'])
        limit: Number of top clips to return (default: 1)
    
    Returns:
        List of clip paths sorted by virality score (highest first)
    """
    if not clip_paths:
        return []
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Group clips by game name and extract clip numbers
    game_clips = {}  # {game_name: [(clip_path, clip_number), ...]}
    for path in clip_paths:
        filename = os.path.basename(path)
        
        # Extract game name and clip number from filename pattern: {game_name}-Short{number}_{clip_number}.mp4
        match = re.match(r'^(.+)-Short(\d+)_(\d+)\.mp4$', filename)
        if match:
            game_name = match.group(1)
            short_num = match.group(2)
            clip_num = int(match.group(3))
            
            if game_name not in game_clips:
                game_clips[game_name] = []
            game_clips[game_name].append((path, clip_num))
        else:
            # Fallback: treat as single clip with number 0
            if 'unknown' not in game_clips:
                game_clips['unknown'] = []
            game_clips['unknown'].append((path, 0))
    
    # For each game, get all clips from database and match by position
    clip_scores = {}
    
    for game_name, clips in game_clips.items():
        if game_name == 'unknown':
            # Fallback for unknown clips
            for path, _ in clips:
                clip_scores[path] = 0.0
            continue
        
        # Get all clips for this game, sorted by virality score
        cursor.execute("""
            SELECT virality_score, duration 
            FROM clips 
            WHERE source_file LIKE ?
            ORDER BY virality_score DESC, duration ASC
        """, (f"%{game_name}%",))
        
        db_clips = cursor.fetchall()
        
        if not db_clips:
            # No clips in database, assign 0
            for path, _ in clips:
                clip_scores[path] = 0.0
            continue
        
        # Sort the clip paths by clip number (ascending)
        clips_sorted_by_num = sorted(clips, key=lambda x: x[1])
        
        # Match database clips to file clips by position
        # Database clips are sorted by score (highest first)
        # File clips are sorted by clip number (1, 2, 3, ...)
        for i, (path, clip_num) in enumerate(clips_sorted_by_num):
            if i < len(db_clips):
                # This clip gets the score of the i-th best database clip
                clip_scores[path] = db_clips[i][0]
            else:
                # More file clips than database clips
                clip_scores[path] = 0.0
    
    conn.close()
    
    # Sort by score (highest first) and return top N
    sorted_clips = sorted(clip_paths, key=lambda x: clip_scores.get(x, 0), reverse=True)
    return sorted_clips[:limit]


def link_video(
    script_id: str,
    clip_id: str,
    video_url: str = None,
    youtube_id: str = None,
    title: str = None
) -> str:
    """Link a YouTube video to a script/clip."""
    conn = get_db()
    cursor = conn.cursor()
    
    video_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    
    cursor.execute("""
        INSERT INTO videos (id, script_id, clip_id, video_url, youtube_id, title, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        video_id,
        script_id,
        clip_id,
        video_url,
        youtube_id,
        title,
        created_at
    ))
    
    conn.commit()
    conn.close()
    return video_id


def store_metrics(
    video_id: str,
    views: int,
    likes: int,
    comments: int,
    favorites: int = 0,
    raw_data: Dict = None
) -> str:
    """Store YouTube metrics for a video. Updates existing row if one exists for this video_id, otherwise inserts."""
    conn = get_db()
    cursor = conn.cursor()
    
    fetched_at = datetime.now(timezone.utc).isoformat()
    
    total_engagement = likes + comments
    engagement_ratio = (total_engagement / views * 100) if views > 0 else 0
    
    performance_score = calculate_performance_score(views, engagement_ratio)
    
    # Check if metrics already exist for this video
    cursor.execute("SELECT id FROM metrics WHERE video_id = ?", (video_id,))
    existing = cursor.fetchone()
    
    if existing:
        # Update existing metrics row
        metric_id = existing['id']
        cursor.execute("""
            UPDATE metrics SET
                fetched_at = ?,
                views = ?,
                likes = ?,
                comments = ?,
                favorites = ?,
                engagement_ratio = ?,
                performance_score = ?,
                raw_data = ?
            WHERE id = ?
        """, (
            fetched_at,
            views,
            likes,
            comments,
            favorites,
            engagement_ratio,
            performance_score,
            json.dumps(raw_data or {}),
            metric_id
        ))
    else:
        # Insert new metrics row
        metric_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO metrics (id, video_id, fetched_at, views, likes, comments, favorites, engagement_ratio, performance_score, raw_data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            metric_id,
            video_id,
            fetched_at,
            views,
            likes,
            comments,
            favorites,
            engagement_ratio,
            performance_score,
            json.dumps(raw_data or {})
        ))
    
    cursor.execute("""
        UPDATE videos SET metrics_fetched_at = ? WHERE id = ?
    """, (fetched_at, video_id))
    
    conn.commit()
    conn.close()
    return metric_id


def get_script_by_id(script_id: str) -> Optional[Dict]:
    """Get script by ID."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM scripts WHERE id = ?", (script_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None


def get_video_by_youtube_id(youtube_id: str) -> Optional[Dict]:
    """Get video by YouTube ID."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM videos WHERE youtube_id = ?", (youtube_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None


def get_successful_scripts(limit: int = 10, min_views: int = 0) -> List[Dict]:
    """Get scripts with highest performance scores."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT s.*, m.views, m.engagement_ratio, m.performance_score
        FROM scripts s
        JOIN videos v ON v.script_id = s.id
        JOIN metrics m ON m.video_id = v.id
        WHERE m.performance_score > 0 AND m.views >= ?
        ORDER BY m.performance_score DESC
        LIMIT ?
    """, (min_views, limit))
    
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_cross_platform_stats() -> Dict:
    """Get cross-platform performance statistics combining YouTube and TikTok.
    
    Returns aggregated stats for the unified Performance dashboard.
    """
    conn = get_db()
    cursor = conn.cursor()
    
    # YouTube stats
    cursor.execute("""
        SELECT COUNT(DISTINCT v.id) as total_videos,
               COALESCE(AVG(m.views), 0) as avg_views,
               COALESCE(AVG(m.engagement_ratio), 0) as avg_engagement,
               COALESCE(AVG(m.performance_score), 0) as avg_performance
        FROM videos v
        JOIN metrics m ON m.video_id = v.id
    """)
    yt_row = cursor.fetchone()
    
    # YouTube content type breakdown
    cursor.execute("""
        SELECT s.content_type,
               COUNT(*) as count,
               COALESCE(AVG(m.views), 0) as avg_views,
               COALESCE(AVG(m.performance_score), 0) as avg_score
        FROM scripts s
        JOIN videos v ON v.script_id = s.id
        JOIN metrics m ON m.video_id = v.id
        GROUP BY s.content_type
    """)
    yt_content = [dict(r) for r in cursor.fetchall()]
    
    # TikTok stats (from tiktok_videos table if it exists)
    tt_stats = {'total_videos': 0, 'avg_views': 0, 'avg_engagement': 0}
    try:
        cursor.execute("""
            SELECT COUNT(*) as total_videos,
                   COALESCE(AVG(total_views), 0) as avg_views,
                   CASE WHEN SUM(total_views) > 0 
                        THEN (SUM(total_likes) + SUM(total_comments) + SUM(total_shares)) * 100.0 / SUM(total_views)
                        ELSE 0 END as avg_engagement
            FROM tiktok_videos
        """)
        tt_row = cursor.fetchone()
        if tt_row:
            tt_stats = {
                'total_videos': tt_row['total_videos'],
                'avg_views': round(tt_row['avg_views'], 1),
                'avg_engagement': round(tt_row['avg_engagement'], 2),
            }
    except Exception:
        pass
    
    # TikTok game breakdown
    tt_games = []
    try:
        cursor.execute("""
            SELECT game,
                   COUNT(*) as count,
                   AVG(total_views) as avg_views,
                   CASE WHEN SUM(total_views) > 0 
                        THEN (SUM(total_likes) + SUM(total_comments) + SUM(total_shares)) * 100.0 / SUM(total_views)
                        ELSE 0 END as avg_engagement
            FROM tiktok_videos
            GROUP BY game
        """)
        tt_games = [dict(r) for r in cursor.fetchall()]
    except Exception:
        pass
    
    conn.close()
    
    return {
        'youtube': {
            'total_videos': yt_row['total_videos'] if yt_row else 0,
            'avg_views': round(yt_row['avg_views'] or 0, 1),
            'avg_engagement': round(yt_row['avg_engagement'] or 0, 2),
            'avg_performance': round(yt_row['avg_performance'] or 0, 1),
            'content_types': yt_content,
        },
        'tiktok': tt_stats,
        'tiktok_games': tt_games,
    }


def get_learnings(metric_type: str = None) -> List[Dict]:
    """Get stored learnings."""
    conn = get_db()
    cursor = conn.cursor()
    
    if metric_type:
        cursor.execute("""
            SELECT * FROM learnings 
            WHERE metric_type = ?
            ORDER BY confidence DESC, sample_count DESC
        """, (metric_type,))
    else:
        cursor.execute("SELECT * FROM learnings ORDER BY confidence DESC, sample_count DESC")
    
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def store_learning(
    feature_name: str,
    feature_value: str,
    metric_type: str,
    impact_score: float,
    sample_count: int,
    confidence: float
):
    """Store a learning, updating existing records instead of replacing."""
    conn = get_db()
    cursor = conn.cursor()
    
    updated_at = datetime.now(timezone.utc).isoformat()
    
    cursor.execute("SELECT id, sample_count, impact_score FROM learnings WHERE feature_name = ? AND feature_value = ?", (feature_name, feature_value))
    existing = cursor.fetchone()
    
    if existing:
        new_sample_count = existing['sample_count'] + sample_count
        old_impact = existing['impact_score'] or 0.0
        new_impact = (old_impact * existing['sample_count'] + impact_score * sample_count) / new_sample_count if new_sample_count > 0 else impact_score
        new_confidence = min(0.3 + new_sample_count * 0.1, 1.0)
        cursor.execute("""
            UPDATE learnings 
            SET sample_count = ?,
                confidence = ?,
                impact_score = ?,
                metric_type = ?,
                updated_at = ?
            WHERE feature_name = ? AND feature_value = ?
        """, (new_sample_count, new_confidence, new_impact, metric_type, updated_at, feature_name, feature_value))
    else:
        learning_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO learnings (id, feature_name, feature_value, metric_type, impact_score, sample_count, confidence, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (learning_id, feature_name, feature_value, metric_type, impact_score, sample_count, confidence, updated_at))
    
    conn.commit()
    conn.close()


def get_channel_baseline() -> Dict[str, float]:
    """Calculate channel baseline from historical data."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            AVG(views) as avg_views,
            AVG(engagement_ratio) as avg_engagement,
            AVG(performance_score) as avg_score,
            COUNT(*) as sample_count
        FROM metrics
        WHERE views > 0
    """)
    row = cursor.fetchone()
    conn.close()
    
    if row and row['sample_count'] > 0:
        return {
            'avg_views': row['avg_views'] or 0,
            'avg_engagement': row['avg_engagement'] or 0,
            'avg_score': row['avg_score'] or 0,
            'sample_count': row['sample_count']
        }
    
    return {'avg_views': 0, 'avg_engagement': 0, 'avg_score': 0, 'sample_count': 0}


def get_all_videos_with_metrics() -> List[Dict]:
    """Get all videos with their latest metrics row."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT v.*, s.content_type, s.features as script_features,
               m.views, m.likes, m.comments, m.engagement_ratio, m.performance_score
        FROM videos v
        LEFT JOIN scripts s ON s.id = v.script_id
        LEFT JOIN metrics m ON m.id = (
            SELECT m2.id FROM metrics m2 WHERE m2.video_id = v.id ORDER BY m2.fetched_at DESC LIMIT 1
        )
        ORDER BY v.created_at DESC
    """)
    
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_performance_stats() -> Dict[str, Any]:
    """Get overall performance statistics."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as total_videos FROM videos WHERE metrics_fetched_at IS NOT NULL")
    total_videos = cursor.fetchone()['total_videos']
    
    cursor.execute("SELECT COUNT(*) as total_scripts FROM scripts")
    total_scripts = cursor.fetchone()['total_scripts']
    
    baseline = get_channel_baseline()
    
    successful = get_successful_scripts(100)
    
    learnings = get_learnings()
    
    conn.close()
    
    return {
        'total_videos': total_videos,
        'total_scripts': total_scripts,
        'baseline': baseline,
        'successful_scripts': len(successful),
        'learnings_count': len(learnings),
        'top_learnings': learnings[:10] if learnings else []
    }


def get_all_scripts() -> List[Dict]:
    """Get all scripts from database."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scripts ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def auto_match_and_fetch(recent_videos: List[Dict]) -> Dict[str, Any]:
    """Auto-match YouTube videos to scripts and fetch metrics.
    
    Matching strategy (in priority order):
    1. Exact match: YouTube title == stored script.title (case-insensitive, whitespace-normalized)
    2. Substring match: stored script.title appears as a contiguous phrase in YouTube title
    3. Word-overlap fallback: legacy scoring (0.3+ threshold) for edge cases
    
    Args:
        recent_videos: List of videos from get_recent_uploads()
    
    Returns:
        Dict with matched_count, new_metrics, errors
    """
    matched = 0
    new_metrics = 0
    errors = []

    scripts = get_all_scripts()
    conn = get_db()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT feature_name, feature_value FROM learnings")
        existing_learning_keys = {(r['feature_name'], r['feature_value']) for r in cursor.fetchall()}

        for video in recent_videos:
            try:
                video_id = video.get('video_id', '')
                yt_title = video.get('title', '')
                duration_seconds = video.get('duration_seconds', 0)

                if duration_seconds == 0 or duration_seconds > 180:
                    import logging
                    logging.getLogger(__name__).info(
                        f"Skipping video {video_id} ({yt_title}): duration={duration_seconds}s (not a short)")
                    continue

                existing = get_video_by_youtube_id(video_id)
                if existing:
                    store_metrics(video_id=existing['id'], views=video.get('views', 0),
                                  likes=video.get('likes', 0), comments=video.get('comments', 0),
                                  favorites=0, raw_data=video)
                    new_metrics += 1
                    continue

                best_match = None
                match_reason = None
                yt_normalized = ' '.join(yt_title.lower().split())

                for script in scripts:
                    script_title = script.get('title') or ''
                    if not script_title:
                        continue
                    script_normalized = ' '.join(script_title.lower().split())
                    if yt_normalized == script_normalized:
                        best_match = script
                        match_reason = 'exact'
                        break

                if not best_match:
                    for script in scripts:
                        script_title = script.get('title') or ''
                        if not script_title:
                            continue
                        if script_title.lower() in yt_title.lower():
                            best_match = script
                            match_reason = 'substring'
                            break

                if not best_match:
                    yt_words = set(yt_normalized.split())
                    best_score = 0.0
                    for script in scripts:
                        video_name = script.get('video_name', '')
                        script_title = script.get('title') or ''
                        candidates = [video_name.lower()]
                        if script_title:
                            candidates.append(' '.join(script_title.lower().split()))
                        for candidate in candidates:
                            cand_words = set(candidate.split())
                            common = yt_words & cand_words
                            if common:
                                score = len(common) / max(len(yt_words), len(cand_words))
                                if score > best_score:
                                    best_score = score
                                    best_match = script
                                    match_reason = 'word_overlap'
                    if best_match and best_score < 0.3:
                        best_match = None

                if best_match:
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    video_db_id = link_video(script_id=best_match['id'], clip_id=None,
                                              video_url=video_url, youtube_id=video_id, title=yt_title)
                    store_metrics(video_id=video_db_id, views=video.get('views', 0),
                                  likes=video.get('likes', 0), comments=video.get('comments', 0),
                                  favorites=0, raw_data=video)
                    matched += 1
                    new_metrics += 1

                    features_str = best_match.get('features', '{}')
                    if isinstance(features_str, str):
                        try:
                            features = json.loads(features_str)
                        except json.JSONDecodeError:
                            features = {}
                    else:
                        features = features_str or {}

                    engagement_ratio = video.get('engagement_ratio', 0)
                    performance_score = calculate_performance_score(video.get('views', 0), engagement_ratio)

                    if best_match.get('content_type'):
                        update_learning_with_variance(feature_name='content_type', feature_value=best_match['content_type'],
                                       metric_type='combined', performance_score=performance_score)

                    if features.get('word_count'):
                        update_learning_with_variance(feature_name='word_count', feature_value=str(features['word_count']),
                                       metric_type='combined', performance_score=performance_score)

                    # Record A/B test result if this script is part of a test
                    try:
                        record_ab_result_for_script(best_match['id'], performance_score)
                    except Exception:
                        pass

                    clip_cursor = conn.cursor()
                    clip_cursor.execute("""
                        SELECT c.features FROM clips c
                        JOIN videos v ON v.clip_id = c.id
                        WHERE v.script_id = ? LIMIT 1
                    """, (best_match['id'],))
                    clip_row = clip_cursor.fetchone()
                    clip_cursor.close()
                    if clip_row:
                        clip_features = json.loads(clip_row['features'] or '{}')
                        voice = clip_features.get('voice', '')
                        style = clip_features.get('style', '')
                        if voice:
                            update_tts_learning(voice=voice, style=style or '',
                                                content_type=best_match.get('content_type'),
                                                views=video.get('views', 0),
                                                engagement_ratio=engagement_ratio,
                                                performance_score=performance_score)
            except Exception as e:
                errors.append(str(e))
    except Exception as e:
        errors.append(str(e))
    finally:
        conn.close()

    return {
        'matched_count': matched,
        'new_metrics': new_metrics,
        'errors': errors,
        'total_videos_processed': len(recent_videos)
    }


def sync_youtube_metrics(days: int = 7, max_results: int = 50) -> Dict[str, Any]:
    """Unified YouTube metrics sync: fetch recent uploads, backfill titles, auto-match.
    
    Single entry point for all YouTube sync operations.
    Call this from pipeline completion, API endpoints, or manual sync.
    
    Returns:
        Dict with matched_count, new_metrics, errors, total_videos_processed
    """
    try:
        from workflows.metrics_fetcher import get_recent_uploads
    except ImportError:
        from workflows.metrics_fetcher import get_recent_uploads
    
    backfill_script_titles()
    videos = get_recent_uploads(days=days, max_results=max_results)
    if not videos:
        return {'matched_count': 0, 'new_metrics': 0, 'errors': [], 'total_videos_processed': 0}
    return auto_match_and_fetch(videos)


def backfill_script_titles() -> Dict[str, Any]:
    """Backfill the title column for existing scripts from .txt files.
    
    Returns dict with updated_count, errors.
    """
    updated = 0
    errors = []
    scripts_dir = os.path.join(WORKSPACE, "scripts")
    
    if not os.path.exists(scripts_dir):
        return {'updated_count': 0, 'errors': ['scripts directory does not exist']}
    
    conn = get_db()
    cursor = conn.cursor()
    
    for fname in os.listdir(scripts_dir):
        if not fname.endswith(".txt"):
            continue
        
        fpath = os.path.join(scripts_dir, fname)
        try:
            with open(fpath, "r") as f:
                script_text = f.read()
        except Exception as e:
            errors.append(f"Failed to read {fname}: {e}")
            continue
        
        title = _extract_title_from_script(script_text)
        if not title:
            errors.append(f"No TITLE: found in {fname}")
            continue
        
        base_name = os.path.splitext(fname)[0]
        
        if '-Script' in base_name:
            video_basename = base_name.rsplit('-Script', 1)[0].strip()
        else:
            video_basename = base_name
        
        cursor.execute(
            "UPDATE scripts SET title = ? WHERE video_name = ? AND (title IS NULL OR title = '')",
            (title, video_basename)
        )
        if cursor.rowcount > 0:
            updated += cursor.rowcount
    
    conn.commit()
    conn.close()
    
    return {'updated_count': updated, 'errors': errors}


def update_tts_learning(
    voice: str,
    style: str,
    content_type: str = None,
    views: int = 0,
    engagement_ratio: float = 0,
    performance_score: float = 0
):
    """Update TTS learning with performance data. Creates or updates record."""
    conn = get_db()
    cursor = conn.cursor()

    updated_at = datetime.now(timezone.utc).isoformat()

    cursor.execute("""
        SELECT id, sample_count, avg_views, avg_engagement, avg_performance_score
        FROM tts_learning
        WHERE voice = ? AND style = ? AND (content_type = ? OR (content_type IS NULL AND ? IS NULL))
    """, (voice, style, content_type, content_type))
    existing = cursor.fetchone()

    if existing:
        old_count = existing['sample_count']
        old_views = existing['avg_views'] or 0
        old_eng = existing['avg_engagement'] or 0
        old_score = existing['avg_performance_score'] or 0

        new_count = old_count + 1
        new_views = (old_views * old_count + views) / new_count
        new_eng = (old_eng * old_count + engagement_ratio) / new_count
        new_score = (old_score * old_count + performance_score) / new_count

        cursor.execute("""
            UPDATE tts_learning
            SET avg_views = ?, avg_engagement = ?, avg_performance_score = ?,
                sample_count = ?, updated_at = ?
            WHERE voice = ? AND style = ? AND (content_type = ? OR (content_type IS NULL AND ? IS NULL))
        """, (new_views, new_eng, new_score, new_count, updated_at, voice, style, content_type, content_type))
    else:
        learning_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO tts_learning
            (id, voice, style, content_type, avg_views, avg_engagement,
             avg_performance_score, sample_count, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
        """, (learning_id, voice, style, content_type, views, engagement_ratio,
              performance_score, updated_at))

    conn.commit()
    conn.close()


def get_tts_learning_data() -> List[Dict]:
    """Get all TTS learning records."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM tts_learning
        WHERE sample_count >= 1
        ORDER BY avg_performance_score DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_weighted_tts_voices() -> List[Dict]:
    """Get TTS voice/style combos weighted by performance.

    Returns list sorted by weight (descending). Combos with no data get weight 0.1.
    Cached with 5-minute TTL to avoid regenerating 300 combinations on every call.
    """
    import time
    if hasattr(get_weighted_tts_voices, '_cache') and hasattr(get_weighted_tts_voices, '_cache_time'):
        if time.time() - get_weighted_tts_voices._cache_time < 300:
            return get_weighted_tts_voices._cache

    all_tts_data = get_tts_learning_data()

    tts_map = {}
    for r in all_tts_data:
        key = (r['voice'], r['style'])
        tts_map[key] = r.get('avg_performance_score', 0)

    max_score = max((v for v in tts_map.values()), default=1)
    if max_score == 0:
        max_score = 1

    weighted = []
    for voice in TTS_VOICES:
        for style in TTS_STYLE_OPTIONS:
            key = (voice, style)
            raw = tts_map.get(key, 0)
            weight = max(0.1, raw / max_score) if raw > 0 else 0.1
            weighted.append({'voice': voice, 'style': style, 'weight': weight})

    weighted.sort(key=lambda x: x['weight'], reverse=True)

    get_weighted_tts_voices._cache = weighted
    get_weighted_tts_voices._cache_time = time.time()
    return weighted


def get_variant_performance_stats() -> Dict[str, Dict]:
    """Get performance stats grouped by variant (content_type)."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT s.content_type,
               COUNT(s.id) as script_count,
               AVG(m.views) as avg_views,
               AVG(m.engagement_ratio) as avg_engagement,
               AVG(m.performance_score) as avg_score,
               MAX(m.performance_score) as max_score
        FROM scripts s
        JOIN videos v ON v.script_id = s.id
        JOIN metrics m ON m.video_id = v.id
        WHERE s.content_type IS NOT NULL AND m.views > 0
        GROUP BY s.content_type
        ORDER BY avg_score DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    result = {}
    for row in rows:
        ct = row['content_type']
        if ct:
            result[ct] = {
                'script_count': row['script_count'] or 0,
                'avg_views': row['avg_views'] or 0,
                'avg_engagement': row['avg_engagement'] or 0,
                'avg_score': row['avg_score'] or 0,
                'max_score': row['max_score'] or 0,
            }
    return result


def get_learned_variant_weights(min_samples: int = 3) -> Dict[str, float]:
    """Get variant weights based on historical performance.

    Returns dict of {variant: weight} where weight is relative performance score.
    Variants with insufficient samples get weight 1.0 (neutral).
    """
    stats = get_variant_performance_stats()
    if not stats:
        return {}

    max_avg = max(v.get('avg_score', 0) for v in stats.values())
    if max_avg == 0:
        return {}

    weights = {}
    for variant, data in stats.items():
        if data.get('script_count', 0) < min_samples:
            weights[variant] = 1.0
        else:
            normalized = data.get('avg_score', 0) / max_avg
            weights[variant] = max(0.2, normalized)

    return weights


def update_learning_with_variance(
    feature_name: str,
    feature_value: str,
    metric_type: str,
    performance_score: float
):
    """Update learning with variance tracking for Thompson Sampling."""
    conn = get_db()
    cursor = conn.cursor()
    
    updated_at = datetime.now(timezone.utc).isoformat()
    
    cursor.execute("""
        SELECT id, sample_count, impact_score, sum_squared_diff
        FROM learnings 
        WHERE feature_name = ? AND feature_value = ?
    """, (feature_name, feature_value))
    existing = cursor.fetchone()
    
    if existing:
        old_count = existing['sample_count'] or 0
        old_mean = existing['impact_score'] or 0
        old_ssd = existing['sum_squared_diff'] or 0
        
        new_count = old_count + 1
        new_mean = (old_mean * old_count + performance_score) / new_count
        
        if old_count > 0:
            new_ssd = old_ssd + (performance_score - old_mean) ** 2
            new_variance = new_ssd / new_count if new_count > 1 else 0
        else:
            new_ssd = 0
            new_variance = 0
        
        new_confidence = min(0.3 + new_count * 0.1, 0.95)
        
        cursor.execute("""
            UPDATE learnings 
            SET sample_count = ?,
                impact_score = ?,
                confidence = ?,
                variance = ?,
                sum_squared_diff = ?,
                updated_at = ?
            WHERE feature_name = ? AND feature_value = ?
        """, (new_count, new_mean, new_confidence, new_variance, new_ssd, updated_at, feature_name, feature_value))
    else:
        learning_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO learnings (id, feature_name, feature_value, metric_type, impact_score, sample_count, confidence, variance, sum_squared_diff, updated_at)
            VALUES (?, ?, ?, ?, ?, 1, 0.3, 0, 0, ?)
        """, (learning_id, feature_name, feature_value, metric_type, performance_score, updated_at))
    
    conn.commit()
    conn.close()


def get_thompson_sampling_weights(explore_ratio: float = 0.3) -> Dict[str, float]:
    """Get content type weights using Thompson Sampling (70/30 explore-exploit).
    
    Args:
        explore_ratio: 0.3 = 30% explore, 70% exploit
    
    Returns:
        Dict of {content_type: weight} with Thompson Sampling sampling
    """
    import random
    import math
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT feature_value, impact_score, variance, sample_count
        FROM learnings 
        WHERE feature_name = 'content_type' AND sample_count >= 1
    """)
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return {}
    
    sampled_scores = {}
    for row in rows:
        content_type = row['feature_value']
        mean = row['impact_score'] or 0.5
        variance = row['variance'] or 0.01
        samples = row['sample_count'] or 1
        
        std_dev = math.sqrt(variance) + 0.01
        
        alpha = max(mean * samples, 1)
        beta = max((1 - mean) * samples, 1)
        
        try:
            from random import betavariate
            sampled_value = betavariate(alpha, beta)
        except Exception:
            sampled_value = max(0, min(1, random.gauss(mean, std_dev)))
        
        sampled_scores[content_type] = sampled_value
    
    if not sampled_scores:
        return {}
    
    best_type = max(sampled_scores.items(), key=lambda x: x[1])
    
    content_types = list(sampled_scores.keys())
    
    if random.random() < explore_ratio:
        selected = random.choice(content_types)
    else:
        selected = best_type[0]
    
    weights = {}
    max_score = max(sampled_scores.values()) or 1
    for ct, score in sampled_scores.items():
        normalized = score / max_score if max_score > 0 else 0.5
        weights[ct] = max(0.3, normalized)
    
    return {'weights': weights, 'selected': selected, 'sampled_scores': sampled_scores}


def select_content_type_70_30() -> str:
    """Select content type using 70/30 explore-exploit strategy.
    
    Returns the selected content type based on Thompson Sampling.
    70% of the time: exploit (best performer)
    30% of the time: explore (random to find new winners)
    """
    result = get_thompson_sampling_weights(explore_ratio=0.3)
    if not result:
        return None
    
    return result.get('selected')


def get_content_type_effectiveness() -> Dict[str, Dict[str, Any]]:
    """Get effectiveness metrics for each content type.
    
    Returns dict of {content_type: {avg_relative_score, sample_count, trend}}
    """
    baseline = get_channel_baseline()
    if baseline['sample_count'] == 0:
        return {}
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT s.content_type, 
               AVG(m.performance_score) as avg_score,
               AVG(m.views) as avg_views,
               COUNT(*) as sample_count
        FROM scripts s
        JOIN videos v ON v.script_id = s.id
        JOIN metrics m ON m.video_id = v.id
        WHERE s.content_type IS NOT NULL AND m.views > 0
        GROUP BY s.content_type
        HAVING sample_count >= 1
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    effectiveness = {}
    for row in rows:
        ct = row['content_type']
        avg_score = row['avg_score'] or 50
        avg_views = row['avg_views'] or 0
        samples = row['sample_count']
        
        relative_score = avg_score / max(baseline['avg_score'], 1)
        relative_views = avg_views / max(baseline['avg_views'], 1)
        
        effectiveness[ct] = {
            'avg_relative_score': round(relative_score, 2),
            'avg_relative_views': round(relative_views, 2),
            'sample_count': samples,
            'is_top_performer': relative_score > 1.2,
        }
    
    return effectiveness


def get_learning_insights() -> Dict[str, Any]:
    """Get actionable learning insights for prompt injection.
    
    Returns insights that can be directly injected into prompts.
    """
    baseline = get_channel_baseline()
    if baseline['sample_count'] < 2:
        return {'has_insights': False, 'message': 'Not enough data yet (need 2+ videos)'}
    
    insights = []
    
    # Content type insights
    ct_effectiveness = get_content_type_effectiveness()
    if ct_effectiveness:
        top_performers = [ct for ct, data in ct_effectiveness.items() if data['is_top_performer']]
        if top_performers:
            insights.append(f"Top-performing content types: {', '.join(top_performers)}")
        
        # Find worst performer
        worst = min(ct_effectiveness.items(), key=lambda x: x[1]['avg_relative_score'])
        if worst[1]['avg_relative_score'] < 0.8:
            insights.append(f"Consider avoiding: {worst[0]} (underperforming by {1 - worst[1]['avg_relative_score']:.0%})")
    
    # Get successful scripts for pattern analysis
    successful = get_successful_scripts(10)
    if successful:
        # Analyze word count patterns
        wc_scores = [(s.get('word_count', 0), s.get('performance_score', 50)) for s in successful if s.get('word_count')]
        if wc_scores:
            avg_wc = sum(wc for wc, _ in wc_scores) / len(wc_scores)
            best_wc = max(wc_scores, key=lambda x: x[1])[0]
            insights.append(f"Optimal word count: ~{best_wc} words (channel avg: {int(avg_wc)})")
        
        # Analyze hook patterns
        scripts_with_hooks = [s for s in successful if s.get('hook_score', 0) > 0.5]
        if len(scripts_with_hooks) > len(successful) * 0.5:
            insights.append("Strong hooks correlate with better performance")
    
    return {
        'has_insights': len(insights) > 0,
        'insights': insights,
        'baseline': baseline,
        'content_types': ct_effectiveness,
    }


# ============================================================================
# A/B TEST FRAMEWORK
# ============================================================================

def create_ab_test(test_name: str, test_type: str, variant_a: Dict, variant_b: Dict) -> str:
    """Create a new A/B test."""
    conn = get_db()
    cursor = conn.cursor()
    
    test_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    
    cursor.execute("""
        INSERT INTO ab_tests (id, test_name, test_type, variant_a, variant_b, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'running', ?)
    """, (test_id, test_name, test_type, json.dumps(variant_a), json.dumps(variant_b), created_at))
    
    conn.commit()
    conn.close()
    return test_id


def record_ab_test_result(test_id: str, variant: str, performance_score: float) -> None:
    """Record a result for an A/B test variant ('a' or 'b')."""
    conn = get_db()
    cursor = conn.cursor()
    
    test = cursor.execute("SELECT * FROM ab_tests WHERE id = ?", (test_id,)).fetchone()
    if not test:
        conn.close()
        return
    
    if variant == 'a':
        cursor.execute("""
            UPDATE ab_tests 
            SET samples_a = samples_a + 1,
                avg_performance_a = (avg_performance_a * samples_a + ?) / (samples_a + 1)
            WHERE id = ?
        """, (performance_score, test_id))
    elif variant == 'b':
        cursor.execute("""
            UPDATE ab_tests 
            SET samples_b = samples_b + 1,
                avg_performance_b = (avg_performance_b * samples_b + ?) / (samples_b + 1)
            WHERE id = ?
        """, (performance_score, test_id))
    
    conn.commit()
    conn.close()


def get_ab_test_results(test_id: str) -> Optional[Dict]:
    """Get A/B test results with statistical significance."""
    conn = get_db()
    cursor = conn.cursor()
    
    test = cursor.execute("SELECT * FROM ab_tests WHERE id = ?", (test_id,)).fetchone()
    if not test:
        conn.close()
        return None
    
    result = {
        'id': test['id'],
        'test_name': test['test_name'],
        'test_type': test['test_type'],
        'variant_a': json.loads(test['variant_a']),
        'variant_b': json.loads(test['variant_b']),
        'status': test['status'],
        'winner': test['winner'],
        'samples_a': test['samples_a'],
        'samples_b': test['samples_b'],
        'avg_performance_a': test['avg_performance_a'],
        'avg_performance_b': test['avg_performance_b'],
        'created_at': test['created_at'],
        'completed_at': test['completed_at'],
    }
    
    # Calculate confidence if we have enough samples
    if test['samples_a'] >= 5 and test['samples_b'] >= 5:
        # Simple confidence based on performance difference
        diff = abs(test['avg_performance_a'] - test['avg_performance_b'])
        min_samples = min(test['samples_a'], test['samples_b'])
        confidence = min(0.95, (diff / 50) * (min_samples / 10))  # Simplified
        result['confidence_score'] = confidence
        
        # Determine winner if confidence is high enough
        if confidence > 0.8 and test['status'] == 'running':
            winner = 'a' if test['avg_performance_a'] > test['avg_performance_b'] else 'b'
            cursor.execute("""
                UPDATE ab_tests SET winner = ?, confidence_score = ?, status = 'completed', completed_at = ?
                WHERE id = ?
            """, (winner, confidence, datetime.now(timezone.utc).isoformat(), test_id))
            result['winner'] = winner
            result['status'] = 'completed'
    
    conn.commit()
    conn.close()
    return result


def get_active_ab_tests() -> List[Dict]:
    """Get all active A/B tests."""
    conn = get_db()
    cursor = conn.cursor()
    
    tests = cursor.execute("SELECT * FROM ab_tests WHERE status = 'running' ORDER BY created_at DESC").fetchall()
    
    results = []
    for test in tests:
        results.append({
            'id': test['id'],
            'test_name': test['test_name'],
            'test_type': test['test_type'],
            'samples_a': test['samples_a'],
            'samples_b': test['samples_b'],
            'avg_performance_a': test['avg_performance_a'],
            'avg_performance_b': test['avg_performance_b'],
            'created_at': test['created_at'],
        })
    
    conn.close()
    return results


def get_ab_test_history() -> List[Dict]:
    """Get completed A/B test history."""
    conn = get_db()
    cursor = conn.cursor()
    
    tests = cursor.execute("SELECT * FROM ab_tests WHERE status = 'completed' ORDER BY completed_at DESC").fetchall()
    
    results = []
    for test in tests:
        results.append({
            'id': test['id'],
            'test_name': test['test_name'],
            'test_type': test['test_type'],
            'winner': test['winner'],
            'confidence_score': test['confidence_score'],
            'samples_a': test['samples_a'],
            'samples_b': test['samples_b'],
            'avg_performance_a': test['avg_performance_a'],
            'avg_performance_b': test['avg_performance_b'],
            'completed_at': test['completed_at'],
        })
    
    conn.close()
    return results


# ─── A/B Test Automation ─────────────────────────────────────────────────────

# Test types and their possible variants
AB_TEST_TYPES = {
    'content_type': {
        'name': 'Content Type',
        'variants': ['mystery_recap', 'breakdown', 'timeline', 'lesson', 'narrative', 'news_report', 'documentary', 'true_crime', 'character_pov', 'true_story'],
    },
    'tts_voice': {
        'name': 'TTS Voice',
        'variants': ['af_heart', 'af_bella', 'af_nicole', 'af_sarah', 'am_adam', 'am_michael'],
    },
    'script_style': {
        'name': 'Script Style',
        'variants': ['direct_hook', 'question_hook', 'story_hook', 'shock_hook'],
    },
    'duration': {
        'name': 'Video Duration',
        'variants': ['short_20s', 'medium_35s', 'long_50s'],
    },
}


def get_or_create_ab_test(test_type: str = None) -> Optional[Dict]:
    """Get an active A/B test or create a new one.
    
    Automatically selects a test type if not specified.
    Returns dict with test_id, variant_a, variant_b, and which variant to use.
    """
    conn = get_db()
    cursor = conn.cursor()
    
    # Check for existing active test
    existing = cursor.execute(
        "SELECT * FROM ab_tests WHERE status = 'running' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    
    if existing:
        result = {
            'test_id': existing['id'],
            'test_name': existing['test_name'],
            'test_type': existing['test_type'],
            'variant_a': json.loads(existing['variant_a']),
            'variant_b': json.loads(existing['variant_b']),
            'samples_a': existing['samples_a'],
            'samples_b': existing['samples_b'],
        }
        conn.close()
        return result
    
    # No active test — create a new one
    if not test_type:
        # Pick a random test type
        import random
        test_type = random.choice(list(AB_TEST_TYPES.keys()))
    
    test_config = AB_TEST_TYPES.get(test_type)
    if not test_config:
        conn.close()
        return None
    
    import random
    variants = test_config['variants']
    # Pick two random variants for A/B comparison
    if len(variants) >= 2:
        chosen = random.sample(variants, 2)
    else:
        chosen = [variants[0], variants[0]]
    
    variant_a = {'value': chosen[0], 'label': f"{test_config['name']}: {chosen[0]}"}
    variant_b = {'value': chosen[1], 'label': f"{test_config['name']}: {chosen[1]}"}
    
    test_id = create_ab_test(
        test_name=f"Auto: {test_config['name']} ({chosen[0]} vs {chosen[1]})",
        test_type=test_type,
        variant_a=variant_a,
        variant_b=variant_b,
    )
    
    conn.close()
    return {
        'test_id': test_id,
        'test_name': f"Auto: {test_config['name']} ({chosen[0]} vs {chosen[1]})",
        'test_type': test_type,
        'variant_a': variant_a,
        'variant_b': variant_b,
        'samples_a': 0,
        'samples_b': 0,
    }


def assign_ab_variant(test_id: str, script_number: int) -> str:
    """Assign a variant ('a' or 'b') based on script number (round-robin).
    
    Even-numbered scripts get variant 'a', odd get variant 'b'.
    """
    return 'a' if script_number % 2 == 0 else 'b'


def record_ab_result_for_script(script_id: str, performance_score: float) -> None:
    """Record A/B test result when metrics are fetched for a script.
    
    Looks up the script's ab_test_id and ab_variant, then records the result.
    """
    conn = get_db()
    cursor = conn.cursor()
    
    script = cursor.execute(
        "SELECT ab_test_id, ab_variant FROM scripts WHERE id = ?", (script_id,)
    ).fetchone()
    
    if not script or not script['ab_test_id'] or not script['ab_variant']:
        conn.close()
        return
    
    test_id = script['ab_test_id']
    variant = script['ab_variant']
    
    conn.close()
    
    # Record the result (this updates samples count and avg performance)
    record_ab_test_result(test_id, variant, performance_score)
    
    # Check if test should be completed
    result = get_ab_test_results(test_id)
    if result and result.get('status') == 'completed':
        _feed_ab_winner_to_learning(result)


def _feed_ab_winner_to_learning(test_result: Dict) -> None:
    """Feed A/B test winner into the learning system.
    
    Boosts the winning variant's weight in the learnings table.
    """
    test_type = test_result.get('test_type', '')
    winner = test_result.get('winner', '')
    
    if not winner or winner == 'tie':
        return
    
    # Determine the winning value
    variant_key = f'variant_{winner}'
    winning_variant = test_result.get(variant_key, {})
    winning_value = winning_variant.get('value', '')
    
    if not winning_value:
        return
    
    # Calculate boost based on performance difference
    avg_a = test_result.get('avg_performance_a', 50)
    avg_b = test_result.get('avg_performance_b', 50)
    winner_avg = avg_a if winner == 'a' else avg_b
    loser_avg = avg_b if winner == 'a' else avg_a
    
    # Boost score: winner gets positive, loser gets negative
    boost = min(20.0, max(-10.0, (winner_avg - loser_avg) * 0.5))
    
    # Record in learnings table
    update_learning_with_variance(
        feature_name=f'ab_test_{test_type}',
        feature_value=winning_value,
        metric_type='ab_test',
        performance_score=50 + boost,  # Center around 50 so boost is relative
    )
    
    # Also boost the regular content_type or tts_voice learning
    if test_type == 'content_type':
        update_learning_with_variance(
            feature_name='content_type',
            feature_value=winning_value,
            metric_type='combined',
            performance_score=winner_avg,
        )
    elif test_type == 'tts_voice':
        update_learning_with_variance(
            feature_name='tts_voice',
            feature_value=winning_value,
            metric_type='combined',
            performance_score=winner_avg,
        )


def get_current_ab_test_info() -> Optional[Dict]:
    """Get info about the current active A/B test for display on dashboard."""
    conn = get_db()
    cursor = conn.cursor()
    
    test = cursor.execute(
        "SELECT * FROM ab_tests WHERE status = 'running' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    
    if not test:
        conn.close()
        return None
    
    # Count scripts assigned to each variant
    cursor.execute("""
        SELECT ab_variant, COUNT(*) as count
        FROM scripts
        WHERE ab_test_id = ?
        GROUP BY ab_variant
    """, (test['id'],))
    variant_counts = {row['ab_variant']: row['count'] for row in cursor.fetchall()}
    
    conn.close()
    
    return {
        'id': test['id'],
        'test_name': test['test_name'],
        'test_type': test['test_type'],
        'variant_a': json.loads(test['variant_a']),
        'variant_b': json.loads(test['variant_b']),
        'samples_a': test['samples_a'],
        'samples_b': test['samples_b'],
        'avg_performance_a': test['avg_performance_a'],
        'avg_performance_b': test['avg_performance_b'],
        'created_at': test['created_at'],
        'scripts_a': variant_counts.get('a', 0),
        'scripts_b': variant_counts.get('b', 0),
    }


init_db()