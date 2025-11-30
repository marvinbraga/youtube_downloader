import os

from pytube import YouTube
from pywebio.output import put_text

from downloaders.abstracts import VideoDownloader


class PytubeDownloader(VideoDownloader):
    """
    Implementação concreta da classe VideoDownloader para baixar vídeos usando a
    biblioteca pytube.
    """

    def download(self, video_link):
        put_text("Fazendo o download do vídeo do YouTube...").style("color: red; font-size: 20px")
        yt = YouTube(video_link)
        video = yt.streams.get_highest_resolution()
        video.download(self._path)
        file_name = f"{yt.title}.mp4"
        put_text(f"Vídeo baixado com sucesso como: {file_name}").style("color: blue; font-size: 20px")
        os.startfile(self._path)
