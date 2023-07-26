import os

from pytube import YouTube
from pywebio.input import input
from pywebio.output import put_text


def video_download():
    while True:
        video_link = input("Informe o link do vídeo: ")
        if video_link.split("//")[0] == "https:":
            put_text("Fazendo o download do video".title()).style("color: red; font-size: 50px")
            url = YouTube(video_link)
            video = url.streams.get_highest_resolution()
            path = (os.path.normpath("~/Downloads"))
            video.download(path)
            put_text("Vídeo baixado com sucesso...".title()).style("color: blue; font-size: 50px")
            os.startfile(path)


if __name__ == '__main__':
    video_download()
