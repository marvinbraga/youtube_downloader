"""
Hybrid Mode Manager - FASE 3 Implementation
Gerencia modos híbridos Redis/JSON com configurações dinâmicas
"""

import os
import asyncio
from typing import Dict, Any, Optional, Literal
from dataclasses import dataclass
from datetime import datetime, timedelta

from loguru import logger

from app.services.redis_connection import get_redis_client, redis_manager, is_redis_available, quick_redis_ping


@dataclass
class HybridConfig:
    """Configuração do modo híbrido"""
    use_redis: bool = True
    compare_redis_json: bool = False
    auto_fallback: bool = True
    performance_monitoring: bool = True
    cache_ttl_seconds: int = 300  # 5 minutos
    comparison_log_level: str = "INFO"
    max_comparison_items: int = 100


@dataclass 
class PerformanceMetrics:
    """Métricas de performance para comparação"""
    redis_time_ms: Optional[float] = None
    json_time_ms: Optional[float] = None
    redis_success: bool = False
    json_success: bool = False
    fallback_used: bool = False
    discrepancies_count: int = 0
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
    
    @property
    def performance_improvement(self) -> Optional[str]:
        """Calcula melhoria de performance Redis vs JSON"""
        if self.redis_time_ms and self.json_time_ms and self.redis_success and self.json_success:
            if self.json_time_ms > 0:
                improvement = (self.json_time_ms - self.redis_time_ms) / self.json_time_ms * 100
                speedup = self.json_time_ms / self.redis_time_ms
                return f"{improvement:.1f}% faster ({speedup:.1f}x speedup)"
        return None


