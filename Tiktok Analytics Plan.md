# TikTok Analytics Integration Plan

## Executive Summary

Integrate TikTok analytics (from exported CSV files) into Cogitator's existing performance tracking system, enabling cross-platform comparison between YouTube Shorts and TikTok performance for the same content.

---

## 1. CSV Files Analysis

### 1.1 File Inventory

| File | Rows | Key Columns | Status |
|------|------|-------------|--------|
| `Content.csv` | 16 (1 header + 15 videos) | Time, Video title, Video link, Post time, Total likes, Total comments, Total shares, Total views | **Primary** — per-video metrics |
| `Overview.csv` | 366 (1 header + 365 days) | Date, Video Views, Profile Views, Likes, Comments, Shares | Daily aggregate trends |
| `Viewers.csv` | 366 (1 header + 365 days) | Date, Total Viewers, New Viewers, Returning Viewers | Audience retention |
| `FollowerHistory.csv` | 366 (1 header + 365 days) | Date, Followers, Difference | Growth tracking |
| `FollowerActivity.csv` | 1 (header only) | Date, Hour, Active followers | **Empty — skip** |
| `FollowerGender.csv` | 1 (header only) | Gender, Distribution | **Empty — skip** |
| `FollowerTopTerritories.csv` | 1 (header only) | Top territories, Distribution | **Empty — skip** |

### 1.2 Content.csv — Video Details

**15 videos** spanning Dec 2024 – Jul 2025:

| Game | Count | Videos |
|------|-------|--------|
| **Atomic Heart** | **10** | Petrov's lost sanity, Facility 3826, Sechenov's plan, Soviet Utopia, Granny Zina, Robot Uprising, Sechenovs True Intentions, Major Seeks Petrov, equality/chaos, good vs evil |
| **Banishers: Ghosts of New Eden** | **4** | Who will you choose?, demise of Charles, game feels different, help did not arrive |
| **Genshin Impact** | **1** | Iudex Neuvillette/Furina |

**Metrics range**: 230–1,296 views | 0–65 likes | 0–2 comments | 0–3 shares

**⚠️ Data quality note**: One row in Overview.csv has negative comments (`-1` on June 18) — needs cleaning on import.

**Column details**:
- `Time` = Export date (always "August 2") — NOT post date
- `Post time` = Actual post date (month+day only, no year) — **year must be inferred from video ID or URL**
- `Video title` = Title + embedded hashtags (no separate hashtag column)
- No `duration` column — duration must come from Cogitator clip data
- No separate `hashtag` column — hashtags are in the title string

### 1.3 Overview.csv — Daily Trends

- **Date range**: Aug 2024 – Aug 2025 (365 days)
- **Peak day**: March 14, 2025 — 1,889 video views, 41 likes, 1 comment
- **Baseline**: Most days 0–5 views; spikes correlate with Content.csv post dates
- **Data issue**: June 18 has `-1` comments — must handle as 0 on import

### 1.4 Viewers.csv — Audience

- **New vs Returning**: Early days all new; later spikes show returning viewers
- **Peak**: March 15 — 1,656 total viewers (1,643 new, 13 returning)
- **Data issue**: August 1 row has `"undefined"` Total Viewers — must handle as 0

### 1.5 FollowerHistory.csv — Growth

- **Range**: 12–15 followers (Aug 2024 – Aug 2025)
- **Growth events**: Aug 19 (+1), Nov 3 (+1), Dec 27 (+1), Mar 28 (+1), Apr 21 (+1), Jul 8 (+1), Jul 11 (+1)

---

## 2. Data Model Design

### 2.1 Database Schema

