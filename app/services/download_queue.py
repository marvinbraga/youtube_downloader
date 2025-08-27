"""
Sistema de Fila de Downloads com controle de concorrência e retry
"""
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable
import uuid
from loguru import logger


class DownloadStatus(str, Enum):
    QUEUED = "queued"
    DOWNLOADING = "downloading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


@dataclass
class DownloadTask:
    """Representa uma tarefa de download na fila"""
    id: str
    audio_id: str
    url: str
    high_quality: bool = True
    status: DownloadStatus = DownloadStatus.QUEUED
    priority: int = 0  # Maior número = maior prioridade
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    retry_delay: int = 5  # segundos
    next_retry_at: Optional[datetime] = None
    progress: int = 0
    
    def can_retry(self) -> bool:
        """Verifica se pode tentar novamente"""
        return (
            self.status == DownloadStatus.FAILED and
            self.retry_count < self.max_retries
        )
    
    def should_retry_now(self) -> bool:
        """Verifica se deve tentar novamente agora"""
        if not self.can_retry():
            return False
        if not self.next_retry_at:
            return True
        return datetime.now() >= self.next_retry_at
    
    def schedule_retry(self):
        """Agenda próxima tentativa com backoff exponencial"""
        self.retry_count += 1
        delay = self.retry_delay * (2 ** (self.retry_count - 1))  # backoff exponencial
        self.next_retry_at = datetime.now() + timedelta(seconds=delay)
        self.status = DownloadStatus.RETRYING
        logger.info(f"Agendando retry {self.retry_count} para {self.audio_id} em {delay}s")


