"""
Production Monitoring System - FASE 4 Implementation
Sistema de monitoramento intensivo pós-cutover para Redis Migration

Agent-Infrastructure - Production Monitoring Intensivo 48h Pós-Cutover
"""

import asyncio
import json
import time
import psutil
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from threading import Lock
import statistics

from loguru import logger

from app.services.redis_connection import get_redis_client
from app.services.api_performance_monitor import api_performance_monitor


@dataclass
class ProductionAlert:
    """Alert gerado pelo sistema de monitoramento"""
    id: str
    type: str  # critical, warning, info
    category: str  # redis, application, system, performance
    title: str
    message: str
    value: float
    threshold: float
    timestamp: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False
    resolved: bool = False
    severity: str = "medium"  # low, medium, high, critical
    
    @property
    def age_minutes(self) -> float:
        return (datetime.now() - self.timestamp).total_seconds() / 60
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['age_minutes'] = self.age_minutes
        return data


@dataclass
class SystemHealthMetrics:
    """Métricas de saúde do sistema"""
    timestamp: datetime
    
    # Redis Metrics
    redis_memory_used_mb: float
    redis_memory_used_percent: float
    redis_hit_rate: float
    redis_connected_clients: int
    redis_ops_per_sec: int
    redis_avg_latency_ms: float
    redis_slow_queries: int
    redis_evicted_keys: int
    
    # Application Metrics
    api_requests_per_minute: float
    api_success_rate: float
    api_avg_response_time_ms: float
    api_p95_response_time_ms: float
    api_error_rate: float
    active_downloads: int
    active_transcriptions: int
    websocket_connections: int
    
    # System Metrics
    cpu_usage_percent: float
    memory_usage_percent: float
    disk_usage_percent: float
    network_io_mbps: float
    process_memory_mb: float
    thread_count: int
    
    health_score: float = 0.0
    status: str = "unknown"  # excellent, good, fair, poor, critical
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class ProductionMonitoring:
    """
    Sistema de monitoramento de produção intensivo pós-cutover
    
    Funcionalidades:
    - Monitoramento Redis em tempo real
    - Métricas de aplicação e sistema
    - Sistema de alertas automático
    - Dashboard em tempo real
    - Otimização automática
    - Relatórios de saúde
    """
    
    def __init__(self, monitoring_interval: int = 30):
        self.monitoring_interval = monitoring_interval
        self.is_monitoring = False
        self._stop_monitoring = False
        
        # Storage
        self._metrics_buffer: deque[SystemHealthMetrics] = deque(maxlen=2880)  # 24h de dados (30s interval)
        self._active_alerts: Dict[str, ProductionAlert] = {}
        self._alert_history: deque[ProductionAlert] = deque(maxlen=10000)
        
        # Thresholds para alertas críticos pós-cutover
        self.alert_thresholds = {
            'redis': {
                'memory_usage_critical': 0.95,    # 95% memory
                'memory_usage_warning': 0.85,     # 85% memory
                'hit_rate_critical': 0.85,        # 85% hit rate
                'hit_rate_warning': 0.90,         # 90% hit rate
                'latency_critical_ms': 100.0,     # 100ms
                'latency_warning_ms': 50.0,       # 50ms
                'slow_queries_critical': 50,      # 50 slow queries
                'slow_queries_warning': 20,       # 20 slow queries
                'connection_critical': 8000,      # 8000 connections
                'connection_warning': 6000,       # 6000 connections
                'evicted_keys_critical': 1000,    # 1000 evicted keys/min
                'evicted_keys_warning': 500       # 500 evicted keys/min
            },
            'application': {
                'api_error_rate_critical': 0.05,  # 5% error rate
                'api_error_rate_warning': 0.02,   # 2% error rate
                'response_time_critical_ms': 2000.0,  # 2s response time
                'response_time_warning_ms': 1000.0,   # 1s response time
                'success_rate_critical': 0.90,    # 90% success rate
                'success_rate_warning': 0.95      # 95% success rate
            },
            'system': {
                'cpu_critical': 0.90,             # 90% CPU
                'cpu_warning': 0.80,              # 80% CPU
                'memory_critical': 0.90,          # 90% memory
                'memory_warning': 0.80,           # 80% memory
                'disk_critical': 0.95,            # 95% disk
                'disk_warning': 0.85              # 85% disk
            }
        }
        
        # Configurações de otimização
        self.optimization_config = {
            'redis_auto_optimize': True,
            'max_memory_policy': 'allkeys-lru',
            'tcp_keepalive': 60,
            'save_policy': '900 1 300 10 60 10000',
            'max_clients': 10000,
            'timeout': 300
        }
        
        # Locks para thread safety
        self._metrics_lock = Lock()
        self._alerts_lock = Lock()
        
        # Redis client
        self._redis_client = None
        
        logger.info(f"ProductionMonitoring initialized (interval: {monitoring_interval}s)")
    
    async def initialize(self) -> bool:
        """Inicializa o sistema de monitoramento"""
        try:
            # Conecta ao Redis
            self._redis_client = await get_redis_client()
            if not self._redis_client:
                logger.error("Failed to connect to Redis - monitoring will be limited")
                return False
            
            # Inicializa monitor de performance da API
            await api_performance_monitor.initialize_redis()
            
            logger.info("Production monitoring system initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize production monitoring: {e}")
            return False
    
    async def start_monitoring(self):
        """Inicia o monitoramento intensivo"""
        if self.is_monitoring:
            logger.warning("Monitoring already running")
            return
        
        if not await self.initialize():
            logger.error("Cannot start monitoring - initialization failed")
            return
        
        self.is_monitoring = True
        self._stop_monitoring = False
        
        logger.info("Starting intensive production monitoring (48h post-cutover)")
        
        # Task principal de monitoramento
        monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        # Task de análise de tendências
        trend_task = asyncio.create_task(self._trend_analysis_loop())
        
        # Task de otimização automática
        optimization_task = asyncio.create_task(self._optimization_loop())
        
        # Task de limpeza de alertas
        cleanup_task = asyncio.create_task(self._alert_cleanup_loop())
        
        try:
            await asyncio.gather(
                monitoring_task,
                trend_task,
                optimization_task,
                cleanup_task
            )
        except Exception as e:
            logger.error(f"Error in monitoring tasks: {e}")
        finally:
            self.is_monitoring = False
            logger.info("Production monitoring stopped")
    
    async def stop_monitoring(self):
        """Para o monitoramento"""
        self._stop_monitoring = True
        self.is_monitoring = False
        logger.info("Stopping production monitoring...")
    
    async def _monitoring_loop(self):
        """Loop principal de coleta de métricas"""
        while not self._stop_monitoring:
            try:
                # Coleta métricas
                metrics = await self._collect_system_metrics()
                
                # Armazena métricas
                with self._metrics_lock:
                    self._metrics_buffer.append(metrics)
                
                # Verifica alertas
                await self._check_alerts(metrics)
                
                # Persiste no Redis para dashboard
                if self._redis_client:
                    await self._persist_metrics(metrics)
                
                # Log de status a cada 5 minutos
                if len(self._metrics_buffer) % 10 == 0:  # 5 min / 30s = 10 intervals
                    await self._log_health_summary(metrics)
                
                await asyncio.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.monitoring_interval)
    
    async def _collect_system_metrics(self) -> SystemHealthMetrics:
        """Coleta todas as métricas do sistema"""
        timestamp = datetime.now()
        
        # Redis metrics
        redis_info = await self._get_redis_info()
        
        # API metrics
        api_stats = await api_performance_monitor.get_realtime_stats(5)  # Últimos 5 minutos
        
        # System metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        network = psutil.net_io_counters()
        process = psutil.Process()
        
        # Calcula network I/O rate (MB/s)
        if hasattr(self, '_last_network_bytes'):
            bytes_diff = (network.bytes_sent + network.bytes_recv) - self._last_network_bytes
            time_diff = (timestamp - self._last_network_time).total_seconds()
            network_io_mbps = (bytes_diff / 1024 / 1024) / time_diff if time_diff > 0 else 0.0
        else:
            network_io_mbps = 0.0
        
        self._last_network_bytes = network.bytes_sent + network.bytes_recv
        self._last_network_time = timestamp
        
        # Cria métricas
        metrics = SystemHealthMetrics(
            timestamp=timestamp,
            
            # Redis metrics
            redis_memory_used_mb=redis_info.get('memory_used_mb', 0.0),
            redis_memory_used_percent=redis_info.get('memory_used_percent', 0.0),
            redis_hit_rate=redis_info.get('hit_rate', 1.0),
            redis_connected_clients=redis_info.get('connected_clients', 0),
            redis_ops_per_sec=redis_info.get('ops_per_sec', 0),
            redis_avg_latency_ms=redis_info.get('avg_latency_ms', 0.0),
            redis_slow_queries=redis_info.get('slow_queries', 0),
            redis_evicted_keys=redis_info.get('evicted_keys', 0),
            
            # API metrics
            api_requests_per_minute=api_stats.get('requests_per_minute', 0.0) if 'requests_per_minute' in api_stats else 0.0,
            api_success_rate=api_stats.get('success_rate', 100.0) if 'success_rate' in api_stats else 100.0,
            api_avg_response_time_ms=api_stats.get('avg_response_time_ms', 0.0) if 'avg_response_time_ms' in api_stats else 0.0,
            api_p95_response_time_ms=api_stats.get('p95_response_time_ms', 0.0) if 'p95_response_time_ms' in api_stats else 0.0,
            api_error_rate=(100.0 - api_stats.get('success_rate', 100.0)) / 100.0 if 'success_rate' in api_stats else 0.0,
            active_downloads=await self._get_active_downloads(),
            active_transcriptions=await self._get_active_transcriptions(),
            websocket_connections=await self._get_websocket_connections(),
            
            # System metrics
            cpu_usage_percent=cpu_percent,
            memory_usage_percent=memory.percent,
            disk_usage_percent=disk.percent,
            network_io_mbps=network_io_mbps,
            process_memory_mb=process.memory_info().rss / 1024 / 1024,
            thread_count=process.num_threads()
        )
        
        # Calcula health score
        metrics.health_score = self._calculate_health_score(metrics)
        metrics.status = self._get_health_status(metrics.health_score)
        
        return metrics
    
    async def _get_redis_info(self) -> Dict[str, Any]:
        """Coleta informações do Redis"""
        if not self._redis_client:
            return {}
        
        try:
            # Info básico
            info = await self._redis_client.info()
            
            # Teste de latência
            start_time = time.time()
            await self._redis_client.ping()
            latency_ms = (time.time() - start_time) * 1000
            
            # Calcula hit rate
            hits = int(info.get('keyspace_hits', 0))
            misses = int(info.get('keyspace_misses', 0))
            hit_rate = hits / (hits + misses) if (hits + misses) > 0 else 1.0
            
            # Memory usage
            used_memory = int(info.get('used_memory', 0))
            max_memory = int(info.get('maxmemory', 0))
            memory_percent = (used_memory / max_memory * 100) if max_memory > 0 else 0.0
            
            return {
                'memory_used_mb': used_memory / 1024 / 1024,
                'memory_used_percent': memory_percent / 100.0,
                'hit_rate': hit_rate,
                'connected_clients': int(info.get('connected_clients', 0)),
                'ops_per_sec': int(info.get('instantaneous_ops_per_sec', 0)),
                'avg_latency_ms': latency_ms,
                'slow_queries': int(info.get('slowlog_len', 0)),
                'evicted_keys': int(info.get('evicted_keys', 0))
            }
            
        except Exception as e:
            logger.error(f"Error collecting Redis info: {e}")
            return {}
    
    async def _get_active_downloads(self) -> int:
        """Obtém número de downloads ativos"""
        if not self._redis_client:
            return 0
        
        try:
            # Conta keys de progresso ativo
            keys = await self._redis_client.keys("progress:download:*")
            return len(keys)
        except Exception:
            return 0
    
    async def _get_active_transcriptions(self) -> int:
        """Obtém número de transcrições ativas"""
        if not self._redis_client:
            return 0
        
        try:
            # Conta keys de transcrição ativa
            keys = await self._redis_client.keys("progress:transcription:*")
            return len(keys)
        except Exception:
            return 0
    
    async def _get_websocket_connections(self) -> int:
        """Obtém número de conexões WebSocket ativas"""
        if not self._redis_client:
            return 0
        
        try:
            # Conta conexões ativas via SSE/WebSocket
            keys = await self._redis_client.keys("connection:*")
            return len(keys)
        except Exception:
            return 0
    
    def _calculate_health_score(self, metrics: SystemHealthMetrics) -> float:
        """Calcula score de saúde do sistema (0-100)"""
        score = 100.0
        factors = []
        
        # Redis health (peso 40%)
        redis_score = 40.0
        
        # Memory usage
        if metrics.redis_memory_used_percent > 0.95:
            redis_score -= 15
        elif metrics.redis_memory_used_percent > 0.85:
            redis_score -= 8
        elif metrics.redis_memory_used_percent > 0.75:
            redis_score -= 3
        
        # Hit rate
        if metrics.redis_hit_rate < 0.85:
            redis_score -= 15
        elif metrics.redis_hit_rate < 0.90:
            redis_score -= 8
        elif metrics.redis_hit_rate < 0.95:
            redis_score -= 3
        
        # Latency
        if metrics.redis_avg_latency_ms > 100:
            redis_score -= 10
        elif metrics.redis_avg_latency_ms > 50:
            redis_score -= 5
        elif metrics.redis_avg_latency_ms > 20:
            redis_score -= 2
        
        factors.append(max(0, redis_score))
        
        # API health (peso 30%)
        api_score = 30.0
        
        # Success rate
        if metrics.api_success_rate < 90:
            api_score -= 15
        elif metrics.api_success_rate < 95:
            api_score -= 8
        elif metrics.api_success_rate < 98:
            api_score -= 3
        
        # Response time
        if metrics.api_avg_response_time_ms > 2000:
            api_score -= 15
        elif metrics.api_avg_response_time_ms > 1000:
            api_score -= 8
        elif metrics.api_avg_response_time_ms > 500:
            api_score -= 3
        
        factors.append(max(0, api_score))
        
        # System health (peso 30%)
        system_score = 30.0
        
        # CPU usage
        if metrics.cpu_usage_percent > 90:
            system_score -= 10
        elif metrics.cpu_usage_percent > 80:
            system_score -= 5
        elif metrics.cpu_usage_percent > 70:
            system_score -= 2
        
        # Memory usage
        if metrics.memory_usage_percent > 90:
            system_score -= 10
        elif metrics.memory_usage_percent > 80:
            system_score -= 5
        elif metrics.memory_usage_percent > 70:
            system_score -= 2
        
        # Disk usage
        if metrics.disk_usage_percent > 95:
            system_score -= 10
        elif metrics.disk_usage_percent > 85:
            system_score -= 5
        elif metrics.disk_usage_percent > 75:
            system_score -= 2
        
        factors.append(max(0, system_score))
        
        return sum(factors)
    
    def _get_health_status(self, score: float) -> str:
        """Retorna status baseado no score"""
        if score >= 95:
            return "excellent"
        elif score >= 85:
            return "good"
        elif score >= 70:
            return "fair"
        elif score >= 50:
            return "poor"
        else:
            return "critical"
    
    async def _check_alerts(self, metrics: SystemHealthMetrics):
        """Verifica e gera alertas baseados nas métricas"""
        alerts_to_create = []
        
        # Redis alerts
        redis_thresholds = self.alert_thresholds['redis']
        
        # Memory usage alert
        if metrics.redis_memory_used_percent >= redis_thresholds['memory_usage_critical']:
            alerts_to_create.append(self._create_alert(
                "redis_memory_critical",
                "critical",
                "redis",
                "Redis Memory Critical",
                f"Redis memory usage is {metrics.redis_memory_used_percent:.1%} (critical threshold: {redis_thresholds['memory_usage_critical']:.1%})",
                metrics.redis_memory_used_percent,
                redis_thresholds['memory_usage_critical'],
                "critical"
            ))
        elif metrics.redis_memory_used_percent >= redis_thresholds['memory_usage_warning']:
            alerts_to_create.append(self._create_alert(
                "redis_memory_warning",
                "warning",
                "redis",
                "Redis Memory Warning",
                f"Redis memory usage is {metrics.redis_memory_used_percent:.1%} (warning threshold: {redis_thresholds['memory_usage_warning']:.1%})",
                metrics.redis_memory_used_percent,
                redis_thresholds['memory_usage_warning'],
                "high"
            ))
        
        # Hit rate alert
        if metrics.redis_hit_rate <= redis_thresholds['hit_rate_critical']:
            alerts_to_create.append(self._create_alert(
                "redis_hitrate_critical",
                "critical",
                "redis",
                "Redis Hit Rate Critical",
                f"Redis hit rate is {metrics.redis_hit_rate:.1%} (critical threshold: {redis_thresholds['hit_rate_critical']:.1%})",
                metrics.redis_hit_rate,
                redis_thresholds['hit_rate_critical'],
                "critical"
            ))
        elif metrics.redis_hit_rate <= redis_thresholds['hit_rate_warning']:
            alerts_to_create.append(self._create_alert(
                "redis_hitrate_warning",
                "warning",
                "redis",
                "Redis Hit Rate Warning",
                f"Redis hit rate is {metrics.redis_hit_rate:.1%} (warning threshold: {redis_thresholds['hit_rate_warning']:.1%})",
                metrics.redis_hit_rate,
                redis_thresholds['hit_rate_warning'],
                "high"
            ))
        
        # Latency alert
        if metrics.redis_avg_latency_ms >= redis_thresholds['latency_critical_ms']:
            alerts_to_create.append(self._create_alert(
                "redis_latency_critical",
                "critical",
                "redis",
                "Redis Latency Critical",
                f"Redis average latency is {metrics.redis_avg_latency_ms:.2f}ms (critical threshold: {redis_thresholds['latency_critical_ms']}ms)",
                metrics.redis_avg_latency_ms,
                redis_thresholds['latency_critical_ms'],
                "critical"
            ))
        elif metrics.redis_avg_latency_ms >= redis_thresholds['latency_warning_ms']:
            alerts_to_create.append(self._create_alert(
                "redis_latency_warning",
                "warning",
                "redis",
                "Redis Latency Warning",
                f"Redis average latency is {metrics.redis_avg_latency_ms:.2f}ms (warning threshold: {redis_thresholds['latency_warning_ms']}ms)",
                metrics.redis_avg_latency_ms,
                redis_thresholds['latency_warning_ms'],
                "high"
            ))
        
        # API alerts
        app_thresholds = self.alert_thresholds['application']
        
        # API error rate alert
        if metrics.api_error_rate >= app_thresholds['api_error_rate_critical']:
            alerts_to_create.append(self._create_alert(
                "api_error_critical",
                "critical",
                "application",
                "API Error Rate Critical",
                f"API error rate is {metrics.api_error_rate:.1%} (critical threshold: {app_thresholds['api_error_rate_critical']:.1%})",
                metrics.api_error_rate,
                app_thresholds['api_error_rate_critical'],
                "critical"
            ))
        elif metrics.api_error_rate >= app_thresholds['api_error_rate_warning']:
            alerts_to_create.append(self._create_alert(
                "api_error_warning",
                "warning",
                "application",
                "API Error Rate Warning",
                f"API error rate is {metrics.api_error_rate:.1%} (warning threshold: {app_thresholds['api_error_rate_warning']:.1%})",
                metrics.api_error_rate,
                app_thresholds['api_error_rate_warning'],
                "high"
            ))
        
        # API response time alert
        if metrics.api_avg_response_time_ms >= app_thresholds['response_time_critical_ms']:
            alerts_to_create.append(self._create_alert(
                "api_response_critical",
                "critical",
                "application",
                "API Response Time Critical",
                f"API response time is {metrics.api_avg_response_time_ms:.2f}ms (critical threshold: {app_thresholds['response_time_critical_ms']}ms)",
                metrics.api_avg_response_time_ms,
                app_thresholds['response_time_critical_ms'],
                "critical"
            ))
        elif metrics.api_avg_response_time_ms >= app_thresholds['response_time_warning_ms']:
            alerts_to_create.append(self._create_alert(
                "api_response_warning",
                "warning",
                "application",
                "API Response Time Warning",
                f"API response time is {metrics.api_avg_response_time_ms:.2f}ms (warning threshold: {app_thresholds['response_time_warning_ms']}ms)",
                metrics.api_avg_response_time_ms,
                app_thresholds['response_time_warning_ms'],
                "high"
            ))
        
        # System alerts
        system_thresholds = self.alert_thresholds['system']
        
        # CPU usage alert
        if metrics.cpu_usage_percent >= system_thresholds['cpu_critical']:
            alerts_to_create.append(self._create_alert(
                "system_cpu_critical",
                "critical",
                "system",
                "System CPU Critical",
                f"CPU usage is {metrics.cpu_usage_percent:.1f}% (critical threshold: {system_thresholds['cpu_critical']:.1%})",
                metrics.cpu_usage_percent / 100,
                system_thresholds['cpu_critical'],
                "critical"
            ))
        elif metrics.cpu_usage_percent >= system_thresholds['cpu_warning']:
            alerts_to_create.append(self._create_alert(
                "system_cpu_warning",
                "warning",
                "system",
                "System CPU Warning",
                f"CPU usage is {metrics.cpu_usage_percent:.1f}% (warning threshold: {system_thresholds['cpu_warning']:.1%})",
                metrics.cpu_usage_percent / 100,
                system_thresholds['cpu_warning'],
                "high"
            ))
        
        # Cria alertas
        with self._alerts_lock:
            for alert in alerts_to_create:
                if alert.id not in self._active_alerts:
                    self._active_alerts[alert.id] = alert
                    self._alert_history.append(alert)
                    logger.warning(f"ALERT CREATED: {alert.title} - {alert.message}")
                    
                    # Persiste alerta no Redis para dashboard
                    if self._redis_client:
                        await self._persist_alert(alert)
    
    def _create_alert(
        self,
        alert_id: str,
        alert_type: str,
        category: str,
        title: str,
        message: str,
        value: float,
        threshold: float,
        severity: str
    ) -> ProductionAlert:
        """Cria um novo alerta"""
        return ProductionAlert(
            id=alert_id,
            type=alert_type,
            category=category,
            title=title,
            message=message,
            value=value,
            threshold=threshold,
            severity=severity
        )
    
    async def _persist_metrics(self, metrics: SystemHealthMetrics):
        """Persiste métricas no Redis para dashboard"""
        if not self._redis_client:
            return
        
        try:
            # Key para métricas em tempo real
            key = "production:monitoring:current"
            
            # Serializa métricas
            data = metrics.to_dict()
            
            # Armazena
            await self._redis_client.setex(key, 300, json.dumps(data))  # TTL 5 minutos
            
            # Armazena histórico diário
            date_key = f"production:monitoring:history:{metrics.timestamp.strftime('%Y-%m-%d')}"
            await self._redis_client.lpush(date_key, json.dumps(data))
            await self._redis_client.ltrim(date_key, 0, 2879)  # Mantém 24h (30s * 2880 = 24h)
            await self._redis_client.expire(date_key, 7 * 24 * 3600)  # 7 dias de retenção
            
        except Exception as e:
            logger.error(f"Error persisting metrics: {e}")
    
    async def _persist_alert(self, alert: ProductionAlert):
        """Persiste alerta no Redis para dashboard"""
        if not self._redis_client:
            return
        
        try:
            # Key para alertas ativos
            active_key = "production:monitoring:alerts:active"
            
            # Key para histórico de alertas
            history_key = f"production:monitoring:alerts:history:{alert.timestamp.strftime('%Y-%m-%d')}"
            
            # Serializa alerta
            data = alert.to_dict()
            
            # Adiciona aos alertas ativos
            await self._redis_client.hset(active_key, alert.id, json.dumps(data))
            await self._redis_client.expire(active_key, 24 * 3600)  # TTL 24h
            
            # Adiciona ao histórico
            await self._redis_client.lpush(history_key, json.dumps(data))
            await self._redis_client.ltrim(history_key, 0, 999)  # Mantém últimos 1000
            await self._redis_client.expire(history_key, 30 * 24 * 3600)  # 30 dias
            
        except Exception as e:
            logger.error(f"Error persisting alert: {e}")
    
    async def _log_health_summary(self, metrics: SystemHealthMetrics):
        """Log resumo de saúde do sistema"""
        logger.info(
            f"HEALTH SUMMARY - Score: {metrics.health_score:.1f} ({metrics.status.upper()}) | "
            f"Redis: {metrics.redis_memory_used_percent:.1%} mem, {metrics.redis_hit_rate:.1%} hit | "
            f"API: {metrics.api_success_rate:.1f}% success, {metrics.api_avg_response_time_ms:.1f}ms avg | "
            f"System: {metrics.cpu_usage_percent:.1f}% CPU, {metrics.memory_usage_percent:.1f}% mem | "
            f"Active: {metrics.active_downloads} downloads, {metrics.active_transcriptions} transcriptions"
        )
    
    async def _trend_analysis_loop(self):
        """Loop de análise de tendências (executa a cada 10 minutos)"""
        while not self._stop_monitoring:
            try:
                await asyncio.sleep(600)  # 10 minutos
                
                if len(self._metrics_buffer) >= 20:  # Pelo menos 10 minutos de dados
                    await self._analyze_trends()
                    
            except Exception as e:
                logger.error(f"Error in trend analysis: {e}")
    
    async def _analyze_trends(self):
        """Analisa tendências nas métricas"""
        with self._metrics_lock:
            recent_metrics = list(self._metrics_buffer)[-20:]  # Últimos 10 minutos
        
        if len(recent_metrics) < 20:
            return
        
        # Analisa tendências de memory usage
        memory_trend = [m.redis_memory_used_percent for m in recent_metrics]
        memory_slope = self._calculate_trend_slope(memory_trend)
        
        # Se memory usage crescendo rapidamente, alerta
        if memory_slope > 0.01:  # 1% por minuto
            logger.warning(
                f"TREND ALERT: Redis memory usage increasing rapidly "
                f"(+{memory_slope*100:.2f}% per minute)"
            )
        
        # Analisa tendências de hit rate
        hitrate_trend = [m.redis_hit_rate for m in recent_metrics]
        hitrate_slope = self._calculate_trend_slope(hitrate_trend)
        
        # Se hit rate diminuindo rapidamente, alerta
        if hitrate_slope < -0.01:  # -1% por minuto
            logger.warning(
                f"TREND ALERT: Redis hit rate decreasing rapidly "
                f"({hitrate_slope*100:.2f}% per minute)"
            )
    
    def _calculate_trend_slope(self, values: List[float]) -> float:
        """Calcula a inclinação da tendência usando regressão linear simples"""
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
    
    async def _optimization_loop(self):
        """Loop de otimização automática (executa a cada 30 minutos)"""
        while not self._stop_monitoring:
            try:
                await asyncio.sleep(1800)  # 30 minutos
                
                if self.optimization_config['redis_auto_optimize']:
                    await self._optimize_redis_performance()
                    
            except Exception as e:
                logger.error(f"Error in optimization loop: {e}")
    
    async def _optimize_redis_performance(self):
        """Otimização automática do Redis baseada nas métricas"""
        if not self._redis_client:
            return
        
        try:
            with self._metrics_lock:
                if not self._metrics_buffer:
                    return
                latest = self._metrics_buffer[-1]
            
            optimizations_applied = []
            
            # Se memory usage alto, ajusta policy
            if latest.redis_memory_used_percent > 0.80:
                try:
                    await self._redis_client.config_set(
                        'maxmemory-policy',
                        self.optimization_config['max_memory_policy']
                    )
                    optimizations_applied.append("Updated maxmemory-policy to allkeys-lru")
                except Exception as e:
                    logger.warning(f"Failed to set maxmemory-policy: {e}")
            
            # Se muitas conexões, ajusta timeout
            if latest.redis_connected_clients > 5000:
                try:
                    await self._redis_client.config_set(
                        'timeout',
                        self.optimization_config['timeout']
                    )
                    optimizations_applied.append("Adjusted connection timeout")
                except Exception as e:
                    logger.warning(f"Failed to set timeout: {e}")
            
            # Se hit rate baixo, força save para otimizar persistence
            if latest.redis_hit_rate < 0.90:
                try:
                    await self._redis_client.config_set(
                        'save',
                        self.optimization_config['save_policy']
                    )
                    optimizations_applied.append("Updated save policy")
                except Exception as e:
                    logger.warning(f"Failed to set save policy: {e}")
            
            if optimizations_applied:
                logger.info(f"AUTO-OPTIMIZATION: Applied {len(optimizations_applied)} optimizations: {', '.join(optimizations_applied)}")
        
        except Exception as e:
            logger.error(f"Error in Redis optimization: {e}")
    
    async def _alert_cleanup_loop(self):
        """Loop de limpeza de alertas (executa a cada hora)"""
        while not self._stop_monitoring:
            try:
                await asyncio.sleep(3600)  # 1 hora
                await self._cleanup_resolved_alerts()
                
            except Exception as e:
                logger.error(f"Error in alert cleanup: {e}")
    
    async def _cleanup_resolved_alerts(self):
        """Remove alertas resolvidos automaticamente"""
        with self._alerts_lock:
            resolved_alerts = []
            
            for alert_id, alert in list(self._active_alerts.items()):
                # Auto-resolve alertas antigos (mais de 30 minutos)
                if alert.age_minutes > 30:
                    # Verifica se condição ainda existe
                    if await self._is_alert_condition_resolved(alert):
                        alert.resolved = True
                        resolved_alerts.append(alert_id)
            
            # Remove alertas resolvidos
            for alert_id in resolved_alerts:
                del self._active_alerts[alert_id]
                logger.info(f"AUTO-RESOLVED: Alert {alert_id} was automatically resolved")
                
                # Remove do Redis
                if self._redis_client:
                    try:
                        await self._redis_client.hdel("production:monitoring:alerts:active", alert_id)
                    except Exception:
                        pass
    
    async def _is_alert_condition_resolved(self, alert: ProductionAlert) -> bool:
        """Verifica se a condição do alerta foi resolvida"""
        try:
            with self._metrics_lock:
                if not self._metrics_buffer:
                    return False
                latest = self._metrics_buffer[-1]
            
            # Verifica condições baseadas no tipo de alerta
            if alert.id.startswith('redis_memory'):
                return latest.redis_memory_used_percent < alert.threshold
            elif alert.id.startswith('redis_hitrate'):
                return latest.redis_hit_rate > alert.threshold
            elif alert.id.startswith('redis_latency'):
                return latest.redis_avg_latency_ms < alert.threshold
            elif alert.id.startswith('api_error'):
                return latest.api_error_rate < alert.threshold
            elif alert.id.startswith('api_response'):
                return latest.api_avg_response_time_ms < alert.threshold
            elif alert.id.startswith('system_cpu'):
                return (latest.cpu_usage_percent / 100) < alert.threshold
            elif alert.id.startswith('system_memory'):
                return (latest.memory_usage_percent / 100) < alert.threshold
            
            return False
            
        except Exception:
            return False
    
    # Métodos públicos para dashboard e relatórios
    
    async def get_current_status(self) -> Dict[str, Any]:
        """Obtém status atual do sistema"""
        with self._metrics_lock:
            if not self._metrics_buffer:
                return {"status": "no_data"}
            
            latest = self._metrics_buffer[-1]
        
        with self._alerts_lock:
            active_alerts = [alert.to_dict() for alert in self._active_alerts.values()]
        
        return {
            "timestamp": latest.timestamp.isoformat(),
            "health_score": latest.health_score,
            "status": latest.status,
            "metrics": latest.to_dict(),
            "active_alerts": active_alerts,
            "alert_count": len(active_alerts),
            "monitoring_duration": self._get_monitoring_duration(),
            "is_monitoring": self.is_monitoring
        }
    
    async def get_health_report(self, hours: int = 24) -> Dict[str, Any]:
        """Gera relatório de saúde detalhado"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        with self._metrics_lock:
            period_metrics = [
                m for m in self._metrics_buffer
                if m.timestamp >= cutoff_time
            ]
        
        if not period_metrics:
            return {"error": f"No data available for last {hours} hours"}
        
        # Estatísticas do período
        health_scores = [m.health_score for m in period_metrics]
        redis_memory = [m.redis_memory_used_percent for m in period_metrics]
        redis_hitrate = [m.redis_hit_rate for m in period_metrics]
        api_response_times = [m.api_avg_response_time_ms for m in period_metrics]
        cpu_usage = [m.cpu_usage_percent for m in period_metrics]
        
        # Alertas do período
        with self._alerts_lock:
            period_alerts = [
                alert for alert in self._alert_history
                if alert.timestamp >= cutoff_time
            ]
        
        return {
            "period_hours": hours,
            "timestamp": datetime.now().isoformat(),
            "data_points": len(period_metrics),
            "health_summary": {
                "avg_score": round(statistics.mean(health_scores), 1),
                "min_score": round(min(health_scores), 1),
                "max_score": round(max(health_scores), 1),
                "current_score": round(health_scores[-1], 1),
                "trend": self._calculate_trend_slope(health_scores[-20:]) if len(health_scores) >= 20 else 0.0
            },
            "redis_summary": {
                "avg_memory_percent": round(statistics.mean(redis_memory) * 100, 1),
                "max_memory_percent": round(max(redis_memory) * 100, 1),
                "avg_hit_rate": round(statistics.mean(redis_hitrate) * 100, 1),
                "min_hit_rate": round(min(redis_hitrate) * 100, 1)
            },
            "api_summary": {
                "avg_response_time_ms": round(statistics.mean(api_response_times), 1),
                "max_response_time_ms": round(max(api_response_times), 1),
                "p95_response_time_ms": round(statistics.quantiles(api_response_times, n=20)[18] if len(api_response_times) >= 20 else max(api_response_times), 1)
            },
            "system_summary": {
                "avg_cpu_percent": round(statistics.mean(cpu_usage), 1),
                "max_cpu_percent": round(max(cpu_usage), 1)
            },
            "alerts_summary": {
                "total_alerts": len(period_alerts),
                "critical_alerts": len([a for a in period_alerts if a.severity == "critical"]),
                "warning_alerts": len([a for a in period_alerts if a.type == "warning"]),
                "active_alerts": len(self._active_alerts)
            },
            "recommendations": self._generate_recommendations(period_metrics, period_alerts)
        }
    
    def _generate_recommendations(self, metrics: List[SystemHealthMetrics], alerts: List[ProductionAlert]) -> List[str]:
        """Gera recomendações baseadas nas métricas e alertas"""
        recommendations = []
        
        if not metrics:
            return recommendations
        
        # Análise de memory usage
        avg_memory = statistics.mean([m.redis_memory_used_percent for m in metrics])
        if avg_memory > 0.80:
            recommendations.append("Consider increasing Redis memory allocation or implementing data cleanup policies")
        
        # Análise de hit rate
        avg_hitrate = statistics.mean([m.redis_hit_rate for m in metrics])
        if avg_hitrate < 0.90:
            recommendations.append("Review Redis cache configuration and data access patterns to improve hit rate")
        
        # Análise de response time
        api_response_times = [m.api_avg_response_time_ms for m in metrics if m.api_avg_response_time_ms > 0]
        if api_response_times:
            avg_response_time = statistics.mean(api_response_times)
            if avg_response_time > 500:
                recommendations.append("API response times are elevated - consider performance optimization")
        
        # Análise de alertas
        critical_alerts = [a for a in alerts if a.severity == "critical"]
        if len(critical_alerts) > 10:
            recommendations.append("High number of critical alerts - immediate attention required")
        
        # Análise de tendências
        if len(metrics) >= 20:
            memory_trend = self._calculate_trend_slope([m.redis_memory_used_percent for m in metrics[-20:]])
            if memory_trend > 0.005:  # 0.5% por amostra
                recommendations.append("Redis memory usage is trending upward - monitor closely")
        
        return recommendations
    
    def _get_monitoring_duration(self) -> str:
        """Retorna duração do monitoramento"""
        if not self._metrics_buffer:
            return "0 minutes"
        
        start_time = self._metrics_buffer[0].timestamp
        duration = datetime.now() - start_time
        
        hours = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)
        
        return f"{hours}h {minutes}m"


# Instância global do monitor de produção
production_monitoring = ProductionMonitoring()