import os
from abc import ABC, abstractmethod


class VideoDownloader(ABC):
    """
    Classe abstrata para baixar vídeos.
    """

    def __init__(self, path):
        self._path = os.path.normpath(path)
        if not os.path.exists(self._path):
            os.makedirs(self._path)

    @abstractmethod
    def download(self, video_link):
        pass
