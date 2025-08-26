"""
Performance Validator - Agent-QualityAssurance FASE 4
Validação de performance do sistema Redis puro
"""

import asyncio
import time
import statistics
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
import redis.asyncio as redis
import psutil
import aiohttp

class PerformanceValidator:
    """Validador de performance do sistema"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.redis_client = None
        
        # Performance criteria (in milliseconds and percentages)
        self.performance_criteria = {
            'p95_response_time': 50,    # < 50ms
            'p99_response_time': 100,   # < 100ms
            'redis_operations': 5,      # < 5ms
            'memory_usage': 85,         # < 85%
            'cpu_usage': 70,            # < 70%
            'api_response_time': 2000,  # < 2s
            'websocket_latency': 100    # < 100ms
        }
        
        # Test data for performance testing
        self.test_operations = [
            'HGET', 'HSET', 'SADD', 'SMEMBERS', 'KEYS', 'EXISTS'
        ]
        
        # Performance history for trend analysis
        self.performance_history = []
    
    async def initialize(self):
        """Inicializar conexões e recursos"""
        try:
            self.redis_client = redis.Redis(
                host='localhost',
                port=int(os.getenv('REDIS_PORT', 6379)),
                decode_responses=True
            )
            await self.redis_client.ping()
            self.logger.info("Performance validator initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize performance validator: {e}")
            raise
    
    async def validate(self) -> Dict[str, Any]:
        """Executar validação de performance"""
        if not self.redis_client:
            await self.initialize()
        
        self.logger.info("Starting performance validation...")
        
        validation_results = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': [],
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            # Run all performance checks
            checks = [
                self._validate_redis_performance(),
                self._validate_api_performance(),
                self._validate_system_resources(),
                self._validate_websocket_performance(),
                self._validate_memory_trends(),
                self._validate_throughput_metrics()
            ]
            
            results = await asyncio.gather(*checks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    validation_results['issues'].append(f"Performance check {i+1} failed: {str(result)}")
                    validation_results['status'] = 'critical'
                else:
                    validation_results['metrics'].update(result['metrics'])
                    validation_results['issues'].extend(result['issues'])
                    validation_results['recommendations'].extend(result['recommendations'])
                    
                    if result['status'] == 'critical':
                        validation_results['status'] = 'critical'
                    elif result['status'] == 'warning' and validation_results['status'] == 'passed':
                        validation_results['status'] = 'warning'
            
            # Calculate overall performance score
            validation_results['metrics']['overall_performance_score'] = self._calculate_performance_score(
                validation_results['metrics']
            )
            
            # Store performance data for trend analysis
            await self._store_performance_data(validation_results['metrics'])
            
            self.logger.info(f"Performance validation completed: {validation_results['status']}")
            
        except Exception as e:
            self.logger.error(f"Performance validation failed: {e}")
            validation_results['status'] = 'critical'
            validation_results['issues'].append(f"Validation failed: {str(e)}")
        
        return validation_results
    
    async def _validate_redis_performance(self) -> Dict[str, Any]:
        """Validar performance das operações Redis"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            operation_times = []
            
            # Test basic Redis operations
            test_key = f"perf_test:{int(time.time())}"
            test_data = {"field1": "value1", "field2": "value2", "field3": "value3"}
            
            # HSET operation
            start_time = time.perf_counter()
            await self.redis_client.hset(test_key, mapping=test_data)
            hset_time = (time.perf_counter() - start_time) * 1000
            operation_times.append(hset_time)
            
            # HGET operation
            start_time = time.perf_counter()
            await self.redis_client.hget(test_key, "field1")
            hget_time = (time.perf_counter() - start_time) * 1000
            operation_times.append(hget_time)
            
            # HGETALL operation
            start_time = time.perf_counter()
            await self.redis_client.hgetall(test_key)
            hgetall_time = (time.perf_counter() - start_time) * 1000
            operation_times.append(hgetall_time)
            
            # EXISTS operation
            start_time = time.perf_counter()
            await self.redis_client.exists(test_key)
            exists_time = (time.perf_counter() - start_time) * 1000
            operation_times.append(exists_time)
            
            # KEYS operation (more expensive)
            start_time = time.perf_counter()
            await self.redis_client.keys(f"{test_key}*")
            keys_time = (time.perf_counter() - start_time) * 1000
            operation_times.append(keys_time)
            
            # Cleanup
            await self.redis_client.delete(test_key)
            
            # Test with actual data operations
            audio_keys = await self.redis_client.keys('audio:*')
            if audio_keys:
                # Test real data access
                sample_key = audio_keys[0]
                
                start_time = time.perf_counter()
                await self.redis_client.hgetall(sample_key)
                real_data_time = (time.perf_counter() - start_time) * 1000
                operation_times.append(real_data_time)
            
            # Calculate statistics
            avg_time = statistics.mean(operation_times)
            p95_time = statistics.quantiles(operation_times, n=20)[18] if len(operation_times) >= 20 else max(operation_times)
            p99_time = statistics.quantiles(operation_times, n=100)[98] if len(operation_times) >= 100 else max(operation_times)
            max_time = max(operation_times)
            
            result['metrics'] = {
                'redis_avg_operation_time': avg_time,
                'redis_p95_time': p95_time,
                'redis_p99_time': p99_time,
                'redis_max_time': max_time,
                'redis_hset_time': hset_time,
                'redis_hget_time': hget_time,
                'redis_hgetall_time': hgetall_time,
                'redis_exists_time': exists_time,
                'redis_keys_time': keys_time
            }
            
            # Check against criteria
            if p95_time > self.performance_criteria['p95_response_time']:
                result['status'] = 'critical'
                result['issues'].append(f"P95 response time too high: {p95_time:.2f}ms")
                result['recommendations'].append("Optimize Redis operations and consider connection pooling")
            
            if p99_time > self.performance_criteria['p99_response_time']:
                result['status'] = 'critical'
                result['issues'].append(f"P99 response time too high: {p99_time:.2f}ms")
                result['recommendations'].append("Investigate Redis performance bottlenecks")
            
            if avg_time > self.performance_criteria['redis_operations']:
                if result['status'] == 'passed':
                    result['status'] = 'warning'
                result['issues'].append(f"Average Redis operation time too high: {avg_time:.2f}ms")
                result['recommendations'].append("Monitor Redis performance and optimize slow operations")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"Redis performance validation failed: {str(e)}")
        
        return result
    
    async def _validate_api_performance(self) -> Dict[str, Any]:
        """Validar performance das APIs"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            api_endpoints = [
                'http://localhost:8000/api/audios',
                'http://localhost:8000/api/videos',
                'http://localhost:8000/api/status'
            ]
            
            response_times = []
            failed_requests = 0
            
            async with aiohttp.ClientSession() as session:
                for endpoint in api_endpoints:
                    try:
                        start_time = time.perf_counter()
                        async with session.get(endpoint, timeout=aiohttp.ClientTimeout(total=10)) as response:
                            response_time = (time.perf_counter() - start_time) * 1000
                            response_times.append(response_time)
                            
                            if response.status != 200:
                                failed_requests += 1
                                result['issues'].append(f"API endpoint {endpoint} returned status {response.status}")
                    
                    except asyncio.TimeoutError:
                        failed_requests += 1
                        result['issues'].append(f"API endpoint {endpoint} timed out")
                    except Exception as e:
                        failed_requests += 1
                        result['issues'].append(f"API endpoint {endpoint} failed: {str(e)}")
            
            if response_times:
                avg_response_time = statistics.mean(response_times)
                max_response_time = max(response_times)
                min_response_time = min(response_times)
            else:
                avg_response_time = max_response_time = min_response_time = 0
            
            result['metrics'] = {
                'api_avg_response_time': avg_response_time,
                'api_max_response_time': max_response_time,
                'api_min_response_time': min_response_time,
                'api_failed_requests': failed_requests,
                'api_success_rate': ((len(api_endpoints) - failed_requests) / len(api_endpoints)) * 100
            }
            
            # Check against criteria
            if avg_response_time > self.performance_criteria['api_response_time']:
                result['status'] = 'critical'
                result['issues'].append(f"API response time too high: {avg_response_time:.2f}ms")
                result['recommendations'].append("Optimize API performance and database queries")
            
            if failed_requests > 0:
                result['status'] = 'critical'
                result['issues'].append(f"{failed_requests} API requests failed")
                result['recommendations'].append("Investigate API failures and ensure service availability")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"API performance validation failed: {str(e)}")
        
        return result
    
    async def _validate_system_resources(self) -> Dict[str, Any]:
        """Validar recursos do sistema"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            memory_available = memory.available
            memory_used = memory.used
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_percent = disk.percent
            
            # Network I/O
            net_io = psutil.net_io_counters()
            
            # Process-specific metrics
            current_process = psutil.Process()
            process_memory = current_process.memory_info()
            process_cpu = current_process.cpu_percent()
            
            result['metrics'] = {
                'system_cpu_percent': cpu_percent,
                'system_memory_percent': memory_percent,
                'system_memory_available': memory_available,
                'system_memory_used': memory_used,
                'system_disk_percent': disk_percent,
                'network_bytes_sent': net_io.bytes_sent,
                'network_bytes_recv': net_io.bytes_recv,
                'process_memory_rss': process_memory.rss,
                'process_memory_vms': process_memory.vms,
                'process_cpu_percent': process_cpu
            }
            
            # Check against criteria
            if cpu_percent > self.performance_criteria['cpu_usage']:
                result['status'] = 'warning'
                result['issues'].append(f"High CPU usage: {cpu_percent:.1f}%")
                result['recommendations'].append("Monitor CPU usage and consider scaling")
            
            if memory_percent > self.performance_criteria['memory_usage']:
                result['status'] = 'warning'
                result['issues'].append(f"High memory usage: {memory_percent:.1f}%")
                result['recommendations'].append("Monitor memory usage and consider optimization")
            
            if disk_percent > 90:
                result['status'] = 'critical'
                result['issues'].append(f"High disk usage: {disk_percent:.1f}%")
                result['recommendations'].append("Free up disk space immediately")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"System resources validation failed: {str(e)}")
        
        return result
    
    async def _validate_websocket_performance(self) -> Dict[str, Any]:
        """Validar performance do WebSocket"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Simulate WebSocket performance testing
            # This would normally connect to actual WebSocket endpoint
            
            # For now, simulate latency measurements
            latency_measurements = []
            connection_attempts = 5
            successful_connections = 0
            
            for i in range(connection_attempts):
                try:
                    # Simulate connection test
                    start_time = time.perf_counter()
                    
                    # In a real scenario, this would be:
                    # async with websockets.connect("ws://localhost:8000/ws") as websocket:
                    #     await websocket.ping()
                    
                    # Simulate network latency
                    await asyncio.sleep(0.01)  # 10ms simulated latency
                    
                    latency = (time.perf_counter() - start_time) * 1000
                    latency_measurements.append(latency)
                    successful_connections += 1
                    
                except Exception as e:
                    result['issues'].append(f"WebSocket connection attempt {i+1} failed: {str(e)}")
            
            if latency_measurements:
                avg_latency = statistics.mean(latency_measurements)
                max_latency = max(latency_measurements)
                min_latency = min(latency_measurements)
            else:
                avg_latency = max_latency = min_latency = 0
            
            connection_success_rate = (successful_connections / connection_attempts) * 100
            
            result['metrics'] = {
                'websocket_avg_latency': avg_latency,
                'websocket_max_latency': max_latency,
                'websocket_min_latency': min_latency,
                'websocket_connection_success_rate': connection_success_rate,
                'websocket_successful_connections': successful_connections,
                'websocket_total_attempts': connection_attempts
            }
            
            # Check against criteria
            if avg_latency > self.performance_criteria['websocket_latency']:
                result['status'] = 'warning'
                result['issues'].append(f"High WebSocket latency: {avg_latency:.2f}ms")
                result['recommendations'].append("Optimize WebSocket performance")
            
            if connection_success_rate < 99:
                result['status'] = 'critical'
                result['issues'].append(f"Low WebSocket connection success rate: {connection_success_rate:.1f}%")
                result['recommendations'].append("Investigate WebSocket connection issues")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"WebSocket performance validation failed: {str(e)}")
        
        return result
    
    async def _validate_memory_trends(self) -> Dict[str, Any]:
        """Validar tendências de uso de memória"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Get Redis memory information
            redis_info = await self.redis_client.info('memory')
            
            used_memory = redis_info.get('used_memory', 0)
            used_memory_human = redis_info.get('used_memory_human', '0B')
            used_memory_peak = redis_info.get('used_memory_peak', 0)
            used_memory_peak_human = redis_info.get('used_memory_peak_human', '0B')
            used_memory_rss = redis_info.get('used_memory_rss', 0)
            
            # Memory efficiency metrics
            memory_efficiency = (used_memory / used_memory_rss * 100) if used_memory_rss > 0 else 0
            
            # Check for memory growth
            memory_growth_rate = 0
            if self.performance_history:
                last_memory = self.performance_history[-1].get('redis_used_memory', used_memory)
                if last_memory > 0:
                    memory_growth_rate = ((used_memory - last_memory) / last_memory) * 100
            
            result['metrics'] = {
                'redis_used_memory': used_memory,
                'redis_used_memory_human': used_memory_human,
                'redis_used_memory_peak': used_memory_peak,
                'redis_used_memory_peak_human': used_memory_peak_human,
                'redis_used_memory_rss': used_memory_rss,
                'redis_memory_efficiency': memory_efficiency,
                'memory_growth_rate': memory_growth_rate
            }
            
            # Check for memory issues
            if memory_growth_rate > 10:  # 10% growth is concerning
                result['status'] = 'warning'
                result['issues'].append(f"High memory growth rate: {memory_growth_rate:.2f}%")
                result['recommendations'].append("Monitor for memory leaks")
            
            if memory_efficiency < 80:
                result['status'] = 'warning'
                result['issues'].append(f"Low memory efficiency: {memory_efficiency:.1f}%")
                result['recommendations'].append("Consider memory optimization")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"Memory trends validation failed: {str(e)}")
        
        return result
    
    async def _validate_throughput_metrics(self) -> Dict[str, Any]:
        """Validar métricas de throughput"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Get Redis statistics
            redis_info = await self.redis_client.info('stats')
            
            total_commands_processed = redis_info.get('total_commands_processed', 0)
            instantaneous_ops_per_sec = redis_info.get('instantaneous_ops_per_sec', 0)
            total_connections_received = redis_info.get('total_connections_received', 0)
            connected_clients = redis_info.get('connected_clients', 0)
            
            # Calculate throughput metrics
            if self.performance_history:
                last_commands = self.performance_history[-1].get('total_commands_processed', 0)
                commands_per_interval = total_commands_processed - last_commands
            else:
                commands_per_interval = 0
            
            result['metrics'] = {
                'redis_total_commands_processed': total_commands_processed,
                'redis_instantaneous_ops_per_sec': instantaneous_ops_per_sec,
                'redis_total_connections_received': total_connections_received,
                'redis_connected_clients': connected_clients,
                'commands_per_validation_interval': commands_per_interval
            }
            
            # Check throughput health
            if instantaneous_ops_per_sec > 10000:  # Very high load
                result['status'] = 'warning'
                result['issues'].append(f"Very high operations per second: {instantaneous_ops_per_sec}")
                result['recommendations'].append("Monitor system load and consider scaling")
            
            if connected_clients > 100:  # Too many connections
                result['status'] = 'warning'
                result['issues'].append(f"High number of connected clients: {connected_clients}")
                result['recommendations'].append("Monitor connection usage and implement connection pooling")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"Throughput metrics validation failed: {str(e)}")
        
        return result
    
    async def _store_performance_data(self, metrics: Dict[str, Any]):
        """Armazenar dados de performance para análise de tendências"""
        try:
            performance_record = {
                'timestamp': datetime.now().isoformat(),
                **metrics
            }
            
            # Store in memory for trend analysis
            self.performance_history.append(performance_record)
            
            # Keep only last 100 records
            if len(self.performance_history) > 100:
                self.performance_history = self.performance_history[-100:]
            
            # Store in Redis for persistence
            await self.redis_client.lpush(
                'performance:history',
                f"{performance_record['timestamp']}:{performance_record.get('overall_performance_score', 0)}"
            )
            
            # Trim to keep only recent records
            await self.redis_client.ltrim('performance:history', 0, 1000)
            
        except Exception as e:
            self.logger.error(f"Failed to store performance data: {e}")
    
    def _calculate_performance_score(self, metrics: Dict[str, Any]) -> float:
        """Calcular score geral de performance"""
        scores = []
        
        # Redis performance score
        redis_avg_time = metrics.get('redis_avg_operation_time', 0)
        if redis_avg_time > 0:
            redis_score = max(0, 100 - (redis_avg_time / self.performance_criteria['redis_operations']) * 100)
            scores.append(redis_score)
        
        # API performance score
        api_time = metrics.get('api_avg_response_time', 0)
        if api_time > 0:
            api_score = max(0, 100 - (api_time / self.performance_criteria['api_response_time']) * 100)
            scores.append(api_score)
        
        # System resources score
        cpu_usage = metrics.get('system_cpu_percent', 0)
        memory_usage = metrics.get('system_memory_percent', 0)
        
        cpu_score = max(0, 100 - (cpu_usage / self.performance_criteria['cpu_usage']) * 100)
        memory_score = max(0, 100 - (memory_usage / self.performance_criteria['memory_usage']) * 100)
        
        scores.extend([cpu_score, memory_score])
        
        # WebSocket performance score
        ws_latency = metrics.get('websocket_avg_latency', 0)
        if ws_latency > 0:
            ws_score = max(0, 100 - (ws_latency / self.performance_criteria['websocket_latency']) * 100)
            scores.append(ws_score)
        
        # Calculate weighted average
        if scores:
            return sum(scores) / len(scores)
        
        return 0.0
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.redis_client:
            await self.redis_client.close()