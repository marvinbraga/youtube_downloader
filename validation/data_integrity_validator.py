"""
Data Integrity Validator - Agent-QualityAssurance FASE 4
Validação de integridade de dados no sistema Redis puro
"""

import asyncio
import json
import random
from typing import Dict, List, Any, Optional, Set
from datetime import datetime
import logging
import redis.asyncio as redis
from pathlib import Path

class DataIntegrityValidator:
    """Validador de integridade de dados"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.redis_client = None
        
        # Criteria for data integrity validation
        self.validation_criteria = {
            'required_fields_present': 100.0,
            'correct_data_types': 100.0,
            'no_duplicates': 100.0,
            'referential_consistency': 100.0,
            'index_synchronization': 100.0
        }
        
        # Sample configuration
        self.sample_size = 5  # Random sample per cycle
        self.max_retries = 3
        
        # Data snapshots for comparison
        self.baseline_snapshots = {}
    
    async def initialize(self):
        """Inicializar conexões e recursos"""
        try:
            self.redis_client = redis.Redis(
                host='localhost',
                port=int(os.getenv('REDIS_PORT', 6379)),
                decode_responses=True
            )
            await self.redis_client.ping()
            
            # Create baseline snapshots
            await self._create_baseline_snapshots()
            
            self.logger.info("Data integrity validator initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize data integrity validator: {e}")
            raise
    
    async def validate(self) -> Dict[str, Any]:
        """Executar validação de integridade de dados"""
        if not self.redis_client:
            await self.initialize()
        
        self.logger.info("Starting data integrity validation...")
        
        validation_results = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': [],
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            # Run all validation checks
            checks = [
                self._validate_required_fields(),
                self._validate_data_types(),
                self._validate_no_duplicates(),
                self._validate_referential_consistency(),
                self._validate_index_synchronization(),
                self._validate_sample_data(),
                self._compare_with_snapshots()
            ]
            
            results = await asyncio.gather(*checks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    validation_results['issues'].append(f"Validation check {i+1} failed: {str(result)}")
                    validation_results['status'] = 'critical'
                else:
                    validation_results['metrics'].update(result['metrics'])
                    validation_results['issues'].extend(result['issues'])
                    validation_results['recommendations'].extend(result['recommendations'])
                    
                    if result['status'] == 'critical':
                        validation_results['status'] = 'critical'
                    elif result['status'] == 'warning' and validation_results['status'] == 'passed':
                        validation_results['status'] = 'warning'
            
            # Calculate overall integrity score
            validation_results['metrics']['overall_integrity_score'] = self._calculate_integrity_score(
                validation_results['metrics']
            )
            
            self.logger.info(f"Data integrity validation completed: {validation_results['status']}")
            
        except Exception as e:
            self.logger.error(f"Data integrity validation failed: {e}")
            validation_results['status'] = 'critical'
            validation_results['issues'].append(f"Validation failed: {str(e)}")
        
        return validation_results
    
    async def _validate_required_fields(self) -> Dict[str, Any]:
        """Validar campos obrigatórios"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Get sample of audio and video records
            audio_keys = await self.redis_client.keys('audio:*')
            video_keys = await self.redis_client.keys('video:*')
            
            # Required fields for audio records
            audio_required_fields = [
                'id', 'title', 'url', 'duration', 'status', 'download_date',
                'file_path', 'transcription_status'
            ]
            
            # Required fields for video records
            video_required_fields = [
                'id', 'title', 'url', 'duration', 'status', 'download_date',
                'file_path', 'quality', 'format'
            ]
            
            # Validate audio records
            audio_valid = 0
            audio_total = 0
            
            for key in random.sample(audio_keys, min(self.sample_size, len(audio_keys))):
                try:
                    audio_data = await self.redis_client.hgetall(key)
                    audio_total += 1
                    
                    if all(field in audio_data for field in audio_required_fields):
                        audio_valid += 1
                    else:
                        missing_fields = [f for f in audio_required_fields if f not in audio_data]
                        result['issues'].append(f"Audio {key} missing fields: {missing_fields}")
                        
                except Exception as e:
                    result['issues'].append(f"Failed to validate audio {key}: {str(e)}")
            
            # Validate video records
            video_valid = 0
            video_total = 0
            
            for key in random.sample(video_keys, min(self.sample_size, len(video_keys))):
                try:
                    video_data = await self.redis_client.hgetall(key)
                    video_total += 1
                    
                    if all(field in video_data for field in video_required_fields):
                        video_valid += 1
                    else:
                        missing_fields = [f for f in video_required_fields if f not in video_data]
                        result['issues'].append(f"Video {key} missing fields: {missing_fields}")
                        
                except Exception as e:
                    result['issues'].append(f"Failed to validate video {key}: {str(e)}")
            
            # Calculate success rates
            audio_success_rate = (audio_valid / audio_total * 100) if audio_total > 0 else 100
            video_success_rate = (video_valid / video_total * 100) if video_total > 0 else 100
            overall_success_rate = ((audio_valid + video_valid) / (audio_total + video_total) * 100) if (audio_total + video_total) > 0 else 100
            
            result['metrics'] = {
                'required_fields_audio_success_rate': audio_success_rate,
                'required_fields_video_success_rate': video_success_rate,
                'required_fields_overall_success_rate': overall_success_rate
            }
            
            # Determine status
            if overall_success_rate < 95:
                result['status'] = 'critical'
                result['recommendations'].append("Investigate and fix missing required fields")
            elif overall_success_rate < 100:
                result['status'] = 'warning'
                result['recommendations'].append("Monitor for missing required fields")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"Required fields validation failed: {str(e)}")
        
        return result
    
    async def _validate_data_types(self) -> Dict[str, Any]:
        """Validar tipos de dados"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Expected data types
            expected_types = {
                'audio': {
                    'duration': float,
                    'download_date': str,
                    'id': str,
                    'title': str,
                    'url': str,
                    'status': str
                },
                'video': {
                    'duration': float,
                    'download_date': str,
                    'id': str,
                    'title': str,
                    'url': str,
                    'status': str,
                    'quality': str,
                    'format': str
                }
            }
            
            type_errors = 0
            total_checks = 0
            
            # Check audio data types
            audio_keys = await self.redis_client.keys('audio:*')
            for key in random.sample(audio_keys, min(self.sample_size, len(audio_keys))):
                audio_data = await self.redis_client.hgetall(key)
                
                for field, expected_type in expected_types['audio'].items():
                    if field in audio_data:
                        total_checks += 1
                        try:
                            # Try to convert to expected type
                            if expected_type == float:
                                float(audio_data[field])
                            elif expected_type == int:
                                int(audio_data[field])
                            # str is always valid
                        except (ValueError, TypeError):
                            type_errors += 1
                            result['issues'].append(f"Audio {key} field {field} has incorrect type")
            
            # Check video data types
            video_keys = await self.redis_client.keys('video:*')
            for key in random.sample(video_keys, min(self.sample_size, len(video_keys))):
                video_data = await self.redis_client.hgetall(key)
                
                for field, expected_type in expected_types['video'].items():
                    if field in video_data:
                        total_checks += 1
                        try:
                            # Try to convert to expected type
                            if expected_type == float:
                                float(video_data[field])
                            elif expected_type == int:
                                int(video_data[field])
                            # str is always valid
                        except (ValueError, TypeError):
                            type_errors += 1
                            result['issues'].append(f"Video {key} field {field} has incorrect type")
            
            # Calculate success rate
            success_rate = ((total_checks - type_errors) / total_checks * 100) if total_checks > 0 else 100
            
            result['metrics'] = {
                'data_types_success_rate': success_rate,
                'total_type_checks': total_checks,
                'type_errors_found': type_errors
            }
            
            # Determine status
            if success_rate < 95:
                result['status'] = 'critical'
                result['recommendations'].append("Fix data type inconsistencies")
            elif success_rate < 100:
                result['status'] = 'warning'
                result['recommendations'].append("Monitor data type consistency")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"Data types validation failed: {str(e)}")
        
        return result
    
    async def _validate_no_duplicates(self) -> Dict[str, Any]:
        """Validar ausência de duplicatas"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            duplicates_found = 0
            
            # Check for duplicate URLs in audio
            audio_urls = set()
            audio_keys = await self.redis_client.keys('audio:*')
            
            for key in audio_keys:
                audio_data = await self.redis_client.hgetall(key)
                if 'url' in audio_data:
                    if audio_data['url'] in audio_urls:
                        duplicates_found += 1
                        result['issues'].append(f"Duplicate audio URL found: {audio_data['url']}")
                    else:
                        audio_urls.add(audio_data['url'])
            
            # Check for duplicate URLs in video
            video_urls = set()
            video_keys = await self.redis_client.keys('video:*')
            
            for key in video_keys:
                video_data = await self.redis_client.hgetall(key)
                if 'url' in video_data:
                    if video_data['url'] in video_urls:
                        duplicates_found += 1
                        result['issues'].append(f"Duplicate video URL found: {video_data['url']}")
                    else:
                        video_urls.add(video_data['url'])
            
            # Check for cross-reference duplicates (audio/video same URL)
            cross_duplicates = audio_urls.intersection(video_urls)
            if cross_duplicates:
                duplicates_found += len(cross_duplicates)
                result['issues'].extend([f"URL exists in both audio and video: {url}" for url in cross_duplicates])
            
            result['metrics'] = {
                'duplicates_found': duplicates_found,
                'unique_audio_urls': len(audio_urls),
                'unique_video_urls': len(video_urls),
                'cross_reference_duplicates': len(cross_duplicates)
            }
            
            # Determine status
            if duplicates_found > 0:
                result['status'] = 'warning'
                result['recommendations'].append("Remove duplicate entries to maintain data consistency")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"Duplicates validation failed: {str(e)}")
        
        return result
    
    async def _validate_referential_consistency(self) -> Dict[str, Any]:
        """Validar consistência referencial"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            consistency_errors = 0
            total_references = 0
            
            # Check if referenced files exist
            audio_keys = await self.redis_client.keys('audio:*')
            for key in random.sample(audio_keys, min(self.sample_size, len(audio_keys))):
                audio_data = await self.redis_client.hgetall(key)
                
                if 'file_path' in audio_data:
                    total_references += 1
                    file_path = Path(audio_data['file_path'])
                    if not file_path.exists():
                        consistency_errors += 1
                        result['issues'].append(f"Audio file not found: {audio_data['file_path']}")
                
                # Check transcription file if exists
                if 'transcription_path' in audio_data and audio_data['transcription_path']:
                    total_references += 1
                    trans_path = Path(audio_data['transcription_path'])
                    if not trans_path.exists():
                        consistency_errors += 1
                        result['issues'].append(f"Transcription file not found: {audio_data['transcription_path']}")
            
            video_keys = await self.redis_client.keys('video:*')
            for key in random.sample(video_keys, min(self.sample_size, len(video_keys))):
                video_data = await self.redis_client.hgetall(key)
                
                if 'file_path' in video_data:
                    total_references += 1
                    file_path = Path(video_data['file_path'])
                    if not file_path.exists():
                        consistency_errors += 1
                        result['issues'].append(f"Video file not found: {video_data['file_path']}")
            
            # Calculate success rate
            success_rate = ((total_references - consistency_errors) / total_references * 100) if total_references > 0 else 100
            
            result['metrics'] = {
                'referential_consistency_rate': success_rate,
                'total_references_checked': total_references,
                'consistency_errors': consistency_errors
            }
            
            # Determine status
            if success_rate < 95:
                result['status'] = 'critical'
                result['recommendations'].append("Fix broken file references")
            elif success_rate < 100:
                result['status'] = 'warning'
                result['recommendations'].append("Monitor for broken file references")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"Referential consistency validation failed: {str(e)}")
        
        return result
    
    async def _validate_index_synchronization(self) -> Dict[str, Any]:
        """Validar sincronização de índices"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            sync_errors = 0
            
            # Check audio indices
            audio_keys = set(await self.redis_client.keys('audio:*'))
            audio_index_keys = set(await self.redis_client.smembers('audio:index'))
            
            # Convert index keys to full keys
            full_audio_index_keys = {f"audio:{key}" for key in audio_index_keys}
            
            missing_in_index = audio_keys - full_audio_index_keys
            extra_in_index = full_audio_index_keys - audio_keys
            
            if missing_in_index:
                sync_errors += len(missing_in_index)
                result['issues'].extend([f"Audio key missing in index: {key}" for key in missing_in_index])
            
            if extra_in_index:
                sync_errors += len(extra_in_index)
                result['issues'].extend([f"Extra key in audio index: {key}" for key in extra_in_index])
            
            # Check video indices
            video_keys = set(await self.redis_client.keys('video:*'))
            video_index_keys = set(await self.redis_client.smembers('video:index'))
            
            # Convert index keys to full keys
            full_video_index_keys = {f"video:{key}" for key in video_index_keys}
            
            missing_in_video_index = video_keys - full_video_index_keys
            extra_in_video_index = full_video_index_keys - video_keys
            
            if missing_in_video_index:
                sync_errors += len(missing_in_video_index)
                result['issues'].extend([f"Video key missing in index: {key}" for key in missing_in_video_index])
            
            if extra_in_video_index:
                sync_errors += len(extra_in_video_index)
                result['issues'].extend([f"Extra key in video index: {key}" for key in extra_in_video_index])
            
            result['metrics'] = {
                'index_synchronization_errors': sync_errors,
                'audio_keys_count': len(audio_keys),
                'audio_index_keys_count': len(audio_index_keys),
                'video_keys_count': len(video_keys),
                'video_index_keys_count': len(video_index_keys)
            }
            
            # Determine status
            if sync_errors > 0:
                result['status'] = 'warning'
                result['recommendations'].append("Synchronize indices with actual data keys")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"Index synchronization validation failed: {str(e)}")
        
        return result
    
    async def _validate_sample_data(self) -> Dict[str, Any]:
        """Validar dados de amostra aleatória"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            sample_errors = 0
            sample_checks = 0
            
            # Get random samples
            all_keys = await self.redis_client.keys('*:*')
            data_keys = [k for k in all_keys if k.startswith(('audio:', 'video:')) and ':index' not in k]
            
            sample_keys = random.sample(data_keys, min(10, len(data_keys)))
            
            for key in sample_keys:
                try:
                    sample_checks += 1
                    data = await self.redis_client.hgetall(key)
                    
                    # Basic validation checks
                    if not data:
                        sample_errors += 1
                        result['issues'].append(f"Empty data for key: {key}")
                        continue
                    
                    # Check essential fields
                    essential_fields = ['id', 'title', 'url', 'status']
                    missing_essential = [f for f in essential_fields if f not in data or not data[f]]
                    
                    if missing_essential:
                        sample_errors += 1
                        result['issues'].append(f"Missing essential fields in {key}: {missing_essential}")
                    
                    # Validate URL format
                    if 'url' in data and not data['url'].startswith(('http://', 'https://')):
                        sample_errors += 1
                        result['issues'].append(f"Invalid URL format in {key}: {data['url']}")
                    
                except Exception as e:
                    sample_errors += 1
                    result['issues'].append(f"Failed to validate sample {key}: {str(e)}")
            
            success_rate = ((sample_checks - sample_errors) / sample_checks * 100) if sample_checks > 0 else 100
            
            result['metrics'] = {
                'sample_validation_success_rate': success_rate,
                'sample_checks_performed': sample_checks,
                'sample_errors_found': sample_errors
            }
            
            # Determine status
            if success_rate < 90:
                result['status'] = 'critical'
                result['recommendations'].append("Investigate and fix sample data issues")
            elif success_rate < 100:
                result['status'] = 'warning'
                result['recommendations'].append("Monitor sample data quality")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"Sample data validation failed: {str(e)}")
        
        return result
    
    async def _compare_with_snapshots(self) -> Dict[str, Any]:
        """Comparar com snapshots de baseline"""
        result = {
            'status': 'passed',
            'metrics': {},
            'issues': [],
            'recommendations': []
        }
        
        try:
            # Compare current state with baseline snapshots
            current_snapshot = await self._create_current_snapshot()
            
            # Compare key metrics
            for metric, baseline_value in self.baseline_snapshots.items():
                current_value = current_snapshot.get(metric, 0)
                
                # Allow for small variations (±5%)
                tolerance = 0.05
                if abs(current_value - baseline_value) / baseline_value > tolerance:
                    result['issues'].append(
                        f"Metric {metric} deviated from baseline: {current_value} vs {baseline_value}"
                    )
            
            result['metrics'] = {
                'snapshot_comparison': current_snapshot,
                'baseline_metrics': self.baseline_snapshots,
                'deviations_found': len(result['issues'])
            }
            
            # Determine status
            if len(result['issues']) > 3:
                result['status'] = 'warning'
                result['recommendations'].append("Investigate significant deviations from baseline")
            
        except Exception as e:
            result['status'] = 'critical'
            result['issues'].append(f"Snapshot comparison failed: {str(e)}")
        
        return result
    
    async def _create_baseline_snapshots(self):
        """Criar snapshots de baseline"""
        try:
            self.baseline_snapshots = await self._create_current_snapshot()
            self.logger.info("Baseline snapshots created")
        except Exception as e:
            self.logger.error(f"Failed to create baseline snapshots: {e}")
    
    async def _create_current_snapshot(self) -> Dict[str, Any]:
        """Criar snapshot do estado atual"""
        snapshot = {}
        
        # Count records
        audio_keys = await self.redis_client.keys('audio:*')
        video_keys = await self.redis_client.keys('video:*')
        
        snapshot['total_audio_records'] = len([k for k in audio_keys if ':index' not in k])
        snapshot['total_video_records'] = len([k for k in video_keys if ':index' not in k])
        snapshot['total_records'] = snapshot['total_audio_records'] + snapshot['total_video_records']
        
        # Memory usage
        info = await self.redis_client.info('memory')
        snapshot['redis_memory_usage'] = info.get('used_memory', 0)
        
        # Database size
        snapshot['database_size'] = await self.redis_client.dbsize()
        
        return snapshot
    
    def _calculate_integrity_score(self, metrics: Dict[str, Any]) -> float:
        """Calcular score geral de integridade"""
        scores = []
        
        # Extract relevant success rates
        for key, value in metrics.items():
            if 'success_rate' in key and isinstance(value, (int, float)):
                scores.append(value)
        
        # Calculate weighted average
        if scores:
            return sum(scores) / len(scores)
        
        return 0.0

    async def cleanup(self):
        """Cleanup resources"""
        if self.redis_client:
            await self.redis_client.close()