import os

import instaloader
from pywebio.output import put_text

from downloaders.abstracts import VideoDownloader


class InstagramDownloader(VideoDownloader):
    def download(self, video_link):
        put_text("Fazendo o download do vídeo do Instagram...").style("color: red; font-size: 20px")
        insta = instaloader.Instaloader(download_videos=True, download_video_thumbnails=False)
        shortcode = video_link.split("/")[-2]
        post = instaloader.Post.from_shortcode(insta.context, shortcode)
        insta.download_post(post, self._path)
        file_name = f"{post.owner_username}_{post.date_utc}.mp4"
        put_text(f"Vídeo baixado com sucesso como: {file_name}").style("color: blue; font-size: 20px")
        os.startfile(self._path)
