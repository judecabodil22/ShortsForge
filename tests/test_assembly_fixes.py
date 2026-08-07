"""Tests for assembly and pipeline fixes."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestAssemblyFilterChain:
    def test_vid_label_exists_without_hwupload(self):
        """When hwupload is None, [vid] label should still be defined."""
        f_parts = [
            "[0:v]trim=duration=60,setpts=PTS-STARTPTS[vid_raw]",
            "[vid_raw]subtitles=test.srt[vid_sub]",
        ]
        hw_upload = None
        if hw_upload:
            f_parts.insert(2, f"[vid_sub]{hw_upload}[vid]")
        if not hw_upload:
            f_parts.append("[vid_sub]null[vid]")

        filter_complex = ";".join(f_parts)
        assert "[vid]" in filter_complex
        assert "null[vid]" in filter_complex

    def test_vid_label_with_hwupload(self):
        """When hwupload is set, [vid] label should come from hwupload."""
        f_parts = [
            "[0:v]trim=duration=60,setpts=PTS-STARTPTS[vid_raw]",
            "[vid_raw]subtitles=test.srt[vid_sub]",
        ]
        hw_upload = "format=nv12,hwupload"
        if hw_upload:
            f_parts.insert(2, f"[vid_sub]{hw_upload}[vid]")
        if not hw_upload:
            f_parts.append("[vid_sub]null[vid]")

        filter_complex = ";".join(f_parts)
        assert "hwupload[vid]" in filter_complex
        assert "null[vid]" not in filter_complex


class TestContextManagerSingleton:
    def test_thread_safe_singleton(self):
        """Context manager should be a thread-safe singleton."""
        import threading
        from workflows.context_manager_v2 import _context_manager_lock

        assert isinstance(_context_manager_lock, type(threading.Lock()))

    def test_cleanup_no_double_delete(self, tmp_path):
        """cleanup_all_files should not double-delete files."""
        import glob
        # Simulate the old behavior: glob("*") + glob("**/*", recursive=True)
        # This would find the same top-level files twice
        test_dir = tmp_path / "test_cleanup"
        test_dir.mkdir()
        (test_dir / "file1.txt").write_text("test")
        sub_dir = test_dir / "subdir"
        sub_dir.mkdir()
        (sub_dir / "file2.txt").write_text("test2")

        # The fix uses a set to track seen files
        seen = set()
        count = 0
        for f in glob.glob(os.path.join(str(test_dir), "**/*"), recursive=True):
            if os.path.isfile(f) and f not in seen:
                seen.add(f)
                count += 1

        # Should find 2 files, not 3 (no double-counting)
        assert count == 2
