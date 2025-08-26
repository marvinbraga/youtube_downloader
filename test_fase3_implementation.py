"""
Teste de Validação - FASE 3 Implementation
Valida endpoints híbridos, SSE integration e performance monitoring
"""

import asyncio
import sys
import importlib.util
from pathlib import Path

# Adiciona o diretório raiz ao path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_imports():
    """Testa se todos os imports necessários funcionam"""
    print("Testando imports dos componentes FASE 3...")
    
    try:
        # Testa redis_endpoints
        from app.api.redis_endpoints import redis_api_endpoints, HybridResponse
        print("[OK] app.api.redis_endpoints")
        
        # Testa sse_integration 
        from app.api.sse_integration import redis_sse_manager, create_progress_stream
        print("[OK] app.api.sse_integration")
        
        # Testa hybrid_mode_manager
        from app.services.hybrid_mode_manager import hybrid_mode_manager, HybridConfig
        print("[OK] app.services.hybrid_mode_manager")
        
        # Testa api_performance_monitor
        from app.services.api_performance_monitor import api_performance_monitor, PerformanceMetric
        print("[OK] app.services.api_performance_monitor")
        
        # Testa redis_fallback middleware
        from app.middleware.redis_fallback import redis_fallback_middleware
        print("[OK] app.middleware.redis_fallback")
        
        return True
        
    except ImportError as e:
        print(f"[ERROR] Erro de import: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Erro inesperado: {e}")
        return False


def test_class_instantiation():
    """Testa instanciação das classes principais"""
    print("\n[OK]� Testando instanciação das classes...")
    
    try:
        # Testa HybridResponse
        from app.api.redis_endpoints import HybridResponse
        response = HybridResponse.create_response(
            data={"test": "data"},
            source="test",
            performance_ms=10.5
        )
        assert "data" in response
        assert response["source"] == "test"
        print("[OK] HybridResponse.create_response - OK")
        
        # Testa HybridConfig
        from app.services.hybrid_mode_manager import HybridConfig
        config = HybridConfig(use_redis=True, compare_redis_json=True)
        assert config.use_redis == True
        print("[OK] HybridConfig instantiation - OK")
        
        # Testa PerformanceMetric
        from app.services.api_performance_monitor import PerformanceMetric
        from datetime import datetime
        metric = PerformanceMetric(
            endpoint="/api/test",
            method="GET",
            response_time_ms=15.5,
            status_code=200,
            source="redis",
            timestamp=datetime.now()
        )
        assert metric.is_success == True
        assert metric.is_redis == True
        print("[OK] PerformanceMetric instantiation - OK")
        
        return True
        
    except Exception as e:
        print(f"[OK] Erro na instanciação: {e}")
        return False


async def test_async_components():
    """Testa componentes assíncronos"""
    print("\n[OK]� Testando componentes assíncronos...")
    
    try:
        # Testa HybridModeManager
        from app.services.hybrid_mode_manager import hybrid_mode_manager
        
        # Testa should_use_redis
        should_use = await hybrid_mode_manager.should_use_redis("test")
        assert isinstance(should_use, bool)
        print("[OK] hybrid_mode_manager.should_use_redis - OK")
        
        # Testa health_check
        health = await hybrid_mode_manager.health_check()
        assert "timestamp" in health
        assert "hybrid_mode_active" in health
        print("[OK] hybrid_mode_manager.health_check - OK")
        
        # Testa APIPerformanceMonitor
        from app.services.api_performance_monitor import api_performance_monitor
        
        # Registra métrica de teste
        await api_performance_monitor.record_request(
            endpoint="/test",
            method="GET", 
            response_time_ms=25.0,
            status_code=200,
            source="test"
        )
        print("[OK] api_performance_monitor.record_request - OK")
        
        # Obtém estatísticas
        stats = await api_performance_monitor.get_realtime_stats(1)
        print("[OK] api_performance_monitor.get_realtime_stats - OK")
        
        # Testa health score
        health_score = await api_performance_monitor.get_system_health_score()
        assert "health_score" in health_score
        print("[OK] api_performance_monitor.get_system_health_score - OK")
        
        return True
        
    except Exception as e:
        print(f"[OK] Erro nos componentes assíncronos: {e}")
        return False


