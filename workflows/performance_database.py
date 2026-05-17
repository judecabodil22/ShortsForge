#!/usr/bin/env python3
"""
ShortsForge Performance Database
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

WORKSPACE = os.path.expanduser("~/ShortsForge")
DB_DIR = os.path.join(WORKSPACE, ".shortsforge")
DB_PATH = os.path.join(DB_DIR, "performance.db")

os.makedirs(DB_DIR, exist_ok=True)


def get_db() -> sqlite3.Connection:
    """Get database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database tables."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scripts (
            id TEXT PRIMARY KEY,
            video_name TEXT NOT NULL,
            content_type TEXT,
            script_text TEXT,
            features TEXT,  -- JSON blob for script features
            variants TEXT,  -- JSON array of alternative variants
            selected_variant INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            phase INTEGER DEFAULT 4
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
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scripts_video ON scripts(video_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_videos_youtube ON videos(youtube_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_metrics_video ON metrics(video_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_learnings_feature ON learnings(feature_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tts_learning_voice ON tts_learning(voice)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tts_learning_content ON tts_learning(content_type)")
    
    cursor.execute("PRAGMA table_info(learnings)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'variance' not in columns:
        cursor.execute("ALTER TABLE learnings ADD COLUMN variance REAL DEFAULT 0")
    if 'sum_squared_diff' not in columns:
        cursor.execute("ALTER TABLE learnings ADD COLUMN sum_squared_diff REAL DEFAULT 0")
    
    conn.commit()
    conn.close()


def store_script(
    video_name: str,
    content_type: str,
    script_text: str,
    features: Dict[str, Any],
    variants: List[Dict] = None,
    selected_variant: int = 0
) -> str:
    """Store a generated script."""
    conn = get_db()
    cursor = conn.cursor()
    
    script_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    
    cursor.execute("""
        INSERT INTO scripts (id, video_name, content_type, script_text, features, variants, selected_variant, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        script_id,
        video_name,
        content_type,
        script_text,
        json.dumps(features),
        json.dumps(variants or []),
        selected_variant,
        created_at
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
    virality_score: float = 0.0
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
        created_at
    ))
    
    conn.commit()
    conn.close()
    return clip_id


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
    """Store YouTube metrics for a video."""
    conn = get_db()
    cursor = conn.cursor()
    
    metric_id = str(uuid.uuid4())
    fetched_at = datetime.now(timezone.utc).isoformat()
    
    total_engagement = likes + comments
    engagement_ratio = (total_engagement / views * 100) if views > 0 else 0
    
    performance_score = _calculate_performance_score(views, engagement_ratio)
    
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


def _calculate_performance_score(views: int, engagement_ratio: float) -> float:
    """Calculate a combined performance score (0-100)."""
    if views == 0:
        return 0.0
    
    views_score = min(views / 100, 100) * 0.4
    engagement_score = min(engagement_ratio * 10, 100) * 0.6
    
    return views_score + engagement_score


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


def get_metrics_for_video(video_id: str) -> Optional[Dict]:
    """Get latest metrics for a video."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM metrics 
        WHERE video_id = ? 
        ORDER BY fetched_at DESC 
        LIMIT 1
    """, (video_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    return None


def get_successful_scripts(limit: int = 10) -> List[Dict]:
    """Get scripts with highest performance scores."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT s.*, m.views, m.engagement_ratio, m.performance_score
        FROM scripts s
        JOIN videos v ON v.script_id = s.id
        JOIN metrics m ON m.video_id = v.id
        WHERE m.performance_score > 0
        ORDER BY m.performance_score DESC
        LIMIT ?
    """, (limit,))
    
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


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
    
    cursor.execute("SELECT id, sample_count FROM learnings WHERE feature_name = ? AND feature_value = ?", (feature_name, feature_value))
    existing = cursor.fetchone()
    
    if existing:
        new_sample_count = existing['sample_count'] + sample_count
        new_confidence = min(0.3 + new_sample_count * 0.1, 1.0)
        cursor.execute("""
            UPDATE learnings 
            SET sample_count = ?,
                confidence = ?,
                updated_at = ?
            WHERE feature_name = ? AND feature_value = ?
        """, (new_sample_count, new_confidence, updated_at, feature_name, feature_value))
    else:
        learning_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO learnings (id, feature_name, feature_value, metric_type, impact_score, sample_count, confidence, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (learning_id, feature_name, feature_value, metric_type, impact_score, sample_count, confidence, updated_at))
    
    conn.commit()
    conn.close()


def get_generation_params() -> Dict[str, Any]:
    """Get current generation parameters."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT param_name, param_value FROM generation_params")
    rows = cursor.fetchall()
    conn.close()
    
    params = {}
    for row in rows:
        try:
            params[row['param_name']] = json.loads(row['param_value'])
        except:
            params[row['param_name']] = row['param_value']
    
    return params


def update_generation_param(param_name: str, param_value: Any):
    """Update a generation parameter."""
    conn = get_db()
    cursor = conn.cursor()
    
    updated_at = datetime.now(timezone.utc).isoformat()
    cursor.execute("""
        INSERT OR REPLACE INTO generation_params (id, param_name, param_value, based_on_samples, updated_at)
        VALUES (
            COALESCE((SELECT id FROM generation_params WHERE param_name = ?), ?),
            ?, ?, COALESCE((SELECT based_on_samples FROM generation_params WHERE param_name = ?) + 1, 1), ?
        )
    """, (
        param_name, str(uuid.uuid4()),
        param_name, json.dumps(param_value),
        param_name, updated_at
    ))
    
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
    """Get all videos with their metrics."""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT v.*, s.content_type, s.features as script_features,
               m.views, m.likes, m.comments, m.engagement_ratio, m.performance_score
        FROM videos v
        LEFT JOIN scripts s ON s.id = v.script_id
        LEFT JOIN metrics m ON m.video_id = v.id
        ORDER BY m.fetched_at DESC
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
    
    Args:
        recent_videos: List of videos from get_recent_uploads()
    
    Returns:
        Dict with matched_count, new_metrics, errors
    """
    matched = 0
    new_metrics = 0
    errors = []
    
    scripts = get_all_scripts()
    script_map = {}
    for script in scripts:
        video_name = script.get('video_name', '')
        if video_name:
            script_map[video_name.lower()] = script
    
    existing_learning_keys = set()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT feature_name, feature_value FROM learnings")
    for row in cursor.fetchall():
        existing_learning_keys.add((row['feature_name'], row['feature_value']))
    conn.close()
    
    for video in recent_videos:
        video_id = video.get('video_id', '')
        title = video.get('title', '')
        duration_seconds = video.get('duration_seconds', 0)

        if duration_seconds == 0 or duration_seconds > 180:
            continue

        existing = get_video_by_youtube_id(video_id)
        if existing:
            continue

        title_clean = re.sub(r'[^\w\s]', ' ', title.lower())
        title_words = set(title_clean.split())
        
        best_match = None
        best_score = 0
        
        for script_video_name, script_data in script_map.items():
            script_words = set(script_video_name.split())
            common = title_words & script_words
            if common:
                score = len(common) / max(len(title_words), len(script_words))
                if score > best_score:
                    best_score = score
                    best_match = script_data
        
        if best_match and best_score >= 0.3:
            try:
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                video_db_id = link_video(
                    script_id=best_match['id'],
                    clip_id=None,
                    video_url=video_url,
                    youtube_id=video_id,
                    title=title
                )
                
                store_metrics(
                    video_id=video_db_id,
                    views=video.get('views', 0),
                    likes=video.get('likes', 0),
                    comments=video.get('comments', 0),
                    favorites=0,
                    raw_data=video
                )
                
                matched += 1
                new_metrics += 1
                
                features_str = best_match.get('features', '{}')
                if isinstance(features_str, str):
                    try:
                        features = json.loads(features_str)
                    except:
                        features = {}
                else:
                    features = features_str or {}
                
                engagement_ratio = video.get('engagement_ratio', 0)
                performance_score = _calculate_performance_score(video.get('views', 0), engagement_ratio)
                
                if best_match.get('content_type'):
                    key = ('content_type', best_match['content_type'])
                    existing_learning_keys.add(key)
                    store_learning(
                        feature_name='content_type',
                        feature_value=best_match['content_type'],
                        metric_type='combined',
                        impact_score=performance_score / 100,
                        sample_count=1,
                        confidence=0.3
                    )
                
                if features.get('word_count'):
                    key = ('word_count', str(features['word_count']))
                    existing_learning_keys.add(key)
                    store_learning(
                        feature_name='word_count',
                        feature_value=str(features['word_count']),
                        metric_type='combined',
                        impact_score=performance_score / 100,
                        sample_count=1,
                        confidence=0.3
                    )

                clip_cursor = conn.cursor()
                clip_cursor.execute("""
                    SELECT c.features FROM clips c
                    JOIN videos v ON v.clip_id = c.id
                    WHERE v.script_id = ?
                    LIMIT 1
                """, (best_match['id'],))
                clip_row = clip_cursor.fetchone()
                clip_cursor.close()
                if clip_row:
                    clip_features = json.loads(clip_row['features'] or '{}')
                    voice = clip_features.get('voice', '')
                    style = clip_features.get('style', '')
                    if voice:
                        update_tts_learning(
                            voice=voice,
                            style=style or '',
                            content_type=best_match.get('content_type'),
                            views=video.get('views', 0),
                            engagement_ratio=engagement_ratio,
                            performance_score=performance_score
                        )
                
            except Exception as e:
                errors.append(str(e))
    
    return {
        'matched_count': matched,
        'new_metrics': new_metrics,
        'errors': errors,
        'total_videos_processed': len(recent_videos)
    }


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
        WHERE voice = ? AND style = ?
    """, (voice, style))
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
            WHERE voice = ? AND style = ?
        """, (new_views, new_eng, new_score, new_count, updated_at, voice, style))
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
    """
    all_tts_data = get_tts_learning_data()
    all_voices_list = [
        "Vindemiatrix", "Aoede", "Callirrhoe", "Gacrux", "Sulafat", "Leda",
        "Kore", "Enceladus", "Erinome", "Despina", "Alnilam", "Laomedeia",
        "Achernar", "Pulcherrima", "Zephyr", "Puck", "Charon", "Fenrir",
        "Orus", "Iapetus", "Umbriel", "Algieba", "Rasalgethi", "Schedar",
        "Sadachbia", "Sadaltager", "Achird", "Zubenelgenubi", "Algenib", "Autonoe"
    ]
    all_styles = [
        "Speak with intrigue and mystery. Drop hints naturally through sentences, not mysterious fragments.",
        "Speak confidently and authoritatively. Explain causes and effects clearly, like an expert.",
        "Speak with urgency and forward momentum. Keep the story moving, build to the climax naturally.",
        "Speak thoughtfully and reflectively. Like sharing wisdom with a friend, measured and genuine.",
        "Speak naturally like telling a story to a friend. Conversational, engaging, keep the flow moving.",
        "Speak like a professional news reporter. Clear, factual, objective. Present information in order.",
        "Speak like a documentary host. Informed, warm, educational. Add context naturally.",
        "Speak with investigative intensity. Build tension through the story, pause for effect naturally.",
        "Speak as if you ARE the character. Personal, emotional, raw. First person, genuine.",
        "Speak like sharing an incredible story with a friend. Conversational, engaging, hook them early.",
    ]

    tts_map = {}
    for r in all_tts_data:
        key = (r['voice'], r['style'])
        tts_map[key] = r.get('avg_performance_score', 0)

    max_score = max((v for v in tts_map.values()), default=1)
    if max_score == 0:
        max_score = 1

    weighted = []
    for voice in all_voices_list:
        for style in all_styles:
            key = (voice, style)
            raw = tts_map.get(key, 0)
            weight = max(0.1, raw / max_score) if raw > 0 else 0.1
            weighted.append({'voice': voice, 'style': style, 'weight': weight})

    weighted.sort(key=lambda x: x['weight'], reverse=True)
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
            old_var = old_ssd / old_count if old_count > 1 else 0
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


init_db()