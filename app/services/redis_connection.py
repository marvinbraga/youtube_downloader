"""
Redis Connection Manager com Pool de Conexões
Gerencia conexões Redis com pool para melhor performance e confiabilidade
"""

import asyncio
import json
import os
import time
from typing import Optional, Dict, Any, List, Union
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from enum import Enum

import redis.asyncio as redis
from loguru import logger
from redis.exceptions import RedisError, ConnectionError


class CircuitBreakerState(Enum):
    """Estados do Circuit Breaker"""
    CLOSED = "closed"     # Normal operation
    OPEN = "open"         # Failing fast
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """Circuit Breaker para conexões Redis"""
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60, success_threshold: int = 2):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout  # seconds
        self.success_threshold = success_threshold
        
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.state = CircuitBreakerState.CLOSED
    
    def should_attempt_call(self) -> bool:
        """Determina se deve tentar fazer a chamada"""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        
        if self.state == CircuitBreakerState.OPEN:
            # Verifica se é hora de tentar novamente
            if self.last_failure_time and \
               datetime.now() - self.last_failure_time > timedelta(seconds=self.recovery_timeout):
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
                logger.info("Circuit breaker moving to HALF_OPEN state")
                return True
            return False
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            return True
        
        return False
    
    def record_success(self):
        """Registra sucesso na operação"""
        self.failure_count = 0
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitBreakerState.CLOSED
                logger.info("Circuit breaker returning to CLOSED state")
    
    def record_failure(self):
        """Registra falha na operação"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
            logger.warning("Circuit breaker returning to OPEN state after failure in HALF_OPEN")
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            logger.warning(f"Circuit breaker OPENED after {self.failure_count} failures")
    
    def get_state(self) -> Dict[str, Any]:
        """Obtém estado atual do circuit breaker"""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout
        }


class RedisConnectionManager:
    """
    Gerencia conexões Redis com pool de conexões para otimizar performance.
    Implementa padrão Singleton para garantir única instância por aplicação.
    """
    
    _instance: Optional['RedisConnectionManager'] = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._connection_pool: Optional[redis.ConnectionPool] = None
            self._redis_client: Optional[redis.Redis] = None
            self._config = self._load_redis_config()
            
            # Armazenar configurações individuais para acesso rápido
            self._redis_host = self._config['host']
            self._redis_port = self._config['port']
            self._redis_password = self._config.get('password')
            self._redis_db = self._config['db']
            
            # Circuit breaker para resiliência
            self._circuit_breaker = CircuitBreaker(
                failure_threshold=3,  # Abre após 3 falhas consecutivas
                recovery_timeout=30,  # Tenta novamente após 30s
                success_threshold=2   # Fecha após 2 sucessos
            )
            
            # Cache de status de conexão
            self._connection_status_cache = None
            self._cache_timestamp = None
            self._cache_ttl = 10  # 10 segundos
            
            self._initialized = True
    
    def _load_redis_config(self) -> Dict[str, Any]:
        """Carrega configurações Redis do ambiente ou usa valores padrão"""
        
        def safe_int(value, default):
            """Converte valor para int de forma segura"""
            try:
                return int(value)
            except (ValueError, TypeError):
                logger.warning(f"Valor inválido para conversão int: {value}. Usando padrão: {default}")
                return default
        
        def safe_float(value, default):
            """Converte valor para float de forma segura"""
            try:
                return float(value)
            except (ValueError, TypeError):
                logger.warning(f"Valor inválido para conversão float: {value}. Usando padrão: {default}")
                return default
        
        return {
            'host': os.getenv('REDIS_HOST', 'localhost'),
            'port': safe_int(os.getenv('REDIS_PORT', '6379'), 6379),
            'db': safe_int(os.getenv('REDIS_DB', '0'), 0),
            'password': os.getenv('REDIS_PASSWORD'),
            'max_connections': safe_int(os.getenv('REDIS_MAX_CONNECTIONS', '100'), 100),
            # Timeouts reduzidos para falhar mais rápido
            'socket_timeout': safe_float(os.getenv('REDIS_SOCKET_TIMEOUT', '2.0'), 2.0),  # 2s instead of 5s
            'socket_connect_timeout': safe_float(os.getenv('REDIS_CONNECT_TIMEOUT', '1.0'), 1.0),  # 1s instead of 5s
            'retry_on_timeout': True,
            'health_check_interval': safe_int(os.getenv('REDIS_HEALTH_CHECK_INTERVAL', '30'), 30),
            'socket_keepalive': True,
            # socket_keepalive_options não funciona no Windows
            # Removendo para evitar erros de tipo
        }
    
    async def initialize(self) -> None:
        """
        Inicializa o pool de conexões Redis com circuit breaker
        """
        if self._connection_pool is None:
            # Verificar circuit breaker antes de tentar conectar
            if not self._circuit_breaker.should_attempt_call():
                logger.warning("Circuit breaker is OPEN, skipping Redis initialization")
                raise ConnectionError("Circuit breaker is OPEN - Redis connections are failing")
            
            try:
                logger.info("Inicializando pool de conexões Redis...")
                
                # Configurar pool de conexões
                pool_config = {
                    'host': self._config['host'],
                    'port': self._config['port'],
                    'db': self._config['db'],
                    'max_connections': self._config['max_connections'],
                    'socket_timeout': self._config['socket_timeout'],
                    'socket_connect_timeout': self._config['socket_connect_timeout'],
                    'retry_on_timeout': self._config['retry_on_timeout'],
                    'health_check_interval': self._config['health_check_interval'],
                    'socket_keepalive': self._config['socket_keepalive'],
                    # socket_keepalive_options removido - não funciona no Windows
                }
                
                # Adicionar senha se configurada
                if self._config['password']:
                    pool_config['password'] = self._config['password']
                
                # Criar pool de conexões
                self._connection_pool = redis.ConnectionPool(**pool_config)
                
                # Criar cliente Redis
                self._redis_client = redis.Redis(connection_pool=self._connection_pool)
                
                # Testar conexão com timeout reduzido
                await asyncio.wait_for(self._redis_client.ping(), timeout=2.0)
                
                # Sucesso - registrar no circuit breaker
                self._circuit_breaker.record_success()
                self._update_connection_cache(True, None)
                
                logger.success(f"Pool de conexões Redis inicializado: {self._config['host']}:{self._config['port']}")
                
            except Exception as e:
                # Registrar falha no circuit breaker
                self._circuit_breaker.record_failure()
                self._update_connection_cache(False, str(e))
                
                logger.error(f"Erro ao inicializar Redis: {str(e)}")
                raise ConnectionError(f"Falha na conexão Redis: {str(e)}")
    
    async def get_client(self) -> redis.Redis:
        """
        Retorna cliente Redis, inicializando se necessário
        Respeita circuit breaker para evitar tentativas desnecessárias
        
        Returns:
            Cliente Redis configurado
        
        Raises:
            ConnectionError: Se circuit breaker estiver aberto ou conexão falhar
        """
        # Verificar cache de status primeiro
        if not self._is_connection_likely_available():
            raise ConnectionError("Redis connection unavailable (cached status)")
        
        if self._redis_client is None:
            await self.initialize()
        
        # Última verificação antes de retornar o client
        if not await self.quick_health_check():
            raise ConnectionError("Redis client is not responding to quick health check")
        
        return self._redis_client
    
    def _is_connection_likely_available(self) -> bool:
        """
        Verifica se a conexão provavelmente está disponível usando cache
        Evita tentativas desnecessárias quando sabemos que Redis está indisponível
        """
        # Verificar circuit breaker primeiro
        if not self._circuit_breaker.should_attempt_call():
            return False
        
        # Verificar cache de status
        if self._connection_status_cache is not None and self._cache_timestamp:
            cache_age = datetime.now() - self._cache_timestamp
            if cache_age < timedelta(seconds=self._cache_ttl):
                return self._connection_status_cache['available']
        
        # Se não temos informação em cache, assumir que pode estar disponível
        return True
    
    def _update_connection_cache(self, available: bool, error: Optional[str] = None):
        """Atualiza cache de status de conexão"""
        self._connection_status_cache = {
            'available': available,
            'error': error,
            'last_check': datetime.now().isoformat()
        }
        self._cache_timestamp = datetime.now()
    
    async def quick_health_check(self) -> bool:
        """
        Verificação rápida de saúde (apenas ping com timeout agressivo)
        Usado para decisões rápidas de fallback
        
        Returns:
            True se Redis está disponível e respondendo
        """
        try:
            # Primeiro verificar circuit breaker
            if not self._circuit_breaker.should_attempt_call():
                return False
            
            # Se não temos cliente, criar um temporário para teste
            test_client = None
            try:
                if self._redis_client is None:
                    # Criar cliente temporário apenas para teste
                    test_client = redis.Redis(
                        host=self._redis_host,
                        port=self._redis_port,
                        password=self._redis_password,
                        db=self._redis_db,
                        decode_responses=True,
                        socket_connect_timeout=1,
                        socket_timeout=1
                    )
                    # Ping rápido com cliente temporário
                    await asyncio.wait_for(test_client.ping(), timeout=0.5)
                    await test_client.close()
                else:
                    # Usar cliente existente
                    await asyncio.wait_for(self._redis_client.ping(), timeout=0.5)
                
                self._circuit_breaker.record_success()
                self._update_connection_cache(True)
                return True
            finally:
                # Limpar cliente temporário se foi criado
                if test_client:
                    try:
                        await test_client.close()
                    except:
                        pass
                        
        except Exception:
            self._circuit_breaker.record_failure()
            self._update_connection_cache(False)
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Verifica saúde da conexão Redis com informações do circuit breaker
        
        Returns:
            Dicionário com informações de saúde
        """
        circuit_breaker_info = self._circuit_breaker.get_state()
        
        # Se circuit breaker está aberto, retornar status sem tentar conectar
        if circuit_breaker_info['state'] == CircuitBreakerState.OPEN.value:
            return {
                'status': 'circuit_breaker_open',
                'error': 'Circuit breaker is open due to repeated failures',
                'circuit_breaker': circuit_breaker_info,
                'cached_status': self._connection_status_cache,
                'timestamp': time.time()
            }
        
        try:
            client = await self.get_client()
            
            # Teste básico de conectividade
            start_time = time.time()
            await asyncio.wait_for(client.ping(), timeout=2.0)
            ping_time = (time.time() - start_time) * 1000  # ms
            
            # Registrar sucesso
            self._circuit_breaker.record_success()
            self._update_connection_cache(True)
            
            # Obter informações do servidor
            info = await client.info()
            
            # Estatísticas do pool de conexões (simplificado para evitar erros)
            pool_stats = {
                'max_connections': self._connection_pool.max_connections if self._connection_pool else 0,
                'pool_active': True if self._connection_pool else False,
            }
            
            return {
                'status': 'healthy',
                'ping_time_ms': round(ping_time, 2),
                'redis_version': info.get('redis_version', 'unknown'),
                'connected_clients': info.get('connected_clients', 0),
                'used_memory': info.get('used_memory', 0),
                'used_memory_human': info.get('used_memory_human', '0B'),
                'keyspace_hits': info.get('keyspace_hits', 0),
                'keyspace_misses': info.get('keyspace_misses', 0),
                'pool_stats': pool_stats,
                'circuit_breaker': circuit_breaker_info,
                'config': {
                    'host': self._config['host'],
                    'port': self._config['port'],
                    'db': self._config['db']
                }
            }
            
        except Exception as e:
            # Registrar falha
            self._circuit_breaker.record_failure()
            self._update_connection_cache(False, str(e))
            
            logger.error(f"Redis health check failed: {str(e)}")
            return {
                'status': 'unhealthy',
                'error': str(e),
                'circuit_breaker': circuit_breaker_info,
                'cached_status': self._connection_status_cache,
                'timestamp': time.time()
            }
    
    @asynccontextmanager
    async def get_pipeline(self, transaction: bool = True):
        """
        Context manager para pipeline Redis
        
        Args:
            transaction: Se True, usa MULTI/EXEC para transações
        """
        client = await self.get_client()
        pipeline = client.pipeline(transaction=transaction)
        try:
            yield pipeline
            if transaction:
                await pipeline.execute()
        except Exception as e:
            logger.error(f"Pipeline error: {str(e)}")
            raise
        finally:
            await pipeline.reset()
    
    async def execute_with_retry(self, operation, max_retries: int = 2) -> Any:  # Reduzido de 3 para 2
        """
        Executa operação Redis com retry automático e circuit breaker
        
        Args:
            operation: Função assíncrona a ser executada
            max_retries: Número máximo de tentativas (reduzido para falhar mais rápido)
            
        Returns:
            Resultado da operação
        """
        # Verificar circuit breaker antes de tentar
        if not self._circuit_breaker.should_attempt_call():
            raise ConnectionError("Circuit breaker is OPEN - Redis operations are being blocked")
        
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                result = await operation()
                
                # Operação bem-sucedida - registrar no circuit breaker
                self._circuit_breaker.record_success()
                self._update_connection_cache(True)
                
                return result
                
            except (ConnectionError, redis.TimeoutError) as e:
                last_error = e
                
                # Registrar falha no circuit breaker
                self._circuit_breaker.record_failure()
                self._update_connection_cache(False, str(e))
                
                if attempt < max_retries:
                    # Reduzir tempo de espera para falhar mais rápido
                    wait_time = min(1.5 ** attempt, 3)  # Máximo 3 segundos
                    logger.warning(f"Redis operation failed, retrying in {wait_time:.1f}s... (attempt {attempt + 1}/{max_retries + 1})")
                    await asyncio.sleep(wait_time)
                    
                    # Verificar circuit breaker antes de tentar reconectar
                    if not self._circuit_breaker.should_attempt_call():
                        logger.warning("Circuit breaker opened during retry, stopping attempts")
                        break
                    
                    # Tentar reconectar apenas se circuit breaker permitir
                    try:
                        await self.reconnect()
                    except Exception as reconnect_error:
                        logger.error(f"Reconnection failed: {str(reconnect_error)}")
                        self._circuit_breaker.record_failure()
                else:
                    logger.error(f"Redis operation failed after {max_retries + 1} attempts: {str(e)}")
                    
            except Exception as e:
                # Para erros não relacionados à conexão, registrar falha e não fazer retry
                self._circuit_breaker.record_failure()
                self._update_connection_cache(False, str(e))
                logger.error(f"Redis operation error (no retry): {str(e)}")
                raise
        
        # Se chegou aqui, todas as tentativas falharam
        raise last_error
    
    async def reconnect(self) -> None:
        """
        Força reconexão Redis respeitando circuit breaker
        """
        # Verificar circuit breaker antes de tentar reconectar
        if not self._circuit_breaker.should_attempt_call():
            raise ConnectionError("Circuit breaker is OPEN - reconnection blocked")
        
        try:
            if self._redis_client:
                await self._redis_client.close()
            
            if self._connection_pool:
                await self._connection_pool.disconnect()
            
            # Reinicializar
            self._redis_client = None
            self._connection_pool = None
            await self.initialize()
            
            logger.info("Redis reconnection successful")
            
        except Exception as e:
            logger.error(f"Redis reconnection failed: {str(e)}")
            raise
    
    async def close(self) -> None:
        """
        Fecha conexões Redis e reseta circuit breaker
        """
        try:
            if self._redis_client:
                await self._redis_client.close()
                self._redis_client = None
            
            if self._connection_pool:
                await self._connection_pool.disconnect()
                self._connection_pool = None
            
            # Reset circuit breaker state
            self._circuit_breaker = CircuitBreaker(
                failure_threshold=3,
                recovery_timeout=30,
                success_threshold=2
            )
            
            # Clear connection cache
            self._connection_status_cache = None
            self._cache_timestamp = None
            
            logger.info("Redis connections closed and circuit breaker reset")
            
        except Exception as e:
            logger.error(f"Error closing Redis connections: {str(e)}")


