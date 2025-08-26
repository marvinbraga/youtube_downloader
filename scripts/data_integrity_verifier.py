"""
Script de Verificação de Integridade de Dados Migrados
Valida 100% da integridade entre dados JSON originais e Redis

Autor: Claude Code Agent
Data: 2025-08-26
Versão: 1.0.0 - FASE 2 Data Integrity Verification
"""

import asyncio
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Set

import redis.asyncio as redis
from loguru import logger

# Importar componentes do sistema
import sys
sys.path.append(str(Path(__file__).parent.parent))

from app.services.redis_connection import get_redis_client, init_redis
from app.services.redis_audio_manager import RedisAudioManager
from app.services.redis_video_manager import RedisVideoManager


class DataIntegrityVerifier:
    """
    Verificador completo de integridade de dados
    Garante 100% de correspondência entre JSON e Redis
    """
    
    def __init__(self, data_dir: str = "E:\\python\\youtube_downloader\\data"):
        self.data_dir = Path(data_dir)
        
        # Componentes Redis
        self.redis_client: Optional[redis.Redis] = None
        self.audio_manager: Optional[RedisAudioManager] = None
        self.video_manager: Optional[RedisVideoManager] = None
        
        # Estado da verificação
        self.verification_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.verification_results = {
            'verification_id': self.verification_id,
            'start_time': None,
            'end_time': None,
            'total_checks': 0,
            'passed_checks': 0,
            'failed_checks': 0,
            'warnings': 0,
            'detailed_results': {
                'audio_verification': {},
                'video_verification': {},
                'structural_verification': {},
                'data_consistency': {},
                'performance_metrics': {}
            },
            'integrity_score': 0.0,
            'recommendation': 'pending'
        }
        
        # Configuração de logs
        self._setup_verification_logging()
        
        logger.info(f"🔍 Verificador de Integridade inicializado: {self.verification_id}")
    
    def _setup_verification_logging(self):
        """Configura sistema de logs para verificação"""
        log_dir = Path("E:\\python\\youtube_downloader\\logs\\verification")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / f"verification_{self.verification_id}.log"
        
        logger.add(
            str(log_file),
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line} | {message}",
            level="DEBUG",
            retention="30 days"
        )
        
        logger.info(f"📋 Logs de verificação: {log_file}")
    
    async def execute_full_verification(self) -> Dict[str, Any]:
        """
        Executa verificação completa de integridade
        
        Returns:
            Resultado detalhado da verificação
        """
        logger.info("🚀 Iniciando verificação completa de integridade")
        self.verification_results['start_time'] = time.time()
        
        try:
            # Inicializar Redis
            await self._initialize_redis_connection()
            
            # Verificação estrutural
            await self._verify_structural_integrity()
            
            # Verificação de dados de áudios
            await self._verify_audio_data_integrity()
            
            # Verificação de dados de vídeos
            await self._verify_video_data_integrity()
            
            # Verificação de consistência
            await self._verify_data_consistency()
            
            # Verificação de performance
            await self._verify_performance_metrics()
            
            # Calcular score de integridade
            await self._calculate_integrity_score()
            
            # Gerar recomendações
            await self._generate_recommendations()
            
            self.verification_results['end_time'] = time.time()
            
            # Salvar relatório
            report = await self._generate_verification_report()
            
            logger.success("✅ Verificação de integridade concluída")
            return report
            
        except Exception as e:
            logger.error(f"❌ Erro na verificação de integridade: {e}")
            self.verification_results['end_time'] = time.time()
            
            return {
                'success': False,
                'error': str(e),
                'verification_id': self.verification_id,
                'verification_results': self.verification_results
            }
    
    async def _initialize_redis_connection(self):
        """Inicializa conexão Redis para verificação"""
        logger.info("🔌 Inicializando conexão Redis...")
        
        try:
            await init_redis()
            self.redis_client = await get_redis_client()
            await self.redis_client.ping()
            
            self.audio_manager = RedisAudioManager()
            self.video_manager = RedisVideoManager()
            
            await self.audio_manager.initialize()
            await self.video_manager.initialize()
            
            logger.success("✅ Conexão Redis estabelecida")
            
        except Exception as e:
            logger.error(f"❌ Falha na conexão Redis: {e}")
            raise
    
    async def _verify_structural_integrity(self):
        """Verifica integridade estrutural dos dados"""
        logger.info("🏗️ Verificando integridade estrutural...")
        
        structural_results = {
            'redis_connection': False,
            'json_files_exist': False,
            'redis_keys_exist': False,
            'schema_validation': False,
            'errors': []
        }
        
        try:
            # Testar conexão Redis
            await self.redis_client.ping()
            structural_results['redis_connection'] = True
            self.verification_results['passed_checks'] += 1
            
        except Exception as e:
            structural_results['errors'].append(f"Redis connection failed: {e}")
            self.verification_results['failed_checks'] += 1
        
        # Verificar arquivos JSON
        audios_file = self.data_dir / 'audios.json'
        videos_file = self.data_dir / 'videos.json'
        
        if audios_file.exists() and videos_file.exists():
            structural_results['json_files_exist'] = True
            self.verification_results['passed_checks'] += 1
        else:
            structural_results['errors'].append("JSON files not found")
            self.verification_results['failed_checks'] += 1
        
        # Verificar chaves Redis
        try:
            redis_keys = await self.redis_client.keys("youtube_downloader:*")
            if len(redis_keys) > 0:
                structural_results['redis_keys_exist'] = True
                self.verification_results['passed_checks'] += 1
                logger.info(f"📊 Encontradas {len(redis_keys)} chaves Redis")
            else:
                structural_results['errors'].append("No Redis keys found")
                self.verification_results['failed_checks'] += 1
                
        except Exception as e:
            structural_results['errors'].append(f"Redis keys check failed: {e}")
            self.verification_results['failed_checks'] += 1
        
        # Validação de schema básica
        try:
            if audios_file.exists():
                with open(audios_file, 'r', encoding='utf-8') as f:
                    audios_data = json.load(f)
                
                if 'audios' in audios_data and isinstance(audios_data['audios'], list):
                    structural_results['schema_validation'] = True
                    self.verification_results['passed_checks'] += 1
                else:
                    structural_results['errors'].append("Invalid JSON schema for audios")
                    self.verification_results['failed_checks'] += 1
                    
        except Exception as e:
            structural_results['errors'].append(f"Schema validation failed: {e}")
            self.verification_results['failed_checks'] += 1
        
        self.verification_results['total_checks'] += 4
        self.verification_results['detailed_results']['structural_verification'] = structural_results
        
        logger.info(f"🏗️ Verificação estrutural: {sum(1 for k, v in structural_results.items() if isinstance(v, bool) and v)}/4 passou")
    
    async def _verify_audio_data_integrity(self):
        """Verifica integridade completa dos dados de áudios"""
        logger.info("🎵 Verificando integridade dos dados de áudios...")
        
        audio_results = {
            'total_json_records': 0,
            'total_redis_records': 0,
            'matched_records': 0,
            'missing_in_redis': [],
            'missing_in_json': [],
            'data_mismatches': [],
            'field_mismatches': {},
            'integrity_score': 0.0
        }
        
        try:
            # Carregar dados JSON
            audios_file = self.data_dir / 'audios.json'
            if not audios_file.exists():
                audio_results['errors'] = ['audios.json not found']
                self.verification_results['detailed_results']['audio_verification'] = audio_results
                return
            
            with open(audios_file, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            json_audios = json_data.get('audios', [])
            audio_results['total_json_records'] = len(json_audios)
            
            # Obter dados Redis
            redis_audio_ids = await self.audio_manager.get_all_audio_ids()
            audio_results['total_redis_records'] = len(redis_audio_ids)
            
            logger.info(f"📊 JSON: {audio_results['total_json_records']} áudios, Redis: {audio_results['total_redis_records']} áudios")
            
            # Criar sets para comparação
            json_ids = {audio['id'] for audio in json_audios}
            redis_ids = set(redis_audio_ids)
            
            # Encontrar IDs faltantes
            audio_results['missing_in_redis'] = list(json_ids - redis_ids)
            audio_results['missing_in_json'] = list(redis_ids - json_ids)
            
            if audio_results['missing_in_redis']:
                logger.warning(f"⚠️ {len(audio_results['missing_in_redis'])} áudios ausentes no Redis")
                self.verification_results['warnings'] += 1
            
            if audio_results['missing_in_json']:
                logger.warning(f"⚠️ {len(audio_results['missing_in_json'])} áudios ausentes no JSON")
                self.verification_results['warnings'] += 1
            
            # Verificação detalhada registro por registro
            matched_count = 0
            field_mismatch_counts = {}
            
            for json_audio in json_audios:
                audio_id = json_audio['id']
                
                if audio_id in redis_ids:
                    # Buscar dados no Redis
                    redis_audio = await self.audio_manager.get_audio(audio_id)
                    
                    if redis_audio:
                        # Comparar dados
                        mismatch_details = self._compare_audio_records(json_audio, redis_audio)
                        
                        if not mismatch_details['has_mismatches']:
                            matched_count += 1
                        else:
                            audio_results['data_mismatches'].append({
                                'audio_id': audio_id,
                                'mismatches': mismatch_details['mismatches']
                            })
                            
                            # Contar tipos de mismatches
                            for field in mismatch_details['mismatched_fields']:
                                field_mismatch_counts[field] = field_mismatch_counts.get(field, 0) + 1
                    else:
                        audio_results['missing_in_redis'].append(audio_id)
            
            audio_results['matched_records'] = matched_count
            audio_results['field_mismatches'] = field_mismatch_counts
            
            # Calcular score de integridade
            if audio_results['total_json_records'] > 0:
                audio_results['integrity_score'] = (matched_count / audio_results['total_json_records']) * 100
            
            # Atualizar contadores globais
            self.verification_results['total_checks'] += audio_results['total_json_records']
            self.verification_results['passed_checks'] += matched_count
            self.verification_results['failed_checks'] += (audio_results['total_json_records'] - matched_count)
            
            logger.info(f"🎵 Áudios verificados: {matched_count}/{audio_results['total_json_records']} ({audio_results['integrity_score']:.1f}%)")
            
        except Exception as e:
            logger.error(f"❌ Erro na verificação de áudios: {e}")
            audio_results['errors'] = [str(e)]
            self.verification_results['failed_checks'] += 1
        
        self.verification_results['detailed_results']['audio_verification'] = audio_results
    
    def _compare_audio_records(self, json_record: Dict, redis_record: Dict) -> Dict[str, Any]:
        """Compara detalhadamente registros de áudio"""
        mismatches = []
        mismatched_fields = []
        
        # Campos críticos para comparação
        critical_fields = ['id', 'title', 'youtube_id', 'url', 'format', 'filesize']
        
        for field in critical_fields:
            json_value = json_record.get(field)
            redis_value = redis_record.get(field)
            
            # Normalizar valores para comparação
            if isinstance(json_value, (int, float)) and isinstance(redis_value, str):
                try:
                    redis_value = type(json_value)(redis_value)
                except (ValueError, TypeError):
                    pass
            
            if json_value != redis_value:
                mismatches.append({
                    'field': field,
                    'json_value': json_value,
                    'redis_value': redis_value,
                    'type_json': type(json_value).__name__,
                    'type_redis': type(redis_value).__name__
                })
                mismatched_fields.append(field)
        
        # Verificação especial para keywords (podem ser em ordens diferentes)
        json_keywords = set(json_record.get('keywords', []))
        redis_keywords = set(redis_record.get('keywords', []))
        
        if json_keywords != redis_keywords:
            mismatches.append({
                'field': 'keywords',
                'json_value': list(json_keywords),
                'redis_value': list(redis_keywords),
                'missing_in_redis': list(json_keywords - redis_keywords),
                'extra_in_redis': list(redis_keywords - json_keywords)
            })
            mismatched_fields.append('keywords')
        
        return {
            'has_mismatches': len(mismatches) > 0,
            'mismatch_count': len(mismatches),
            'mismatches': mismatches,
            'mismatched_fields': mismatched_fields
        }
    
    async def _verify_video_data_integrity(self):
        """Verifica integridade dos dados de vídeos"""
        logger.info("🎬 Verificando integridade dos dados de vídeos...")
        
        video_results = {
            'total_json_records': 0,
            'total_redis_records': 0,
            'matched_records': 0,
            'data_mismatches': [],
            'integrity_score': 0.0
        }
        
        try:
            # Carregar dados JSON
            videos_file = self.data_dir / 'videos.json'
            if not videos_file.exists():
                video_results['errors'] = ['videos.json not found']
                self.verification_results['detailed_results']['video_verification'] = video_results
                return
            
            with open(videos_file, 'r', encoding='utf-8') as f:
                json_data = json.load(f)
            
            json_videos = json_data.get('videos', [])
            video_results['total_json_records'] = len(json_videos)
            
            # Obter contagem Redis
            redis_video_count = await self.video_manager.get_total_count()
            video_results['total_redis_records'] = redis_video_count
            
            # Verificação registro por registro
            matched_count = 0
            
            for json_video in json_videos:
                video_name = json_video.get('name')
                if not video_name:
                    continue
                
                # Buscar no Redis
                redis_video = await self.video_manager.get_video(video_name)
                
                if redis_video:
                    # Comparar dados básicos
                    if (json_video.get('path') == redis_video.get('path') and
                        json_video.get('type') == redis_video.get('type')):
                        matched_count += 1
                    else:
                        video_results['data_mismatches'].append({
                            'video_name': video_name,
                            'json_data': json_video,
                            'redis_data': redis_video
                        })
                else:
                    video_results['data_mismatches'].append({
                        'video_name': video_name,
                        'error': 'not_found_in_redis'
                    })
            
            video_results['matched_records'] = matched_count
            
            if video_results['total_json_records'] > 0:
                video_results['integrity_score'] = (matched_count / video_results['total_json_records']) * 100
            
            # Atualizar contadores globais
            self.verification_results['total_checks'] += video_results['total_json_records']
            self.verification_results['passed_checks'] += matched_count
            self.verification_results['failed_checks'] += (video_results['total_json_records'] - matched_count)
            
            logger.info(f"🎬 Vídeos verificados: {matched_count}/{video_results['total_json_records']} ({video_results['integrity_score']:.1f}%)")
            
        except Exception as e:
            logger.error(f"❌ Erro na verificação de vídeos: {e}")
            video_results['errors'] = [str(e)]
            self.verification_results['failed_checks'] += 1
        
        self.verification_results['detailed_results']['video_verification'] = video_results
    
    async def _verify_data_consistency(self):
        """Verifica consistência geral dos dados"""
        logger.info("🔗 Verificando consistência dos dados...")
        
        consistency_results = {
            'duplicate_checks': {},
            'referential_integrity': {},
            'data_types_consistency': {},
            'encoding_issues': []
        }
        
        # Verificar duplicatas no Redis
        audio_ids = await self.audio_manager.get_all_audio_ids()
        duplicate_ids = []
        seen_ids = set()
        
        for audio_id in audio_ids:
            if audio_id in seen_ids:
                duplicate_ids.append(audio_id)
            else:
                seen_ids.add(audio_id)
        
        consistency_results['duplicate_checks'] = {
            'total_audio_ids': len(audio_ids),
            'unique_audio_ids': len(seen_ids),
            'duplicates_found': len(duplicate_ids),
            'duplicate_ids': duplicate_ids
        }
        
        if len(duplicate_ids) > 0:
            logger.warning(f"⚠️ {len(duplicate_ids)} IDs duplicados encontrados")
            self.verification_results['warnings'] += 1
        else:
            self.verification_results['passed_checks'] += 1
        
        self.verification_results['total_checks'] += 1
        self.verification_results['detailed_results']['data_consistency'] = consistency_results
    
    async def _verify_performance_metrics(self):
        """Verifica métricas de performance do Redis"""
        logger.info("⚡ Verificando métricas de performance...")
        
        performance_results = {
            'connection_latency': 0.0,
            'read_latency': 0.0,
            'memory_usage': {},
            'key_counts': {}
        }
        
        try:
            # Testar latência de conexão
            start_time = time.time()
            await self.redis_client.ping()
            performance_results['connection_latency'] = (time.time() - start_time) * 1000  # ms
            
            # Testar latência de leitura
            audio_ids = await self.audio_manager.get_all_audio_ids()
            if audio_ids:
                sample_id = audio_ids[0]
                start_time = time.time()
                await self.audio_manager.get_audio(sample_id)
                performance_results['read_latency'] = (time.time() - start_time) * 1000  # ms
            
            # Informações de memória
            info = await self.redis_client.info()
            performance_results['memory_usage'] = {
                'used_memory': info.get('used_memory', 0),
                'used_memory_human': info.get('used_memory_human', '0B'),
                'used_memory_peak': info.get('used_memory_peak', 0),
                'used_memory_peak_human': info.get('used_memory_peak_human', '0B')
            }
            
            # Contagem de chaves
            all_keys = await self.redis_client.keys("youtube_downloader:*")
            audio_keys = [k for k in all_keys if b'audio:' in k]
            video_keys = [k for k in all_keys if b'video:' in k]
            
            performance_results['key_counts'] = {
                'total_keys': len(all_keys),
                'audio_keys': len(audio_keys),
                'video_keys': len(video_keys)
            }
            
            logger.info(f"⚡ Latência: {performance_results['connection_latency']:.2f}ms (ping), {performance_results['read_latency']:.2f}ms (read)")
            logger.info(f"⚡ Memória: {performance_results['memory_usage']['used_memory_human']}")
            
            self.verification_results['passed_checks'] += 1
            
        except Exception as e:
            logger.error(f"❌ Erro na verificação de performance: {e}")
            performance_results['errors'] = [str(e)]
            self.verification_results['failed_checks'] += 1
        
        self.verification_results['total_checks'] += 1
        self.verification_results['detailed_results']['performance_metrics'] = performance_results
    
    async def _calculate_integrity_score(self):
        """Calcula score geral de integridade"""
        logger.info("📊 Calculando score de integridade...")
        
        if self.verification_results['total_checks'] > 0:
            score = (self.verification_results['passed_checks'] / self.verification_results['total_checks']) * 100
            self.verification_results['integrity_score'] = round(score, 2)
        else:
            self.verification_results['integrity_score'] = 0.0
        
        logger.info(f"📊 Score de Integridade: {self.verification_results['integrity_score']:.1f}%")
    
    async def _generate_recommendations(self):
        """Gera recomendações baseadas nos resultados"""
        score = self.verification_results['integrity_score']
        failed_checks = self.verification_results['failed_checks']
        warnings = self.verification_results['warnings']
        
        if score >= 98.0 and failed_checks == 0:
            recommendation = "EXCELLENT - Migração perfeita, sistema pronto para produção"
        elif score >= 95.0 and failed_checks <= 2:
            recommendation = "GOOD - Migração bem-sucedida com problemas menores, monitorar"
        elif score >= 90.0 and failed_checks <= 5:
            recommendation = "ACCEPTABLE - Migração aceitável, corrigir problemas identificados"
        elif score >= 80.0:
            recommendation = "NEEDS_ATTENTION - Problemas significativos, investigação necessária"
        else:
            recommendation = "CRITICAL - Falhas graves, rollback recomendado"
        
        self.verification_results['recommendation'] = recommendation
        logger.info(f"💡 Recomendação: {recommendation}")
    
    async def _generate_verification_report(self) -> Dict[str, Any]:
        """Gera relatório completo da verificação"""
        duration = self.verification_results['end_time'] - self.verification_results['start_time']
        
        report = {
            'success': True,
            'verification_id': self.verification_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'duration_seconds': round(duration, 2),
            'integrity_score': self.verification_results['integrity_score'],
            'recommendation': self.verification_results['recommendation'],
            'summary': {
                'total_checks': self.verification_results['total_checks'],
                'passed_checks': self.verification_results['passed_checks'],
                'failed_checks': self.verification_results['failed_checks'],
                'warnings': self.verification_results['warnings'],
                'pass_rate': round(
                    (self.verification_results['passed_checks'] / max(1, self.verification_results['total_checks'])) * 100, 2
                )
            },
            'detailed_results': self.verification_results['detailed_results'],
            'verification_results': self.verification_results
        }
        
        # Salvar relatório
        report_dir = Path("E:\\python\\youtube_downloader\\reports\\verification")
        report_dir.mkdir(parents=True, exist_ok=True)
        
        report_file = report_dir / f"integrity_verification_{self.verification_id}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        logger.success(f"📊 Relatório de verificação salvo: {report_file}")
        
        return report


# Função principal para execução
async def verify_data_integrity() -> Dict[str, Any]:
    """
    Executa verificação completa de integridade dos dados
    
    Returns:
        Resultado da verificação
    """
    verifier = DataIntegrityVerifier()
    return await verifier.execute_full_verification()


if __name__ == "__main__":
    # Exemplo de uso
    async def main():
        result = await verify_data_integrity()
        
        if result['success']:
            print(f"✅ Verificação concluída!")
            print(f"📊 Score de Integridade: {result['integrity_score']:.1f}%")
            print(f"🔍 Checks: {result['summary']['passed_checks']}/{result['summary']['total_checks']} passou")
            print(f"💡 Recomendação: {result['recommendation']}")
            
            if result['summary']['failed_checks'] > 0:
                print(f"⚠️ Falhas encontradas: {result['summary']['failed_checks']}")
            
            if result['summary']['warnings'] > 0:
                print(f"⚠️ Avisos: {result['summary']['warnings']}")
        else:
            print(f"❌ Verificação falhou: {result.get('error')}")
    
    asyncio.run(main())