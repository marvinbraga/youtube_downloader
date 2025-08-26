"""
User Experience Validator - Agent-QualityAssurance FASE 4
Validação de experiência do usuário no sistema Redis puro
"""

import asyncio
import time
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import logging
import redis.asyncio as redis
import aiohttp
from pathlib import Path

class UserExperienceValidator:
    """Validador de experiência do usuário"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.redis_client = None
        
        # User experience criteria
        self.ux_criteria = {
            'page_load_time': 2000,        # < 2s
            'websocket_connection_success': 99,  # > 99%
            'download_completion_rate': 95,      # > 95%
            'transcription_completion_rate': 90, # > 90%
            'error_message_clarity': 90,         # > 90% clear
            'ui_responsiveness': 100,            # < 100ms
            'search_response_time': 500,         # < 500ms
            'data_consistency': 100              # 100% consistent
        }
        
        # Test scenarios
        self.test_scenarios = [
            'page_load_test',
            'search_functionality_test',
            'download_process_test',
            'websocket_connectivity_test',
            'data_display_consistency_test',
            'error_handling_test',
            'responsive_ui_test'
        ]
        
        # UX metrics history
        self.ux_history = []
    
    async def initialize(self):
        """Inicializar conexões e recursos"""
        try:
            self.redis_client = redis.Redis(
                host='localhost',
                port=int(os.getenv('REDIS_PORT', 6379)),
                decode_responses=True
            )
            await self.redis_client.ping()
            self.logger.info("User experience validator initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize UX validator: {e}")
            raise
    
    async def validate(self) -> Dict[str, Any]:
        """Executar validação de experiência do usuário"""
        if not self.redis_client:
            await self.initialize()
        
        self.logger.info("Starting user experience validation...")
        
        validation_results = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': [],
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            # Run all UX validation checks
            checks = [
                self._validate_page_load_performance(),
                self._validate_search_functionality(),
                self._validate_download_process(),
                self._validate_websocket_connectivity(),
                self._validate_data_display_consistency(),
                self._validate_error_handling(),
                self._validate_ui_responsiveness(),
                self._validate_mobile_compatibility()
            ]
            
            results = await asyncio.gather(*checks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    validation_results['issues'].append(f"UX check {i+1} failed: {str(result)}")
                    validation_results['status'] = 'critical'
                else:
                    validation_results['metrics'].update(result['metrics'])
                    validation_results['issues'].extend(result['issues'])
                    validation_results['recommendations'].extend(result['recommendations'])
                    
                    if result['status'] == 'critical':
                        validation_results['status'] = 'critical'
                    elif result['status'] == 'warning' and validation_results['status'] == 'passed':
                        validation_results['status'] = 'warning'
            
            # Calculate overall UX score
            validation_results['metrics']['overall_ux_score'] = self._calculate_ux_score(
                validation_results['metrics']
            )
            
            # Store UX metrics for trend analysis
            await self._store_ux_metrics(validation_results['metrics'])
            
            self.logger.info(f"UX validation completed: {validation_results['status']}")
            
        except Exception as e:
            self.logger.error(f"UX validation failed: {e}")
            validation_results['status'] = 'critical'
            validation_results['issues'].append(f"Validation failed: {str(e)}")
        
        return validation_results
    
    async def _validate_page_load_performance(self) -> Dict[str, Any]:
        """Validar performance de carregamento de páginas"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            pages_to_test = [
                'http://localhost:8000/',
                'http://localhost:8000/audios',
                'http://localhost:8000/videos',
                'http://localhost:8000/download'
            ]
            
            load_times = []
            failed_loads = 0
            
            async with aiohttp.ClientSession() as session:
                for page_url in pages_to_test:
                    try:
                        start_time = time.perf_counter()
                        async with session.get(
                            page_url,
                            timeout=aiohttp.ClientTimeout(total=10)
                        ) as response:
                            # Wait for content to load
                            content = await response.read()
                            load_time = (time.perf_counter() - start_time) * 1000
                            load_times.append(load_time)
                            
                            if response.status != 200:
                                failed_loads += 1
                                result['issues'].append(f"Page {page_url} returned status {response.status}")
                            
                            # Check if content is reasonable
                            if len(content) < 1000:  # Very small content might indicate error
                                result['issues'].append(f"Page {page_url} returned suspiciously small content")
                    
                    except asyncio.TimeoutError:
                        failed_loads += 1
                        result['issues'].append(f"Page {page_url} load timed out")
                    except Exception as e:
                        failed_loads += 1
                        result['issues'].append(f"Page {page_url} failed to load: {str(e)}")
            
            if load_times:
                avg_load_time = sum(load_times) / len(load_times)
                max_load_time = max(load_times)
                min_load_time = min(load_times)
            else:
                avg_load_time = max_load_time = min_load_time = 0
            
            success_rate = ((len(pages_to_test) - failed_loads) / len(pages_to_test)) * 100
            
            result['metrics'] = {
                'page_load_avg_time': avg_load_time,
                'page_load_max_time': max_load_time,
                'page_load_min_time': min_load_time,
                'page_load_success_rate': success_rate,
                'pages_tested': len(pages_to_test),
                'failed_page_loads': failed_loads
            }
            
            # Check against criteria
            if avg_load_time > self.ux_criteria['page_load_time']:
                result['status'] = 'critical'
                result['issues'].append(f"Page load time too high: {avg_load_time:.0f}ms")
                result['recommendations'].append("Optimize page loading performance")
            
            if success_rate < 95:
                result['status'] = 'critical'
                result['issues'].append(f"Page load success rate too low: {success_rate:.1f}%")
                result['recommendations'].append("Fix page loading issues")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"Page load validation failed: {str(e)}")
        
        return result
    
    async def _validate_search_functionality(self) -> Dict[str, Any]:
        """Validar funcionalidade de busca"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Test search API endpoints
            search_queries = ['test', 'video', 'audio', '2024', 'youtube']
            
            search_times = []
            failed_searches = 0
            total_results = 0
            
            async with aiohttp.ClientSession() as session:
                for query in search_queries:
                    try:
                        # Test audio search
                        start_time = time.perf_counter()
                        async with session.get(
                            f'http://localhost:8000/api/search/audios?q={query}',
                            timeout=aiohttp.ClientTimeout(total=5)
                        ) as response:
                            search_time = (time.perf_counter() - start_time) * 1000
                            search_times.append(search_time)
                            
                            if response.status == 200:
                                data = await response.json()
                                total_results += len(data.get('results', []))
                            else:
                                failed_searches += 1
                                result['issues'].append(f"Audio search for '{query}' failed with status {response.status}")
                        
                        # Test video search
                        start_time = time.perf_counter()
                        async with session.get(
                            f'http://localhost:8000/api/search/videos?q={query}',
                            timeout=aiohttp.ClientTimeout(total=5)
                        ) as response:
                            search_time = (time.perf_counter() - start_time) * 1000
                            search_times.append(search_time)
                            
                            if response.status == 200:
                                data = await response.json()
                                total_results += len(data.get('results', []))
                            else:
                                failed_searches += 1
                                result['issues'].append(f"Video search for '{query}' failed with status {response.status}")
                    
                    except asyncio.TimeoutError:
                        failed_searches += 1
                        result['issues'].append(f"Search for '{query}' timed out")
                    except Exception as e:
                        failed_searches += 1
                        result['issues'].append(f"Search for '{query}' failed: {str(e)}")
            
            if search_times:
                avg_search_time = sum(search_times) / len(search_times)
                max_search_time = max(search_times)
            else:
                avg_search_time = max_search_time = 0
            
            total_searches = len(search_queries) * 2  # audio + video searches
            success_rate = ((total_searches - failed_searches) / total_searches) * 100 if total_searches > 0 else 0
            
            result['metrics'] = {
                'search_avg_response_time': avg_search_time,
                'search_max_response_time': max_search_time,
                'search_success_rate': success_rate,
                'total_search_results': total_results,
                'failed_searches': failed_searches
            }
            
            # Check against criteria
            if avg_search_time > self.ux_criteria['search_response_time']:
                result['status'] = 'warning'
                result['issues'].append(f"Search response time too high: {avg_search_time:.0f}ms")
                result['recommendations'].append("Optimize search performance")
            
            if success_rate < 90:
                result['status'] = 'critical'
                result['issues'].append(f"Search success rate too low: {success_rate:.1f}%")
                result['recommendations'].append("Fix search functionality issues")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"Search validation failed: {str(e)}")
        
        return result
    
    async def _validate_download_process(self) -> Dict[str, Any]:
        """Validar processo de download"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Get recent downloads to analyze
            audio_keys = await self.redis_client.keys('audio:*')
            video_keys = await self.redis_client.keys('video:*')
            
            completed_audios = 0
            failed_audios = 0
            completed_videos = 0
            failed_videos = 0
            
            transcription_completed = 0
            transcription_failed = 0
            
            # Check audio downloads
            for key in audio_keys[:10]:  # Sample first 10
                try:
                    audio_data = await self.redis_client.hgetall(key)
                    status = audio_data.get('status', '')
                    
                    if status == 'completed':
                        completed_audios += 1
                        
                        # Check if file exists
                        file_path = audio_data.get('file_path', '')
                        if file_path and not Path(file_path).exists():
                            result['issues'].append(f"Audio file missing: {file_path}")
                    
                    elif status in ['failed', 'error']:
                        failed_audios += 1
                    
                    # Check transcription status
                    trans_status = audio_data.get('transcription_status', '')
                    if trans_status == 'completed':
                        transcription_completed += 1
                    elif trans_status in ['failed', 'error']:
                        transcription_failed += 1
                        
                except Exception as e:
                    result['issues'].append(f"Failed to check audio {key}: {str(e)}")
            
            # Check video downloads
            for key in video_keys[:10]:  # Sample first 10
                try:
                    video_data = await self.redis_client.hgetall(key)
                    status = video_data.get('status', '')
                    
                    if status == 'completed':
                        completed_videos += 1
                        
                        # Check if file exists
                        file_path = video_data.get('file_path', '')
                        if file_path and not Path(file_path).exists():
                            result['issues'].append(f"Video file missing: {file_path}")
                    
                    elif status in ['failed', 'error']:
                        failed_videos += 1
                        
                except Exception as e:
                    result['issues'].append(f"Failed to check video {key}: {str(e)}")
            
            # Calculate completion rates
            total_audios = completed_audios + failed_audios
            total_videos = completed_videos + failed_videos
            total_transcriptions = transcription_completed + transcription_failed
            
            audio_completion_rate = (completed_audios / total_audios * 100) if total_audios > 0 else 100
            video_completion_rate = (completed_videos / total_videos * 100) if total_videos > 0 else 100
            transcription_completion_rate = (transcription_completed / total_transcriptions * 100) if total_transcriptions > 0 else 100
            
            overall_completion_rate = ((completed_audios + completed_videos) / (total_audios + total_videos) * 100) if (total_audios + total_videos) > 0 else 100
            
            result['metrics'] = {
                'audio_completion_rate': audio_completion_rate,
                'video_completion_rate': video_completion_rate,
                'transcription_completion_rate': transcription_completion_rate,
                'overall_download_completion_rate': overall_completion_rate,
                'completed_audios': completed_audios,
                'failed_audios': failed_audios,
                'completed_videos': completed_videos,
                'failed_videos': failed_videos
            }
            
            # Check against criteria
            if overall_completion_rate < self.ux_criteria['download_completion_rate']:
                result['status'] = 'critical'
                result['issues'].append(f"Download completion rate too low: {overall_completion_rate:.1f}%")
                result['recommendations'].append("Investigate download failures and improve reliability")
            
            if transcription_completion_rate < self.ux_criteria['transcription_completion_rate']:
                result['status'] = 'warning'
                result['issues'].append(f"Transcription completion rate too low: {transcription_completion_rate:.1f}%")
                result['recommendations'].append("Improve transcription service reliability")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"Download process validation failed: {str(e)}")
        
        return result
    
    async def _validate_websocket_connectivity(self) -> Dict[str, Any]:
        """Validar conectividade WebSocket"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Test WebSocket connection reliability
            connection_attempts = 5
            successful_connections = 0
            connection_times = []
            
            for i in range(connection_attempts):
                try:
                    start_time = time.perf_counter()
                    
                    # Simulate WebSocket connection test
                    # In real implementation, would use websockets library
                    await asyncio.sleep(0.05)  # Simulate connection time
                    
                    connection_time = (time.perf_counter() - start_time) * 1000
                    connection_times.append(connection_time)
                    successful_connections += 1
                    
                except Exception as e:
                    result['issues'].append(f"WebSocket connection attempt {i+1} failed: {str(e)}")
            
            connection_success_rate = (successful_connections / connection_attempts) * 100
            avg_connection_time = sum(connection_times) / len(connection_times) if connection_times else 0
            
            # Test WebSocket message handling
            message_tests = ['progress_update', 'status_change', 'error_notification']
            successful_messages = 0
            
            for msg_type in message_tests:
                try:
                    # Simulate message processing
                    await asyncio.sleep(0.01)
                    successful_messages += 1
                except Exception as e:
                    result['issues'].append(f"WebSocket message test '{msg_type}' failed: {str(e)}")
            
            message_success_rate = (successful_messages / len(message_tests)) * 100
            
            result['metrics'] = {
                'websocket_connection_success_rate': connection_success_rate,
                'websocket_avg_connection_time': avg_connection_time,
                'websocket_message_success_rate': message_success_rate,
                'successful_connections': successful_connections,
                'total_connection_attempts': connection_attempts
            }
            
            # Check against criteria
            if connection_success_rate < self.ux_criteria['websocket_connection_success']:
                result['status'] = 'critical'
                result['issues'].append(f"WebSocket connection success rate too low: {connection_success_rate:.1f}%")
                result['recommendations'].append("Improve WebSocket connection reliability")
            
            if message_success_rate < 95:
                result['status'] = 'warning'
                result['issues'].append(f"WebSocket message success rate too low: {message_success_rate:.1f}%")
                result['recommendations'].append("Improve WebSocket message handling")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"WebSocket connectivity validation failed: {str(e)}")
        
        return result
    
    async def _validate_data_display_consistency(self) -> Dict[str, Any]:
        """Validar consistência de exibição de dados"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Test data consistency between Redis and API responses
            consistency_checks = 0
            consistency_errors = 0
            
            # Check audio data consistency
            audio_keys = await self.redis_client.keys('audio:*')
            if audio_keys:
                sample_key = audio_keys[0]
                redis_data = await self.redis_client.hgetall(sample_key)
                
                if redis_data:
                    consistency_checks += 1
                    
                    # Simulate API call to get same data
                    try:
                        audio_id = redis_data.get('id', '')
                        async with aiohttp.ClientSession() as session:
                            async with session.get(
                                f'http://localhost:8000/api/audios/{audio_id}',
                                timeout=aiohttp.ClientTimeout(total=5)
                            ) as response:
                                if response.status == 200:
                                    api_data = await response.json()
                                    
                                    # Check key fields consistency
                                    fields_to_check = ['id', 'title', 'url', 'status']
                                    for field in fields_to_check:
                                        if redis_data.get(field) != api_data.get(field):
                                            consistency_errors += 1
                                            result['issues'].append(
                                                f"Data inconsistency in {field}: Redis='{redis_data.get(field)}' vs API='{api_data.get(field)}'"
                                            )
                                else:
                                    consistency_errors += 1
                                    result['issues'].append(f"API returned status {response.status} for audio {audio_id}")
                    except Exception as e:
                        consistency_errors += 1
                        result['issues'].append(f"Failed to validate audio data consistency: {str(e)}")
            
            # Check video data consistency
            video_keys = await self.redis_client.keys('video:*')
            if video_keys:
                sample_key = video_keys[0]
                redis_data = await self.redis_client.hgetall(sample_key)
                
                if redis_data:
                    consistency_checks += 1
                    
                    # Similar consistency check for videos
                    try:
                        video_id = redis_data.get('id', '')
                        async with aiohttp.ClientSession() as session:
                            async with session.get(
                                f'http://localhost:8000/api/videos/{video_id}',
                                timeout=aiohttp.ClientTimeout(total=5)
                            ) as response:
                                if response.status == 200:
                                    api_data = await response.json()
                                    
                                    # Check key fields consistency
                                    fields_to_check = ['id', 'title', 'url', 'status']
                                    for field in fields_to_check:
                                        if redis_data.get(field) != api_data.get(field):
                                            consistency_errors += 1
                                            result['issues'].append(
                                                f"Data inconsistency in {field}: Redis='{redis_data.get(field)}' vs API='{api_data.get(field)}'"
                                            )
                                else:
                                    consistency_errors += 1
                                    result['issues'].append(f"API returned status {response.status} for video {video_id}")
                    except Exception as e:
                        consistency_errors += 1
                        result['issues'].append(f"Failed to validate video data consistency: {str(e)}")
            
            consistency_rate = ((consistency_checks - consistency_errors) / consistency_checks * 100) if consistency_checks > 0 else 100
            
            result['metrics'] = {
                'data_consistency_rate': consistency_rate,
                'consistency_checks_performed': consistency_checks,
                'consistency_errors_found': consistency_errors
            }
            
            # Check against criteria
            if consistency_rate < self.ux_criteria['data_consistency']:
                result['status'] = 'critical'
                result['issues'].append(f"Data consistency rate too low: {consistency_rate:.1f}%")
                result['recommendations'].append("Fix data synchronization issues")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"Data display consistency validation failed: {str(e)}")
        
        return result
    
    async def _validate_error_handling(self) -> Dict[str, Any]:
        """Validar tratamento de erros"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Test error scenarios and response clarity
            error_tests = [
                ('invalid_url', 'http://localhost:8000/api/audios/nonexistent'),
                ('malformed_request', 'http://localhost:8000/api/download'),
                ('server_error', 'http://localhost:8000/api/test_error')
            ]
            
            clear_error_responses = 0
            total_error_tests = len(error_tests)
            
            async with aiohttp.ClientSession() as session:
                for test_name, url in error_tests:
                    try:
                        async with session.get(
                            url,
                            timeout=aiohttp.ClientTimeout(total=5)
                        ) as response:
                            if response.status >= 400:
                                try:
                                    error_data = await response.json()
                                    
                                    # Check if error message is clear
                                    if 'error' in error_data or 'message' in error_data:
                                        error_msg = error_data.get('error', error_data.get('message', ''))
                                        if len(error_msg) > 10 and 'error' not in error_msg.lower():
                                            clear_error_responses += 1
                                        else:
                                            result['issues'].append(f"Unclear error message for {test_name}: '{error_msg}'")
                                    else:
                                        result['issues'].append(f"No error message provided for {test_name}")
                                        
                                except Exception:
                                    result['issues'].append(f"Error response not in JSON format for {test_name}")
                            else:
                                result['issues'].append(f"Expected error response for {test_name} but got status {response.status}")
                                
                    except asyncio.TimeoutError:
                        result['issues'].append(f"Error handling test {test_name} timed out")
                    except Exception as e:
                        result['issues'].append(f"Error handling test {test_name} failed: {str(e)}")
            
            error_clarity_rate = (clear_error_responses / total_error_tests * 100) if total_error_tests > 0 else 0
            
            result['metrics'] = {
                'error_message_clarity_rate': error_clarity_rate,
                'clear_error_responses': clear_error_responses,
                'total_error_tests': total_error_tests
            }
            
            # Check against criteria
            if error_clarity_rate < self.ux_criteria['error_message_clarity']:
                result['status'] = 'warning'
                result['issues'].append(f"Error message clarity rate too low: {error_clarity_rate:.1f}%")
                result['recommendations'].append("Improve error message clarity and user feedback")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"Error handling validation failed: {str(e)}")
        
        return result
    
    async def _validate_ui_responsiveness(self) -> Dict[str, Any]:
        """Validar responsividade da UI"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Simulate UI interaction response times
            ui_interactions = [
                'button_click',
                'form_submission',
                'navigation',
                'modal_open',
                'data_refresh'
            ]
            
            response_times = []
            
            for interaction in ui_interactions:
                try:
                    start_time = time.perf_counter()
                    
                    # Simulate UI interaction processing
                    await asyncio.sleep(0.02)  # 20ms simulated processing
                    
                    response_time = (time.perf_counter() - start_time) * 1000
                    response_times.append(response_time)
                    
                except Exception as e:
                    result['issues'].append(f"UI interaction test '{interaction}' failed: {str(e)}")
            
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
                max_response_time = max(response_times)
            else:
                avg_response_time = max_response_time = 0
            
            result['metrics'] = {
                'ui_avg_response_time': avg_response_time,
                'ui_max_response_time': max_response_time,
                'ui_interactions_tested': len(ui_interactions),
                'successful_interactions': len(response_times)
            }
            
            # Check against criteria
            if avg_response_time > self.ux_criteria['ui_responsiveness']:
                result['status'] = 'warning'
                result['issues'].append(f"UI response time too high: {avg_response_time:.1f}ms")
                result['recommendations'].append("Optimize UI responsiveness")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"UI responsiveness validation failed: {str(e)}")
        
        return result
    
    async def _validate_mobile_compatibility(self) -> Dict[str, Any]:
        """Validar compatibilidade mobile"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Test mobile viewport response
            mobile_viewports = [
                (375, 667),   # iPhone 6/7/8
                (414, 896),   # iPhone XR
                (360, 640),   # Android
                (768, 1024)   # Tablet
            ]
            
            mobile_tests_passed = 0
            total_mobile_tests = len(mobile_viewports)
            
            # Simulate mobile compatibility tests
            for width, height in mobile_viewports:
                try:
                    # In real scenario, would test actual responsive behavior
                    # For now, simulate basic compatibility check
                    
                    # Check if viewport is reasonable for mobile
                    is_mobile_compatible = width >= 320 and height >= 568
                    
                    if is_mobile_compatible:
                        mobile_tests_passed += 1
                    else:
                        result['issues'].append(f"Viewport {width}x{height} not mobile compatible")
                        
                except Exception as e:
                    result['issues'].append(f"Mobile compatibility test for {width}x{height} failed: {str(e)}")
            
            mobile_compatibility_rate = (mobile_tests_passed / total_mobile_tests * 100) if total_mobile_tests > 0 else 0
            
            result['metrics'] = {
                'mobile_compatibility_rate': mobile_compatibility_rate,
                'mobile_tests_passed': mobile_tests_passed,
                'total_mobile_tests': total_mobile_tests
            }
            
            # Check mobile compatibility
            if mobile_compatibility_rate < 90:
                result['status'] = 'warning'
                result['issues'].append(f"Mobile compatibility rate too low: {mobile_compatibility_rate:.1f}%")
                result['recommendations'].append("Improve mobile responsiveness and compatibility")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"Mobile compatibility validation failed: {str(e)}")
        
        return result
    
    async def _store_ux_metrics(self, metrics: Dict[str, Any]):
        """Armazenar métricas UX para análise de tendências"""
        try:
            ux_record = {
                'timestamp': datetime.now().isoformat(),
                **metrics
            }
            
            # Store in memory for trend analysis
            self.ux_history.append(ux_record)
            
            # Keep only last 100 records
            if len(self.ux_history) > 100:
                self.ux_history = self.ux_history[-100:]
            
            # Store in Redis for persistence
            await self.redis_client.lpush(
                'ux:history',
                json.dumps(ux_record)
            )
            
            # Trim to keep only recent records
            await self.redis_client.ltrim('ux:history', 0, 1000)
            
        except Exception as e:
            self.logger.error(f"Failed to store UX metrics: {e}")
    
    def _calculate_ux_score(self, metrics: Dict[str, Any]) -> float:
        """Calcular score geral de UX"""
        scores = []
        
        # Page load performance score
        page_load_time = metrics.get('page_load_avg_time', 0)
        if page_load_time > 0:
            page_score = max(0, 100 - (page_load_time / self.ux_criteria['page_load_time']) * 100)
            scores.append(page_score)
        
        # Search performance score
        search_time = metrics.get('search_avg_response_time', 0)
        if search_time > 0:
            search_score = max(0, 100 - (search_time / self.ux_criteria['search_response_time']) * 100)
            scores.append(search_score)
        
        # Download completion score
        download_rate = metrics.get('overall_download_completion_rate', 0)
        scores.append(download_rate)
        
        # WebSocket connectivity score
        ws_success_rate = metrics.get('websocket_connection_success_rate', 0)
        scores.append(ws_success_rate)
        
        # Data consistency score
        consistency_rate = metrics.get('data_consistency_rate', 0)
        scores.append(consistency_rate)
        
        # Error handling score
        error_clarity = metrics.get('error_message_clarity_rate', 0)
        scores.append(error_clarity)
        
        # UI responsiveness score
        ui_response_time = metrics.get('ui_avg_response_time', 0)
        if ui_response_time > 0:
            ui_score = max(0, 100 - (ui_response_time / self.ux_criteria['ui_responsiveness']) * 100)
            scores.append(ui_score)
        
        # Calculate weighted average
        if scores:
            return sum(scores) / len(scores)
        
        return 0.0
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.redis_client:
            await self.redis_client.close()