# Instância global do manager
redis_manager = RedisConnectionManager()


async def get_redis_client() -> redis.Redis:
    """
    Função utilitária para obter cliente Redis
    Respeita circuit breaker para evitar tentativas desnecessárias
    
    Returns:
        Cliente Redis configurado
    
    Raises:
        ConnectionError: Se Redis não estiver disponível
    """
    return await redis_manager.get_client()


async def redis_health_check() -> Dict[str, Any]:
    """
    Função utilitária global para verificação rápida de saúde do Redis
    Pode ser chamada antes de operações Redis para evitar delays
    
    Returns:
        Dict com status de saúde
    """
    return await redis_manager.health_check()


async def is_redis_available() -> bool:
    """
    Verificação rápida se Redis está disponível
    Usa cache e circuit breaker para evitar delays
    
    Returns:
        True se Redis provavelmente está disponível
    """
    return redis_manager._is_connection_likely_available()


async def quick_redis_ping() -> bool:
    """
    Ping rápido no Redis com timeout agressivo
    Usado para decisões de fallback
    
    Returns:
        True se Redis respondeu ao ping
    """
    return await redis_manager.quick_health_check()


async def init_redis() -> None:
    """
    Inicializa Redis - chamada na inicialização da aplicação
    Falha rápido se circuit breaker estiver aberto
    """
    await redis_manager.initialize()


async def close_redis() -> None:
    """
    Fecha conexões Redis - chamada no shutdown da aplicação
    """
    await redis_manager.close()