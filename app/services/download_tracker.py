"""
Download Tracker com Redis - Exemplo de implementação completa
Demonstra tracking granular com ETA, velocidade e progresso detalhado
"""

import asyncio
import time
import os
from typing import Optional, Dict, Any, Callable
from datetime import datetime, timedelta

from loguru import logger
import yt_dlp

from .redis_progress_manager import (
    RedisProgressManager, ProgressMetrics, TaskType,
    get_progress_manager
)
from .sse_redis_adapter import get_sse_manager


class DownloadTracker:
    """
    Tracker avançado para downloads com métricas em tempo real
    Integra com Redis para notificações instantâneas
    """
    
    def __init__(self):
        self._progress_manager: Optional[RedisProgressManager] = None
        self._sse_manager = None
        self._active_downloads: Dict[str, Dict[str, Any]] = {}
        
    async def initialize(self):
        """Inicializa o tracker"""
        try:
            self._sse_manager = await get_sse_manager()
            self._progress_manager = await get_progress_manager(self._sse_manager)
            
            logger.info("DownloadTracker inicializado com Redis")
            
        except Exception as e:
            logger.error(f"Erro ao inicializar DownloadTracker: {e}")
            raise
    
    async def download_with_progress(
        self,
        url: str,
        output_path: str,
        audio_id: str,
        format_selector: str = "bestaudio",
        progress_callback: Optional[Callable] = None
    ) -> bool:
        """
        Download com tracking completo de progresso
        
        Args:
            url: URL do vídeo
            output_path: Caminho de saída
            audio_id: ID único do áudio
            format_selector: Seletor de formato
            progress_callback: Callback adicional de progresso
            
        Returns:
            True se download foi bem-sucedido
        """
        
        start_time = time.time()
        last_update_time = start_time
        last_bytes = 0
        speed_history = []
        
        try:
            # Inicializar tracking
            await self._initialize_download_tracking(audio_id, url, output_path)
            
            # Configurar yt-dlp
            ydl_opts = {
                'format': format_selector,
                'outtmpl': output_path,
                'noplaylist': True,
                'extractaudio': True,
                'audioformat': 'mp3',
                'progress_hooks': [self._create_progress_hook(audio_id, progress_callback)],
                'logger': logger,
            }
            
            # Executar download
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                logger.info(f"Iniciando download: {url}")
                await self._progress_manager.start_task(
                    audio_id, 
                    f"Iniciando download de {url}"
                )
                
                # Download em thread separada para não bloquear
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, ydl.download, [url])
            
            # Finalizar com sucesso
            await self._finalize_download_success(audio_id)
            return True
            
        except Exception as e:
            await self._finalize_download_error(audio_id, str(e))
            return False
        
        finally:
            # Limpar tracking
            self._cleanup_download_tracking(audio_id)
    
    async def _initialize_download_tracking(
        self, 
        audio_id: str, 
        url: str, 
        output_path: str
    ):
        """Inicializa tracking para um download"""
        try:
            # Criar tarefa no Redis
            await self._progress_manager.create_task(
                task_id=audio_id,
                task_type=TaskType.DOWNLOAD,
                metadata={
                    "url": url,
                    "output_path": output_path,
                    "started_at": datetime.now().isoformat(),
                    "estimated_duration": None,
                    "file_size": None
                }
            )
            
            # Inicializar tracking local
            self._active_downloads[audio_id] = {
                "url": url,
                "output_path": output_path,
                "start_time": time.time(),
                "last_update": time.time(),
                "total_bytes": 0,
                "downloaded_bytes": 0,
                "speed_history": [],
                "eta_history": []
            }
            
            logger.info(f"Download tracking inicializado: {audio_id}")
            
        except Exception as e:
            logger.error(f"Erro ao inicializar tracking {audio_id}: {e}")
            raise
    
    def _create_progress_hook(
        self, 
        audio_id: str, 
        callback: Optional[Callable] = None
    ) -> Callable:
        """Cria hook de progresso para yt-dlp"""
        
        def progress_hook(d):
            try:
                if d['status'] == 'downloading':
                    asyncio.create_task(self._handle_download_progress(audio_id, d, callback))
                elif d['status'] == 'finished':
                    asyncio.create_task(self._handle_download_finished(audio_id, d))
                elif d['status'] == 'error':
                    asyncio.create_task(self._handle_download_error(audio_id, d))
                    
            except Exception as e:
                logger.error(f"Erro no progress hook {audio_id}: {e}")
        
        return progress_hook
    
    async def _handle_download_progress(
        self, 
        audio_id: str, 
        d: Dict[str, Any], 
        callback: Optional[Callable] = None
    ):
        """Processa atualização de progresso"""
        try:
            current_time = time.time()
            
            # Extrair dados do yt-dlp
            downloaded_bytes = d.get('downloaded_bytes', 0)
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            speed = d.get('speed', 0) or 0
            eta = d.get('eta')
            
            # Calcular porcentagem
            if total_bytes > 0:
                percentage = (downloaded_bytes / total_bytes) * 100
            else:
                percentage = 0.0
            
            # Calcular velocidade média
            if audio_id in self._active_downloads:
                tracking_data = self._active_downloads[audio_id]
                time_diff = current_time - tracking_data['last_update']
                
                if time_diff > 0:
                    bytes_diff = downloaded_bytes - tracking_data['downloaded_bytes']
                    current_speed = bytes_diff / time_diff if time_diff > 0 else 0
                    
                    # Manter histórico de velocidade para suavização
                    tracking_data['speed_history'].append(current_speed)
                    if len(tracking_data['speed_history']) > 10:
                        tracking_data['speed_history'].pop(0)
                    
                    # Velocidade média
                    avg_speed = sum(tracking_data['speed_history']) / len(tracking_data['speed_history'])
                    
                    # Calcular ETA próprio
                    if avg_speed > 0 and total_bytes > 0:
                        remaining_bytes = total_bytes - downloaded_bytes
                        estimated_eta = int(remaining_bytes / avg_speed)
                    else:
                        estimated_eta = eta
                    
                    # Atualizar dados de tracking
                    tracking_data.update({
                        'last_update': current_time,
                        'downloaded_bytes': downloaded_bytes,
                        'total_bytes': total_bytes,
                        'current_speed': avg_speed
                    })
                else:
                    avg_speed = speed
                    estimated_eta = eta
            else:
                avg_speed = speed
                estimated_eta = eta
            
            # Criar métricas detalhadas
            progress_metrics = ProgressMetrics(
                percentage=percentage,
                bytes_downloaded=downloaded_bytes,
                total_bytes=total_bytes,
                speed_bps=avg_speed,
                eta_seconds=estimated_eta
            )
            
            # Atualizar via Redis
            await self._progress_manager.update_progress(
                task_id=audio_id,
                progress=progress_metrics,
                message=self._format_progress_message(
                    percentage, avg_speed, estimated_eta, downloaded_bytes, total_bytes
                )
            )
            
            # Callback adicional se fornecido
            if callback:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(audio_id, progress_metrics)
                    else:
                        callback(audio_id, progress_metrics)
                except Exception as e:
                    logger.warning(f"Erro em callback personalizado: {e}")
                    
            # Log periódico
            if int(percentage) % 5 == 0 and int(percentage) != getattr(self, f'_last_log_{audio_id}', -1):
                logger.info(f"Download {audio_id}: {percentage:.1f}% - {self._format_speed(avg_speed)}")
                setattr(self, f'_last_log_{audio_id}', int(percentage))
                
        except Exception as e:
            logger.error(f"Erro ao processar progresso {audio_id}: {e}")
    
    def _format_progress_message(
        self, 
        percentage: float, 
        speed: float, 
        eta: Optional[int],
        downloaded: int, 
        total: int
    ) -> str:
        """Formata mensagem de progresso"""
        try:
            speed_str = self._format_speed(speed)
            size_str = self._format_size(downloaded, total)
            
            if eta and eta > 0:
                eta_str = self._format_eta(eta)
                return f"{percentage:.1f}% - {speed_str} - {size_str} - ETA: {eta_str}"
            else:
                return f"{percentage:.1f}% - {speed_str} - {size_str}"
                
        except Exception:
            return f"{percentage:.1f}%"
    
    def _format_speed(self, speed_bps: float) -> str:
        """Formata velocidade para exibição"""
        if speed_bps < 1024:
            return f"{speed_bps:.0f} B/s"
        elif speed_bps < 1024 * 1024:
            return f"{speed_bps / 1024:.1f} KB/s"
        elif speed_bps < 1024 * 1024 * 1024:
            return f"{speed_bps / (1024 * 1024):.1f} MB/s"
        else:
            return f"{speed_bps / (1024 * 1024 * 1024):.1f} GB/s"
    
    def _format_size(self, downloaded: int, total: int) -> str:
        """Formata tamanho para exibição"""
        def format_bytes(bytes_value):
            if bytes_value < 1024:
                return f"{bytes_value} B"
            elif bytes_value < 1024 * 1024:
                return f"{bytes_value / 1024:.1f} KB"
            elif bytes_value < 1024 * 1024 * 1024:
                return f"{bytes_value / (1024 * 1024):.1f} MB"
            else:
                return f"{bytes_value / (1024 * 1024 * 1024):.1f} GB"
        
        if total > 0:
            return f"{format_bytes(downloaded)} / {format_bytes(total)}"
        else:
            return format_bytes(downloaded)
    
    def _format_eta(self, eta_seconds: int) -> str:
        """Formata ETA para exibição"""
        if eta_seconds < 60:
            return f"{eta_seconds}s"
        elif eta_seconds < 3600:
            minutes = eta_seconds // 60
            seconds = eta_seconds % 60
            return f"{minutes}m{seconds:02d}s"
        else:
            hours = eta_seconds // 3600
            minutes = (eta_seconds % 3600) // 60
            return f"{hours}h{minutes:02d}m"
    
    async def _handle_download_finished(self, audio_id: str, d: Dict[str, Any]):
        """Processa conclusão do download"""
        try:
            filename = d.get('filename', 'Unknown')
            file_size = os.path.getsize(filename) if os.path.exists(filename) else 0
            
            await self._finalize_download_success(audio_id, {
                "filename": filename,
                "file_size": file_size,
                "final_status": "finished"
            })
            
        except Exception as e:
            logger.error(f"Erro ao finalizar download {audio_id}: {e}")
            await self._finalize_download_error(audio_id, str(e))
    
    async def _handle_download_error(self, audio_id: str, d: Dict[str, Any]):
        """Processa erro no download"""
        error_msg = d.get('error', 'Unknown error')
        await self._finalize_download_error(audio_id, error_msg)
    
    async def _finalize_download_success(
        self, 
        audio_id: str, 
        final_data: Optional[Dict[str, Any]] = None
    ):
        """Finaliza download com sucesso"""
        try:
            completion_message = "Download concluído com sucesso"
            
            if final_data and 'filename' in final_data:
                completion_message += f" - {os.path.basename(final_data['filename'])}"
            
            await self._progress_manager.complete_task(audio_id, completion_message)
            
            # Calcular estatísticas finais
            if audio_id in self._active_downloads:
                tracking_data = self._active_downloads[audio_id]
                total_time = time.time() - tracking_data['start_time']
                avg_speed = tracking_data.get('downloaded_bytes', 0) / total_time if total_time > 0 else 0
                
                logger.success(
                    f"Download concluído: {audio_id} - "
                    f"Tempo: {total_time:.1f}s - "
                    f"Velocidade média: {self._format_speed(avg_speed)}"
                )
                
        except Exception as e:
            logger.error(f"Erro ao finalizar download com sucesso {audio_id}: {e}")
    
    async def _finalize_download_error(self, audio_id: str, error: str):
        """Finaliza download com erro"""
        try:
            await self._progress_manager.fail_task(
                task_id=audio_id,
                error=error,
                message=f"Download falhou: {error}"
            )
            
            logger.error(f"Download falhou: {audio_id} - {error}")
            
        except Exception as e:
            logger.error(f"Erro ao finalizar download com erro {audio_id}: {e}")
    
    def _cleanup_download_tracking(self, audio_id: str):
        """Limpa dados de tracking local"""
        try:
            if audio_id in self._active_downloads:
                del self._active_downloads[audio_id]
            
            # Limpar logs temporários
            if hasattr(self, f'_last_log_{audio_id}'):
                delattr(self, f'_last_log_{audio_id}')
                
        except Exception as e:
            logger.warning(f"Erro ao limpar tracking {audio_id}: {e}")
    
    async def get_active_downloads(self) -> Dict[str, Any]:
        """Obtém informações de downloads ativos"""
        try:
            if self._progress_manager:
                active_tasks = await self._progress_manager.get_active_tasks()
                
                result = {}
                for task_id in active_tasks:
                    task_info = await self._progress_manager.get_task_info(task_id)
                    if task_info and task_info.task_type == TaskType.DOWNLOAD:
                        result[task_id] = {
                            "status": task_info.status.value,
                            "progress": task_info.progress.percentage,
                            "speed": task_info.progress.speed_bps,
                            "eta": task_info.progress.eta_seconds,
                            "started_at": task_info.started_at,
                            "updated_at": task_info.updated_at
                        }
                
                return result
                
            return {}
            
        except Exception as e:
            logger.error(f"Erro ao obter downloads ativos: {e}")
            return {}
    
    async def cancel_download(self, audio_id: str) -> bool:
        """Cancela um download ativo"""
        try:
            if self._progress_manager:
                await self._progress_manager.cancel_task(
                    task_id=audio_id,
                    message="Download cancelado pelo usuário"
                )
                
                # Cleanup local
                self._cleanup_download_tracking(audio_id)
                
                logger.info(f"Download cancelado: {audio_id}")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Erro ao cancelar download {audio_id}: {e}")
            return False


