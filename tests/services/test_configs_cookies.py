"""Unit tests for get_yt_dlp_cookies_opts in app/services/configs.py."""

import os
import tempfile
from pathlib import Path
import pytest

from app.services.configs import get_yt_dlp_cookies_opts, VALID_BROWSERS


class TestGetYtDlpCookiesOpts:
    """Tests for the cookie authentication helper."""

    def test_no_env_vars_returns_empty_dict(self, monkeypatch):
        monkeypatch.delenv("YT_COOKIES_FROM_BROWSER", raising=False)
        monkeypatch.delenv("YT_COOKIES_FILE", raising=False)
        assert get_yt_dlp_cookies_opts() == {}

    def test_browser_chrome_returns_cookiesfrombrowser(self, monkeypatch):
        monkeypatch.setenv("YT_COOKIES_FROM_BROWSER", "chrome")
        monkeypatch.delenv("YT_COOKIES_FILE", raising=False)
        result = get_yt_dlp_cookies_opts()
        assert result == {"cookiesfrombrowser": ("chrome",)}

    def test_browser_brave_returns_cookiesfrombrowser(self, monkeypatch):
        monkeypatch.setenv("YT_COOKIES_FROM_BROWSER", "brave")
        monkeypatch.delenv("YT_COOKIES_FILE", raising=False)
        result = get_yt_dlp_cookies_opts()
        assert result == {"cookiesfrombrowser": ("brave",)}

    def test_browser_name_is_normalized_to_lowercase(self, monkeypatch):
        monkeypatch.setenv("YT_COOKIES_FROM_BROWSER", "Chrome")
        monkeypatch.delenv("YT_COOKIES_FILE", raising=False)
        result = get_yt_dlp_cookies_opts()
        assert result == {"cookiesfrombrowser": ("chrome",)}

    def test_browser_name_strips_whitespace(self, monkeypatch):
        monkeypatch.setenv("YT_COOKIES_FROM_BROWSER", "  firefox  ")
        monkeypatch.delenv("YT_COOKIES_FILE", raising=False)
        result = get_yt_dlp_cookies_opts()
        assert result == {"cookiesfrombrowser": ("firefox",)}

    def test_invalid_browser_raises_value_error(self, monkeypatch):
        monkeypatch.setenv("YT_COOKIES_FROM_BROWSER", "netscape")
        monkeypatch.delenv("YT_COOKIES_FILE", raising=False)
        with pytest.raises(ValueError, match="not supported"):
            get_yt_dlp_cookies_opts()

    def test_cookies_file_returns_cookiefile(self, monkeypatch):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            monkeypatch.delenv("YT_COOKIES_FROM_BROWSER", raising=False)
            monkeypatch.setenv("YT_COOKIES_FILE", tmp_path)
            result = get_yt_dlp_cookies_opts()
            assert result == {"cookiefile": str(Path(tmp_path).resolve())}
        finally:
            os.unlink(tmp_path)

    def test_browser_takes_precedence_over_cookies_file(self, monkeypatch):
        tmp = tempfile.NamedTemporaryFile(delete=False)
        tmp_path = tmp.name
        tmp.close()
        try:
            monkeypatch.setenv("YT_COOKIES_FROM_BROWSER", "firefox")
            monkeypatch.setenv("YT_COOKIES_FILE", tmp_path)
            result = get_yt_dlp_cookies_opts()
            assert result == {"cookiesfrombrowser": ("firefox",)}
        finally:
            os.unlink(tmp_path)

    def test_cookies_file_nonexistent_raises_value_error(self, monkeypatch):
        monkeypatch.delenv("YT_COOKIES_FROM_BROWSER", raising=False)
        monkeypatch.setenv(
            "YT_COOKIES_FILE", "/nonexistent/path/that/does/not/exist.txt"
        )
        with pytest.raises(ValueError, match="does not point to a regular file"):
            get_yt_dlp_cookies_opts()

    def test_cookies_file_is_directory_raises_value_error(self, monkeypatch, tmp_path):
        monkeypatch.delenv("YT_COOKIES_FROM_BROWSER", raising=False)
        monkeypatch.setenv("YT_COOKIES_FILE", str(tmp_path))  # tmp_path is a directory
        with pytest.raises(ValueError, match="does not point to a regular file"):
            get_yt_dlp_cookies_opts()

    def test_whitespace_only_cookies_file_returns_empty_dict(self, monkeypatch):
        monkeypatch.delenv("YT_COOKIES_FROM_BROWSER", raising=False)
        monkeypatch.setenv("YT_COOKIES_FILE", "   ")
        assert get_yt_dlp_cookies_opts() == {}

    def test_empty_browser_env_var_falls_through_to_file(self, monkeypatch):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            monkeypatch.setenv("YT_COOKIES_FROM_BROWSER", "")
            monkeypatch.setenv("YT_COOKIES_FILE", tmp_path)
            result = get_yt_dlp_cookies_opts()
            assert result == {"cookiefile": str(Path(tmp_path).resolve())}
        finally:
            os.unlink(tmp_path)

    def test_valid_browsers_contains_expected_browsers(self):
        expected = {"chrome", "brave", "firefox", "edge", "opera", "safari", "vivaldi"}
        assert VALID_BROWSERS == expected
