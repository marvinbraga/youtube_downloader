import os
from datetime import datetime
from urllib.parse import urlparse

from pywebio.input import input
from pywebio.output import put_html, put_text
from pywebio.session import set_env

from downloaders.instagram import InstagramDownloader
from downloaders.youtube_ytdlp import YTDLPDownloader


class VideoClient:
    """
    Classe cliente para interagir com o usuário e baixar o vídeo.
    """

    def __init__(self, path):
        set_env(title="Video Downloader")
        self.path = os.path.join(path, datetime.now().strftime('%Y-%m-%d'))
        self.downloader = None

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

        if "youtube.com" in domain or "youtu.be" in domain:
            self.downloader = YTDLPDownloader(self.path)
        elif "instagram.com" in domain:
            self.downloader = InstagramDownloader(self.path)
        else:
            put_text("Domínio não suportado. Tente novamente.")

    def download_video(self):
        while True:
            video_link = self.input_video_link()
            if video_link:
                self.select_downloader(video_link)
                if self.downloader:
                    try:
                        self.downloader.download(video_link)
                    except Exception as e:
                        put_text(f"Problema: {e}").style("color: red; font-size: 20px")

    def add_css_styles(self):
        styles = """
        <style>
            body {
                font-family: Arial, sans-serif;
                padding: 20px;
                background-color: #f7f7f7;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin: 15px 0;
            }
            th, td {
                padding: 8px;
                text-align: left;
                border: 1px solid #ddd;
            }
            th {
                background-color: #4CAF50;
                color: white;
            }
            tr:nth-child(even) {
                background-color: #f2f2f2;
            }
            .progress-bar {
                margin: 20px 0;
            }
        </style>
        """
        put_html(styles)
        return self


if __name__ == '__main__':
    try:
        VideoClient(path="downloads").add_css_styles().download_video()
    except Exception as e:
        print(f"Exceção: {e}")