```sql
-- TikTok videos (separate table, different ID system)
CREATE TABLE IF NOT EXISTS tiktok_videos (
    id TEXT PRIMARY KEY,
    tiktok_video_id TEXT UNIQUE NOT NULL,  -- from URL: 7616892584375487764
    tiktok_url TEXT,
    title TEXT,
    game TEXT,  -- extracted from hashtags/title
    post_date TEXT,  -- YYYY-MM-DD (year inferred)
    total_views INTEGER DEFAULT 0,
    total_likes INTEGER DEFAULT 0,
    total_comments INTEGER DEFAULT 0,
    total_shares INTEGER DEFAULT 0,
    matched_clip_id TEXT,  -- FK to clips.id (if matched)
    matched_youtube_id TEXT,  -- FK to videos.id (if matched)
    match_confidence REAL DEFAULT 0,
    imported_at TEXT NOT NULL,
    raw_data TEXT  -- JSON blob
);

-- Daily aggregate metrics (platform-agnostic)
CREATE TABLE IF NOT EXISTS daily_metrics (
    id TEXT PRIMARY KEY,
    platform TEXT NOT NULL,  -- 'youtube' or 'tiktok'
    metric_date TEXT NOT NULL,  -- YYYY-MM-DD
    video_views INTEGER DEFAULT 0,
    profile_views INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    total_viewers INTEGER DEFAULT 0,  -- TikTok only
    new_viewers INTEGER DEFAULT 0,  -- TikTok only
    returning_viewers INTEGER DEFAULT 0,  -- TikTok only
    followers INTEGER DEFAULT 0,  -- TikTok only
    follower_delta INTEGER DEFAULT 0,  -- TikTok only
    UNIQUE(platform, metric_date)
);

-- Video-level metrics (per platform)
CREATE TABLE IF NOT EXISTS video_metrics (
    id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL,  -- tiktok_videos.id or videos.id
    platform TEXT NOT NULL,  -- 'youtube' or 'tiktok'
    fetched_at TEXT NOT NULL,
    views INTEGER DEFAULT 0,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    engagement_ratio REAL,
    performance_score REAL,
    raw_data TEXT
);
```

### 2.2 Key Design Decisions

1. **Use `platform TEXT` not `platform_id INTEGER`** — simpler, no join needed for common queries
2. **Separate `tiktok_videos` table** — TikTok has different ID system (no youtube_id)
3. **Year inference for `post_date`** — TikTok video IDs encode timestamp; use that or fall back to Content.csv `Time` export date
4. **Match via `matched_clip_id`** — links TikTok video to Cogitator clip for cross-platform comparison
5. **Skip empty tables** — FollowerActivity, FollowerGender, FollowerTopTerritories have no data; add later if TikTok provides them

---

## 3. Backend Implementation

### 3.1 New Module: `workflows/tiktok_analytics.py`

```python
# Core functions:
def parse_tiktok_content_csv(path: str) -> List[Dict]:
    """Parse Content.csv into list of video dicts."""

def parse_tiktok_overview_csv(path: str) -> List[Dict]:
    """Parse Overview.csv into daily metrics. Handle -1 comments."""

def parse_tiktok_viewers_csv(path: str) -> List[Dict]:
    """Parse Viewers.csv. Handle 'undefined' values."""

def parse_tiktok_followers_csv(path: str) -> List[Dict]:
    """Parse FollowerHistory.csv."""

def extract_game_from_title(title: str) -> str:
    """Extract game name from hashtags/title text."""

def infer_post_year(video_id: str, export_date: str) -> int:
    """Infer year from TikTok video ID timestamp or export date."""

def import_tiktok_data(csv_dir: str) -> Dict:
    """Import all CSVs into database."""

def match_tiktok_to_clips() -> Dict:
    """Match TikTok videos to Cogitator clips by title similarity."""

def get_tiktok_summary() -> Dict:
    """Aggregated TikTok stats for API."""

def get_tiktok_videos() -> List[Dict]:
    """All TikTok videos with metrics."""

def get_tiktok_daily_metrics(days: int = 30) -> List[Dict]:
    """Daily trend data for charts."""

def get_cross_platform_comparison() -> Dict:
    """Side-by-side YouTube vs TikTok for matched videos."""
```

### 3.2 Game Extraction from Title

Since there's no separate hashtag column, extract game from title text:

```python
GAME_KEYWORDS = {
    'atomic_heart': ['atomic heart', 'petrov', 'sechenov', 'facility 3826', 
                     'granny zina', 'soviet', 'robot uprising'],
    'banishers': ['banishers', 'ghosts of new eden', 'charles'],
    'genshin_impact': ['genshin', 'neuvillette', 'furina', 'fontaine', 'focalors'],
}

def extract_game_from_title(title: str) -> str:
    title_lower = title.lower()
    for game, keywords in GAME_KEYWORDS.items():
        if any(kw in title_lower for kw in keywords):
            return game
    return 'unknown'
```

### 3.3 Year Inference for Post Date

TikTok video IDs encode Unix timestamp. Extract year:

