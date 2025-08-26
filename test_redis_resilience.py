#!/usr/bin/env python3
"""
Teste das melhorias de resiliência Redis
Demonstra as funcionalidades de circuit breaker, cache e fallback rápido
"""

import asyncio
import time
from app.services.redis_connection import (
    redis_manager, 
    redis_health_check, 
    is_redis_available, 
    quick_redis_ping
)
from app.services.hybrid_mode_manager import (
    hybrid_mode_manager,
    should_use_redis_for_operation,
    get_current_operation_mode,
    enable_json_fallback_mode,
    clear_hybrid_cache
)
from loguru import logger

async def test_circuit_breaker():
    """Testa o circuit breaker"""
    logger.info("🔧 Testando Circuit Breaker...")
    
    # Verificar estado inicial
    health = await redis_health_check()
    logger.info(f"Estado inicial: {health.get('status')}")
    
    # Verificar circuit breaker
    if 'circuit_breaker' in health:
        cb_state = health['circuit_breaker']
        logger.info(f"Circuit Breaker: {cb_state['state']} (failures: {cb_state['failure_count']})")

async def test_quick_checks():
    """Testa verificações rápidas"""
    logger.info("⚡ Testando verificações rápidas...")
    
    # Teste 1: Verificação de disponibilidade (usa cache)
    start = time.time()
    available = await is_redis_available()
    cache_time = (time.time() - start) * 1000
    logger.info(f"is_redis_available(): {available} ({cache_time:.2f}ms)")
    
    # Teste 2: Ping rápido
    start = time.time()
    ping_result = await quick_redis_ping()
    ping_time = (time.time() - start) * 1000
    logger.info(f"quick_redis_ping(): {ping_result} ({ping_time:.2f}ms)")

async def test_hybrid_fallback():
    """Testa sistema híbrido com fallback"""
    logger.info("🔄 Testando sistema híbrido...")
    
    # Limpar cache para teste
    clear_hybrid_cache()
    
    operations = ["get_audios", "search", "download_progress", "notifications"]
    
    for operation in operations:
        start = time.time()
        should_use_redis = await should_use_redis_for_operation(operation)
        decision_time = (time.time() - start) * 1000
        logger.info(f"Operação '{operation}': Redis={should_use_redis} ({decision_time:.2f}ms)")
    
    # Mostrar informações do modo atual
    mode_info = get_current_operation_mode()
    logger.info(f"Modo atual: {mode_info}")

async def test_fallback_mode():
    """Testa ativação forçada do modo fallback"""
    logger.info("📱 Testando modo fallback forçado...")
    
    # Ativar fallback JSON por 10 segundos
    enable_json_fallback_mode(duration_seconds=10)
    
    # Testar operações durante fallback
    for i in range(3):
        should_use_redis = await should_use_redis_for_operation("test_fallback")
        mode_info = get_current_operation_mode()
        logger.info(f"Durante fallback: Redis={should_use_redis}, fast_fallback_active={mode_info['fast_fallback_active']}")
        await asyncio.sleep(1)

async def performance_comparison():
    """Compara performance das verificações"""
    logger.info("📊 Comparação de performance...")
    
    # Teste múltiplas verificações para medir cache
    num_tests = 10
    
    # Com cache (múltiplas verificações rápidas)
    start = time.time()
    for _ in range(num_tests):
        await is_redis_available()
    cached_time = (time.time() - start) * 1000
    
    logger.info(f"Verificações com cache ({num_tests}x): {cached_time:.2f}ms total, {cached_time/num_tests:.2f}ms média")
    
    # Teste decisão híbrida (com cache)
    start = time.time()
    for i in range(num_tests):
        await should_use_redis_for_operation(f"test_{i}")
    hybrid_time = (time.time() - start) * 1000
    
    logger.info(f"Decisões híbridas com cache ({num_tests}x): {hybrid_time:.2f}ms total, {hybrid_time/num_tests:.2f}ms média")

async def main():
    """Executa todos os testes"""
    logger.info("🚀 Iniciando testes de resiliência Redis...")
    
    try:
        # Teste 1: Circuit breaker
        await test_circuit_breaker()
        
        # Teste 2: Verificações rápidas
        await test_quick_checks()
        
        # Teste 3: Sistema híbrido
        await test_hybrid_fallback()
        
        # Teste 4: Modo fallback forçado
        await test_fallback_mode()
        
        # Teste 5: Comparação de performance
        await performance_comparison()
        
        # Health check final
        logger.info("🏥 Health check final...")
        health = await redis_health_check()
        logger.info(f"Status final: {health.get('status')}")
        
        # Health check híbrido
        hybrid_health = await hybrid_mode_manager.health_check()
        logger.info(f"Sistema híbrido: Redis={hybrid_health['redis_status']}, JSON={hybrid_health['json_operations']['status']}")
        
        if 'fallback_status' in hybrid_health:
            fallback = hybrid_health['fallback_status']
            logger.info(f"Fallback ativo: {fallback['fast_fallback_enabled']}, Modo cache: {fallback['operation_mode_cache']}")
        
    except Exception as e:
        logger.error(f"Erro durante teste: {e}")
    
    logger.success("✅ Testes de resiliência concluídos!")

if __name__ == "__main__":
    asyncio.run(main())