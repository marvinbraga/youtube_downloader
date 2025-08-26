"""
Testes de migração e integridade de dados
Validação completa da migração JSON -> Redis
"""

import asyncio
import json
import hashlib
import os
import tempfile
import shutil
from pathlib import Path
from typing import Dict, List, Any, Tuple
from datetime import datetime
import pytest
from unittest.mock import patch, MagicMock

from app.services.redis_audio_manager import RedisAudioManager
from app.services.redis_video_manager import RedisVideoManager
from app.models.video import VideoSource


class DataMigrationValidator:
    """Validador para migração de dados JSON -> Redis"""
    
    def __init__(self):
        self.validation_results = {
            'total_records': 0,
            'migrated_successfully': 0,
            'validation_errors': [],
            'data_integrity_checks': [],
            'performance_metrics': {}
        }
    
    def calculate_checksum(self, data: Any) -> str:
        """Calcula checksum MD5 para dados"""
        if isinstance(data, dict):
            # Ordenar chaves para checksum consistente
            sorted_data = json.dumps(data, sort_keys=True, ensure_ascii=False)
        else:
            sorted_data = str(data)
        
        return hashlib.md5(sorted_data.encode('utf-8')).hexdigest()
    
    def validate_field_mapping(self, json_data: Dict, redis_data: Dict, field_mappings: Dict[str, str]) -> List[str]:
        """Valida mapeamento de campos entre JSON e Redis"""
        errors = []
        
        for json_field, redis_field in field_mappings.items():
            json_value = json_data.get(json_field)
            redis_value = redis_data.get(redis_field)
            
            # Converter Redis string values para tipos apropriados
            if isinstance(redis_value, str) and json_value is not None:
                if isinstance(json_value, int):
                    try:
                        redis_value = int(redis_value)
                    except ValueError:
                        errors.append(f"Field {redis_field}: Cannot convert '{redis_value}' to int")
                        continue
                elif isinstance(json_value, float):
                    try:
                        redis_value = float(redis_value)
                    except ValueError:
                        errors.append(f"Field {redis_field}: Cannot convert '{redis_value}' to float")
                        continue
            
            if json_value != redis_value:
                errors.append(f"Field mismatch - JSON {json_field}: {json_value} != Redis {redis_field}: {redis_value}")
        
        return errors
    
    def validate_data_completeness(self, original_data: List[Dict], migrated_data: List[Dict]) -> Dict[str, Any]:
        """Valida completude dos dados migrados"""
        result = {
            'original_count': len(original_data),
            'migrated_count': len(migrated_data),
            'missing_records': [],
            'extra_records': [],
            'completeness_ratio': 0.0
        }
        
        # Criar sets de IDs para comparação
        original_ids = {item.get('id') for item in original_data if item.get('id')}
        migrated_ids = {item.get('id') for item in migrated_data if item.get('id')}
        
        # Encontrar registros faltando e extras
        result['missing_records'] = list(original_ids - migrated_ids)
        result['extra_records'] = list(migrated_ids - original_ids)
        result['completeness_ratio'] = len(migrated_ids & original_ids) / len(original_ids) if original_ids else 1.0
        
        return result
    
    def add_validation_result(self, test_name: str, passed: bool, details: Dict = None):
        """Adiciona resultado de validação"""
        self.validation_results['data_integrity_checks'].append({
            'test': test_name,
            'passed': passed,
            'details': details or {},
            'timestamp': datetime.now().isoformat()
        })
    
    def generate_report(self) -> str:
        """Gera relatório de migração"""
        results = self.validation_results
        
        report = "# Data Migration Validation Report\n\n"
        report += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        report += "## Migration Summary\n\n"
        report += f"- **Total Records**: {results['total_records']}\n"
        report += f"- **Successfully Migrated**: {results['migrated_successfully']}\n"
        report += f"- **Migration Success Rate**: {(results['migrated_successfully'] / results['total_records'] * 100) if results['total_records'] > 0 else 0:.2f}%\n"
        report += f"- **Validation Errors**: {len(results['validation_errors'])}\n\n"
        
        report += "## Data Integrity Checks\n\n"
        
        passed_checks = sum(1 for check in results['data_integrity_checks'] if check['passed'])
        total_checks = len(results['data_integrity_checks'])
        
        report += f"**Integrity Score**: {passed_checks}/{total_checks} ({(passed_checks/total_checks*100) if total_checks > 0 else 0:.1f}%)\n\n"
        
        for check in results['data_integrity_checks']:
            status = "✅" if check['passed'] else "❌"
            report += f"{status} **{check['test']}**\n"
            if check['details']:
                for key, value in check['details'].items():
                    report += f"  - {key}: {value}\n"
            report += "\n"
        
        if results['validation_errors']:
            report += "## Validation Errors\n\n"
            for i, error in enumerate(results['validation_errors'][:10], 1):  # Mostrar primeiros 10
                report += f"{i}. {error}\n"
            
            if len(results['validation_errors']) > 10:
                report += f"... and {len(results['validation_errors']) - 10} more errors\n"
            report += "\n"
        
        report += "## Performance Metrics\n\n"
        for metric, value in results['performance_metrics'].items():
            report += f"- **{metric}**: {value}\n"
        
        return report


