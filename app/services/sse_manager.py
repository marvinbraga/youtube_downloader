"""
Gerenciador de Server-Sent Events (SSE) para comunicação em tempo real
"""
import asyncio
import json
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from loguru import logger


@dataclass
class DownloadEvent:
    """Estrutura de um evento de download"""
    audio_id: str
    event_type: str  # download_started, download_progress, download_completed, download_error
    progress: Optional[int] = None
    message: Optional[str] = None
    error: Optional[str] = None
    timestamp: Optional[str] = None
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def to_sse(self) -> str:
        """Converte o evento para formato SSE"""
        data = json.dumps(asdict(self))
        return f"event: {self.event_type}\ndata: {data}\n\n"


class SSEManager:
    """Gerencia conexões SSE e broadcasting de eventos"""
    
    def __init__(self):
        self._clients: Dict[str, asyncio.Queue] = {}
        self._download_status: Dict[str, Dict] = {}
        logger.info("SSE Manager inicializado")
    
    async def connect(self, client_id: str) -> asyncio.Queue:
        """Conecta um novo cliente SSE"""
        queue = asyncio.Queue()
        self._clients[client_id] = queue
        logger.info(f"Cliente SSE conectado: {client_id}")
        
        # Enviar evento de conexão
        welcome_event = DownloadEvent(
            audio_id="system",
            event_type="connected",
            message=f"Conectado ao stream de eventos. ID: {client_id}"
        )
        await queue.put(welcome_event.to_sse())
        
        return queue
    
    def disconnect(self, client_id: str):
        """Desconecta um cliente SSE"""
        if client_id in self._clients:
            del self._clients[client_id]
            logger.info(f"Cliente SSE desconectado: {client_id}")
    
    async def broadcast_event(self, event: DownloadEvent):
        """Envia um evento para todos os clientes conectados"""
        if not self._clients:
            return
        
        sse_data = event.to_sse()
        disconnected_clients = []
        
        for client_id, queue in self._clients.items():
            try:
                # Não bloquear se a fila estiver cheia
                queue.put_nowait(sse_data)
            except asyncio.QueueFull:
                logger.warning(f"Fila cheia para cliente {client_id}, pulando evento")
            except Exception as e:
                logger.error(f"Erro ao enviar evento para cliente {client_id}: {e}")
                disconnected_clients.append(client_id)
        
        # Remover clientes desconectados
        for client_id in disconnected_clients:
            self.disconnect(client_id)
    
    async def download_started(self, audio_id: str, message: str = "Download iniciado"):
        """Notifica que um download começou"""
        self._download_status[audio_id] = {
            "status": "downloading",
            "progress": 0,
            "started_at": datetime.now().isoformat()
        }
        
        event = DownloadEvent(
            audio_id=audio_id,
            event_type="download_started",
            progress=0,
            message=message
        )
        await self.broadcast_event(event)
        logger.info(f"Download iniciado: {audio_id}")
    
    async def download_progress(self, audio_id: str, progress: int, message: str = None):
        """Notifica progresso do download"""
        if audio_id in self._download_status:
            self._download_status[audio_id]["progress"] = progress
        
        event = DownloadEvent(
            audio_id=audio_id,
            event_type="download_progress",
            progress=progress,
            message=message or f"Progresso: {progress}%"
        )
        await self.broadcast_event(event)
        
        # Log apenas a cada 10% para não poluir
        if progress % 10 == 0:
            logger.debug(f"Download progresso: {audio_id} - {progress}%")
    
    async def download_completed(self, audio_id: str, message: str = "Download concluído"):
        """Notifica que um download foi concluído"""
        if audio_id in self._download_status:
            self._download_status[audio_id].update({
                "status": "completed",
                "progress": 100,
                "completed_at": datetime.now().isoformat()
            })
        
        event = DownloadEvent(
            audio_id=audio_id,
            event_type="download_completed",
            progress=100,
            message=message
        )
        await self.broadcast_event(event)
        logger.info(f"Download concluído: {audio_id}")
    
    async def download_error(self, audio_id: str, error: str):
        """Notifica erro no download"""
        if audio_id in self._download_status:
            self._download_status[audio_id].update({
                "status": "error",
                "error": error,
                "error_at": datetime.now().isoformat()
            })
        
        event = DownloadEvent(
            audio_id=audio_id,
            event_type="download_error",
            error=error,
            message=f"Erro no download: {error}"
        )
        await self.broadcast_event(event)
        logger.error(f"Download erro: {audio_id} - {error}")
    
    def get_download_status(self, audio_id: str) -> Optional[Dict]:
        """Retorna o status atual de um download"""
        return self._download_status.get(audio_id)
    
    def get_all_downloads_status(self) -> Dict[str, Dict]:
        """Retorna o status de todos os downloads"""
        return self._download_status.copy()


# Instância global do gerenciador SSE
sse_manager = SSEManager()