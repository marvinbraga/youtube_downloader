"""
Redis Fallback Middleware - FASE 3 Implementation
Sistema de fallback automático e graceful degradation para operações Redis
"""

import time
import asyncio
from typing import Callable, Dict, Any, Optional
from datetime import datetime, timedelta

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from loguru import logger

from app.services.redis_connection import get_redis_client
from app.services.hybrid_mode_manager import hybrid_mode_manager, PerformanceMetrics


class RedisHealthTracker:
    """Rastreia saúde do Redis para decisões inteligentes de fallback"""
    
    def __init__(self):
        self._failure_count = 0
        self._last_success = None
        self._last_failure = None
        self._circuit_breaker_until = None
        
        # Configurações
        self.MAX_FAILURES = 5
        self.CIRCUIT_BREAKER_DURATION = 300  # 5 minutos
        self.SUCCESS_RESET_THRESHOLD = 3
        
    def record_success(self):
        """Registra sucesso na operação Redis"""
        self._last_success = datetime.now()
        
        # Reset circuit breaker após sucessos consecutivos
        if self._failure_count > 0:
            self._failure_count = max(0, self._failure_count - 1)
            
        # Reset circuit breaker se teve sucessos suficientes
        if self._failure_count == 0:
            self._circuit_breaker_until = None
    
    def record_failure(self, error: str):
        """Registra falha na operação Redis"""
        self._failure_count += 1
        self._last_failure = datetime.now()
        
        logger.warning(f"Redis operation failed ({self._failure_count}/{self.MAX_FAILURES}): {error}")
        
        # Ativa circuit breaker após muitas falhas
        if self._failure_count >= self.MAX_FAILURES:
            self._circuit_breaker_until = datetime.now() + timedelta(seconds=self.CIRCUIT_BREAKER_DURATION)
            logger.error(f"Redis circuit breaker activated until {self._circuit_breaker_until}")
    
    def should_use_redis(self) -> bool:
        """Determina se Redis deve ser usado baseado no histórico"""
        now = datetime.now()
        
        # Circuit breaker ativo
        if self._circuit_breaker_until and now < self._circuit_breaker_until:
            return False
        
        # Circuit breaker expirou, permite tentativa
        if self._circuit_breaker_until and now >= self._circuit_breaker_until:
            self._circuit_breaker_until = None
            self._failure_count = 0  # Reset para dar nova chance
            logger.info("Redis circuit breaker expired, allowing Redis operations")
        
        return True
    
    def get_health_info(self) -> Dict[str, Any]:
        """Obtém informações de saúde do Redis"""
        now = datetime.now()
        
        return {
            "failure_count": self._failure_count,
            "max_failures": self.MAX_FAILURES,
            "circuit_breaker_active": bool(self._circuit_breaker_until and now < self._circuit_breaker_until),
            "circuit_breaker_until": self._circuit_breaker_until.isoformat() if self._circuit_breaker_until else None,
            "last_success": self._last_success.isoformat() if self._last_success else None,
            "last_failure": self._last_failure.isoformat() if self._last_failure else None,
            "should_use_redis": self.should_use_redis()
        }