@pytest.mark.migration
@pytest.mark.asyncio
class TestDataMigrationIntegrity:
    """Testes de migração e integridade de dados"""
    
    async def test_audio_json_to_redis_migration(self, redis_audio_manager, temp_json_files):
        """Teste completo de migração de áudios JSON -> Redis"""
        validator = DataMigrationValidator()
        
        print("Starting audio JSON -> Redis migration test...")
        
        try:
            # 1. PREPARAR DADOS JSON
            json_audio_data = temp_json_files['audio_data']
            validator.validation_results['total_records'] = len(json_audio_data)
            
            print(f"Migrating {len(json_audio_data)} audio records...")
            
            # 2. EXECUTAR MIGRAÇÃO
            migration_start = datetime.now()
            migrated_ids = []
            migration_errors = []
            
            for audio_data in json_audio_data:
                try:
                    # Enriquecer dados JSON com campos necessários para Redis
                    enriched_data = audio_data.copy()
                    enriched_data.update({
                        'keywords': [audio_data.get('title', '').lower().split()[0]] if audio_data.get('title') else [],
                        'transcription_status': 'none',
                        'format': audio_data.get('format', 'mp3'),
                        'created_date': audio_data.get('created_date', datetime.now().isoformat()),
                        'modified_date': audio_data.get('modified_date', datetime.now().isoformat()),
                        'filesize': audio_data.get('file_size', 0)  # Mapear field
                    })
                    
                    # Migrar para Redis
                    migrated_id = await redis_audio_manager.create_audio(enriched_data)
                    migrated_ids.append(migrated_id)
                    validator.validation_results['migrated_successfully'] += 1
                    
                except Exception as e:
                    migration_errors.append(f"Error migrating {audio_data.get('id', 'unknown')}: {str(e)}")
                    validator.validation_results['validation_errors'].append(str(e))
            
            migration_time = (datetime.now() - migration_start).total_seconds()
            validator.validation_results['performance_metrics']['migration_time_seconds'] = migration_time
            
            print(f"Migration completed in {migration_time:.2f}s")
            print(f"Successfully migrated: {len(migrated_ids)}/{len(json_audio_data)}")
            
            # 3. VALIDAÇÃO DE INTEGRIDADE
            print("Validating data integrity...")
            
            # Obter todos os dados migrados
            migrated_data = []
            for audio_id in migrated_ids:
                redis_data = await redis_audio_manager.get_audio(audio_id)
                if redis_data:
                    migrated_data.append(redis_data)
            
            # Validação de completude
            completeness = validator.validate_data_completeness(json_audio_data, migrated_data)
            validator.add_validation_result(
                "Data Completeness",
                completeness['completeness_ratio'] >= 0.95,
                completeness
            )
            
            # Validação campo a campo
            field_mappings = {
                'id': 'id',
                'title': 'title',
                'url': 'url',
                'duration': 'duration'
            }
            
            field_validation_errors = 0
            for i, json_record in enumerate(json_audio_data):
                if i < len(migrated_data):
                    redis_record = migrated_data[i]
                    field_errors = validator.validate_field_mapping(json_record, redis_record, field_mappings)
                    if field_errors:
                        field_validation_errors += len(field_errors)
                        validator.validation_results['validation_errors'].extend(field_errors)
            
            validator.add_validation_result(
                "Field Mapping Accuracy",
                field_validation_errors == 0,
                {'field_errors': field_validation_errors}
            )
            
            # Validação de funcionalidade
            print("Testing post-migration functionality...")
            
            # Teste de busca
            search_results = await redis_audio_manager.search_by_keyword('audio')
            validator.add_validation_result(
                "Search Functionality",
                len(search_results) > 0,
                {'search_results_count': len(search_results)}
            )
            
            # Teste de listagem
            all_audios = await redis_audio_manager.get_all_audios()
            validator.add_validation_result(
                "List All Functionality",
                len(all_audios) >= len(migrated_ids),
                {'listed_count': len(all_audios), 'expected_min': len(migrated_ids)}
            )
            
            # Teste de estatísticas
            stats = await redis_audio_manager.get_statistics()
            validator.add_validation_result(
                "Statistics Functionality",
                stats.get('total_count', 0) >= len(migrated_ids),
                {'stats_count': stats.get('total_count', 0)}
            )
            
            # 4. VALIDAÇÃO DE PERFORMANCE PÓS-MIGRAÇÃO
            print("Testing post-migration performance...")
            
            # Benchmark operações básicas
            import time
            
            # Read performance
            read_start = time.time()
            sample_ids = migrated_ids[:min(10, len(migrated_ids))]
            read_tasks = [redis_audio_manager.get_audio(audio_id) for audio_id in sample_ids]
            await asyncio.gather(*read_tasks)
            read_time = time.time() - read_start
            
            validator.validation_results['performance_metrics']['avg_read_time_ms'] = (read_time * 1000) / len(sample_ids)
            
            # Search performance
            search_start = time.time()
            await redis_audio_manager.search_by_keyword('test')
            search_time = (time.time() - search_start) * 1000
            
            validator.validation_results['performance_metrics']['search_time_ms'] = search_time
            
            # Performance validation
            validator.add_validation_result(
                "Read Performance",
                validator.validation_results['performance_metrics']['avg_read_time_ms'] < 50,
                {'avg_read_time_ms': validator.validation_results['performance_metrics']['avg_read_time_ms']}
            )
            
            validator.add_validation_result(
                "Search Performance",
                search_time < 100,
                {'search_time_ms': search_time}
            )
            
            # 5. CLEANUP (opcional para alguns testes)
            print("Cleaning up migrated data...")
            cleanup_tasks = [redis_audio_manager.delete_audio(audio_id) for audio_id in migrated_ids]
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            
            # RESULTADOS FINAIS
            report = validator.generate_report()
            print("\n" + "="*60)
            print(report)
            
            # Assertions
            assert validator.validation_results['migrated_successfully'] == len(json_audio_data), "Not all records migrated successfully"
            assert completeness['completeness_ratio'] >= 0.95, f"Data completeness too low: {completeness['completeness_ratio']:.2%}"
            assert field_validation_errors == 0, f"Field mapping errors: {field_validation_errors}"
            assert len(search_results) > 0, "Search functionality failed"
            assert len(all_audios) >= len(migrated_ids), "List functionality failed"
            
            print("✅ Audio JSON -> Redis migration test passed!")
            
        except Exception as e:
            print(f"❌ Audio migration test failed: {str(e)}")
            raise
    
    async def test_video_json_to_redis_migration(self, redis_video_manager, temp_json_files):
        """Teste completo de migração de vídeos JSON -> Redis"""
        validator = DataMigrationValidator()
        
        print("Starting video JSON -> Redis migration test...")
        
        try:
            # 1. PREPARAR DADOS JSON
            json_video_data = temp_json_files['video_data']
            validator.validation_results['total_records'] = len(json_video_data)
            
            print(f"Migrating {len(json_video_data)} video records...")
            
            # 2. EXECUTAR MIGRAÇÃO
            migration_start = datetime.now()
            migrated_ids = []
            
            for video_data in json_video_data:
                try:
                    # Enriquecer dados JSON com campos necessários
                    enriched_data = video_data.copy()
                    enriched_data.update({
                        'name': video_data.get('title', video_data.get('name', 'Unknown')),
                        'source': VideoSource.LOCAL,
                        'type': 'mp4',
                        'created_date': video_data.get('created_date', datetime.now().isoformat()),
                        'modified_date': video_data.get('modified_date', datetime.now().isoformat()),
                        'size': video_data.get('file_size', 0)
                    })
                    
                    # Migrar para Redis
                    migrated_id = await redis_video_manager.create_video(enriched_data)
                    migrated_ids.append(migrated_id)
                    validator.validation_results['migrated_successfully'] += 1
                    
                except Exception as e:
                    validator.validation_results['validation_errors'].append(str(e))
            
            migration_time = (datetime.now() - migration_start).total_seconds()
            validator.validation_results['performance_metrics']['migration_time_seconds'] = migration_time
            
            # 3. VALIDAÇÃO DE INTEGRIDADE
            migrated_data = []
            for video_id in migrated_ids:
                redis_data = await redis_video_manager.get_video(video_id)
                if redis_data:
                    migrated_data.append(redis_data)
            
            # Validação de completude
            completeness = validator.validate_data_completeness(json_video_data, migrated_data)
            validator.add_validation_result(
                "Video Data Completeness",
                completeness['completeness_ratio'] >= 0.95,
                completeness
            )
            
            # Teste funcionalidades específicas de vídeo
            local_videos = await redis_video_manager.get_videos_by_source(VideoSource.LOCAL)
            validator.add_validation_result(
                "Source Filtering",
                len(local_videos) >= len(migrated_ids),
                {'local_videos_count': len(local_videos)}
            )
            
            # Cleanup
            cleanup_tasks = [redis_video_manager.delete_video(video_id) for video_id in migrated_ids]
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            
            # Assertions
            assert validator.validation_results['migrated_successfully'] == len(json_video_data)
            assert completeness['completeness_ratio'] >= 0.95
            
            print("✅ Video JSON -> Redis migration test passed!")
            
        except Exception as e:
            print(f"❌ Video migration test failed: {str(e)}")
            raise
    
    async def test_data_integrity_during_concurrent_migration(self, redis_audio_manager, performance_data_generator):
        """Teste de integridade durante migração concorrente"""
        validator = DataMigrationValidator()
        
        print("Starting concurrent migration integrity test...")
        
        try:
            # Gerar dataset grande para migração concorrente
            large_dataset = performance_data_generator['audio_batch'](500)
            validator.validation_results['total_records'] = len(large_dataset)
            
            # Preparar dados para Redis
            redis_ready_data = []
            for audio_data in large_dataset:
                enriched_data = audio_data.copy()
                enriched_data.update({
                    'keywords': [audio_data.get('title', '').lower().split()[0]] if audio_data.get('title') else [],
                    'transcription_status': 'none',
                    'format': 'mp3',
                    'created_date': datetime.now().isoformat(),
                    'modified_date': datetime.now().isoformat()
                })
                redis_ready_data.append(enriched_data)
            
            # Executar migração concorrente
            migration_start = datetime.now()
            
            # Dividir em batches para simular migração real
            batch_size = 50
            all_results = []
            
            for i in range(0, len(redis_ready_data), batch_size):
                batch = redis_ready_data[i:i + batch_size]
                batch_tasks = [redis_audio_manager.create_audio(audio) for audio in batch]
                batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                all_results.extend(batch_results)
            
            migration_time = (datetime.now() - migration_start).total_seconds()
            
            # Análise dos resultados
            successful_migrations = []
            failed_migrations = []
            
            for i, result in enumerate(all_results):
                if isinstance(result, Exception):
                    failed_migrations.append((i, str(result)))
                else:
                    successful_migrations.append(result)
                    validator.validation_results['migrated_successfully'] += 1
            
            # Validação de integridade
            print(f"Concurrent migration: {len(successful_migrations)}/{len(large_dataset)} successful")
            
            # Verificar integridade dos dados migrados
            integrity_checks = []
            
            for audio_id in successful_migrations[:50]:  # Amostra para verificação
                try:
                    retrieved_data = await redis_audio_manager.get_audio(audio_id)
                    if retrieved_data:
                        integrity_checks.append(True)
                    else:
                        integrity_checks.append(False)
                except:
                    integrity_checks.append(False)
            
            integrity_ratio = sum(integrity_checks) / len(integrity_checks) if integrity_checks else 0
            
            validator.add_validation_result(
                "Concurrent Migration Integrity",
                integrity_ratio >= 0.98,
                {
                    'successful_migrations': len(successful_migrations),
                    'failed_migrations': len(failed_migrations),
                    'integrity_ratio': integrity_ratio,
                    'migration_time': migration_time
                }
            )
            
            # Performance durante concorrência
            validator.validation_results['performance_metrics'].update({
                'concurrent_migration_time': migration_time,
                'concurrent_throughput': len(successful_migrations) / migration_time,
                'concurrent_success_rate': len(successful_migrations) / len(large_dataset)
            })
            
            # Cleanup
            cleanup_tasks = [redis_audio_manager.delete_audio(audio_id) for audio_id in successful_migrations]
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            
            # Assertions
            assert len(successful_migrations) / len(large_dataset) >= 0.95, "Concurrent migration success rate too low"
            assert integrity_ratio >= 0.98, "Data integrity compromised during concurrent migration"
            
            print("✅ Concurrent migration integrity test passed!")
            
        except Exception as e:
            print(f"❌ Concurrent migration test failed: {str(e)}")
            raise
    
    async def test_data_consistency_validation(self, redis_audio_manager):
        """Teste de consistência de dados após operações"""
        validator = DataMigrationValidator()
        
        print("Starting data consistency validation test...")
        
        try:
            # 1. CRIAR DADOS DE TESTE
            test_data = [
                {
                    "id": f"consistency_test_{i}",
                    "title": f"Consistency Test Audio {i}",
                    "url": f"https://test.com/audio_{i}",
                    "duration": 120 + i,
                    "keywords": ["consistency", "test", f"audio_{i}"],
                    "transcription_status": "none",
                    "format": "mp3",
                    "created_date": datetime.now().isoformat(),
                    "modified_date": datetime.now().isoformat(),
                    "filesize": 1048576 + i * 1024
                }
                for i in range(100)
            ]
            
            # Criar todos os registros
            creation_tasks = [redis_audio_manager.create_audio(audio) for audio in test_data]
            created_ids = await asyncio.gather(*creation_tasks)
            
            # 2. OPERAÇÕES MISTAS PARA TESTAR CONSISTÊNCIA
            print("Performing mixed operations...")
            
            mixed_operations = []
            
            # Operações de leitura
            for audio_id in created_ids[:30]:
                mixed_operations.append(('read', redis_audio_manager.get_audio(audio_id)))
            
            # Operações de atualização
            for i, audio_id in enumerate(created_ids[30:60]):
                updates = {"title": f"Updated Audio {i}", "duration": 180 + i}
                mixed_operations.append(('update', redis_audio_manager.update_audio(audio_id, updates)))
            
            # Operações de busca
            for term in ["consistency", "test", "audio"]:
                mixed_operations.append(('search', redis_audio_manager.search_by_keyword(term)))
            
            # Executar todas as operações
            operation_results = await asyncio.gather(*[op[1] for op in mixed_operations], return_exceptions=True)
            
            # 3. VALIDAÇÃO DE CONSISTÊNCIA
            print("Validating data consistency...")
            
            # Verificar que todas as operações foram bem-sucedidas
            successful_ops = sum(1 for result in operation_results if not isinstance(result, Exception))
            total_ops = len(operation_results)
            
            validator.add_validation_result(
                "Mixed Operations Success Rate",
                successful_ops / total_ops >= 0.98,
                {'successful_ops': successful_ops, 'total_ops': total_ops}
            )
            
            # Verificar consistência de dados após updates
            updated_ids = created_ids[30:60]
            consistency_checks = []
            
            for i, audio_id in enumerate(updated_ids):
                retrieved_data = await redis_audio_manager.get_audio(audio_id)
                if retrieved_data:
                    expected_title = f"Updated Audio {i}"
                    actual_title = retrieved_data.get('title', '')
                    consistency_checks.append(expected_title == actual_title)
            
            consistency_ratio = sum(consistency_checks) / len(consistency_checks) if consistency_checks else 0
            
            validator.add_validation_result(
                "Update Consistency",
                consistency_ratio >= 0.98,
                {'consistency_ratio': consistency_ratio}
            )
            
            # Verificar integridade dos índices
            search_results = await redis_audio_manager.search_by_keyword("consistency")
            expected_search_count = len([audio for audio in test_data if "consistency" in audio.get("keywords", [])])
            
            validator.add_validation_result(
                "Index Integrity",
                len(search_results) >= expected_search_count * 0.95,  # 95% tolerance
                {
                    'found_results': len(search_results),
                    'expected_results': expected_search_count
                }
            )
            
            # 4. VERIFICAÇÃO DE ATOMICIDADE
            print("Testing operation atomicity...")
            
            # Tentar operação que deve falhar para testar rollback
            try:
                # Tentar criar registro com ID duplicado
                duplicate_data = test_data[0].copy()
                await redis_audio_manager.create_audio(duplicate_data)
                atomicity_test = False  # Se chegou aqui, não detectou duplicata
            except:
                atomicity_test = True  # Esperado - deve rejeitar duplicata
            
            validator.add_validation_result(
                "Operation Atomicity",
                atomicity_test,
                {'duplicate_prevention': atomicity_test}
            )
            
            # 5. CLEANUP E VERIFICAÇÃO DE LIMPEZA
            print("Testing cleanup integrity...")
            
            # Deletar todos os registros
            deletion_tasks = [redis_audio_manager.delete_audio(audio_id) for audio_id in created_ids]
            deletion_results = await asyncio.gather(*deletion_tasks, return_exceptions=True)
            
            successful_deletions = sum(1 for result in deletion_results if result is True)
            
            # Verificar que registros foram realmente removidos
            verification_tasks = [redis_audio_manager.get_audio(audio_id) for audio_id in created_ids]
            verification_results = await asyncio.gather(*verification_tasks)
            
            actually_deleted = sum(1 for result in verification_results if result is None)
            
            validator.add_validation_result(
                "Cleanup Integrity",
                actually_deleted == successful_deletions,
                {
                    'successful_deletions': successful_deletions,
                    'verified_deletions': actually_deleted
                }
            )
            
            # Gerar relatório
            report = validator.generate_report()
            print("\n" + "="*60)
            print(report)
            
            # Assertions finais
            assert successful_ops / total_ops >= 0.98, "Mixed operations success rate too low"
            assert consistency_ratio >= 0.98, "Data consistency compromised"
            assert atomicity_test, "Atomicity test failed"
            assert actually_deleted == successful_deletions, "Cleanup integrity failed"
            
            print("✅ Data consistency validation test passed!")
            
        except Exception as e:
            print(f"❌ Data consistency test failed: {str(e)}")
            raise
    
    async def test_incremental_migration_integrity(self, redis_audio_manager, performance_data_generator):
        """Teste de integridade em migração incremental"""
        validator = DataMigrationValidator()
        
        print("Starting incremental migration integrity test...")
        
        try:
            # Simular migração incremental
            base_dataset = performance_data_generator['audio_batch'](100)
            incremental_dataset = performance_data_generator['audio_batch'](50)
            
            # Primeira migração (base)
            print("Phase 1: Base migration...")
            
            base_migration_tasks = []
            for audio_data in base_dataset:
                enriched_data = audio_data.copy()
                enriched_data.update({
                    'keywords': ['base', 'migration'],
                    'transcription_status': 'none',
                    'format': 'mp3',
                    'created_date': datetime.now().isoformat(),
                    'modified_date': datetime.now().isoformat()
                })
                base_migration_tasks.append(redis_audio_manager.create_audio(enriched_data))
            
            base_results = await asyncio.gather(*base_migration_tasks, return_exceptions=True)
            base_successful = [r for r in base_results if not isinstance(r, Exception)]
            
            # Verificar estado após primeira migração
            base_count = len(await redis_audio_manager.get_all_audios())
            
            # Segunda migração (incremental)
            print("Phase 2: Incremental migration...")
            
            incremental_tasks = []
            for audio_data in incremental_dataset:
                enriched_data = audio_data.copy()
                enriched_data.update({
                    'keywords': ['incremental', 'migration'],
                    'transcription_status': 'none',
                    'format': 'mp3',
                    'created_date': datetime.now().isoformat(),
                    'modified_date': datetime.now().isoformat()
                })
                incremental_tasks.append(redis_audio_manager.create_audio(enriched_data))
            
            incremental_results = await asyncio.gather(*incremental_tasks, return_exceptions=True)
            incremental_successful = [r for r in incremental_results if not isinstance(r, Exception)]
            
            # Verificar estado final
            final_count = len(await redis_audio_manager.get_all_audios())
            expected_count = len(base_successful) + len(incremental_successful)
            
            # Validação da migração incremental
            validator.add_validation_result(
                "Incremental Migration Integrity",
                final_count == expected_count,
                {
                    'base_count': len(base_successful),
                    'incremental_count': len(incremental_successful),
                    'final_count': final_count,
                    'expected_count': expected_count
                }
            )
            
            # Verificar que ambos os tipos de dados estão presentes
            base_search = await redis_audio_manager.search_by_keyword('base')
            incremental_search = await redis_audio_manager.search_by_keyword('incremental')
            
            validator.add_validation_result(
                "Incremental Data Coexistence",
                len(base_search) > 0 and len(incremental_search) > 0,
                {
                    'base_search_results': len(base_search),
                    'incremental_search_results': len(incremental_search)
                }
            )
            
            # Cleanup
            all_successful = base_successful + incremental_successful
            cleanup_tasks = [redis_audio_manager.delete_audio(audio_id) for audio_id in all_successful]
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            
            # Assertions
            assert final_count == expected_count, f"Incremental migration count mismatch: {final_count} != {expected_count}"
            assert len(base_search) > 0 and len(incremental_search) > 0, "Incremental data coexistence failed"
            
            print("✅ Incremental migration integrity test passed!")
            
        except Exception as e:
            print(f"❌ Incremental migration test failed: {str(e)}")
            raise


