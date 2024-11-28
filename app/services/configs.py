from pathlib import Path
from typing import Dict, Union

from fastapi.security import HTTPBearer

ROOT_DIR = Path(__file__).parent.parent.parent
VIDEO_DIR = ROOT_DIR / "downloads"
JSON_CONFIG_PATH = ROOT_DIR / "data" / "videos.json"
VIDEO_DIR.mkdir(exist_ok=True)
video_mapping: Dict[str, Union[Path, str]] = {}
security = HTTPBearer()
