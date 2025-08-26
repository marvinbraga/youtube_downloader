"""
Continuous Validation Manager - Agent-QualityAssurance FASE 4
Sistema de validação contínua pós-cutover por 96 horas
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from pathlib import Path
import logging
import redis.asyncio as redis
import threading

from .data_integrity_validator import DataIntegrityValidator
from .performance_validator import PerformanceValidator
from .user_experience_validator import UserExperienceValidator
from .error_rate_validator import ErrorRateValidator
from .validation_reporter import ValidationReporter
from .validation_dashboard import ValidationDashboard

@dataclass
class ValidationConfig:
    """Configuração da validação contínua"""
    validation_interval: int = 300  # 5 minutes
    validation_duration: int = 96 * 3600  # 96 hours
    critical_alert_threshold: Dict[str, Any] = None
    warning_alert_threshold: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.critical_alert_threshold is None:
            self.critical_alert_threshold = {
                'data_corruption': True,
                'performance_degradation': 50,  # 50% worse
                'error_spike': 5,              # 5% errors
                'availability': 95              # <95% uptime
            }
        
        if self.warning_alert_threshold is None:
            self.warning_alert_threshold = {
                'performance_degradation': 20,  # 20% worse
                'error_spike': 2,              # 2% errors
                'availability': 99              # <99% uptime
            }

@dataclass
class ValidationResult:
    """Resultado de uma validação"""
    timestamp: str
    validation_type: str
    status: str  # 'passed', 'warning', 'critical'
    metrics: Dict[str, Any]
    issues: List[str]
    recommendations: List[str]
    duration: float

class ContinuousValidationManager:
    """Manager principal para validação contínua por 96 horas"""
    
    def __init__(self, config: Optional[ValidationConfig] = None):
        self.config = config or ValidationConfig()
        self.is_validating = False
        self.validation_start_time = None
        self.validation_results: List[ValidationResult] = []
        
        # Setup logging
        self.logger = logging.getLogger(__name__)
        handler = logging.FileHandler('validation/continuous_validation.log')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
        
        # Initialize validators
        self.data_integrity_validator = DataIntegrityValidator()
        self.performance_validator = PerformanceValidator()
        self.user_experience_validator = UserExperienceValidator()
        self.error_rate_validator = ErrorRateValidator()
        
        # Initialize reporter and dashboard
        self.reporter = ValidationReporter()
        self.dashboard = ValidationDashboard()
        
        # Redis connection
        self.redis_client = None
        
        # Validation statistics
        self.validation_stats = {
            'total_validations': 0,
            'passed_validations': 0,
            'warning_validations': 0,
            'critical_validations': 0,
            'data_integrity_success_rate': 0.0,
            'performance_success_rate': 0.0,
            'user_experience_success_rate': 0.0,
            'error_rate_success_rate': 0.0
        }
    
    async def initialize_redis(self):
        """Inicializar conexão Redis"""
        try:
            # Função para conversão segura
            def safe_int(value, default):
                try:
                    return int(value)
                except (ValueError, TypeError):
                    self.logger.warning(f"Valor inválido para REDIS_PORT: {value}. Usando padrão: {default}")
                    return default
            
            self.redis_client = redis.Redis(
                host='localhost',
                port=safe_int(os.getenv('REDIS_PORT', 6379), 6379),
                decode_responses=True
            )
            await self.redis_client.ping()
            self.logger.info("Redis connection initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Redis connection: {e}")
            raise
    
    async def start_continuous_validation(self) -> Dict[str, Any]:
        """Iniciar validação contínua por 96 horas"""
        self.logger.info("Starting 96-hour continuous validation...")
        
        # Initialize Redis connection
        await self.initialize_redis()
        
        # Set validation parameters
        self.is_validating = True
        self.validation_start_time = datetime.now()
        
        # Initialize dashboard
        await self.dashboard.start()
        
        validation_tasks = [
            self.validate_data_integrity_continuously(),
            self.validate_performance_continuously(),
            self.validate_user_experience_continuously(),
            self.validate_error_rates_continuously(),
            self.generate_periodic_reports(),
            self.monitor_validation_health()
        ]
        
        try:
            # Run validation for 96 hours with timeout
            await asyncio.wait_for(
                asyncio.gather(*validation_tasks),
                timeout=self.config.validation_duration
            )
            
            self.logger.info("96-hour validation completed successfully")
            return await self.generate_final_report()
            
        except asyncio.TimeoutError:
            self.logger.info("96-hour validation period completed")
            return await self.generate_final_report()
            
        except Exception as e:
            self.logger.error(f"Validation failed: {e}")
            self.is_validating = False
            raise
        finally:
            await self.cleanup()
    
    async def validate_data_integrity_continuously(self):
        """Validação contínua de integridade de dados"""
        while self.is_validating and self._should_continue_validation():
            try:
                start_time = time.time()
                result = await self.data_integrity_validator.validate()
                
                validation_result = ValidationResult(
                    timestamp=datetime.now().isoformat(),
                    validation_type='data_integrity',
                    status=result['status'],
                    metrics=result['metrics'],
                    issues=result['issues'],
                    recommendations=result['recommendations'],
                    duration=time.time() - start_time
                )
                
                await self._process_validation_result(validation_result)
                
            except Exception as e:
                self.logger.error(f"Data integrity validation failed: {e}")
            
            await asyncio.sleep(self.config.validation_interval)
    
    async def validate_performance_continuously(self):
        """Validação contínua de performance"""
        while self.is_validating and self._should_continue_validation():
            try:
                start_time = time.time()
                result = await self.performance_validator.validate()
                
                validation_result = ValidationResult(
                    timestamp=datetime.now().isoformat(),
                    validation_type='performance',
                    status=result['status'],
                    metrics=result['metrics'],
                    issues=result['issues'],
                    recommendations=result['recommendations'],
                    duration=time.time() - start_time
                )
                
                await self._process_validation_result(validation_result)
                
            except Exception as e:
                self.logger.error(f"Performance validation failed: {e}")
            
            await asyncio.sleep(self.config.validation_interval)
    
    async def validate_user_experience_continuously(self):
        """Validação contínua de experiência do usuário"""
        while self.is_validating and self._should_continue_validation():
            try:
                start_time = time.time()
                result = await self.user_experience_validator.validate()
                
                validation_result = ValidationResult(
                    timestamp=datetime.now().isoformat(),
                    validation_type='user_experience',
                    status=result['status'],
                    metrics=result['metrics'],
                    issues=result['issues'],
                    recommendations=result['recommendations'],
                    duration=time.time() - start_time
                )
                
                await self._process_validation_result(validation_result)
                
            except Exception as e:
                self.logger.error(f"User experience validation failed: {e}")
            
            await asyncio.sleep(self.config.validation_interval)
    
    async def validate_error_rates_continuously(self):
        """Validação contínua de taxas de erro"""
        while self.is_validating and self._should_continue_validation():
            try:
                start_time = time.time()
                result = await self.error_rate_validator.validate()
                
                validation_result = ValidationResult(
                    timestamp=datetime.now().isoformat(),
                    validation_type='error_rates',
                    status=result['status'],
                    metrics=result['metrics'],
                    issues=result['issues'],
                    recommendations=result['recommendations'],
                    duration=time.time() - start_time
                )
                
                await self._process_validation_result(validation_result)
                
            except Exception as e:
                self.logger.error(f"Error rate validation failed: {e}")
            
            await asyncio.sleep(self.config.validation_interval)
    
    async def generate_periodic_reports(self):
        """Gerar relatórios periódicos (hourly/daily)"""
        hourly_interval = 3600  # 1 hour
        daily_interval = 86400  # 24 hours
        
        last_hourly_report = time.time()
        last_daily_report = time.time()
        
        while self.is_validating and self._should_continue_validation():
            current_time = time.time()
            
            # Generate hourly report
            if current_time - last_hourly_report >= hourly_interval:
                await self.reporter.generate_hourly_report(self.validation_results)
                last_hourly_report = current_time
                self.logger.info("Generated hourly validation report")
            
            # Generate daily report
            if current_time - last_daily_report >= daily_interval:
                await self.reporter.generate_daily_report(self.validation_results)
                last_daily_report = current_time
                self.logger.info("Generated daily validation report")
            
            await asyncio.sleep(300)  # Check every 5 minutes
    
    async def monitor_validation_health(self):
        """Monitor da saúde do próprio sistema de validação"""
        while self.is_validating and self._should_continue_validation():
            try:
                # Check validation system health
                health_metrics = {
                    'validation_uptime': self._get_validation_uptime(),
                    'memory_usage': self._get_memory_usage(),
                    'validation_success_rate': self._get_validation_success_rate(),
                    'average_validation_duration': self._get_average_validation_duration()
                }
                
                # Update dashboard
                await self.dashboard.update_health_metrics(health_metrics)
                
                self.logger.info(f"Validation health check: {health_metrics}")
                
            except Exception as e:
                self.logger.error(f"Validation health monitoring failed: {e}")
            
            await asyncio.sleep(600)  # Check every 10 minutes
    
    async def _process_validation_result(self, result: ValidationResult):
        """Processar resultado de validação"""
        # Add to results list
        self.validation_results.append(result)
        
        # Update statistics
        self._update_validation_stats(result)
        
        # Store in Redis for real-time access
        await self.redis_client.lpush(
            f"validation:results:{result.validation_type}",
            json.dumps(asdict(result))
        )
        
        # Trim to keep only recent results
        await self.redis_client.ltrim(f"validation:results:{result.validation_type}", 0, 100)
        
        # Update dashboard
        await self.dashboard.update_validation_result(result)
        
        # Check for alerts
        await self._check_alerts(result)
        
        self.logger.info(f"Processed {result.validation_type} validation: {result.status}")
    
    async def _check_alerts(self, result: ValidationResult):
        """Verificar se alertas devem ser enviados"""
        if result.status == 'critical':
            await self._send_critical_alert(result)
        elif result.status == 'warning':
            await self._send_warning_alert(result)
    
    async def _send_critical_alert(self, result: ValidationResult):
        """Enviar alerta crítico"""
        alert = {
            'type': 'critical',
            'validation_type': result.validation_type,
            'timestamp': result.timestamp,
            'issues': result.issues,
            'metrics': result.metrics
        }
        
        # Store alert in Redis
        await self.redis_client.lpush('validation:alerts:critical', json.dumps(alert))
        
        self.logger.critical(f"CRITICAL ALERT: {result.validation_type} - {result.issues}")
    
    async def _send_warning_alert(self, result: ValidationResult):
        """Enviar alerta de warning"""
        alert = {
            'type': 'warning',
            'validation_type': result.validation_type,
            'timestamp': result.timestamp,
            'issues': result.issues,
            'metrics': result.metrics
        }
        
        # Store alert in Redis
        await self.redis_client.lpush('validation:alerts:warning', json.dumps(alert))
        
        self.logger.warning(f"WARNING ALERT: {result.validation_type} - {result.issues}")
    
    def _should_continue_validation(self) -> bool:
        """Verificar se deve continuar validação"""
        if not self.validation_start_time:
            return False
            
        elapsed_time = (datetime.now() - self.validation_start_time).total_seconds()
        return elapsed_time < self.config.validation_duration
    
    def _update_validation_stats(self, result: ValidationResult):
        """Atualizar estatísticas de validação"""
        self.validation_stats['total_validations'] += 1
        
        if result.status == 'passed':
            self.validation_stats['passed_validations'] += 1
        elif result.status == 'warning':
            self.validation_stats['warning_validations'] += 1
        elif result.status == 'critical':
            self.validation_stats['critical_validations'] += 1
        
        # Update success rates by validation type
        type_results = [r for r in self.validation_results if r.validation_type == result.validation_type]
        passed_count = len([r for r in type_results if r.status == 'passed'])
        success_rate = (passed_count / len(type_results)) * 100 if type_results else 0
        
        self.validation_stats[f'{result.validation_type}_success_rate'] = success_rate
    
    def _get_validation_uptime(self) -> float:
        """Calcular uptime da validação"""
        if not self.validation_start_time:
            return 0.0
        
        elapsed = (datetime.now() - self.validation_start_time).total_seconds()
        return (elapsed / self.config.validation_duration) * 100
    
    def _get_memory_usage(self) -> float:
        """Obter uso de memória"""
        import psutil
        process = psutil.Process()
        return process.memory_percent()
    
    def _get_validation_success_rate(self) -> float:
        """Calcular taxa de sucesso geral"""
        total = self.validation_stats['total_validations']
        passed = self.validation_stats['passed_validations']
        return (passed / total) * 100 if total > 0 else 0
    
    def _get_average_validation_duration(self) -> float:
        """Calcular duração média das validações"""
        if not self.validation_results:
            return 0.0
        
        total_duration = sum(r.duration for r in self.validation_results)
        return total_duration / len(self.validation_results)
    
    async def generate_final_report(self) -> Dict[str, Any]:
        """Gerar relatório final de 96 horas"""
        self.logger.info("Generating final 96-hour validation report...")
        
        final_report = {
            'validation_period': {
                'start_time': self.validation_start_time.isoformat(),
                'end_time': datetime.now().isoformat(),
                'duration_hours': (datetime.now() - self.validation_start_time).total_seconds() / 3600
            },
            'overall_statistics': self.validation_stats,
            'success_criteria': self._evaluate_success_criteria(),
            'validation_summary': self._generate_validation_summary(),
            'recommendations': await self._generate_final_recommendations(),
            'approval_status': self._determine_approval_status()
        }
        
        # Save final report
        report_path = f"validation/final_validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w') as f:
            json.dump(final_report, f, indent=2)
        
        self.logger.info(f"Final report saved to {report_path}")
        return final_report
    
    def _evaluate_success_criteria(self) -> Dict[str, Any]:
        """Avaliar critérios de sucesso"""
        return {
            'data_integrity': {
                'target': 100.0,
                'actual': self.validation_stats['data_integrity_success_rate'],
                'met': self.validation_stats['data_integrity_success_rate'] >= 100.0
            },
            'performance': {
                'target': 95.0,
                'actual': self.validation_stats['performance_success_rate'],
                'met': self.validation_stats['performance_success_rate'] >= 95.0
            },
            'user_experience': {
                'target': 90.0,
                'actual': self.validation_stats['user_experience_success_rate'],
                'met': self.validation_stats['user_experience_success_rate'] >= 90.0
            },
            'error_rates': {
                'target': 99.0,  # <1% error rate
                'actual': self.validation_stats['error_rate_success_rate'],
                'met': self.validation_stats['error_rate_success_rate'] >= 99.0
            }
        }
    
    def _generate_validation_summary(self) -> Dict[str, Any]:
        """Gerar resumo das validações"""
        # Group results by type and status
        summary = {}
        for result_type in ['data_integrity', 'performance', 'user_experience', 'error_rates']:
            type_results = [r for r in self.validation_results if r.validation_type == result_type]
            summary[result_type] = {
                'total_validations': len(type_results),
                'passed': len([r for r in type_results if r.status == 'passed']),
                'warnings': len([r for r in type_results if r.status == 'warning']),
                'critical': len([r for r in type_results if r.status == 'critical']),
                'success_rate': self.validation_stats[f'{result_type}_success_rate']
            }
        
        return summary
    
    async def _generate_final_recommendations(self) -> List[str]:
        """Gerar recomendações finais"""
        recommendations = []
        
        # Analyze validation results and generate recommendations
        if self.validation_stats['data_integrity_success_rate'] < 100:
            recommendations.append("Address data integrity issues identified during validation")
        
        if self.validation_stats['performance_success_rate'] < 95:
            recommendations.append("Optimize performance bottlenecks found during validation")
        
        if self.validation_stats['user_experience_success_rate'] < 90:
            recommendations.append("Improve user experience issues detected during validation")
        
        if self.validation_stats['critical_validations'] > 0:
            recommendations.append("Resolve all critical issues before final approval")
        
        return recommendations
    
    def _determine_approval_status(self) -> Dict[str, Any]:
        """Determinar status de aprovação final"""
        criteria = self._evaluate_success_criteria()
        
        all_criteria_met = all(c['met'] for c in criteria.values())
        no_critical_issues = self.validation_stats['critical_validations'] == 0
        
        approved = all_criteria_met and no_critical_issues
        
        return {
            'approved': approved,
            'criteria_met': all_criteria_met,
            'critical_issues_resolved': no_critical_issues,
            'approval_timestamp': datetime.now().isoformat() if approved else None,
            'next_steps': "System approved for production" if approved else "Address issues before approval"
        }
    
    async def cleanup(self):
        """Limpeza final"""
        self.is_validating = False
        
        if self.redis_client:
            await self.redis_client.close()
        
        await self.dashboard.stop()
        
        self.logger.info("Validation cleanup completed")

async def main():
    """Função principal para executar validação contínua"""
    config = ValidationConfig()
    manager = ContinuousValidationManager(config)
    
    try:
        final_report = await manager.start_continuous_validation()
        print(f"96-hour validation completed. Final report: {final_report}")
        
        if final_report['approval_status']['approved']:
            print("✅ SYSTEM APPROVED FOR PRODUCTION")
        else:
            print("❌ SYSTEM REQUIRES ADDITIONAL WORK")
            
    except Exception as e:
        print(f"Validation failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())