from pathlib import Path
from typing import Dict, Union

from fastapi.security import HTTPBearer

VIDEO_DIR = Path(__file__).parent.parent.parent / "downloads"
JSON_CONFIG_PATH = Path(__file__).parent.parent.parent / "data" / "videos.json"
VIDEO_DIR.mkdir(exist_ok=True)
video_mapping: Dict[str, Union[Path, str]] = {}
security = HTTPBearer()
