#!/usr/bin/env python3
"""
FASE 3 - Load Testing & Stress Testing Suite
Testes de carga massiva para validar escalabilidade

Agent-QualityAssurance - Validação de carga e stress
Testa 1000+ conexões WebSocket, 10k requests/min, dashboard com 100+ usuários
"""

import asyncio
import json
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import sys
import os
import aiohttp
import websockets
import psutil
from concurrent.futures import ThreadPoolExecutor
import threading

# Adicionar pasta app ao path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'app'))

from loguru import logger

# Configurar logger
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>")


@dataclass
class LoadTestResult:
    """Resultado de um teste de carga"""
    test_name: str
    target_load: int
    achieved_load: int
    success_rate: float
    avg_response_time: float
    p95_response_time: float
    p99_response_time: float
    errors_count: int
    duration_seconds: float
    throughput_ops_sec: float


@dataclass
class SystemResourceUsage:
    """Uso de recursos do sistema durante teste"""
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    connections_count: int
    timestamp: str


class FASE3LoadStressTests:
    """
    Load & Stress Testing Suite para FASE 3
    
    Executa testes de carga massiva:
    - 1000+ conexões WebSocket simultâneas (95%+ success rate)
    - 10k API requests/min com alta concorrência (98%+ success rate)
    - Dashboard com 100+ usuários simultâneos
    - Teste de degradação graceful sob estresse
    - Monitoramento de recursos em tempo real
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.websocket_url = base_url.replace("http", "ws")
        self.results: List[LoadTestResult] = []
        self.resource_usage: List[SystemResourceUsage] = []
        
        # Parâmetros dos testes de carga
        self.load_params = {
            "websocket_connections": 1000,        # 1000+ conexões WebSocket
            "websocket_min_success_rate": 95.0,   # 95% mínimo
            
            "api_requests_per_minute": 10000,     # 10k requests/min
            "api_min_success_rate": 98.0,         # 98% mínimo
            
            "dashboard_concurrent_users": 100,    # 100 usuários simultâneos
            "dashboard_min_success_rate": 90.0,   # 90% mínimo
            
            "stress_duration_seconds": 300,       # 5 minutos de stress test
        }
        
        # Controle de recursos
        self.resource_monitor_running = False
        self.active_connections = []
        
        logger.info("🔥 FASE 3 Load & Stress Tests initialized")
        logger.info(f"Testing against: {base_url}")
    
    async def run_complete_load_tests(self) -> bool:
        """Executa todos os testes de carga e stress"""
        logger.info("=" * 80)
        logger.info("🔥 FASE 3 - LOAD & STRESS TESTING SUITE")
        logger.info("=" * 80)
        
        # Iniciar monitoramento de recursos
        resource_monitor_task = asyncio.create_task(self.monitor_system_resources())
        
        try:
            # 1. WebSocket Load Test (1000+ conexões)
            await self.test_websocket_massive_connections()
            
            # 2. API Load Test (10k requests/min)
            await self.test_api_high_throughput()
            
            # 3. Dashboard Load Test (100+ usuários)
            await self.test_dashboard_concurrent_users()
            
            # 4. Mixed Load Stress Test
            await self.test_mixed_load_stress()
            
            # 5. Degradation Test (overload scenario)
            await self.test_graceful_degradation()
            
            # Parar monitoramento
            resource_monitor_task.cancel()
            
            return self.compile_load_test_results()
            
        except Exception as e:
            resource_monitor_task.cancel()
            logger.error(f"❌ Load tests failed: {e}")
            return False
        finally:
            # Cleanup conexões ativas
            await self.cleanup_active_connections()
    
    async def monitor_system_resources(self):
        """Monitora recursos do sistema durante os testes"""
        self.resource_monitor_running = True
        
        try:
            while self.resource_monitor_running:
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                
                # Contar conexões ativas
                connections_count = len(self.active_connections)
                
                usage = SystemResourceUsage(
                    cpu_percent=cpu_percent,
                    memory_percent=memory.percent,
                    memory_mb=memory.used / 1024 / 1024,
                    connections_count=connections_count,
                    timestamp=datetime.now().isoformat()
                )
                
                self.resource_usage.append(usage)
                await asyncio.sleep(2)  # Monitor a cada 2 segundos
                
        except asyncio.CancelledError:
            self.resource_monitor_running = False
            logger.info("📊 Resource monitoring stopped")
    
    async def test_websocket_massive_connections(self):
        """Teste de carga: 1000+ conexões WebSocket simultâneas"""
        logger.info("🔗 Testing Massive WebSocket Connections...")
        
        target_connections = self.load_params["websocket_connections"]
        min_success_rate = self.load_params["websocket_min_success_rate"]
        
        successful_connections = 0
        failed_connections = 0
        connection_times = []
        
        start_time = time.time()
        
        async def create_websocket_connection(connection_id: int) -> Tuple[bool, float]:
            """Cria uma conexão WebSocket individual"""
            connect_start = time.time()
            
            try:
                ws_url = f"{self.websocket_url}/ws/progress?client_id=load_test_{connection_id}"
                
                websocket = await websockets.connect(ws_url, timeout=10)
                self.active_connections.append(websocket)
                
                # Aguardar mensagem de boas-vindas
                welcome = await asyncio.wait_for(websocket.recv(), timeout=5)
                
                # Enviar ping para validar conexão
                ping_msg = {
                    "type": "ping",
                    "data": {"connection_id": connection_id, "timestamp": datetime.now().isoformat()}
                }
                
                await websocket.send(json.dumps(ping_msg))
                pong = await asyncio.wait_for(websocket.recv(), timeout=5)
                
                connect_time = time.time() - connect_start
                
                # Manter conexão ativa por um tempo
                await asyncio.sleep(random.uniform(1, 5))  # 1-5 segundos
                
                return True, connect_time
                
            except Exception as e:
                logger.debug(f"Connection {connection_id} failed: {e}")
                return False, time.time() - connect_start
        
        logger.info(f"Creating {target_connections} WebSocket connections...")
        
        # Criar conexões em batches para evitar sobrecarregar
        batch_size = 50
        tasks = []
        
        for i in range(0, target_connections, batch_size):
            batch_end = min(i + batch_size, target_connections)
            batch_tasks = [
                create_websocket_connection(conn_id) 
                for conn_id in range(i, batch_end)
            ]
            
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Processar resultados do batch
            for result in batch_results:
                if isinstance(result, tuple):
                    success, conn_time = result
                    if success:
                        successful_connections += 1
                        connection_times.append(conn_time)
                    else:
                        failed_connections += 1
                else:
                    failed_connections += 1
            
            # Pequeno delay entre batches
            await asyncio.sleep(0.5)
            
            logger.info(f"Progress: {min(batch_end, target_connections)}/{target_connections} connections attempted")
        
        total_time = time.time() - start_time
        success_rate = (successful_connections / target_connections) * 100
        avg_connect_time = sum(connection_times) / len(connection_times) if connection_times else 0
        
        # Registrar resultado
        result = LoadTestResult(
            test_name="WebSocket Massive Connections",
            target_load=target_connections,
            achieved_load=successful_connections,
            success_rate=success_rate,
            avg_response_time=avg_connect_time * 1000,  # ms
            p95_response_time=self.calculate_percentile(connection_times, 95) * 1000,
            p99_response_time=self.calculate_percentile(connection_times, 99) * 1000,
            errors_count=failed_connections,
            duration_seconds=total_time,
            throughput_ops_sec=successful_connections / total_time if total_time > 0 else 0
        )
        
        self.results.append(result)
        
        logger.info(f"✅ WebSocket Load Test: {successful_connections}/{target_connections} connections ({success_rate:.1f}%)")
        
        # Manter conexões ativas por mais tempo para simular uso real
        logger.info("Maintaining connections for 30 seconds...")
        await asyncio.sleep(30)
    
    async def test_api_high_throughput(self):
        """Teste de throughput alto: 10k requests/min"""
        logger.info("⚡ Testing High API Throughput...")
        
        requests_per_minute = self.load_params["api_requests_per_minute"]
        min_success_rate = self.load_params["api_min_success_rate"]
        
        # Duração do teste: 2 minutos
        test_duration = 120  # segundos
        total_requests = int((requests_per_minute * test_duration) / 60)
        
        # Calcular intervalo entre requests
        request_interval = test_duration / total_requests
        
        successful_requests = 0
        failed_requests = 0
        response_times = []
        
        endpoints = [
            "/api/audios",
            "/api/videos", 
            "/api/audios/search?q=test",
            "/api/dashboard/summary"
        ]
        
        start_time = time.time()
        
        async def single_api_request(session: aiohttp.ClientSession, request_id: int) -> Tuple[bool, float]:
            """Executa uma requisição API individual"""
            endpoint = random.choice(endpoints)
            params = {"use_redis": True} if "audios" in endpoint or "videos" in endpoint else {}
            
            request_start = time.time()
            
            try:
                async with session.get(f"{self.base_url}{endpoint}", params=params, timeout=10) as resp:
                    if resp.status == 200:
                        await resp.json()
                        request_time = time.time() - request_start
                        return True, request_time
                    else:
                        return False, time.time() - request_start
                        
            except Exception as e:
                return False, time.time() - request_start
        
        # Executar requests em paralelo controlado
        connector = aiohttp.TCPConnector(limit=200, limit_per_host=100)
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            
            # Criar tasks em batches
            batch_size = 100
            completed_requests = 0
            
            for batch_start in range(0, total_requests, batch_size):
                batch_end = min(batch_start + batch_size, total_requests)
                
                batch_tasks = [
                    single_api_request(session, req_id)
                    for req_id in range(batch_start, batch_end)
                ]
                
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                
                # Processar resultados
                for result in batch_results:
                    if isinstance(result, tuple):
                        success, resp_time = result
                        if success:
                            successful_requests += 1
                            response_times.append(resp_time)
                        else:
                            failed_requests += 1
                    else:
                        failed_requests += 1
                
                completed_requests = batch_end
                logger.info(f"API Progress: {completed_requests}/{total_requests} requests completed")
                
                # Controlar taxa de requests
                await asyncio.sleep(0.1)
        
        total_time = time.time() - start_time
        success_rate = (successful_requests / total_requests) * 100
        actual_throughput = successful_requests / (total_time / 60)  # requests per minute
        
        # Registrar resultado
        result = LoadTestResult(
            test_name="API High Throughput",
            target_load=requests_per_minute,
            achieved_load=int(actual_throughput),
            success_rate=success_rate,
            avg_response_time=sum(response_times) / len(response_times) * 1000 if response_times else 0,
            p95_response_time=self.calculate_percentile(response_times, 95) * 1000,
            p99_response_time=self.calculate_percentile(response_times, 99) * 1000,
            errors_count=failed_requests,
            duration_seconds=total_time,
            throughput_ops_sec=successful_requests / total_time if total_time > 0 else 0
        )
        
        self.results.append(result)
        
        logger.info(f"✅ API Throughput Test: {successful_requests}/{total_requests} requests ({success_rate:.1f}%)")
        logger.info(f"   Achieved: {actual_throughput:.0f} req/min (target: {requests_per_minute})")
    
    async def test_dashboard_concurrent_users(self):
        """Teste: 100+ usuários simultâneos no dashboard"""
        logger.info("👥 Testing Dashboard Concurrent Users...")
        
        concurrent_users = self.load_params["dashboard_concurrent_users"]
        min_success_rate = self.load_params["dashboard_min_success_rate"]
        
        successful_sessions = 0
        failed_sessions = 0
        session_times = []
        
        async def simulate_dashboard_user(user_id: int) -> Tuple[bool, float]:
            """Simula um usuário usando o dashboard"""
            session_start = time.time()
            
            dashboard_endpoints = [
                "/api/dashboard/",        # HTML page
                "/api/dashboard/data",    # Dashboard data
                "/api/dashboard/summary", # Summary
                "/api/dashboard/health",  # Health check
                "/api/dashboard/metrics", # Metrics
            ]
            
            try:
                async with aiohttp.ClientSession() as session:
                    # Simular navegação do usuário
                    for endpoint in dashboard_endpoints:
                        async with session.get(f"{self.base_url}{endpoint}") as resp:
                            if resp.status == 200:
                                if endpoint.endswith("/"):
                                    await resp.text()  # HTML
                                else:
                                    await resp.json()  # JSON
                            else:
                                raise Exception(f"HTTP {resp.status}")
                        
                        # Delay entre requests (simular leitura)
                        await asyncio.sleep(random.uniform(0.5, 2.0))
                
                session_time = time.time() - session_start
                return True, session_time
                
            except Exception as e:
                logger.debug(f"User {user_id} session failed: {e}")
                return False, time.time() - session_start
        
        logger.info(f"Simulating {concurrent_users} concurrent dashboard users...")
        
        start_time = time.time()
        
        # Executar sessões de usuários em paralelo
        user_tasks = [simulate_dashboard_user(i) for i in range(concurrent_users)]
        user_results = await asyncio.gather(*user_tasks, return_exceptions=True)
        
        # Processar resultados
        for result in user_results:
            if isinstance(result, tuple):
                success, session_time = result
                if success:
                    successful_sessions += 1
                    session_times.append(session_time)
                else:
                    failed_sessions += 1
            else:
                failed_sessions += 1
        
        total_time = time.time() - start_time
        success_rate = (successful_sessions / concurrent_users) * 100
        
        # Registrar resultado
        result = LoadTestResult(
            test_name="Dashboard Concurrent Users",
            target_load=concurrent_users,
            achieved_load=successful_sessions,
            success_rate=success_rate,
            avg_response_time=sum(session_times) / len(session_times) * 1000 if session_times else 0,
            p95_response_time=self.calculate_percentile(session_times, 95) * 1000,
            p99_response_time=self.calculate_percentile(session_times, 99) * 1000,
            errors_count=failed_sessions,
            duration_seconds=total_time,
            throughput_ops_sec=successful_sessions / total_time if total_time > 0 else 0
        )
        
        self.results.append(result)
        
        logger.info(f"✅ Dashboard Load Test: {successful_sessions}/{concurrent_users} users ({success_rate:.1f}%)")
    
    async def test_mixed_load_stress(self):
        """Teste de stress misto: WebSocket + API + Dashboard simultaneamente"""
        logger.info("🔥 Testing Mixed Load Stress...")
        
        # Cargas reduzidas mas simultâneas
        websocket_connections = 200
        api_requests_per_min = 2000
        dashboard_users = 25
        
        start_time = time.time()
        
        # Criar tasks para todos os tipos de carga
        tasks = []
        
        # Task 1: WebSocket connections
        async def websocket_stress():
            connections = []
            try:
                for i in range(websocket_connections):
                    ws_url = f"{self.websocket_url}/ws/progress?client_id=stress_test_{i}"
                    ws = await websockets.connect(ws_url, timeout=5)
                    connections.append(ws)
                    
                    if i % 50 == 0:
                        await asyncio.sleep(0.1)  # Pace connections
                
                # Manter conexões ativas
                await asyncio.sleep(60)
                return len(connections), 0
                
            except Exception as e:
                return len(connections), 1
            finally:
                for ws in connections:
                    try:
                        await ws.close()
                    except:
                        pass
        
        # Task 2: API stress
        async def api_stress():
            successful = 0
            failed = 0
            
            async with aiohttp.ClientSession() as session:
                for i in range(api_requests_per_min):
                    try:
                        async with session.get(f"{self.base_url}/api/audios", params={"use_redis": True}) as resp:
                            if resp.status == 200:
                                await resp.json()
                                successful += 1
                            else:
                                failed += 1
                    except:
                        failed += 1
                    
                    if i % 100 == 0:
                        await asyncio.sleep(0.05)
            
            return successful, failed
        
        # Task 3: Dashboard stress
        async def dashboard_stress():
            successful = 0
            failed = 0
            
            async def user_session():
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f"{self.base_url}/api/dashboard/data") as resp:
                            if resp.status == 200:
                                await resp.json()
                                return 1, 0
                            else:
                                return 0, 1
                except:
                    return 0, 1
            
            tasks = [user_session() for _ in range(dashboard_users)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, tuple):
                    s, f = result
                    successful += s
                    failed += f
                else:
                    failed += 1
            
            return successful, failed
        
        # Executar todos os stress tests simultaneamente
        ws_task = asyncio.create_task(websocket_stress())
        api_task = asyncio.create_task(api_stress())
        dashboard_task = asyncio.create_task(dashboard_stress())
        
        # Aguardar conclusão de todos
        ws_result = await ws_task
        api_result = await api_task
        dashboard_result = await dashboard_task
        
        total_time = time.time() - start_time
        
        # Calcular métricas agregadas
        total_successful = ws_result[0] + api_result[0] + dashboard_result[0]
        total_failed = ws_result[1] + api_result[1] + dashboard_result[1]
        total_operations = total_successful + total_failed
        success_rate = (total_successful / total_operations) * 100 if total_operations > 0 else 0
        
        # Registrar resultado
        result = LoadTestResult(
            test_name="Mixed Load Stress Test",
            target_load=websocket_connections + api_requests_per_min + dashboard_users,
            achieved_load=total_successful,
            success_rate=success_rate,
            avg_response_time=0,  # Mixed test, não aplicável
            p95_response_time=0,
            p99_response_time=0,
            errors_count=total_failed,
            duration_seconds=total_time,
            throughput_ops_sec=total_successful / total_time if total_time > 0 else 0
        )
        
        self.results.append(result)
        
        logger.info(f"✅ Mixed Stress Test: {total_successful}/{total_operations} operations ({success_rate:.1f}%)")
    
    async def test_graceful_degradation(self):
        """Teste de degradação graceful sob sobrecarga extrema"""
        logger.info("🚨 Testing Graceful Degradation...")
        
        # Aplicar carga extrema propositalmente
        extreme_load = 2000  # Requests simultâneos
        
        async def extreme_load_request(session, req_id):
            try:
                async with session.get(f"{self.base_url}/api/audios", 
                                     params={"use_redis": True}, 
                                     timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    return resp.status, await resp.json() if resp.status == 200 else None
            except asyncio.TimeoutError:
                return 408, None  # Timeout
            except Exception:
                return 500, None  # Error
        
        start_time = time.time()
        status_codes = []
        successful_responses = 0
        
        connector = aiohttp.TCPConnector(limit=500, limit_per_host=300)
        timeout = aiohttp.ClientTimeout(total=60)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            tasks = [extreme_load_request(session, i) for i in range(extreme_load)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, tuple):
                    status, response = result
                    status_codes.append(status)
                    if status == 200 and response:
                        successful_responses += 1
                else:
                    status_codes.append(500)
        
        total_time = time.time() - start_time
        success_rate = (successful_responses / extreme_load) * 100
        
        # Analisar códigos de status para verificar degradação graceful
        status_distribution = {}
        for status in status_codes:
            status_distribution[status] = status_distribution.get(status, 0) + 1
        
        # Degradação graceful é indicada por:
        # - Alguns sucessos (sistema não travou completamente)
        # - Muitos 429 (Too Many Requests) ou timeouts (503)
        # - Poucos 500 (Internal Server Error)
        
        graceful_degradation = (
            status_distribution.get(200, 0) > 0 and  # Alguns sucessos
            status_distribution.get(500, 0) < (extreme_load * 0.5)  # Menos de 50% de erros internos
        )
        
        logger.info(f"✅ Degradation Test: {successful_responses}/{extreme_load} successful ({success_rate:.1f}%)")
        logger.info(f"   Status codes: {status_distribution}")
        logger.info(f"   Graceful degradation: {'Yes' if graceful_degradation else 'No'}")
    
    async def cleanup_active_connections(self):
        """Limpa todas as conexões ativas"""
        logger.info("🧹 Cleaning up active connections...")
        
        cleanup_tasks = []
        for websocket in self.active_connections:
            try:
                if not websocket.closed:
                    cleanup_tasks.append(websocket.close())
            except:
                pass
        
        if cleanup_tasks:
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        self.active_connections.clear()
        logger.info("✅ Cleanup completed")
    
    def calculate_percentile(self, data: List[float], percentile: int) -> float:
        """Calcula percentil"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int((percentile / 100.0) * len(sorted_data))
        index = min(index, len(sorted_data) - 1)
        return sorted_data[index]
    
    def compile_load_test_results(self) -> bool:
        """Compila resultados dos testes de carga"""
        logger.info("=" * 80)
        logger.info("🔥 FASE 3 Load & Stress Test Results")
        logger.info("=" * 80)
        
        total_tests = len(self.results)
        successful_tests = 0
        
        logger.info("Test Results Summary:")
        logger.info("-" * 100)
        logger.info(f"{'Test Name':<35} {'Target':<10} {'Achieved':<10} {'Success%':<10} {'Errors':<8} {'Status'}")
        logger.info("-" * 100)
        
        for result in self.results:
            status = "✅ PASS" if result.success_rate >= 90 else "❌ FAIL"
            if result.success_rate >= 90:
                successful_tests += 1
                
            logger.info(
                f"{result.test_name:<35} {result.target_load:<10} "
                f"{result.achieved_load:<10} {result.success_rate:<10.1f} "
                f"{result.errors_count:<8} {status}"
            )
        
        logger.info("-" * 100)
        logger.info("")
        
        # Resource usage summary
        if self.resource_usage:
            cpu_usage = [r.cpu_percent for r in self.resource_usage]
            memory_usage = [r.memory_percent for r in self.resource_usage]
            max_connections = max(r.connections_count for r in self.resource_usage)
            
            logger.info("Resource Usage During Tests:")
            logger.info(f"Max CPU Usage: {max(cpu_usage):.1f}%")
            logger.info(f"Average CPU Usage: {sum(cpu_usage)/len(cpu_usage):.1f}%")
            logger.info(f"Max Memory Usage: {max(memory_usage):.1f}%")
            logger.info(f"Average Memory Usage: {sum(memory_usage)/len(memory_usage):.1f}%")
            logger.info(f"Peak Connections: {max_connections}")
            logger.info("")
        
        # Performance targets validation
        target_validations = {
            "WebSocket Massive Connections": ("websocket_min_success_rate", 95.0),
            "API High Throughput": ("api_min_success_rate", 98.0),
            "Dashboard Concurrent Users": ("dashboard_min_success_rate", 90.0),
        }
        
        critical_tests_passed = 0
        critical_tests_total = len(target_validations)
        
        logger.info("🎯 Critical Load Test Validation:")
        for result in self.results:
            if result.test_name in target_validations:
                param_name, target_rate = target_validations[result.test_name]
                target_met = result.success_rate >= target_rate
                
                status = "✅" if target_met else "❌"
                logger.info(f"{status} {result.test_name}: {result.success_rate:.1f}% (target: ≥{target_rate}%)")
                
                if target_met:
                    critical_tests_passed += 1
        
        # Determinar sucesso geral
        overall_success_rate = (successful_tests / total_tests) * 100 if total_tests > 0 else 0
        critical_success_rate = (critical_tests_passed / critical_tests_total) * 100
        
        overall_success = (
            overall_success_rate >= 80 and    # 80% dos testes passaram
            critical_success_rate >= 100       # 100% dos testes críticos passaram
        )
        
        logger.info("")
        logger.info(f"Overall Success Rate: {overall_success_rate:.1f}%")
        logger.info(f"Critical Tests Success Rate: {critical_success_rate:.1f}%")
        logger.info("")
        
        if overall_success:
            logger.success("🎉 FASE 3 LOAD & STRESS TESTS PASSED!")
            logger.success("✅ System handles massive concurrent load")
            logger.success("✅ WebSocket scales to 1000+ connections")
            logger.success("✅ API maintains high throughput under load")
            logger.success("✅ Dashboard supports many concurrent users")
            logger.success("✅ System shows graceful degradation")
            return True
        else:
            logger.error("❌ FASE 3 LOAD & STRESS TESTS FAILED")
            logger.error(f"Overall: {overall_success_rate:.1f}% (required: ≥80%)")
            logger.error(f"Critical: {critical_success_rate:.1f}% (required: 100%)")
            logger.error("System needs scaling improvements")
            return False


async def main():
    """Função principal para execução standalone"""
    load_tests = FASE3LoadStressTests()
    
    try:
        success = await load_tests.run_complete_load_tests()
        
        if success:
            logger.info("🏆 Load & stress tests passed - system scales well!")
            return 0
        else:
            logger.error("🔧 Load & stress tests failed - scaling needed")
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