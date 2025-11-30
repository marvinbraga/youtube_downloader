import os

import yt_dlp
from pywebio.output import put_text, put_processbar, set_processbar, use_scope, clear

from downloaders.abstracts import VideoDownloader


class YTDLPDownloader(VideoDownloader):
    def __init__(self, path):
        super().__init__(path)
        self.ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'progress_hooks': [self.progress_hook],
            'postprocessor_hooks': [self.postprocessor_hook],
            'outtmpl': os.path.join(self._path, '%(title)s.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
            'merge_output_format': 'mp4',
        }
        self.current_progress = 0
        self.download_completed = False
        self.download_started = False

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            if not self.download_started:
                self.download_started = True
                with use_scope('download_progress', clear=True):
                    put_text("Baixando...").style("color: blue; font-size: 16px")
                    put_processbar('download')

            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded_bytes = d.get('downloaded_bytes', 0)

            if total_bytes:
                progress = (downloaded_bytes / total_bytes)
                speed = d.get('speed', 0)
                if speed:
                    speed_mb = speed / 1024 / 1024
                    eta = d.get('eta', 0)
                    with use_scope('status', clear=True):
                        put_text(f"Velocidade: {speed_mb:.1f} MB/s - Tempo restante: {eta} segundos")

                set_processbar('download', progress)

        elif d['status'] == 'finished':
            if not self.download_completed:
                with use_scope('download_progress', clear=True):
                    put_text("Download dos arquivos concluído! Iniciando processamento final...").style(
                        "color: blue; font-size: 16px")
                    put_processbar('processing')
                    set_processbar('processing', 0.5)
                self.download_completed = True

    def postprocessor_hook(self, d):
        if d['status'] == 'started':
            with use_scope('processing', clear=True):
                put_text("Iniciando mesclagem de áudio e vídeo...").style("color: blue; font-size: 16px")
                put_processbar('merge')
                set_processbar('merge', 0.3)
        elif d['status'] == 'processing':
            set_processbar('merge', 0.6)
        elif d['status'] == 'finished':
            set_processbar('merge', 1.0)
            with use_scope('status', clear=True):
                put_text("Mesclagem concluída com sucesso!").style("color: green; font-size: 16px")
            self.download_completed = False
            self.download_started = False

    def download(self, video_link):
        try:
            # Limpa escopos anteriores
            clear('download_progress')
            clear('processing')
            clear('status')

            put_text("Iniciando download em alta qualidade...").style("color: blue; font-size: 20px")

            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                # Obtém informações do vídeo
                info = ydl.extract_info(video_link, download=False)
                put_text(f"Título: {info.get('title')}")
                put_text(f"Canal: {info.get('channel')}")

                # Inicia o download
                ydl.download([video_link])

            expected_path = os.path.join(self._path, f"{info.get('title')}.mp4")
            if os.path.exists(expected_path):
                put_text("Processo finalizado com sucesso!").style("color: green; font-size: 20px")
                os.startfile(self._path)
                return True
            else:
                put_text("Arquivo final não encontrado. Verifique a pasta de downloads.").style(
                    "color: red; font-size: 16px")
                return False

        except Exception as e:
            put_text(f"Erro durante o processamento: {str(e)}").style("color: red; font-size: 16px")
            return False

        finally:
            self.current_progress = 0
            self.download_completed = False
            self.download_started = False
