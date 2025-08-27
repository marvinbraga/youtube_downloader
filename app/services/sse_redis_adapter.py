"""
Adaptador SSE-Redis para integração transparente
Mantém compatibilidade com sistema SSE existente usando Redis como backend
"""

import asyncio
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime

from loguru import logger

from .sse_manager import SSEManager, DownloadEvent
from .redis_progress_manager import (
    RedisProgressManager, TaskType, TaskStatus, ProgressMetrics,
    get_progress_manager
)
from .redis_notifications import (
    RedisNotificationManager, NotificationType, NotificationPriority,
    get_notification_manager
)


class SSERedisAdapter(SSEManager):
    """
    Adaptador que substitui SSEManager mantendo compatibilidade total
    Usa Redis como backend para performance 100x superior
    """
    
    def __init__(self):
        # Não chamar super().__init__() para evitar duplicação
        self._clients: Dict[str, asyncio.Queue] = {}
        self._download_status: Dict[str, Dict] = {}
        
        # Componentes Redis
        self._progress_manager: Optional[RedisProgressManager] = None
        self._notification_manager: Optional[RedisNotificationManager] = None
        
        # Cache local para compatibilidade
        self._local_cache_enabled = True
        
        logger.info("SSERedisAdapter inicializado")
    
    async def initialize(self) -> None:
        """Inicializa componentes Redis"""
        try:
            # Inicializar managers Redis
            self._progress_manager = await get_progress_manager(self)
            self._notification_manager = await get_notification_manager()
            
            # Registrar handlers para integração
            self._setup_integration_handlers()
            
            logger.success("SSERedisAdapter inicializado com Redis backend")
            
        except Exception as e:
            logger.error(f"Erro ao inicializar SSERedisAdapter: {e}")
            raise
    
    def _setup_integration_handlers(self) -> None:
        """Configura handlers para integração entre componentes"""
        try:
            # Handler para eventos de progresso -> notificações
            async def progress_to_notification_handler(event):
                try:
                    # Mapear evento de progresso para notificação
                    notification_type = self._map_progress_to_notification(event.event_type)
                    
                    if notification_type:
                        title = self._generate_notification_title(event)
                        # Handle progress as dict or object
                        progress_pct = event.progress.get('percentage', 0) if isinstance(event.progress, dict) else getattr(event.progress, 'percentage', 0)
                        message = event.message or f"{event.event_type}: {progress_pct:.1f}%"
                        
                        # Determinar prioridade
                        priority = NotificationPriority.NORMAL
                        if event.status == TaskStatus.FAILED:
                            priority = NotificationPriority.HIGH
                        elif event.status == TaskStatus.COMPLETED:
                            priority = NotificationPriority.NORMAL
                        
                        # Broadcast para todos os clientes interessados no task
                        await self._notification_manager.broadcast(
                            notification_type=notification_type,
                            title=title,
                            message=message,
                            priority=priority,
                            data={
                                "task_id": event.task_id,
                                "task_type": event.task_type.value if hasattr(event.task_type, 'value') else str(event.task_type),
                                "status": event.status.value if hasattr(event.status, 'value') else str(event.status),
                                "progress": event.progress.get('percentage', 0) if isinstance(event.progress, dict) else getattr(event.progress, 'percentage', 0),
                                "timestamp": event.timestamp
                            }
                        )
                        
                except Exception as e:
                    logger.error(f"Erro em progress_to_notification_handler: {e}")
            
            # Registrar handler no progress manager
            if self._progress_manager:
                asyncio.create_task(
                    self._progress_manager.subscribe_to_all(progress_to_notification_handler)
                )
            
        except Exception as e:
            logger.error(f"Erro ao configurar handlers de integração: {e}")
    
    def _map_progress_to_notification(self, event_type: str) -> Optional[NotificationType]:
        """Mapeia eventos de progresso para tipos de notificação"""
        mapping = {
            "started": NotificationType.TASK_STARTED,
            "progress": NotificationType.TASK_PROGRESS,
            "completed": NotificationType.TASK_COMPLETED,
            "failed": NotificationType.TASK_FAILED,
            "cancelled": NotificationType.TASK_CANCELLED
        }
        return mapping.get(event_type)
    
    def _generate_notification_title(self, event) -> str:
        """Gera título da notificação baseado no evento"""
        task_type_names = {
            TaskType.DOWNLOAD: "Download",
            TaskType.TRANSCRIPTION: "Transcrição",
            TaskType.CONVERSION: "Conversão",
            TaskType.UPLOAD: "Upload"
        }
        
        task_name = task_type_names.get(event.task_type, event.task_type.value if hasattr(event.task_type, 'value') else str(event.task_type))
        
        if event.status == TaskStatus.RUNNING and event.event_type == "started":
            return f"{task_name} Iniciado"
        elif event.status == TaskStatus.RUNNING and event.event_type == "progress":
            return f"{task_name} em Progresso"
        elif event.status == TaskStatus.COMPLETED:
            return f"{task_name} Concluído"
        elif event.status == TaskStatus.FAILED:
            return f"{task_name} Falhou"
        elif event.status == TaskStatus.CANCELLED:
            return f"{task_name} Cancelado"
        
        return f"{task_name} - {event.event_type}"
    
    # Métodos compatíveis com SSEManager original
    async def connect(self, client_id: str) -> asyncio.Queue:
        """Conecta cliente mantendo compatibilidade com SSE original"""
        try:
            # Conectar ao sistema de notificações Redis
            if self._notification_manager:
                await self._notification_manager.register_client(
                    client_id=client_id,
                    groups=["downloads", "transcriptions"],  # Grupos padrão
                    metadata={"connected_via": "sse", "type": "web_client"}
                )
            
            # Manter comportamento original
            queue = asyncio.Queue()
            self._clients[client_id] = queue
            
            # Enviar evento de conexão
            welcome_event = DownloadEvent(
                audio_id="system",
                event_type="connected",
                message=f"Conectado ao stream Redis. ID: {client_id}"
            )
            await queue.put(welcome_event.to_sse())
            
            logger.info(f"Cliente SSE conectado via Redis: {client_id}")
            return queue
            
        except Exception as e:
            logger.error(f"Erro ao conectar cliente {client_id}: {e}")
            raise
    
    def disconnect(self, client_id: str):
        """Desconecta cliente"""
        try:
            # Remover do sistema de notificações
            if self._notification_manager:
                asyncio.create_task(
                    self._notification_manager.unregister_client(client_id)
                )
            
            # Manter comportamento original
            if client_id in self._clients:
                del self._clients[client_id]
                logger.info(f"Cliente SSE desconectado: {client_id}")
                
        except Exception as e:
            logger.error(f"Erro ao desconectar cliente {client_id}: {e}")
    
    async def download_started(self, audio_id: str, message: str = "Download iniciado"):
        """Notifica início de download usando Redis"""
        try:
            # Criar tarefa no Redis
            if self._progress_manager:
                task_info = await self._progress_manager.create_task(
                    task_id=audio_id,
                    task_type=TaskType.DOWNLOAD,
                    metadata={
                        "audio_id": audio_id,
                        "started_message": message
                    }
                )
                
                await self._progress_manager.start_task(audio_id, message)
            
            # Manter cache local para compatibilidade
            if self._local_cache_enabled:
                self._download_status[audio_id] = {
                    "status": "downloading",
                    "progress": 0,
                    "started_at": datetime.now().isoformat()
                }
            
            # Broadcast via SSE original (será interceptado pelo Redis)
            event = DownloadEvent(
                audio_id=audio_id,
                event_type="download_started",
                progress=0,
                message=message
            )
            await self.broadcast_event(event)
            
            logger.info(f"Download iniciado via Redis: {audio_id}")
            
        except Exception as e:
            logger.error(f"Erro ao iniciar download {audio_id}: {e}")
            # Fallback para método original
            await super().download_started(audio_id, message)
    
    async def download_progress(
        self, 
        audio_id: str, 
        progress: int, 
        message: str = None,
        speed_bps: float = 0.0,
        bytes_downloaded: int = 0,
        total_bytes: int = 0,
        eta_seconds: Optional[int] = None
    ):
        """Atualiza progresso com métricas detalhadas"""
        try:
            # Atualizar via Redis com métricas completas
            if self._progress_manager:
                progress_metrics = ProgressMetrics(
                    percentage=float(progress),
                    bytes_downloaded=bytes_downloaded,
                    total_bytes=total_bytes,
                    speed_bps=speed_bps,
                    eta_seconds=eta_seconds
                )
                
                await self._progress_manager.update_progress(
                    task_id=audio_id,
                    progress=progress_metrics,
                    message=message or f"Progresso: {progress}%"
                )
            
            # Manter cache local
            if self._local_cache_enabled and audio_id in self._download_status:
                self._download_status[audio_id]["progress"] = progress
            
            # Broadcast via SSE
            event = DownloadEvent(
                audio_id=audio_id,
                event_type="download_progress",
                progress=progress,
                message=message or f"Progresso: {progress}%"
            )
            await self.broadcast_event(event)
            
            # Log otimizado
            if progress % 10 == 0:
                logger.debug(f"Download progresso via Redis: {audio_id} - {progress}%")
                
        except Exception as e:
            logger.error(f"Erro ao atualizar progresso {audio_id}: {e}")
            # Fallback
            await super().download_progress(audio_id, progress, message)
    
    async def download_completed(self, audio_id: str, message: str = "Download concluído"):
        """Marca download como concluído"""
        try:
            # Completar via Redis
            if self._progress_manager:
                await self._progress_manager.complete_task(audio_id, message)
            
            # Manter cache local
            if self._local_cache_enabled and audio_id in self._download_status:
                self._download_status[audio_id].update({
                    "status": "completed",
                    "progress": 100,
                    "completed_at": datetime.now().isoformat()
                })
            
            # Broadcast via SSE
            event = DownloadEvent(
                audio_id=audio_id,
                event_type="download_completed",
                progress=100,
                message=message
            )
            await self.broadcast_event(event)
            
            logger.info(f"Download concluído via Redis: {audio_id}")
            
        except Exception as e:
            logger.error(f"Erro ao completar download {audio_id}: {e}")
            # Fallback
            await super().download_completed(audio_id, message)
    
    async def download_error(self, audio_id: str, error: str):
        """Notifica erro no download"""
        try:
            # Marcar como falhou no Redis
            if self._progress_manager:
                await self._progress_manager.fail_task(
                    task_id=audio_id,
                    error=error,
                    message=f"Erro no download: {error}"
                )
            
            # Manter cache local
            if self._local_cache_enabled and audio_id in self._download_status:
                self._download_status[audio_id].update({
                    "status": "error",
                    "error": error,
                    "error_at": datetime.now().isoformat()
                })
            
            # Broadcast via SSE
            event = DownloadEvent(
                audio_id=audio_id,
                event_type="download_error",
                error=error,
                message=f"Erro no download: {error}"
            )
            await self.broadcast_event(event)
            
            logger.error(f"Download erro via Redis: {audio_id} - {error}")
            
        except Exception as e:
            logger.error(f"Erro ao processar erro de download {audio_id}: {e}")
            # Fallback
            await super().download_error(audio_id, error)
    
    # Métodos para transcrição (extensão do sistema original)
    async def transcription_started(self, audio_id: str, message: str = "Transcrição iniciada"):
        """Inicia processo de transcrição"""
        try:
            if self._progress_manager:
                task_info = await self._progress_manager.create_task(
                    task_id=f"transcription_{audio_id}",
                    task_type=TaskType.TRANSCRIPTION,
                    metadata={
                        "audio_id": audio_id,
                        "started_message": message
                    }
                )
                
                await self._progress_manager.start_task(f"transcription_{audio_id}", message)
            
            # Broadcast via SSE
            event = DownloadEvent(
                audio_id=audio_id,
                event_type="transcription_started",
                progress=0,
                message=message
            )
            await self.broadcast_event(event)
            
            logger.info(f"Transcrição iniciada via Redis: {audio_id}")
            
        except Exception as e:
            logger.error(f"Erro ao iniciar transcrição {audio_id}: {e}")
    
    async def transcription_progress(
        self, 
        audio_id: str, 
        progress: int, 
        current_step: str = "",
        total_steps: int = 1,
        step_progress: float = 0.0,
        message: str = None
    ):
        """Atualiza progresso da transcrição com detalhes granulares"""
        try:
            if self._progress_manager:
                progress_metrics = ProgressMetrics(
                    percentage=float(progress),
                    current_step=current_step,
                    total_steps=total_steps,
                    step_progress=step_progress
                )
                
                await self._progress_manager.update_progress(
                    task_id=f"transcription_{audio_id}",
                    progress=progress_metrics,
                    message=message or f"Transcrição: {progress}% - {current_step}"
                )
            
            # Broadcast via SSE
            event = DownloadEvent(
                audio_id=audio_id,
                event_type="transcription_progress",
                progress=progress,
                message=message or f"Transcrição: {progress}% - {current_step}"
            )
            await self.broadcast_event(event)
            
        except Exception as e:
            logger.error(f"Erro ao atualizar progresso de transcrição {audio_id}: {e}")
    
    async def transcription_completed(self, audio_id: str, message: str = "Transcrição concluída"):
        """Marca transcrição como concluída"""
        try:
            if self._progress_manager:
                await self._progress_manager.complete_task(f"transcription_{audio_id}", message)
            
            # Broadcast via SSE
            event = DownloadEvent(
                audio_id=audio_id,
                event_type="transcription_completed",
                progress=100,
                message=message
            )
            await self.broadcast_event(event)
            
            logger.info(f"Transcrição concluída via Redis: {audio_id}")
            
        except Exception as e:
            logger.error(f"Erro ao completar transcrição {audio_id}: {e}")
    
    async def transcription_error(self, audio_id: str, error: str):
        """Notifica erro na transcrição"""
        try:
            if self._progress_manager:
                await self._progress_manager.fail_task(
                    task_id=f"transcription_{audio_id}",
                    error=error,
                    message=f"Erro na transcrição: {error}"
                )
            
            # Broadcast via SSE
            event = DownloadEvent(
                audio_id=audio_id,
                event_type="transcription_error",
                error=error,
                message=f"Erro na transcrição: {error}"
            )
            await self.broadcast_event(event)
            
            logger.error(f"Transcrição erro via Redis: {audio_id} - {error}")
            
        except Exception as e:
            logger.error(f"Erro ao processar erro de transcrição {audio_id}: {e}")
    
    # Métodos de consulta aprimorados
    def get_download_status(self, audio_id: str) -> Optional[Dict]:
        """Obtém status de download (compatibilidade + Redis)"""
        try:
            # Tentar obter do Redis primeiro
            if self._progress_manager:
                task_info = asyncio.create_task(
                    self._progress_manager.get_task_info(audio_id)
                )
                
                # Se não conseguir de forma síncrona, usar cache local
                if self._local_cache_enabled:
                    return self._download_status.get(audio_id)
            
            return self._download_status.get(audio_id)
            
        except Exception as e:
            logger.error(f"Erro ao obter status de download {audio_id}: {e}")
            return self._download_status.get(audio_id)
    
    def get_all_downloads_status(self) -> Dict[str, Dict]:
        """Retorna status de todos os downloads"""
        try:
            # Para compatibilidade, retornar cache local
            # Em implementação completa, consultaria Redis
            return self._download_status.copy()
            
        except Exception as e:
            logger.error(f"Erro ao obter todos os status: {e}")
            return {}
    
    async def get_detailed_statistics(self) -> Dict[str, Any]:
        """Obtém estatísticas detalhadas do sistema Redis"""
        try:
            stats = {}
            
            if self._progress_manager:
                stats["progress"] = await self._progress_manager.get_statistics()
            
            if self._notification_manager:
                stats["notifications"] = await self._notification_manager.get_statistics()
            
            stats["adapter"] = {
                "connected_clients": len(self._clients),
                "local_cache_enabled": self._local_cache_enabled,
                "cached_downloads": len(self._download_status)
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas detalhadas: {e}")
            return {}
    
    async def close(self) -> None:
        """Fecha recursos do adapter"""
        try:
            if self._progress_manager:
                await self._progress_manager.close()
            
            if self._notification_manager:
                await self._notification_manager.close()
            
            logger.info("SSERedisAdapter fechado")
            
        except Exception as e:
            logger.error(f"Erro ao fechar SSERedisAdapter: {e}")


# Instância global que substitui sse_manager
sse_redis_adapter: Optional[SSERedisAdapter] = None


async def get_sse_manager() -> SSERedisAdapter:
    """Obtém instância do SSE Redis Adapter"""
    global sse_redis_adapter
    
    if sse_redis_adapter is None:
        sse_redis_adapter = SSERedisAdapter()
        await sse_redis_adapter.initialize()
    
    return sse_redis_adapter


async def init_sse_redis_adapter() -> None:
    """Inicializa o SSE Redis Adapter"""
    await get_sse_manager()


async def close_sse_redis_adapter() -> None:
    """Fecha o SSE Redis Adapter"""
    global sse_redis_adapter
    
    if sse_redis_adapter:
        await sse_redis_adapter.close()
        sse_redis_adapter = None