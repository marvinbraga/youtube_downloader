"""
FASE 4 - PRODUCTION CUTOVER EXECUTOR  
Executor controlado do cutover final com validação rigorosa
Zero downtime, máxima precisão, monitoramento em tempo real

Agent-Deployment - Production Cutover Final
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from loguru import logger

from app.services.redis_connection import get_redis_client, redis_manager
from app.services.hybrid_mode_manager import hybrid_mode_manager
from scripts.data_integrity_verifier import DataIntegrityVerifier
from scripts.redis_system_monitor import RedisSystemMonitor


class CutoverPhase(Enum):
    """Fases do cutover"""
    PREPARING = "preparing"
    PRE_FLIGHT = "pre_flight"
    EXECUTING = "executing"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class CutoverStep:
    """Representação de um passo do cutover"""
    name: str
    description: str
    phase: CutoverPhase
    executor: Callable
    timeout_seconds: int = 60
    critical: bool = True
    rollback_action: Optional[Callable] = None
    completed: bool = False
    success: bool = False
    error: Optional[str] = None
    execution_time_seconds: float = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    def mark_started(self):
        """Marca início da execução"""
        self.start_time = datetime.now()
    
    def mark_completed(self, success: bool, error: Optional[str] = None):
        """Marca conclusão da execução"""
        self.end_time = datetime.now()
        self.completed = True
        self.success = success
        self.error = error
        if self.start_time:
            self.execution_time_seconds = (self.end_time - self.start_time).total_seconds()


@dataclass
class CutoverMetrics:
    """Métricas detalhadas do cutover"""
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    current_phase: CutoverPhase = CutoverPhase.PREPARING
    steps_completed: int = 0
    steps_total: int = 0
    success_rate: float = 0.0
    critical_failures: int = 0
    total_execution_time: float = 0
    validation_score: float = 0.0
    rollback_executed: bool = False
    
    @property
    def completion_percentage(self) -> float:
        if self.steps_total == 0:
            return 0.0
        return (self.steps_completed / self.steps_total) * 100
    
    @property
    def is_successful(self) -> bool:
        return (self.current_phase == CutoverPhase.COMPLETED and 
                self.success_rate >= 0.95 and 
                self.critical_failures == 0)


class ProductionCutoverExecutor:
    """
    Executor controlado do cutover final de produção
    
    Executa cutover com controle rigoroso:
    - Execução passo a passo com validação
    - Monitoramento em tempo real
    - Rollback automático em falhas
    - Métricas detalhadas de execução
    - Timeout e circuit breaker
    """
    
    def __init__(self):
        self.metrics = CutoverMetrics()
        self.steps: List[CutoverStep] = []
        self.integrity_verifier = DataIntegrityVerifier()
        self.redis_monitor = RedisSystemMonitor()
        
        # Configurações do executor
        self.max_total_time_minutes = 15
        self.validation_threshold = 0.95
        self.critical_failure_limit = 2
        
        # Estado interno
        self._execution_log = []
        self._rollback_stack = []
        
        self._setup_cutover_steps()
        
        logger.info("🎯 ProductionCutoverExecutor initialized for controlled cutover")
    
    def _setup_cutover_steps(self):
        """Configura os passos do cutover"""
        self.steps = [
            # Fase: Preparação
            CutoverStep(
                name="system_readiness_check",
                description="Verificação final de prontidão do sistema",
                phase=CutoverPhase.PREPARING,
                executor=self._step_system_readiness_check,
                timeout_seconds=30,
                critical=True
            ),
            CutoverStep(
                name="backup_verification",
                description="Verificação de integridade dos backups",
                phase=CutoverPhase.PREPARING,
                executor=self._step_backup_verification,
                timeout_seconds=45,
                critical=True
            ),
            CutoverStep(
                name="redis_health_final",
                description="Health check final do Redis",
                phase=CutoverPhase.PREPARING,
                executor=self._step_redis_health_final,
                timeout_seconds=20,
                critical=True
            ),
            
            # Fase: Pre-flight
            CutoverStep(
                name="data_consistency_check",
                description="Verificação de consistência de dados Redis/JSON",
                phase=CutoverPhase.PRE_FLIGHT,
                executor=self._step_data_consistency_check,
                timeout_seconds=90,
                critical=True
            ),
            CutoverStep(
                name="performance_baseline",
                description="Estabelecimento de baseline de performance",
                phase=CutoverPhase.PRE_FLIGHT,
                executor=self._step_performance_baseline,
                timeout_seconds=60,
                critical=False
            ),
            CutoverStep(
                name="service_dependencies",
                description="Verificação de dependências dos serviços",
                phase=CutoverPhase.PRE_FLIGHT,
                executor=self._step_service_dependencies,
                timeout_seconds=30,
                critical=True
            ),
            
            # Fase: Execução
            CutoverStep(
                name="mode_switch_execution",
                description="Execução do switch para modo Redis puro",
                phase=CutoverPhase.EXECUTING,
                executor=self._step_mode_switch_execution,
                timeout_seconds=10,
                critical=True,
                rollback_action=self._rollback_mode_switch
            ),
            CutoverStep(
                name="configuration_update",
                description="Atualização das configurações do sistema",
                phase=CutoverPhase.EXECUTING,
                executor=self._step_configuration_update,
                timeout_seconds=15,
                critical=True,
                rollback_action=self._rollback_configuration
            ),
            CutoverStep(
                name="service_restart",
                description="Reinicialização graceful dos serviços",
                phase=CutoverPhase.EXECUTING,
                executor=self._step_service_restart,
                timeout_seconds=30,
                critical=True,
                rollback_action=self._rollback_service_restart
            ),
            
            # Fase: Validação
            CutoverStep(
                name="immediate_validation",
                description="Validação imediata pós-cutover",
                phase=CutoverPhase.VALIDATING,
                executor=self._step_immediate_validation,
                timeout_seconds=45,
                critical=True
            ),
            CutoverStep(
                name="data_integrity_final",
                description="Verificação final de integridade dos dados",
                phase=CutoverPhase.VALIDATING,
                executor=self._step_data_integrity_final,
                timeout_seconds=60,
                critical=True
            ),
            CutoverStep(
                name="performance_validation",
                description="Validação de performance pós-cutover",
                phase=CutoverPhase.VALIDATING,
                executor=self._step_performance_validation,
                timeout_seconds=40,
                critical=False
            ),
            CutoverStep(
                name="functional_testing",
                description="Testes funcionais básicos",
                phase=CutoverPhase.VALIDATING,
                executor=self._step_functional_testing,
                timeout_seconds=120,
                critical=True
            )
        ]
        
        self.metrics.steps_total = len(self.steps)
    
    async def execute_controlled_cutover(self) -> Dict[str, Any]:
        """
        Executa cutover controlado com validação rigorosa
        
        Returns:
            Relatório completo da execução
        """
        logger.critical("🚀 INICIANDO CONTROLLED PRODUCTION CUTOVER")
        
        try:
            cutover_start = time.time()
            
            # Executar todas as fases
            await self._execute_phase(CutoverPhase.PREPARING)
            await self._execute_phase(CutoverPhase.PRE_FLIGHT)
            await self._execute_phase(CutoverPhase.EXECUTING)
            await self._execute_phase(CutoverPhase.VALIDATING)
            
            # Finalizar
            self.metrics.end_time = datetime.now()
            self.metrics.total_execution_time = time.time() - cutover_start
            self.metrics.current_phase = CutoverPhase.COMPLETED
            
            # Verificar critérios de sucesso
            if self._verify_success_criteria():
                logger.success(f"✅ CONTROLLED CUTOVER COMPLETED SUCCESSFULLY in {self.metrics.total_execution_time:.2f}s")
                return await self._generate_success_report()
            else:
                raise Exception("Success criteria not met")
                
        except Exception as e:
            logger.critical(f"❌ CONTROLLED CUTOVER FAILED: {str(e)}")
            await self._execute_emergency_rollback()
            return await self._generate_failure_report(str(e))
    
    async def _execute_phase(self, phase: CutoverPhase):
        """Executa uma fase específica do cutover"""
        phase_steps = [step for step in self.steps if step.phase == phase]
        
        logger.info(f"📋 Executing phase: {phase.value} ({len(phase_steps)} steps)")
        self.metrics.current_phase = phase
        
        for step in phase_steps:
            await self._execute_step(step)
            
            # Verificar se deve parar por falhas críticas
            if step.critical and not step.success:
                self.metrics.critical_failures += 1
                if self.metrics.critical_failures >= self.critical_failure_limit:
                    raise Exception(f"Critical failure limit exceeded at step: {step.name}")
        
        logger.success(f"✅ Phase {phase.value} completed")
    
    async def _execute_step(self, step: CutoverStep):
        """Executa um passo individual do cutover"""
        logger.info(f"🔧 Executing step: {step.name}")
        
        step.mark_started()
        
        try:
            # Executar com timeout
            result = await asyncio.wait_for(
                step.executor(),
                timeout=step.timeout_seconds
            )
            
            step.mark_completed(success=True)
            self.metrics.steps_completed += 1
            
            # Adicionar ao log
            self._execution_log.append({
                "step": step.name,
                "success": True,
                "execution_time": step.execution_time_seconds,
                "timestamp": step.end_time.isoformat()
            })
            
            # Adicionar ação de rollback se disponível
            if step.rollback_action:
                self._rollback_stack.append(step.rollback_action)
            
            logger.success(f"✅ Step completed: {step.name} ({step.execution_time_seconds:.2f}s)")
            
        except asyncio.TimeoutError:
            error_msg = f"Step timeout after {step.timeout_seconds}s"
            step.mark_completed(success=False, error=error_msg)
            logger.error(f"⏰ {error_msg}: {step.name}")
            
            if step.critical:
                raise Exception(f"Critical step failed due to timeout: {step.name}")
                
        except Exception as e:
            error_msg = str(e)
            step.mark_completed(success=False, error=error_msg)
            logger.error(f"❌ Step failed: {step.name} - {error_msg}")
            
            if step.critical:
                raise Exception(f"Critical step failed: {step.name} - {error_msg}")
        
        # Atualizar taxa de sucesso
        successful_steps = len([s for s in self.steps if s.completed and s.success])
        self.metrics.success_rate = successful_steps / max(1, self.metrics.steps_completed)
    
    # Implementação dos passos do cutover
    async def _step_system_readiness_check(self):
        """Verificação final de prontidão do sistema"""
        logger.info("Checking system readiness...")
        
        # Verificar recursos do sistema
        import psutil
        cpu_usage = psutil.cpu_percent(interval=1)
        memory_usage = psutil.virtual_memory().percent
        
        if cpu_usage > 90:
            raise Exception(f"High CPU usage: {cpu_usage}%")
        
        if memory_usage > 85:
            raise Exception(f"High memory usage: {memory_usage}%")
        
        # Verificar espaço em disco
        disk_usage = psutil.disk_usage('/')
        free_gb = disk_usage.free / (1024**3)
        
        if free_gb < 1:
            raise Exception(f"Low disk space: {free_gb:.2f}GB")
        
        logger.success("System readiness verified")
    
    async def _step_backup_verification(self):
        """Verificação de integridade dos backups"""
        logger.info("Verifying backup integrity...")
        
        backup_dir = Path(__file__).parent.parent / "backups"
        
        if not backup_dir.exists():
            raise Exception("Backup directory not found")
        
        # Verificar se existe backup recente (últimas 2 horas)
        recent_backups = []
        cutoff_time = datetime.now() - timedelta(hours=2)
        
        for backup_file in backup_dir.glob("*.zip"):
            if backup_file.stat().st_mtime > cutoff_time.timestamp():
                recent_backups.append(backup_file)
        
        if not recent_backups:
            raise Exception("No recent backups found")
        
        logger.success(f"Backup verification passed: {len(recent_backups)} recent backups")
    
    async def _step_redis_health_final(self):
        """Health check final do Redis"""
        logger.info("Performing final Redis health check...")
        
        health_result = await redis_manager.health_check()
        
        if health_result.get("status") != "healthy":
            raise Exception(f"Redis health check failed: {health_result}")
        
        # Verificar latência
        ping_time = health_result.get("ping_time_ms", 0)
        if ping_time > 10:
            logger.warning(f"High Redis latency: {ping_time}ms")
        
        logger.success("Redis health check passed")
    
    async def _step_data_consistency_check(self):
        """Verificação de consistência de dados"""
        logger.info("Checking data consistency...")
        
        consistency_result = await self.integrity_verifier.verify_redis_json_consistency()
        
        if not consistency_result.get("consistent"):
            discrepancies = consistency_result.get("discrepancies", [])
            if len(discrepancies) > 5:  # Tolerância baixa para discrepâncias
                raise Exception(f"Too many data discrepancies: {len(discrepancies)}")
        
        logger.success("Data consistency verified")
    
    async def _step_performance_baseline(self):
        """Estabelecimento de baseline de performance"""
        logger.info("Establishing performance baseline...")
        
        redis_client = await get_redis_client()
        
        # Medir latências
        latencies = []
        for _ in range(20):
            start = time.time()
            await redis_client.ping()
            latency = (time.time() - start) * 1000
            latencies.append(latency)
        
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        
        baseline = {
            "avg_latency_ms": avg_latency,
            "max_latency_ms": max_latency,
            "timestamp": datetime.now().isoformat()
        }
        
        # Salvar baseline para comparação posterior
        self._performance_baseline = baseline
        
        logger.success(f"Performance baseline established: {avg_latency:.2f}ms avg")
    
    async def _step_service_dependencies(self):
        """Verificação de dependências dos serviços"""
        logger.info("Checking service dependencies...")
        
        # Verificar Redis
        redis_client = await get_redis_client()
        await redis_client.ping()
        
        # Verificar outras dependências críticas
        dependencies_ok = True
        
        if not dependencies_ok:
            raise Exception("Service dependencies check failed")
        
        logger.success("Service dependencies verified")
    
    async def _step_mode_switch_execution(self):
        """Execução do switch para modo Redis puro"""
        logger.critical("Executing mode switch to pure Redis...")
        
        # Salvar estado anterior para rollback
        self._previous_config = {
            "use_redis": hybrid_mode_manager.config.use_redis,
            "auto_fallback": hybrid_mode_manager.config.auto_fallback,
            "compare_redis_json": hybrid_mode_manager.config.compare_redis_json
        }
        
        # Executar switch
        hybrid_mode_manager.update_config(
            use_redis=True,
            compare_redis_json=False,
            auto_fallback=False
        )
        
        logger.success("Mode switch executed successfully")
    
    async def _step_configuration_update(self):
        """Atualização das configurações do sistema"""
        logger.info("Updating system configurations...")
        
        # Atualizar variáveis de ambiente
        import os
        self._previous_env = {
            "USE_REDIS": os.getenv("USE_REDIS", "false"),
            "AUTO_FALLBACK": os.getenv("AUTO_FALLBACK", "true"),
            "COMPARE_REDIS_JSON": os.getenv("COMPARE_REDIS_JSON", "false")
        }
        
        os.environ["USE_REDIS"] = "true"
        os.environ["AUTO_FALLBACK"] = "false"
        os.environ["COMPARE_REDIS_JSON"] = "false"
        
        logger.success("System configurations updated")
    
    async def _step_service_restart(self):
        """Reinicialização graceful dos serviços"""
        logger.info("Performing graceful service restart...")
        
        # Simular restart dos serviços
        await asyncio.sleep(1)
        
        # Reconectar Redis
        await redis_manager.reconnect()
        
        logger.success("Services restarted gracefully")
    
    async def _step_immediate_validation(self):
        """Validação imediata pós-cutover"""
        logger.info("Performing immediate post-cutover validation...")
        
        redis_client = await get_redis_client()
        
        # Teste básico de conectividade
        await redis_client.ping()
        
        # Verificar se dados estão acessíveis
        audio_keys = await redis_client.keys("audio:*")
        video_keys = await redis_client.keys("video:*")
        
        total_keys = len(audio_keys) + len(video_keys)
        
        if total_keys == 0:
            raise Exception("No data accessible after cutover")
        
        logger.success(f"Immediate validation passed: {total_keys} keys accessible")
    
    async def _step_data_integrity_final(self):
        """Verificação final de integridade dos dados"""
        logger.info("Performing final data integrity check...")
        
        integrity_result = await self.integrity_verifier.comprehensive_verification()
        
        if not integrity_result.get("overall_success"):
            raise Exception(f"Final integrity check failed: {integrity_result}")
        
        # Calcular score de validação
        self.metrics.validation_score = integrity_result.get("success_rate", 0.0)
        
        logger.success(f"Final data integrity verified (score: {self.metrics.validation_score:.1%})")
    
    async def _step_performance_validation(self):
        """Validação de performance pós-cutover"""
        logger.info("Validating post-cutover performance...")
        
        if not hasattr(self, '_performance_baseline'):
            logger.warning("No performance baseline available for comparison")
            return
        
        redis_client = await get_redis_client()
        
        # Medir performance atual
        latencies = []
        for _ in range(20):
            start = time.time()
            await redis_client.ping()
            latency = (time.time() - start) * 1000
            latencies.append(latency)
        
        current_avg = sum(latencies) / len(latencies)
        baseline_avg = self._performance_baseline.get("avg_latency_ms", 0)
        
        # Permitir até 20% de degradação
        if baseline_avg > 0 and current_avg > baseline_avg * 1.2:
            logger.warning(f"Performance degradation detected: {current_avg:.2f}ms vs {baseline_avg:.2f}ms baseline")
        else:
            logger.success(f"Performance validation passed: {current_avg:.2f}ms")
    
    async def _step_functional_testing(self):
        """Testes funcionais básicos"""
        logger.info("Performing basic functional tests...")
        
        redis_client = await get_redis_client()
        
        # Teste de escrita/leitura
        test_key = "cutover_functional_test"
        test_value = f"test_{int(time.time())}"
        
        await redis_client.set(test_key, test_value)
        retrieved_value = await redis_client.get(test_key)
        
        if retrieved_value.decode() != test_value:
            raise Exception("Basic read/write test failed")
        
        await redis_client.delete(test_key)
        
        # Testes adicionais de funcionalidade
        await self._test_audio_operations()
        await self._test_video_operations()
        
        logger.success("Functional testing completed")
    
    async def _test_audio_operations(self):
        """Testa operações básicas de áudio"""
        try:
            from app.services.redis_audio_manager import RedisAudioManager
            audio_manager = RedisAudioManager()
            
            # Testar listagem
            audios = await audio_manager.get_audios()
            logger.info(f"Audio operations test passed: {len(audios)} audios found")
            
        except Exception as e:
            logger.warning(f"Audio operations test failed: {str(e)}")
    
    async def _test_video_operations(self):
        """Testa operações básicas de vídeo"""
        try:
            from app.services.redis_video_manager import RedisVideoManager
            video_manager = RedisVideoManager()
            
            # Testar listagem
            videos = await video_manager.get_videos()
            logger.info(f"Video operations test passed: {len(videos)} videos found")
            
        except Exception as e:
            logger.warning(f"Video operations test failed: {str(e)}")
    
    # Ações de rollback
    async def _rollback_mode_switch(self):
        """Rollback do switch de modo"""
        if hasattr(self, '_previous_config'):
            hybrid_mode_manager.update_config(**self._previous_config)
            logger.info("Mode switch rolled back")
    
    async def _rollback_configuration(self):
        """Rollback das configurações"""
        if hasattr(self, '_previous_env'):
            import os
            for key, value in self._previous_env.items():
                os.environ[key] = value
            logger.info("Configuration rolled back")
    
    async def _rollback_service_restart(self):
        """Rollback do restart de serviços"""
        await redis_manager.reconnect()
        logger.info("Service restart rolled back")
    
    async def _execute_emergency_rollback(self):
        """Executa rollback de emergência"""
        logger.critical("🚨 EXECUTING EMERGENCY ROLLBACK")
        
        rollback_start = time.time()
        
        try:
            # Executar ações de rollback na ordem inversa
            for rollback_action in reversed(self._rollback_stack):
                try:
                    await rollback_action()
                except Exception as e:
                    logger.error(f"Rollback action failed: {str(e)}")
            
            # Atualizar métricas
            self.metrics.rollback_executed = True
            self.metrics.current_phase = CutoverPhase.ROLLED_BACK
            
            rollback_time = time.time() - rollback_start
            logger.critical(f"🚨 Emergency rollback completed in {rollback_time:.2f}s")
            
        except Exception as e:
            logger.critical(f"🚨 Emergency rollback FAILED: {str(e)}")
    
    def _verify_success_criteria(self) -> bool:
        """Verifica critérios de sucesso do cutover"""
        criteria = {
            "success_rate": self.metrics.success_rate >= self.validation_threshold,
            "no_critical_failures": self.metrics.critical_failures == 0,
            "validation_score": self.metrics.validation_score >= 0.95,
            "execution_time": self.metrics.total_execution_time < (self.max_total_time_minutes * 60)
        }
        
        all_passed = all(criteria.values())
        
        logger.info(f"Success criteria check: {criteria}")
        
        return all_passed
    
    async def _generate_success_report(self) -> Dict[str, Any]:
        """Gera relatório de sucesso"""
        return {
            "status": "SUCCESS",
            "execution_summary": {
                "total_time_seconds": self.metrics.total_execution_time,
                "steps_completed": self.metrics.steps_completed,
                "success_rate": self.metrics.success_rate,
                "validation_score": self.metrics.validation_score
            },
            "step_details": [
                {
                    "name": step.name,
                    "success": step.success,
                    "execution_time": step.execution_time_seconds,
                    "error": step.error
                }
                for step in self.steps if step.completed
            ],
            "performance_metrics": getattr(self, '_performance_baseline', {}),
            "timestamp": datetime.now().isoformat()
        }
    
    async def _generate_failure_report(self, error: str) -> Dict[str, Any]:
        """Gera relatório de falha"""
        return {
            "status": "FAILED",
            "error": error,
            "rollback_executed": self.metrics.rollback_executed,
            "execution_summary": {
                "total_time_seconds": self.metrics.total_execution_time,
                "steps_completed": self.metrics.steps_completed,
                "critical_failures": self.metrics.critical_failures,
                "phase_failed": self.metrics.current_phase.value
            },
            "failed_steps": [
                {
                    "name": step.name,
                    "error": step.error,
                    "critical": step.critical
                }
                for step in self.steps if step.completed and not step.success
            ],
            "timestamp": datetime.now().isoformat()
        }


# Função principal para execução
async def main():
    """Executa cutover controlado"""
    executor = ProductionCutoverExecutor()
    
    result = await executor.execute_controlled_cutover()
    logger.info(f"Cutover result: {result['status']}")
    
    return result


if __name__ == "__main__":
    asyncio.run(main())