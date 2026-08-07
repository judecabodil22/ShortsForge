"""Tests for backend API endpoints."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestSanitizeInput:
    def test_normal_input(self):
        from backend.main import sanitize_input
        result = sanitize_input("hello world")
        assert result == "hello world"

    def test_strips_double_dots(self):
        from backend.main import sanitize_input
        result = sanitize_input("path/to/../file")
        assert ".." not in result

    def test_max_length(self):
        from backend.main import sanitize_input
        result = sanitize_input("a" * 200, max_length=10)
        assert len(result) <= 10

    def test_empty_input(self):
        from backend.main import sanitize_input
        result = sanitize_input("")
        assert result == ""


class TestPipelineStatusCodes:
    def test_pipeline_error_returns_non_200(self, monkeypatch):
        """Pipeline errors should return proper HTTP status codes, not 200."""
        from fastapi.testclient import TestClient
        from backend.main import app

        # Verify the endpoint exists and returns proper status codes
        # When auth fails, it should return 401/403, not 200 with error body
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/api/pipeline/run",
            json={},
        )
        # Without API key, should get 401/403 (Unauthorized/Forbidden), not 200
        assert response.status_code in (401, 403)
        assert response.status_code != 200


class TestLogsEndpoint:
    def test_reads_from_correct_path(self, monkeypatch, tmp_path):
        """Logs endpoint should read from ~/.cogitator/pipeline.log."""
        from backend.main import PIPELINE_LOG

        # The endpoint should use PIPELINE_LOG, not WORKSPACE/pipeline.log
        assert "cogitator" in PIPELINE_LOG or ".cogitator" in PIPELINE_LOG