```python
def infer_post_year(video_id: str, export_date: str) -> int:
    """TikTok video IDs are snowflake-like; high bits = timestamp."""
    # Method 1: Extract from video ID (bits 32-63 = seconds since epoch)
    try:
        ts = (int(video_id) >> 32) / 1024
        return datetime.fromtimestamp(ts).year
    except:
        pass
    # Method 2: Use export date year (August 2 = 2025)
    return 2025  # Default to export year
```

### 3.4 Data Cleaning on Import

```python
def clean_overview_row(row: Dict) -> Dict:
    """Handle known data quality issues."""
    # Fix negative comments
    if row.get('comments', 0) < 0:
        row['comments'] = 0
    return row

def clean_viewers_row(row: Dict) -> Dict:
    """Handle 'undefined' values."""
    for key in ['total_viewers', 'new_viewers', 'returning_viewers']:
        val = row.get(key, 0)
        if val == 'undefined' or val is None:
            row[key] = 0
    return row
```

### 3.5 New API Endpoints

```python
# In backend/main.py

@app.get("/api/metrics/tiktok/summary")
async def get_tiktok_summary():
    """Aggregated TikTok stats (total videos, views, engagement)"""

@app.get("/api/metrics/tiktok/videos")
async def get_tiktok_videos():
    """All TikTok videos with metrics, matched to local clips"""

@app.get("/api/metrics/tiktok/daily")
async def get_tiktok_daily(days: int = 30):
    """Daily trend data for charts"""

@app.get("/api/metrics/tiktok/comparison")
async def get_cross_platform_comparison():
    """Side-by-side YouTube vs TikTok for matched videos"""

@app.post("/api/metrics/tiktok/import")
async def import_tiktok_csv(request: Request):
    """Import CSV files from Tiktok Analytics/ folder"""

@app.post("/api/metrics/tiktok/match")
async def match_tiktok_to_local(request: Request):
    """Match TikTok videos to Cogitator clips"""
```

### 3.6 Enhanced Existing Endpoints

Modify `/api/metrics/summary` to include TikTok totals:
```python
@app.get("/api/metrics/summary")
async def get_metrics_summary():
    youtube_stats = get_performance_stats()
    tiktok_stats = get_tiktok_summary()
    return {
        "youtube": youtube_stats,
        "tiktok": tiktok_stats,
        "combined": {
            "total_videos": youtube_stats['total_videos'] + tiktok_stats['total_videos'],
            "total_views": youtube_stats.get('total_views', 0) + tiktok_stats['total_views'],
        }
    }
```

---

## 4. Frontend Implementation

### 4.1 New API Functions (`frontend/src/lib/api.ts`)

```typescript
export const getTikTokSummary = () => fetchAPI('/api/metrics/tiktok/summary')
export const getTikTokVideos = () => fetchAPI('/api/metrics/tiktok/videos')
export const getTikTokDaily = (days: number = 30) => 
  fetchAPI(`/api/metrics/tiktok/daily?days=${days}`)
export const getCrossPlatformComparison = () => fetchAPI('/api/metrics/tiktok/comparison')
export const importTikTokData = () => fetchAPI('/api/metrics/tiktok/import', { method: 'POST' })
export const matchTikTokToLocal = () => fetchAPI('/api/metrics/tiktok/match', { method: 'POST' })
```

### 4.2 Metrics Page Restructure

Current `Metrics.tsx` has a single view. Restructure to 3 tabs:

**Tab 1: YouTube Shorts** — existing content (no changes)

**Tab 2: TikTok** — new content:
- StatCards: Total Videos (15), Total Views (6,033), Avg Views (402), Followers (15)
- Top Videos bar chart (by views)
- Daily trend line chart (Overview.csv: views + likes)
- Audience area chart (Viewers.csv: new vs returning)
- Follower growth line chart (FollowerHistory.csv)
- Video table with all 15 videos

**Tab 3: Comparison** — new content:
- Side-by-side cards for matched videos
- Platform performance delta indicators
- Best platform by game
- Cross-platform engagement rate comparison

### 4.3 New Page: `TikTokAnalytics.tsx`

Dedicated TikTok deep-dive page with:

