"""
API Performance Monitor - FASE 3 Implementation
Sistema de monitoramento de performance em tempo real com métricas avançadas
"""

import time
import json
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
import statistics

from loguru import logger

from app.services.redis_connection import get_redis_client
from app.services.hybrid_mode_manager import hybrid_mode_manager


@dataclass
class PerformanceMetric:
    """Métrica individual de performance"""
    endpoint: str
    method: str
    response_time_ms: float
    status_code: int
    source: str  # redis, json, fallback
    timestamp: datetime
    client_id: Optional[str] = None
    user_agent: Optional[str] = None
    error_message: Optional[str] = None
    
    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code < 400
    
    @property
    def is_redis(self) -> bool:
        return 'redis' in self.source.lower() and 'fallback' not in self.source.lower()
    
    @property
    def is_fallback(self) -> bool:
        return 'fallback' in self.source.lower()


@dataclass  
class EndpointStats:
    """Estatísticas agregadas de um endpoint"""
    endpoint: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time_ms: float = 0.0
    min_response_time_ms: float = float('inf')
    max_response_time_ms: float = 0.0
    p95_response_time_ms: float = 0.0
    redis_requests: int = 0
    json_requests: int = 0
    fallback_requests: int = 0
    last_updated: datetime = field(default_factory=datetime.now)
    
    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100
    
    @property
    def redis_usage_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.redis_requests / self.total_requests) * 100
    
    @property
    def fallback_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return (self.fallback_requests / self.total_requests) * 100


