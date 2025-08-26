"""
Error Rate Validator - Agent-QualityAssurance FASE 4
Validação de taxas de erro do sistema Redis puro
"""

import asyncio
import json
import time
import statistics
from typing import Dict, List, Any, Optional, Set
from datetime import datetime, timedelta
import logging
import redis.asyncio as redis
from collections import defaultdict, Counter
import re

class ErrorRateValidator:
    """Validador de taxas de erro do sistema"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.redis_client = None
        
        # Error rate criteria (percentages)
        self.error_criteria = {
            'api_error_rate': 1.0,         # < 1%
            'redis_connection_errors': 0.1, # < 0.1%
            'timeout_errors': 0.5,         # < 0.5%
            'data_corruption': 0.0,        # 0%
            'recovery_success_rate': 99.0,  # > 99%
            'system_availability': 99.0,   # > 99%
            'download_failure_rate': 5.0,  # < 5%
            'transcription_error_rate': 10.0 # < 10%
        }
        
        # Error categories
        self.error_categories = {
            'critical': ['data_corruption', 'system_crash', 'redis_data_loss'],
            'major': ['api_timeout', 'download_failure', 'connection_lost'],
            'minor': ['transcription_timeout', 'ui_glitch', 'warning_message'],
            'recoverable': ['temporary_slowdown', 'retry_success', 'graceful_degradation']
        }
        
        # Error tracking
        self.error_history = []
        self.error_patterns = defaultdict(list)
        
        # Monitoring timeframes
        self.monitoring_windows = {
            'last_5min': 300,
            'last_15min': 900,
            'last_1hour': 3600,
            'last_24hours': 86400
        }
    
    async def initialize(self):
        """Inicializar conexões e recursos"""
        try:
            self.redis_client = redis.Redis(
                host='localhost',
                port=int(os.getenv('REDIS_PORT', 6379)),
                decode_responses=True
            )
            await self.redis_client.ping()
            self.logger.info("Error rate validator initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize error rate validator: {e}")
            raise
    
    async def validate(self) -> Dict[str, Any]:
        """Executar validação de taxas de erro"""
        if not self.redis_client:
            await self.initialize()
        
        self.logger.info("Starting error rate validation...")
        
        validation_results = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': [],
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            # Run all error rate validation checks
            checks = [
                self._validate_api_error_rates(),
                self._validate_redis_connection_errors(),
                self._validate_timeout_errors(),
                self._validate_data_corruption(),
                self._validate_recovery_success_rates(),
                self._validate_system_availability(),
                self._validate_download_failure_rates(),
                self._validate_transcription_errors(),
                self._analyze_error_patterns(),
                self._validate_error_trending()
            ]
            
            results = await asyncio.gather(*checks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    validation_results['issues'].append(f"Error rate check {i+1} failed: {str(result)}")
                    validation_results['status'] = 'critical'
                else:
                    validation_results['metrics'].update(result['metrics'])
                    validation_results['issues'].extend(result['issues'])
                    validation_results['recommendations'].extend(result['recommendations'])
                    
                    if result['status'] == 'critical':
                        validation_results['status'] = 'critical'
                    elif result['status'] == 'warning' and validation_results['status'] == 'passed':
                        validation_results['status'] = 'warning'
            
            # Calculate overall error health score
            validation_results['metrics']['overall_error_health_score'] = self._calculate_error_health_score(
                validation_results['metrics']
            )
            
            # Store error metrics for trend analysis
            await self._store_error_metrics(validation_results['metrics'])
            
            self.logger.info(f"Error rate validation completed: {validation_results['status']}")
            
        except Exception as e:
            self.logger.error(f"Error rate validation failed: {e}")
            validation_results['status'] = 'critical'
            validation_results['issues'].append(f"Validation failed: {str(e)}")
        
        return validation_results
    
    async def _validate_api_error_rates(self) -> Dict[str, Any]:
        """Validar taxas de erro das APIs"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Get API error logs from Redis
            api_logs = await self.redis_client.lrange('api:error_log', 0, -1)
            
            total_requests = 0
            error_requests = 0
            error_types = Counter()
            recent_errors = []
            
            # Get total request count
            total_requests = await self.redis_client.get('api:total_requests') or 0
            total_requests = int(total_requests)
            
            # Analyze error logs
            current_time = datetime.now()
            for log_entry in api_logs:
                try:
                    error_data = json.loads(log_entry)
                    error_time = datetime.fromisoformat(error_data.get('timestamp', ''))
                    
                    # Count errors in different time windows
                    time_diff = (current_time - error_time).total_seconds()
                    
                    if time_diff <= self.monitoring_windows['last_24hours']:
                        error_requests += 1
                        error_types[error_data.get('error_type', 'unknown')] += 1
                        
                        if time_diff <= self.monitoring_windows['last_1hour']:
                            recent_errors.append(error_data)
                
                except (json.JSONDecodeError, ValueError) as e:
                    self.logger.warning(f"Failed to parse API error log entry: {e}")
                    continue
            
            # Calculate error rates for different time windows
            error_rates = {}
            for window_name, window_seconds in self.monitoring_windows.items():
                window_errors = sum(1 for log in api_logs 
                                  if self._is_within_timeframe(log, window_seconds))
                window_requests = max(1, total_requests // (86400 // window_seconds))  # Estimate requests for window
                error_rates[window_name] = (window_errors / window_requests * 100) if window_requests > 0 else 0
            
            # Overall API error rate
            overall_error_rate = (error_requests / total_requests * 100) if total_requests > 0 else 0
            
            result['metrics'] = {
                'api_overall_error_rate': overall_error_rate,
                'api_total_requests': total_requests,
                'api_error_requests': error_requests,
                'api_error_types': dict(error_types),
                'api_recent_errors_count': len(recent_errors),
                **{f'api_error_rate_{k}': v for k, v in error_rates.items()}
            }
            
            # Check against criteria
            if overall_error_rate > self.error_criteria['api_error_rate']:
                result['status'] = 'critical'
                result['issues'].append(f"API error rate too high: {overall_error_rate:.2f}%")
                result['recommendations'].append("Investigate and fix API error sources")
            
            # Check for error spikes
            if error_rates.get('last_5min', 0) > overall_error_rate * 2:
                result['status'] = 'critical'
                result['issues'].append(f"API error spike detected in last 5 minutes")
                result['recommendations'].append("Investigate recent API error spike")
            
            # Analyze error patterns
            most_common_errors = error_types.most_common(3)
            if most_common_errors:
                for error_type, count in most_common_errors:
                    if count > error_requests * 0.3:  # > 30% of errors are same type
                        result['issues'].append(f"High frequency of {error_type} errors: {count} occurrences")
                        result['recommendations'].append(f"Focus on fixing {error_type} errors")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"API error rate validation failed: {str(e)}")
        
        return result
    
    async def _validate_redis_connection_errors(self) -> Dict[str, Any]:
        """Validar erros de conexão Redis"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Get Redis connection statistics
            redis_info = await self.redis_client.info('stats')
            
            total_connections = redis_info.get('total_connections_received', 0)
            rejected_connections = redis_info.get('rejected_connections', 0)
            
            # Get Redis error logs
            redis_error_logs = await self.redis_client.lrange('redis:connection_errors', 0, -1)
            
            connection_errors = 0
            timeout_errors = 0
            auth_errors = 0
            
            current_time = datetime.now()
            for log_entry in redis_error_logs:
                try:
                    error_data = json.loads(log_entry)
                    error_time = datetime.fromisoformat(error_data.get('timestamp', ''))
                    
                    time_diff = (current_time - error_time).total_seconds()
                    if time_diff <= self.monitoring_windows['last_24hours']:
                        error_type = error_data.get('error_type', '')
                        if 'connection' in error_type.lower():
                            connection_errors += 1
                        elif 'timeout' in error_type.lower():
                            timeout_errors += 1
                        elif 'auth' in error_type.lower():
                            auth_errors += 1
                
                except (json.JSONDecodeError, ValueError):
                    continue
            
            # Calculate error rates
            connection_error_rate = (connection_errors / total_connections * 100) if total_connections > 0 else 0
            rejection_rate = (rejected_connections / total_connections * 100) if total_connections > 0 else 0
            
            result['metrics'] = {
                'redis_connection_error_rate': connection_error_rate,
                'redis_connection_rejection_rate': rejection_rate,
                'redis_total_connections': total_connections,
                'redis_rejected_connections': rejected_connections,
                'redis_connection_errors': connection_errors,
                'redis_timeout_errors': timeout_errors,
                'redis_auth_errors': auth_errors
            }
            
            # Check against criteria
            if connection_error_rate > self.error_criteria['redis_connection_errors']:
                result['status'] = 'critical'
                result['issues'].append(f"Redis connection error rate too high: {connection_error_rate:.2f}%")
                result['recommendations'].append("Investigate Redis connection stability")
            
            if rejection_rate > 1.0:  # > 1% rejections is concerning
                result['status'] = 'warning'
                result['issues'].append(f"High Redis connection rejection rate: {rejection_rate:.2f}%")
                result['recommendations'].append("Check Redis configuration and connection limits")
            
            if auth_errors > 0:
                result['status'] = 'critical'
                result['issues'].append(f"Redis authentication errors detected: {auth_errors}")
                result['recommendations'].append("Check Redis authentication configuration")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"Redis connection error validation failed: {str(e)}")
        
        return result
    
    async def _validate_timeout_errors(self) -> Dict[str, Any]:
        """Validar erros de timeout"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Get timeout error logs
            timeout_logs = await self.redis_client.lrange('system:timeout_errors', 0, -1)
            
            total_operations = await self.redis_client.get('system:total_operations') or 0
            total_operations = int(total_operations)
            
            timeout_errors = 0
            api_timeouts = 0
            database_timeouts = 0
            network_timeouts = 0
            download_timeouts = 0
            
            current_time = datetime.now()
            for log_entry in timeout_logs:
                try:
                    timeout_data = json.loads(log_entry)
                    error_time = datetime.fromisoformat(timeout_data.get('timestamp', ''))
                    
                    time_diff = (current_time - error_time).total_seconds()
                    if time_diff <= self.monitoring_windows['last_24hours']:
                        timeout_errors += 1
                        
                        timeout_type = timeout_data.get('timeout_type', '').lower()
                        if 'api' in timeout_type:
                            api_timeouts += 1
                        elif 'database' in timeout_type or 'redis' in timeout_type:
                            database_timeouts += 1
                        elif 'network' in timeout_type:
                            network_timeouts += 1
                        elif 'download' in timeout_type:
                            download_timeouts += 1
                
                except (json.JSONDecodeError, ValueError):
                    continue
            
            # Calculate timeout rates
            overall_timeout_rate = (timeout_errors / total_operations * 100) if total_operations > 0 else 0
            
            result['metrics'] = {
                'overall_timeout_error_rate': overall_timeout_rate,
                'total_timeout_errors': timeout_errors,
                'api_timeout_errors': api_timeouts,
                'database_timeout_errors': database_timeouts,
                'network_timeout_errors': network_timeouts,
                'download_timeout_errors': download_timeouts,
                'total_operations_tracked': total_operations
            }
            
            # Check against criteria
            if overall_timeout_rate > self.error_criteria['timeout_errors']:
                result['status'] = 'critical'
                result['issues'].append(f"Timeout error rate too high: {overall_timeout_rate:.2f}%")
                result['recommendations'].append("Investigate and optimize timeout-prone operations")
            
            # Check specific timeout categories
            if api_timeouts > timeout_errors * 0.5:  # > 50% of timeouts are API-related
                result['status'] = 'warning'
                result['issues'].append(f"High API timeout rate: {api_timeouts} out of {timeout_errors} timeouts")
                result['recommendations'].append("Optimize API response times")
            
            if download_timeouts > 10:  # Absolute threshold for download timeouts
                result['status'] = 'warning'
                result['issues'].append(f"High download timeout errors: {download_timeouts}")
                result['recommendations'].append("Investigate download timeout issues")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"Timeout error validation failed: {str(e)}")
        
        return result
    
    async def _validate_data_corruption(self) -> Dict[str, Any]:
        """Validar corrupção de dados"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Check for data corruption indicators
            corruption_indicators = 0
            total_data_checks = 0
            
            # Check audio data integrity
            audio_keys = await self.redis_client.keys('audio:*')
            for key in audio_keys[:20]:  # Sample check
                try:
                    audio_data = await self.redis_client.hgetall(key)
                    total_data_checks += 1
                    
                    # Check for corruption indicators
                    if not audio_data:
                        corruption_indicators += 1
                        result['issues'].append(f"Empty audio data for key: {key}")
                        continue
                    
                    # Check required fields
                    required_fields = ['id', 'title', 'url', 'status']
                    for field in required_fields:
                        if field not in audio_data or not audio_data[field]:
                            corruption_indicators += 1
                            result['issues'].append(f"Missing or empty {field} in {key}")
                            break
                    
                    # Check data format consistency
                    if 'duration' in audio_data:
                        try:
                            float(audio_data['duration'])
                        except ValueError:
                            corruption_indicators += 1
                            result['issues'].append(f"Invalid duration format in {key}: {audio_data['duration']}")
                    
                except Exception as e:
                    total_data_checks += 1
                    corruption_indicators += 1
                    result['issues'].append(f"Failed to validate audio data {key}: {str(e)}")
            
            # Check video data integrity
            video_keys = await self.redis_client.keys('video:*')
            for key in video_keys[:20]:  # Sample check
                try:
                    video_data = await self.redis_client.hgetall(key)
                    total_data_checks += 1
                    
                    # Similar checks for video data
                    if not video_data:
                        corruption_indicators += 1
                        result['issues'].append(f"Empty video data for key: {key}")
                        continue
                    
                    required_fields = ['id', 'title', 'url', 'status']
                    for field in required_fields:
                        if field not in video_data or not video_data[field]:
                            corruption_indicators += 1
                            result['issues'].append(f"Missing or empty {field} in {key}")
                            break
                    
                except Exception as e:
                    total_data_checks += 1
                    corruption_indicators += 1
                    result['issues'].append(f"Failed to validate video data {key}: {str(e)}")
            
            # Calculate corruption rate
            corruption_rate = (corruption_indicators / total_data_checks * 100) if total_data_checks > 0 else 0
            
            result['metrics'] = {
                'data_corruption_rate': corruption_rate,
                'corruption_indicators_found': corruption_indicators,
                'total_data_checks_performed': total_data_checks,
                'audio_keys_checked': min(20, len(audio_keys)),
                'video_keys_checked': min(20, len(video_keys))
            }
            
            # Check against criteria (should be 0%)
            if corruption_rate > self.error_criteria['data_corruption']:
                result['status'] = 'critical'
                result['issues'].append(f"Data corruption detected: {corruption_rate:.2f}%")
                result['recommendations'].append("Immediately investigate and fix data corruption issues")
            
            if corruption_indicators > 0:
                result['status'] = 'critical'
                result['recommendations'].append("Run full data integrity check and repair corrupted data")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"Data corruption validation failed: {str(e)}")
        
        return result
    
    async def _validate_recovery_success_rates(self) -> Dict[str, Any]:
        """Validar taxas de sucesso de recuperação"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Get recovery attempt logs
            recovery_logs = await self.redis_client.lrange('system:recovery_attempts', 0, -1)
            
            total_recovery_attempts = 0
            successful_recoveries = 0
            failed_recoveries = 0
            recovery_types = Counter()
            
            current_time = datetime.now()
            for log_entry in recovery_logs:
                try:
                    recovery_data = json.loads(log_entry)
                    recovery_time = datetime.fromisoformat(recovery_data.get('timestamp', ''))
                    
                    time_diff = (current_time - recovery_time).total_seconds()
                    if time_diff <= self.monitoring_windows['last_24hours']:
                        total_recovery_attempts += 1
                        recovery_types[recovery_data.get('recovery_type', 'unknown')] += 1
                        
                        if recovery_data.get('status') == 'success':
                            successful_recoveries += 1
                        else:
                            failed_recoveries += 1
                
                except (json.JSONDecodeError, ValueError):
                    continue
            
            # Calculate recovery success rate
            recovery_success_rate = (successful_recoveries / total_recovery_attempts * 100) if total_recovery_attempts > 0 else 100
            
            result['metrics'] = {
                'recovery_success_rate': recovery_success_rate,
                'total_recovery_attempts': total_recovery_attempts,
                'successful_recoveries': successful_recoveries,
                'failed_recoveries': failed_recoveries,
                'recovery_types': dict(recovery_types)
            }
            
            # Check against criteria
            if recovery_success_rate < self.error_criteria['recovery_success_rate']:
                result['status'] = 'critical'
                result['issues'].append(f"Recovery success rate too low: {recovery_success_rate:.1f}%")
                result['recommendations'].append("Improve error recovery mechanisms")
            
            if failed_recoveries > 5:  # Absolute threshold
                result['status'] = 'warning'
                result['issues'].append(f"High number of failed recoveries: {failed_recoveries}")
                result['recommendations'].append("Investigate recovery failure patterns")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"Recovery success rate validation failed: {str(e)}")
        
        return result
    
    async def _validate_system_availability(self) -> Dict[str, Any]:
        """Validar disponibilidade do sistema"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Get system availability logs
            availability_logs = await self.redis_client.lrange('system:availability', 0, -1)
            
            total_uptime_checks = 0
            successful_checks = 0
            downtime_incidents = 0
            
            current_time = datetime.now()
            for log_entry in availability_logs:
                try:
                    availability_data = json.loads(log_entry)
                    check_time = datetime.fromisoformat(availability_data.get('timestamp', ''))
                    
                    time_diff = (current_time - check_time).total_seconds()
                    if time_diff <= self.monitoring_windows['last_24hours']:
                        total_uptime_checks += 1
                        
                        if availability_data.get('status') == 'up':
                            successful_checks += 1
                        else:
                            downtime_incidents += 1
                
                except (json.JSONDecodeError, ValueError):
                    continue
            
            # Calculate availability percentage
            availability_rate = (successful_checks / total_uptime_checks * 100) if total_uptime_checks > 0 else 100
            
            # Get current system status
            try:
                # Test Redis connectivity
                await self.redis_client.ping()
                redis_available = True
            except Exception:
                redis_available = False
                downtime_incidents += 1
            
            result['metrics'] = {
                'system_availability_rate': availability_rate,
                'total_uptime_checks': total_uptime_checks,
                'successful_availability_checks': successful_checks,
                'downtime_incidents': downtime_incidents,
                'redis_currently_available': redis_available
            }
            
            # Check against criteria
            if availability_rate < self.error_criteria['system_availability']:
                result['status'] = 'critical'
                result['issues'].append(f"System availability too low: {availability_rate:.1f}%")
                result['recommendations'].append("Investigate and fix system availability issues")
            
            if not redis_available:
                result['status'] = 'critical'
                result['issues'].append("Redis is currently unavailable")
                result['recommendations'].append("Immediately restore Redis service")
            
            if downtime_incidents > 2:  # More than 2 incidents in 24h
                result['status'] = 'warning'
                result['issues'].append(f"Multiple downtime incidents: {downtime_incidents}")
                result['recommendations'].append("Analyze downtime patterns and improve reliability")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"System availability validation failed: {str(e)}")
        
        return result
    
    async def _validate_download_failure_rates(self) -> Dict[str, Any]:
        """Validar taxas de falha de download"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Get download statistics from Redis
            total_downloads = await self.redis_client.get('downloads:total') or 0
            failed_downloads = await self.redis_client.get('downloads:failed') or 0
            
            total_downloads = int(total_downloads)
            failed_downloads = int(failed_downloads)
            
            # Get detailed download failure logs
            download_failure_logs = await self.redis_client.lrange('downloads:failures', 0, -1)
            
            recent_failures = 0
            failure_reasons = Counter()
            
            current_time = datetime.now()
            for log_entry in download_failure_logs:
                try:
                    failure_data = json.loads(log_entry)
                    failure_time = datetime.fromisoformat(failure_data.get('timestamp', ''))
                    
                    time_diff = (current_time - failure_time).total_seconds()
                    if time_diff <= self.monitoring_windows['last_24hours']:
                        recent_failures += 1
                        failure_reasons[failure_data.get('reason', 'unknown')] += 1
                
                except (json.JSONDecodeError, ValueError):
                    continue
            
            # Calculate failure rates
            overall_failure_rate = (failed_downloads / total_downloads * 100) if total_downloads > 0 else 0
            recent_failure_rate = (recent_failures / max(1, total_downloads // 30)) * 100  # Estimate daily rate
            
            result['metrics'] = {
                'download_failure_rate': overall_failure_rate,
                'recent_download_failure_rate': recent_failure_rate,
                'total_downloads': total_downloads,
                'failed_downloads': failed_downloads,
                'recent_failures': recent_failures,
                'failure_reasons': dict(failure_reasons)
            }
            
            # Check against criteria
            if overall_failure_rate > self.error_criteria['download_failure_rate']:
                result['status'] = 'critical'
                result['issues'].append(f"Download failure rate too high: {overall_failure_rate:.2f}%")
                result['recommendations'].append("Investigate and fix download failure causes")
            
            # Analyze failure patterns
            most_common_failures = failure_reasons.most_common(3)
            for reason, count in most_common_failures:
                if count > recent_failures * 0.3:  # > 30% of failures
                    result['issues'].append(f"High frequency of '{reason}' download failures: {count}")
                    result['recommendations'].append(f"Focus on fixing '{reason}' download issues")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"Download failure rate validation failed: {str(e)}")
        
        return result
    
    async def _validate_transcription_errors(self) -> Dict[str, Any]:
        """Validar erros de transcrição"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Get transcription statistics
            total_transcriptions = await self.redis_client.get('transcriptions:total') or 0
            failed_transcriptions = await self.redis_client.get('transcriptions:failed') or 0
            
            total_transcriptions = int(total_transcriptions)
            failed_transcriptions = int(failed_transcriptions)
            
            # Get transcription error logs
            transcription_error_logs = await self.redis_client.lrange('transcriptions:errors', 0, -1)
            
            recent_transcription_errors = 0
            transcription_error_types = Counter()
            
            current_time = datetime.now()
            for log_entry in transcription_error_logs:
                try:
                    error_data = json.loads(log_entry)
                    error_time = datetime.fromisoformat(error_data.get('timestamp', ''))
                    
                    time_diff = (current_time - error_time).total_seconds()
                    if time_diff <= self.monitoring_windows['last_24hours']:
                        recent_transcription_errors += 1
                        transcription_error_types[error_data.get('error_type', 'unknown')] += 1
                
                except (json.JSONDecodeError, ValueError):
                    continue
            
            # Calculate transcription error rates
            transcription_error_rate = (failed_transcriptions / total_transcriptions * 100) if total_transcriptions > 0 else 0
            
            result['metrics'] = {
                'transcription_error_rate': transcription_error_rate,
                'total_transcriptions': total_transcriptions,
                'failed_transcriptions': failed_transcriptions,
                'recent_transcription_errors': recent_transcription_errors,
                'transcription_error_types': dict(transcription_error_types)
            }
            
            # Check against criteria
            if transcription_error_rate > self.error_criteria['transcription_error_rate']:
                result['status'] = 'warning'
                result['issues'].append(f"Transcription error rate too high: {transcription_error_rate:.2f}%")
                result['recommendations'].append("Improve transcription service reliability")
            
            # Check for specific error patterns
            if 'api_limit' in transcription_error_types:
                result['issues'].append(f"Transcription API limit errors: {transcription_error_types['api_limit']}")
                result['recommendations'].append("Monitor transcription API usage and limits")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"Transcription error validation failed: {str(e)}")
        
        return result
    
    async def _analyze_error_patterns(self) -> Dict[str, Any]:
        """Analisar padrões de erro"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Collect all error logs for pattern analysis
            all_error_logs = []
            
            # Get different types of error logs
            error_log_keys = [
                'api:error_log',
                'redis:connection_errors',
                'system:timeout_errors',
                'downloads:failures',
                'transcriptions:errors'
            ]
            
            for log_key in error_log_keys:
                logs = await self.redis_client.lrange(log_key, 0, -1)
                for log in logs:
                    try:
                        error_data = json.loads(log)
                        error_data['log_type'] = log_key
                        all_error_logs.append(error_data)
                    except (json.JSONDecodeError, ValueError):
                        continue
            
            # Analyze temporal patterns
            hourly_errors = defaultdict(int)
            daily_errors = defaultdict(int)
            error_correlations = defaultdict(list)
            
            for error in all_error_logs:
                try:
                    timestamp = datetime.fromisoformat(error.get('timestamp', ''))
                    hour = timestamp.hour
                    day = timestamp.strftime('%Y-%m-%d')
                    
                    hourly_errors[hour] += 1
                    daily_errors[day] += 1
                    
                    # Look for correlated errors (same timestamp range)
                    for other_error in all_error_logs:
                        if error != other_error:
                            other_timestamp = datetime.fromisoformat(other_error.get('timestamp', ''))
                            if abs((timestamp - other_timestamp).total_seconds()) <= 60:  # Within 1 minute
                                error_correlations[error['log_type']].append(other_error['log_type'])
                
                except (ValueError, KeyError):
                    continue
            
            # Identify patterns
            peak_error_hours = sorted(hourly_errors.items(), key=lambda x: x[1], reverse=True)[:3]
            high_error_days = {day: count for day, count in daily_errors.items() if count > 10}
            
            # Find correlated error types
            frequent_correlations = {}
            for error_type, correlated_types in error_correlations.items():
                if correlated_types:
                    correlation_counter = Counter(correlated_types)
                    most_correlated = correlation_counter.most_common(1)[0]
                    if most_correlated[1] > 3:  # At least 3 correlations
                        frequent_correlations[error_type] = most_correlated
            
            result['metrics'] = {
                'total_errors_analyzed': len(all_error_logs),
                'peak_error_hours': dict(peak_error_hours),
                'high_error_days': high_error_days,
                'frequent_error_correlations': frequent_correlations,
                'unique_error_types': len(set(error['log_type'] for error in all_error_logs))
            }
            
            # Generate insights
            if peak_error_hours:
                peak_hour, peak_count = peak_error_hours[0]
                if peak_count > len(all_error_logs) * 0.2:  # > 20% of errors in one hour
                    result['issues'].append(f"Error spike pattern detected at hour {peak_hour} with {peak_count} errors")
                    result['recommendations'].append(f"Investigate system load and issues around hour {peak_hour}")
            
            if high_error_days:
                result['issues'].append(f"High error days detected: {list(high_error_days.keys())}")
                result['recommendations'].append("Analyze events on high-error days for common causes")
            
            if frequent_correlations:
                for error_type, (correlated_type, count) in frequent_correlations.items():
                    result['issues'].append(f"Frequent error correlation: {error_type} -> {correlated_type} ({count} times)")
                    result['recommendations'].append(f"Investigate relationship between {error_type} and {correlated_type} errors")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"Error pattern analysis failed: {str(e)}")
        
        return result
    
    async def _validate_error_trending(self) -> Dict[str, Any]:
        """Validar tendências de erro"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Get error counts for different time periods
            current_time = datetime.now()
            
            time_periods = {
                'last_hour': current_time - timedelta(hours=1),
                'last_6_hours': current_time - timedelta(hours=6),
                'last_24_hours': current_time - timedelta(hours=24),
                'last_week': current_time - timedelta(days=7)
            }
            
            error_counts = {}
            
            # Count errors in each time period
            all_error_logs = []
            error_log_keys = ['api:error_log', 'redis:connection_errors', 'system:timeout_errors']
            
            for log_key in error_log_keys:
                logs = await self.redis_client.lrange(log_key, 0, -1)
                for log in logs:
                    try:
                        error_data = json.loads(log)
                        error_time = datetime.fromisoformat(error_data.get('timestamp', ''))
                        all_error_logs.append((error_time, error_data))
                    except (json.JSONDecodeError, ValueError):
                        continue
            
            for period_name, period_start in time_periods.items():
                count = sum(1 for error_time, _ in all_error_logs if error_time >= period_start)
                error_counts[period_name] = count
            
            # Calculate error rate trends
            hourly_rate = error_counts['last_hour']
            six_hour_rate = error_counts['last_6_hours'] / 6
            daily_rate = error_counts['last_24_hours'] / 24
            weekly_rate = error_counts['last_week'] / (24 * 7)
            
            # Detect trends
            trending_up = hourly_rate > six_hour_rate > daily_rate
            trending_down = hourly_rate < six_hour_rate < daily_rate
            
            result['metrics'] = {
                'error_counts_by_period': error_counts,
                'hourly_error_rate': hourly_rate,
                'six_hour_error_rate': six_hour_rate,
                'daily_error_rate': daily_rate,
                'weekly_error_rate': weekly_rate,
                'error_trending_up': trending_up,
                'error_trending_down': trending_down
            }
            
            # Check for concerning trends
            if trending_up and hourly_rate > daily_rate * 2:
                result['status'] = 'warning'
                result['issues'].append(f"Error rate trending up: {hourly_rate}/hr vs {daily_rate:.1f}/hr average")
                result['recommendations'].append("Monitor error trend and investigate causes of increase")
            
            if hourly_rate > 20:  # Absolute threshold
                result['status'] = 'critical'
                result['issues'].append(f"Very high current error rate: {hourly_rate} errors in last hour")
                result['recommendations'].append("Immediately investigate high error rate")
            
            if trending_down:
                result['recommendations'].append("Error rate improving - continue monitoring")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"Error trending validation failed: {str(e)}")
        
        return result
    
    def _is_within_timeframe(self, log_entry: str, seconds: int) -> bool:
        """Verificar se entrada de log está dentro do timeframe"""
        try:
            error_data = json.loads(log_entry)
            error_time = datetime.fromisoformat(error_data.get('timestamp', ''))
            time_diff = (datetime.now() - error_time).total_seconds()
            return time_diff <= seconds
        except:
            return False
    
    async def _store_error_metrics(self, metrics: Dict[str, Any]):
        """Armazenar métricas de erro para análise de tendências"""
        try:
            error_record = {
                'timestamp': datetime.now().isoformat(),
                **metrics
            }
            
            # Store in memory for trend analysis
            self.error_history.append(error_record)
            
            # Keep only last 100 records
            if len(self.error_history) > 100:
                self.error_history = self.error_history[-100:]
            
            # Store in Redis for persistence
            await self.redis_client.lpush(
                'error_validation:history',
                json.dumps(error_record)
            )
            
            # Trim to keep only recent records
            await self.redis_client.ltrim('error_validation:history', 0, 1000)
            
        except Exception as e:
            self.logger.error(f"Failed to store error metrics: {e}")
    
    def _calculate_error_health_score(self, metrics: Dict[str, Any]) -> float:
        """Calcular score geral de saúde de erros"""
        scores = []
        
        # API error rate score (inverted - lower is better)
        api_error_rate = metrics.get('api_overall_error_rate', 0)
        api_score = max(0, 100 - (api_error_rate / self.error_criteria['api_error_rate']) * 100)
        scores.append(api_score)
        
        # Redis connection error score
        redis_error_rate = metrics.get('redis_connection_error_rate', 0)
        redis_score = max(0, 100 - (redis_error_rate / self.error_criteria['redis_connection_errors']) * 100)
        scores.append(redis_score)
        
        # Timeout error score
        timeout_rate = metrics.get('overall_timeout_error_rate', 0)
        timeout_score = max(0, 100 - (timeout_rate / self.error_criteria['timeout_errors']) * 100)
        scores.append(timeout_score)
        
        # Data corruption score (critical)
        corruption_rate = metrics.get('data_corruption_rate', 0)
        corruption_score = 0 if corruption_rate > 0 else 100
        scores.append(corruption_score * 2)  # Weight this heavily
        
        # Recovery success score
        recovery_rate = metrics.get('recovery_success_rate', 100)
        recovery_score = recovery_rate
        scores.append(recovery_score)
        
        # System availability score
        availability_rate = metrics.get('system_availability_rate', 100)
        scores.append(availability_rate)
        
        # Calculate weighted average
        if scores:
            return sum(scores) / len(scores)
        
        return 0.0
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.redis_client:
            await self.redis_client.close()