```
┌─────────────────────────────────────────────────────────────┐
│ TIKTOK ANALYTICS                       [Import CSV] [Refresh]│
├─────────────────────────────────────────────────────────────┤
│ █ Total Videos  █ Total Views  █ Avg Views  █ Followers     │
│      15             6,033          402           15          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Daily Video Views (Last 30 Days)                     │  │
│  │ ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▂▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▂▁▁▁▁▁▁▁▁▁▁▁▁▁  │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌─────────────────────────────┬────────────────────────┐  │
│  │ Top Videos by Views         │ Audience (New vs Return)│  │
│  │ ████████████░░░░░░░░░░░░░░ │ ████████████░░░░░░░░░░ │  │
│  │ ██████████░░░░░░░░░░░░░░░░ │ ████████░░░░░░░░░░░░░░ │  │
│  │ ████████░░░░░░░░░░░░░░░░░░ │ ██████░░░░░░░░░░░░░░░░ │  │
│  └─────────────────────────────┴────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ All TikTok Videos                                   │  │
│  │ ┌─────────────────────────┬───────┬───────┬────────┐ │  │
│  │ │ Title                   │ Views │ Likes │ Game   │ │  │
│  │ ├─────────────────────────┼───────┼───────┼────────┤ │  │
│  │ │ Who will you choose?    │ 1,296 │ 26    │ Banish │ │  │
│  │ │ Iudex Neuvillette       │ 1,080 │ 65    │ Genshin│ │  │
│  │ │ Petrov's lost sanity    │   272 │  4    │ Atomic │ │  │
│  │ │ ... (15 total)          │       │       │        │ │  │
│  │ └─────────────────────────┴───────┴───────┴────────┘ │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 4.4 Navigation Integration

Add to `Layout.tsx` sidebar:
```tsx
<NavItem icon={BarChart2} href="/metrics" label="Metrics" />
<NavItem icon={Video} href="/tiktok" label="TikTok" />  // NEW
<NavItem icon={Brain} href="/learning" label="Learning" />
```

### 4.5 Recharts Components

```typescript
import {
  LineChart, Line,           // Daily trends
  AreaChart, Area,           // New vs returning viewers
  BarChart, Bar,             // Top videos
  ResponsiveContainer,       // All charts
  XAxis, YAxis, CartesianGrid, Tooltip, Legend
} from 'recharts'
```

### 4.6 Video Table Columns (TikTok Tab)

| Column | Source | Notes |
|--------|--------|-------|
| Title | Content.csv `Video title` | Truncate at 40 chars |
| Game | Extracted from title | Atomic Heart / Banishers / Genshin |
| Views | Content.csv `Total views` | Sortable |
| Likes | Content.csv `Total likes` | Sortable |
| Comments | Content.csv `Total comments` | Sortable |
| Shares | Content.csv `Total shares` | Sortable |
| Post Date | Content.csv `Post time` + inferred year | Formatted |
| Matched | tiktok_videos `matched_clip_id` | Checkmark if matched |

### 4.7 Daily Trend Chart Data

```typescript
// Source: Overview.csv (last 30 days)
const trendData = overviewMetrics.slice(-30).map(row => ({
  date: row.date,
  views: row.video_views,
  likes: row.likes,
  profileViews: row.profile_views,
}))
```

### 4.8 Audience Chart Data

```typescript
// Source: Viewers.csv (last 30 days)
const audienceData = viewersMetrics.slice(-30).map(row => ({
  date: row.date,
  new: row.new_viewers,
  returning: row.returning_viewers,
}))
```

---

## 5. Implementation Steps

### Phase 1: Backend Foundation (Day 1-2)
1. [ ] Create `workflows/tiktok_analytics.py` with CSV parsing functions
2. [ ] Implement `extract_game_from_title()` with keyword matching
3. [ ] Implement `infer_post_year()` from video ID
4. [ ] Implement data cleaning (handle -1 comments, 'undefined' values)
5. [ ] Add database migrations for `tiktok_videos`, `daily_metrics`, `video_metrics`
6. [ ] Implement `import_tiktok_data()` to import all 4 CSV files
7. [ ] Test import: verify 15 videos, 365 daily rows imported correctly

### Phase 2: API Endpoints (Day 2-3)
8. [ ] Add `/api/metrics/tiktok/summary` endpoint
9. [ ] Add `/api/metrics/tiktok/videos` endpoint
10. [ ] Add `/api/metrics/tiktok/daily` endpoint
11. [ ] Add `/api/metrics/tiktok/import` endpoint
12. [ ] Add `/api/metrics/tiktok/match` endpoint
13. [ ] Modify `/api/metrics/summary` to include TikTok totals
14. [ ] Test all endpoints with curl/Postman

### Phase 3: Frontend - TikTok Page (Day 3-5)
15. [ ] Add API functions in `frontend/src/lib/api.ts`
16. [ ] Create `TikTokAnalytics.tsx` page with layout
17. [ ] Add StatCards (Total Videos, Total Views, Avg Views, Followers)
18. [ ] Build daily trend LineChart (views + likes over time)
19. [ ] Build audience AreaChart (new vs returning viewers)
20. [ ] Build top videos BarChart (sorted by views)
21. [ ] Build video table with all 15 videos
22. [ ] Add navigation link in `Layout.tsx`

### Phase 4: Frontend - Metrics Tabs (Day 5-6)
23. [ ] Add tab state to `Metrics.tsx`
24. [ ] Extract existing YouTube content into `YouTubeMetrics` component
25. [ ] Create `TikTokMetrics` component (simplified version of TikTok page)
26. [ ] Create `ComparisonMetrics` component (placeholder)
27. [ ] Wire up tab switching

### Phase 5: Cross-Platform Matching (Day 6-7)
28. [ ] Implement `match_tiktok_to_clips()` in backend
29. [ ] Add `/api/metrics/tiktok/comparison` endpoint
30. [ ] Build Comparison tab with matched video display
31. [ ] Add match confidence indicators in TikTok video table

### Phase 6: Polish (Day 7-8)
32. [ ] Add loading states for all queries
33. [ ] Add error handling for CSV import failures
34. [ ] Add CSV file validation before import
35. [ ] Test full flow: import → display → match → compare
36. [ ] Update CHANGELOG.md

---

## 6. Matching Algorithm

### 6.1 Title Normalization

```python
def normalize_title(title: str) -> str:
    """Normalize title for comparison."""
    import re
    # Remove hashtags
    text = re.sub(r'#\w+', '', title)
    # Remove emojis and special chars
    text = re.sub(r'[^\w\s]', '', text)
    # Lowercase and collapse whitespace
    text = ' '.join(text.lower().split())
    return text.strip()
