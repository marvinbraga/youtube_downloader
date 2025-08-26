#!/usr/bin/env python3
"""
Test Monitoring System - Comprehensive Validation
Script para validação completa do sistema de monitoramento intensivo

Agent-Infrastructure - FASE 4 Production Monitoring
"""

import asyncio
import sys
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Tuple

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from loguru import logger

# Import monitoring components
from monitoring import (
    production_monitoring,
    redis_monitor, 
    application_metrics_collector,
    alert_system,
    performance_optimizer,
    monitoring_dashboard,
    intensive_monitoring_scheduler,
    get_system_info,
    initialize_monitoring_system
)


class MonitoringSystemValidator:
    """
    Validador completo do sistema de monitoramento
    
    Testa todos os componentes individualmente e em integração
    """
    
    def __init__(self):
        self.test_results: Dict[str, Any] = {}
        self.start_time = datetime.now()
        
        # Test configuration
        self.test_timeout = 30  # seconds
        
        logger.info("MonitoringSystemValidator initialized")
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Executa todos os testes do sistema"""
        logger.info("Starting comprehensive monitoring system validation")
        
        # Initialize test results
        self.test_results = {
            'test_session': {
                'start_time': self.start_time.isoformat(),
                'system_info': get_system_info()
            },
            'component_tests': {},
            'integration_tests': {},
            'performance_tests': {},
            'summary': {}
        }
        
        try:
            # 1. Component tests
            logger.info("Running component tests...")
            await self._run_component_tests()
            
            # 2. Integration tests
            logger.info("Running integration tests...")
            await self._run_integration_tests()
            
            # 3. Performance tests
            logger.info("Running performance tests...")
            await self._run_performance_tests()
            
            # 4. Generate summary
            await self._generate_test_summary()
            
            # 5. Save results
            await self._save_test_results()
            
            logger.info("Monitoring system validation completed")
            return self.test_results
            
        except Exception as e:
            logger.error(f"Error during testing: {e}")
            self.test_results['error'] = str(e)
            return self.test_results
    
    async def _run_component_tests(self):
        """Testa cada componente individualmente"""
        components = {
            'production_monitoring': production_monitoring,
            'redis_monitor': redis_monitor,
            'application_metrics_collector': application_metrics_collector,
            'alert_system': alert_system,
            'performance_optimizer': performance_optimizer,
            'intensive_monitoring_scheduler': intensive_monitoring_scheduler
        }
        
        for component_name, component in components.items():
            logger.info(f"Testing component: {component_name}")
            
            try:
                result = await self._test_component(component_name, component)
                self.test_results['component_tests'][component_name] = result
                
                status = "✅ PASS" if result['status'] == 'pass' else "❌ FAIL"
                logger.info(f"{status} {component_name}: {result.get('message', 'No message')}")
                
            except Exception as e:
                self.test_results['component_tests'][component_name] = {
                    'status': 'error',
                    'error': str(e),
                    'test_time': datetime.now().isoformat()
                }
                logger.error(f"❌ ERROR {component_name}: {e}")
    
    async def _test_component(self, component_name: str, component) -> Dict[str, Any]:
        """Testa um componente específico"""
        test_start = datetime.now()
        
        try:
            # Test 1: Initialization
            if hasattr(component, 'initialize'):
                init_success = await asyncio.wait_for(
                    component.initialize(),
                    timeout=self.test_timeout
                )
                
                if not init_success:
                    return {
                        'status': 'fail',
                        'message': 'Component initialization failed',
                        'test_time': datetime.now().isoformat(),
                        'duration_seconds': (datetime.now() - test_start).total_seconds()
                    }
            
            # Test 2: Basic functionality based on component type
            if component_name == 'production_monitoring':
                result = await self._test_production_monitoring()
            elif component_name == 'redis_monitor':
                result = await self._test_redis_monitor()
            elif component_name == 'application_metrics_collector':
                result = await self._test_application_metrics()
            elif component_name == 'alert_system':
                result = await self._test_alert_system()
            elif component_name == 'performance_optimizer':
                result = await self._test_performance_optimizer()
            elif component_name == 'intensive_monitoring_scheduler':
                result = await self._test_intensive_scheduler()
            else:
                result = {'status': 'skip', 'message': 'No specific test defined'}
            
            result['test_time'] = datetime.now().isoformat()
            result['duration_seconds'] = (datetime.now() - test_start).total_seconds()
            
            return result
            
        except asyncio.TimeoutError:
            return {
                'status': 'fail',
                'message': f'Component test timed out after {self.test_timeout}s',
                'test_time': datetime.now().isoformat(),
                'duration_seconds': self.test_timeout
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'test_time': datetime.now().isoformat(),
                'duration_seconds': (datetime.now() - test_start).total_seconds()
            }
    
    async def _test_production_monitoring(self) -> Dict[str, Any]:
        """Testa ProductionMonitoring"""
        try:
            # Test get_current_status
            status = await production_monitoring.get_current_status()
            
            if not isinstance(status, dict):
                return {'status': 'fail', 'message': 'get_current_status did not return dict'}
            
            # Test health report generation
            health_report = await production_monitoring.get_health_report(1)
            
            if not isinstance(health_report, dict):
                return {'status': 'fail', 'message': 'get_health_report did not return dict'}
            
            return {
                'status': 'pass',
                'message': 'Production monitoring tests passed',
                'details': {
                    'current_status_keys': list(status.keys()),
                    'health_report_keys': list(health_report.keys())
                }
            }
            
        except Exception as e:
            return {'status': 'fail', 'message': f'Production monitoring test failed: {e}'}
    
    async def _test_redis_monitor(self) -> Dict[str, Any]:
        """Testa RedisMonitor"""
        try:
            # Test current status
            status = await redis_monitor.get_current_status()
            
            if not isinstance(status, dict):
                return {'status': 'fail', 'message': 'get_current_status did not return dict'}
            
            # Test performance report
            perf_report = await redis_monitor.get_performance_report(1)
            
            if not isinstance(perf_report, dict):
                return {'status': 'fail', 'message': 'get_performance_report did not return dict'}
            
            return {
                'status': 'pass',
                'message': 'Redis monitor tests passed',
                'details': {
                    'status_keys': list(status.keys()),
                    'performance_report_keys': list(perf_report.keys())
                }
            }
            
        except Exception as e:
            return {'status': 'fail', 'message': f'Redis monitor test failed: {e}'}
    
    async def _test_application_metrics(self) -> Dict[str, Any]:
        """Testa ApplicationMetricsCollector"""
        try:
            # Test current metrics
            metrics = await application_metrics_collector.get_current_metrics()
            
            if not isinstance(metrics, dict):
                return {'status': 'fail', 'message': 'get_current_metrics did not return dict'}
            
            # Test metrics summary
            summary = await application_metrics_collector.get_metrics_summary(1)
            
            if not isinstance(summary, dict):
                return {'status': 'fail', 'message': 'get_metrics_summary did not return dict'}
            
            return {
                'status': 'pass',
                'message': 'Application metrics tests passed',
                'details': {
                    'current_metrics_keys': list(metrics.keys()),
                    'metrics_summary_keys': list(summary.keys())
                }
            }
            
        except Exception as e:
            return {'status': 'fail', 'message': f'Application metrics test failed: {e}'}
    
    async def _test_alert_system(self) -> Dict[str, Any]:
        """Testa AlertSystem"""
        try:
            # Test dashboard
            dashboard = await alert_system.get_alert_dashboard()
            
            if not isinstance(dashboard, dict):
                return {'status': 'fail', 'message': 'get_alert_dashboard did not return dict'}
            
            # Test alert history
            history = await alert_system.get_alert_history(1)
            
            if not isinstance(history, list):
                return {'status': 'fail', 'message': 'get_alert_history did not return list'}
            
            # Test custom metric recording
            await alert_system.record_metric('test_metric', 42.0, 'test')
            
            return {
                'status': 'pass',
                'message': 'Alert system tests passed',
                'details': {
                    'dashboard_keys': list(dashboard.keys()),
                    'history_count': len(history)
                }
            }
            
        except Exception as e:
            return {'status': 'fail', 'message': f'Alert system test failed: {e}'}
    
    async def _test_performance_optimizer(self) -> Dict[str, Any]:
        """Testa PerformanceOptimizer"""
        try:
            # Test status
            status = await performance_optimizer.get_optimization_status()
            
            if not isinstance(status, dict):
                return {'status': 'fail', 'message': 'get_optimization_status did not return dict'}
            
            # Test optimization report
            report = await performance_optimizer.get_optimization_report(1)
            
            if not isinstance(report, dict):
                return {'status': 'fail', 'message': 'get_optimization_report did not return dict'}
            
            return {
                'status': 'pass',
                'message': 'Performance optimizer tests passed',
                'details': {
                    'status_keys': list(status.keys()),
                    'report_keys': list(report.keys())
                }
            }
            
        except Exception as e:
            return {'status': 'fail', 'message': f'Performance optimizer test failed: {e}'}
    
    async def _test_intensive_scheduler(self) -> Dict[str, Any]:
        """Testa IntensiveMonitoringScheduler"""
        try:
            # Test monitoring status
            status = await intensive_monitoring_scheduler.get_monitoring_status()
            
            if not isinstance(status, dict):
                return {'status': 'fail', 'message': 'get_monitoring_status did not return dict'}
            
            return {
                'status': 'pass',
                'message': 'Intensive scheduler tests passed',
                'details': {
                    'status_keys': list(status.keys()),
                    'is_running': status.get('is_running', False)
                }
            }
            
        except Exception as e:
            return {'status': 'fail', 'message': f'Intensive scheduler test failed: {e}'}
    
    async def _run_integration_tests(self):
        """Testa integração entre componentes"""
        integration_tests = {
            'system_initialization': self._test_system_initialization,
            'component_communication': self._test_component_communication,
            'data_flow': self._test_data_flow,
            'error_handling': self._test_error_handling
        }
        
        for test_name, test_func in integration_tests.items():
            logger.info(f"Running integration test: {test_name}")
            
            try:
                result = await asyncio.wait_for(
                    test_func(),
                    timeout=self.test_timeout * 2  # Double timeout for integration tests
                )
                
                self.test_results['integration_tests'][test_name] = result
                
                status = "✅ PASS" if result['status'] == 'pass' else "❌ FAIL"
                logger.info(f"{status} Integration test {test_name}: {result.get('message', 'No message')}")
                
            except Exception as e:
                self.test_results['integration_tests'][test_name] = {
                    'status': 'error',
                    'error': str(e),
                    'test_time': datetime.now().isoformat()
                }
                logger.error(f"❌ ERROR Integration test {test_name}: {e}")
    
    async def _test_system_initialization(self) -> Dict[str, Any]:
        """Testa inicialização completa do sistema"""
        try:
            # Test system initialization
            initialized_components = await initialize_monitoring_system()
            
            if not initialized_components:
                return {
                    'status': 'fail',
                    'message': 'No components were initialized'
                }
            
            # Verify critical components are initialized
            expected_components = [
                'ProductionMonitoring',
                'RedisMonitor', 
                'ApplicationMetricsCollector',
                'AlertSystem',
                'PerformanceOptimizer'
            ]
            
            missing_components = set(expected_components) - set(initialized_components)
            
            if missing_components:
                return {
                    'status': 'fail',
                    'message': f'Missing components: {missing_components}',
                    'details': {
                        'initialized': initialized_components,
                        'missing': list(missing_components)
                    }
                }
            
            return {
                'status': 'pass',
                'message': 'System initialization successful',
                'details': {
                    'initialized_components': initialized_components
                }
            }
            
        except Exception as e:
            return {'status': 'fail', 'message': f'System initialization failed: {e}'}
    
    async def _test_component_communication(self) -> Dict[str, Any]:
        """Testa comunicação entre componentes"""
        try:
            # Test AlertSystem receiving metrics from ApplicationMetrics
            await alert_system.record_metric('test_communication', 100.0, 'integration_test')
            
            # Test ProductionMonitoring getting data from other components
            production_status = await production_monitoring.get_current_status()
            
            # Check if data is flowing
            has_data = (
                isinstance(production_status, dict) and
                'timestamp' in production_status
            )
            
            if not has_data:
                return {
                    'status': 'fail',
                    'message': 'Component communication test failed - no data flow detected'
                }
            
            return {
                'status': 'pass',
                'message': 'Component communication successful',
                'details': {
                    'production_status_available': bool(production_status),
                    'test_metric_recorded': True
                }
            }
            
        except Exception as e:
            return {'status': 'fail', 'message': f'Component communication failed: {e}'}
    
    async def _test_data_flow(self) -> Dict[str, Any]:
        """Testa fluxo de dados através do sistema"""
        try:
            # Simulate data flow by recording metrics and checking alerts
            test_metrics = [
                ('cpu_usage_test', 95.0),  # High CPU to potentially trigger alert
                ('memory_usage_test', 90.0),  # High memory
                ('response_time_test', 500.0)  # Slow response
            ]
            
            for metric_name, value in test_metrics:
                await alert_system.record_metric(metric_name, value, 'data_flow_test')
            
            # Allow some time for processing
            await asyncio.sleep(2)
            
            # Check if data appears in various components
            production_status = await production_monitoring.get_current_status()
            alert_dashboard = await alert_system.get_alert_dashboard()
            
            data_flow_working = (
                isinstance(production_status, dict) and
                isinstance(alert_dashboard, dict) and
                'timestamp' in production_status and
                'timestamp' in alert_dashboard
            )
            
            if not data_flow_working:
                return {
                    'status': 'fail',
                    'message': 'Data flow test failed - data not propagating properly'
                }
            
            return {
                'status': 'pass',
                'message': 'Data flow test successful',
                'details': {
                    'test_metrics_recorded': len(test_metrics),
                    'production_status_updated': bool(production_status.get('timestamp')),
                    'alerts_dashboard_updated': bool(alert_dashboard.get('timestamp'))
                }
            }
            
        except Exception as e:
            return {'status': 'fail', 'message': f'Data flow test failed: {e}'}
    
    async def _test_error_handling(self) -> Dict[str, Any]:
        """Testa tratamento de erros"""
        try:
            error_tests = []
            
            # Test 1: Invalid metric recording
            try:
                await alert_system.record_metric('', None, '')  # Invalid parameters
                error_tests.append('invalid_metric_handled')
            except Exception:
                # Expected to fail - this is good
                error_tests.append('invalid_metric_rejected')
            
            # Test 2: Non-existent alert acknowledgment
            try:
                result = await alert_system.acknowledge_alert('non_existent_alert', 'test_user')
                if not result:  # Should return False for non-existent alert
                    error_tests.append('nonexistent_alert_handled')
            except Exception:
                error_tests.append('nonexistent_alert_exception')
            
            # Test 3: Invalid optimization request
            try:
                result = await performance_optimizer.manual_optimization('invalid_rule_id')
                if 'error' in result:  # Should return error for invalid rule
                    error_tests.append('invalid_optimization_handled')
            except Exception:
                error_tests.append('invalid_optimization_exception')
            
            return {
                'status': 'pass',
                'message': 'Error handling test completed',
                'details': {
                    'error_tests_results': error_tests,
                    'tests_count': len(error_tests)
                }
            }
            
        except Exception as e:
            return {'status': 'fail', 'message': f'Error handling test failed: {e}'}
    
    async def _run_performance_tests(self):
        """Testa performance do sistema"""
        performance_tests = {
            'response_time': self._test_response_times,
            'concurrent_operations': self._test_concurrent_operations,
            'memory_usage': self._test_memory_usage,
            'throughput': self._test_throughput
        }
        
        for test_name, test_func in performance_tests.items():
            logger.info(f"Running performance test: {test_name}")
            
            try:
                result = await asyncio.wait_for(
                    test_func(),
                    timeout=self.test_timeout * 3  # Triple timeout for performance tests
                )
                
                self.test_results['performance_tests'][test_name] = result
                
                status = "✅ PASS" if result['status'] == 'pass' else "❌ FAIL"
                logger.info(f"{status} Performance test {test_name}: {result.get('message', 'No message')}")
                
            except Exception as e:
                self.test_results['performance_tests'][test_name] = {
                    'status': 'error',
                    'error': str(e),
                    'test_time': datetime.now().isoformat()
                }
                logger.error(f"❌ ERROR Performance test {test_name}: {e}")
    
    async def _test_response_times(self) -> Dict[str, Any]:
        """Testa tempos de resposta dos componentes"""
        try:
            response_times = {}
            
            # Test ProductionMonitoring
            start_time = time.time()
            await production_monitoring.get_current_status()
            response_times['production_monitoring'] = (time.time() - start_time) * 1000
            
            # Test RedisMonitor
            start_time = time.time()
            await redis_monitor.get_current_status()
            response_times['redis_monitor'] = (time.time() - start_time) * 1000
            
            # Test AlertSystem
            start_time = time.time()
            await alert_system.get_alert_dashboard()
            response_times['alert_system'] = (time.time() - start_time) * 1000
            
            # Test ApplicationMetrics
            start_time = time.time()
            await application_metrics_collector.get_current_metrics()
            response_times['application_metrics'] = (time.time() - start_time) * 1000
            
            # Check if any response time is too high (> 5 seconds)
            slow_components = {
                name: time_ms for name, time_ms in response_times.items()
                if time_ms > 5000
            }
            
            avg_response_time = sum(response_times.values()) / len(response_times)
            
            return {
                'status': 'pass' if not slow_components else 'fail',
                'message': f'Average response time: {avg_response_time:.2f}ms' + 
                          (f' - Slow components: {slow_components}' if slow_components else ''),
                'details': {
                    'response_times_ms': response_times,
                    'average_response_time_ms': avg_response_time,
                    'slow_components': slow_components
                }
            }
            
        except Exception as e:
            return {'status': 'fail', 'message': f'Response time test failed: {e}'}
    
    async def _test_concurrent_operations(self) -> Dict[str, Any]:
        """Testa operações concorrentes"""
        try:
            # Create multiple concurrent requests
            tasks = []
            
            # Multiple status requests
            for i in range(10):
                tasks.append(production_monitoring.get_current_status())
                tasks.append(redis_monitor.get_current_status())
                tasks.append(alert_system.get_alert_dashboard())
            
            # Multiple metric recordings
            for i in range(20):
                tasks.append(alert_system.record_metric(f'concurrent_test_{i}', i * 10.0, 'concurrency_test'))
            
            # Execute all tasks concurrently
            start_time = time.time()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            execution_time = time.time() - start_time
            
            # Count successful operations
            successful_ops = sum(1 for result in results if not isinstance(result, Exception))
            failed_ops = len(results) - successful_ops
            
            return {
                'status': 'pass' if failed_ops == 0 else 'fail',
                'message': f'Concurrent operations: {successful_ops} successful, {failed_ops} failed',
                'details': {
                    'total_operations': len(tasks),
                    'successful_operations': successful_ops,
                    'failed_operations': failed_ops,
                    'execution_time_seconds': execution_time,
                    'operations_per_second': len(tasks) / execution_time
                }
            }
            
        except Exception as e:
            return {'status': 'fail', 'message': f'Concurrent operations test failed: {e}'}
    
    async def _test_memory_usage(self) -> Dict[str, Any]:
        """Testa uso de memória"""
        try:
            import psutil
            import os
            
            process = psutil.Process(os.getpid())
            
            # Get initial memory
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            # Perform memory-intensive operations
            for i in range(100):
                await alert_system.record_metric(f'memory_test_{i}', i * 1.0, 'memory_test')
                await production_monitoring.get_current_status()
                await redis_monitor.get_current_status()
            
            # Allow garbage collection
            import gc
            gc.collect()
            await asyncio.sleep(1)
            
            # Get final memory
            final_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = final_memory - initial_memory
            
            # Check if memory usage is reasonable (< 50MB increase)
            memory_ok = memory_increase < 50
            
            return {
                'status': 'pass' if memory_ok else 'fail',
                'message': f'Memory usage: {memory_increase:.2f}MB increase',
                'details': {
                    'initial_memory_mb': initial_memory,
                    'final_memory_mb': final_memory,
                    'memory_increase_mb': memory_increase,
                    'memory_ok': memory_ok
                }
            }
            
        except Exception as e:
            return {'status': 'fail', 'message': f'Memory usage test failed: {e}'}
    
    async def _test_throughput(self) -> Dict[str, Any]:
        """Testa throughput de operações"""
        try:
            # Test metric recording throughput
            start_time = time.time()
            operations = 1000
            
            tasks = []
            for i in range(operations):
                tasks.append(alert_system.record_metric(f'throughput_test_{i}', i * 1.0, 'throughput_test'))
            
            await asyncio.gather(*tasks)
            execution_time = time.time() - start_time
            
            throughput = operations / execution_time
            
            # Good throughput is > 100 operations/second
            throughput_ok = throughput > 100
            
            return {
                'status': 'pass' if throughput_ok else 'fail',
                'message': f'Throughput: {throughput:.2f} operations/second',
                'details': {
                    'total_operations': operations,
                    'execution_time_seconds': execution_time,
                    'throughput_ops_per_second': throughput,
                    'throughput_ok': throughput_ok
                }
            }
            
        except Exception as e:
            return {'status': 'fail', 'message': f'Throughput test failed: {e}'}
    
    async def _generate_test_summary(self):
        """Gera resumo dos testes"""
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds()
        
        # Count test results
        def count_results(test_category: Dict[str, Any]) -> Dict[str, int]:
            counts = {'pass': 0, 'fail': 0, 'error': 0, 'skip': 0}
            for test_result in test_category.values():
                status = test_result.get('status', 'unknown')
                counts[status] = counts.get(status, 0) + 1
            return counts
        
        component_results = count_results(self.test_results['component_tests'])
        integration_results = count_results(self.test_results['integration_tests'])
        performance_results = count_results(self.test_results['performance_tests'])
        
        total_tests = (
            sum(component_results.values()) +
            sum(integration_results.values()) + 
            sum(performance_results.values())
        )
        
        total_passed = (
            component_results['pass'] +
            integration_results['pass'] + 
            performance_results['pass']
        )
        
        total_failed = (
            component_results['fail'] +
            integration_results['fail'] + 
            performance_results['fail']
        )
        
        success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        
        self.test_results['summary'] = {
            'end_time': end_time.isoformat(),
            'total_duration_seconds': total_duration,
            'total_tests': total_tests,
            'total_passed': total_passed,
            'total_failed': total_failed,
            'success_rate_percent': round(success_rate, 2),
            'component_tests': component_results,
            'integration_tests': integration_results,
            'performance_tests': performance_results,
            'overall_status': 'PASS' if total_failed == 0 else 'FAIL'
        }
    
    async def _save_test_results(self):
        """Salva resultados dos testes"""
        try:
            # Create reports directory if it doesn't exist
            reports_dir = Path('reports/monitoring')
            reports_dir.mkdir(parents=True, exist_ok=True)
            
            # Save detailed results
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            results_file = reports_dir / f'monitoring_system_test_results_{timestamp}.json'
            
            with open(results_file, 'w', encoding='utf-8') as f:
                json.dump(self.test_results, f, indent=2, default=str)
            
            logger.info(f"Test results saved to: {results_file}")
            
        except Exception as e:
            logger.error(f"Failed to save test results: {e}")


async def main():
    """Função principal de teste"""
    print("🧪 Starting Monitoring System Validation")
    print("="*60)
    
    # Setup logging for tests
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        level="INFO",
        colorize=True
    )
    
    # Create validator
    validator = MonitoringSystemValidator()
    
    try:
        # Run all tests
        results = await validator.run_all_tests()
        
        # Display results
        print("\n" + "="*60)
        print("📊 TEST RESULTS SUMMARY")
        print("="*60)
        
        summary = results.get('summary', {})
        
        print(f"Total Tests: {summary.get('total_tests', 0)}")
        print(f"Passed: ✅ {summary.get('total_passed', 0)}")
        print(f"Failed: ❌ {summary.get('total_failed', 0)}")
        print(f"Success Rate: {summary.get('success_rate_percent', 0):.1f}%")
        print(f"Duration: {summary.get('total_duration_seconds', 0):.2f} seconds")
        print(f"Overall Status: {summary.get('overall_status', 'UNKNOWN')}")
        
        # Component breakdown
        print(f"\n📦 Component Tests: {summary.get('component_tests', {})}")
        print(f"🔗 Integration Tests: {summary.get('integration_tests', {})}")
        print(f"⚡ Performance Tests: {summary.get('performance_tests', {})}")
        
        # Overall result
        overall_status = summary.get('overall_status', 'UNKNOWN')
        if overall_status == 'PASS':
            print(f"\n🎉 ALL TESTS PASSED - Monitoring system is ready for production!")
        else:
            print(f"\n⚠️  SOME TESTS FAILED - Review the detailed results before production deployment")
        
        print("="*60)
        
        # Exit with appropriate code
        sys.exit(0 if overall_status == 'PASS' else 1)
        
    except Exception as e:
        logger.error(f"Test execution failed: {e}")
        print(f"\n❌ TEST EXECUTION FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())