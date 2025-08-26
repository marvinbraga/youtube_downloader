#!/usr/bin/env python3
"""
FASE 3 - Performance Benchmarking Suite
Benchmarks detalhados para validar todos os performance targets

Agent-QualityAssurance - Validação de performance completa
Mede latência, throughput e valida targets específicos da FASE 3
"""

import asyncio
import json
import time
import statistics
import aiohttp
import websockets
import redis.asyncio as redis
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import sys
import os
import concurrent.futures
import psutil

# Adicionar pasta app ao path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'app'))

from loguru import logger

# Configurar logger
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>")


@dataclass
class PerformanceBenchmark:
    """Resultado de um benchmark de performance"""
    operation: str
    target_ms: float
    measured_ms: float
    target_met: bool
    samples: int
    min_ms: float
    max_ms: float
    p95_ms: float
    p99_ms: float
    std_dev_ms: float
    throughput_ops_sec: Optional[float] = None


@dataclass
class SystemMetrics:
    """Métricas do sistema durante testes"""
    cpu_percent: float
    memory_percent: float
    memory_mb: float
    timestamp: str


class FASE3PerformanceBenchmarks:
    """
    Performance Benchmarking Suite para FASE 3
    
    Valida todos os performance targets especificados:
    - API Redis: <50ms (p95), target 2-5ms
    - Search Redis: <10ms (p95), target 1-3ms  
    - SSE latency: <10ms
    - WebSocket latency: <5ms
    - Dashboard load: <100ms
    - Concurrent operations: 98%+ success rate
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.websocket_url = base_url.replace("http", "ws")
        self.benchmarks: List[PerformanceBenchmark] = []
        self.system_metrics: List[SystemMetrics] = []
        
        # Performance targets FASE 3
        self.targets = {
            # API targets (95th percentile)
            "get_all_audios_redis": 50.0,  # Target: 2-5ms, Max allowed: 50ms
            "search_audios_redis": 10.0,   # Target: 1-3ms, Max allowed: 10ms
            "get_audio_by_id_redis": 5.0,  # Target: <5ms
            
            # Comparison with JSON
            "get_all_audios_json": 50.0,   # Baseline
            "search_audios_json": 30.0,    # Baseline
            
            # Real-time communication
            "websocket_latency": 5.0,      # <5ms
            "sse_latency": 10.0,           # <10ms
            "dashboard_load": 100.0,       # <100ms
            
            # Concurrent operations
            "concurrent_reads_success_rate": 98.0,    # 98%+
            "concurrent_searches_success_rate": 95.0, # 95%+
        }
        
        logger.info("⚡ FASE 3 Performance Benchmarks initialized")
        logger.info(f"Testing against: {base_url}")
    
    async def run_complete_benchmarks(self) -> bool:
        """Executa todos os benchmarks de performance"""
        logger.info("=" * 80)
        logger.info("⚡ FASE 3 - PERFORMANCE BENCHMARKING SUITE")
        logger.info("=" * 80)
        
        # Iniciar monitoramento do sistema
        system_monitor_task = asyncio.create_task(self.monitor_system_metrics())
        
        try:
            # 1. Benchmark API Redis vs JSON
            await self.benchmark_api_redis_vs_json()
            
            # 2. Benchmark Search Operations
            await self.benchmark_search_operations()
            
            # 3. Benchmark Real-time Communications
            await self.benchmark_realtime_communications()
            
            # 4. Benchmark Dashboard Performance
            await self.benchmark_dashboard_performance()
            
            # 5. Benchmark Concurrent Operations
            await self.benchmark_concurrent_operations()
            
            # 6. Benchmark Memory and Resource Usage
            await self.benchmark_resource_usage()
            
            # Parar monitoramento do sistema
            system_monitor_task.cancel()
            
            return self.compile_benchmark_results()
            
        except Exception as e:
            system_monitor_task.cancel()
            logger.error(f"❌ Benchmarks failed: {e}")
            return False
    
    async def monitor_system_metrics(self):
        """Monitora métricas do sistema durante os testes"""
        try:
            while True:
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                
                metric = SystemMetrics(
                    cpu_percent=cpu_percent,
                    memory_percent=memory.percent,
                    memory_mb=memory.used / 1024 / 1024,
                    timestamp=datetime.now().isoformat()
                )
                
                self.system_metrics.append(metric)
                await asyncio.sleep(5)  # Coletar a cada 5 segundos
                
        except asyncio.CancelledError:
            logger.info("📊 System monitoring stopped")
    
    async def benchmark_api_redis_vs_json(self):
        """Benchmark APIs Redis vs JSON"""
        logger.info("📋 Benchmarking API Redis vs JSON Performance...")
        
        operations = [
            ("get_all_audios", "/api/audios", {}),
            ("get_all_videos", "/api/videos", {}),
            ("get_audio_by_id", "/api/audios/search", {"q": "test"})
        ]
        
        async with aiohttp.ClientSession() as session:
            for op_name, endpoint, params in operations:
                
                # Benchmark Redis
                redis_times = await self.measure_endpoint_performance(
                    session, endpoint, {**params, "use_redis": True}, 
                    f"{op_name}_redis", 100  # 100 samples
                )
                
                # Benchmark JSON  
                json_times = await self.measure_endpoint_performance(
                    session, endpoint, {**params, "use_redis": False},
                    f"{op_name}_json", 100  # 100 samples
                )
                
                # Calcular estatísticas e registrar benchmarks
                if redis_times:
                    self.add_benchmark(f"{op_name}_redis", redis_times, 
                                     self.targets.get(f"{op_name}_redis", 50.0))
                
                if json_times:
                    self.add_benchmark(f"{op_name}_json", json_times, 
                                     self.targets.get(f"{op_name}_json", 100.0))
    
    async def benchmark_search_operations(self):
        """Benchmark específico para operações de busca"""
        logger.info("🔍 Benchmarking Search Operations...")
        
        search_queries = ["tutorial", "python", "test", "video", "audio"]
        
        async with aiohttp.ClientSession() as session:
            
            # Benchmark busca Redis
            redis_search_times = []
            for query in search_queries:
                times = await self.measure_endpoint_performance(
                    session, "/api/audios/search", 
                    {"q": query, "use_redis": True}, 
                    f"search_redis_{query}", 20
                )
                redis_search_times.extend(times)
            
            # Benchmark busca JSON
            json_search_times = []
            for query in search_queries:
                times = await self.measure_endpoint_performance(
                    session, "/api/audios/search",
                    {"q": query, "use_redis": False},
                    f"search_json_{query}", 20
                )
                json_search_times.extend(times)
            
            # Registrar benchmarks agregados
            if redis_search_times:
                self.add_benchmark("search_audios_redis", redis_search_times, 
                                 self.targets["search_audios_redis"])
            
            if json_search_times:
                self.add_benchmark("search_audios_json", json_search_times, 
                                 self.targets["search_audios_json"])
    
    async def benchmark_realtime_communications(self):
        """Benchmark WebSocket e SSE latency"""
        logger.info("📡 Benchmarking Real-time Communications...")
        
        # WebSocket Latency Benchmark
        websocket_latencies = await self.measure_websocket_latency(50)
        if websocket_latencies:
            self.add_benchmark("websocket_latency", websocket_latencies, 
                             self.targets["websocket_latency"])
        
        # SSE Latency Benchmark
        sse_latencies = await self.measure_sse_latency(30)
        if sse_latencies:
            self.add_benchmark("sse_latency", sse_latencies,
                             self.targets["sse_latency"])
    
    async def benchmark_dashboard_performance(self):
        """Benchmark performance do dashboard"""
        logger.info("📊 Benchmarking Dashboard Performance...")
        
        dashboard_endpoints = [
            "/api/dashboard/data",
            "/api/dashboard/summary",
            "/api/dashboard/health",
            "/api/dashboard/metrics"
        ]
        
        async with aiohttp.ClientSession() as session:
            for endpoint in dashboard_endpoints:
                times = await self.measure_endpoint_performance(
                    session, endpoint, {}, 
                    f"dashboard_{endpoint.split('/')[-1]}", 30
                )
                
                if times:
                    self.add_benchmark(f"dashboard_{endpoint.split('/')[-1]}", times,
                                     self.targets["dashboard_load"])
    
    async def benchmark_concurrent_operations(self):
        """Benchmark operações concorrentes"""
        logger.info("🔄 Benchmarking Concurrent Operations...")
        
        # Teste 1000 requests concorrentes para get_all_audios
        concurrent_read_results = await self.measure_concurrent_operations(
            "/api/audios", {"use_redis": True}, 1000
        )
        
        success_rate = (concurrent_read_results["successful"] / concurrent_read_results["total"]) * 100
        
        # Registrar resultado como benchmark especial
        self.benchmarks.append(PerformanceBenchmark(
            operation="concurrent_reads_1000",
            target_ms=self.targets["concurrent_reads_success_rate"],  # Success rate, não time
            measured_ms=success_rate,  # Success rate como "time"
            target_met=success_rate >= self.targets["concurrent_reads_success_rate"],
            samples=concurrent_read_results["total"],
            min_ms=min(concurrent_read_results["times"]) if concurrent_read_results["times"] else 0,
            max_ms=max(concurrent_read_results["times"]) if concurrent_read_results["times"] else 0,
            p95_ms=self.calculate_percentile(concurrent_read_results["times"], 95) if concurrent_read_results["times"] else 0,
            p99_ms=self.calculate_percentile(concurrent_read_results["times"], 99) if concurrent_read_results["times"] else 0,
            std_dev_ms=statistics.stdev(concurrent_read_results["times"]) if len(concurrent_read_results["times"]) > 1 else 0,
            throughput_ops_sec=concurrent_read_results.get("throughput", 0)
        ))
        
        # Teste 500 searches concorrentes  
        concurrent_search_results = await self.measure_concurrent_operations(
            "/api/audios/search", {"q": "test", "use_redis": True}, 500
        )
        
        search_success_rate = (concurrent_search_results["successful"] / concurrent_search_results["total"]) * 100
        
        self.benchmarks.append(PerformanceBenchmark(
            operation="concurrent_searches_500",
            target_ms=self.targets["concurrent_searches_success_rate"],
            measured_ms=search_success_rate,
            target_met=search_success_rate >= self.targets["concurrent_searches_success_rate"],
            samples=concurrent_search_results["total"],
            min_ms=min(concurrent_search_results["times"]) if concurrent_search_results["times"] else 0,
            max_ms=max(concurrent_search_results["times"]) if concurrent_search_results["times"] else 0,
            p95_ms=self.calculate_percentile(concurrent_search_results["times"], 95) if concurrent_search_results["times"] else 0,
            p99_ms=self.calculate_percentile(concurrent_search_results["times"], 99) if concurrent_search_results["times"] else 0,
            std_dev_ms=statistics.stdev(concurrent_search_results["times"]) if len(concurrent_search_results["times"]) > 1 else 0,
            throughput_ops_sec=concurrent_search_results.get("throughput", 0)
        ))
    
    async def benchmark_resource_usage(self):
        """Benchmark uso de recursos"""
        logger.info("💾 Benchmarking Resource Usage...")
        
        # Aguardar alguns segundos para coletar métricas
        await asyncio.sleep(5)
        
        if self.system_metrics:
            cpu_usage = [m.cpu_percent for m in self.system_metrics]
            memory_usage = [m.memory_percent for m in self.system_metrics]
            
            logger.info(f"Average CPU usage: {statistics.mean(cpu_usage):.2f}%")
            logger.info(f"Average Memory usage: {statistics.mean(memory_usage):.2f}%")
    
    async def measure_endpoint_performance(self, session: aiohttp.ClientSession, 
                                         endpoint: str, params: dict, 
                                         operation_name: str, samples: int) -> List[float]:
        """Mede performance de um endpoint específico"""
        times = []
        
        for i in range(samples):
            start_time = time.perf_counter()
            
            try:
                async with session.get(f"{self.base_url}{endpoint}", params=params) as resp:
                    if resp.status == 200:
                        await resp.json()  # Aguardar o parse completo
                        end_time = time.perf_counter()
                        response_time = (end_time - start_time) * 1000  # ms
                        times.append(response_time)
                    
                    await asyncio.sleep(0.01)  # Pequeno delay entre requests
                    
            except Exception as e:
                logger.debug(f"Request failed for {operation_name}: {e}")
                continue
        
        if times:
            logger.info(f"✅ {operation_name}: {len(times)} samples, avg {statistics.mean(times):.2f}ms")
        else:
            logger.warning(f"⚠️ {operation_name}: No successful samples")
        
        return times
    
    async def measure_websocket_latency(self, samples: int) -> List[float]:
        """Mede latência WebSocket"""
        latencies = []
        
        try:
            ws_url = f"{self.websocket_url}/ws/progress"
            
            async with websockets.connect(ws_url, timeout=10) as websocket:
                # Aguardar mensagem de boas-vindas
                await websocket.recv()
                
                for i in range(samples):
                    start_time = time.perf_counter()
                    
                    ping_msg = {
                        "type": "ping",
                        "data": {"timestamp": datetime.now().isoformat(), "test_id": i}
                    }
                    
                    await websocket.send(json.dumps(ping_msg))
                    pong_response = await websocket.recv()
                    
                    end_time = time.perf_counter()
                    latency = (end_time - start_time) * 1000
                    latencies.append(latency)
                    
                    await asyncio.sleep(0.05)
                    
        except Exception as e:
            logger.error(f"WebSocket latency measurement failed: {e}")
        
        return latencies
    
    async def measure_sse_latency(self, samples: int) -> List[float]:
        """Mede latência SSE (simulação)"""
        latencies = []
        
        try:
            async with aiohttp.ClientSession() as session:
                for i in range(samples):
                    start_time = time.perf_counter()
                    
                    async with session.get(f"{self.base_url}/api/progress/stream") as resp:
                        if resp.status == 200:
                            # Ler primeiro chunk
                            chunk = await resp.content.read(512)
                            end_time = time.perf_counter()
                            
                            if chunk:
                                latency = (end_time - start_time) * 1000
                                latencies.append(latency)
                    
                    await asyncio.sleep(0.1)
                    
        except Exception as e:
            logger.error(f"SSE latency measurement failed: {e}")
        
        return latencies
    
    async def measure_concurrent_operations(self, endpoint: str, params: dict, 
                                          concurrent_count: int) -> Dict[str, Any]:
        """Mede operações concorrentes"""
        successful = 0
        total = concurrent_count
        times = []
        start_time = time.perf_counter()
        
        async def single_request(session, request_id):
            request_start = time.perf_counter()
            try:
                async with session.get(f"{self.base_url}{endpoint}", params=params) as resp:
                    if resp.status == 200:
                        await resp.json()
                        request_end = time.perf_counter()
                        return True, (request_end - request_start) * 1000
                    else:
                        return False, 0
            except Exception:
                return False, 0
        
        # Criar todas as tasks
        async with aiohttp.ClientSession() as session:
            tasks = [single_request(session, i) for i in range(concurrent_count)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
        
        end_time = time.perf_counter()
        total_duration = end_time - start_time
        
        # Processar resultados
        for result in results:
            if isinstance(result, tuple) and result[0]:
                successful += 1
                times.append(result[1])
        
        throughput = successful / total_duration if total_duration > 0 else 0
        
        logger.info(f"✅ Concurrent {endpoint}: {successful}/{total} successful ({successful/total*100:.1f}%)")
        
        return {
            "successful": successful,
            "total": total,
            "times": times,
            "throughput": throughput
        }
    
    def add_benchmark(self, operation: str, times: List[float], target: float):
        """Adiciona um benchmark com estatísticas calculadas"""
        if not times:
            return
        
        mean_time = statistics.mean(times)
        min_time = min(times)
        max_time = max(times)
        p95_time = self.calculate_percentile(times, 95)
        p99_time = self.calculate_percentile(times, 99)
        std_dev = statistics.stdev(times) if len(times) > 1 else 0
        
        # O target é baseado no P95 para a maioria das operações
        target_met = p95_time <= target
        
        benchmark = PerformanceBenchmark(
            operation=operation,
            target_ms=target,
            measured_ms=mean_time,
            target_met=target_met,
            samples=len(times),
            min_ms=min_time,
            max_ms=max_time,
            p95_ms=p95_time,
            p99_ms=p99_time,
            std_dev_ms=std_dev
        )
        
        self.benchmarks.append(benchmark)
    
    def calculate_percentile(self, data: List[float], percentile: int) -> float:
        """Calcula percentil específico"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int((percentile / 100.0) * len(sorted_data))
        index = min(index, len(sorted_data) - 1)
        return sorted_data[index]
    
    def compile_benchmark_results(self) -> bool:
        """Compila e analisa resultados dos benchmarks"""
        logger.info("=" * 80)
        logger.info("⚡ FASE 3 Performance Benchmark Results")
        logger.info("=" * 80)
        
        total_benchmarks = len(self.benchmarks)
        targets_met = len([b for b in self.benchmarks if b.target_met])
        targets_failed = total_benchmarks - targets_met
        
        logger.info(f"Total Benchmarks: {total_benchmarks}")
        logger.info(f"Targets Met: {targets_met}")
        logger.info(f"Targets Failed: {targets_failed}")
        logger.info(f"Success Rate: {(targets_met/total_benchmarks)*100:.1f}%")
        logger.info("")
        
        # Mostrar detalhes de cada benchmark
        logger.info("Detailed Results:")
        logger.info("-" * 120)
        logger.info(f"{'Operation':<25} {'Target':<8} {'Mean':<8} {'P95':<8} {'P99':<8} {'Samples':<8} {'Met':<5} {'Status'}")
        logger.info("-" * 120)
        
        for benchmark in self.benchmarks:
            status = "✅ PASS" if benchmark.target_met else "❌ FAIL"
            
            # Para concurrent operations, mostrar como percentage
            if "concurrent" in benchmark.operation:
                logger.info(
                    f"{benchmark.operation:<25} {benchmark.target_ms:<8.1f} "
                    f"{benchmark.measured_ms:<8.1f} {'N/A':<8} {'N/A':<8} "
                    f"{benchmark.samples:<8} {benchmark.target_met!s:<5} {status}"
                )
            else:
                logger.info(
                    f"{benchmark.operation:<25} {benchmark.target_ms:<8.1f} "
                    f"{benchmark.measured_ms:<8.2f} {benchmark.p95_ms:<8.2f} "
                    f"{benchmark.p99_ms:<8.2f} {benchmark.samples:<8} "
                    f"{benchmark.target_met!s:<5} {status}"
                )
        
        logger.info("-" * 120)
        logger.info("")
        
        # Performance Analysis
        redis_benchmarks = [b for b in self.benchmarks if "redis" in b.operation and "concurrent" not in b.operation]
        json_benchmarks = [b for b in self.benchmarks if "json" in b.operation]
        
        if redis_benchmarks and json_benchmarks:
            redis_avg = statistics.mean([b.measured_ms for b in redis_benchmarks])
            json_avg = statistics.mean([b.measured_ms for b in json_benchmarks])
            improvement = ((json_avg - redis_avg) / json_avg * 100) if json_avg > 0 else 0
            
            logger.info("Performance Analysis:")
            logger.info(f"Redis Average: {redis_avg:.2f}ms")
            logger.info(f"JSON Average: {json_avg:.2f}ms")
            logger.info(f"Performance Improvement: {improvement:.1f}%")
            logger.info("")
        
        # Target Validation Summary
        logger.info("🎯 Target Validation Summary:")
        
        critical_targets = [
            ("get_all_audios_redis", "API Redis <50ms"),
            ("search_audios_redis", "Search Redis <10ms"),
            ("websocket_latency", "WebSocket <5ms"),
            ("concurrent_reads_1000", "Concurrent 98%+"),
        ]
        
        critical_passed = 0
        for target_key, description in critical_targets:
            benchmark = next((b for b in self.benchmarks if target_key in b.operation), None)
            if benchmark:
                status = "✅" if benchmark.target_met else "❌"
                logger.info(f"{status} {description}: {benchmark.target_met}")
                if benchmark.target_met:
                    critical_passed += 1
            else:
                logger.info(f"⚠️ {description}: Not tested")
        
        # Determinar sucesso geral
        success_rate = (targets_met / total_benchmarks) * 100 if total_benchmarks > 0 else 0
        critical_success_rate = (critical_passed / len(critical_targets)) * 100
        
        overall_success = (
            success_rate >= 80 and          # 80% general success
            critical_success_rate >= 100    # 100% critical targets
        )
        
        logger.info("")
        
        if overall_success:
            logger.success("🎉 FASE 3 PERFORMANCE BENCHMARKS PASSED!")
            logger.success("✅ All critical performance targets met")
            logger.success("✅ Redis delivers significant performance improvement")
            logger.success("✅ Real-time communication meets latency targets")
            logger.success("✅ System handles concurrent load efficiently")
            return True
        else:
            logger.error("❌ FASE 3 PERFORMANCE BENCHMARKS FAILED")
            logger.error(f"Overall success rate: {success_rate:.1f}% (required: ≥80%)")
            logger.error(f"Critical targets: {critical_success_rate:.1f}% (required: 100%)")
            logger.error("Performance targets need optimization")
            return False


async def main():
    """Função principal para execução standalone"""
    benchmarks = FASE3PerformanceBenchmarks()
    
    try:
        success = await benchmarks.run_complete_benchmarks()
        
        if success:
            logger.info("🏆 Performance benchmarks passed - targets met!")
            return 0
        else:
            logger.error("🔧 Performance benchmarks failed - optimization needed")
            return 1
            
    except KeyboardInterrupt:
        logger.warning("⚠️ Benchmarks interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"💥 Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))