@pytest.mark.migration
@pytest.mark.asyncio
class TestDataBackupAndRestore:
    """Testes de backup e restauração de dados"""
    
    async def test_data_backup_integrity(self, redis_audio_manager, performance_data_generator):
        """Teste de integridade de backup de dados"""
        print("Starting data backup integrity test...")
        
        try:
            # Criar dados originais
            original_data = performance_data_generator['audio_batch'](50)
            
            # Enriquecer e criar no Redis
            enriched_data = []
            for audio_data in original_data:
                enriched = audio_data.copy()
                enriched.update({
                    'keywords': ['backup', 'test'],
                    'transcription_status': 'none',
                    'format': 'mp3',
                    'created_date': datetime.now().isoformat(),
                    'modified_date': datetime.now().isoformat()
                })
                enriched_data.append(enriched)
            
            # Criar registros
            creation_tasks = [redis_audio_manager.create_audio(audio) for audio in enriched_data]
            created_ids = await asyncio.gather(*creation_tasks)
            
            # "Backup" dos dados (simulação)
            backup_data = []
            for audio_id in created_ids:
                audio_data = await redis_audio_manager.get_audio(audio_id)
                if audio_data:
                    backup_data.append(audio_data)
            
            # Simular perda de dados (delete)
            print("Simulating data loss...")
            deletion_tasks = [redis_audio_manager.delete_audio(audio_id) for audio_id in created_ids]
            await asyncio.gather(*deletion_tasks)
            
            # Verificar que dados foram perdidos
            verification_tasks = [redis_audio_manager.get_audio(audio_id) for audio_id in created_ids]
            verification_results = await asyncio.gather(*verification_tasks)
            lost_count = sum(1 for result in verification_results if result is None)
            
            assert lost_count == len(created_ids), "Data loss simulation failed"
            
            # "Restaurar" dados do backup
            print("Restoring from backup...")
            restore_tasks = [redis_audio_manager.create_audio(backup_audio) for backup_audio in backup_data]
            restored_ids = await asyncio.gather(*restore_tasks, return_exceptions=True)
            
            successful_restores = [r for r in restored_ids if not isinstance(r, Exception)]
            
            # Verificar integridade da restauração
            integrity_checks = []
            for i, restored_id in enumerate(successful_restores):
                if i < len(backup_data):
                    original_backup = backup_data[i]
                    restored_data = await redis_audio_manager.get_audio(restored_id)
                    
                    if restored_data:
                        # Comparar campos chave
                        title_match = original_backup.get('title') == restored_data.get('title')
                        url_match = original_backup.get('url') == restored_data.get('url')
                        duration_match = str(original_backup.get('duration')) == str(restored_data.get('duration'))
                        
                        integrity_checks.append(title_match and url_match and duration_match)
            
            integrity_ratio = sum(integrity_checks) / len(integrity_checks) if integrity_checks else 0
            
            # Cleanup
            final_cleanup = [redis_audio_manager.delete_audio(r_id) for r_id in successful_restores]
            await asyncio.gather(*final_cleanup, return_exceptions=True)
            
            # Assertions
            assert len(successful_restores) == len(backup_data), f"Restore count mismatch: {len(successful_restores)} != {len(backup_data)}"
            assert integrity_ratio >= 0.98, f"Restore integrity too low: {integrity_ratio:.2%}"
            
            print("✅ Data backup integrity test passed!")
            
        except Exception as e:
            print(f"❌ Data backup test failed: {str(e)}")
            raise


if __name__ == "__main__":
    """Execução standalone para testes de migração"""
    async def run_migration_tests():
        print("Starting Data Migration & Integrity Tests...")
        print("=" * 60)
        
        print("These tests validate:")
        print("- JSON to Redis migration accuracy")
        print("- Data integrity during migration")
        print("- Concurrent migration stability")
        print("- Data consistency after operations")
        print("- Backup and restore functionality")
        print()
        
        print("Expected validation criteria:")
        print("- 100% data migration success rate")
        print("- >98% data integrity after migration")
        print("- >95% consistency under concurrent operations")
        print("- Full backup/restore capability")
    
    asyncio.run(run_migration_tests())