import os

import yt_dlp
from pywebio.output import put_text, put_processbar, set_processbar, put_html, clear

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
            'ffmpeg_location': None,  # Deixe None para usar o FFmpeg do sistema
        }
        self.current_progress = 0
        self.download_completed = False
        self.progress_div_id = 'download-progress'

    def create_progress_html(self, progress, speed_mb, eta):
        """Cria HTML para a barra de progresso com informações detalhadas"""
        return f"""
        <div style="margin: 10px 0;">
            <div style="background-color: #f0f0f0; border-radius: 4px; padding: 10px; margin-bottom: 5px;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                    <span>Progresso: {progress:.1f}%</span>
                    <span>Velocidade: {speed_mb:.1f} MB/s</span>
                    <span>Tempo restante: {eta} segundos</span>
                </div>
                <div style="background-color: #ddd; height: 20px; border-radius: 4px; overflow: hidden;">
                    <div style="background-color: #4CAF50; width: {progress}%; height: 100%; transition: width 0.3s ease;">
                    </div>
                </div>
            </div>
        </div>
        """

    def progress_hook(self, d):
        if d['status'] == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            downloaded_bytes = d.get('downloaded_bytes', 0)

            if total_bytes:
                progress = (downloaded_bytes / total_bytes) * 100
                if progress > self.current_progress + 1:  # Atualiza a cada 1%
                    self.current_progress = progress
                    speed = d.get('speed', 0)
                    speed_mb = speed / 1024 / 1024 if speed else 0
                    eta = d.get('eta', 0)

                    # Limpa o progresso anterior
                    clear(self.progress_div_id)

                    # Atualiza com o novo progresso
                    put_html(
                        self.create_progress_html(progress, speed_mb, eta),
                        scope=self.progress_div_id
                    )

        elif d['status'] == 'finished':
            if not self.download_completed:
                put_text("Download dos arquivos concluído! Iniciando processamento final...").style(
                    "color: blue; font-size: 20px")
                self.download_completed = True

    def postprocessor_hook(self, d):
        if d['status'] == 'started':
            put_text("Iniciando mesclagem de áudio e vídeo...").style("color: blue; font-size: 16px")
            # Cria uma nova barra para o processo de mesclagem
            put_processbar('merge_progress')
            set_processbar('merge_progress', 0)
        elif d['status'] == 'processing':
            # Atualiza o progresso da mesclagem (se disponível)
            set_processbar('merge_progress', 0.5)
        elif d['status'] == 'finished':
            set_processbar('merge_progress', 1)
            put_text("Mesclagem concluída com sucesso!").style("color: green; font-size: 16px")
            self.download_completed = False

    def get_video_info(self, url):
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                return info
            except Exception as e:
                put_text(f"Erro ao obter informações do vídeo: {str(e)}").style("color: red; font-size: 16px")
                return None

    def download(self, video_link):
        put_text("Iniciando download em alta qualidade...").style("color: blue; font-size: 20px")

        try:
            video_info = self.get_video_info(video_link)
            if not video_info:
                return False

            put_text(f"Título: {video_info.get('title')}")
            put_text(f"Canal: {video_info.get('channel')}")

            # Cria um div para o progresso
            put_html(f'<div id="{self.progress_div_id}"></div>')

            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                ydl.download([video_link])

            expected_path = os.path.join(self._path, f"{video_info.get('title')}.mp4")
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
