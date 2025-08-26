"""
Benchmark de Performance - Sistema Redis vs Sistema Atual
Valida a melhoria de 100x na performance (10-50ms vs 1-2s)
"""

import asyncio
import time
import statistics
import sys
import os
from typing import List, Dict, Any
import uuid

from loguru import logger

# Adicionar path para importar módulos
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.services.redis_system_init import RedisSystemContext
from app.services.sse_redis_adapter import get_sse_manager
from app.services.sse_manager import SSEManager  # Sistema original


class PerformanceBenchmark:
    """
    Benchmark completo comparando sistema Redis vs sistema original
    Testa latência, throughput e concorrência
    """
    
    def __init__(self):
        self.results: Dict[str, List[float]] = {
            "redis_single_operation": [],
            "redis_batch_operations": [],
            "redis_concurrent_clients": [],
            "original_single_operation": [],
            "original_batch_operations": [],
            "original_concurrent_clients": []
        }
        
    async def run_full_benchmark(self) -> Dict[str, Any]:
        """Executa benchmark completo"""
        try:
            logger.info("🚀 Iniciando Benchmark de Performance")
            logger.info("=" * 60)
            
            # Benchmark do sistema Redis
            redis_results = await self._benchmark_redis_system()
            
            # Benchmark do sistema original
            original_results = await self._benchmark_original_system()
            
            # Comparar resultados
            comparison = self._compare_results(redis_results, original_results)
            
            # Relatório final
            self._generate_report(redis_results, original_results, comparison)
            
            return {
                "redis": redis_results,
                "original": original_results,
                "comparison": comparison
            }
            
        except Exception as e:
            logger.error(f"Erro no benchmark: {e}")
            raise
    
    async def _benchmark_redis_system(self) -> Dict[str, Any]:
        """Benchmark do sistema Redis"""
        logger.info("🔍 Testando Sistema Redis...")
        
        async with RedisSystemContext():
            sse_manager = await get_sse_manager()
            
            # Teste 1: Operação única
            single_times = await self._test_single_operations(sse_manager, "redis")
            
            # Teste 2: Operações em lote
            batch_times = await self._test_batch_operations(sse_manager, "redis")
            
            # Teste 3: Clientes concorrentes
            concurrent_times = await self._test_concurrent_clients(sse_manager, "redis")
            
            return {
                "single_operation": {
                    "times_ms": single_times,
                    "avg_ms": statistics.mean(single_times),
                    "median_ms": statistics.median(single_times),
                    "min_ms": min(single_times),
                    "max_ms": max(single_times),
                    "std_ms": statistics.stdev(single_times) if len(single_times) > 1 else 0
                },
                "batch_operations": {
                    "times_ms": batch_times,
                    "avg_ms": statistics.mean(batch_times),
                    "median_ms": statistics.median(batch_times),
                    "min_ms": min(batch_times),
                    "max_ms": max(batch_times),
                    "throughput_ops_sec": len(batch_times) / (sum(batch_times) / 1000)
                },
                "concurrent_clients": {
                    "times_ms": concurrent_times,
                    "avg_ms": statistics.mean(concurrent_times),
                    "median_ms": statistics.median(concurrent_times),
                    "min_ms": min(concurrent_times),
                    "max_ms": max(concurrent_times),
                    "p95_ms": self._percentile(concurrent_times, 95),
                    "p99_ms": self._percentile(concurrent_times, 99)
                }
            }
    
    async def _benchmark_original_system(self) -> Dict[str, Any]:
        """Benchmark do sistema original"""
        logger.info("🔍 Testando Sistema Original...")
        
        sse_manager = SSEManager()
        
        # Teste 1: Operação única
        single_times = await self._test_single_operations(sse_manager, "original")
        
        # Teste 2: Operações em lote
        batch_times = await self._test_batch_operations(sse_manager, "original")
        
        # Teste 3: Clientes concorrentes
        concurrent_times = await self._test_concurrent_clients(sse_manager, "original")
        
        return {
            "single_operation": {
                "times_ms": single_times,
                "avg_ms": statistics.mean(single_times),
                "median_ms": statistics.median(single_times),
                "min_ms": min(single_times),
                "max_ms": max(single_times),
                "std_ms": statistics.stdev(single_times) if len(single_times) > 1 else 0
            },
            "batch_operations": {
                "times_ms": batch_times,
                "avg_ms": statistics.mean(batch_times),
                "median_ms": statistics.median(batch_times),
                "min_ms": min(batch_times),
                "max_ms": max(batch_times),
                "throughput_ops_sec": len(batch_times) / (sum(batch_times) / 1000)
            },
            "concurrent_clients": {
                "times_ms": concurrent_times,
                "avg_ms": statistics.mean(concurrent_times),
                "median_ms": statistics.median(concurrent_times),
                "min_ms": min(concurrent_times),
                "max_ms": max(concurrent_times),
                "p95_ms": self._percentile(concurrent_times, 95),
                "p99_ms": self._percentile(concurrent_times, 99)
            }
        }
    
    async def _test_single_operations(self, sse_manager, system_type: str) -> List[float]:
        """Testa operações individuais"""
        logger.info(f"   📊 Testando operações individuais ({system_type})")
        
        times = []
        num_operations = 100
        
        for i in range(num_operations):
            audio_id = f"test_{system_type}_{i}_{uuid.uuid4().hex[:8]}"
            
            start_time = time.perf_counter()
            
            # Simular sequência completa de download
            await sse_manager.download_started(audio_id, "Teste iniciado")
            
            for progress in [25, 50, 75, 100]:
                await sse_manager.download_progress(audio_id, progress)
            
            await sse_manager.download_completed(audio_id, "Teste concluído")
            
            end_time = time.perf_counter()
            operation_time = (end_time - start_time) * 1000  # ms
            times.append(operation_time)
            
            # Log progresso a cada 25 operações
            if (i + 1) % 25 == 0:
                avg_time = statistics.mean(times[-25:])
                logger.info(f"      Progresso: {i+1}/{num_operations} | Avg últimas 25: {avg_time:.2f}ms")
        
        avg_time = statistics.mean(times)
        logger.success(f"   ✅ Operações individuais ({system_type}): {avg_time:.2f}ms média")
        
        return times
    
    async def _test_batch_operations(self, sse_manager, system_type: str) -> List[float]:
        """Testa operações em lote"""
        logger.info(f"   📊 Testando operações em lote ({system_type})")
        
        times = []
        batch_size = 50
        num_batches = 10
        
        for batch in range(num_batches):
            start_time = time.perf_counter()
            
            # Processar batch de operações
            tasks = []
            for i in range(batch_size):
                audio_id = f"batch_{system_type}_{batch}_{i}_{uuid.uuid4().hex[:8]}"
                
                # Criar task para cada operação
                task = self._single_download_sequence(sse_manager, audio_id)
                tasks.append(task)
            
            # Executar todas as operações do batch concorrentemente
            await asyncio.gather(*tasks)
            
            end_time = time.perf_counter()
            batch_time = (end_time - start_time) * 1000  # ms
            times.append(batch_time)
            
            ops_per_sec = batch_size / (batch_time / 1000)
            logger.info(f"      Batch {batch+1}/{num_batches}: {batch_time:.2f}ms | {ops_per_sec:.1f} ops/sec")
        
        avg_time = statistics.mean(times)
        total_ops = batch_size * num_batches
        total_time_sec = sum(times) / 1000
        throughput = total_ops / total_time_sec
        
        logger.success(f"   ✅ Operações em lote ({system_type}): {avg_time:.2f}ms | {throughput:.1f} ops/sec")
        
        return times
    
    async def _test_concurrent_clients(self, sse_manager, system_type: str) -> List[float]:
        """Testa múltiplos clientes concorrentes"""
        logger.info(f"   📊 Testando clientes concorrentes ({system_type})")
        
        times = []
        num_clients = 20
        operations_per_client = 10
        
        async def client_workload(client_id: int) -> List[float]:
            """Carga de trabalho por cliente"""
            client_times = []
            
            for op in range(operations_per_client):
                audio_id = f"client_{system_type}_{client_id}_op_{op}_{uuid.uuid4().hex[:8]}"
                
                start_time = time.perf_counter()
                await self._single_download_sequence(sse_manager, audio_id)
                end_time = time.perf_counter()
                
                operation_time = (end_time - start_time) * 1000  # ms
                client_times.append(operation_time)
            
            return client_times
        
        # Executar todos os clientes concorrentemente
        start_time = time.perf_counter()
        
        client_tasks = [client_workload(i) for i in range(num_clients)]
        client_results = await asyncio.gather(*client_tasks)
        
        end_time = time.perf_counter()
        total_time = (end_time - start_time) * 1000  # ms
        
        # Consolidar tempos
        for client_times in client_results:
            times.extend(client_times)
        
        avg_time = statistics.mean(times)
        total_ops = num_clients * operations_per_client
        throughput = total_ops / (total_time / 1000)
        
        logger.success(
            f"   ✅ Clientes concorrentes ({system_type}): {avg_time:.2f}ms média | "
            f"{throughput:.1f} ops/sec | {num_clients} clientes"
        )
        
        return times
    
    async def _single_download_sequence(self, sse_manager, audio_id: str):
        """Sequência única de download para testes"""
        await sse_manager.download_started(audio_id, "Teste")
        await sse_manager.download_progress(audio_id, 50)
        await sse_manager.download_completed(audio_id, "Concluído")
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calcula percentil dos dados"""
        sorted_data = sorted(data)
        index = int(len(sorted_data) * (percentile / 100.0))
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def _compare_results(
        self, 
        redis_results: Dict[str, Any], 
        original_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compara resultados entre sistemas"""
        
        comparison = {}
        
        for test_type in ["single_operation", "batch_operations", "concurrent_clients"]:
            redis_avg = redis_results[test_type]["avg_ms"]
            original_avg = original_results[test_type]["avg_ms"]
            
            improvement_ratio = original_avg / redis_avg if redis_avg > 0 else 0
            improvement_percent = ((original_avg - redis_avg) / original_avg) * 100 if original_avg > 0 else 0
            
            comparison[test_type] = {
                "redis_avg_ms": redis_avg,
                "original_avg_ms": original_avg,
                "improvement_ratio": improvement_ratio,
                "improvement_percent": improvement_percent,
                "meets_target": improvement_ratio >= 50  # 50x seria metade do objetivo de 100x
            }
        
        # Throughput comparison
        if "throughput_ops_sec" in redis_results["batch_operations"]:
            redis_throughput = redis_results["batch_operations"]["throughput_ops_sec"]
            original_throughput = original_results["batch_operations"]["throughput_ops_sec"]
            
            throughput_improvement = redis_throughput / original_throughput if original_throughput > 0 else 0
            
            comparison["throughput"] = {
                "redis_ops_sec": redis_throughput,
                "original_ops_sec": original_throughput,
                "improvement_ratio": throughput_improvement,
                "meets_target": throughput_improvement >= 50
            }
        
        return comparison
    
    def _generate_report(
        self, 
        redis_results: Dict[str, Any], 
        original_results: Dict[str, Any], 
        comparison: Dict[str, Any]
    ):
        """Gera relatório final do benchmark"""
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("📊 RELATÓRIO DE PERFORMANCE - REDIS vs ORIGINAL")
        logger.info("=" * 80)
        
        # Resumo executivo
        logger.info("\n🎯 RESUMO EXECUTIVO")
        logger.info("-" * 40)
        
        single_op_improvement = comparison["single_operation"]["improvement_ratio"]
        batch_improvement = comparison["batch_operations"]["improvement_ratio"]
        concurrent_improvement = comparison["concurrent_clients"]["improvement_ratio"]
        
        avg_improvement = (single_op_improvement + batch_improvement + concurrent_improvement) / 3
        
        target_met = avg_improvement >= 50  # 50x seria metade do objetivo
        
        status_emoji = "✅" if target_met else "⚠️"
        status_text = "OBJETIVO ATINGIDO" if target_met else "ABAIXO DO OBJETIVO"
        
        logger.info(f"{status_emoji} Status: {status_text}")
        logger.info(f"🚀 Melhoria Média: {avg_improvement:.1f}x")
        logger.info(f"🎯 Objetivo: 100x (mínimo 50x)")
        
        # Detalhes por teste
        logger.info("\n📈 DETALHES POR TESTE")
        logger.info("-" * 40)
        
        test_names = {
            "single_operation": "Operações Individuais",
            "batch_operations": "Operações em Lote", 
            "concurrent_clients": "Clientes Concorrentes"
        }
        
        for test_type, display_name in test_names.items():
            comp = comparison[test_type]
            redis_avg = comp["redis_avg_ms"]
            original_avg = comp["original_avg_ms"]
            improvement = comp["improvement_ratio"]
            meets_target = comp["meets_target"]
            
            status = "✅" if meets_target else "❌"
            
            logger.info(f"\n{status} {display_name}:")
            logger.info(f"   Redis:    {redis_avg:>8.2f}ms")
            logger.info(f"   Original: {original_avg:>8.2f}ms")
            logger.info(f"   Melhoria: {improvement:>8.1f}x ({comp['improvement_percent']:>5.1f}%)")
        
        # Throughput
        if "throughput" in comparison:
            logger.info(f"\n📊 THROUGHPUT:")
            throughput_comp = comparison["throughput"]
            redis_tps = throughput_comp["redis_ops_sec"]
            original_tps = throughput_comp["original_ops_sec"]
            tps_improvement = throughput_comp["improvement_ratio"]
            
            status = "✅" if throughput_comp["meets_target"] else "❌"
            
            logger.info(f"   {status} Redis:    {redis_tps:>8.1f} ops/sec")
            logger.info(f"   {status} Original: {original_tps:>8.1f} ops/sec")
            logger.info(f"   {status} Melhoria: {tps_improvement:>8.1f}x")
        
        # Latência P95/P99 para concorrentes
        logger.info(f"\n⏱️ LATÊNCIA (Clientes Concorrentes):")
        redis_p95 = redis_results["concurrent_clients"]["p95_ms"]
        redis_p99 = redis_results["concurrent_clients"]["p99_ms"]
        original_p95 = original_results["concurrent_clients"]["p95_ms"]
        original_p99 = original_results["concurrent_clients"]["p99_ms"]
        
        logger.info(f"   Redis P95:    {redis_p95:>8.2f}ms")
        logger.info(f"   Redis P99:    {redis_p99:>8.2f}ms")
        logger.info(f"   Original P95: {original_p95:>8.2f}ms")
        logger.info(f"   Original P99: {original_p99:>8.2f}ms")
        
        # Conclusões
        logger.info("\n🎯 CONCLUSÕES")
        logger.info("-" * 40)
        
        if avg_improvement >= 100:
            logger.success("🌟 EXCELENTE: Objetivo de 100x atingido!")
        elif avg_improvement >= 50:
            logger.success("✅ BOM: Melhoria significativa, próximo do objetivo")
        elif avg_improvement >= 10:
            logger.warning("⚠️ MODERADO: Melhoria substancial, mas abaixo do esperado")
        else:
            logger.error("❌ INSUFICIENTE: Melhoria inadequada, revisar implementação")
        
        # Recomendações
        logger.info("\n💡 PRÓXIMOS PASSOS:")
        
        if redis_results["single_operation"]["avg_ms"] > 50:
            logger.info("   • Otimizar operações individuais (target: <10ms)")
        
        if redis_results["concurrent_clients"]["p99_ms"] > 100:
            logger.info("   • Melhorar latência P99 sob carga")
        
        if comparison.get("throughput", {}).get("redis_ops_sec", 0) < 1000:
            logger.info("   • Aumentar throughput (target: >1000 ops/sec)")
        
        logger.info("   • Monitorar performance em produção")
        logger.info("   • Configurar alertas de latência")
        
        logger.info("=" * 80)


async def main():
    """Função principal do benchmark"""
    
    # Configurar logging
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level="INFO"
    )
    logger.add(
        "logs/performance_benchmark.log",
        rotation="10 MB",
        retention="3 days",
        level="DEBUG"
    )
    
    benchmark = PerformanceBenchmark()
    
    try:
        results = await benchmark.run_full_benchmark()
        
        # Salvar resultados em arquivo
        import json
        with open("benchmark_results.json", "w") as f:
            json.dump(results, f, indent=2, default=str)
        
        logger.success("✅ Benchmark concluído! Resultados salvos em benchmark_results.json")
        
        return results
        
    except Exception as e:
        logger.error(f"❌ Erro no benchmark: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())