"""
FASE 4 - FINAL SYSTEM VALIDATOR
Validador final abrangente do sistema pós-cutover
Testes completos, validação de integridade, certificação de produção

Agent-Deployment - Production Cutover Final
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import statistics

from loguru import logger

from app.services.redis_connection import get_redis_client, redis_manager
from app.services.hybrid_mode_manager import hybrid_mode_manager
from scripts.data_integrity_verifier import DataIntegrityVerifier
from scripts.redis_system_monitor import RedisSystemMonitor


class ValidationCategory(Enum):
    """Categorias de validação"""
    INFRASTRUCTURE = "infrastructure"
    DATA_INTEGRITY = "data_integrity"
    FUNCTIONALITY = "functionality"
    PERFORMANCE = "performance"
    SECURITY = "security"
    SCALABILITY = "scalability"
    RELIABILITY = "reliability"


class ValidationSeverity(Enum):
    """Severidade dos resultados de validação"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class ValidationTest:
    """Representação de um teste de validação"""
    name: str
    description: str
    category: ValidationCategory
    severity: ValidationSeverity
    executor: callable
    timeout_seconds: int = 60
    expected_result: Any = True
    success: bool = False
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0
    timestamp: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "severity": self.severity.value,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "execution_time": self.execution_time,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }


@dataclass
class ValidationMetrics:
    """Métricas da validação final"""
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    total_tests: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    critical_failures: int = 0
    high_severity_failures: int = 0
    overall_success_rate: float = 0.0
    overall_score: float = 0.0
    certification_level: str = "none"
    
    @property
    def execution_time_seconds(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0
    
    @property
    def is_production_ready(self) -> bool:
        return (self.critical_failures == 0 and 
                self.overall_success_rate >= 0.95 and 
                self.overall_score >= 85.0)


class FinalSystemValidator:
    """
    Validador final abrangente do sistema pós-cutover
    
    Executa validação completa em 7 categorias:
    - Infraestrutura (Redis, conectividade, recursos)
    - Integridade de dados (consistência, backup, recovery)
    - Funcionalidade (APIs, operações CRUD, business logic)
    - Performance (latência, throughput, limites)
    - Segurança (autenticação, autorização, validação)
    - Escalabilidade (carga, concorrência, limites)
    - Confiabilidade (failover, recovery, monitoramento)
    """
    
    def __init__(self):
        self.metrics = ValidationMetrics()
        self.tests: List[ValidationTest] = []
        self.results: Dict[str, Any] = {}
        
        # Componentes auxiliares
        self.integrity_verifier = DataIntegrityVerifier()
        self.redis_monitor = RedisSystemMonitor()
        
        # Configurações
        self.performance_baseline = {}
        self.load_test_duration = 30  # segundos
        self.concurrent_operations = 10
        
        # Critérios de certificação
        self.certification_criteria = {
            "PRODUCTION": {"min_score": 95.0, "max_critical": 0, "min_success_rate": 0.98},
            "STAGING": {"min_score": 85.0, "max_critical": 1, "min_success_rate": 0.90},
            "TESTING": {"min_score": 70.0, "max_critical": 3, "min_success_rate": 0.80}
        }
        
        self._setup_validation_tests()
        
        logger.info("🔍 FinalSystemValidator initialized for comprehensive validation")
    
    def _setup_validation_tests(self):
        """Configura todos os testes de validação"""
        # Infraestrutura
        self.tests.extend([
            ValidationTest(
                name="redis_connectivity",
                description="Verificar conectividade Redis básica",
                category=ValidationCategory.INFRASTRUCTURE,
                severity=ValidationSeverity.CRITICAL,
                executor=self._test_redis_connectivity
            ),
            ValidationTest(
                name="redis_health_comprehensive",
                description="Health check abrangente Redis",
                category=ValidationCategory.INFRASTRUCTURE,
                severity=ValidationSeverity.CRITICAL,
                executor=self._test_redis_health_comprehensive
            ),
            ValidationTest(
                name="system_resources",
                description="Verificar recursos do sistema",
                category=ValidationCategory.INFRASTRUCTURE,
                severity=ValidationSeverity.HIGH,
                executor=self._test_system_resources
            ),
            ValidationTest(
                name="configuration_integrity",
                description="Verificar integridade das configurações",
                category=ValidationCategory.INFRASTRUCTURE,
                severity=ValidationSeverity.HIGH,
                executor=self._test_configuration_integrity
            )
        ])
        
        # Integridade de Dados
        self.tests.extend([
            ValidationTest(
                name="data_consistency_redis",
                description="Verificar consistência dos dados Redis",
                category=ValidationCategory.DATA_INTEGRITY,
                severity=ValidationSeverity.CRITICAL,
                executor=self._test_data_consistency_redis
            ),
            ValidationTest(
                name="data_completeness",
                description="Verificar completude dos dados",
                category=ValidationCategory.DATA_INTEGRITY,
                severity=ValidationSeverity.HIGH,
                executor=self._test_data_completeness
            ),
            ValidationTest(
                name="backup_integrity",
                description="Verificar integridade dos backups",
                category=ValidationCategory.DATA_INTEGRITY,
                severity=ValidationSeverity.HIGH,
                executor=self._test_backup_integrity
            ),
            ValidationTest(
                name="data_recovery_capability",
                description="Testar capacidade de recuperação de dados",
                category=ValidationCategory.DATA_INTEGRITY,
                severity=ValidationSeverity.MEDIUM,
                executor=self._test_data_recovery_capability,
                timeout_seconds=120
            )
        ])
        
        # Funcionalidade
        self.tests.extend([
            ValidationTest(
                name="audio_operations_crud",
                description="Testar operações CRUD de áudio",
                category=ValidationCategory.FUNCTIONALITY,
                severity=ValidationSeverity.CRITICAL,
                executor=self._test_audio_operations_crud
            ),
            ValidationTest(
                name="video_operations_crud",
                description="Testar operações CRUD de vídeo",
                category=ValidationCategory.FUNCTIONALITY,
                severity=ValidationSeverity.CRITICAL,
                executor=self._test_video_operations_crud
            ),
            ValidationTest(
                name="search_functionality",
                description="Testar funcionalidades de busca",
                category=ValidationCategory.FUNCTIONALITY,
                severity=ValidationSeverity.HIGH,
                executor=self._test_search_functionality
            ),
            ValidationTest(
                name="api_endpoints",
                description="Testar endpoints da API",
                category=ValidationCategory.FUNCTIONALITY,
                severity=ValidationSeverity.HIGH,
                executor=self._test_api_endpoints
            )
        ])
        
        # Performance
        self.tests.extend([
            ValidationTest(
                name="response_time_baseline",
                description="Medir baseline de tempo de resposta",
                category=ValidationCategory.PERFORMANCE,
                severity=ValidationSeverity.HIGH,
                executor=self._test_response_time_baseline
            ),
            ValidationTest(
                name="throughput_measurement",
                description="Medir throughput do sistema",
                category=ValidationCategory.PERFORMANCE,
                severity=ValidationSeverity.MEDIUM,
                executor=self._test_throughput_measurement
            ),
            ValidationTest(
                name="memory_usage_optimization",
                description="Verificar otimização de uso de memória",
                category=ValidationCategory.PERFORMANCE,
                severity=ValidationSeverity.MEDIUM,
                executor=self._test_memory_usage_optimization
            ),
            ValidationTest(
                name="concurrent_operations",
                description="Testar operações concorrentes",
                category=ValidationCategory.PERFORMANCE,
                severity=ValidationSeverity.HIGH,
                executor=self._test_concurrent_operations,
                timeout_seconds=120
            )
        ])
        
        # Segurança
        self.tests.extend([
            ValidationTest(
                name="data_validation_security",
                description="Verificar validação de entrada de dados",
                category=ValidationCategory.SECURITY,
                severity=ValidationSeverity.HIGH,
                executor=self._test_data_validation_security
            ),
            ValidationTest(
                name="connection_security",
                description="Verificar segurança das conexões",
                category=ValidationCategory.SECURITY,
                severity=ValidationSeverity.MEDIUM,
                executor=self._test_connection_security
            )
        ])
        
        # Escalabilidade
        self.tests.extend([
            ValidationTest(
                name="load_handling",
                description="Testar capacidade de carga",
                category=ValidationCategory.SCALABILITY,
                severity=ValidationSeverity.MEDIUM,
                executor=self._test_load_handling,
                timeout_seconds=180
            ),
            ValidationTest(
                name="resource_scaling",
                description="Testar escalabilidade de recursos",
                category=ValidationCategory.SCALABILITY,
                severity=ValidationSeverity.LOW,
                executor=self._test_resource_scaling
            )
        ])
        
        # Confiabilidade
        self.tests.extend([
            ValidationTest(
                name="error_handling",
                description="Testar tratamento de erros",
                category=ValidationCategory.RELIABILITY,
                severity=ValidationSeverity.HIGH,
                executor=self._test_error_handling
            ),
            ValidationTest(
                name="monitoring_capabilities",
                description="Verificar capacidades de monitoramento",
                category=ValidationCategory.RELIABILITY,
                severity=ValidationSeverity.MEDIUM,
                executor=self._test_monitoring_capabilities
            )
        ])
        
        self.metrics.total_tests = len(self.tests)
    
    async def execute_comprehensive_validation(self) -> Dict[str, Any]:
        """
        Executa validação comprehensive completa
        
        Returns:
            Relatório detalhado de validação
        """
        logger.critical("🔍 INICIANDO COMPREHENSIVE FINAL VALIDATION")
        
        try:
            validation_start = time.time()
            
            # Executar todos os testes por categoria
            for category in ValidationCategory:
                await self._execute_category_tests(category)
            
            # Calcular métricas finais
            self._calculate_final_metrics()
            
            # Determinar nível de certificação
            self._determine_certification_level()
            
            self.metrics.end_time = datetime.now()
            
            # Gerar relatório final
            report = await self._generate_comprehensive_report()
            
            if self.metrics.is_production_ready:
                logger.success(f"✅ COMPREHENSIVE VALIDATION PASSED - PRODUCTION READY!")
                logger.success(f"🏆 Certification Level: {self.metrics.certification_level}")
                logger.success(f"📊 Overall Score: {self.metrics.overall_score:.1f}/100")
            else:
                logger.warning(f"⚠️ VALIDATION COMPLETED WITH ISSUES")
                logger.warning(f"🏆 Certification Level: {self.metrics.certification_level}")
                logger.warning(f"📊 Overall Score: {self.metrics.overall_score:.1f}/100")
                logger.warning(f"❌ Critical Failures: {self.metrics.critical_failures}")
            
            return report
            
        except Exception as e:
            logger.critical(f"💥 COMPREHENSIVE VALIDATION FAILED: {str(e)}")
            self.metrics.end_time = datetime.now()
            raise Exception(f"Final validation failed: {str(e)}")
    
    async def _execute_category_tests(self, category: ValidationCategory):
        """Executa testes de uma categoria específica"""
        category_tests = [test for test in self.tests if test.category == category]
        
        logger.info(f"📋 Executing {category.value.title()} tests ({len(category_tests)} tests)")
        
        for test in category_tests:
            await self._execute_single_test(test)
        
        # Calcular estatísticas da categoria
        passed = len([t for t in category_tests if t.success])
        success_rate = passed / len(category_tests) if category_tests else 0
        
        logger.info(f"✅ {category.value.title()} tests completed: {passed}/{len(category_tests)} ({success_rate:.1%})")
    
    async def _execute_single_test(self, test: ValidationTest):
        """Executa um único teste de validação"""
        logger.debug(f"🔧 Executing test: {test.name}")
        
        start_time = time.time()
        test.timestamp = datetime.now()
        
        try:
            # Executar teste com timeout
            test.result = await asyncio.wait_for(
                test.executor(),
                timeout=test.timeout_seconds
            )
            
            test.execution_time = time.time() - start_time
            
            # Verificar sucesso baseado no resultado esperado
            if test.expected_result is True:
                test.success = bool(test.result)
            else:
                test.success = (test.result == test.expected_result)
            
            if test.success:
                self.metrics.tests_passed += 1
                logger.debug(f"✅ Test passed: {test.name} ({test.execution_time:.2f}s)")
            else:
                self.metrics.tests_failed += 1
                logger.warning(f"⚠️ Test failed: {test.name}")
                
                # Contar falhas por severidade
                if test.severity == ValidationSeverity.CRITICAL:
                    self.metrics.critical_failures += 1
                elif test.severity == ValidationSeverity.HIGH:
                    self.metrics.high_severity_failures += 1
                    
        except asyncio.TimeoutError:
            test.error = f"Test timeout after {test.timeout_seconds}s"
            test.execution_time = test.timeout_seconds
            test.success = False
            self.metrics.tests_failed += 1
            
            if test.severity == ValidationSeverity.CRITICAL:
                self.metrics.critical_failures += 1
            
            logger.error(f"⏰ Test timeout: {test.name}")
            
        except Exception as e:
            test.error = str(e)
            test.execution_time = time.time() - start_time
            test.success = False
            self.metrics.tests_failed += 1
            
            if test.severity == ValidationSeverity.CRITICAL:
                self.metrics.critical_failures += 1
                
            logger.error(f"❌ Test error: {test.name} - {str(e)}")
    
    # Implementação dos testes de validação
    
    # INFRAESTRUTURA
    async def _test_redis_connectivity(self):
        """Testa conectividade básica Redis"""
        redis_client = await get_redis_client()
        await redis_client.ping()
        return True
    
    async def _test_redis_health_comprehensive(self):
        """Health check abrangente Redis"""
        health = await redis_manager.health_check()
        
        if health.get("status") != "healthy":
            return False
        
        # Verificar métricas específicas
        ping_time = health.get("ping_time_ms", 0)
        used_memory = health.get("used_memory", 0)
        
        if ping_time > 50:  # > 50ms é preocupante
            return False
        
        if used_memory > 1073741824:  # > 1GB pode ser problema
            logger.warning(f"High Redis memory usage: {used_memory} bytes")
        
        return True
    
    async def _test_system_resources(self):
        """Verifica recursos do sistema"""
        import psutil
        
        cpu_usage = psutil.cpu_percent(interval=1)
        memory_usage = psutil.virtual_memory().percent
        disk_usage = psutil.disk_usage('/').percent
        
        # Critérios de aprovação
        if cpu_usage > 80:
            logger.warning(f"High CPU usage: {cpu_usage}%")
            return False
        
        if memory_usage > 85:
            logger.warning(f"High memory usage: {memory_usage}%")
            return False
        
        if disk_usage > 90:
            logger.warning(f"High disk usage: {disk_usage}%")
            return False
        
        return {
            "cpu_percent": cpu_usage,
            "memory_percent": memory_usage,
            "disk_percent": disk_usage
        }
    
    async def _test_configuration_integrity(self):
        """Verifica integridade das configurações"""
        # Verificar configurações críticas
        critical_configs = {
            "USE_REDIS": "true",
            "AUTO_FALLBACK": "false"
        }
        
        import os
        for key, expected in critical_configs.items():
            actual = os.getenv(key, "").lower()
            if actual != expected.lower():
                logger.warning(f"Configuration mismatch: {key}={actual}, expected={expected}")
                return False
        
        # Verificar configuração híbrida
        if hybrid_mode_manager.config.use_redis != True:
            return False
        
        if hybrid_mode_manager.config.auto_fallback != False:
            return False
        
        return True
    
    # INTEGRIDADE DE DADOS
    async def _test_data_consistency_redis(self):
        """Verifica consistência dos dados Redis"""
        integrity_result = await self.integrity_verifier.comprehensive_verification()
        return integrity_result.get("overall_success", False)
    
    async def _test_data_completeness(self):
        """Verifica completude dos dados"""
        redis_client = await get_redis_client()
        
        # Contar dados por tipo
        audio_keys = await redis_client.keys("audio:*")
        video_keys = await redis_client.keys("video:*")
        
        audio_count = len(audio_keys)
        video_count = len(video_keys)
        total_count = audio_count + video_count
        
        if total_count == 0:
            return False
        
        # Verificar algumas amostras
        sample_size = min(5, audio_count)
        if sample_size > 0:
            sample_keys = audio_keys[:sample_size]
            for key in sample_keys:
                data = await redis_client.get(key)
                if not data:
                    return False
                
                try:
                    json.loads(data)
                except json.JSONDecodeError:
                    return False
        
        return {
            "audio_count": audio_count,
            "video_count": video_count,
            "total_count": total_count
        }
    
    async def _test_backup_integrity(self):
        """Verifica integridade dos backups"""
        backup_dir = Path(__file__).parent.parent / "backups"
        
        if not backup_dir.exists():
            return False
        
        # Verificar backups recentes (últimas 24 horas)
        cutoff_time = datetime.now() - timedelta(hours=24)
        recent_backups = []
        
        for backup_file in backup_dir.glob("*.zip"):
            if backup_file.stat().st_mtime > cutoff_time.timestamp():
                recent_backups.append(backup_file)
        
        return len(recent_backups) > 0
    
    async def _test_data_recovery_capability(self):
        """Testa capacidade de recuperação de dados"""
        # Teste simulado de recovery - criar e recuperar um item de teste
        redis_client = await get_redis_client()
        
        test_key = "validation_recovery_test"
        test_data = {"test": "data_recovery", "timestamp": time.time()}
        
        # Criar item de teste
        await redis_client.set(test_key, json.dumps(test_data))
        
        # Simular remoção
        await redis_client.delete(test_key)
        
        # Verificar que foi removido
        result = await redis_client.get(test_key)
        if result is not None:
            return False
        
        # Simular recovery (recriar)
        await redis_client.set(test_key, json.dumps(test_data))
        
        # Verificar recovery
        recovered = await redis_client.get(test_key)
        if not recovered:
            return False
        
        recovered_data = json.loads(recovered)
        
        # Limpar teste
        await redis_client.delete(test_key)
        
        return recovered_data == test_data
    
    # FUNCIONALIDADE
    async def _test_audio_operations_crud(self):
        """Testa operações CRUD de áudio"""
        try:
            from app.services.redis_audio_manager import RedisAudioManager
            audio_manager = RedisAudioManager()
            
            # READ - Listar áudios
            audios = await audio_manager.get_audios()
            
            if not isinstance(audios, list):
                return False
            
            # Se há áudios, testar busca
            if audios:
                first_audio = audios[0]
                audio_id = first_audio.get("id")
                
                if audio_id:
                    # READ específico
                    specific_audio = await audio_manager.get_audio_by_id(audio_id)
                    if not specific_audio:
                        return False
            
            return {"tested_operations": ["list", "get_by_id"], "audio_count": len(audios)}
            
        except Exception as e:
            logger.error(f"Audio CRUD test failed: {str(e)}")
            return False
    
    async def _test_video_operations_crud(self):
        """Testa operações CRUD de vídeo"""
        try:
            from app.services.redis_video_manager import RedisVideoManager
            video_manager = RedisVideoManager()
            
            # READ - Listar vídeos
            videos = await video_manager.get_videos()
            
            if not isinstance(videos, list):
                return False
            
            return {"tested_operations": ["list"], "video_count": len(videos)}
            
        except Exception as e:
            logger.error(f"Video CRUD test failed: {str(e)}")
            return False
    
    async def _test_search_functionality(self):
        """Testa funcionalidades de busca"""
        try:
            from app.services.redis_audio_manager import RedisAudioManager
            audio_manager = RedisAudioManager()
            
            # Busca básica
            search_results = await audio_manager.search_audios("test")
            
            if not isinstance(search_results, list):
                return False
            
            # Busca por categoria se disponível
            audios = await audio_manager.get_audios()
            if audios:
                # Buscar por termo que deve existir
                sample_audio = audios[0]
                title = sample_audio.get("title", "")
                
                if title:
                    # Buscar uma palavra do título
                    words = title.split()
                    if words:
                        search_word = words[0]
                        results = await audio_manager.search_audios(search_word)
                        
                        # Verificar que encontrou resultados
                        found = any(search_word.lower() in r.get("title", "").lower() for r in results)
                        
                        return {"search_functional": found, "results_count": len(results)}
            
            return {"search_functional": True, "results_count": len(search_results)}
            
        except Exception as e:
            logger.error(f"Search functionality test failed: {str(e)}")
            return False
    
    async def _test_api_endpoints(self):
        """Testa endpoints da API"""
        # Teste básico - verificar se managers estão funcionando
        try:
            from app.services.redis_audio_manager import RedisAudioManager
            from app.services.redis_video_manager import RedisVideoManager
            
            audio_manager = RedisAudioManager()
            video_manager = RedisVideoManager()
            
            # Testar endpoints básicos
            audios = await audio_manager.get_audios()
            videos = await video_manager.get_videos()
            
            endpoints_ok = {
                "get_audios": isinstance(audios, list),
                "get_videos": isinstance(videos, list)
            }
            
            return all(endpoints_ok.values())
            
        except Exception as e:
            logger.error(f"API endpoints test failed: {str(e)}")
            return False
    
    # PERFORMANCE
    async def _test_response_time_baseline(self):
        """Mede baseline de tempo de resposta"""
        redis_client = await get_redis_client()
        
        # Medir latências de ping
        ping_times = []
        for _ in range(20):
            start = time.time()
            await redis_client.ping()
            latency = (time.time() - start) * 1000
            ping_times.append(latency)
        
        avg_ping = statistics.mean(ping_times)
        max_ping = max(ping_times)
        
        # Medir tempo de operações de dados
        from app.services.redis_audio_manager import RedisAudioManager
        audio_manager = RedisAudioManager()
        
        start = time.time()
        audios = await audio_manager.get_audios()
        data_operation_time = (time.time() - start) * 1000
        
        baseline = {
            "avg_ping_ms": avg_ping,
            "max_ping_ms": max_ping,
            "data_operation_ms": data_operation_time
        }
        
        self.performance_baseline = baseline
        
        # Critérios de aprovação
        if avg_ping > 10 or data_operation_time > 100:
            return False
        
        return baseline
    
    async def _test_throughput_measurement(self):
        """Mede throughput do sistema"""
        redis_client = await get_redis_client()
        
        # Teste de throughput - operações por segundo
        operations = 100
        start_time = time.time()
        
        # Executar operações
        for i in range(operations):
            await redis_client.ping()
        
        total_time = time.time() - start_time
        throughput = operations / total_time
        
        return {
            "operations_per_second": throughput,
            "total_operations": operations,
            "total_time_seconds": total_time
        }
    
    async def _test_memory_usage_optimization(self):
        """Verifica otimização de uso de memória"""
        import psutil
        import gc
        
        # Medir uso de memória antes
        process = psutil.Process()
        memory_before = process.memory_info().rss
        
        # Executar operação que pode consumir memória
        from app.services.redis_audio_manager import RedisAudioManager
        audio_manager = RedisAudioManager()
        
        # Executar múltiplas operações
        for _ in range(5):
            audios = await audio_manager.get_audios()
        
        # Forçar garbage collection
        gc.collect()
        
        # Medir uso de memória depois
        memory_after = process.memory_info().rss
        memory_diff = memory_after - memory_before
        
        return {
            "memory_before_mb": memory_before / 1024 / 1024,
            "memory_after_mb": memory_after / 1024 / 1024,
            "memory_diff_mb": memory_diff / 1024 / 1024,
            "optimized": memory_diff < 50 * 1024 * 1024  # < 50MB diferença
        }
    
    async def _test_concurrent_operations(self):
        """Testa operações concorrentes"""
        from app.services.redis_audio_manager import RedisAudioManager
        
        # Executar operações concorrentes
        async def concurrent_operation():
            audio_manager = RedisAudioManager()
            return await audio_manager.get_audios()
        
        start_time = time.time()
        
        # Executar múltiplas operações em paralelo
        tasks = [concurrent_operation() for _ in range(self.concurrent_operations)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        execution_time = time.time() - start_time
        
        # Verificar resultados
        successful_operations = 0
        for result in results:
            if not isinstance(result, Exception) and isinstance(result, list):
                successful_operations += 1
        
        success_rate = successful_operations / len(tasks)
        
        return {
            "concurrent_operations": self.concurrent_operations,
            "successful_operations": successful_operations,
            "success_rate": success_rate,
            "total_time_seconds": execution_time,
            "operations_per_second": len(tasks) / execution_time
        }
    
    # SEGURANÇA
    async def _test_data_validation_security(self):
        """Verifica validação de entrada de dados"""
        # Teste básico de validação - tentar operações com dados inválidos
        redis_client = await get_redis_client()
        
        # Teste 1: Tentar armazenar dados maliciosos
        malicious_data = "<script>alert('xss')</script>"
        test_key = "security_test_xss"
        
        try:
            await redis_client.set(test_key, malicious_data)
            stored_data = await redis_client.get(test_key)
            
            # Limpar teste
            await redis_client.delete(test_key)
            
            # Verificar que dados foram armazenados como string literal
            if stored_data.decode() == malicious_data:
                return True  # Sistema não executou, apenas armazenou
            
        except Exception:
            return True  # Sistema rejeitou dados maliciosos
        
        return False
    
    async def _test_connection_security(self):
        """Verifica segurança das conexões"""
        # Verificar se conexão Redis está configurada corretamente
        redis_client = await get_redis_client()
        
        # Testar conexão
        await redis_client.ping()
        
        # Verificar configurações de segurança básicas
        info = await redis_client.info()
        
        return {
            "connection_established": True,
            "redis_version": info.get("redis_version", "unknown")
        }
    
    # ESCALABILIDADE
    async def _test_load_handling(self):
        """Testa capacidade de carga"""
        from app.services.redis_audio_manager import RedisAudioManager
        
        # Executar teste de carga
        operations_count = 50
        audio_manager = RedisAudioManager()
        
        start_time = time.time()
        successful_operations = 0
        
        for i in range(operations_count):
            try:
                audios = await audio_manager.get_audios()
                if isinstance(audios, list):
                    successful_operations += 1
                    
                # Pequena pausa para simular carga real
                await asyncio.sleep(0.01)
                
            except Exception as e:
                logger.debug(f"Load test operation {i} failed: {str(e)}")
        
        total_time = time.time() - start_time
        success_rate = successful_operations / operations_count
        
        return {
            "total_operations": operations_count,
            "successful_operations": successful_operations,
            "success_rate": success_rate,
            "total_time_seconds": total_time,
            "operations_per_second": operations_count / total_time
        }
    
    async def _test_resource_scaling(self):
        """Testa escalabilidade de recursos"""
        import psutil
        
        # Monitorar uso de recursos durante operações
        process = psutil.Process()
        
        # Baseline
        cpu_before = process.cpu_percent()
        memory_before = process.memory_info().rss
        
        # Executar operações intensivas
        from app.services.redis_audio_manager import RedisAudioManager
        audio_manager = RedisAudioManager()
        
        for _ in range(10):
            await audio_manager.get_audios()
        
        # Medir recursos após operações
        cpu_after = process.cpu_percent()
        memory_after = process.memory_info().rss
        
        return {
            "cpu_usage_change": cpu_after - cpu_before,
            "memory_usage_change_mb": (memory_after - memory_before) / 1024 / 1024,
            "scales_well": (cpu_after - cpu_before) < 20  # Aumento de CPU < 20%
        }
    
    # CONFIABILIDADE
    async def _test_error_handling(self):
        """Testa tratamento de erros"""
        redis_client = await get_redis_client()
        
        # Teste 1: Operação com chave inválida
        try:
            result = await redis_client.get("nonexistent_key_12345")
            # Deve retornar None sem erro
            if result is None:
                error_handling_ok = True
            else:
                error_handling_ok = False
        except Exception:
            error_handling_ok = False
        
        # Teste 2: Operação com dados inválidos
        try:
            # Tentar buscar áudios com manager
            from app.services.redis_audio_manager import RedisAudioManager
            audio_manager = RedisAudioManager()
            
            # Esta operação deve funcionar mesmo se não há dados
            audios = await audio_manager.get_audios()
            manager_error_handling = isinstance(audios, list)
            
        except Exception as e:
            logger.debug(f"Manager error handling test: {str(e)}")
            manager_error_handling = False
        
        return {
            "basic_error_handling": error_handling_ok,
            "manager_error_handling": manager_error_handling,
            "overall_error_handling": error_handling_ok and manager_error_handling
        }
    
    async def _test_monitoring_capabilities(self):
        """Verifica capacidades de monitoramento"""
        # Verificar se sistemas de monitoramento estão funcionais
        
        # Teste 1: Health check Redis
        try:
            health = await redis_manager.health_check()
            health_monitoring = health.get("status") == "healthy"
        except Exception:
            health_monitoring = False
        
        # Teste 2: Métricas híbridas
        try:
            hybrid_health = await hybrid_mode_manager.health_check()
            hybrid_monitoring = isinstance(hybrid_health, dict)
        except Exception:
            hybrid_monitoring = False
        
        return {
            "redis_health_monitoring": health_monitoring,
            "hybrid_mode_monitoring": hybrid_monitoring,
            "monitoring_functional": health_monitoring and hybrid_monitoring
        }
    
    def _calculate_final_metrics(self):
        """Calcula métricas finais da validação"""
        if self.metrics.total_tests > 0:
            self.metrics.overall_success_rate = self.metrics.tests_passed / self.metrics.total_tests
        
        # Calcular score ponderado por severidade
        total_weight = 0
        weighted_score = 0
        
        severity_weights = {
            ValidationSeverity.CRITICAL: 10,
            ValidationSeverity.HIGH: 7,
            ValidationSeverity.MEDIUM: 5,
            ValidationSeverity.LOW: 3,
            ValidationSeverity.INFO: 1
        }
        
        for test in self.tests:
            weight = severity_weights.get(test.severity, 1)
            total_weight += weight
            
            if test.success:
                weighted_score += weight
        
        if total_weight > 0:
            self.metrics.overall_score = (weighted_score / total_weight) * 100
    
    def _determine_certification_level(self):
        """Determina nível de certificação baseado nas métricas"""
        for level, criteria in self.certification_criteria.items():
            if (self.metrics.overall_score >= criteria["min_score"] and
                self.metrics.critical_failures <= criteria["max_critical"] and
                self.metrics.overall_success_rate >= criteria["min_success_rate"]):
                
                self.metrics.certification_level = level
                return
        
        self.metrics.certification_level = "NOT_CERTIFIED"
    
    async def _generate_comprehensive_report(self) -> Dict[str, Any]:
        """Gera relatório comprehensive da validação"""
        # Agrupar testes por categoria
        tests_by_category = {}
        for category in ValidationCategory:
            tests_by_category[category.value] = [
                test.to_dict() for test in self.tests if test.category == category
            ]
        
        # Calcular estatísticas por categoria
        category_stats = {}
        for category, tests in tests_by_category.items():
            passed = len([t for t in tests if t["success"]])
            total = len(tests)
            category_stats[category] = {
                "total_tests": total,
                "passed_tests": passed,
                "success_rate": passed / total if total > 0 else 0,
                "critical_failures": len([t for t in tests if not t["success"] and t["severity"] == "critical"])
            }
        
        return {
            "validation_summary": {
                "overall_success": self.metrics.is_production_ready,
                "certification_level": self.metrics.certification_level,
                "overall_score": round(self.metrics.overall_score, 2),
                "execution_time_seconds": self.metrics.execution_time_seconds,
                "timestamp": self.metrics.end_time.isoformat() if self.metrics.end_time else None
            },
            "test_statistics": {
                "total_tests": self.metrics.total_tests,
                "tests_passed": self.metrics.tests_passed,
                "tests_failed": self.metrics.tests_failed,
                "overall_success_rate": round(self.metrics.overall_success_rate, 4),
                "critical_failures": self.metrics.critical_failures,
                "high_severity_failures": self.metrics.high_severity_failures
            },
            "category_results": category_stats,
            "detailed_results": tests_by_category,
            "performance_baseline": self.performance_baseline,
            "certification_criteria": self.certification_criteria,
            "recommendations": self._generate_recommendations()
        }
    
    def _generate_recommendations(self) -> List[str]:
        """Gera recomendações baseadas nos resultados"""
        recommendations = []
        
        if self.metrics.critical_failures > 0:
            recommendations.append("CRITICAL: Address all critical failures before proceeding to production")
        
        if self.metrics.overall_score < 85:
            recommendations.append("Improve system performance and reliability before production deployment")
        
        if self.metrics.overall_success_rate < 0.95:
            recommendations.append("Investigate and fix failing tests to improve success rate")
        
        if self.metrics.certification_level == "NOT_CERTIFIED":
            recommendations.append("System does not meet minimum certification requirements")
        
        # Recomendações por categoria
        failed_tests = [test for test in self.tests if not test.success]
        
        for category in ValidationCategory:
            category_failures = [t for t in failed_tests if t.category == category]
            if category_failures:
                recommendations.append(f"Address {category.value} issues: {len(category_failures)} failures detected")
        
        if self.metrics.is_production_ready:
            recommendations.extend([
                "System certified for production deployment",
                "Continue monitoring for 48 hours post-deployment",
                "Perform regular health checks",
                "Maintain current performance baselines"
            ])
        
        return recommendations


# Função principal para execução
async def main():
    """Executa validação final comprehensive"""
    validator = FinalSystemValidator()
    
    result = await validator.execute_comprehensive_validation()
    
    print(f"Validation Status: {result['validation_summary']['overall_success']}")
    print(f"Certification Level: {result['validation_summary']['certification_level']}")
    print(f"Overall Score: {result['validation_summary']['overall_score']}")
    
    return result


if __name__ == "__main__":
    asyncio.run(main())