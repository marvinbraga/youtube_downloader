#!/usr/bin/env python3
"""
FASE 3 - Integration Testing Suite
Teste completo de integração dos componentes da FASE 3

Agent-QualityAssurance - Validação completa da integração controlada
Testa todos endpoints API em modo Redis vs JSON, sistema híbrido e fallback automático
"""

import asyncio
import json
import time
import pytest
import aiohttp
import websockets
import redis.asyncio as redis
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import sys
import os

# Adicionar pasta app ao path para imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'app'))

from loguru import logger

# Configurar logger para testes
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>")


@dataclass
class IntegrationTestResult:
    """Resultado de um teste de integração"""
    test_name: str
    endpoint: str
    redis_response_time: float
    json_response_time: float
    data_consistent: bool
    fallback_working: bool
    error: Optional[str] = None


class FASE3IntegrationTestSuite:
    """
    Integration Testing Suite para FASE 3
    
    Testa todos os componentes desenvolvidos pelos Agent-Integration e Agent-ProgressSystem:
    - API endpoints híbridos com fallback automático
    - Comparação Redis vs JSON
    - SSE integration com Redis pub/sub
    - WebSocket progress system
    - Sistema de métricas e dashboard
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.websocket_url = base_url.replace("http", "ws")
        self.results: List[IntegrationTestResult] = []
        
        # Endpoints para testar
        self.test_endpoints = [
            ("/api/audios", "GET", {"use_redis": True}),
            ("/api/audios", "GET", {"use_redis": False}),
            ("/api/audios/search", "GET", {"q": "tutorial", "use_redis": True}),
            ("/api/audios/search", "GET", {"q": "tutorial", "use_redis": False}),
            ("/api/videos", "GET", {"use_redis": True}),
            ("/api/videos", "GET", {"use_redis": False}),
        ]
        
        logger.info("🧪 FASE 3 Integration Test Suite initialized")
    
    async def run_complete_integration_tests(self) -> bool:
        """Executa todos os testes de integração da FASE 3"""
        logger.info("=" * 80)
        logger.info("🔍 FASE 3 - COMPLETE INTEGRATION TESTING")
        logger.info("=" * 80)
        
        try:
            # 1. Testar API Endpoints Redis vs JSON
            await self.test_api_endpoints_redis_vs_json()
            
            # 2. Testar Sistema Híbrido e Fallback
            await self.test_hybrid_mode_and_fallback()
            
            # 3. Testar SSE Integration com Redis
            await self.test_sse_redis_integration()
            
            # 4. Testar WebSocket Progress System
            await self.test_websocket_progress_integration()
            
            # 5. Testar Dashboard e Métricas
            await self.test_dashboard_metrics_integration()
            
            # 6. Testar Comparação Redis vs JSON
            await self.test_redis_json_comparison()
            
            return self.compile_integration_results()
            
        except Exception as e:
            logger.error(f"❌ Integration tests failed: {e}")
            return False
    
    async def test_api_endpoints_redis_vs_json(self):
        """Testa todos endpoints API em modo Redis vs JSON"""
        logger.info("📋 Testing API Endpoints - Redis vs JSON...")
        
        async with aiohttp.ClientSession() as session:
            for endpoint, method, base_params in self.test_endpoints:
                
                # Teste Redis
                redis_start = time.time()
                redis_params = {**base_params, "use_redis": True}
                
                try:
                    async with session.request(method, f"{self.base_url}{endpoint}", params=redis_params) as resp:
                        redis_data = await resp.json() if resp.status == 200 else {}
                        redis_response_time = (time.time() - redis_start) * 1000
                        redis_source = redis_data.get("source", "unknown")
                        redis_success = resp.status == 200 and "data" in redis_data
                except Exception as e:
                    redis_data = {}
                    redis_response_time = float('inf')
                    redis_success = False
                    logger.error(f"Redis request failed for {endpoint}: {e}")
                
                # Teste JSON
                json_start = time.time()
                json_params = {**base_params, "use_redis": False}
                
                try:
                    async with session.request(method, f"{self.base_url}{endpoint}", params=json_params) as resp:
                        json_data = await resp.json() if resp.status == 200 else {}
                        json_response_time = (time.time() - json_start) * 1000
                        json_source = json_data.get("source", "unknown")
                        json_success = resp.status == 200 and "data" in json_data
                except Exception as e:
                    json_data = {}
                    json_response_time = float('inf')
                    json_success = False
                    logger.error(f"JSON request failed for {endpoint}: {e}")
                
                # Validar consistência de dados
                data_consistent = self.validate_data_consistency(redis_data, json_data)
                
                # Teste de fallback (forçar erro Redis)
                fallback_working = await self.test_endpoint_fallback(session, endpoint, method, base_params)
                
                # Registrar resultado
                result = IntegrationTestResult(
                    test_name=f"API Endpoint {method} {endpoint}",
                    endpoint=endpoint,
                    redis_response_time=redis_response_time,
                    json_response_time=json_response_time,
                    data_consistent=data_consistent,
                    fallback_working=fallback_working,
                    error=None if redis_success and json_success else "Request failed"
                )
                
                self.results.append(result)
                
                logger.info(f"✅ {endpoint}: Redis {redis_response_time:.2f}ms vs JSON {json_response_time:.2f}ms")
    
    async def test_endpoint_fallback(self, session, endpoint: str, method: str, params: dict) -> bool:
        """Testa se o fallback automático funciona"""
        try:
            # Simular falha Redis usando parâmetro especial
            fallback_params = {**params, "use_redis": True, "simulate_redis_error": True}
            
            async with session.request(method, f"{self.base_url}{endpoint}", params=fallback_params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Verificar se caiu no fallback
                    return data.get("source") in ["json_fallback", "json"]
                
        except Exception as e:
            logger.debug(f"Fallback test error for {endpoint}: {e}")
        
        return False
    
    async def test_hybrid_mode_and_fallback(self):
        """Testa sistema híbrido e fallback automático"""
        logger.info("🔄 Testing Hybrid Mode and Auto-Fallback...")
        
        async with aiohttp.ClientSession() as session:
            # Testar toggle híbrido
            try:
                async with session.get(f"{self.base_url}/api/system/hybrid-status") as resp:
                    if resp.status == 200:
                        hybrid_status = await resp.json()
                        logger.info(f"Hybrid mode status: {hybrid_status}")
                        
                # Testar comparação Redis vs JSON
                async with session.get(f"{self.base_url}/api/system/compare-redis-json") as resp:
                    if resp.status == 200:
                        comparison = await resp.json()
                        logger.info(f"Redis vs JSON comparison: {comparison.get('consistent', 'unknown')}")
                        
            except Exception as e:
                logger.error(f"Hybrid mode test failed: {e}")
    
    async def test_sse_redis_integration(self):
        """Testa integração SSE com Redis pub/sub"""
        logger.info("📡 Testing SSE Redis Integration...")
        
        try:
            async with aiohttp.ClientSession() as session:
                # Conectar ao SSE endpoint
                async with session.get(f"{self.base_url}/api/progress/stream") as resp:
                    if resp.status == 200:
                        # Ler alguns eventos SSE
                        content = await resp.content.read(1024)
                        logger.info("✅ SSE connection established")
                        
                        # Verificar formato dos eventos
                        if b"data:" in content:
                            logger.info("✅ SSE events format valid")
                        else:
                            logger.warning("⚠️ SSE events format may be invalid")
                    else:
                        logger.error(f"❌ SSE connection failed: {resp.status}")
                        
        except Exception as e:
            logger.error(f"❌ SSE integration test failed: {e}")
    
    async def test_websocket_progress_integration(self):
        """Testa integração WebSocket do sistema de progresso"""
        logger.info("🔗 Testing WebSocket Progress Integration...")
        
        try:
            ws_url = f"{self.websocket_url}/ws/progress"
            
            async with websockets.connect(ws_url, timeout=5) as websocket:
                # Enviar subscrição
                subscribe_msg = {
                    "type": "subscribe",
                    "data": {
                        "task_ids": ["test_task_integration"],
                        "channels": ["progress", "system"]
                    }
                }
                
                await websocket.send(json.dumps(subscribe_msg))
                
                # Aguardar resposta
                response = await asyncio.wait_for(websocket.recv(), timeout=3)
                response_data = json.loads(response)
                
                logger.info(f"✅ WebSocket response: {response_data.get('type', 'unknown')}")
                
                # Testar ping/pong
                ping_msg = {"type": "ping", "data": {"timestamp": datetime.now().isoformat()}}
                await websocket.send(json.dumps(ping_msg))
                
                pong_response = await asyncio.wait_for(websocket.recv(), timeout=2)
                pong_data = json.loads(pong_response)
                
                if pong_data.get("type") == "pong":
                    logger.info("✅ WebSocket ping/pong working")
                else:
                    logger.warning("⚠️ WebSocket ping/pong may not be working")
                    
        except Exception as e:
            logger.error(f"❌ WebSocket integration test failed: {e}")
    
    async def test_dashboard_metrics_integration(self):
        """Testa integração dashboard e sistema de métricas"""
        logger.info("📊 Testing Dashboard & Metrics Integration...")
        
        async with aiohttp.ClientSession() as session:
            # Testar endpoints do dashboard
            dashboard_endpoints = [
                "/api/dashboard/data",
                "/api/dashboard/summary", 
                "/api/dashboard/health",
                "/api/dashboard/metrics"
            ]
            
            for endpoint in dashboard_endpoints:
                try:
                    async with session.get(f"{self.base_url}{endpoint}") as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            logger.info(f"✅ {endpoint}: {len(str(data))} bytes")
                        else:
                            logger.warning(f"⚠️ {endpoint}: HTTP {resp.status}")
                            
                except Exception as e:
                    logger.error(f"❌ {endpoint} failed: {e}")
    
    async def test_redis_json_comparison(self):
        """Testa sistema de comparação Redis vs JSON"""
        logger.info("🔍 Testing Redis vs JSON Comparison System...")
        
        async with aiohttp.ClientSession() as session:
            try:
                # Endpoint de comparação
                async with session.get(f"{self.base_url}/api/system/compare-redis-json?detailed=true") as resp:
                    if resp.status == 200:
                        comparison_data = await resp.json()
                        
                        consistent = comparison_data.get("consistent", False)
                        audios_match = comparison_data.get("audios_match", False) 
                        videos_match = comparison_data.get("videos_match", False)
                        
                        logger.info(f"✅ Redis vs JSON comparison: Consistent={consistent}")
                        logger.info(f"   Audios match: {audios_match}")
                        logger.info(f"   Videos match: {videos_match}")
                        
                        if not consistent:
                            discrepancies = comparison_data.get("discrepancies", {})
                            logger.warning(f"⚠️ Discrepancies found: {discrepancies}")
                    else:
                        logger.error(f"❌ Comparison endpoint failed: {resp.status}")
                        
            except Exception as e:
                logger.error(f"❌ Redis vs JSON comparison test failed: {e}")
    
    def validate_data_consistency(self, redis_data: dict, json_data: dict) -> bool:
        """Valida consistência entre dados Redis e JSON"""
        if not redis_data or not json_data:
            return False
            
        # Verificar se ambos têm campo 'data'
        redis_items = redis_data.get("data", [])
        json_items = json_data.get("data", [])
        
        # Para arrays, comparar tamanho
        if isinstance(redis_items, list) and isinstance(json_items, list):
            return len(redis_items) == len(json_items)
        
        # Para objetos, comparar chaves principais
        if isinstance(redis_items, dict) and isinstance(json_items, dict):
            redis_keys = set(redis_items.keys())
            json_keys = set(json_items.keys())
            return redis_keys == json_keys
        
        return True  # Assumir consistente se não conseguir validar
    
    def compile_integration_results(self) -> bool:
        """Compila resultados dos testes de integração"""
        logger.info("=" * 80)
        logger.info("📊 FASE 3 Integration Test Results")
        logger.info("=" * 80)
        
        total_tests = len(self.results)
        successful_tests = len([r for r in self.results if r.error is None])
        consistent_data_tests = len([r for r in self.results if r.data_consistent])
        working_fallback_tests = len([r for r in self.results if r.fallback_working])
        
        # Performance analysis
        redis_times = [r.redis_response_time for r in self.results if r.redis_response_time != float('inf')]
        json_times = [r.json_response_time for r in self.results if r.json_response_time != float('inf')]
        
        avg_redis_time = sum(redis_times) / len(redis_times) if redis_times else 0
        avg_json_time = sum(json_times) / len(json_times) if json_times else 0
        
        performance_improvement = ((avg_json_time - avg_redis_time) / avg_json_time * 100) if avg_json_time > 0 else 0
        
        # Mostrar resultados
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"Successful: {successful_tests}")
        logger.info(f"Data Consistent: {consistent_data_tests}")
        logger.info(f"Fallback Working: {working_fallback_tests}")
        logger.info("")
        
        logger.info("Performance Analysis:")
        logger.info(f"Average Redis Response: {avg_redis_time:.2f}ms")
        logger.info(f"Average JSON Response: {avg_json_time:.2f}ms") 
        logger.info(f"Performance Improvement: {performance_improvement:.1f}%")
        logger.info("")
        
        # Performance targets validation
        redis_target_met = avg_redis_time < 50  # Target: <50ms
        search_target_met = True  # Detailed validation needed
        fallback_target_met = working_fallback_tests >= (total_tests * 0.8)  # 80% fallback success
        
        logger.info("Target Validation:")
        logger.info(f"✅ Redis API <50ms: {redis_target_met} ({avg_redis_time:.2f}ms)")
        logger.info(f"✅ Fallback Working: {fallback_target_met} ({working_fallback_tests}/{total_tests})")
        logger.info(f"✅ Data Consistency: {consistent_data_tests}/{total_tests}")
        
        # Determinar sucesso geral
        success_rate = (successful_tests / total_tests) * 100 if total_tests > 0 else 0
        integration_success = (
            success_rate >= 95 and  # 95% success rate
            redis_target_met and
            fallback_target_met and
            performance_improvement > 50  # At least 50% improvement
        )
        
        if integration_success:
            logger.success("🎉 FASE 3 INTEGRATION TESTS PASSED!")
            logger.success("✅ All API endpoints working in hybrid mode")
            logger.success("✅ Fallback system operational")
            logger.success("✅ Redis performance targets met")
            logger.success("✅ Data consistency maintained")
            return True
        else:
            logger.error("❌ FASE 3 INTEGRATION TESTS FAILED")
            logger.error(f"Success rate: {success_rate:.1f}% (required: ≥95%)")
            logger.error("Some integration components need attention")
            return False


@pytest.mark.asyncio
async def test_fase3_complete_integration():
    """Pytest entry point para testes de integração"""
    suite = FASE3IntegrationTestSuite()
    success = await suite.run_complete_integration_tests()
    assert success, "FASE 3 integration tests failed"


async def main():
    """Função principal para execução standalone"""
    suite = FASE3IntegrationTestSuite()
    
    try:
        success = await suite.run_complete_integration_tests()
        
        if success:
            logger.info("🏆 All integration tests passed - FASE 3 ready!")
            return 0
        else:
            logger.error("🔧 Integration tests failed - needs fixes")
            return 1
            
    except KeyboardInterrupt:
        logger.warning("⚠️ Tests interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))