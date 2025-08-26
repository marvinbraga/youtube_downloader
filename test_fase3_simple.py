"""
Teste Simples - FASE 3 Implementation
Valida imports e funcionalidades basicas
"""

import sys
from pathlib import Path

# Adiciona o diretorio raiz ao path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_basic_imports():
    """Testa imports basicos"""
    print("Testando imports FASE 3...")
    
    try:
        from app.api.redis_endpoints import redis_api_endpoints, HybridResponse
        print("[OK] redis_endpoints importado")
        
        from app.api.sse_integration import redis_sse_manager
        print("[OK] sse_integration importado")
        
        from app.services.hybrid_mode_manager import hybrid_mode_manager
        print("[OK] hybrid_mode_manager importado")
        
        from app.services.api_performance_monitor import api_performance_monitor
        print("[OK] api_performance_monitor importado")
        
        from app.middleware.redis_fallback import redis_fallback_middleware
        print("[OK] redis_fallback importado")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        return False

def test_basic_functionality():
    """Testa funcionalidades basicas"""
    print("Testando funcionalidades basicas...")
    
    try:
        from app.api.redis_endpoints import HybridResponse
        
        # Testa HybridResponse
        response = HybridResponse.create_response(
            data={"test": True},
            source="test",
            performance_ms=10.0
        )
        
        assert response["data"]["test"] == True
        assert response["source"] == "test"
        print("[OK] HybridResponse funcionando")
        
        from app.services.hybrid_mode_manager import HybridConfig
        config = HybridConfig()
        assert hasattr(config, 'use_redis')
        print("[OK] HybridConfig funcionando")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        return False

if __name__ == "__main__":
    print("FASE 3 - Teste Simples de Validacao")
    print("=" * 40)
    
    tests = [test_basic_imports, test_basic_functionality]
    results = []
    
    for test in tests:
        try:
            result = test()
            results.append(result)
            print()
        except Exception as e:
            print(f"[ERROR] {e}")
            results.append(False)
    
    passed = sum(results)
    total = len(results)
    
    print("=" * 40)
    print(f"Resultados: {passed}/{total} testes passaram")
    
    if passed == total:
        print("SUCESSO: Implementacao FASE 3 validada!")
        sys.exit(0)
    else:
        print("FALHA: Alguns testes falharam")
        sys.exit(1)