class APIPerformanceMonitor:
    """
    Monitor de performance da API com métricas em tempo real
    
    Funcionalidades:
    - Coleta métricas em tempo real
    - Estatísticas agregadas por endpoint
    - Alertas de performance
    - Comparação Redis vs JSON
    - Persistência opcional no Redis
    - Dashboard de métricas
    """
    
    def __init__(self, max_metrics_in_memory: int = 10000):
        self.max_metrics_in_memory = max_metrics_in_memory
        
        # Armazenamento em memória (circular buffer)
        self._metrics: deque[PerformanceMetric] = deque(maxlen=max_metrics_in_memory)
        
        # Cache de estatísticas agregadas
        self._endpoint_stats: Dict[str, EndpointStats] = {}
        self._last_aggregation = datetime.now()
        
        # Configurações de alertas
        self.SLOW_RESPONSE_THRESHOLD_MS = 1000
        self.HIGH_ERROR_RATE_THRESHOLD = 10.0  # 10%
        self.PERFORMANCE_DEGRADATION_THRESHOLD = 50.0  # 50% slower
        
        # Redis para persistência
        self._redis_client = None
        self.REDIS_KEY_PREFIX = "api_metrics"
        
        logger.info(f"APIPerformanceMonitor initialized (max_metrics: {max_metrics_in_memory})")
    
    async def initialize_redis(self):
        """Inicializa conexão Redis para persistência"""
        try:
            self._redis_client = await get_redis_client()
            if self._redis_client:
                logger.info("Redis connection established for performance monitoring")
                return True
            else:
                logger.info("Redis not available - metrics will be memory-only")
                return False
        except Exception as e:
            logger.warning(f"Failed to initialize Redis for monitoring: {e}")
            return False
    
    async def record_request(
        self,
        endpoint: str,
        method: str,
        response_time_ms: float,
        status_code: int,
        source: str,
        client_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        error_message: Optional[str] = None
    ):
        """Registra uma métrica de request"""
        metric = PerformanceMetric(
            endpoint=endpoint,
            method=method,
            response_time_ms=response_time_ms,
            status_code=status_code,
            source=source,
            timestamp=datetime.now(),
            client_id=client_id,
            user_agent=user_agent,
            error_message=error_message
        )
        
        # Adiciona à coleção em memória
        self._metrics.append(metric)
        
        # Atualiza estatísticas agregadas
        await self._update_endpoint_stats(metric)
        
        # Verifica alertas
        await self._check_performance_alerts(metric)
        
        # Persiste no Redis se disponível (async)
        if self._redis_client:
            asyncio.create_task(self._persist_metric_to_redis(metric))
    
    async def get_realtime_stats(self, last_minutes: int = 15) -> Dict[str, Any]:
        """Obtém estatísticas em tempo real"""
        cutoff_time = datetime.now() - timedelta(minutes=last_minutes)
        
        recent_metrics = [m for m in self._metrics if m.timestamp >= cutoff_time]
        
        if not recent_metrics:
            return {"message": f"No metrics in last {last_minutes} minutes"}
        
        # Estatísticas gerais
        total_requests = len(recent_metrics)
        successful_requests = sum(1 for m in recent_metrics if m.is_success)
        failed_requests = total_requests - successful_requests
        
        response_times = [m.response_time_ms for m in recent_metrics]
        
        # Estatísticas por source
        sources = defaultdict(int)
        for metric in recent_metrics:
            sources[metric.source] += 1
        
        # Estatísticas por endpoint
        endpoints = defaultdict(list)
        for metric in recent_metrics:
            endpoints[metric.endpoint].append(metric.response_time_ms)
        
        endpoint_stats = {}
        for endpoint, times in endpoints.items():
            endpoint_stats[endpoint] = {
                "requests": len(times),
                "avg_time_ms": round(statistics.mean(times), 2),
                "p95_time_ms": round(statistics.quantiles(times, n=20)[18] if len(times) >= 20 else max(times), 2)
            }
        
        return {
            "period_minutes": last_minutes,
            "timestamp": datetime.now().isoformat(),
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "success_rate": round((successful_requests / total_requests) * 100, 2),
            "avg_response_time_ms": round(statistics.mean(response_times), 2),
            "p95_response_time_ms": round(statistics.quantiles(response_times, n=20)[18] if len(response_times) >= 20 else max(response_times), 2),
            "min_response_time_ms": round(min(response_times), 2),
            "max_response_time_ms": round(max(response_times), 2),
            "requests_per_minute": round(total_requests / last_minutes, 2),
            "sources": dict(sources),
            "endpoints": endpoint_stats
        }
    
    async def get_endpoint_comparison(self, endpoint: str, last_hours: int = 24) -> Dict[str, Any]:
        """Compara performance Redis vs JSON para um endpoint"""
        cutoff_time = datetime.now() - timedelta(hours=last_hours)
        
        endpoint_metrics = [
            m for m in self._metrics 
            if m.endpoint == endpoint and m.timestamp >= cutoff_time
        ]
        
        if not endpoint_metrics:
            return {"error": f"No data for endpoint {endpoint} in last {last_hours} hours"}
        
        # Separa por source
        redis_metrics = [m for m in endpoint_metrics if m.is_redis]
        json_metrics = [m for m in endpoint_metrics if not m.is_redis and not m.is_fallback]
        fallback_metrics = [m for m in endpoint_metrics if m.is_fallback]
        
        def calculate_stats(metrics: List[PerformanceMetric]) -> Dict[str, Any]:
            if not metrics:
                return {"requests": 0}
            
            times = [m.response_time_ms for m in metrics]
            successes = sum(1 for m in metrics if m.is_success)
            
            return {
                "requests": len(metrics),
                "success_rate": round((successes / len(metrics)) * 100, 2),
                "avg_time_ms": round(statistics.mean(times), 2),
                "min_time_ms": round(min(times), 2),
                "max_time_ms": round(max(times), 2),
                "p95_time_ms": round(statistics.quantiles(times, n=20)[18] if len(times) >= 20 else max(times), 2)
            }
        
        redis_stats = calculate_stats(redis_metrics)
        json_stats = calculate_stats(json_metrics)
        fallback_stats = calculate_stats(fallback_metrics)
        
        # Calcula melhoria de performance
        performance_improvement = None
        if redis_stats.get("requests", 0) > 0 and json_stats.get("requests", 0) > 0:
            redis_avg = redis_stats["avg_time_ms"]
            json_avg = json_stats["avg_time_ms"]
            if json_avg > 0:
                improvement_pct = ((json_avg - redis_avg) / json_avg) * 100
                speedup = json_avg / redis_avg if redis_avg > 0 else 0
                performance_improvement = {
                    "improvement_percent": round(improvement_pct, 1),
                    "speedup_factor": round(speedup, 1),
                    "time_saved_ms": round(json_avg - redis_avg, 2)
                }
        
        return {
            "endpoint": endpoint,
            "period_hours": last_hours,
            "timestamp": datetime.now().isoformat(),
            "redis": redis_stats,
            "json": json_stats,
            "fallback": fallback_stats,
            "performance_improvement": performance_improvement,
            "total_requests": len(endpoint_metrics)
        }
    
    async def get_performance_alerts(self) -> List[Dict[str, Any]]:
        """Obtém alertas de performance ativas"""
        alerts = []
        current_time = datetime.now()
        
        # Verifica cada endpoint
        for endpoint, stats in self._endpoint_stats.items():
            # Alerta: Taxa de erro alta
            if stats.success_rate < (100 - self.HIGH_ERROR_RATE_THRESHOLD):
                alerts.append({
                    "type": "high_error_rate",
                    "endpoint": endpoint,
                    "current_rate": round(100 - stats.success_rate, 1),
                    "threshold": self.HIGH_ERROR_RATE_THRESHOLD,
                    "severity": "high" if stats.success_rate < 85 else "medium"
                })
            
            # Alerta: Resposta lenta
            if stats.avg_response_time_ms > self.SLOW_RESPONSE_THRESHOLD_MS:
                alerts.append({
                    "type": "slow_response",
                    "endpoint": endpoint,
                    "current_time_ms": stats.avg_response_time_ms,
                    "threshold_ms": self.SLOW_RESPONSE_THRESHOLD_MS,
                    "severity": "high" if stats.avg_response_time_ms > 2000 else "medium"
                })
            
            # Alerta: Alta taxa de fallback
            if stats.fallback_rate > 20.0:  # 20% fallback rate
                alerts.append({
                    "type": "high_fallback_rate",
                    "endpoint": endpoint,
                    "fallback_rate": stats.fallback_rate,
                    "redis_usage_rate": stats.redis_usage_rate,
                    "severity": "medium"
                })
        
        return alerts
    
    async def get_system_health_score(self) -> Dict[str, Any]:
        """Calcula score de saúde do sistema (0-100)"""
        stats = await self.get_realtime_stats(15)  # Últimos 15 minutos
        
        if "message" in stats:
            return {"health_score": 100, "message": "No recent activity"}
        
        score = 100.0
        factors = {}
        
        # Fator 1: Taxa de sucesso (peso 40%)
        success_rate = stats["success_rate"]
        success_factor = min(success_rate / 100, 1.0) * 40
        factors["success_rate"] = {
            "value": success_rate,
            "score": success_factor,
            "weight": 40
        }
        
        # Fator 2: Performance (peso 30%)
        avg_time = stats["avg_response_time_ms"]
        if avg_time <= 50:
            perf_factor = 30
        elif avg_time <= 200:
            perf_factor = 25
        elif avg_time <= 500:
            perf_factor = 20
        elif avg_time <= 1000:
            perf_factor = 15
        else:
            perf_factor = 10
        
        factors["performance"] = {
            "avg_time_ms": avg_time,
            "score": perf_factor,
            "weight": 30
        }
        
        # Fator 3: Uso do Redis (peso 20%)
        redis_usage = stats["sources"].get("redis", 0) / stats["total_requests"] * 100
        redis_factor = min(redis_usage / 80, 1.0) * 20  # 80% redis usage = full score
        factors["redis_usage"] = {
            "usage_rate": redis_usage,
            "score": redis_factor,
            "weight": 20
        }
        
        # Fator 4: Estabilidade - poucos fallbacks (peso 10%)
        fallback_count = sum(v for k, v in stats["sources"].items() if "fallback" in k)
        fallback_rate = fallback_count / stats["total_requests"] * 100
        stability_factor = max(0, 10 - (fallback_rate * 2))  # Penaliza fallbacks
        factors["stability"] = {
            "fallback_rate": fallback_rate,
            "score": stability_factor,
            "weight": 10
        }
        
        # Score final
        final_score = sum(f["score"] for f in factors.values())
        
        # Classificação
        if final_score >= 90:
            classification = "excellent"
        elif final_score >= 75:
            classification = "good"
        elif final_score >= 60:
            classification = "fair"
        elif final_score >= 40:
            classification = "poor"
        else:
            classification = "critical"
        
        return {
            "health_score": round(final_score, 1),
            "classification": classification,
            "timestamp": datetime.now().isoformat(),
            "factors": factors,
            "period_minutes": 15,
            "total_requests_analyzed": stats["total_requests"]
        }
    
    async def _update_endpoint_stats(self, metric: PerformanceMetric):
        """Atualiza estatísticas agregadas do endpoint"""
        endpoint = metric.endpoint
        
        if endpoint not in self._endpoint_stats:
            self._endpoint_stats[endpoint] = EndpointStats(endpoint=endpoint)
        
        stats = self._endpoint_stats[endpoint]
        
        # Atualiza contadores
        stats.total_requests += 1
        if metric.is_success:
            stats.successful_requests += 1
        else:
            stats.failed_requests += 1
        
        if metric.is_redis:
            stats.redis_requests += 1
        elif metric.is_fallback:
            stats.fallback_requests += 1
        else:
            stats.json_requests += 1
        
        # Atualiza tempos de resposta
        response_time = metric.response_time_ms
        stats.min_response_time_ms = min(stats.min_response_time_ms, response_time)
        stats.max_response_time_ms = max(stats.max_response_time_ms, response_time)
        
        # Recalcula média (aproximação)
        old_avg = stats.avg_response_time_ms
        stats.avg_response_time_ms = ((old_avg * (stats.total_requests - 1)) + response_time) / stats.total_requests
        
        stats.last_updated = datetime.now()
    
    async def _check_performance_alerts(self, metric: PerformanceMetric):
        """Verifica e gera alertas de performance"""
        # Alerta: Resposta muito lenta
        if metric.response_time_ms > self.SLOW_RESPONSE_THRESHOLD_MS:
            logger.warning(
                f"Slow response detected: {metric.endpoint} took {metric.response_time_ms:.2f}ms "
                f"(threshold: {self.SLOW_RESPONSE_THRESHOLD_MS}ms)"
            )
        
        # Alerta: Erro de servidor
        if metric.status_code >= 500:
            logger.error(
                f"Server error: {metric.endpoint} returned {metric.status_code} "
                f"in {metric.response_time_ms:.2f}ms - {metric.error_message or 'No error message'}"
            )
    
    async def _persist_metric_to_redis(self, metric: PerformanceMetric):
        """Persiste métrica no Redis para análise histórica"""
        if not self._redis_client:
            return
        
        try:
            # Chave baseada na data para facilitar limpeza
            date_key = metric.timestamp.strftime("%Y-%m-%d")
            redis_key = f"{self.REDIS_KEY_PREFIX}:metrics:{date_key}"
            
            # Serializa métrica
            metric_data = {
                "endpoint": metric.endpoint,
                "method": metric.method,
                "response_time_ms": metric.response_time_ms,
                "status_code": metric.status_code,
                "source": metric.source,
                "timestamp": metric.timestamp.isoformat(),
                "is_success": metric.is_success,
                "client_id": metric.client_id,
                "error_message": metric.error_message
            }
            
            # Adiciona à lista Redis (mantém últimas 10000 entradas por dia)
            pipe = self._redis_client.pipeline()
            pipe.lpush(redis_key, json.dumps(metric_data))
            pipe.ltrim(redis_key, 0, 9999)  # Mantém últimas 10k
            pipe.expire(redis_key, 7 * 24 * 3600)  # Expira em 7 dias
            
            await pipe.execute()
            
        except Exception as e:
            logger.warning(f"Failed to persist metric to Redis: {e}")
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """Obtém informações sobre uso de memória"""
        return {
            "metrics_in_memory": len(self._metrics),
            "max_metrics": self.max_metrics_in_memory,
            "memory_usage_percent": (len(self._metrics) / self.max_metrics_in_memory) * 100,
            "endpoints_tracked": len(self._endpoint_stats),
            "oldest_metric": self._metrics[0].timestamp.isoformat() if self._metrics else None,
            "newest_metric": self._metrics[-1].timestamp.isoformat() if self._metrics else None
        }


# Instância global do monitor
api_performance_monitor = APIPerformanceMonitor()