class RedisFallbackMiddleware:
    """
    Middleware que implementa fallback automático para operações Redis
    
    Funcionalidades:
    - Circuit breaker pattern
    - Fallback automático para JSON
    - Métricas de performance
    - Health monitoring
    - Graceful degradation
    """
    
    def __init__(self):
        self.health_tracker = RedisHealthTracker()
        self._performance_cache = {}
        
        # Paths que devem usar fallback
        self.REDIS_ENDPOINTS = {
            "/api/audios",
            "/api/audios/search", 
            "/api/videos",
            "/api/videos/search"
        }
        
        # Paths que sempre usam JSON (sem fallback)
        self.JSON_ONLY_ENDPOINTS = {
            "/audio/list",
            "/videos"
        }
        
        logger.info("RedisFallbackMiddleware initialized")
    
    async def __call__(self, request: Request, call_next: Callable) -> Response:
        """Middleware principal"""
        start_time = time.time()
        path = request.url.path
        
        # Só aplica middleware para endpoints relevantes
        if not self._should_apply_middleware(path):
            return await call_next(request)
        
        # Verifica se deve usar Redis baseado na saúde
        should_use_redis = self.health_tracker.should_use_redis()
        
        # Adiciona header indicando status do Redis
        request.state.redis_available = should_use_redis
        request.state.performance_start = start_time
        
        try:
            # Processa requisição
            response = await call_next(request)
            
            # Se chegou até aqui sem erro, Redis funcionou
            if should_use_redis and self._is_redis_response(response):
                self.health_tracker.record_success()
                
            # Coleta métricas de performance
            await self._collect_performance_metrics(request, response, start_time)
            
            return response
            
        except Exception as e:
            # Se erro foi relacionado ao Redis, registra falha
            if should_use_redis and self._is_redis_error(e):
                self.health_tracker.record_failure(str(e))
            
            # Re-lança exceção para handling normal
            raise e
    
    def _should_apply_middleware(self, path: str) -> bool:
        """Determina se middleware deve ser aplicado ao path"""
        return any(endpoint in path for endpoint in self.REDIS_ENDPOINTS)
    
    def _is_redis_response(self, response: Response) -> bool:
        """Verifica se resposta veio do Redis baseado em headers/conteúdo"""
        if hasattr(response, 'body'):
            try:
                # Tenta detectar source="redis" no JSON
                import json
                if hasattr(response, 'body') and response.body:
                    body = response.body.decode()
                    data = json.loads(body)
                    source = data.get('source', '')
                    return 'redis' in source and 'fallback' not in source
            except:
                pass
        return False
    
    def _is_redis_error(self, error: Exception) -> bool:
        """Determina se erro está relacionado ao Redis"""
        error_str = str(error).lower()
        redis_error_keywords = [
            'redis',
            'connection refused',
            'connection timeout', 
            'redis server',
            'redisconnectionerror',
            'connectionerror'
        ]
        
        return any(keyword in error_str for keyword in redis_error_keywords)
    
    async def _collect_performance_metrics(
        self,
        request: Request,
        response: Response,
        start_time: float
    ):
        """Coleta métricas de performance para análise"""
        try:
            performance_ms = (time.time() - start_time) * 1000
            
            # Determina source da resposta
            source = "unknown"
            if hasattr(response, 'body') and response.body:
                try:
                    import json
                    body = response.body.decode()
                    data = json.loads(body)
                    source = data.get('source', 'unknown')
                except:
                    pass
            
            # Cria métricas
            metrics = PerformanceMetrics()
            
            if 'redis' in source:
                metrics.redis_time_ms = performance_ms
                metrics.redis_success = True
            elif 'json' in source:
                metrics.json_time_ms = performance_ms
                metrics.json_success = True
            
            metrics.fallback_used = 'fallback' in source
            
            # Registra no hybrid manager
            hybrid_mode_manager.record_performance_metrics(metrics)
            
            # Cache para análise posterior
            path = request.url.path
            if path not in self._performance_cache:
                self._performance_cache[path] = []
            
            self._performance_cache[path].append({
                'timestamp': datetime.now(),
                'performance_ms': performance_ms,
                'source': source,
                'success': response.status_code < 400
            })
            
            # Mantém apenas últimos 100 registros por path
            if len(self._performance_cache[path]) > 100:
                self._performance_cache[path] = self._performance_cache[path][-100:]
                
        except Exception as e:
            logger.warning(f"Failed to collect performance metrics: {e}")
    
    def get_middleware_stats(self) -> Dict[str, Any]:
        """Obtém estatísticas do middleware"""
        stats = {
            "redis_health": self.health_tracker.get_health_info(),
            "performance_cache": {},
            "middleware_info": {
                "redis_endpoints": list(self.REDIS_ENDPOINTS),
                "json_only_endpoints": list(self.JSON_ONLY_ENDPOINTS)
            }
        }
        
        # Adiciona estatísticas de performance por endpoint
        for path, metrics in self._performance_cache.items():
            recent_metrics = [m for m in metrics if m['timestamp'] > datetime.now() - timedelta(hours=1)]
            
            if recent_metrics:
                avg_performance = sum(m['performance_ms'] for m in recent_metrics) / len(recent_metrics)
                success_rate = sum(1 for m in recent_metrics if m['success']) / len(recent_metrics) * 100
                
                sources = {}
                for metric in recent_metrics:
                    source = metric['source']
                    sources[source] = sources.get(source, 0) + 1
                
                stats["performance_cache"][path] = {
                    "total_requests_1h": len(recent_metrics),
                    "avg_performance_ms": round(avg_performance, 2),
                    "success_rate_percent": round(success_rate, 1),
                    "sources": sources
                }
        
        return stats
    
    async def force_circuit_breaker_reset(self):
        """Força reset do circuit breaker para testes"""
        self.health_tracker._failure_count = 0
        self.health_tracker._circuit_breaker_until = None
        logger.info("Circuit breaker manually reset")
    
    async def test_redis_connection(self) -> Dict[str, Any]:
        """Testa conexão Redis e retorna resultado"""
        start_time = time.time()
        
        try:
            client = await get_redis_client()
            if client:
                await client.ping()
                response_time = (time.time() - start_time) * 1000
                
                self.health_tracker.record_success()
                
                return {
                    "status": "success",
                    "response_time_ms": round(response_time, 2),
                    "timestamp": datetime.now().isoformat()
                }
            else:
                raise Exception("Redis client not available")
                
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            self.health_tracker.record_failure(str(e))
            
            return {
                "status": "error",
                "error": str(e),
                "response_time_ms": round(response_time, 2),
                "timestamp": datetime.now().isoformat()
            }


# Instância global do middleware
redis_fallback_middleware = RedisFallbackMiddleware()