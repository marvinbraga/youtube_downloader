import asyncio
import os
import re
import json
import datetime
from pathlib import Path
from typing import Optional, Dict, List, Union, Any

import aiohttp
from fastapi import HTTPException
from loguru import logger
from yt_dlp import YoutubeDL

from app.services.configs import AUDIO_DIR, audio_mapping, AUDIO_CONFIG_PATH
from app.services.files import load_json_audios


class VideoStreamManager:
    def __init__(self):
        self.ydl_opts = {
            'format': 'best[ext=mp4]',  # Preferimos MP4 para compatibilidade
            'quiet': True,
            'no_warnings': True
        }

    async def get_direct_url(self, url: str) -> str:
        """Obtém a URL direta do stream do YouTube"""
        try:
            with YoutubeDL(self.ydl_opts) as ydl:
                # Executa a extração de forma assíncrona para não bloquear
                info = await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: ydl.extract_info(url, download=False)
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


class AudioDownloadManager:
    """Gerencia o download de áudio do YouTube."""
    
    def __init__(self):
        """
        Inicializa o gerenciador de download de áudio usando o diretório de áudio configurado
        """
        self.download_dir = AUDIO_DIR
        self.audio_data = self._load_audio_data()
        logger.info(f"Gerenciador de download de áudio inicializado com diretório: {self.download_dir}")
    
    def _load_audio_data(self) -> Dict[str, Any]:
        """
        Carrega os dados de áudio do arquivo JSON utilizando a função load_json_audios
        
        Returns:
            Dicionário com os dados de áudio
        """
        return load_json_audios()
    
    def _save_audio_data(self) -> None:
        """
        Salva os dados de áudio no arquivo JSON
        """
        try:
            with open(AUDIO_CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.audio_data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Dados de áudio salvos em: {AUDIO_CONFIG_PATH}")
        except Exception as e:
            logger.error(f"Erro ao salvar arquivo de configuração de áudio: {str(e)}")
    
    def extract_youtube_id(self, url: str) -> Optional[str]:
        """
        Extrai o ID do YouTube de uma URL
        
        Args:
            url: URL do vídeo do YouTube
            
        Returns:
            ID do YouTube ou None se não for possível extrair
        """
        try:
            # Primeiro, tenta extrair o ID usando expressões regulares
            youtube_id = None
            
            # Padrão para URLs no formato https://www.youtube.com/watch?v=VIDEO_ID
            match = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]+)', url)
            if match:
                youtube_id = match.group(1)
            
            # Se não encontrou com regex, tenta usando yt-dlp
            if not youtube_id:
                ydl_info_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'skip_download': True,
                    'extract_flat': True
                }
                
                with YoutubeDL(ydl_info_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    youtube_id = info.get('id', '')
            
            return youtube_id
        except Exception as e:
            logger.error(f"Erro ao extrair ID do YouTube: {str(e)}")
            return None
    
    def download_audio(self, url: str) -> str:
        """
        Baixa apenas o áudio de um vídeo do YouTube em alta qualidade.
        Cada download é salvo em um diretório com o ID do YouTube.
        
        Args:
            url: URL do vídeo do YouTube
            
        Returns:
            Caminho do arquivo baixado
        """
        try:
            logger.info(f"Iniciando download de áudio: {url}")
            
            # Primeiro, vamos extrair as informações do vídeo para obter o ID do YouTube
            youtube_id = self.extract_youtube_id(url)
                
            if not youtube_id:
                logger.warning("Não foi possível obter o ID do YouTube, usando data atual como fallback")
                # Fallback para um formato de data se não conseguir obter o ID
                youtube_id = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Cria um diretório específico usando o ID do YouTube
            download_dir = self.download_dir / youtube_id
            download_dir.mkdir(exist_ok=True)
            
            logger.info(f"Salvando áudio no diretório: {download_dir}")
            
            # Registra a data de criação
            created_date = datetime.datetime.now().isoformat()
            
            # Configurações para download apenas de áudio em alta qualidade
            ydl_opts = {
                # Formato de áudio de alta qualidade
                'format': 'bestaudio/best',
                
                # Diretório e padrão de nome para o arquivo baixado
                'outtmpl': str(download_dir / '%(title)s.%(ext)s'),
                
                # Processador para extrair áudio e converter para m4a
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'm4a',
                    'preferredquality': '192',  # Qualidade do áudio (bitrate)
                }],
                
                # Configurações de rede e extração
                'socket_timeout': 30,
                'retries': 10,
                'fragment_retries': 10,
                'nocheckcertificate': True,
                'ignoreerrors': False,
                'verbose': True,
                'noplaylist': True,
                
                # Cabeçalhos HTTP para contornar restrições
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'DNT': '1',
                }
            }
            
            # Faz o download do áudio
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                
                # O arquivo será m4a após o processamento
                original_filename = ydl.prepare_filename(info)
                filename = Path(original_filename).with_suffix('.m4a')
                
                # Preparar metadados do áudio
                audio_metadata = {
                    "id": youtube_id,  # Usamos o ID do YouTube como ID do áudio
                    "title": info.get('title', ''),
                    "youtube_id": youtube_id,
                    "url": url,
                    "path": str(filename.relative_to(self.download_dir.parent)),
                    "directory": str(download_dir.relative_to(self.download_dir.parent)),
                    "created_date": created_date,
                    "modified_date": created_date,
                    "format": "m4a",
                    "filesize": filename.stat().st_size if filename.exists() else 0,
                    "has_transcription": False,
                    "transcription_path": "",
                    "keywords": self._extract_keywords(info.get('title', ''))
                }
                
                # Adicionar à lista de áudios
                self.audio_data["audios"].append(audio_metadata)
                
                # Adicionar aos mapeamentos
                mappings = {}
                mappings[youtube_id] = str(filename)
                mappings[self._normalize_filename(filename.stem)] = str(filename)
                mappings[self._normalize_filename(info.get('title', ''))] = str(filename)
                
                # Atualizar o dicionário de mapeamentos
                self.audio_data["mappings"].update(mappings)
                
                # Salvar os dados
                self._save_audio_data()
                
                # Atualizar o mapeamento em memória
                self._add_audio_mappings(filename, info, youtube_id)
            
            logger.success(f"Download de áudio concluído: {filename}")
            return str(filename)
            
        except Exception as e:
            logger.exception(f"Erro no download de áudio: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Erro no download de áudio: {str(e)}"
            )
    
    def get_audio_info(self, audio_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtém informações de um áudio pelo ID
        
        Args:
            audio_id: ID do áudio
            
        Returns:
            Dicionário com informações do áudio ou None se não encontrado
        """
        for audio in self.audio_data["audios"]:
            if audio["id"] == audio_id:
                return audio
                
        # Se não encontrou pelo ID exato, procura por keywords ou ID do YouTube
        normalized_id = self._normalize_filename(audio_id)
        for audio in self.audio_data["audios"]:
            # Verificar se o ID normalizado está contido nas keywords
            if normalized_id in audio["keywords"]:
                return audio
            # Verificar se é o ID do YouTube
            if audio_id == audio["youtube_id"]:
                return audio
        
        return None
    
    def update_transcription_status(self, audio_id: str, transcription_path: str) -> bool:
        """
        Atualiza o status de transcrição de um áudio
        
        Args:
            audio_id: ID do áudio
            transcription_path: Caminho do arquivo de transcrição
            
        Returns:
            True se atualizado com sucesso, False caso contrário
        """
        for audio in self.audio_data["audios"]:
            if audio["id"] == audio_id:
                audio["has_transcription"] = True
                audio["transcription_path"] = transcription_path
                audio["modified_date"] = datetime.datetime.now().isoformat()
                self._save_audio_data()
                return True
                
        return False
    
    def _normalize_filename(self, filename: str) -> str:
        """
        Normaliza um nome de arquivo para ser usado como ID.
        Remove caracteres especiais e converte para minúsculas.
        
        Args:
            filename: Nome do arquivo
            
        Returns:
            Nome normalizado
        """
        # Remove caracteres especiais, deixando apenas letras, números e espaços
        normalized = re.sub(r'[^\w\s]', ' ', filename.lower())
        # Substitui espaços múltiplos por um único espaço
        normalized = re.sub(r'\s+', ' ', normalized)
        # Substituir espaços por underscores para um ID mais limpo
        normalized = normalized.strip().replace(' ', '_')
        return normalized
    
    def _extract_keywords(self, title: str) -> List[str]:
        """
        Extrai palavras-chave de um título para facilitar a busca
        
        Args:
            title: Título do áudio
            
        Returns:
            Lista de palavras-chave
        """
        # Normaliza o título
        normalized = self._normalize_filename(title)
        
        # Extrai as palavras
        words = normalized.split('_')
        
        # Filtra palavras muito curtas
        keywords = [word for word in words if len(word) > 3]
        
        # Adiciona o título normalizado completo
        keywords.append(normalized)
        
        return keywords
    
    def _add_audio_mappings(self, filename: Path, info: dict, youtube_id: str) -> None:
        """
        Adiciona várias formas de ID ao mapeamento de áudio.
        Isso aumenta as chances de encontrar o arquivo mais tarde.
        
        Args:
            filename: Caminho do arquivo de áudio
            info: Informações do vídeo obtidas do yt-dlp
            youtube_id: ID do vídeo do YouTube
        """
        # Mapeamentos básicos
        title = info.get('title', '')
        
        # Mapeia pelo ID do YouTube
        audio_mapping[youtube_id] = filename
        logger.debug(f"Mapeamento adicionado (ID YouTube): '{youtube_id}' -> {filename}")
        
        # Mapeia pelo nome do arquivo normalizado
        file_id = self._normalize_filename(filename.stem)
        audio_mapping[file_id] = filename
        logger.debug(f"Mapeamento adicionado: '{file_id}' -> {filename}")
        
        # Mapeia pelo título normalizado
        title_id = self._normalize_filename(title)
        if title_id and title_id != file_id:
            audio_mapping[title_id] = filename
            logger.debug(f"Mapeamento adicional: '{title_id}' -> {filename}")
        
        # Mapeia por partes do título para aumentar as chances de correspondência
        for word in self._extract_keywords(title):
            audio_mapping[word] = filename
            logger.debug(f"Mapeamento para palavra-chave: '{word}' -> {filename}")
