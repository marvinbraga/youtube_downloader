import os
from abc import abstractmethod, ABCMeta

from pytube import YouTube
from pywebio.input import input
from pywebio.output import put_text


class VideoDownloader(metaclass=ABCMeta):
    """
    Classe abstrata para baixar vídeos.
    """

    def __init__(self, path):
        self._path = os.path.normpath(path)

    @abstractmethod
    def download(self, video_link):
        pass


class PytubeDownloader(VideoDownloader):
    """
    Implementação concreta da classe VideoDownloader para baixar vídeos usando a
    biblioteca pytube.
    """

    def download(self, video_link):
        put_text("Fazendo o download do vídeo".title()).style("color: red; font-size: 50px")
        url = YouTube(video_link)
        video = url.streams.get_highest_resolution()
        video.download(self._path)
        put_text("Vídeo baixado com sucesso...".title()).style("color: blue; font-size: 50px")
        os.startfile(self._path)


class VideoClient:
    """
    Classe cliente para interagir com o usuário e baixar o vídeo.
    """

    def __init__(self, downloader):
        self.downloader = downloader

    def input_video_link(self):
        video_link = input("Informe o link do vídeo: ")
        if self.is_valid_link(video_link):
            return video_link
        put_text("Link do vídeo inválido. Tente novamente.")

    @staticmethod
    def is_valid_link(video_link):
        return video_link.split("//")[0] == "https:"

    def download_video(self):
        while True:
            video_link = self.input_video_link()
            self.downloader.download(video_link)


if __name__ == '__main__':
    VideoClient(PytubeDownloader(path="downloads")).download_video()