def test_configuration():
    """Testa configurações e variáveis de ambiente"""
    print("\n[OK]� Testando configurações...")
    
    try:
        from app.services.hybrid_mode_manager import hybrid_mode_manager
        
        # Testa configuração inicial
        config = hybrid_mode_manager.config
        assert hasattr(config, 'use_redis')
        assert hasattr(config, 'compare_redis_json')
        print("[OK] Configuração inicial carregada - OK")
        
        # Testa update de configuração
        original_use_redis = config.use_redis
        hybrid_mode_manager.update_config(use_redis=not original_use_redis)
        assert hybrid_mode_manager.config.use_redis == (not original_use_redis)
        
        # Restaura configuração original
        hybrid_mode_manager.update_config(use_redis=original_use_redis)
        print("[OK] Update dinâmico de configuração - OK")
        
        return True
        
    except Exception as e:
        print(f"[OK] Erro nas configurações: {e}")
        return False


def test_redis_fallback_middleware():
    """Testa middleware de fallback"""
    print("\n[OK]� Testando Redis fallback middleware...")
    
    try:
        from app.middleware.redis_fallback import redis_fallback_middleware
        
        # Testa health tracker
        health_info = redis_fallback_middleware.health_tracker.get_health_info()
        assert "failure_count" in health_info
        assert "should_use_redis" in health_info
        print("[OK] Redis health tracker - OK")
        
        # Testa middleware stats
        stats = redis_fallback_middleware.get_middleware_stats()
        assert "redis_health" in stats
        assert "middleware_info" in stats
        print("[OK] Middleware stats - OK")
        
        return True
        
    except Exception as e:
        print(f"[OK] Erro no middleware: {e}")
        return False


def test_sse_integration():
    """Testa integração SSE"""
    print("\n[OK]� Testando SSE integration...")
    
    try:
        from app.api.sse_integration import redis_sse_manager, SSEEvent
        
        # Testa SSEEvent
        event = SSEEvent(
            event_type="test",
            data={"message": "test"}
        )
        sse_format = event.to_sse_format()
        assert "event: test" in sse_format
        assert "data:" in sse_format
        print("[OK] SSEEvent creation and formatting - OK")
        
        # Testa client stats
        stats = redis_sse_manager.get_client_stats()
        assert "total_clients" in stats
        assert "max_clients" in stats
        print("[OK] SSE client stats - OK")
        
        return True
        
    except Exception as e:
        print(f"[OK] Erro na integração SSE: {e}")
        return False


async def run_all_tests():
    """Executa todos os testes"""
    print("INICIANDO TESTES DE VALIDACAO FASE 3")
    print("=" * 50)
    
    tests = [
        ("Imports", test_imports),
        ("Class Instantiation", test_class_instantiation),
        ("Async Components", test_async_components),
        ("Configuration", test_configuration),
        ("Redis Fallback Middleware", test_redis_fallback_middleware),
        ("SSE Integration", test_sse_integration)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n[OK]� Executando teste: {test_name}")
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"[OK] Falha no teste {test_name}: {e}")
            results[test_name] = False
    
    # Sumário dos resultados
    print("\n" + "=" * 50)
    print("RESUMO DOS TESTES")
    print("=" * 50)
    
    passed = 0
    failed = 0
    
    for test_name, result in results.items():
        status = "PASSOU" if result else "FALHOU"
        print(f"{test_name:<25} : {status}")
        
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\nTotal: {passed + failed} | Passou: {passed} | Falhou: {failed}")
    
    if failed == 0:
        print("\nTODOS OS TESTES PASSARAM! FASE 3 IMPLEMENTADA COM SUCESSO!")
        return True
    else:
        print(f"\n{failed} teste(s) falharam. Revise a implementacao.")
        return False


if __name__ == "__main__":
    print("YouTube Downloader - FASE 3 Validation Tests")
    print("Agent-Integration - API Endpoint Migration")
    
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n[OK][OK]  Testes interrompidos pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n[OK]� Erro crítico durante os testes: {e}")
        sys.exit(1)