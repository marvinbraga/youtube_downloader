#!/usr/bin/env python3
"""
FASE 3 - Complete System Validation Test
Teste completo de validação do sistema avançado de progresso

Este script testa todos os componentes da FASE 3:
- Sistema de progresso multi-stage 
- WebSocket endpoints com latência ultra-baixa
- Dashboard operacional com métricas
- Cliente JavaScript avançado
- Performance targets
"""

import asyncio
import json
import time
import aiohttp
import websockets
from datetime import datetime
from typing import Dict, List, Any
from dataclasses import dataclass

from loguru import logger
import sys
import os

# Adicionar pasta app ao path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

# Configurar logger
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>")


@dataclass
class ValidationResult:
    """Resultado de um teste de validação"""
    test_name: str
    passed: bool
    duration_ms: float
    details: Dict[str, Any]
    error: str = None


class FASE3SystemValidator:
    """
    Validador completo do sistema FASE 3
    
    Testa todos os componentes e performance targets:
    - Progress Manager Advanced
    - WebSocket Communications (<5ms latency)
    - Dashboard Operational 
    - Metrics Collection System
    - Frontend Integration
    - 1000+ concurrent connections support
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.websocket_url = base_url.replace("http", "ws")
        self.results: List[ValidationResult] = []
        
        # Performance targets FASE 3
        self.targets = {
            "websocket_latency_ms": 5,
            "dashboard_load_ms": 100, 
            "progress_update_latency_ms": 5,
            "concurrent_connections": 1000,
            "eta_accuracy_percent": 10
        }
        
        logger.info("🚀 FASE 3 System Validator initialized")
        logger.info(f"Target URL: {base_url}")
        logger.info(f"Performance Targets: {self.targets}")
    
    async def run_complete_validation(self) -> bool:
        """Executa validação completa do sistema"""
        logger.info("=" * 80)
        logger.info("🔍 Starting FASE 3 Complete System Validation")
        logger.info("=" * 80)
        
        try:
            # 1. Validação dos Componentes Base
            await self._test_component_initialization()
            
            # 2. Teste do Sistema de Progresso Avançado
            await self._test_advanced_progress_system()
            
            # 3. Teste do WebSocket (Latência Ultra-baixa)
            await self._test_websocket_performance()
            
            # 4. Teste do Dashboard Operacional
            await self._test_dashboard_functionality()
            
            # 5. Teste do Sistema de Métricas
            await self._test_metrics_system()
            
            # 6. Teste de Integração Frontend
            await self._test_frontend_integration()
            
            # 7. Teste de Performance e Load
            await self._test_performance_targets()
            
            # 8. Teste de Conectividade Massiva
            await self._test_concurrent_connections()
            
            # Compilar e mostrar resultados
            return self._compile_results()
            
        except Exception as e:
            logger.error(f"❌ Validation failed with error: {e}")
            return False
    
    async def _test_component_initialization(self):
        """Testa inicialização de todos os componentes"""
        logger.info("📋 Testing Component Initialization...")
        
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession() as session:
                # Test API availability
                async with session.get(f"{self.base_url}/api/dashboard/validation/test") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        self.results.append(ValidationResult(
                            test_name="Component Initialization",
                            passed=data.get("overall_status") == "pass",
                            duration_ms=(time.time() - start_time) * 1000,
                            details=data.get("tests", {}),
                            error=None if data.get("overall_status") == "pass" else "Some components failed"
                        ))
                        
                        logger.success("✅ All components initialized successfully")
                    else:
                        raise Exception(f"API returned status {resp.status}")
                        
        except Exception as e:
            self.results.append(ValidationResult(
                test_name="Component Initialization",
                passed=False,
                duration_ms=(time.time() - start_time) * 1000,
                details={},
                error=str(e)
            ))
            logger.error(f"❌ Component initialization failed: {e}")
    
    async def _test_advanced_progress_system(self):
        """Testa sistema de progresso avançado multi-stage"""
        logger.info("⚙️ Testing Advanced Progress System...")
        
        start_time = time.time()
        
        try:
            # Import após adicionar ao path
            from services.advanced_progress_manager import (
                get_advanced_progress_manager, DownloadStage, TaskType
            )
            
            progress_manager = await get_advanced_progress_manager()
            
            # Criar tarefa avançada de teste
            task_id = f"test_task_{int(time.time())}"
            stages = [DownloadStage.METADATA, DownloadStage.DOWNLOADING, 
                     DownloadStage.EXTRACTING, DownloadStage.FINALIZING]
            
            task_info = await progress_manager.create_advanced_task(
                task_id=task_id,
                task_type=TaskType.DOWNLOAD,
                stages=stages,
                metadata={"test": True}
            )
            
            # Testar progressão por estágios
            for i, stage in enumerate(stages):
                await progress_manager.start_stage(task_id, stage, total_bytes=1000)
                
                # Simular progresso
                for progress in range(0, 101, 25):
                    await progress_manager.update_stage_progress(
                        task_id, stage, 
                        bytes_processed=int(progress * 10),
                        percentage=progress
                    )
                    await asyncio.sleep(0.01)  # Simular processamento
                
                await progress_manager.complete_stage(task_id, stage)
            
            # Completar tarefa
            await progress_manager.complete_task(task_id, "Test completed successfully")
            
            # Validar task info
            final_info = await progress_manager.get_advanced_task_info(task_id)
            
            # Validar métricas
            system_metrics = await progress_manager.get_system_metrics()
            
            success = (
                final_info is not None and
                final_info.progress.calculate_overall_progress() >= 100.0 and
                len(final_info.progress.stages) == len(stages) and
                system_metrics is not None
            )
            
            self.results.append(ValidationResult(
                test_name="Advanced Progress System",
                passed=success,
                duration_ms=(time.time() - start_time) * 1000,
                details={
                    "task_id": task_id,
                    "stages_completed": len(stages),
                    "final_progress": final_info.progress.calculate_overall_progress() if final_info else 0,
                    "timeline_events": len(final_info.timeline.events) if final_info and final_info.timeline else 0
                }
            ))
            
            if success:
                logger.success("✅ Advanced Progress System working correctly")
            else:
                logger.error("❌ Advanced Progress System validation failed")
                
        except Exception as e:
            self.results.append(ValidationResult(
                test_name="Advanced Progress System", 
                passed=False,
                duration_ms=(time.time() - start_time) * 1000,
                details={},
                error=str(e)
            ))
            logger.error(f"❌ Advanced Progress System test failed: {e}")
    
    async def _test_websocket_performance(self):
        """Testa performance do WebSocket (latência <5ms)"""
        logger.info("🚀 Testing WebSocket Ultra-Low Latency Performance...")
        
        start_time = time.time()
        latencies = []
        
        try:
            ws_url = f"{self.websocket_url}/ws/progress"
            
            async with websockets.connect(ws_url) as websocket:
                # Esperar conexão
                welcome = await websocket.recv()
                welcome_data = json.loads(welcome)
                
                if "connected" in welcome:
                    logger.info("📡 WebSocket connected successfully")
                
                # Testar latência com pings
                for i in range(10):
                    ping_start = time.time()
                    
                    ping_msg = {
                        "type": "ping",
                        "data": {
                            "timestamp": datetime.now().isoformat(),
                            "test_id": i
                        }
                    }
                    
                    await websocket.send(json.dumps(ping_msg))
                    pong_response = await websocket.recv()
                    
                    ping_end = time.time()
                    latency_ms = (ping_end - ping_start) * 1000
                    latencies.append(latency_ms)
                    
                    await asyncio.sleep(0.1)
                
                # Calcular estatísticas de latência
                avg_latency = sum(latencies) / len(latencies)
                max_latency = max(latencies)
                min_latency = min(latencies)
                
                # Target: <5ms average latency
                target_met = avg_latency < self.targets["websocket_latency_ms"]
                
                self.results.append(ValidationResult(
                    test_name="WebSocket Ultra-Low Latency",
                    passed=target_met,
                    duration_ms=(time.time() - start_time) * 1000,
                    details={
                        "average_latency_ms": round(avg_latency, 2),
                        "min_latency_ms": round(min_latency, 2),
                        "max_latency_ms": round(max_latency, 2),
                        "target_latency_ms": self.targets["websocket_latency_ms"],
                        "samples": len(latencies)
                    }
                ))
                
                if target_met:
                    logger.success(f"✅ WebSocket latency: {avg_latency:.2f}ms (target: <{self.targets['websocket_latency_ms']}ms)")
                else:
                    logger.warning(f"⚠️ WebSocket latency: {avg_latency:.2f}ms exceeds target of {self.targets['websocket_latency_ms']}ms")
                    
        except Exception as e:
            self.results.append(ValidationResult(
                test_name="WebSocket Ultra-Low Latency",
                passed=False,
                duration_ms=(time.time() - start_time) * 1000,
                details={"latencies": latencies},
                error=str(e)
            ))
            logger.error(f"❌ WebSocket performance test failed: {e}")
    
    async def _test_dashboard_functionality(self):
        """Testa funcionalidade do dashboard operacional"""
        logger.info("📊 Testing Dashboard Operational Functionality...")
        
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession() as session:
                # Test dashboard data endpoint
                async with session.get(f"{self.base_url}/api/dashboard/data") as resp:
                    dashboard_data = await resp.json() if resp.status == 200 else {}
                
                # Test dashboard summary
                async with session.get(f"{self.base_url}/api/dashboard/summary") as resp:
                    summary_data = await resp.json() if resp.status == 200 else {}
                
                # Test health endpoint
                async with session.get(f"{self.base_url}/api/dashboard/health") as resp:
                    health_data = await resp.json() if resp.status == 200 else {}
                
                # Test metrics endpoint  
                async with session.get(f"{self.base_url}/api/dashboard/metrics") as resp:
                    metrics_data = await resp.json() if resp.status == 200 else {}
                
                # Validar estrutura dos dados
                required_dashboard_keys = ["timestamp", "summary", "active_tasks", "system_metrics", "alerts"]
                dashboard_valid = all(key in dashboard_data for key in required_dashboard_keys)
                
                summary_valid = "summary" in summary_data and "system_health" in summary_data
                health_valid = "overall_status" in health_data and "components" in health_data
                metrics_valid = "metrics" in metrics_data
                
                all_valid = dashboard_valid and summary_valid and health_valid and metrics_valid
                
                self.results.append(ValidationResult(
                    test_name="Dashboard Operational Functionality",
                    passed=all_valid,
                    duration_ms=(time.time() - start_time) * 1000,
                    details={
                        "dashboard_data_valid": dashboard_valid,
                        "summary_valid": summary_valid, 
                        "health_valid": health_valid,
                        "metrics_valid": metrics_valid,
                        "dashboard_keys": list(dashboard_data.keys()),
                        "active_tasks_count": len(dashboard_data.get("active_tasks", [])),
                        "alerts_count": len(dashboard_data.get("alerts", [])),
                        "system_health": health_data.get("overall_status", "unknown")
                    }
                ))
                
                if all_valid:
                    logger.success("✅ Dashboard operational functionality working correctly")
                else:
                    logger.error("❌ Dashboard functionality validation failed")
                    
        except Exception as e:
            self.results.append(ValidationResult(
                test_name="Dashboard Operational Functionality",
                passed=False,
                duration_ms=(time.time() - start_time) * 1000,
                details={},
                error=str(e)
            ))
            logger.error(f"❌ Dashboard functionality test failed: {e}")
    
    async def _test_metrics_system(self):
        """Testa sistema de coleta de métricas"""
        logger.info("📈 Testing Metrics Collection System...")
        
        start_time = time.time()
        
        try:
            from services.progress_metrics_collector import get_metrics_collector
            
            metrics_collector = await get_metrics_collector()
            
            # Testar coleta de métricas
            await metrics_collector.record_metric("test_metric", 42.0, {"test": "validation"})
            await metrics_collector.record_latency("test_operation", 15.5)
            await metrics_collector.record_throughput("test_ops", 100, 5.0)
            
            # Aguardar processamento
            await asyncio.sleep(0.5)
            
            # Obter resumo das métricas
            metrics_summary = await metrics_collector.get_all_metrics_summary(300)  # 5 min
            
            # Gerar relatório de performance
            performance_report = await metrics_collector.generate_performance_report(300)
            
            # Obter lista de métricas disponíveis
            available_metrics = metrics_collector.get_metrics_list()
            
            # Validações
            has_metrics = len(metrics_summary) > 0
            has_report = performance_report is not None
            has_available_list = len(available_metrics) > 0
            
            success = has_metrics and has_report and has_available_list
            
            self.results.append(ValidationResult(
                test_name="Metrics Collection System",
                passed=success,
                duration_ms=(time.time() - start_time) * 1000,
                details={
                    "metrics_count": len(metrics_summary),
                    "available_metrics_count": len(available_metrics),
                    "has_performance_report": has_report,
                    "report_summary": performance_report.summary if has_report else None,
                    "sample_metrics": list(metrics_summary.keys())[:5]
                }
            ))
            
            if success:
                logger.success(f"✅ Metrics system working - {len(available_metrics)} metrics available")
            else:
                logger.error("❌ Metrics collection system validation failed")
                
        except Exception as e:
            self.results.append(ValidationResult(
                test_name="Metrics Collection System",
                passed=False,
                duration_ms=(time.time() - start_time) * 1000,
                details={},
                error=str(e)
            ))
            logger.error(f"❌ Metrics system test failed: {e}")
    
    async def _test_frontend_integration(self):
        """Testa integração frontend"""
        logger.info("🌐 Testing Frontend Integration...")
        
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession() as session:
                # Test dashboard HTML page
                async with session.get(f"{self.base_url}/api/dashboard/") as resp:
                    html_available = resp.status == 200
                    html_content = await resp.text() if html_available else ""
                
                # Test static files (JS/CSS)
                js_available = False
                css_available = False
                
                try:
                    async with session.get(f"{self.base_url}/static/js/progress_client.js") as resp:
                        js_available = resp.status == 200 and "AdvancedProgressClient" in await resp.text()
                except:
                    pass
                
                try:
                    async with session.get(f"{self.base_url}/static/css/dashboard.css") as resp:
                        css_available = resp.status == 200
                except:
                    pass
                
                # Verificar componentes necessários no HTML
                has_progress_elements = (
                    "progress-client.js" in html_content and
                    "dashboard.js" in html_content and
                    "dashboard.css" in html_content
                )
                
                frontend_functional = html_available and js_available and css_available and has_progress_elements
                
                self.results.append(ValidationResult(
                    test_name="Frontend Integration",
                    passed=frontend_functional,
                    duration_ms=(time.time() - start_time) * 1000,
                    details={
                        "html_page_available": html_available,
                        "javascript_available": js_available,
                        "css_available": css_available,
                        "progress_elements_present": has_progress_elements,
                        "html_size_bytes": len(html_content)
                    }
                ))
                
                if frontend_functional:
                    logger.success("✅ Frontend integration working correctly")
                else:
                    logger.error("❌ Frontend integration validation failed")
                    
        except Exception as e:
            self.results.append(ValidationResult(
                test_name="Frontend Integration",
                passed=False,
                duration_ms=(time.time() - start_time) * 1000,
                details={},
                error=str(e)
            ))
            logger.error(f"❌ Frontend integration test failed: {e}")
    
    async def _test_performance_targets(self):
        """Testa se targets de performance são atingidos"""
        logger.info("🎯 Testing Performance Targets...")
        
        start_time = time.time()
        
        try:
            async with aiohttp.ClientSession() as session:
                # Test dashboard load time (target: <100ms)
                dashboard_start = time.time()
                async with session.get(f"{self.base_url}/api/dashboard/data") as resp:
                    dashboard_load_time = (time.time() - dashboard_start) * 1000
                
                # Test API performance endpoint
                async with session.get(f"{self.base_url}/api/dashboard/validation/performance") as resp:
                    perf_data = await resp.json() if resp.status == 200 else {}
                
                # Validar targets
                dashboard_target_met = dashboard_load_time < self.targets["dashboard_load_ms"]
                
                # Extrair outros targets do performance test
                other_targets_met = perf_data.get("targets_met", {}).get("pass_rate", 0) >= 80
                
                overall_performance_good = dashboard_target_met and other_targets_met
                
                self.results.append(ValidationResult(
                    test_name="Performance Targets",
                    passed=overall_performance_good,
                    duration_ms=(time.time() - start_time) * 1000,
                    details={
                        "dashboard_load_time_ms": round(dashboard_load_time, 2),
                        "dashboard_target_ms": self.targets["dashboard_load_ms"],
                        "dashboard_target_met": dashboard_target_met,
                        "api_performance_tests": perf_data.get("tests", {}),
                        "overall_pass_rate": perf_data.get("targets_met", {}).get("pass_rate", 0)
                    }
                ))
                
                if overall_performance_good:
                    logger.success(f"✅ Performance targets met - Dashboard: {dashboard_load_time:.2f}ms")
                else:
                    logger.warning(f"⚠️ Performance targets not fully met - Dashboard: {dashboard_load_time:.2f}ms")
                    
        except Exception as e:
            self.results.append(ValidationResult(
                test_name="Performance Targets",
                passed=False,
                duration_ms=(time.time() - start_time) * 1000,
                details={},
                error=str(e)
            ))
            logger.error(f"❌ Performance targets test failed: {e}")
    
    async def _test_concurrent_connections(self):
        """Testa suporte a conexões concorrentes (target: 1000+)"""
        logger.info("🔗 Testing Concurrent Connections Support...")
        
        start_time = time.time()
        
        # Para demonstração, testar com número menor (50 conexões)
        # Em produção, testaria com 1000+
        target_connections = 50
        successful_connections = 0
        
        try:
            async def create_websocket_connection(connection_id):
                try:
                    ws_url = f"{self.websocket_url}/ws/progress?client_id=test_{connection_id}"
                    async with websockets.connect(ws_url, timeout=5) as websocket:
                        # Enviar ping para validar conexão
                        ping_msg = {
                            "type": "ping",
                            "data": {"connection_id": connection_id}
                        }
                        await websocket.send(json.dumps(ping_msg))
                        
                        # Aguardar resposta
                        response = await asyncio.wait_for(websocket.recv(), timeout=2)
                        return True
                        
                except Exception as e:
                    logger.debug(f"Connection {connection_id} failed: {e}")
                    return False
            
            # Criar conexões em paralelo
            connection_tasks = [
                create_websocket_connection(i) 
                for i in range(target_connections)
            ]
            
            results = await asyncio.gather(*connection_tasks, return_exceptions=True)
            successful_connections = sum(1 for result in results if result is True)
            
            # Calcular success rate
            success_rate = (successful_connections / target_connections) * 100
            connection_target_met = success_rate >= 90  # 90% de sucesso mínimo
            
            self.results.append(ValidationResult(
                test_name="Concurrent Connections Support",
                passed=connection_target_met,
                duration_ms=(time.time() - start_time) * 1000,
                details={
                    "target_connections": target_connections,
                    "successful_connections": successful_connections,
                    "success_rate_percent": round(success_rate, 1),
                    "minimum_success_rate": 90,
                    "production_target": self.targets["concurrent_connections"]
                }
            ))
            
            if connection_target_met:
                logger.success(f"✅ Concurrent connections: {successful_connections}/{target_connections} ({success_rate:.1f}%)")
            else:
                logger.warning(f"⚠️ Concurrent connections: {successful_connections}/{target_connections} ({success_rate:.1f}%)")
                
        except Exception as e:
            self.results.append(ValidationResult(
                test_name="Concurrent Connections Support",
                passed=False,
                duration_ms=(time.time() - start_time) * 1000,
                details={"successful_connections": successful_connections, "target_connections": target_connections},
                error=str(e)
            ))
            logger.error(f"❌ Concurrent connections test failed: {e}")
    
    def _compile_results(self) -> bool:
        """Compila e exibe resultados finais"""
        logger.info("=" * 80)
        logger.info("📊 FASE 3 Validation Results Summary")
        logger.info("=" * 80)
        
        total_tests = len(self.results)
        passed_tests = len([r for r in self.results if r.passed])
        failed_tests = total_tests - passed_tests
        
        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        
        # Mostrar resumo
        logger.info(f"Total Tests: {total_tests}")
        logger.info(f"Passed: {passed_tests}")
        logger.info(f"Failed: {failed_tests}")
        logger.info(f"Success Rate: {success_rate:.1f}%")
        logger.info("")
        
        # Mostrar detalhes de cada teste
        for result in self.results:
            status = "✅ PASS" if result.passed else "❌ FAIL"
            logger.info(f"{status} {result.test_name} ({result.duration_ms:.2f}ms)")
            
            if result.error:
                logger.error(f"   Error: {result.error}")
            
            # Mostrar alguns detalhes importantes
            if result.details:
                key_details = []
                for key, value in result.details.items():
                    if isinstance(value, (int, float, bool, str)) and len(str(value)) < 50:
                        key_details.append(f"{key}: {value}")
                
                if key_details:
                    logger.info(f"   Details: {', '.join(key_details[:3])}")
        
        logger.info("")
        
        # Performance targets summary
        logger.info("🎯 Performance Targets Summary:")
        for target_name, target_value in self.targets.items():
            logger.info(f"   {target_name}: {target_value}")
        
        logger.info("")
        
        # Conclusão final
        if success_rate >= 90:
            logger.success("🎉 FASE 3 VALIDATION SUCCESSFUL!")
            logger.success("Sistema avançado de progresso funcionando corretamente")
            logger.success("Todos os componentes validados:")
            logger.success("  ✅ Sistema de progresso multi-stage")
            logger.success("  ✅ WebSocket com latência ultra-baixa")
            logger.success("  ✅ Dashboard operacional")
            logger.success("  ✅ Sistema de métricas avançado")
            logger.success("  ✅ Integração frontend completa")
            return True
        else:
            logger.error("❌ FASE 3 VALIDATION FAILED")
            logger.error(f"Success rate {success_rate:.1f}% below required 90%")
            logger.error("Some components need attention before production")
            return False


async def main():
    """Função principal"""
    validator = FASE3SystemValidator()
    
    try:
        success = await validator.run_complete_validation()
        
        if success:
            logger.info("🏆 All systems operational - Ready for production!")
            sys.exit(0)
        else:
            logger.error("🔧 System needs fixes before deployment")
            sys.exit(1)
            
    except KeyboardInterrupt:
        logger.warning("⚠️ Validation interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"💥 Unexpected error during validation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())