"""
Application Metrics Collector - Comprehensive Application and System Monitoring
Coletor completo de métricas de aplicação e sistema para monitoramento pós-cutover

Agent-Infrastructure - FASE 4 Production Monitoring
"""

import asyncio
import json
import time
import psutil
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
import statistics
import traceback

from loguru import logger

from app.services.redis_connection import get_redis_client
from app.services.api_performance_monitor import api_performance_monitor


@dataclass
class ApplicationMetric:
    """Métrica individual da aplicação"""
    timestamp: datetime
    category: str  # api, downloads, transcriptions, websockets, cache, database
    name: str
    value: float
    unit: str
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class SystemResourceMetrics:
    """Métricas de recursos do sistema"""
    timestamp: datetime
    
    # CPU metrics
    cpu_percent: float
    cpu_cores: int
    load_avg_1m: float
    load_avg_5m: float
    load_avg_15m: float
    
    # Memory metrics
    memory_total_gb: float
    memory_available_gb: float
    memory_used_gb: float
    memory_percent: float
    memory_cached_gb: float
    memory_buffers_gb: float
    
    # Disk metrics
    disk_total_gb: float
    disk_used_gb: float
    disk_free_gb: float
    disk_percent: float
    disk_read_mb_per_sec: float
    disk_write_mb_per_sec: float
    disk_read_iops: float
    disk_write_iops: float
    
    # Network metrics
    network_bytes_sent_per_sec: float
    network_bytes_recv_per_sec: float
    network_packets_sent_per_sec: float
    network_packets_recv_per_sec: float
    
    # Process metrics
    process_cpu_percent: float
    process_memory_mb: float
    process_threads: int
    process_open_files: int
    process_connections: int
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class ApplicationHealthMetrics:
    """Métricas de saúde da aplicação"""
    timestamp: datetime
    
    # API metrics
    api_requests_total: int
    api_requests_per_minute: float
    api_success_rate: float
    api_error_rate: float
    api_avg_response_time_ms: float
    api_p95_response_time_ms: float
    api_p99_response_time_ms: float
    
    # Download metrics
    active_downloads: int
    completed_downloads_today: int
    failed_downloads_today: int
    download_success_rate: float
    avg_download_speed_mbps: float
    
    # Transcription metrics
    active_transcriptions: int
    completed_transcriptions_today: int
    failed_transcriptions_today: int
    transcription_success_rate: float
    avg_transcription_time_sec: float
    
    # WebSocket/SSE metrics
    active_websocket_connections: int
    websocket_messages_per_minute: float
    websocket_error_rate: float
    
    # Cache metrics
    cache_hit_rate: float
    cache_miss_rate: float
    cache_operations_per_sec: float
    
    # Queue metrics
    queue_pending_jobs: int
    queue_processing_jobs: int
    queue_failed_jobs_today: int
    avg_queue_wait_time_sec: float
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class ApplicationMetricsCollector:
    """
    Coletor completo de métricas de aplicação e sistema
    
    Funcionalidades:
    - Métricas de recursos do sistema (CPU, memória, disk, network)
    - Métricas de aplicação (API, downloads, transcrições)
    - Métricas de performance de componentes
    - Análise de tendências
    - Detecção de anomalias
    - Correlação entre métricas
    """
    
    def __init__(self, collection_interval: int = 30):
        self.collection_interval = collection_interval
        self.is_collecting = False
        self._stop_collecting = False
        
        # Storage
        self._system_metrics: deque[SystemResourceMetrics] = deque(maxlen=2880)  # 24h
        self._app_metrics: deque[ApplicationHealthMetrics] = deque(maxlen=2880)  # 24h
        self._raw_metrics: deque[ApplicationMetric] = deque(maxlen=10000)
        
        # Sistema de coleta personalizada
        self._custom_collectors: Dict[str, Callable] = {}
        
        # Cache para cálculos de rate
        self._last_values = {}
        self._last_disk_io = None
        self._last_network_io = None
        
        # Process handle
        self._process = psutil.Process()
        
        # Redis client
        self._redis_client = None
        
        # Locks para thread safety
        self._metrics_lock = threading.Lock()
        
        logger.info(f"ApplicationMetricsCollector initialized (interval: {collection_interval}s)")
    
    async def initialize(self) -> bool:
        """Inicializa o coletor de métricas"""
        try:
            # Conecta ao Redis
            self._redis_client = await get_redis_client()
            if self._redis_client:
                logger.info("Redis connection established for metrics persistence")
            else:
                logger.warning("Redis not available - metrics will be memory-only")
            
            # Registra coletores customizados
            await self._register_custom_collectors()
            
            logger.info("Application metrics collector initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize application metrics collector: {e}")
            return False
    
    async def start_collection(self):
        """Inicia a coleta de métricas"""
        if self.is_collecting:
            logger.warning("Metrics collection already running")
            return
        
        if not await self.initialize():
            logger.error("Cannot start metrics collection - initialization failed")
            return
        
        self.is_collecting = True
        self._stop_collecting = False
        
        logger.info("Starting comprehensive metrics collection")
        
        # Tasks de coleta
        system_task = asyncio.create_task(self._system_metrics_loop())
        app_task = asyncio.create_task(self._application_metrics_loop())
        custom_task = asyncio.create_task(self._custom_metrics_loop())
        analysis_task = asyncio.create_task(self._analysis_loop())
        
        try:
            await asyncio.gather(
                system_task,
                app_task,
                custom_task,
                analysis_task
            )
        except Exception as e:
            logger.error(f"Error in metrics collection tasks: {e}")
        finally:
            self.is_collecting = False
            logger.info("Metrics collection stopped")
    
    async def stop_collection(self):
        """Para a coleta de métricas"""
        self._stop_collecting = True
        self.is_collecting = False
        logger.info("Stopping metrics collection...")
    
    async def _system_metrics_loop(self):
        """Loop de coleta de métricas de sistema"""
        while not self._stop_collecting:
            try:
                metrics = await self._collect_system_metrics()
                
                if metrics:
                    with self._metrics_lock:
                        self._system_metrics.append(metrics)
                    
                    # Persiste no Redis
                    if self._redis_client:
                        await self._persist_system_metrics(metrics)
                
                await asyncio.sleep(self.collection_interval)
                
            except Exception as e:
                logger.error(f"Error in system metrics collection: {e}")
                await asyncio.sleep(self.collection_interval)
    
    async def _collect_system_metrics(self) -> Optional[SystemResourceMetrics]:
        """Coleta métricas de recursos do sistema"""
        try:
            timestamp = datetime.now()
            
            # CPU metrics
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_cores = psutil.cpu_count()
            
            try:
                load_avg = psutil.getloadavg()
                load_avg_1m, load_avg_5m, load_avg_15m = load_avg
            except (AttributeError, OSError):
                # Windows não tem getloadavg
                load_avg_1m = load_avg_5m = load_avg_15m = cpu_percent / 100 * cpu_cores
            
            # Memory metrics
            memory = psutil.virtual_memory()
            memory_total_gb = memory.total / (1024**3)
            memory_available_gb = memory.available / (1024**3)
            memory_used_gb = memory.used / (1024**3)
            memory_cached_gb = getattr(memory, 'cached', 0) / (1024**3)
            memory_buffers_gb = getattr(memory, 'buffers', 0) / (1024**3)
            
            # Disk metrics
            disk = psutil.disk_usage('/')
            disk_total_gb = disk.total / (1024**3)
            disk_used_gb = disk.used / (1024**3)
            disk_free_gb = disk.free / (1024**3)
            
            # Disk I/O
            disk_io = psutil.disk_io_counters()
            disk_read_mb_per_sec, disk_write_mb_per_sec = 0.0, 0.0
            disk_read_iops, disk_write_iops = 0.0, 0.0
            
            if self._last_disk_io and disk_io:
                time_diff = (timestamp - self._last_disk_io['timestamp']).total_seconds()
                if time_diff > 0:
                    bytes_read_diff = disk_io.read_bytes - self._last_disk_io['read_bytes']
                    bytes_write_diff = disk_io.write_bytes - self._last_disk_io['write_bytes']
                    reads_diff = disk_io.read_count - self._last_disk_io['read_count']
                    writes_diff = disk_io.write_count - self._last_disk_io['write_count']
                    
                    disk_read_mb_per_sec = (bytes_read_diff / (1024**2)) / time_diff
                    disk_write_mb_per_sec = (bytes_write_diff / (1024**2)) / time_diff
                    disk_read_iops = reads_diff / time_diff
                    disk_write_iops = writes_diff / time_diff
            
            if disk_io:
                self._last_disk_io = {
                    'timestamp': timestamp,
                    'read_bytes': disk_io.read_bytes,
                    'write_bytes': disk_io.write_bytes,
                    'read_count': disk_io.read_count,
                    'write_count': disk_io.write_count
                }
            
            # Network metrics
            network_io = psutil.net_io_counters()
            network_bytes_sent_per_sec, network_bytes_recv_per_sec = 0.0, 0.0
            network_packets_sent_per_sec, network_packets_recv_per_sec = 0.0, 0.0
            
            if self._last_network_io and network_io:
                time_diff = (timestamp - self._last_network_io['timestamp']).total_seconds()
                if time_diff > 0:
                    bytes_sent_diff = network_io.bytes_sent - self._last_network_io['bytes_sent']
                    bytes_recv_diff = network_io.bytes_recv - self._last_network_io['bytes_recv']
                    packets_sent_diff = network_io.packets_sent - self._last_network_io['packets_sent']
                    packets_recv_diff = network_io.packets_recv - self._last_network_io['packets_recv']
                    
                    network_bytes_sent_per_sec = bytes_sent_diff / time_diff
                    network_bytes_recv_per_sec = bytes_recv_diff / time_diff
                    network_packets_sent_per_sec = packets_sent_diff / time_diff
                    network_packets_recv_per_sec = packets_recv_diff / time_diff
            
            if network_io:
                self._last_network_io = {
                    'timestamp': timestamp,
                    'bytes_sent': network_io.bytes_sent,
                    'bytes_recv': network_io.bytes_recv,
                    'packets_sent': network_io.packets_sent,
                    'packets_recv': network_io.packets_recv
                }
            
            # Process metrics
            process_cpu = self._process.cpu_percent()
            process_memory = self._process.memory_info().rss / (1024**2)  # MB
            process_threads = self._process.num_threads()
            
            try:
                process_open_files = len(self._process.open_files())
            except (psutil.AccessDenied, OSError):
                process_open_files = 0
            
            try:
                process_connections = len(self._process.connections())
            except (psutil.AccessDenied, OSError):
                process_connections = 0
            
            return SystemResourceMetrics(
                timestamp=timestamp,
                cpu_percent=cpu_percent,
                cpu_cores=cpu_cores,
                load_avg_1m=load_avg_1m,
                load_avg_5m=load_avg_5m,
                load_avg_15m=load_avg_15m,
                memory_total_gb=memory_total_gb,
                memory_available_gb=memory_available_gb,
                memory_used_gb=memory_used_gb,
                memory_percent=memory.percent,
                memory_cached_gb=memory_cached_gb,
                memory_buffers_gb=memory_buffers_gb,
                disk_total_gb=disk_total_gb,
                disk_used_gb=disk_used_gb,
                disk_free_gb=disk_free_gb,
                disk_percent=disk.percent,
                disk_read_mb_per_sec=max(0, disk_read_mb_per_sec),
                disk_write_mb_per_sec=max(0, disk_write_mb_per_sec),
                disk_read_iops=max(0, disk_read_iops),
                disk_write_iops=max(0, disk_write_iops),
                network_bytes_sent_per_sec=max(0, network_bytes_sent_per_sec),
                network_bytes_recv_per_sec=max(0, network_bytes_recv_per_sec),
                network_packets_sent_per_sec=max(0, network_packets_sent_per_sec),
                network_packets_recv_per_sec=max(0, network_packets_recv_per_sec),
                process_cpu_percent=process_cpu,
                process_memory_mb=process_memory,
                process_threads=process_threads,
                process_open_files=process_open_files,
                process_connections=process_connections
            )
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            return None
    
    async def _application_metrics_loop(self):
        """Loop de coleta de métricas de aplicação"""
        while not self._stop_collecting:
            try:
                metrics = await self._collect_application_metrics()
                
                if metrics:
                    with self._metrics_lock:
                        self._app_metrics.append(metrics)
                    
                    # Persiste no Redis
                    if self._redis_client:
                        await self._persist_application_metrics(metrics)
                
                await asyncio.sleep(self.collection_interval)
                
            except Exception as e:
                logger.error(f"Error in application metrics collection: {e}")
                await asyncio.sleep(self.collection_interval)
    
    async def _collect_application_metrics(self) -> Optional[ApplicationHealthMetrics]:
        """Coleta métricas específicas da aplicação"""
        try:
            timestamp = datetime.now()
            
            # API metrics via performance monitor
            api_stats = await api_performance_monitor.get_realtime_stats(5)  # Últimos 5 minutos
            
            api_requests_total = api_stats.get('total_requests', 0)
            api_requests_per_minute = api_stats.get('requests_per_minute', 0.0)
            api_success_rate = api_stats.get('success_rate', 100.0)
            api_error_rate = 100.0 - api_success_rate
            api_avg_response_time_ms = api_stats.get('avg_response_time_ms', 0.0)
            api_p95_response_time_ms = api_stats.get('p95_response_time_ms', 0.0)
            api_p99_response_time_ms = api_stats.get('max_response_time_ms', 0.0)  # Aproximação
            
            # Download metrics
            active_downloads = await self._count_active_operations('download')
            download_stats = await self._get_operation_stats('download')
            
            # Transcription metrics
            active_transcriptions = await self._count_active_operations('transcription')
            transcription_stats = await self._get_operation_stats('transcription')
            
            # WebSocket/SSE metrics
            active_websocket_connections = await self._count_websocket_connections()
            websocket_stats = await self._get_websocket_stats()
            
            # Cache metrics (Redis)
            cache_stats = await self._get_cache_stats()
            
            # Queue metrics
            queue_stats = await self._get_queue_stats()
            
            return ApplicationHealthMetrics(
                timestamp=timestamp,
                api_requests_total=api_requests_total,
                api_requests_per_minute=api_requests_per_minute,
                api_success_rate=api_success_rate,
                api_error_rate=api_error_rate,
                api_avg_response_time_ms=api_avg_response_time_ms,
                api_p95_response_time_ms=api_p95_response_time_ms,
                api_p99_response_time_ms=api_p99_response_time_ms,
                active_downloads=active_downloads,
                completed_downloads_today=download_stats.get('completed_today', 0),
                failed_downloads_today=download_stats.get('failed_today', 0),
                download_success_rate=download_stats.get('success_rate', 100.0),
                avg_download_speed_mbps=download_stats.get('avg_speed_mbps', 0.0),
                active_transcriptions=active_transcriptions,
                completed_transcriptions_today=transcription_stats.get('completed_today', 0),
                failed_transcriptions_today=transcription_stats.get('failed_today', 0),
                transcription_success_rate=transcription_stats.get('success_rate', 100.0),
                avg_transcription_time_sec=transcription_stats.get('avg_time_sec', 0.0),
                active_websocket_connections=active_websocket_connections,
                websocket_messages_per_minute=websocket_stats.get('messages_per_minute', 0.0),
                websocket_error_rate=websocket_stats.get('error_rate', 0.0),
                cache_hit_rate=cache_stats.get('hit_rate', 1.0),
                cache_miss_rate=cache_stats.get('miss_rate', 0.0),
                cache_operations_per_sec=cache_stats.get('operations_per_sec', 0.0),
                queue_pending_jobs=queue_stats.get('pending', 0),
                queue_processing_jobs=queue_stats.get('processing', 0),
                queue_failed_jobs_today=queue_stats.get('failed_today', 0),
                avg_queue_wait_time_sec=queue_stats.get('avg_wait_time_sec', 0.0)
            )
            
        except Exception as e:
            logger.error(f"Error collecting application metrics: {e}")
            return None
    
    async def _count_active_operations(self, operation_type: str) -> int:
        """Conta operações ativas no Redis"""
        if not self._redis_client:
            return 0
        
        try:
            pattern = f"progress:{operation_type}:*"
            keys = await self._redis_client.keys(pattern)
            return len(keys)
        except Exception:
            return 0
    
    async def _get_operation_stats(self, operation_type: str) -> Dict[str, Any]:
        """Obtém estatísticas de operações do tipo especificado"""
        if not self._redis_client:
            return {'completed_today': 0, 'failed_today': 0, 'success_rate': 100.0}
        
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Chaves de estatísticas
            completed_key = f"stats:{operation_type}:completed:{today}"
            failed_key = f"stats:{operation_type}:failed:{today}"
            
            # Conta operações
            completed_count = await self._redis_client.scard(completed_key) or 0
            failed_count = await self._redis_client.scard(failed_key) or 0
            
            total = completed_count + failed_count
            success_rate = (completed_count / total * 100) if total > 0 else 100.0
            
            # Estatísticas adicionais específicas por tipo
            extra_stats = {}
            
            if operation_type == 'download':
                # Velocidade média de download das últimas 24h
                speed_key = f"stats:download:speeds:{today}"
                speeds = await self._redis_client.lrange(speed_key, 0, -1)
                if speeds:
                    avg_speed = statistics.mean([float(s) for s in speeds])
                    extra_stats['avg_speed_mbps'] = round(avg_speed, 2)
                else:
                    extra_stats['avg_speed_mbps'] = 0.0
            
            elif operation_type == 'transcription':
                # Tempo médio de transcrição das últimas 24h
                time_key = f"stats:transcription:times:{today}"
                times = await self._redis_client.lrange(time_key, 0, -1)
                if times:
                    avg_time = statistics.mean([float(t) for t in times])
                    extra_stats['avg_time_sec'] = round(avg_time, 1)
                else:
                    extra_stats['avg_time_sec'] = 0.0
            
            return {
                'completed_today': completed_count,
                'failed_today': failed_count,
                'success_rate': round(success_rate, 1),
                **extra_stats
            }
            
        except Exception as e:
            logger.error(f"Error getting {operation_type} stats: {e}")
            return {'completed_today': 0, 'failed_today': 0, 'success_rate': 100.0}
    
    async def _count_websocket_connections(self) -> int:
        """Conta conexões WebSocket/SSE ativas"""
        if not self._redis_client:
            return 0
        
        try:
            # Conexões ativas via SSE/WebSocket
            pattern = "connection:*"
            keys = await self._redis_client.keys(pattern)
            return len(keys)
        except Exception:
            return 0
    
    async def _get_websocket_stats(self) -> Dict[str, Any]:
        """Obtém estatísticas de WebSocket/SSE"""
        if not self._redis_client:
            return {'messages_per_minute': 0.0, 'error_rate': 0.0}
        
        try:
            # Mensagens enviadas na última hora
            hour_key = f"stats:websocket:messages:{datetime.now().strftime('%Y-%m-%d-%H')}"
            messages_count = await self._redis_client.get(hour_key) or 0
            messages_per_minute = int(messages_count) / 60.0
            
            # Taxa de erro nas últimas 24h
            today = datetime.now().strftime('%Y-%m-%d')
            errors_key = f"stats:websocket:errors:{today}"
            total_key = f"stats:websocket:total:{today}"
            
            errors = int(await self._redis_client.get(errors_key) or 0)
            total = int(await self._redis_client.get(total_key) or 0)
            
            error_rate = (errors / total * 100) if total > 0 else 0.0
            
            return {
                'messages_per_minute': round(messages_per_minute, 1),
                'error_rate': round(error_rate, 1)
            }
            
        except Exception:
            return {'messages_per_minute': 0.0, 'error_rate': 0.0}
    
    async def _get_cache_stats(self) -> Dict[str, Any]:
        """Obtém estatísticas de cache (Redis)"""
        if not self._redis_client:
            return {'hit_rate': 1.0, 'miss_rate': 0.0, 'operations_per_sec': 0.0}
        
        try:
            info = await self._redis_client.info()
            
            hits = int(info.get('keyspace_hits', 0))
            misses = int(info.get('keyspace_misses', 0))
            
            total_ops = hits + misses
            hit_rate = (hits / total_ops) if total_ops > 0 else 1.0
            miss_rate = (misses / total_ops) if total_ops > 0 else 0.0
            
            ops_per_sec = int(info.get('instantaneous_ops_per_sec', 0))
            
            return {
                'hit_rate': round(hit_rate, 3),
                'miss_rate': round(miss_rate, 3),
                'operations_per_sec': float(ops_per_sec)
            }
            
        except Exception:
            return {'hit_rate': 1.0, 'miss_rate': 0.0, 'operations_per_sec': 0.0}
    
    async def _get_queue_stats(self) -> Dict[str, Any]:
        """Obtém estatísticas de filas de processamento"""
        if not self._redis_client:
            return {'pending': 0, 'processing': 0, 'failed_today': 0, 'avg_wait_time_sec': 0.0}
        
        try:
            # Jobs pendentes
            pending = await self._redis_client.llen('queue:pending') or 0
            
            # Jobs processando
            processing = await self._redis_client.llen('queue:processing') or 0
            
            # Jobs falharam hoje
            today = datetime.now().strftime('%Y-%m-%d')
            failed_key = f"stats:queue:failed:{today}"
            failed_today = await self._redis_client.scard(failed_key) or 0
            
            # Tempo médio de espera (últimas 100 amostras)
            wait_times_key = "stats:queue:wait_times"
            wait_times = await self._redis_client.lrange(wait_times_key, 0, 99)
            
            avg_wait_time_sec = 0.0
            if wait_times:
                avg_wait_time_sec = statistics.mean([float(wt) for wt in wait_times])
            
            return {
                'pending': pending,
                'processing': processing,
                'failed_today': failed_today,
                'avg_wait_time_sec': round(avg_wait_time_sec, 1)
            }
            
        except Exception:
            return {'pending': 0, 'processing': 0, 'failed_today': 0, 'avg_wait_time_sec': 0.0}
    
    async def _custom_metrics_loop(self):
        """Loop de coleta de métricas customizadas"""
        while not self._stop_collecting:
            try:
                for name, collector in self._custom_collectors.items():
                    try:
                        metric = await collector()
                        if metric:
                            with self._metrics_lock:
                                self._raw_metrics.append(metric)
                    except Exception as e:
                        logger.error(f"Error in custom collector '{name}': {e}")
                
                await asyncio.sleep(self.collection_interval)
                
            except Exception as e:
                logger.error(f"Error in custom metrics collection: {e}")
                await asyncio.sleep(self.collection_interval)
    
    async def _register_custom_collectors(self):
        """Registra coletores customizados"""
        # Coletor de métricas de file system
        self._custom_collectors['filesystem'] = self._collect_filesystem_metrics
        
        # Coletor de métricas de logs
        self._custom_collectors['logs'] = self._collect_log_metrics
        
        # Coletor de métricas de backup
        self._custom_collectors['backup'] = self._collect_backup_metrics
    
    async def _collect_filesystem_metrics(self) -> Optional[ApplicationMetric]:
        """Coleta métricas do sistema de arquivos"""
        try:
            import os
            
            # Conta arquivos nos diretórios principais
            downloads_dir = "downloads"
            backups_dir = "backups"
            logs_dir = "logs"
            
            total_files = 0
            total_size_mb = 0.0
            
            for root, dirs, files in os.walk("."):
                for file in files:
                    try:
                        filepath = os.path.join(root, file)
                        size = os.path.getsize(filepath)
                        total_files += 1
                        total_size_mb += size / (1024**2)
                    except (OSError, IOError):
                        continue
            
            return ApplicationMetric(
                timestamp=datetime.now(),
                category="filesystem",
                name="total_files_and_size",
                value=total_files,
                unit="files",
                tags={
                    "total_size_mb": str(round(total_size_mb, 2))
                }
            )
            
        except Exception as e:
            logger.error(f"Error collecting filesystem metrics: {e}")
            return None
    
    async def _collect_log_metrics(self) -> Optional[ApplicationMetric]:
        """Coleta métricas de logs"""
        try:
            import os
            
            log_errors = 0
            log_warnings = 0
            log_size_mb = 0.0
            
            logs_dir = "logs"
            if os.path.exists(logs_dir):
                for root, dirs, files in os.walk(logs_dir):
                    for file in files:
                        if file.endswith('.log'):
                            filepath = os.path.join(root, file)
                            try:
                                log_size_mb += os.path.getsize(filepath) / (1024**2)
                                
                                # Conta erros e warnings nas últimas 1000 linhas
                                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                                    lines = f.readlines()[-1000:]  # Últimas 1000 linhas
                                    for line in lines:
                                        line_lower = line.lower()
                                        if 'error' in line_lower:
                                            log_errors += 1
                                        elif 'warning' in line_lower:
                                            log_warnings += 1
                            except (OSError, IOError):
                                continue
            
            return ApplicationMetric(
                timestamp=datetime.now(),
                category="logs",
                name="log_analysis",
                value=log_errors,
                unit="errors",
                tags={
                    "warnings": str(log_warnings),
                    "total_size_mb": str(round(log_size_mb, 2))
                }
            )
            
        except Exception as e:
            logger.error(f"Error collecting log metrics: {e}")
            return None
    
    async def _collect_backup_metrics(self) -> Optional[ApplicationMetric]:
        """Coleta métricas de backup"""
        try:
            import os
            
            backup_count = 0
            backup_size_mb = 0.0
            latest_backup_age_hours = 0.0
            
            backups_dir = "backups"
            if os.path.exists(backups_dir):
                latest_backup_time = 0
                
                for root, dirs, files in os.walk(backups_dir):
                    for file in files:
                        if file.endswith(('.zip', '.tar.gz', '.json')):
                            filepath = os.path.join(root, file)
                            try:
                                stat = os.stat(filepath)
                                backup_count += 1
                                backup_size_mb += stat.st_size / (1024**2)
                                latest_backup_time = max(latest_backup_time, stat.st_mtime)
                            except OSError:
                                continue
                
                if latest_backup_time > 0:
                    latest_backup_age_hours = (time.time() - latest_backup_time) / 3600
            
            return ApplicationMetric(
                timestamp=datetime.now(),
                category="backup",
                name="backup_status",
                value=backup_count,
                unit="backups",
                tags={
                    "total_size_mb": str(round(backup_size_mb, 2)),
                    "latest_backup_age_hours": str(round(latest_backup_age_hours, 1))
                }
            )
            
        except Exception as e:
            logger.error(f"Error collecting backup metrics: {e}")
            return None
    
    async def _analysis_loop(self):
        """Loop de análise de métricas e detecção de anomalias"""
        while not self._stop_collecting:
            try:
                await asyncio.sleep(600)  # A cada 10 minutos
                await self._analyze_metrics()
                
            except Exception as e:
                logger.error(f"Error in metrics analysis: {e}")
    
    async def _analyze_metrics(self):
        """Analisa métricas para detectar anomalias e tendências"""
        with self._metrics_lock:
            if len(self._system_metrics) < 10 or len(self._app_metrics) < 10:
                return
            
            recent_system = list(self._system_metrics)[-10:]
            recent_app = list(self._app_metrics)[-10:]
        
        # Análise de sistema
        await self._analyze_system_trends(recent_system)
        
        # Análise de aplicação
        await self._analyze_application_trends(recent_app)
        
        # Correlação entre métricas
        await self._analyze_metric_correlations(recent_system, recent_app)
    
    async def _analyze_system_trends(self, metrics: List[SystemResourceMetrics]):
        """Analisa tendências de métricas de sistema"""
        # CPU trend
        cpu_values = [m.cpu_percent for m in metrics]
        cpu_trend = self._calculate_trend(cpu_values)
        
        if cpu_trend > 5.0:  # Crescimento de 5% por amostra
            logger.warning(f"CPU usage trending upward: +{cpu_trend:.1f}% per sample")
        
        # Memory trend
        memory_values = [m.memory_percent for m in metrics]
        memory_trend = self._calculate_trend(memory_values)
        
        if memory_trend > 2.0:  # Crescimento de 2% por amostra
            logger.warning(f"Memory usage trending upward: +{memory_trend:.1f}% per sample")
        
        # Disk I/O anomalies
        disk_read_values = [m.disk_read_mb_per_sec for m in metrics]
        disk_write_values = [m.disk_write_mb_per_sec for m in metrics]
        
        avg_read = statistics.mean(disk_read_values)
        avg_write = statistics.mean(disk_write_values)
        
        if avg_read > 50.0:  # > 50 MB/s sustained
            logger.warning(f"High sustained disk read activity: {avg_read:.1f} MB/s")
        
        if avg_write > 50.0:  # > 50 MB/s sustained
            logger.warning(f"High sustained disk write activity: {avg_write:.1f} MB/s")
    
    async def _analyze_application_trends(self, metrics: List[ApplicationHealthMetrics]):
        """Analisa tendências de métricas de aplicação"""
        # API error rate trend
        error_rates = [m.api_error_rate for m in metrics]
        error_trend = self._calculate_trend(error_rates)
        
        if error_trend > 1.0:  # Crescimento de 1% por amostra
            logger.warning(f"API error rate trending upward: +{error_trend:.2f}% per sample")
        
        # Response time trend
        response_times = [m.api_avg_response_time_ms for m in metrics]
        response_trend = self._calculate_trend(response_times)
        
        if response_trend > 10.0:  # Crescimento de 10ms por amostra
            logger.warning(f"API response time trending upward: +{response_trend:.1f}ms per sample")
        
        # Active operations trends
        downloads = [m.active_downloads for m in metrics]
        transcriptions = [m.active_transcriptions for m in metrics]
        
        if statistics.mean(downloads) > 50:
            logger.info(f"High download activity: avg {statistics.mean(downloads):.0f} active downloads")
        
        if statistics.mean(transcriptions) > 20:
            logger.info(f"High transcription activity: avg {statistics.mean(transcriptions):.0f} active transcriptions")
    
    async def _analyze_metric_correlations(
        self,
        system_metrics: List[SystemResourceMetrics],
        app_metrics: List[ApplicationHealthMetrics]
    ):
        """Analisa correlações entre métricas de sistema e aplicação"""
        if len(system_metrics) != len(app_metrics):
            return
        
        # Correlação CPU vs Response Time
        cpu_values = [m.cpu_percent for m in system_metrics]
        response_times = [m.api_avg_response_time_ms for m in app_metrics]
        
        cpu_response_corr = self._calculate_correlation(cpu_values, response_times)
        
        if cpu_response_corr > 0.7:  # Correlação alta
            logger.warning(
                f"High correlation between CPU usage and API response time: {cpu_response_corr:.2f}"
            )
        
        # Correlação Memory vs Cache Hit Rate
        memory_values = [m.memory_percent for m in system_metrics]
        cache_hit_rates = [m.cache_hit_rate for m in app_metrics]
        
        memory_cache_corr = self._calculate_correlation(memory_values, cache_hit_rates)
        
        if memory_cache_corr < -0.5:  # Correlação negativa moderada
            logger.warning(
                f"Negative correlation between memory usage and cache hit rate: {memory_cache_corr:.2f}"
            )
    
    def _calculate_trend(self, values: List[float]) -> float:
        """Calcula tendência usando regressão linear simples"""
        if len(values) < 2:
            return 0.0
        
        n = len(values)
        x = list(range(n))
        
        sum_x = sum(x)
        sum_y = sum(values)
        sum_xy = sum(x[i] * values[i] for i in range(n))
        sum_x2 = sum(x_val * x_val for x_val in x)
        
        denominator = n * sum_x2 - sum_x * sum_x
        if denominator == 0:
            return 0.0
        
        slope = (n * sum_xy - sum_x * sum_y) / denominator
        return slope
    
    def _calculate_correlation(self, x: List[float], y: List[float]) -> float:
        """Calcula coeficiente de correlação de Pearson"""
        if len(x) != len(y) or len(x) < 2:
            return 0.0
        
        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(x[i] * y[i] for i in range(n))
        sum_x2 = sum(x_val * x_val for x_val in x)
        sum_y2 = sum(y_val * y_val for y_val in y)
        
        numerator = n * sum_xy - sum_x * sum_y
        denominator_x = n * sum_x2 - sum_x * sum_x
        denominator_y = n * sum_y2 - sum_y * sum_y
        
        if denominator_x <= 0 or denominator_y <= 0:
            return 0.0
        
        denominator = (denominator_x * denominator_y) ** 0.5
        
        return numerator / denominator if denominator != 0 else 0.0
    
    async def _persist_system_metrics(self, metrics: SystemResourceMetrics):
        """Persiste métricas de sistema no Redis"""
        if not self._redis_client:
            return
        
        try:
            key = f"metrics:system:{metrics.timestamp.strftime('%Y-%m-%d-%H')}"
            data = metrics.to_dict()
            
            await self._redis_client.lpush(key, json.dumps(data))
            await self._redis_client.ltrim(key, 0, 119)  # Mantém 2h de dados por hora
            await self._redis_client.expire(key, 7 * 24 * 3600)  # 7 dias
            
        except Exception as e:
            logger.error(f"Error persisting system metrics: {e}")
    
    async def _persist_application_metrics(self, metrics: ApplicationHealthMetrics):
        """Persiste métricas de aplicação no Redis"""
        if not self._redis_client:
            return
        
        try:
            key = f"metrics:application:{metrics.timestamp.strftime('%Y-%m-%d-%H')}"
            data = metrics.to_dict()
            
            await self._redis_client.lpush(key, json.dumps(data))
            await self._redis_client.ltrim(key, 0, 119)  # Mantém 2h de dados por hora
            await self._redis_client.expire(key, 7 * 24 * 3600)  # 7 dias
            
        except Exception as e:
            logger.error(f"Error persisting application metrics: {e}")
    
    # Métodos públicos para consultas
    
    async def get_current_metrics(self) -> Dict[str, Any]:
        """Obtém métricas atuais"""
        with self._metrics_lock:
            if not self._system_metrics or not self._app_metrics:
                return {"status": "no_data"}
            
            latest_system = self._system_metrics[-1]
            latest_app = self._app_metrics[-1]
        
        return {
            "timestamp": datetime.now().isoformat(),
            "system": latest_system.to_dict(),
            "application": latest_app.to_dict(),
            "is_collecting": self.is_collecting,
            "collection_duration": self._get_collection_duration()
        }
    
    async def get_metrics_summary(self, hours: int = 6) -> Dict[str, Any]:
        """Obtém resumo de métricas do período especificado"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with self._metrics_lock:
            period_system = [m for m in self._system_metrics if m.timestamp >= cutoff_time]
            period_app = [m for m in self._app_metrics if m.timestamp >= cutoff_time]
        
        if not period_system or not period_app:
            return {"error": f"No data available for last {hours} hours"}
        
        # System summary
        cpu_values = [m.cpu_percent for m in period_system]
        memory_values = [m.memory_percent for m in period_system]
        disk_values = [m.disk_percent for m in period_system]
        
        # Application summary
        api_response_times = [m.api_avg_response_time_ms for m in period_app]
        api_success_rates = [m.api_success_rate for m in period_app]
        active_downloads = [m.active_downloads for m in period_app]
        
        return {
            "period_hours": hours,
            "timestamp": datetime.now().isoformat(),
            "data_points": len(period_system),
            "system_summary": {
                "cpu": {
                    "avg": round(statistics.mean(cpu_values), 1),
                    "max": round(max(cpu_values), 1),
                    "current": round(cpu_values[-1], 1)
                },
                "memory": {
                    "avg": round(statistics.mean(memory_values), 1),
                    "max": round(max(memory_values), 1),
                    "current": round(memory_values[-1], 1)
                },
                "disk": {
                    "avg": round(statistics.mean(disk_values), 1),
                    "max": round(max(disk_values), 1),
                    "current": round(disk_values[-1], 1)
                }
            },
            "application_summary": {
                "api_performance": {
                    "avg_response_time_ms": round(statistics.mean(api_response_times), 1),
                    "max_response_time_ms": round(max(api_response_times), 1),
                    "avg_success_rate": round(statistics.mean(api_success_rates), 1),
                    "min_success_rate": round(min(api_success_rates), 1)
                },
                "activity": {
                    "avg_downloads": round(statistics.mean(active_downloads), 0),
                    "max_downloads": max(active_downloads),
                    "current_downloads": active_downloads[-1]
                }
            }
        }
    
    def _get_collection_duration(self) -> str:
        """Retorna duração da coleta"""
        if not self._system_metrics:
            return "0 minutes"
        
        start_time = self._system_metrics[0].timestamp
        duration = datetime.now() - start_time
        
        hours = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)
        
        return f"{hours}h {minutes}m"


# Instância global do coletor de métricas
application_metrics_collector = ApplicationMetricsCollector()