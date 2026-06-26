import pytest
import sys
import os
import json
import tempfile
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from workflows.performance_database import (
    init_db,
    store_script,
    store_clip,
    link_video,
    store_metrics,
    get_script_by_id,
    get_performance_stats,
    get_channel_baseline,
    get_all_scripts,
    backfill_script_titles,
    _extract_title_from_script,
)


class TestExtractTitleFromScript:
    def test_finds_title_line(self):
        script = "TITLE: My Amazing Video\n\nSome content here."
        assert _extract_title_from_script(script) == "My Amazing Video"

    def test_no_title_returns_none(self):
        assert _extract_title_from_script("Just some content.") is None

    def test_empty_returns_none(self):
        assert _extract_title_from_script("") is None


class TestInitDB:
    def test_creates_tables(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        def mock_get_db():
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = None
            mock_cursor.fetchall.return_value = []
            return mock_conn

        monkeypatch.setattr("workflows.performance_database.get_db", mock_get_db)
        init_db()
        assert mock_cursor.execute.call_count > 0


class TestStoreScript:
    def test_stores_and_returns_id(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None
        mock_cursor.fetchall.return_value = []

        def mock_get_db():
            mock_conn.cursor.return_value = mock_cursor
            return mock_conn

        monkeypatch.setattr("workflows.performance_database.get_db", mock_get_db)
        script_id = store_script(
            video_name="test_video",
            content_type="analysis",
            script_text="Test content",
            features={"word_count": 2},
        )
        assert script_id is not None
        assert isinstance(script_id, str)


class TestStoreClip:
    def test_stores_and_returns_id(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        def mock_get_db():
            mock_conn.cursor.return_value = mock_cursor
            return mock_conn

        monkeypatch.setattr("workflows.performance_database.get_db", mock_get_db)
        clip_id = store_clip(
            script_id="test-script-id",
            source_file="test.mp4",
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            features={"scene": "intro"},
        )
        assert clip_id is not None
        assert isinstance(clip_id, str)


class TestLinkVideo:
    def test_links_and_returns_id(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        def mock_get_db():
            mock_conn.cursor.return_value = mock_cursor
            return mock_conn

        monkeypatch.setattr("workflows.performance_database.get_db", mock_get_db)
        video_id = link_video(
            script_id="test-script-id",
            clip_id="test-clip-id",
            video_url="https://youtube.com/watch?v=test",
            youtube_id="test",
            title="Test Video",
        )
        assert video_id is not None
        assert isinstance(video_id, str)


class TestStoreMetrics:
    def test_stores_and_returns_id(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None

        def mock_get_db():
            mock_conn.cursor.return_value = mock_cursor
            return mock_conn

        monkeypatch.setattr("workflows.performance_database.get_db", mock_get_db)
        metric_id = store_metrics(
            video_id="test-video-id",
            views=1000,
            likes=100,
            comments=50,
        )
        assert metric_id is not None
        assert isinstance(metric_id, str)


class TestGetScriptById:
    def test_nonexistent_returns_none(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None

        def mock_get_db():
            mock_conn.cursor.return_value = mock_cursor
            return mock_conn

        monkeypatch.setattr("workflows.performance_database.get_db", mock_get_db)
        result = get_script_by_id("nonexistent-id")
        assert result is None


class TestGetPerformanceStats:
    def test_returns_dict_with_keys(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        def mock_fetchone():
            return type("Row", (), {"__getitem__": lambda self, k: 0 if k != "sample_count" else 0})()

        mock_cursor.fetchone.side_effect = [mock_fetchone(), mock_fetchone(), mock_fetchone()]

        def mock_get_db():
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchall.return_value = []
            return mock_conn

        monkeypatch.setattr("workflows.performance_database.get_db", mock_get_db)
        stats = get_performance_stats()
        assert "total_videos" in stats
        assert "total_scripts" in stats
        assert "baseline" in stats


class TestGetChannelBaseline:
    def test_returns_dict(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_row = type("Row", (), {"__getitem__": lambda self, k: 0})()

        def mock_get_db():
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchone.return_value = mock_row
            return mock_conn

        monkeypatch.setattr("workflows.performance_database.get_db", mock_get_db)
        baseline = get_channel_baseline()
        assert "avg_views" in baseline
        assert "avg_engagement" in baseline


class TestGetAllScripts:
    def test_returns_list(self, monkeypatch):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        def mock_get_db():
            mock_conn.cursor.return_value = mock_cursor
            mock_cursor.fetchall.return_value = []
            return mock_conn

        monkeypatch.setattr("workflows.performance_database.get_db", mock_get_db)
        scripts = get_all_scripts()
        assert isinstance(scripts, list)


class TestBackfillScriptTitles:
    def test_nonexistent_dir_returns_error(self, monkeypatch):
        nonexistent = "/nonexistent_cogitator_test_dir_xyz"
        monkeypatch.setattr(
            "workflows.performance_database.os.path.expanduser",
            lambda p: nonexistent,
        )
        result = backfill_script_titles()
        assert "errors" in result
