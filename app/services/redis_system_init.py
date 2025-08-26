"""
Inicialização do Sistema Redis - FASE 2
Integra todos os componentes Redis de forma coordenada
"""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime

from loguru import logger

from .redis_connection import init_redis, close_redis, redis_manager, quick_redis_ping, is_redis_available
from .redis_progress_manager import init_progress_manager, close_progress_manager
from .redis_notifications import init_notification_manager, close_notification_manager
from .sse_redis_adapter import init_sse_redis_adapter, close_sse_redis_adapter, get_sse_manager
from .download_tracker import init_download_tracker


class RedisSystemManager:
    """
    Gerenciador central do sistema Redis
    Coordena inicialização, saúde e shutdown de todos os componentes
    """
    
    def __init__(self):
        self._initialized = False
        self._components_status: Dict[str, Dict[str, Any]] = {}
        self._startup_time: Optional[str] = None
        self._health_check_interval = 60  # 60 segundos
        self._health_task: Optional[asyncio.Task] = None
        self._redis_ever_connected = False  # Track se Redis já foi conectado alguma vez
        
    async def initialize(self) -> bool:
        """
        Inicializa todo o sistema Redis com verificação rápida inicial
        
        Returns:
            True se inicialização foi bem-sucedida
        """
        try:
            self._startup_time = datetime.now().isoformat()
            
            # 0. Verificação rápida ANTES de inicializar completamente
            logger.info("Executando verificação rápida do Redis...")
            redis_quick_available = await self._quick_redis_check()
            
            if not redis_quick_available:
                logger.warning("Redis não está disponível - sistema continuará sem Redis")
                # Não falha completamente, mas indica que Redis não está disponível
                self._components_status["Redis Connection"] = {
                    "status": "unavailable",
                    "error": "Redis not reachable in quick check",
                    "checked_at": datetime.now().isoformat(),
                    "error_count": 1
                }
                return True  # Sistema continua sem Redis
            
            # 1. Inicializar conexão Redis (base) - apenas se passou na verificação rápida
            await self._init_component("Redis Connection", init_redis)
            self._redis_ever_connected = True
            
            # 2. Testar conectividade completa
            await self._verify_redis_connection()
            
            # 3. Inicializar componentes em paralelo (independentes)
            await asyncio.gather(
                self._init_component("Progress Manager", init_progress_manager),
                self._init_component("Notification Manager", init_notification_manager),
                return_exceptions=True
            )
            
            # 4. Inicializar componentes dependentes
            await self._init_component("SSE Redis Adapter", init_sse_redis_adapter)
            
            # 5. Inicializar serviços de aplicação
            await self._init_component("Download Tracker", init_download_tracker)
            
            # 6. Iniciar monitoramento de saúde
            self._health_task = asyncio.create_task(self._health_monitor())
            
            # 7. Executar teste de integração (apenas se Redis foi conectado)
            if self._redis_ever_connected:
                await self._integration_test()
            
            self._initialized = True
            
            logger.success("Sistema Redis inicializado com sucesso")
            return True
            
        except Exception as e:
            logger.error(f"Erro na inicialização do sistema Redis: {e}")
            
            # Só executa limpeza de emergência se Redis foi conectado
            if self._redis_ever_connected:
                await self._emergency_cleanup()
            else:
                logger.info("Pulando limpeza de emergência - Redis nunca foi conectado")
            
            return False
    
    async def _init_component(self, name: str, init_func) -> bool:
        """Inicializa componente individual com tracking"""
        try:
            start_time = asyncio.get_event_loop().time()
            
            await init_func()
            
            init_time = (asyncio.get_event_loop().time() - start_time) * 1000  # ms
            
            self._components_status[name] = {
                "status": "healthy",
                "initialized_at": datetime.now().isoformat(),
                "init_time_ms": round(init_time, 2),
                "last_health_check": datetime.now().isoformat(),
                "error_count": 0
            }
            
            return True
            
        except Exception as e:
            self._components_status[name] = {
                "status": "failed",
                "error": str(e),
                "failed_at": datetime.now().isoformat(),
                "error_count": 1
            }
            
            logger.error(f"Erro ao inicializar {name}: {e}")
            raise
    
    async def _quick_redis_check(self) -> bool:
        """
        Verificação rápida se Redis está disponível
        Evita delays longos no startup se Redis não estiver rodando
        
        Returns:
            True se Redis parece disponível
        """
        try:
            # Primeira verificação usando cache/circuit breaker
            if not await is_redis_available():
                logger.debug("Redis marcado como indisponível no cache")
                return False
            
            # Ping rápido com timeout agressivo
            ping_result = await quick_redis_ping()
            if ping_result:
                logger.debug("Redis respondeu ao ping rápido")
                return True
            else:
                logger.debug("Redis não respondeu ao ping rápido")
                return False
            
        except Exception as e:
            logger.debug(f"Erro na verificação rápida do Redis: {e}")
            return False
    
    async def _verify_redis_connection(self):
        """Verifica conectividade completa com Redis"""
        try:
            health = await redis_manager.health_check()
            
            if health['status'] not in ['healthy']:
                # Permite circuit_breaker_open como status válido para continuação
                if health['status'] == 'circuit_breaker_open':
                    logger.warning("Redis circuit breaker está aberto, mas sistema continuará")
                    return
                
                raise Exception(f"Redis não está saudável: {health}")
            
            logger.debug("Verificação completa do Redis bem-sucedida")
            
        except Exception as e:
            logger.error(f"Falha na verificação do Redis: {e}")
            raise
    
    async def _integration_test(self):
        """Executa teste de integração básico - apenas se Redis estiver disponível"""
        try:
            # Verificar se Redis ainda está disponível antes do teste
            if not await is_redis_available():
                logger.info("Pulando teste de integração - Redis não disponível")
                return
            
            logger.debug("Executando teste de integração...")
            
            # Teste do SSE Manager
            sse_manager = await get_sse_manager()
            
            # Simular conexão de cliente
            test_client_id = f"test_client_{int(asyncio.get_event_loop().time())}"
            queue = await sse_manager.connect(test_client_id)
            
            # Simular evento de download
            await sse_manager.download_started("test_audio_123", "Teste de integração")
            await sse_manager.download_progress("test_audio_123", 50, "Meio do teste")
            await sse_manager.download_completed("test_audio_123", "Teste concluído")
            
            # Desconectar cliente de teste
            sse_manager.disconnect(test_client_id)
            
            logger.debug("Teste de integração concluído com sucesso")
            
        except Exception as e:
            logger.error(f"Teste de integração falhou: {e}")
            # Não falhar a inicialização por causa do teste
    
    async def _health_monitor(self):
        """Monitor contínuo de saúde do sistema"""
        try:
            while True:
                await asyncio.sleep(self._health_check_interval)
                await self._check_system_health()
                
        except asyncio.CancelledError:
            logger.info("Monitor de saúde cancelado")
        except Exception as e:
            logger.error(f"Erro no monitor de saúde: {e}")
    
    async def _check_system_health(self):
        """Verifica saúde de todos os componentes com verificação rápida"""
        try:
            # Verificação rápida antes da completa
            if not await is_redis_available():
                if "Redis Connection" in self._components_status:
                    self._components_status["Redis Connection"]["status"] = "unavailable_cached"
                    self._components_status["Redis Connection"]["last_health_check"] = datetime.now().isoformat()
                return
            
            # Verificar Redis com health check completo
            redis_health = await redis_manager.health_check()
            
            if redis_health['status'] in ['healthy']:
                if "Redis Connection" in self._components_status:
                    self._components_status["Redis Connection"]["status"] = "healthy"
                    self._components_status["Redis Connection"]["last_health_check"] = datetime.now().isoformat()
                    if 'ping_time_ms' in redis_health:
                        self._components_status["Redis Connection"]["ping_time_ms"] = redis_health['ping_time_ms']
            elif redis_health['status'] == 'circuit_breaker_open':
                if "Redis Connection" in self._components_status:
                    self._components_status["Redis Connection"]["status"] = "circuit_breaker_open"
                    self._components_status["Redis Connection"]["last_health_check"] = datetime.now().isoformat()
            else:
                logger.warning(f"Redis health check falhou: {redis_health.get('status')}")
                if "Redis Connection" in self._components_status:
                    self._components_status["Redis Connection"]["status"] = "unhealthy"
                    self._components_status["Redis Connection"]["error_count"] = self._components_status["Redis Connection"].get("error_count", 0) + 1
            
            # Log periódico de saúde (apenas se houver problemas)
            unhealthy_components = [
                name for name, status in self._components_status.items() 
                if status.get('status') not in ['healthy', 'circuit_breaker_open']
            ]
            
            if unhealthy_components:
                logger.warning(f"Componentes não saudáveis: {unhealthy_components}")
            
        except Exception as e:
            logger.error(f"Erro na verificação de saúde: {e}")
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Obtém status completo do sistema"""
        try:
            # Status geral
            healthy_count = len([c for c in self._components_status.values() if c.get('status') == 'healthy'])
            total_count = len(self._components_status)
            
            # Estatísticas detalhadas
            stats = {}
            
            try:
                sse_manager = await get_sse_manager()
                stats = await sse_manager.get_detailed_statistics()
            except Exception as e:
                logger.warning(f"Erro ao obter estatísticas detalhadas: {e}")
            
            # Redis health
            try:
                redis_health = await redis_manager.health_check()
            except Exception as e:
                redis_health = {"status": "error", "error": str(e)}
            
            return {
                "initialized": self._initialized,
                "startup_time": self._startup_time,
                "system_health": {
                    "status": "healthy" if healthy_count == total_count else "degraded",
                    "healthy_components": healthy_count,
                    "total_components": total_count,
                    "uptime_seconds": (
                        (datetime.now() - datetime.fromisoformat(self._startup_time)).total_seconds()
                        if self._startup_time else 0
                    )
                },
                "components": self._components_status,
                "redis": redis_health,
                "statistics": stats,
                "performance": {
                    "target_latency_ms": 10,
                    "target_throughput": "1000+ ops/sec",
                    "expected_improvement": "100x vs sistema atual"
                }
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter status do sistema: {e}")
            return {
                "initialized": self._initialized,
                "error": str(e),
                "components": self._components_status
            }
    
    async def _emergency_cleanup(self):
        """Limpeza de emergência em caso de falha - apenas se Redis foi conectado"""
        try:
            # Só executa limpeza se Redis foi conectado pelo menos uma vez
            if not self._redis_ever_connected:
                logger.info("Pulando limpeza de emergência - Redis nunca foi conectado nesta sessão")
                return
            
            logger.warning("🚨 Executando limpeza de emergência...")
            
            # Cancelar health monitor
            if self._health_task:
                self._health_task.cancel()
                try:
                    await self._health_task
                except asyncio.CancelledError:
                    pass
            
            # Tentar fechar componentes em ordem reversa - apenas os que foram inicializados
            cleanup_tasks = []
            
            # Verificar quais componentes foram realmente inicializados
            initialized_components = [
                name for name, status in self._components_status.items() 
                if status.get('status') in ['healthy', 'unhealthy']  # Foram pelo menos tentados
            ]
            
            logger.info(f"Limpando componentes inicializados: {initialized_components}")
            
            if "Download Tracker" in initialized_components:
                # Download tracker não tem método close específico
                pass
            
            if "SSE Redis Adapter" in initialized_components:
                cleanup_tasks.append(("SSE Redis Adapter", close_sse_redis_adapter()))
            
            if "Notification Manager" in initialized_components:
                cleanup_tasks.append(("Notification Manager", close_notification_manager()))
            
            if "Progress Manager" in initialized_components:
                cleanup_tasks.append(("Progress Manager", close_progress_manager()))
            
            if "Redis Connection" in initialized_components:
                cleanup_tasks.append(("Redis Connection", close_redis()))
            
            # Executar limpeza com timeout e tratamento individual
            if cleanup_tasks:
                for component_name, task in cleanup_tasks:
                    try:
                        await asyncio.wait_for(task, timeout=5.0)  # Timeout menor por componente
                        logger.debug(f"Componente {component_name} limpo com sucesso")
                    except Exception as e:
                        logger.warning(f"Erro ao limpar {component_name}: {e}")
            
            logger.info("Limpeza de emergência concluída")
            
        except Exception as e:
            logger.error(f"Erro na limpeza de emergência: {e}")
    
    async def shutdown(self):
        """Shutdown gracioso do sistema"""
        try:
            
            # Cancelar health monitor
            if self._health_task:
                self._health_task.cancel()
                try:
                    await self._health_task
                except asyncio.CancelledError:
                    pass
            
            # Fechar componentes em ordem reversa da inicialização
            shutdown_sequence = [
                ("Download Tracker", None),  # Sem método close específico
                ("SSE Redis Adapter", close_sse_redis_adapter),
                ("Notification Manager", close_notification_manager),
                ("Progress Manager", close_progress_manager),
                ("Redis Connection", close_redis),
            ]
            
            for component_name, close_func in shutdown_sequence:
                if component_name in self._components_status:
                    try:
                        if close_func:
                            await close_func()
                        
                        self._components_status[component_name]["status"] = "shutdown"
                        self._components_status[component_name]["shutdown_at"] = datetime.now().isoformat()
                        
                        
                    except Exception as e:
                        logger.error(f"Erro ao fechar {component_name}: {e}")
            
            self._initialized = False
            self._redis_ever_connected = False  # Reset connection tracking
            
            
        except Exception as e:
            logger.error(f"Erro no shutdown: {e}")
    
    def is_healthy(self) -> bool:
        """Verifica se o sistema está saudável"""
        if not self._initialized:
            return False
        
        # Considerar componentes saudáveis ou com circuit breaker aberto (mas funcional)
        healthy_count = len([
            c for c in self._components_status.values() 
            if c.get('status') in ['healthy', 'circuit_breaker_open', 'unavailable_cached']
        ])
        total_count = len(self._components_status)
        
        # Considerar saudável se pelo menos 80% dos componentes estão OK
        # ou se Redis nunca foi conectado (operação apenas JSON)
        if not self._redis_ever_connected and total_count == 0:
            return True  # Sistema funcionando apenas com JSON
        
        return (healthy_count / total_count) >= 0.8 if total_count > 0 else False


# Instância global
redis_system_manager = RedisSystemManager()


async def init_redis_system() -> bool:
    """Inicializa todo o sistema Redis"""
    return await redis_system_manager.initialize()


async def get_redis_system_status() -> Dict[str, Any]:
    """Obtém status do sistema Redis"""
    return await redis_system_manager.get_system_status()


async def shutdown_redis_system():
    """Encerra sistema Redis"""
    await redis_system_manager.shutdown()


def is_redis_system_healthy() -> bool:
    """Verifica se sistema está saudável"""
    return redis_system_manager.is_healthy()


# Hook para integração com FastAPI
async def lifespan_startup():
    """Hook de startup para FastAPI - não falha se Redis indisponível"""
    success = await init_redis_system()
    
    # Mudamos para não falhar criticamente se Redis não estiver disponível
    # O sistema pode operar sem Redis usando fallback JSON
    if not success:
        logger.warning("Sistema Redis não foi inicializado, mas aplicação continuará com fallback JSON")
        # Não lançar RuntimeError - permitir que aplicação continue
    
    return success


async def lifespan_shutdown():
    """Hook de shutdown para FastAPI"""
    await shutdown_redis_system()


# Exemplo de uso com contexto
class RedisSystemContext:
    """Context manager para uso em testes"""
    
    async def __aenter__(self):
        success = await init_redis_system()
        if not success:
            raise RuntimeError("Falha na inicialização do sistema Redis")
        return redis_system_manager
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await shutdown_redis_system()


# Função de teste
async def test_redis_system():
    """Teste completo do sistema Redis"""
    
    async with RedisSystemContext() as system:
        logger.info("🧪 Executando teste completo do sistema...")
        
        # Verificar status
        status = await system.get_system_status()
        logger.info(f"Status: {status['system_health']['status']}")
        
        # Simular operações
        sse_manager = await get_sse_manager()
        
        # Conectar cliente
        client_id = "test_client_full"
        await sse_manager.connect(client_id)
        
        # Simular download
        await sse_manager.download_started("test_audio_full", "Teste completo")
        
        for i in range(0, 101, 20):
            await sse_manager.download_progress("test_audio_full", i)
            await asyncio.sleep(0.1)
        
        await sse_manager.download_completed("test_audio_full")
        
        # Desconectar
        sse_manager.disconnect(client_id)
        


if __name__ == "__main__":
    # Executar teste
    asyncio.run(test_redis_system())