```

### 6.2 Scoring Function

```python
def match_score(tiktok_title: str, local_title: str, 
                tiktok_game: str, local_game: str) -> float:
    """Score match between TikTok video and Cogitator clip."""
    from difflib import SequenceMatcher
    
    score = 0.0
    
    # Title similarity (0-50 points)
    norm_tt = normalize_title(tiktok_title)
    norm_local = normalize_title(local_title)
    title_sim = SequenceMatcher(None, norm_tt, norm_local).ratio()
    score += 50 * title_sim
    
    # Game match (0-30 points)
    if tiktok_game == local_game:
        score += 30
    elif tiktok_game in local_game or local_game in tiktok_game:
        score += 15
    
    # Substring match (0-20 points)
    if norm_tt in norm_local or norm_local in norm_tt:
        score += 20
    
    return min(100, score)
```

### 6.3 Confidence Thresholds

| Score | Action | UI |
|-------|--------|----|
| ≥ 80 | Auto-match | Green checkmark |
| 50–79 | Suggest match | Yellow warning, manual confirm |
| < 50 | No match | Red X, manual only |

---

## 7. UI Mockup: Comparison Tab

```
┌─────────────────────────────────────────────────────────────┐
│ [YouTube Shorts] [TikTok] [Comparison]                      │
├─────────────────────────────────────────────────────────────┤
│ Cross-Platform Matched Videos                                │
├─────────────────────┬──────────────┬──────────────┬─────────┤
│ Video               │ YouTube      │ TikTok       │ Winner  │
├─────────────────────┼──────────────┼──────────────┼─────────┤
│ Who will you choose │ 1,240 views  │ 1,296 views  │ TikTok  │
│ (Banishers)         │ 3.2% eng.    │ 2.0% eng.    │ YouTube │
├─────────────────────┼──────────────┼──────────────┼─────────┤
│ Neuvillette declare │ 890 views    │ 1,080 views  │ TikTok  │
│ (Genshin)           │ 4.1% eng.    │ 6.0% eng.    │ TikTok  │
├─────────────────────┼──────────────┼──────────────┼─────────┤
│ Atomic Heart Petrov │ 450 views    │ 272 views    │ YouTube │
│ (Atomic Heart)      │ 2.8% eng.    │ 1.5% eng.    │ YouTube │
└─────────────────────┴──────────────┴──────────────┴─────────┘

