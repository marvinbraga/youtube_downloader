from pathlib import Path
from typing import Dict, Union

from fastapi.security import HTTPBearer

# Diretórios base
ROOT_DIR = Path(__file__).parent.parent.parent
DATA_DIR = ROOT_DIR / "data"
DOWNLOADS_DIR = ROOT_DIR / "downloads"

# Diretórios específicos
VIDEO_DIR = DOWNLOADS_DIR / "videos"
AUDIO_DIR = DOWNLOADS_DIR / "audio"
JSON_CONFIG_PATH = DATA_DIR / "videos.json"
AUDIO_CONFIG_PATH = DATA_DIR / "audios.json"

# Garante que os diretórios existam
DATA_DIR.mkdir(exist_ok=True)
DOWNLOADS_DIR.mkdir(exist_ok=True)
VIDEO_DIR.mkdir(exist_ok=True)
AUDIO_DIR.mkdir(exist_ok=True)

# Mapeamentos
video_mapping: Dict[str, Union[Path, str]] = {}
audio_mapping: Dict[str, Union[Path, str]] = {}

# Configuração de segurança
security = HTTPBearer()
