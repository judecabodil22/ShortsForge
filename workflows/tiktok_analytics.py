"""
TikTok Analytics Module
Parses TikTok CSV exports and stores metrics for cross-platform comparison.
"""
import csv
import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from difflib import SequenceMatcher

WORKSPACE = os.path.expanduser("~/Cogitator")
DB_DIR = os.path.join(WORKSPACE, ".cogitator")
DB_PATH = os.path.join(DB_DIR, "performance.db")
TIKTOK_CSV_DIR = os.path.join(WORKSPACE, "Tiktok Analytics")

# Game keyword mapping for title-based extraction
GAME_KEYWORDS = {
    'atomic_heart': [
        'atomic heart', 'petrov', 'sechenov', 'facility 3826',
        'granny zina', 'soviet', 'robot uprising', 'major seeks',
        'sechenovs', 'dr. sechenov'
    ],
    'banishers': [
        'banishers', 'ghosts of new eden', 'charles',
        'banishersghostsofneweden'
    ],
    'genshin_impact': [
        'genshin', 'neuvillette', 'furina', 'fontaine', 'focalors',
        'genshinimpact'
    ],
}


def _get_db():
    """Get database connection."""
    import sqlite3
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_tiktok_tables():
    """Create TikTok-specific tables if they don't exist."""
    conn = _get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tiktok_videos (
            id TEXT PRIMARY KEY,
            tiktok_video_id TEXT UNIQUE NOT NULL,
            tiktok_url TEXT,
            title TEXT,
            game TEXT,
            post_date TEXT,
            total_views INTEGER DEFAULT 0,
            total_likes INTEGER DEFAULT 0,
            total_comments INTEGER DEFAULT 0,
            total_shares INTEGER DEFAULT 0,
            matched_clip_id TEXT,
            matched_youtube_id TEXT,
            match_confidence REAL DEFAULT 0,
            imported_at TEXT NOT NULL,
            raw_data TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tiktok_daily_metrics (
            id TEXT PRIMARY KEY,
            metric_date TEXT NOT NULL UNIQUE,
            video_views INTEGER DEFAULT 0,
            profile_views INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0,
            comments INTEGER DEFAULT 0,
            shares INTEGER DEFAULT 0,
            total_viewers INTEGER DEFAULT 0,
            new_viewers INTEGER DEFAULT 0,
            returning_viewers INTEGER DEFAULT 0,
            followers INTEGER DEFAULT 0,
            follower_delta INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


# ─── CSV Parsers ─────────────────────────────────────────────────────────────

def _extract_game_from_title(title: str) -> str:
    """Extract game name from hashtags/title text."""
    title_lower = title.lower()
    for game, keywords in GAME_KEYWORDS.items():
        if any(kw in title_lower for kw in keywords):
            return game
    return 'unknown'


def _infer_post_year(video_id: str) -> int:
    """Infer year from TikTok video ID (snowflake-like timestamp)."""
    try:
        ts = (int(video_id) >> 32) / 1024
        return datetime.fromtimestamp(ts).year
    except Exception:
        return 2025


def _parse_tiktok_date(month_day: str, year: int) -> str:
    """Parse 'March 14' + year into '2025-03-14'."""
    try:
        dt = datetime.strptime(f"{month_day} {year}", "%B %d %Y")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return f"{year}-01-01"


def parse_content_csv(path: str) -> List[Dict]:
    """Parse Content.csv into list of video dicts."""
    videos = []
    with open(path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        # Clean header names (remove BOM, quotes)
        if reader.fieldnames:
            reader.fieldnames = [h.strip().strip('"').strip('\ufeff') for h in reader.fieldnames]
        for row in reader:
            # Extract video ID from URL
            url = row.get('Video link', '')
            video_id_match = re.search(r'/video/(\d+)', url)
            video_id = video_id_match.group(1) if video_id_match else ''

            # Infer year from video ID
            year = _infer_post_year(video_id) if video_id else 2025

            # Parse post date
            post_time = row.get('Post time', '')
            post_date = _parse_tiktok_date(post_time, year)

            # Extract game from title
            title = row.get('Video title', '')
            game = _extract_game_from_title(title)

            # Clean numeric fields
            def safe_int(val):
                try:
                    v = int(val)
                    return max(0, v)  # No negatives
                except (ValueError, TypeError):
                    return 0

            videos.append({
                'id': str(uuid.uuid4()),
                'tiktok_video_id': video_id,
                'tiktok_url': url,
                'title': title.strip(),
                'game': game,
                'post_date': post_date,
                'total_views': safe_int(row.get('Total views', 0)),
                'total_likes': safe_int(row.get('Total likes', 0)),
                'total_comments': safe_int(row.get('Total comments', 0)),
                'total_shares': safe_int(row.get('Total shares', 0)),
                'imported_at': datetime.now(timezone.utc).isoformat(),
                'raw_data': json.dumps(dict(row)),
            })
    return videos


def parse_overview_csv(path: str) -> List[Dict]:
    """Parse Overview.csv into daily metrics."""
    metrics = []
    with open(path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        # Clean header names (remove BOM, quotes)
        if reader.fieldnames:
            reader.fieldnames = [h.strip().strip('"').strip('\ufeff') for h in reader.fieldnames]
        for row in reader:
            date_str = row.get('Date', '')

            # Parse date (assume 2024-2025 range based on month order)
            parsed_date = _parse_overview_date(date_str)
            if not parsed_date:
                continue

            def safe_int(val):
                try:
                    v = int(val)
                    return max(0, v)  # Fix -1 comments
                except (ValueError, TypeError):
                    return 0

            metrics.append({
                'id': str(uuid.uuid4()),
                'metric_date': parsed_date,
                'video_views': safe_int(row.get('Video Views', 0)),
                'profile_views': safe_int(row.get('Profile Views', 0)),
                'likes': safe_int(row.get('Likes', 0)),
                'comments': safe_int(row.get('Comments', 0)),
                'shares': safe_int(row.get('Shares', 0)),
            })
    return metrics


def _parse_overview_date(date_str: str) -> Optional[str]:
    """Parse 'August 2' into 'YYYY-MM-DD' format."""
    # Overview.csv spans Aug 2024 - Aug 2025
    # Months in order: Aug, Sep, Oct, Nov, Dec, Jan, Feb, Mar, Apr, May, Jun, Jul, Aug
    month_order = [
        ('August', 2024), ('September', 2024), ('October', 2024),
        ('November', 2024), ('December', 2024), ('January', 2025),
        ('February', 2025), ('March', 2025), ('April', 2025),
        ('May', 2025), ('June', 2025), ('July', 2025), ('August', 2025),
    ]

    parts = date_str.strip().split()
    if len(parts) != 2:
        return None

    month_name, day = parts[0], parts[1]

    # Find the year based on position in the sequence
    # Count occurrences of each month to determine which year
    for i, (m, y) in enumerate(month_order):
        if m == month_name:
            # Check if we've seen this month before (for Jan-Aug which repeat)
            # Simple heuristic: first occurrence = first year, second = second year
            if i < 5:  # Aug-Dec = 2024
                year = 2024
            else:  # Jan-Aug = 2025
                year = 2025
            break
    else:
        return None

    try:
        dt = datetime.strptime(f"{month_name} {day} {year}", "%B %d %Y")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return None


def parse_viewers_csv(path: str) -> Dict[str, Dict]:
    """Parse Viewers.csv into date-indexed dict."""
    viewers = {}
    with open(path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        # Clean header names (remove BOM, quotes)
        if reader.fieldnames:
            reader.fieldnames = [h.strip().strip('"').strip('\ufeff') for h in reader.fieldnames]
        for row in reader:
            date_str = row.get('Date', '')
            parsed_date = _parse_overview_date(date_str)
            if not parsed_date:
                continue

            def safe_int(val):
                try:
                    if val == 'undefined' or val is None:
                        return 0
                    return max(0, int(val))
                except (ValueError, TypeError):
                    return 0

            viewers[parsed_date] = {
                'total_viewers': safe_int(row.get('Total Viewers', 0)),
                'new_viewers': safe_int(row.get('New Viewers', 0)),
                'returning_viewers': safe_int(row.get('Returning Viewers', 0)),
            }
    return viewers


def parse_followers_csv(path: str) -> Dict[str, Dict]:
    """Parse FollowerHistory.csv into date-indexed dict."""
    followers = {}
    with open(path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        # Clean header names (remove BOM, quotes)
        if reader.fieldnames:
            reader.fieldnames = [h.strip().strip('"').strip('\ufeff') for h in reader.fieldnames]
        for row in reader:
            date_str = row.get('Date', '')
            parsed_date = _parse_overview_date(date_str)
            if not parsed_date:
                continue

            def safe_int(val):
                try:
                    return int(val)
                except (ValueError, TypeError):
                    return 0

            followers[parsed_date] = {
                'followers': safe_int(row.get('Followers', 0)),
                'follower_delta': safe_int(row.get('Difference in followers from previous day', 0)),
            }
    return followers


# ─── Database Operations ─────────────────────────────────────────────────────

def import_tiktok_data(csv_dir: str = None) -> Dict[str, Any]:
    """Import all TikTok CSV files into database."""
    csv_dir = csv_dir or TIKTOK_CSV_DIR
    init_tiktok_tables()

    results = {
        'videos_imported': 0,
        'daily_rows_imported': 0,
        'errors': [],
    }

    conn = _get_db()
    cursor = conn.cursor()

    # 1. Import Content.csv → tiktok_videos
    content_path = os.path.join(csv_dir, 'Content.csv')
    if os.path.exists(content_path):
        try:
            videos = parse_content_csv(content_path)
            for v in videos:
                cursor.execute("""
                    INSERT OR REPLACE INTO tiktok_videos
                    (id, tiktok_video_id, tiktok_url, title, game, post_date,
                     total_views, total_likes, total_comments, total_shares,
                     imported_at, raw_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    v['id'], v['tiktok_video_id'], v['tiktok_url'],
                    v['title'], v['game'], v['post_date'],
                    v['total_views'], v['total_likes'], v['total_comments'],
                    v['total_shares'], v['imported_at'], v['raw_data'],
                ))
            results['videos_imported'] = len(videos)
        except Exception as e:
            results['errors'].append(f"Content.csv: {e}")

    # 2. Import Overview.csv + Viewers.csv + FollowerHistory.csv → tiktok_daily_metrics
    overview_path = os.path.join(csv_dir, 'Overview.csv')
    viewers_path = os.path.join(csv_dir, 'Viewers.csv')
    followers_path = os.path.join(csv_dir, 'FollowerHistory.csv')

    overview_data = {}
    viewers_data = {}
    followers_data = {}

    if os.path.exists(overview_path):
        try:
            for m in parse_overview_csv(overview_path):
                overview_data[m['metric_date']] = m
        except Exception as e:
            results['errors'].append(f"Overview.csv: {e}")

    if os.path.exists(viewers_path):
        try:
            viewers_data = parse_viewers_csv(viewers_path)
        except Exception as e:
            results['errors'].append(f"Viewers.csv: {e}")

    if os.path.exists(followers_path):
        try:
            followers_data = parse_followers_csv(followers_path)
        except Exception as e:
            results['errors'].append(f"FollowerHistory.csv: {e}")

    # Merge all daily data by date
    all_dates = set(list(overview_data.keys()) + list(viewers_data.keys()) + list(followers_data.keys()))

    for date in sorted(all_dates):
        ov = overview_data.get(date, {})
        vw = viewers_data.get(date, {})
        fl = followers_data.get(date, {})

        cursor.execute("""
            INSERT OR REPLACE INTO tiktok_daily_metrics
            (id, metric_date, video_views, profile_views, likes, comments, shares,
             total_viewers, new_viewers, returning_viewers, followers, follower_delta)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()),
            date,
            ov.get('video_views', 0),
            ov.get('profile_views', 0),
            ov.get('likes', 0),
            ov.get('comments', 0),
            ov.get('shares', 0),
            vw.get('total_viewers', 0),
            vw.get('new_viewers', 0),
            vw.get('returning_viewers', 0),
            fl.get('followers', 0),
            fl.get('follower_delta', 0),
        ))
        results['daily_rows_imported'] += 1

    conn.commit()
    conn.close()

    return results


# ─── Query Functions ─────────────────────────────────────────────────────────

def get_tiktok_summary() -> Dict[str, Any]:
    """Get aggregated TikTok stats."""
    conn = _get_db()
    cursor = conn.cursor()

    # Video counts
    cursor.execute("SELECT COUNT(*) as total FROM tiktok_videos")
    total_videos = cursor.fetchone()['total']

    cursor.execute("SELECT SUM(total_views) as total FROM tiktok_videos")
    total_views = cursor.fetchone()['total'] or 0

    cursor.execute("SELECT AVG(total_views) as avg FROM tiktok_videos")
    avg_views = cursor.fetchone()['avg'] or 0

    cursor.execute("SELECT SUM(total_likes) as total FROM tiktok_videos")
    total_likes = cursor.fetchone()['total'] or 0

    # Current followers
    cursor.execute("SELECT followers FROM tiktok_daily_metrics ORDER BY metric_date DESC LIMIT 1")
    row = cursor.fetchone()
    current_followers = row['followers'] if row else 0

    # Engagement ratio
    engagement = (total_likes / total_views * 100) if total_views > 0 else 0

    # Peak day
    cursor.execute("""
        SELECT metric_date, video_views
        FROM tiktok_daily_metrics
        ORDER BY video_views DESC
        LIMIT 1
    """)
    peak = cursor.fetchone()
    peak_day = peak['metric_date'] if peak else None
    peak_views = peak['video_views'] if peak else 0

    conn.close()

    return {
        'total_videos': total_videos,
        'total_views': total_views,
        'avg_views': round(avg_views, 1),
        'total_likes': total_likes,
        'engagement_ratio': round(engagement, 2),
        'current_followers': current_followers,
        'peak_day': peak_day,
        'peak_views': peak_views,
    }


def get_tiktok_videos() -> List[Dict]:
    """Get all TikTok videos with metrics."""
    conn = _get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM tiktok_videos
        ORDER BY total_views DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_tiktok_daily_metrics(days: int = 30) -> List[Dict]:
    """Get daily trend data for charts."""
    conn = _get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM tiktok_daily_metrics
        ORDER BY metric_date DESC
        LIMIT ?
    """, (days,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in reversed(rows)]  # Chronological order


def get_tiktok_game_stats() -> Dict[str, Any]:
    """Get per-game stats for TikTok videos."""
    conn = _get_db()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT game,
               COUNT(*) as video_count,
               SUM(total_views) as total_views,
               AVG(total_views) as avg_views,
               SUM(total_likes) as total_likes
        FROM tiktok_videos
        GROUP BY game
        ORDER BY total_views DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    stats = {}
    for row in rows:
        stats[row['game']] = {
            'video_count': row['video_count'],
            'total_views': row['total_views'],
            'avg_views': round(row['avg_views'], 1),
            'total_likes': row['total_likes'],
        }
    return stats


def match_tiktok_to_clips() -> Dict[str, Any]:
    """Match TikTok videos to Cogitator clips by title similarity."""
    conn = _get_db()
    cursor = conn.cursor()

    # Get all TikTok videos
    cursor.execute("SELECT id, title, game FROM tiktok_videos")
    tiktok_videos = cursor.fetchall()

    # Get all Cogitator clips (from clips table)
    cursor.execute("SELECT id, source_file, features FROM clips")
    local_clips = cursor.fetchall()

    # Also get scripts for title matching
    cursor.execute("SELECT id, title, video_name FROM scripts WHERE title IS NOT NULL AND title != ''")
    scripts = cursor.fetchall()

    matches = []
    matched_count = 0

    for tt in tiktok_videos:
        tt_title = tt['title']
        tt_game = tt['game']
        best_score = 0
        best_match = None

        # Try matching against scripts
        for script in scripts:
            script_title = script['title'] or ''
            script_game = script['video_name'] or ''

            score = _match_score(tt_title, script_title, tt_game, script_game)
            if score > best_score:
                best_score = score
                best_match = {
                    'type': 'script',
                    'id': script['id'],
                    'title': script_title,
                    'score': score,
                }

        # Update match in database
        if best_match and best_score >= 50:
            matched_clip_id = best_match['id'] if best_match['type'] == 'clip' else None
            matched_youtube_id = best_match['id'] if best_match['type'] == 'script' else None

            cursor.execute("""
                UPDATE tiktok_videos
                SET matched_clip_id = ?, matched_youtube_id = ?, match_confidence = ?
                WHERE id = ?
            """, (matched_clip_id, matched_youtube_id, best_score, tt['id']))
            matched_count += 1

        matches.append({
            'tiktok_id': tt['id'],
            'tiktok_title': tt_title,
            'best_match': best_match,
            'confidence': best_score,
        })

    conn.commit()
    conn.close()

    return {
        'total_videos': len(tiktok_videos),
        'matched_count': matched_count,
        'matches': matches,
    }


def _match_score(tiktok_title: str, local_title: str,
                 tiktok_game: str, local_game: str) -> float:
    """Score match between TikTok video and local clip."""
    score = 0.0

    # Title similarity (0-50 points)
    norm_tt = _normalize_title(tiktok_title)
    norm_local = _normalize_title(local_title)
    title_sim = SequenceMatcher(None, norm_tt, norm_local).ratio()
    score += 50 * title_sim

    # Game match (0-30 points)
    if tiktok_game and local_game:
        if tiktok_game.lower() in local_game.lower() or local_game.lower() in tiktok_game.lower():
            score += 30

    # Substring match (0-20 points)
    if norm_tt and norm_local:
        if norm_tt in norm_local or norm_local in norm_tt:
            score += 20

    return min(100, score)


def _normalize_title(title: str) -> str:
    """Normalize title for comparison."""
    # Remove hashtags
    text = re.sub(r'#\w+', '', title)
    # Remove emojis and special chars
    text = re.sub(r'[^\w\s]', '', text)
    # Lowercase and collapse whitespace
    text = ' '.join(text.lower().split())
    return text.strip()
