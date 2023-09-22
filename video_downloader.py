import os
from abc import abstractmethod, ABCMeta
from urllib.parse import urlparse

import instaloader
from pytube import YouTube
from pywebio.input import input
from pywebio.output import put_text, put_html
from pywebio.session import set_env


class VideoDownloader(metaclass=ABCMeta):
    """
    Classe abstrata para baixar vídeos.
    """

    def __init__(self, path):
        self._path = os.path.normpath(path)

    @abstractmethod
    def download(self, video_link):
        pass


class InstagramDownloader(VideoDownloader):

    def download(self, video_link):
        put_text("Fazendo o download do vídeo do Instagram...").style("color: red; font-size: 20px")
        insta = instaloader.Instaloader(download_videos=True, download_video_thumbnails=False)
        shortcode = video_link.split("/")[-2]
        post = instaloader.Post.from_shortcode(insta.context, shortcode)
        insta.download_post(post, self._path)
        file_name = f"{post.owner_username}_{post.date_utc}.mp4"  # exemplo de nome do arquivo
        put_text(f"Vídeo baixado com sucesso como: {file_name}").style("color: blue; font-size: 20px")
        os.startfile(self._path)


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
        file_name = f"{yt.title}.mp4"  # exemplo de nome do arquivo
        put_text(f"Vídeo baixado com sucesso como: {file_name}").style("color: blue; font-size: 20px")
        os.startfile(self._path)


class VideoClient:
    """
    Classe cliente para interagir com o usuário e baixar o vídeo.
    """

    def __init__(self, path):
        set_env(title="Video Downloader")
        self.path = path
        self.downloader = None  # Inicialize como None; será definido mais tarde

    def input_video_link(self):
        video_link = input("Informe o link do vídeo: ")
        if self.is_valid_link(video_link):
            return video_link
        put_text("Link do vídeo inválido. Tente novamente.")

    @staticmethod
    def is_valid_link(video_link):
        return video_link.split("//")[0] == "https:"

    def select_downloader(self, video_link):
        parsed_url = urlparse(video_link)
        domain = parsed_url.netloc

        if "youtube.com" in domain:
            self.downloader = PytubeDownloader(self.path)
        elif "instagram.com" in domain:
            self.downloader = InstagramDownloader(self.path)
        else:
            put_text("Domínio não suportado. Tente novamente.")

    def download_video(self):
        while True:
            video_link = self.input_video_link()
            if video_link:
                self.select_downloader(video_link)
                if self.downloader:  # Certifique-se de que um downloader foi selecionado
                    self.downloader.download(video_link)

    def add_css_styles(self):
        # Adicionando estilos personalizados
        styles = """
        <style>
            body {
                font-family: Arial, sans-serif;
                padding: 20px;
                background-color: #f7f7f7;
            }
        </style>
        """
        put_html(styles)
        return self


if __name__ == '__main__':
    try:
        VideoClient(path="downloads").add_css_styles().download_video()
    except:
        pass
