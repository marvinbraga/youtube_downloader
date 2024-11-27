import asyncio

import aiohttp
from fastapi import HTTPException
from loguru import logger
from yt_dlp import YoutubeDL


class VideoStreamManager:
    def __init__(self):
        self.ydl_opts = {
            'format': 'best[ext=mp4]',  # Preferimos MP4 para compatibilidade
            'quiet': True,
            'no_warnings': True
        }

    async def get_direct_url(self, youtube_url: str) -> str:
        """Obtém a URL direta do stream do YouTube"""
        try:
            with YoutubeDL(self.ydl_opts) as ydl:
                # Executa a extração de forma assíncrona para não bloquear
                info = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: ydl.extract_info(youtube_url, download=False)
                )

                # Pega a URL do formato selecionado
                return info['url']
        except Exception as e:
            logger.error(f"Erro ao obter URL do YouTube: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Erro ao processar vídeo do YouTube: {str(e)}"
            )

    async def stream_youtube_video(self, url: str):
        """Faz o streaming do vídeo do YouTube"""
        try:
            direct_url = await self.get_direct_url(url)

            async with aiohttp.ClientSession() as session:
                async with session.get(direct_url) as response:
                    if response.status != 200:
                        raise HTTPException(
                            status_code=response.status,
                            detail="Erro ao acessar stream do YouTube"
                        )

                    # Stream em chunks de 1MB
                    async for chunk in response.content.iter_chunked(1024 * 1024):
                        yield chunk

        except Exception as e:
            logger.error(f"Erro no streaming do YouTube: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Erro no streaming: {str(e)}"
            )