class HybridModeManager:
    """
    Gerenciador do modo híbrido Redis/JSON
    
    Funcionalidades:
    - Toggle dinâmico entre Redis/JSON
    - Comparação automática para validação
    - Métricas de performance em tempo real
    - Configuração via variáveis de ambiente
    - Graceful degradation
    - Healthchecks
    """
    
    def __init__(self):
        self.config = HybridConfig()
        self._load_config_from_env()
        
        # Métricas em memória
        self._performance_history: list[PerformanceMetrics] = []
        self._last_health_check = None
        self._redis_available = None
        
        # Cache para evitar checagens frequentes
        self._config_cache = {}
        self._cache_timestamp = None
        
        # Cache de modo de operação - evita verificações repetidas
        self._operation_mode_cache = None
        self._operation_mode_timestamp = None
        self._operation_mode_ttl = 30  # 30 segundos
        
        # Fallback rápido quando Redis definitivamente não disponivel
        self._fast_fallback_enabled = False
        self._fast_fallback_until = None
        
        logger.info(f"HybridModeManager initialized with config: {self.config}")
    
    def _load_config_from_env(self):
        """Carrega configurações das variáveis de ambiente"""
        self.config.use_redis = os.getenv("USE_REDIS", "true").lower() == "true"
        self.config.compare_redis_json = os.getenv("COMPARE_REDIS_JSON", "false").lower() == "true"
        self.config.auto_fallback = os.getenv("AUTO_FALLBACK", "true").lower() == "true"
        self.config.performance_monitoring = os.getenv("PERFORMANCE_MONITORING", "true").lower() == "true"
        
        # Configurações numéricas com fallback
        try:
            self.config.cache_ttl_seconds = int(os.getenv("CACHE_TTL_SECONDS", "300"))
        except ValueError:
            self.config.cache_ttl_seconds = 300
        
        try:
            self.config.max_comparison_items = int(os.getenv("MAX_COMPARISON_ITEMS", "100"))
        except ValueError:
            self.config.max_comparison_items = 100
        
        self.config.comparison_log_level = os.getenv("COMPARISON_LOG_LEVEL", "INFO").upper()
    
    async def should_use_redis(self, operation: str = "default") -> bool:
        """
        Determina se deve usar Redis baseado na configuração e disponibilidade
        Com cache agressivo para evitar delays repetidos
        
        Args:
            operation: Tipo de operação (get_audios, search, etc.)
        """
        if not self.config.use_redis:
            self._set_operation_mode("json_config_disabled")
            return False
        
        # Verificar fast fallback primeiro - se ativo, ir direto para JSON
        if self._is_fast_fallback_active():
            logger.debug(f"Fast fallback ativo para operação '{operation}', usando JSON")
            return False
        
        # Verificar cache de modo de operação antes de fazer verificações custosas
        cached_mode = self._get_cached_operation_mode()
        if cached_mode is not None:
            if cached_mode in ['redis_available', 'redis_circuit_breaker_ok']:
                return True
            else:  # json_fallback, redis_unavailable, etc.
                return False
        
        # Verifica disponibilidade do Redis (verificação mais rápida primeiro)
        is_available = await self._quick_redis_availability_check(operation)
        
        if not is_available:
            if self.config.auto_fallback:
                logger.debug(f"Redis não disponível para operação '{operation}', usando fallback JSON")
                self._set_operation_mode("json_fallback_auto")
                return False
            else:
                logger.warning(f"Redis não disponível para operação '{operation}' e auto_fallback está desabilitado")
                self._set_operation_mode("json_fallback_forced")
                return False
        
        self._set_operation_mode("redis_available")
        return True
    
    async def should_compare_modes(self, operation: str = "default") -> bool:
        """Determina se deve executar modo comparação Redis vs JSON"""
        if not self.config.compare_redis_json:
            return False
        
        # Só compara se Redis estiver disponível
        redis_available = await self._check_redis_availability()
        if not redis_available:
            return False
        
        # Limita comparações em operações de busca para não sobrecarregar
        if operation == "search" and not self._should_compare_search():
            return False
        
        return True
    
    def record_performance_metrics(self, metrics: PerformanceMetrics):
        """Registra métricas de performance para análise"""
        if not self.config.performance_monitoring:
            return
        
        self._performance_history.append(metrics)
        
        # Mantém apenas últimas 1000 métricas
        if len(self._performance_history) > 1000:
            self._performance_history = self._performance_history[-1000:]
        
        # Log da performance
        if metrics.performance_improvement:
            level = getattr(logger, self.config.comparison_log_level.lower())
            level(f"Performance metrics - {metrics.performance_improvement}")
        
        # Log discrepâncias
        if metrics.discrepancies_count > 0:
            logger.warning(f"Found {metrics.discrepancies_count} discrepancies between Redis and JSON")
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Obtém resumo das métricas de performance"""
        if not self._performance_history:
            return {"message": "No performance data available"}
        
        recent_metrics = [m for m in self._performance_history if m.timestamp > datetime.now() - timedelta(hours=1)]
        
        if not recent_metrics:
            return {"message": "No recent performance data"}
        
        # Calcula estatísticas
        redis_times = [m.redis_time_ms for m in recent_metrics if m.redis_time_ms and m.redis_success]
        json_times = [m.json_time_ms for m in recent_metrics if m.json_time_ms and m.json_success]
        
        summary = {
            "period": "Last 1 hour",
            "total_operations": len(recent_metrics),
            "redis_operations": len([m for m in recent_metrics if m.redis_success]),
            "json_operations": len([m for m in recent_metrics if m.json_success]),
            "fallback_operations": len([m for m in recent_metrics if m.fallback_used]),
            "total_discrepancies": sum(m.discrepancies_count for m in recent_metrics)
        }
        
        if redis_times:
            summary["redis_performance"] = {
                "avg_time_ms": round(sum(redis_times) / len(redis_times), 2),
                "min_time_ms": round(min(redis_times), 2),
                "max_time_ms": round(max(redis_times), 2)
            }
        
        if json_times:
            summary["json_performance"] = {
                "avg_time_ms": round(sum(json_times) / len(json_times), 2),
                "min_time_ms": round(min(json_times), 2),
                "max_time_ms": round(max(json_times), 2)
            }
        
        # Calcula melhoria média
        improvements = [m.performance_improvement for m in recent_metrics if m.performance_improvement]
        if improvements:
            # Extrai valores numéricos das melhorias
            speedups = []
            for imp in improvements:
                try:
                    # Busca padrão "Nx speedup"
                    if "x speedup" in imp:
                        speedup = float(imp.split("(")[1].split("x")[0])
                        speedups.append(speedup)
                except:
                    pass
            
            if speedups:
                summary["average_speedup"] = f"{sum(speedups) / len(speedups):.1f}x"
        
        return summary
    
    async def health_check(self) -> Dict[str, Any]:
        """Executa health check completo do sistema híbrido com informações de fallback"""
        start_time = datetime.now()
        
        health = {
            "timestamp": start_time.isoformat(),
            "hybrid_mode_active": True,
            "configuration": {
                "use_redis": self.config.use_redis,
                "compare_redis_json": self.config.compare_redis_json,
                "auto_fallback": self.config.auto_fallback,
                "performance_monitoring": self.config.performance_monitoring
            },
            "fallback_status": {
                "fast_fallback_enabled": self._fast_fallback_enabled,
                "fast_fallback_until": self._fast_fallback_until.isoformat() if self._fast_fallback_until else None,
                "operation_mode_cache": self._operation_mode_cache,
                "cache_expires_in_seconds": (
                    (self._operation_mode_timestamp + timedelta(seconds=self._operation_mode_ttl) - datetime.now()).total_seconds()
                    if self._operation_mode_timestamp else 0
                )
            }
        }
        
        # Testa Redis com verificação rápida primeiro
        try:
            # Usar verificação rápida primeiro
            redis_quick_available = await is_redis_available()
            
            if redis_quick_available:
                # Só faz ping completo se verificação rápida passou
                redis_client = await get_redis_client()
                if redis_client:
                    await redis_client.ping()
                    health["redis_status"] = "available"
                    health["redis_connection"] = "ok"
                else:
                    health["redis_status"] = "unavailable"
                    health["redis_connection"] = "client_failed"
            else:
                health["redis_status"] = "unavailable_cached"
                health["redis_connection"] = "blocked_by_cache_or_circuit_breaker"
            
        except Exception as e:
            health["redis_status"] = "error"
            health["redis_connection"] = str(e)
        
        # Sistema JSON eliminado - apenas documenta
        health["json_operations"] = {
            "status": "disabled",
            "message": "audios.json system completely eliminated",
            "test_time_ms": 0,
            "sample_count": 0
        }
        
        # Adiciona resumo de performance
        if self.config.performance_monitoring:
            health["performance_summary"] = self.get_performance_summary()
        
        # Cache resultado por 30 segundos
        self._last_health_check = health
        
        total_time = (datetime.now() - start_time).total_seconds() * 1000
        health["health_check_time_ms"] = round(total_time, 2)
        
        return health
    
    def _is_fast_fallback_active(self) -> bool:
        """Verifica se fast fallback está ativo"""
        if not self._fast_fallback_enabled or not self._fast_fallback_until:
            return False
        
        if datetime.now() > self._fast_fallback_until:
            self._fast_fallback_enabled = False
            self._fast_fallback_until = None
            logger.debug("Fast fallback period expired, re-enabling Redis checks")
            return False
        
        return True
    
    def _enable_fast_fallback(self, duration_seconds: int = 300):  # 5 minutos
        """Ativa fast fallback por um período"""
        self._fast_fallback_enabled = True
        self._fast_fallback_until = datetime.now() + timedelta(seconds=duration_seconds)
        logger.info(f"Fast fallback enabled for {duration_seconds} seconds")
    
    def _get_cached_operation_mode(self) -> Optional[str]:
        """Obtém modo de operação do cache se ainda válido"""
        if (self._operation_mode_cache and self._operation_mode_timestamp and 
            datetime.now() - self._operation_mode_timestamp < timedelta(seconds=self._operation_mode_ttl)):
            return self._operation_mode_cache
        return None
    
    def _set_operation_mode(self, mode: str):
        """Define modo de operação no cache"""
        self._operation_mode_cache = mode
        self._operation_mode_timestamp = datetime.now()
    
    async def _quick_redis_availability_check(self, operation: str) -> bool:
        """Verificação rápida de disponibilidade Redis com múltiplas camadas de cache"""
        try:
            # 1. Verificação usando função global (usa circuit breaker interno)
            if not await is_redis_available():
                logger.debug(f"Redis marcado como indisponível pela função global para '{operation}'")
                # Ativa fast fallback se Redis está consistentemente indisponível
                if not self._fast_fallback_enabled:
                    self._enable_fast_fallback(duration_seconds=60)  # 1 minuto
                return False
            
            # 2. Se passou na verificação rápida, tentar ping rápido
            if not await quick_redis_ping():
                logger.debug(f"Redis não respondeu ao ping rápido para '{operation}'")
                return False
            
            # Se chegou aqui, Redis parece disponível
            logger.debug(f"Redis disponível para operação '{operation}'")
            return True
        
        except Exception as e:
            logger.debug(f"Erro na verificação rápida do Redis para '{operation}': {e}")
            return False
    
    async def _check_redis_availability(self) -> bool:
        """Verifica disponibilidade do Redis - DEPRECATED - usar _quick_redis_availability_check"""
        # Manter compatibilidade, mas usar nova função
        return await self._quick_redis_availability_check("legacy_check")
    
    def _should_compare_search(self) -> bool:
        """Determina se deve executar comparação em buscas (rate limiting)"""
        # Limita comparações de busca para não sobrecarregar
        recent_comparisons = [m for m in self._performance_history 
                            if m.timestamp > datetime.now() - timedelta(minutes=5)]
        
        # Máximo 10 comparações de busca por 5 minutos
        return len(recent_comparisons) < 10
    
    def get_operation_mode_info(self) -> Dict[str, Any]:
        """Obtém informações sobre o modo de operação atual"""
        return {
            "current_mode": self._operation_mode_cache,
            "cache_valid": self._get_cached_operation_mode() is not None,
            "cache_expires_in_seconds": (
                (self._operation_mode_timestamp + timedelta(seconds=self._operation_mode_ttl) - datetime.now()).total_seconds()
                if self._operation_mode_timestamp else 0
            ),
            "fast_fallback_active": self._is_fast_fallback_active(),
            "fast_fallback_remaining_seconds": (
                (self._fast_fallback_until - datetime.now()).total_seconds()
                if self._fast_fallback_until and self._fast_fallback_enabled else 0
            )
        }
    
    def force_operation_mode(self, mode: str, duration_seconds: int = 60):
        """
        Força um modo de operação específico
        Útil para testes ou situações de emergência
        
        Args:
            mode: 'redis' para forçar Redis, 'json' para forçar JSON
            duration_seconds: Duração da força
        """
        if mode == 'redis':
            self._operation_mode_cache = "redis_forced"
            self._fast_fallback_enabled = False
            self._fast_fallback_until = None
        elif mode == 'json':
            self._enable_fast_fallback(duration_seconds)
            self._operation_mode_cache = "json_forced"
        else:
            logger.warning(f"Unknown operation mode: {mode}")
            return
        
        self._operation_mode_timestamp = datetime.now()
        logger.info(f"Operation mode forced to {mode} for {duration_seconds} seconds")
    
    def clear_operation_cache(self):
        """Limpa cache de modo de operação e força nova verificação"""
        self._operation_mode_cache = None
        self._operation_mode_timestamp = None
        self._fast_fallback_enabled = False
        self._fast_fallback_until = None
        logger.info("Operation mode cache cleared")
    
    def update_config(self, **kwargs):
        """Atualiza configuração dinamicamente"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logger.info(f"Configuration updated: {key} = {value}")
            else:
                logger.warning(f"Unknown configuration key: {key}")
        
        # Limpa todos os caches quando configuração muda
        self._cache_timestamp = None
        self.clear_operation_cache()


# Instância global do gerenciador híbrido
hybrid_mode_manager = HybridModeManager()


# Funções utilitárias globais para uso fácil
async def should_use_redis_for_operation(operation: str = "default") -> bool:
    """
    Função utilitária global para decidir se usar Redis
    Inclui todas as otimizações de cache e fallback
    
    Args:
        operation: Nome da operação
    
    Returns:
        True se deve usar Redis, False se deve usar JSON
    """
    return await hybrid_mode_manager.should_use_redis(operation)


def get_current_operation_mode() -> Dict[str, Any]:
    """
    Obtém informações sobre o modo de operação atual
    
    Returns:
        Dicionário com informações do modo atual
    """
    return hybrid_mode_manager.get_operation_mode_info()


def enable_json_fallback_mode(duration_seconds: int = 300):
    """
    Ativa modo de fallback JSON por um período
    Útil quando se sabe que Redis está indisponível
    
    Args:
        duration_seconds: Duração do modo fallback em segundos
    """
    hybrid_mode_manager.force_operation_mode('json', duration_seconds)


def clear_hybrid_cache():
    """
    Limpa cache do modo híbrido
    Força nova verificação de disponibilidade do Redis
    """
    hybrid_mode_manager.clear_operation_cache()