"""Abstract base for platform-specific downloaders."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ExtractedInfo:
    """Result of a download, normalized across platforms."""

    info: Dict[str, Any]
    filename: str  # absolute or yt-dlp-prepared filename
    extra: Dict[str, Any] = field(default_factory=dict)


class Downloader(ABC):
    """Abstract Strategy for downloading media from a single platform.

    Each subclass encapsulates:
      * ID extraction from a URL (regex + yt-dlp fallback)
      * The yt-dlp option dictionary (cookies, headers, format selection)
      * Source identifier (`'youtube'`, `'instagram'`, ...)
    """

    source: str = "unknown"  # MUST be overridden by subclasses

    @abstractmethod
    def extract_id(self, url: str) -> Optional[str]:
        """Return the platform-native ID for ``url`` or ``None`` if not parseable."""

    @abstractmethod
    def get_info(self, url: str) -> Dict[str, Any]:
        """Return yt-dlp info dict for ``url`` (without downloading the media)."""

    @abstractmethod
    def build_audio_opts(self, output_dir: str, progress_hook) -> Dict[str, Any]:
        """Return yt-dlp opts for audio-only download into ``output_dir``."""

    @abstractmethod
    def build_video_opts(
        self, output_dir: str, resolution: str, progress_hook
    ) -> Dict[str, Any]:
        """Return yt-dlp opts for video download into ``output_dir``."""