# Instância global
download_tracker: Optional[DownloadTracker] = None


async def get_download_tracker() -> DownloadTracker:
    """Obtém instância global do download tracker"""
    global download_tracker
    
    if download_tracker is None:
        download_tracker = DownloadTracker()
        await download_tracker.initialize()
    
    return download_tracker


async def init_download_tracker() -> None:
    """Inicializa o download tracker"""
    await get_download_tracker()


# Exemplo de uso
async def example_download_with_tracking():
    """Exemplo de como usar o download tracker"""
    
    async def custom_progress_callback(audio_id: str, progress: ProgressMetrics):
        """Callback personalizado de progresso"""
        print(f"Custom callback: {audio_id} - {progress.percentage:.1f}%")
    
    try:
        tracker = await get_download_tracker()
        
        success = await tracker.download_with_progress(
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            output_path="/tmp/%(title)s.%(ext)s",
            audio_id="test_download_123",
            format_selector="bestaudio[ext=m4a]",
            progress_callback=custom_progress_callback
        )
        
        if success:
            print("Download concluído com sucesso!")
        else:
            print("Download falhou!")
            
        # Verificar status
        active_downloads = await tracker.get_active_downloads()
        print(f"Downloads ativos: {len(active_downloads)}")
        
    except Exception as e:
        logger.error(f"Erro no exemplo: {e}")


if __name__ == "__main__":
    # Executar exemplo
    asyncio.run(example_download_with_tracking())