Best Platform by Game:
████████████████░░░░░░  Banishers: TikTok (2/4 metrics)
████████████████████  Genshin: TikTok (all metrics)
████████████░░░░░░░░░░  Atomic Heart: YouTube (7/10 metrics)
```

---

## 8. Testing Checklist

### Backend
- [ ] Import Content.csv → 15 videos in `tiktok_videos` table
- [ ] Import Overview.csv → 365 rows in `daily_metrics` (platform='tiktok')
- [ ] Import Viewers.csv → 365 rows with correct new/returning viewer counts
- [ ] Import FollowerHistory.csv → 365 rows with follower counts
- [ ] Handle `-1` comments (June 18) → stored as 0
- [ ] Handle `'undefined'` viewers (Aug 1) → stored as 0
- [ ] Game extraction: all 15 videos classified correctly
- [ ] Year inference: all post dates have correct year
- [ ] GET `/api/metrics/tiktok/summary` returns correct totals
- [ ] GET `/api/metrics/tiktok/videos` returns all 15 videos
- [ ] GET `/api/metrics/tiktok/daily?days=30` returns last 30 days

### Frontend
- [ ] TikTok page loads with StatCards showing correct values
- [ ] Daily trend chart renders 30 data points
- [ ] Audience chart renders new vs returning viewers
- [ ] Top videos bar chart shows all 15 videos sorted by views
- [ ] Video table shows all 15 videos with correct metrics
- [ ] Metrics page tabs switch correctly (YouTube/TikTok/Comparison)
- [ ] Navigation link appears in sidebar

### Integration
- [ ] No regression in existing YouTube metrics
- [ ] Import button triggers re-import from CSV folder
- [ ] Matching finds at least 5/15 videos matched to Cogitator clips

---

## 9. Data Summary for Import

### Pre-Import Validation

```python
EXPECTED_DATA = {
    'content_videos': 15,
    'overview_days': 365,
    'viewers_days': 365,
    'follower_days': 365,
    'game_distribution': {
        'atomic_heart': 10,
        'banishers': 4,
        'genshin_impact': 1,
    },
    'total_views': 6033,
    'peak_views_day': ('2025-03-14', 1889),
    'current_followers': 15,
}
```

### Import Order

1. `FollowerHistory.csv` → `daily_metrics` (followers, follower_delta)
2. `Overview.csv` → `daily_metrics` (video_views, likes, comments, shares)
3. `Viewers.csv` → `daily_metrics` (total_viewers, new_viewers, returning_viewers)
4. `Content.csv` → `tiktok_videos` (per-video metrics)

---

## Appendix: Actual Content.csv Data

```
Row | Title (truncated)                              | Views | Likes | Game
----|------------------------------------------------|-------|-------|------------
 1  | Who will you choose? #banishers                | 1,296 |    26 | Banishers
 2  | Iudex Neuvillette #genshinimpact               | 1,080 |    65 | Genshin
 3  | Petrov's lost sanity #AtomicHeart              |   272 |     4 | Atomic Heart
 4  | demise of Charles #banishers                   |   260 |     5 | Banishers
 5  | Major Seeks Petrov In Chaos                    |   250 |     0 | Atomic Heart
 6  | Facility 3826 #AtomicHeart                     |   246 |     2 | Atomic Heart
 7  | Soviet Utopia Turns Deadly                     |   242 |     4 | Atomic Heart
 8  | Dr. Sechenov's plan #AtomicHeart               |   241 |     3 | Atomic Heart
 9  | game feels different #banishers                |   241 |     5 | Banishers
10  | good vs evil #AtomicHeart                      |   240 |     3 | Atomic Heart
11  | help did not arrive #banishers                 |   240 |     2 | Banishers
12  | equality/chaos #AtomicHeart                    |   238 |     1 | Atomic Heart
13  | Granny Zina #AtomicHeart                       |   232 |     3 | Atomic Heart
14  | Robot Uprising #AtomicHeart                    |   231 |     1 | Atomic Heart
15  | Sechenovs True Intentions                      |   230 |     1 | Atomic Heart
```