class DownloadQueue:
    """Gerenciador de fila de downloads com controle de concorrência"""
    
    def __init__(self, max_concurrent_downloads: int = 2):
        self.max_concurrent_downloads = max_concurrent_downloads
        self.tasks: Dict[str, DownloadTask] = {}
        self.active_downloads: Dict[str, asyncio.Task] = {}
        self.queue_lock = asyncio.Lock()
        self.is_running = False
        self._processor_task: Optional[asyncio.Task] = None
        
        # Callbacks
        self.on_download_started: Optional[Callable[[DownloadTask], None]] = None
        self.on_download_progress: Optional[Callable[[DownloadTask, int], None]] = None
        self.on_download_completed: Optional[Callable[[DownloadTask], None]] = None
        self.on_download_failed: Optional[Callable[[DownloadTask, str], None]] = None
        self.on_download_cancelled: Optional[Callable[[DownloadTask], None]] = None
        
        logger.info(f"Fila de downloads inicializada com limite de {max_concurrent_downloads} downloads simultâneos")
    
    async def add_download(
        self, 
        audio_id: str, 
        url: str, 
        high_quality: bool = True, 
        priority: int = 0
    ) -> str:
        """Adiciona um download à fila"""
        task_id = str(uuid.uuid4())
        task = DownloadTask(
            id=task_id,
            audio_id=audio_id,
            url=url,
            high_quality=high_quality,
            priority=priority
        )
        
        async with self.queue_lock:
            self.tasks[task_id] = task
            
        logger.info(f"Download adicionado à fila: {audio_id} (ID: {task_id})")
        return task_id
    
    async def cancel_download(self, task_id: str) -> bool:
        """Cancela um download"""
        async with self.queue_lock:
            task = self.tasks.get(task_id)
            if not task:
                return False
            
            # Se está baixando ativamente, cancelar task
            if task_id in self.active_downloads:
                active_task = self.active_downloads[task_id]
                active_task.cancel()
                try:
                    await active_task
                except asyncio.CancelledError:
                    pass
                del self.active_downloads[task_id]
            
            task.status = DownloadStatus.CANCELLED
            task.completed_at = datetime.now()
            
            if self.on_download_cancelled:
                await self.on_download_cancelled(task)
            
            logger.info(f"Download cancelado: {task.audio_id}")
            return True
    
    async def get_queue_status(self) -> Dict:
        """Retorna status da fila"""
        async with self.queue_lock:
            total = len(self.tasks)
            queued = len([t for t in self.tasks.values() if t.status == DownloadStatus.QUEUED])
            downloading = len([t for t in self.tasks.values() if t.status == DownloadStatus.DOWNLOADING])
            completed = len([t for t in self.tasks.values() if t.status == DownloadStatus.COMPLETED])
            failed = len([t for t in self.tasks.values() if t.status == DownloadStatus.FAILED])
            cancelled = len([t for t in self.tasks.values() if t.status == DownloadStatus.CANCELLED])
            retrying = len([t for t in self.tasks.values() if t.status == DownloadStatus.RETRYING])
            
            return {
                "total": total,
                "queued": queued,
                "downloading": downloading,
                "completed": completed,
                "failed": failed,
                "cancelled": cancelled,
                "retrying": retrying,
                "active_slots": len(self.active_downloads),
                "max_concurrent": self.max_concurrent_downloads
            }
    
    async def get_task_status(self, task_id: str) -> Optional[DownloadTask]:
        """Retorna status de uma task específica"""
        return self.tasks.get(task_id)
    
    async def get_tasks_by_audio_id(self, audio_id: str) -> List[DownloadTask]:
        """Retorna todas as tasks de um audio_id"""
        return [task for task in self.tasks.values() if task.audio_id == audio_id]
    
    def start_processing(self):
        """Inicia o processamento da fila"""
        if not self.is_running:
            self.is_running = True
            self._processor_task = asyncio.create_task(self._process_queue())
            logger.info("Processamento da fila de downloads iniciado")
    
    async def stop_processing(self):
        """Para o processamento da fila"""
        self.is_running = False
        
        # Cancelar processor task
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        
        # Cancelar todos os downloads ativos
        for task_id, active_task in self.active_downloads.items():
            active_task.cancel()
            try:
                await active_task
            except asyncio.CancelledError:
                pass
        
        self.active_downloads.clear()
        logger.info("Processamento da fila de downloads parado")
    
    async def _process_queue(self):
        """Loop principal de processamento da fila"""
        while self.is_running:
            try:
                await self._process_next_downloads()
                await self._check_retries()
                await asyncio.sleep(1)  # Check a cada segundo
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Erro no processamento da fila: {e}")
                await asyncio.sleep(5)  # Wait antes de tentar novamente
    
    async def _process_next_downloads(self):
        """Processa próximos downloads disponíveis"""
        async with self.queue_lock:
            # Verificar se há slots disponíveis
            if len(self.active_downloads) >= self.max_concurrent_downloads:
                return
            
            # Encontrar próxima task na fila (por prioridade e tempo)
            available_tasks = [
                task for task in self.tasks.values()
                if task.status == DownloadStatus.QUEUED
            ]
            
            if not available_tasks:
                return
            
            # Ordenar por prioridade (desc) e depois por tempo de criação (asc)
            available_tasks.sort(key=lambda t: (-t.priority, t.created_at))
            
            # Pegar próxima task
            next_task = available_tasks[0]
            next_task.status = DownloadStatus.DOWNLOADING
            next_task.started_at = datetime.now()
            
            # Criar task assíncrona para processar download
            download_task = asyncio.create_task(
                self._execute_download(next_task)
            )
            
            self.active_downloads[next_task.id] = download_task
            
            logger.info(f"Iniciando download: {next_task.audio_id}")
    
    async def _check_retries(self):
        """Verifica e processa retries agendados"""
        async with self.queue_lock:
            retry_tasks = [
                task for task in self.tasks.values()
                if task.status == DownloadStatus.RETRYING and task.should_retry_now()
            ]
            
            for task in retry_tasks:
                task.status = DownloadStatus.QUEUED
                task.next_retry_at = None
                logger.info(f"Retry agendado voltou para fila: {task.audio_id}")
    
    async def _execute_download(self, task: DownloadTask):
        """Executa o download de uma task"""
        try:
            if self.on_download_started:
                await self.on_download_started(task)
            
            # Aqui seria a integração com o AudioDownloadManager
            # Por enquanto, vamos simular um download
            from app.services.redis_managers_adapter import RedisAudioDownloadManager
            from app.services.sse_manager import sse_manager
            
            # Instanciar o RedisAudioDownloadManager
            audio_manager = RedisAudioDownloadManager()
            
            # Callback para progresso
            async def progress_callback(progress):
                task.progress = progress
                if self.on_download_progress:
                    await self.on_download_progress(task, progress)
            
            # Executar download
            result = await audio_manager.download_audio_with_status_async(
                task.audio_id,
                task.url,
                sse_manager=sse_manager
            )
            
            # Sucesso
            task.status = DownloadStatus.COMPLETED
            task.completed_at = datetime.now()
            task.progress = 100
            
            if self.on_download_completed:
                await self.on_download_completed(task)
            
            logger.success(f"Download concluído: {task.audio_id}")
            
        except asyncio.CancelledError:
            task.status = DownloadStatus.CANCELLED
            task.completed_at = datetime.now()
            logger.info(f"Download cancelado: {task.audio_id}")
            raise
            
        except Exception as e:
            error_msg = str(e)
            task.error_message = error_msg
            
            # Tentar retry se possível
            if task.can_retry():
                task.schedule_retry()
                logger.warning(f"Download falhou, agendando retry: {task.audio_id} - {error_msg}")
            else:
                task.status = DownloadStatus.FAILED
                task.completed_at = datetime.now()
                logger.error(f"Download falhou definitivamente: {task.audio_id} - {error_msg}")
            
            if self.on_download_failed:
                await self.on_download_failed(task, error_msg)
            
        finally:
            # Remover da lista de downloads ativos
            if task.id in self.active_downloads:
                del self.active_downloads[task.id]
    
    async def cleanup_old_tasks(self, max_age_hours: int = 24):
        """Remove tasks antigas para evitar acúmulo de memória"""
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        
        async with self.queue_lock:
            old_tasks = [
                task_id for task_id, task in self.tasks.items()
                if task.completed_at and task.completed_at < cutoff
            ]
            
            for task_id in old_tasks:
                del self.tasks[task_id]
            
            if old_tasks:
                logger.info(f"Removidas {len(old_tasks)} tasks antigas da fila")


# Instância global da fila
download_queue = DownloadQueue(max_concurrent_downloads=2)