"""
Progress Metrics Collector - FASE 3 Sistema de Métricas Avançado
Coleta, análise e relatórios de métricas de performance em tempo real
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict, deque
import statistics

import redis.asyncio as redis
from loguru import logger

from .redis_connection import get_redis_client
from .advanced_progress_manager import AdvancedProgressManager, TaskType, TaskStatus


class MetricType(str, Enum):
    """Tipos de métricas coletadas"""
    LATENCY = "latency"
    THROUGHPUT = "throughput" 
    ERROR_RATE = "error_rate"
    CONNECTION_COUNT = "connection_count"
    STAGE_DURATION = "stage_duration"
    SPEED = "speed"
    RESOURCE_USAGE = "resource_usage"


class MetricAggregation(str, Enum):
    """Tipos de agregação de métricas"""
    AVERAGE = "average"
    MIN = "min"
    MAX = "max"
    SUM = "sum"
    COUNT = "count"
    PERCENTILE_95 = "p95"
    PERCENTILE_99 = "p99"


@dataclass
class MetricPoint:
    """Ponto individual de métrica"""
    timestamp: float
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "value": self.value,
            "labels": self.labels
        }


@dataclass
class MetricSeries:
    """Série temporal de métricas"""
    name: str
    metric_type: MetricType
    points: deque = field(default_factory=lambda: deque(maxlen=1000))  # Últimos 1000 pontos
    unit: str = ""
    description: str = ""
    
    def add_point(self, value: float, labels: Dict[str, str] = None, timestamp: Optional[float] = None):
        """Adiciona ponto à série"""
        if timestamp is None:
            timestamp = time.time()
        
        point = MetricPoint(
            timestamp=timestamp,
            value=value,
            labels=labels or {}
        )
        self.points.append(point)
    
    def get_latest(self, count: int = 1) -> List[MetricPoint]:
        """Obtém os últimos N pontos"""
        return list(self.points)[-count:] if self.points else []
    
    def get_range(self, start_time: float, end_time: float) -> List[MetricPoint]:
        """Obtém pontos em intervalo de tempo"""
        return [
            point for point in self.points 
            if start_time <= point.timestamp <= end_time
        ]
    
    def aggregate(self, aggregation: MetricAggregation, time_window: Optional[float] = None) -> Optional[float]:
        """Agrega valores da série"""
        points = self.points
        
        if time_window:
            cutoff_time = time.time() - time_window
            points = [p for p in points if p.timestamp >= cutoff_time]
        
        if not points:
            return None
        
        values = [p.value for p in points]
        
        if aggregation == MetricAggregation.AVERAGE:
            return statistics.mean(values)
        elif aggregation == MetricAggregation.MIN:
            return min(values)
        elif aggregation == MetricAggregation.MAX:
            return max(values)
        elif aggregation == MetricAggregation.SUM:
            return sum(values)
        elif aggregation == MetricAggregation.COUNT:
            return len(values)
        elif aggregation == MetricAggregation.PERCENTILE_95:
            return statistics.quantiles(values, n=20)[18] if len(values) > 1 else values[0]
        elif aggregation == MetricAggregation.PERCENTILE_99:
            return statistics.quantiles(values, n=100)[98] if len(values) > 1 else values[0]
        
        return None


@dataclass
class PerformanceReport:
    """Relatório de performance"""
    timestamp: str
    time_range: Tuple[str, str]
    summary: Dict[str, Any]
    metrics: Dict[str, Dict[str, float]]
    alerts: List[Dict[str, Any]]
    recommendations: List[str]


class ProgressMetricsCollector:
    """
    Coletor de métricas de performance avançado
    
    Funcionalidades:
    - Coleta métricas em tempo real
    - Agregações estatísticas (média, percentis, etc.)
    - Alertas automáticos baseados em thresholds
    - Relatórios de performance
    - Armazenamento em Redis com TTL
    - Dashboard de métricas em tempo real
    """
    
    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self._redis: Optional[redis.Redis] = redis_client
        self._metrics: Dict[str, MetricSeries] = {}
        self._collection_task: Optional[asyncio.Task] = None
        self._alert_task: Optional[asyncio.Task] = None
        
        # Configurações
        self.COLLECTION_INTERVAL = 5.0  # segundos
        self.ALERT_CHECK_INTERVAL = 30.0  # segundos
        self.METRICS_TTL = 24 * 3600  # 24 horas
        
        # Thresholds de alerta
        self.ALERT_THRESHOLDS = {
            MetricType.LATENCY: {
                "warning": 100.0,  # ms
                "critical": 500.0
            },
            MetricType.ERROR_RATE: {
                "warning": 5.0,  # %
                "critical": 10.0
            },
            MetricType.CONNECTION_COUNT: {
                "warning": 800,
                "critical": 950
            }
        }
        
        # Inicializar métricas padrão
        self._init_default_metrics()
        
        logger.info("ProgressMetricsCollector initialized")
    
    def _init_default_metrics(self):
        """Inicializa métricas padrão"""
        default_metrics = [
            ("websocket_latency", MetricType.LATENCY, "ms", "WebSocket message latency"),
            ("sse_latency", MetricType.LATENCY, "ms", "SSE event latency"),
            ("download_speed", MetricType.SPEED, "bytes/s", "Download speed"),
            ("active_connections", MetricType.CONNECTION_COUNT, "count", "Active WebSocket connections"),
            ("active_tasks", MetricType.CONNECTION_COUNT, "count", "Active progress tasks"),
            ("error_rate", MetricType.ERROR_RATE, "percent", "System error rate"),
            ("stage_completion_time", MetricType.STAGE_DURATION, "seconds", "Time to complete stages"),
            ("memory_usage", MetricType.RESOURCE_USAGE, "MB", "Memory usage"),
            ("cpu_usage", MetricType.RESOURCE_USAGE, "percent", "CPU usage"),
            ("redis_operations_per_sec", MetricType.THROUGHPUT, "ops/s", "Redis operations per second")
        ]
        
        for name, metric_type, unit, description in default_metrics:
            self._metrics[name] = MetricSeries(
                name=name,
                metric_type=metric_type,
                unit=unit,
                description=description
            )
    
    async def initialize(self):
        """Inicializa o coletor de métricas"""
        try:
            if not self._redis:
                self._redis = await get_redis_client()
            
            # Iniciar tarefas de coleta
            self._collection_task = asyncio.create_task(self._collection_loop())
            self._alert_task = asyncio.create_task(self._alert_loop())
            
            logger.success("ProgressMetricsCollector initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize ProgressMetricsCollector: {e}")
            raise
    
    async def record_metric(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
        timestamp: Optional[float] = None
    ):
        """Registra ponto de métrica"""
        try:
            if name not in self._metrics:
                logger.warning(f"Unknown metric: {name}")
                return
            
            metric = self._metrics[name]
            metric.add_point(value, labels, timestamp)
            
            # Persistir no Redis
            await self._persist_metric_point(name, value, labels, timestamp or time.time())
            
        except Exception as e:
            logger.error(f"Error recording metric {name}: {e}")
    
    async def record_latency(
        self,
        operation: str,
        latency_ms: float,
        labels: Optional[Dict[str, str]] = None
    ):
        """Registra métrica de latência"""
        metric_name = f"{operation}_latency"
        
        # Criar métrica se não existir
        if metric_name not in self._metrics:
            self._metrics[metric_name] = MetricSeries(
                name=metric_name,
                metric_type=MetricType.LATENCY,
                unit="ms",
                description=f"Latency for {operation}"
            )
        
        await self.record_metric(metric_name, latency_ms, labels)
    
    async def record_throughput(
        self,
        operation: str,
        count: int,
        time_window: float = 1.0,
        labels: Optional[Dict[str, str]] = None
    ):
        """Registra métrica de throughput"""
        metric_name = f"{operation}_throughput"
        throughput = count / time_window
        
        # Criar métrica se não existir
        if metric_name not in self._metrics:
            self._metrics[metric_name] = MetricSeries(
                name=metric_name,
                metric_type=MetricType.THROUGHPUT,
                unit="ops/s",
                description=f"Throughput for {operation}"
            )
        
        await self.record_metric(metric_name, throughput, labels)
    
    async def record_error(
        self,
        operation: str,
        error_type: str,
        labels: Optional[Dict[str, str]] = None
    ):
        """Registra erro para cálculo de error rate"""
        metric_name = f"{operation}_errors"
        
        # Criar métrica se não existir
        if metric_name not in self._metrics:
            self._metrics[metric_name] = MetricSeries(
                name=metric_name,
                metric_type=MetricType.ERROR_RATE,
                unit="count",
                description=f"Error count for {operation}"
            )
        
        error_labels = {**(labels or {}), "error_type": error_type}
        await self.record_metric(metric_name, 1.0, error_labels)
    
    async def get_metric_summary(
        self,
        metric_name: str,
        time_window: Optional[float] = 3600  # 1 hora por padrão
    ) -> Optional[Dict[str, float]]:
        """Obtém resumo estatístico de uma métrica"""
        if metric_name not in self._metrics:
            return None
        
        metric = self._metrics[metric_name]
        
        return {
            "current": metric.get_latest(1)[0].value if metric.points else 0.0,
            "average": metric.aggregate(MetricAggregation.AVERAGE, time_window) or 0.0,
            "min": metric.aggregate(MetricAggregation.MIN, time_window) or 0.0,
            "max": metric.aggregate(MetricAggregation.MAX, time_window) or 0.0,
            "p95": metric.aggregate(MetricAggregation.PERCENTILE_95, time_window) or 0.0,
            "p99": metric.aggregate(MetricAggregation.PERCENTILE_99, time_window) or 0.0,
            "count": metric.aggregate(MetricAggregation.COUNT, time_window) or 0.0
        }
    
    async def get_all_metrics_summary(
        self, 
        time_window: Optional[float] = 3600
    ) -> Dict[str, Dict[str, float]]:
        """Obtém resumo de todas as métricas"""
        summary = {}
        
        for metric_name in self._metrics.keys():
            metric_summary = await self.get_metric_summary(metric_name, time_window)
            if metric_summary:
                summary[metric_name] = metric_summary
        
        return summary
    
    async def get_metric_history(
        self,
        metric_name: str,
        time_window: float = 3600,
        resolution: int = 60  # Número de pontos desejados
    ) -> Optional[List[Dict[str, Any]]]:
        """Obtém histórico de métrica com resolução específica"""
        if metric_name not in self._metrics:
            return None
        
        metric = self._metrics[metric_name]
        
        # Calcular intervalo de agregação
        interval = time_window / resolution
        current_time = time.time()
        start_time = current_time - time_window
        
        history = []
        
        for i in range(resolution):
            bucket_start = start_time + (i * interval)
            bucket_end = bucket_start + interval
            
            # Obter pontos no bucket
            bucket_points = [
                p for p in metric.points
                if bucket_start <= p.timestamp < bucket_end
            ]
            
            if bucket_points:
                avg_value = statistics.mean(p.value for p in bucket_points)
                history.append({
                    "timestamp": bucket_start,
                    "value": avg_value,
                    "count": len(bucket_points)
                })
            else:
                history.append({
                    "timestamp": bucket_start,
                    "value": None,
                    "count": 0
                })
        
        return history
    
    async def generate_performance_report(
        self,
        time_window: float = 3600
    ) -> PerformanceReport:
        """Gera relatório de performance"""
        try:
            current_time = datetime.now()
            start_time = current_time - timedelta(seconds=time_window)
            
            # Coletar resumos de métricas
            metrics_summary = await self.get_all_metrics_summary(time_window)
            
            # Calcular métricas principais
            summary = {
                "total_metrics": len(self._metrics),
                "data_points_collected": sum(len(m.points) for m in self._metrics.values()),
                "time_window_hours": time_window / 3600,
                "report_generated_at": current_time.isoformat()
            }
            
            # Gerar alertas
            alerts = await self._check_alerts()
            
            # Gerar recomendações
            recommendations = await self._generate_recommendations(metrics_summary)
            
            return PerformanceReport(
                timestamp=current_time.isoformat(),
                time_range=(start_time.isoformat(), current_time.isoformat()),
                summary=summary,
                metrics=metrics_summary,
                alerts=alerts,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Error generating performance report: {e}")
            raise
    
    async def _persist_metric_point(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]],
        timestamp: float
    ):
        """Persiste ponto de métrica no Redis"""
        try:
            if not self._redis:
                return
            
            # Chave para a série temporal
            key = f"metrics:series:{name}"
            
            # Dados do ponto
            point_data = {
                "timestamp": timestamp,
                "value": value,
                "labels": json.dumps(labels or {})
            }
            
            # Adicionar à lista no Redis
            await self._redis.lpush(key, json.dumps(point_data))
            
            # Manter apenas últimos 1000 pontos
            await self._redis.ltrim(key, 0, 999)
            
            # Definir TTL
            await self._redis.expire(key, self.METRICS_TTL)
            
        except Exception as e:
            logger.error(f"Error persisting metric point: {e}")
    
    async def _collection_loop(self):
        """Loop principal de coleta de métricas"""
        while True:
            try:
                await asyncio.sleep(self.COLLECTION_INTERVAL)
                
                # Coletar métricas do sistema
                await self._collect_system_metrics()
                
                # Persistir snapshot das métricas atuais
                await self._persist_metrics_snapshot()
                
            except asyncio.CancelledError:
                logger.info("Metrics collection task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in metrics collection loop: {e}")
    
    async def _collect_system_metrics(self):
        """Coleta métricas do sistema"""
        try:
            # CPU e Memória (simulado - em produção usar psutil)
            import psutil
            
            cpu_percent = psutil.cpu_percent(interval=1)
            memory_info = psutil.virtual_memory()
            memory_mb = memory_info.used / (1024 * 1024)
            
            await self.record_metric("cpu_usage", cpu_percent)
            await self.record_metric("memory_usage", memory_mb)
            
            # Métricas Redis se disponível
            if self._redis:
                info = await self._redis.info()
                connected_clients = info.get('connected_clients', 0)
                operations_per_sec = info.get('instantaneous_ops_per_sec', 0)
                
                await self.record_metric("redis_connected_clients", connected_clients)
                await self.record_metric("redis_operations_per_sec", operations_per_sec)
            
        except ImportError:
            # psutil não disponível, usar métricas mock
            await self.record_metric("cpu_usage", 0.0)
            await self.record_metric("memory_usage", 0.0)
        except Exception as e:
            logger.warning(f"Error collecting system metrics: {e}")
    
    async def _persist_metrics_snapshot(self):
        """Persiste snapshot atual das métricas"""
        try:
            if not self._redis:
                return
            
            snapshot = {
                "timestamp": time.time(),
                "metrics": {}
            }
            
            for name, metric in self._metrics.items():
                latest = metric.get_latest(1)
                if latest:
                    snapshot["metrics"][name] = {
                        "value": latest[0].value,
                        "timestamp": latest[0].timestamp,
                        "labels": latest[0].labels
                    }
            
            # Salvar snapshot
            snapshot_key = f"metrics:snapshot:{int(time.time())}"
            await self._redis.setex(
                snapshot_key,
                self.METRICS_TTL,
                json.dumps(snapshot)
            )
            
        except Exception as e:
            logger.error(f"Error persisting metrics snapshot: {e}")
    
    async def _alert_loop(self):
        """Loop de verificação de alertas"""
        while True:
            try:
                await asyncio.sleep(self.ALERT_CHECK_INTERVAL)
                
                alerts = await self._check_alerts()
                
                for alert in alerts:
                    if alert["level"] == "critical":
                        logger.error(f"CRITICAL ALERT: {alert['message']}")
                    elif alert["level"] == "warning":
                        logger.warning(f"WARNING: {alert['message']}")
                
            except asyncio.CancelledError:
                logger.info("Alert checking task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in alert loop: {e}")
    
    async def _check_alerts(self) -> List[Dict[str, Any]]:
        """Verifica condições de alerta"""
        alerts = []
        
        try:
            for metric_name, metric in self._metrics.items():
                if metric.metric_type not in self.ALERT_THRESHOLDS:
                    continue
                
                thresholds = self.ALERT_THRESHOLDS[metric.metric_type]
                latest = metric.get_latest(1)
                
                if not latest:
                    continue
                
                current_value = latest[0].value
                
                # Verificar threshold crítico
                if current_value >= thresholds["critical"]:
                    alerts.append({
                        "level": "critical",
                        "metric": metric_name,
                        "current_value": current_value,
                        "threshold": thresholds["critical"],
                        "message": f"{metric_name} is critically high: {current_value} >= {thresholds['critical']}",
                        "timestamp": datetime.now().isoformat()
                    })
                
                # Verificar threshold de warning
                elif current_value >= thresholds["warning"]:
                    alerts.append({
                        "level": "warning",
                        "metric": metric_name,
                        "current_value": current_value,
                        "threshold": thresholds["warning"],
                        "message": f"{metric_name} is above warning threshold: {current_value} >= {thresholds['warning']}",
                        "timestamp": datetime.now().isoformat()
                    })
            
        except Exception as e:
            logger.error(f"Error checking alerts: {e}")
        
        return alerts
    
    async def _generate_recommendations(
        self,
        metrics_summary: Dict[str, Dict[str, float]]
    ) -> List[str]:
        """Gera recomendações baseadas nas métricas"""
        recommendations = []
        
        try:
            # Verificar latência
            for metric_name in metrics_summary:
                if "latency" in metric_name:
                    summary = metrics_summary[metric_name]
                    avg_latency = summary.get("average", 0)
                    p99_latency = summary.get("p99", 0)
                    
                    if p99_latency > 200:  # ms
                        recommendations.append(
                            f"High P99 latency detected for {metric_name} ({p99_latency:.1f}ms). "
                            "Consider optimizing or scaling the system."
                        )
                    
                    if avg_latency > 100:  # ms
                        recommendations.append(
                            f"Average latency for {metric_name} is high ({avg_latency:.1f}ms). "
                            "Review performance bottlenecks."
                        )
            
            # Verificar connections
            if "active_connections" in metrics_summary:
                conn_summary = metrics_summary["active_connections"]
                max_connections = conn_summary.get("max", 0)
                
                if max_connections > 800:
                    recommendations.append(
                        f"High connection count detected ({max_connections}). "
                        "Consider implementing connection pooling or rate limiting."
                    )
            
            # Verificar error rate
            error_metrics = [m for m in metrics_summary if "error" in m]
            if error_metrics:
                for metric_name in error_metrics:
                    error_summary = metrics_summary[metric_name]
                    avg_errors = error_summary.get("average", 0)
                    
                    if avg_errors > 0.1:  # > 10% error rate
                        recommendations.append(
                            f"High error rate detected for {metric_name} ({avg_errors:.2%}). "
                            "Investigate error causes and implement fixes."
                        )
            
            # Verificar resource usage
            if "cpu_usage" in metrics_summary:
                cpu_summary = metrics_summary["cpu_usage"]
                avg_cpu = cpu_summary.get("average", 0)
                
                if avg_cpu > 80:
                    recommendations.append(
                        f"High CPU usage detected ({avg_cpu:.1f}%). "
                        "Consider scaling or optimizing CPU-intensive operations."
                    )
            
            if "memory_usage" in metrics_summary:
                mem_summary = metrics_summary["memory_usage"]
                avg_memory = mem_summary.get("average", 0)
                
                if avg_memory > 1000:  # MB
                    recommendations.append(
                        f"High memory usage detected ({avg_memory:.1f}MB). "
                        "Review memory leaks and optimize memory usage."
                    )
            
            # Adicionar recomendações gerais se não há problemas
            if not recommendations:
                recommendations.append(
                    "System is performing well. Continue monitoring for any changes."
                )
                recommendations.append(
                    "Consider setting up automated alerts for proactive monitoring."
                )
            
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            recommendations.append("Error generating recommendations - manual review needed.")
        
        return recommendations
    
    def get_metrics_list(self) -> List[Dict[str, Any]]:
        """Obtém lista de métricas disponíveis"""
        return [
            {
                "name": metric.name,
                "type": metric.metric_type,
                "unit": metric.unit,
                "description": metric.description,
                "data_points": len(metric.points),
                "latest_value": metric.get_latest(1)[0].value if metric.points else None
            }
            for metric in self._metrics.values()
        ]
    
    async def shutdown(self):
        """Shutdown graceful do collector"""
        logger.info("Shutting down ProgressMetricsCollector...")
        
        # Cancelar tasks
        if self._collection_task:
            self._collection_task.cancel()
            try:
                await self._collection_task
            except asyncio.CancelledError:
                pass
        
        if self._alert_task:
            self._alert_task.cancel()
            try:
                await self._alert_task
            except asyncio.CancelledError:
                pass
        
        logger.info("ProgressMetricsCollector shutdown complete")


# Instância global
metrics_collector: Optional[ProgressMetricsCollector] = None


async def get_metrics_collector() -> ProgressMetricsCollector:
    """Obtém instância global do metrics collector"""
    global metrics_collector
    
    if metrics_collector is None:
        redis_client = await get_redis_client()
        metrics_collector = ProgressMetricsCollector(redis_client)
        await metrics_collector.initialize()
    
    return metrics_collector


async def init_metrics_collector() -> None:
    """Inicializa o metrics collector"""
    await get_metrics_collector()


async def close_metrics_collector() -> None:
    """Fecha o metrics collector"""
    global metrics_collector
    
    if metrics_collector:
        await metrics_collector.shutdown()
        metrics_collector = None