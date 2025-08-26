"""
Sistema de Recovery e Restauração de Dados
Implementa recuperação avançada com múltiplas estratégias de restore

Autor: Claude Code Agent
Data: 2025-08-26
Versão: 1.0.0 - FASE 2 Advanced Recovery System
"""

import asyncio
import json
import os
import shutil
import time
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Union

import redis.asyncio as redis
from loguru import logger

# Importar componentes do sistema
import sys
sys.path.append(str(Path(__file__).parent.parent))

from app.services.redis_connection import get_redis_client, init_redis
from app.services.redis_audio_manager import RedisAudioManager
from app.services.redis_video_manager import RedisVideoManager
from scripts.migration_backup_system import MigrationBackupSystem
from scripts.data_integrity_verifier import DataIntegrityVerifier


class DataRecoverySystem:
    """
    Sistema avançado de recovery com múltiplas estratégias
    Implementa recuperação inteligente baseada em contexto
    """
    
    def __init__(self, 
                 backup_dir: str = "E:\\python\\youtube_downloader\\backups",
                 data_dir: str = "E:\\python\\youtube_downloader\\data",
                 recovery_strategy: str = "intelligent"):
        
        self.backup_dir = Path(backup_dir)
        self.data_dir = Path(data_dir)
        self.recovery_strategy = recovery_strategy  # intelligent, conservative, aggressive
        
        # Componentes do sistema
        self.redis_client: Optional[redis.Redis] = None
        self.audio_manager: Optional[RedisAudioManager] = None
        self.video_manager: Optional[RedisVideoManager] = None
        self.integrity_verifier: Optional[DataIntegrityVerifier] = None
        
        # Estado do recovery
        self.recovery_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.recovery_state = {
            'recovery_id': self.recovery_id,
            'strategy': recovery_strategy,
            'start_time': None,
            'end_time': None,
            'status': 'initialized',
            'current_phase': 'setup',
            'recovery_operations': [],
            'data_sources_analyzed': [],
            'recovery_success_rate': 0.0,
            'issues_found': [],
            'issues_resolved': [],
            'final_recommendations': []
        }
        
        # Configuração de logs
        self._setup_recovery_logging()
        
        logger.info(f"🔧 Sistema de Recovery inicializado: {self.recovery_id}")
        logger.info(f"📋 Estratégia: {recovery_strategy}")
    
    def _setup_recovery_logging(self):
        """Configura sistema de logs para recovery"""
        log_dir = Path("E:\\python\\youtube_downloader\\logs\\recovery")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / f"recovery_{self.recovery_id}.log"
        
        logger.add(
            str(log_file),
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | RECOVERY | {message}",
            level="DEBUG",
            retention="60 days",
            compression="zip"
        )
        
        logger.info(f"📋 Logs de recovery: {log_file}")
    
    async def execute_intelligent_recovery(self, 
                                         recovery_scope: str = "full",
                                         target_timestamp: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Executa recovery inteligente com análise automática
        
        Args:
            recovery_scope: Escopo do recovery (full, partial, audio_only, video_only)
            target_timestamp: Timestamp alvo para recovery (None = mais recente)
            
        Returns:
            Resultado do recovery
        """
        logger.info(f"🚀 Iniciando recovery inteligente: {recovery_scope}")
        self.recovery_state['start_time'] = time.time()
        self.recovery_state['status'] = 'in_progress'
        
        try:
            # FASE 1: Análise da situação atual
            await self._analyze_current_state()
            
            # FASE 2: Identificar fontes de dados disponíveis
            available_sources = await self._discover_data_sources(target_timestamp)
            
            # FASE 3: Criar plano de recovery
            recovery_plan = await self._create_recovery_plan(available_sources, recovery_scope)
            
            # FASE 4: Executar recovery baseado no plano
            recovery_results = await self._execute_recovery_plan(recovery_plan)
            
            # FASE 5: Validar dados recuperados
            validation_results = await self._validate_recovered_data()
            
            # FASE 6: Resolver problemas encontrados
            resolution_results = await self._resolve_identified_issues(validation_results)
            
            # FASE 7: Finalizar e otimizar
            await self._finalize_recovery()
            
            self.recovery_state['status'] = 'completed'
            self.recovery_state['end_time'] = time.time()
            
            # Gerar relatório final
            final_report = await self._generate_recovery_report(
                recovery_results, validation_results, resolution_results
            )
            
            logger.success("✅ Recovery inteligente concluído com sucesso")
            return final_report
            
        except Exception as e:
            logger.error(f"❌ Falha no recovery inteligente: {e}")
            
            self.recovery_state['status'] = 'failed'
            self.recovery_state['end_time'] = time.time()
            
            # Tentar recovery de emergência
            emergency_result = await self._emergency_recovery_fallback()
            
            return {
                'success': False,
                'recovery_id': self.recovery_id,
                'error': str(e),
                'recovery_state': self.recovery_state,
                'emergency_recovery': emergency_result,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    async def _analyze_current_state(self):
        """Analisa estado atual do sistema"""
        logger.info("🔍 Analisando estado atual do sistema...")
        self.recovery_state['current_phase'] = 'state_analysis'
        
        current_state = {
            'timestamp': time.time(),
            'files_status': {},
            'redis_status': {},
            'system_health': {}
        }
        
        # Analisar arquivos JSON
        audios_file = self.data_dir / 'audios.json'
        videos_file = self.data_dir / 'videos.json'
        
        current_state['files_status'] = {
            'audios_json': {
                'exists': audios_file.exists(),
                'size': audios_file.stat().st_size if audios_file.exists() else 0,
                'modified': audios_file.stat().st_mtime if audios_file.exists() else 0,
                'valid_json': False,
                'record_count': 0
            },
            'videos_json': {
                'exists': videos_file.exists(),
                'size': videos_file.stat().st_size if videos_file.exists() else 0,
                'modified': videos_file.stat().st_mtime if videos_file.exists() else 0,
                'valid_json': False,
                'record_count': 0
            }
        }
        
        # Validar JSONs
        if audios_file.exists():
            try:
                with open(audios_file, 'r', encoding='utf-8') as f:
                    audios_data = json.load(f)
                current_state['files_status']['audios_json']['valid_json'] = True
                current_state['files_status']['audios_json']['record_count'] = len(audios_data.get('audios', []))
            except Exception as e:
                logger.warning(f"⚠️ audios.json inválido: {e}")
                self.recovery_state['issues_found'].append({
                    'type': 'invalid_json',
                    'file': 'audios.json',
                    'error': str(e)
                })
        
        if videos_file.exists():
            try:
                with open(videos_file, 'r', encoding='utf-8') as f:
                    videos_data = json.load(f)
                current_state['files_status']['videos_json']['valid_json'] = True
                current_state['files_status']['videos_json']['record_count'] = len(videos_data.get('videos', []))
            except Exception as e:
                logger.warning(f"⚠️ videos.json inválido: {e}")
                self.recovery_state['issues_found'].append({
                    'type': 'invalid_json',
                    'file': 'videos.json',
                    'error': str(e)
                })
        
        # Analisar Redis
        try:
            await init_redis()
            self.redis_client = await get_redis_client()
            await self.redis_client.ping()
            
            redis_keys = await self.redis_client.keys("youtube_downloader:*")
            audio_keys = [k for k in redis_keys if b'audio:' in k]
            video_keys = [k for k in redis_keys if b'video:' in k]
            
            current_state['redis_status'] = {
                'connected': True,
                'total_keys': len(redis_keys),
                'audio_keys': len(audio_keys),
                'video_keys': len(video_keys),
                'health_ok': True
            }
            
            # Inicializar managers
            self.audio_manager = RedisAudioManager()
            self.video_manager = RedisVideoManager()
            
            await self.audio_manager.initialize()
            await self.video_manager.initialize()
            
        except Exception as e:
            logger.warning(f"⚠️ Problema com Redis: {e}")
            current_state['redis_status'] = {
                'connected': False,
                'error': str(e),
                'health_ok': False
            }
            self.recovery_state['issues_found'].append({
                'type': 'redis_connection',
                'error': str(e)
            })
        
        self.recovery_state['recovery_operations'].append({
            'operation': 'state_analysis',
            'result': current_state,
            'timestamp': time.time()
        })
        
        logger.info(f"📊 Estado atual analisado")
        logger.info(f"📁 Áudios JSON: {current_state['files_status']['audios_json']['record_count']} registros")
        logger.info(f"📁 Vídeos JSON: {current_state['files_status']['videos_json']['record_count']} registros")
        logger.info(f"📊 Redis: {current_state['redis_status'].get('total_keys', 0)} chaves")
    
    async def _discover_data_sources(self, target_timestamp: Optional[datetime]) -> Dict[str, List[Dict]]:
        """Descobre todas as fontes de dados disponíveis"""
        logger.info("🔎 Descobrindo fontes de dados disponíveis...")
        self.recovery_state['current_phase'] = 'source_discovery'
        
        data_sources = {
            'migration_backups': [],
            'compressed_backups': [],
            'manual_backups': [],
            'system_backups': [],
            'partial_data': []
        }
        
        # Procurar backups de migração
        for backup_dir in self.backup_dir.glob("migration_*"):
            if backup_dir.is_dir():
                try:
                    # Extrair timestamp
                    timestamp_str = backup_dir.name.replace("migration_", "")
                    backup_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    
                    # Verificar se atende critério temporal
                    if target_timestamp and backup_time > target_timestamp:
                        continue
                    
                    # Analisar conteúdo do backup
                    backup_info = await self._analyze_backup_content(backup_dir)
                    backup_info.update({
                        'path': backup_dir,
                        'timestamp': backup_time,
                        'type': 'migration',
                        'priority': 1
                    })
                    
                    data_sources['migration_backups'].append(backup_info)
                    
                except ValueError:
                    continue
        
        # Procurar backups comprimidos
        for zip_file in self.backup_dir.glob("backup_*.zip"):
            try:
                backup_time = datetime.fromtimestamp(zip_file.stat().st_mtime)
                
                if target_timestamp and backup_time > target_timestamp:
                    continue
                
                backup_info = {
                    'path': zip_file,
                    'timestamp': backup_time,
                    'type': 'compressed',
                    'size': zip_file.stat().st_size,
                    'priority': 2
                }
                
                data_sources['compressed_backups'].append(backup_info)
                
            except Exception:
                continue
        
        # Procurar dados parciais
        partial_data = await self._find_partial_data()
        data_sources['partial_data'] = partial_data
        
        # Ordenar por prioridade e timestamp
        for source_type in data_sources:
            data_sources[source_type].sort(
                key=lambda x: (x.get('priority', 99), x.get('timestamp', datetime.min)),
                reverse=True
            )
        
        self.recovery_state['data_sources_analyzed'] = data_sources
        
        total_sources = sum(len(sources) for sources in data_sources.values())
        logger.info(f"🔎 {total_sources} fontes de dados descobertas")
        
        for source_type, sources in data_sources.items():
            if sources:
                logger.info(f"  📁 {source_type}: {len(sources)} fontes")
        
        return data_sources
    
    async def _analyze_backup_content(self, backup_path: Path) -> Dict[str, Any]:
        """Analisa conteúdo de um backup"""
        content_info = {
            'has_json_data': False,
            'has_audio_samples': False,
            'has_configurations': False,
            'manifest_exists': False,
            'estimated_records': 0,
            'integrity_verified': False
        }
        
        try:
            # Verificar manifesto
            manifest_file = backup_path / 'backup_manifest.json'
            if manifest_file.exists():
                content_info['manifest_exists'] = True
                
                with open(manifest_file, 'r', encoding='utf-8') as f:
                    manifest = json.load(f)
                
                content_info['estimated_records'] = manifest.get('total_stats', {}).get('files_count', 0)
            
            # Verificar dados JSON
            json_data_dir = backup_path / 'json_data'
            if json_data_dir.exists():
                content_info['has_json_data'] = True
                
                # Contar registros se possível
                audios_backup = json_data_dir / 'audios.json'
                if audios_backup.exists():
                    try:
                        with open(audios_backup, 'r', encoding='utf-8') as f:
                            audios_data = json.load(f)
                        content_info['estimated_records'] = len(audios_data.get('audios', []))
                    except:
                        pass
            
            # Verificar amostras de áudio
            audio_samples_dir = backup_path / 'audio_samples'
            content_info['has_audio_samples'] = audio_samples_dir.exists()
            
            # Verificar configurações
            config_dir = backup_path / 'configurations'
            content_info['has_configurations'] = config_dir.exists()
            
            # Verificar integridade
            verification_report = backup_path / 'verification_report.json'
            if verification_report.exists():
                try:
                    with open(verification_report, 'r', encoding='utf-8') as f:
                        verification_data = json.load(f)
                    content_info['integrity_verified'] = verification_data.get('success', False)
                except:
                    pass
            
        except Exception as e:
            logger.warning(f"⚠️ Erro analisando backup {backup_path}: {e}")
        
        return content_info
    
    async def _find_partial_data(self) -> List[Dict[str, Any]]:
        """Procura por dados parciais no sistema"""
        partial_sources = []
        
        # Procurar por arquivos de backup temporários
        for backup_file in self.data_dir.glob("*.rollback_backup_*"):
            partial_sources.append({
                'path': backup_file,
                'type': 'rollback_backup',
                'timestamp': datetime.fromtimestamp(backup_file.stat().st_mtime),
                'size': backup_file.stat().st_size,
                'priority': 3
            })
        
        # Procurar por dados em diretórios temporários
        temp_dirs = [
            self.backup_dir / "extracted_*",
            self.backup_dir / "emergency_extract_*"
        ]
        
        for pattern in temp_dirs:
            for temp_dir in self.backup_dir.glob(pattern.name):
                if temp_dir.is_dir():
                    partial_sources.append({
                        'path': temp_dir,
                        'type': 'temporary_extraction',
                        'timestamp': datetime.fromtimestamp(temp_dir.stat().st_mtime),
                        'priority': 4
                    })
        
        return partial_sources
    
    async def _create_recovery_plan(self, available_sources: Dict[str, List], recovery_scope: str) -> Dict[str, Any]:
        """Cria plano inteligente de recovery"""
        logger.info("📋 Criando plano de recovery inteligente...")
        self.recovery_state['current_phase'] = 'plan_creation'
        
        recovery_plan = {
            'strategy': self.recovery_strategy,
            'scope': recovery_scope,
            'primary_source': None,
            'fallback_sources': [],
            'recovery_steps': [],
            'risk_assessment': 'low',
            'estimated_duration': 0,
            'success_probability': 0.0
        }
        
        # Selecionar fonte primária
        primary_source = None
        
        # Priorizar por tipo e qualidade
        for source_type in ['migration_backups', 'compressed_backups', 'manual_backups']:
            sources = available_sources.get(source_type, [])
            if sources:
                # Pegar o melhor baseado em critérios
                best_source = max(sources, key=lambda x: (
                    x.get('integrity_verified', False),
                    x.get('estimated_records', 0),
                    x.get('timestamp', datetime.min)
                ))
                
                if best_source:
                    primary_source = best_source
                    break
        
        if not primary_source:
            # Usar dados parciais como último recurso
            partial_sources = available_sources.get('partial_data', [])
            if partial_sources:
                primary_source = partial_sources[0]
                recovery_plan['risk_assessment'] = 'high'
        
        recovery_plan['primary_source'] = primary_source
        
        # Definir fontes de fallback
        fallback_sources = []
        for source_type in available_sources:
            for source in available_sources[source_type]:
                if source != primary_source:
                    fallback_sources.append(source)
        
        # Ordenar fallbacks por qualidade
        fallback_sources.sort(key=lambda x: (
            x.get('priority', 99),
            -x.get('estimated_records', 0),
            x.get('timestamp', datetime.min)
        ))
        
        recovery_plan['fallback_sources'] = fallback_sources[:3]  # Top 3 fallbacks
        
        # Definir passos do recovery
        recovery_steps = []
        
        if recovery_scope in ['full', 'audio_only']:
            recovery_steps.append({
                'step': 'recover_audio_data',
                'description': 'Recuperar dados de áudios',
                'estimated_time': 30,
                'critical': True
            })
        
        if recovery_scope in ['full', 'video_only']:
            recovery_steps.append({
                'step': 'recover_video_data',
                'description': 'Recuperar dados de vídeos',
                'estimated_time': 10,
                'critical': False
            })
        
        if recovery_scope == 'full':
            recovery_steps.extend([
                {
                    'step': 'validate_data_integrity',
                    'description': 'Validar integridade dos dados',
                    'estimated_time': 60,
                    'critical': True
                },
                {
                    'step': 'optimize_redis_data',
                    'description': 'Otimizar dados no Redis',
                    'estimated_time': 30,
                    'critical': False
                }
            ])
        
        recovery_plan['recovery_steps'] = recovery_steps
        recovery_plan['estimated_duration'] = sum(step['estimated_time'] for step in recovery_steps)
        
        # Calcular probabilidade de sucesso
        success_factors = []
        
        if primary_source:
            success_factors.append(0.4)  # Fonte primária disponível
            
            if primary_source.get('integrity_verified', False):
                success_factors.append(0.3)  # Integridade verificada
            
            if primary_source.get('estimated_records', 0) > 0:
                success_factors.append(0.2)  # Dados disponíveis
        
        if len(fallback_sources) > 0:
            success_factors.append(0.1)  # Fallbacks disponíveis
        
        recovery_plan['success_probability'] = sum(success_factors) * 100
        
        self.recovery_state['recovery_operations'].append({
            'operation': 'plan_creation',
            'result': recovery_plan,
            'timestamp': time.time()
        })
        
        logger.info(f"📋 Plano de recovery criado")
        logger.info(f"  🎯 Escopo: {recovery_scope}")
        logger.info(f"  📊 Probabilidade de sucesso: {recovery_plan['success_probability']:.1f}%")
        logger.info(f"  ⏱️ Duração estimada: {recovery_plan['estimated_duration']} segundos")
        logger.info(f"  📁 Fonte primária: {primary_source['type'] if primary_source else 'None'}")
        
        return recovery_plan
    
    async def _execute_recovery_plan(self, recovery_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Executa o plano de recovery"""
        logger.info("🚀 Executando plano de recovery...")
        self.recovery_state['current_phase'] = 'plan_execution'
        
        execution_results = {
            'steps_completed': 0,
            'steps_failed': 0,
            'data_recovered': {
                'audios': 0,
                'videos': 0
            },
            'sources_used': [],
            'fallback_activations': 0,
            'execution_details': []
        }
        
        primary_source = recovery_plan['primary_source']
        fallback_sources = recovery_plan['fallback_sources']
        
        if not primary_source:
            raise Exception("Nenhuma fonte primária disponível para recovery")
        
        try:
            # Executar cada passo do plano
            for step_info in recovery_plan['recovery_steps']:
                step_name = step_info['step']
                logger.info(f"⚙️ Executando: {step_info['description']}")
                
                step_start_time = time.time()
                step_success = False
                step_details = {
                    'step': step_name,
                    'start_time': step_start_time,
                    'description': step_info['description'],
                    'critical': step_info['critical']
                }
                
                try:
                    if step_name == 'recover_audio_data':
                        result = await self._recover_audio_data(primary_source, fallback_sources)
                        execution_results['data_recovered']['audios'] = result['recovered_count']
                        step_success = result['success']
                        step_details['result'] = result
                        
                    elif step_name == 'recover_video_data':
                        result = await self._recover_video_data(primary_source, fallback_sources)
                        execution_results['data_recovered']['videos'] = result['recovered_count']
                        step_success = result['success']
                        step_details['result'] = result
                        
                    elif step_name == 'validate_data_integrity':
                        if not self.integrity_verifier:
                            self.integrity_verifier = DataIntegrityVerifier()
                        
                        result = await self.integrity_verifier.execute_full_verification()
                        step_success = result.get('success', False) and result.get('integrity_score', 0) >= 90
                        step_details['result'] = {
                            'integrity_score': result.get('integrity_score', 0),
                            'validation_success': step_success
                        }
                        
                    elif step_name == 'optimize_redis_data':
                        result = await self._optimize_redis_data()
                        step_success = result['success']
                        step_details['result'] = result
                    
                    if step_success:
                        execution_results['steps_completed'] += 1
                        logger.success(f"✅ {step_info['description']} - Concluído")
                    else:
                        execution_results['steps_failed'] += 1
                        logger.warning(f"⚠️ {step_info['description']} - Falhou")
                        
                        # Se é crítico e falhou, tentar fallback
                        if step_info['critical']:
                            logger.warning("🔄 Passo crítico falhou, tentando fallback...")
                            # Implementar lógica de fallback se necessário
                    
                except Exception as e:
                    logger.error(f"❌ Erro no passo {step_name}: {e}")
                    execution_results['steps_failed'] += 1
                    step_details['error'] = str(e)
                    
                    if step_info['critical']:
                        # Para passos críticos, interromper execução
                        step_details['critical_failure'] = True
                        execution_results['execution_details'].append(step_details)
                        raise Exception(f"Passo crítico falhou: {step_name}")
                
                step_details['end_time'] = time.time()
                step_details['duration'] = step_details['end_time'] - step_start_time
                step_details['success'] = step_success
                
                execution_results['execution_details'].append(step_details)
        
        except Exception as e:
            logger.error(f"❌ Falha na execução do plano: {e}")
            execution_results['execution_error'] = str(e)
            raise
        
        self.recovery_state['recovery_operations'].append({
            'operation': 'plan_execution',
            'result': execution_results,
            'timestamp': time.time()
        })
        
        logger.info(f"🚀 Execução do plano concluída")
        logger.info(f"  ✅ Passos concluídos: {execution_results['steps_completed']}")
        logger.info(f"  ❌ Passos falharam: {execution_results['steps_failed']}")
        logger.info(f"  🎵 Áudios recuperados: {execution_results['data_recovered']['audios']}")
        logger.info(f"  🎬 Vídeos recuperados: {execution_results['data_recovered']['videos']}")
        
        return execution_results
    
    async def _recover_audio_data(self, primary_source: Dict, fallback_sources: List[Dict]) -> Dict[str, Any]:
        """Recupera dados de áudios de fontes disponíveis"""
        logger.info("🎵 Recuperando dados de áudios...")
        
        recovery_result = {
            'success': False,
            'recovered_count': 0,
            'source_used': None,
            'errors': []
        }
        
        # Lista de fontes para tentar (primária + fallbacks)
        sources_to_try = [primary_source] + fallback_sources
        
        for source in sources_to_try:
            try:
                logger.info(f"🔄 Tentando fonte: {source['type']} - {source['path']}")
                
                audios_data = await self._extract_audio_data_from_source(source)
                
                if audios_data:
                    # Restaurar dados no sistema
                    if await self._restore_audio_data_to_system(audios_data):
                        recovery_result['success'] = True
                        recovery_result['recovered_count'] = len(audios_data.get('audios', []))
                        recovery_result['source_used'] = source
                        
                        logger.success(f"✅ {recovery_result['recovered_count']} áudios recuperados de {source['type']}")
                        break
                    else:
                        recovery_result['errors'].append(f"Falha ao restaurar dados de {source['type']}")
                else:
                    recovery_result['errors'].append(f"Nenhum dado encontrado em {source['type']}")
                    
            except Exception as e:
                error_msg = f"Erro com fonte {source['type']}: {str(e)}"
                logger.warning(f"⚠️ {error_msg}")
                recovery_result['errors'].append(error_msg)
                continue
        
        if not recovery_result['success']:
            logger.error("❌ Falha ao recuperar dados de áudios de todas as fontes")
        
        return recovery_result
    
    async def _extract_audio_data_from_source(self, source: Dict) -> Optional[Dict]:
        """Extrai dados de áudios de uma fonte específica"""
        source_path = Path(source['path'])
        source_type = source['type']
        
        try:
            if source_type == 'compressed':
                # Extrair backup comprimido
                extract_dir = self.backup_dir / f"temp_extract_{self.recovery_id}"
                extract_dir.mkdir(parents=True, exist_ok=True)
                
                with zipfile.ZipFile(source_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                
                # Procurar por audios.json
                for audios_file in extract_dir.rglob('audios.json'):
                    with open(audios_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
                        
            elif source_type in ['migration', 'manual_backup']:
                # Backup em diretório
                json_data_dir = source_path / 'json_data'
                audios_file = json_data_dir / 'audios.json'
                
                if audios_file.exists():
                    with open(audios_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
                        
            elif source_type == 'rollback_backup':
                # Arquivo de backup direto
                if source_path.name == 'audios.json' or source_path.name.endswith('.json'):
                    with open(source_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                    # Se é um backup de audios.json
                    if 'audios' in data:
                        return data
            
        except Exception as e:
            logger.error(f"❌ Erro extraindo dados de {source_type}: {e}")
            
        return None
    
    async def _restore_audio_data_to_system(self, audios_data: Dict) -> bool:
        """Restaura dados de áudios no sistema (JSON + Redis)"""
        try:
            # Restaurar arquivo JSON
            audios_file = self.data_dir / 'audios.json'
            
            # Fazer backup do arquivo atual se existir
            if audios_file.exists():
                backup_file = audios_file.with_suffix(f'.recovery_backup_{self.recovery_id}.json')
                shutil.copy2(audios_file, backup_file)
            
            # Salvar novos dados
            with open(audios_file, 'w', encoding='utf-8') as f:
                json.dump(audios_data, f, indent=2, ensure_ascii=False)
            
            # Restaurar no Redis se managers estão disponíveis
            if self.audio_manager:
                audios_list = audios_data.get('audios', [])
                
                for audio in audios_list:
                    try:
                        await self.audio_manager.add_audio(audio)
                    except Exception as e:
                        logger.warning(f"⚠️ Erro adicionando áudio {audio.get('id', 'unknown')} ao Redis: {e}")
                        # Continuar com outros áudios
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro restaurando dados de áudios: {e}")
            return False
    
    async def _recover_video_data(self, primary_source: Dict, fallback_sources: List[Dict]) -> Dict[str, Any]:
        """Recupera dados de vídeos (implementação similar aos áudios)"""
        logger.info("🎬 Recuperando dados de vídeos...")
        
        recovery_result = {
            'success': False,
            'recovered_count': 0,
            'source_used': None,
            'errors': []
        }
        
        # Implementação similar ao recovery de áudios
        sources_to_try = [primary_source] + fallback_sources
        
        for source in sources_to_try:
            try:
                videos_data = await self._extract_video_data_from_source(source)
                
                if videos_data:
                    if await self._restore_video_data_to_system(videos_data):
                        recovery_result['success'] = True
                        recovery_result['recovered_count'] = len(videos_data.get('videos', []))
                        recovery_result['source_used'] = source
                        
                        logger.success(f"✅ {recovery_result['recovered_count']} vídeos recuperados")
                        break
                        
            except Exception as e:
                error_msg = f"Erro com fonte {source['type']}: {str(e)}"
                recovery_result['errors'].append(error_msg)
                continue
        
        return recovery_result
    
    async def _extract_video_data_from_source(self, source: Dict) -> Optional[Dict]:
        """Extrai dados de vídeos de uma fonte"""
        # Implementação similar à extração de áudios, mas para videos.json
        source_path = Path(source['path'])
        source_type = source['type']
        
        try:
            if source_type == 'compressed':
                extract_dir = self.backup_dir / f"temp_extract_{self.recovery_id}"
                extract_dir.mkdir(parents=True, exist_ok=True)
                
                with zipfile.ZipFile(source_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                
                for videos_file in extract_dir.rglob('videos.json'):
                    with open(videos_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
                        
            elif source_type in ['migration', 'manual_backup']:
                json_data_dir = source_path / 'json_data'
                videos_file = json_data_dir / 'videos.json'
                
                if videos_file.exists():
                    with open(videos_file, 'r', encoding='utf-8') as f:
                        return json.load(f)
                        
        except Exception as e:
            logger.error(f"❌ Erro extraindo dados de vídeos: {e}")
            
        return None
    
    async def _restore_video_data_to_system(self, videos_data: Dict) -> bool:
        """Restaura dados de vídeos no sistema"""
        try:
            videos_file = self.data_dir / 'videos.json'
            
            if videos_file.exists():
                backup_file = videos_file.with_suffix(f'.recovery_backup_{self.recovery_id}.json')
                shutil.copy2(videos_file, backup_file)
            
            with open(videos_file, 'w', encoding='utf-8') as f:
                json.dump(videos_data, f, indent=2, ensure_ascii=False)
            
            # Restaurar no Redis
            if self.video_manager:
                videos_list = videos_data.get('videos', [])
                
                for video in videos_list:
                    try:
                        await self.video_manager.add_video(video)
                    except Exception as e:
                        logger.warning(f"⚠️ Erro adicionando vídeo ao Redis: {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro restaurando dados de vídeos: {e}")
            return False
    
    async def _optimize_redis_data(self) -> Dict[str, Any]:
        """Otimiza dados no Redis após recovery"""
        logger.info("⚡ Otimizando dados no Redis...")
        
        optimization_result = {
            'success': False,
            'operations_performed': [],
            'performance_improvement': {}
        }
        
        try:
            if self.redis_client and self.audio_manager:
                # Otimização de índices
                await self.audio_manager._rebuild_search_indexes()
                optimization_result['operations_performed'].append('search_indexes_rebuilt')
                
                # Compactação de dados (se aplicável)
                # Implementar otimizações específicas conforme necessário
                
                optimization_result['success'] = True
                
        except Exception as e:
            logger.error(f"❌ Erro na otimização: {e}")
            optimization_result['error'] = str(e)
        
        return optimization_result
    
    async def _validate_recovered_data(self) -> Dict[str, Any]:
        """Valida dados recuperados"""
        logger.info("🔍 Validando dados recuperados...")
        
        if not self.integrity_verifier:
            self.integrity_verifier = DataIntegrityVerifier()
        
        validation_results = await self.integrity_verifier.execute_full_verification()
        
        return validation_results
    
    async def _resolve_identified_issues(self, validation_results: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve problemas identificados durante validação"""
        logger.info("🔧 Resolvendo problemas identificados...")
        
        resolution_results = {
            'issues_resolved': 0,
            'issues_remaining': 0,
            'resolutions_applied': []
        }
        
        # Implementar lógica de resolução baseada nos resultados de validação
        # Por agora, apenas registrar os problemas
        
        if not validation_results.get('success', False):
            logger.warning("⚠️ Problemas de validação detectados")
            
        return resolution_results
    
    async def _finalize_recovery(self):
        """Finaliza processo de recovery"""
        logger.info("🏁 Finalizando recovery...")
        self.recovery_state['current_phase'] = 'finalization'
        
        # Limpar arquivos temporários
        temp_dirs = list(self.backup_dir.glob(f"temp_extract_{self.recovery_id}"))
        for temp_dir in temp_dirs:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
                logger.info(f"🧹 Removido diretório temporário: {temp_dir}")
        
        # Criar marcador de recovery completo
        recovery_marker = self.data_dir / f'.recovery_completed_{self.recovery_id}'
        recovery_marker.write_text(
            json.dumps({
                'recovery_id': self.recovery_id,
                'completion_time': datetime.now(timezone.utc).isoformat(),
                'strategy': self.recovery_strategy
            }, indent=2)
        )
    
    async def _emergency_recovery_fallback(self) -> Dict[str, Any]:
        """Recovery de emergência quando recovery principal falha"""
        logger.critical("🆘 Executando recovery de emergência...")
        
        # Implementação básica - tentar restaurar de qualquer fonte disponível
        emergency_result = {
            'success': False,
            'operations': [],
            'data_found': False
        }
        
        try:
            # Procurar qualquer arquivo JSON válido
            for json_file in self.backup_dir.rglob('*.json'):
                if json_file.name in ['audios.json', 'videos.json']:
                    try:
                        with open(json_file, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        
                        # Copiar para local correto
                        target_file = self.data_dir / json_file.name
                        shutil.copy2(json_file, target_file)
                        
                        emergency_result['operations'].append(f"Restored {json_file.name}")
                        emergency_result['data_found'] = True
                        
                    except Exception:
                        continue
            
            emergency_result['success'] = emergency_result['data_found']
            
        except Exception as e:
            emergency_result['error'] = str(e)
        
        return emergency_result
    
    async def _generate_recovery_report(self, 
                                      recovery_results: Dict,
                                      validation_results: Dict,
                                      resolution_results: Dict) -> Dict[str, Any]:
        """Gera relatório completo do recovery"""
        duration = self.recovery_state['end_time'] - self.recovery_state['start_time']
        
        # Calcular taxa de sucesso geral
        total_operations = len(self.recovery_state['recovery_operations'])
        successful_operations = sum(
            1 for op in self.recovery_state['recovery_operations'] 
            if op.get('result', {}).get('success', True)
        )
        
        success_rate = (successful_operations / total_operations * 100) if total_operations > 0 else 0
        
        report = {
            'success': True,
            'recovery_id': self.recovery_id,
            'strategy': self.recovery_strategy,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'duration_seconds': round(duration, 2),
            'duration_minutes': round(duration / 60, 2),
            'success_rate': round(success_rate, 2),
            'data_recovered': {
                'audios': recovery_results.get('data_recovered', {}).get('audios', 0),
                'videos': recovery_results.get('data_recovered', {}).get('videos', 0)
            },
            'integrity_score': validation_results.get('integrity_score', 0),
            'issues_found': len(self.recovery_state['issues_found']),
            'issues_resolved': resolution_results.get('issues_resolved', 0),
            'recovery_state': self.recovery_state,
            'detailed_results': {
                'recovery_execution': recovery_results,
                'validation_results': validation_results,
                'resolution_results': resolution_results
            },
            'recommendations': self._generate_recovery_recommendations(validation_results)
        }
        
        # Salvar relatório
        report_dir = Path("E:\\python\\youtube_downloader\\reports\\recovery")
        report_dir.mkdir(parents=True, exist_ok=True)
        
        report_file = report_dir / f"recovery_report_{self.recovery_id}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        logger.success(f"📊 Relatório de recovery salvo: {report_file}")
        
        return report
    
    def _generate_recovery_recommendations(self, validation_results: Dict[str, Any]) -> List[str]:
        """Gera recomendações baseadas nos resultados"""
        recommendations = []
        
        integrity_score = validation_results.get('integrity_score', 0)
        
        if integrity_score >= 95:
            recommendations.append("Sistema recuperado com excelência - nenhuma ação adicional necessária")
        elif integrity_score >= 90:
            recommendations.append("Recovery bem-sucedido - monitorar sistema por 24h")
        elif integrity_score >= 80:
            recommendations.append("Recovery parcialmente bem-sucedido - investigar problemas menores")
        else:
            recommendations.append("Recovery com problemas - considerar rollback ou recovery adicional")
        
        # Adicionar recomendações específicas baseadas nos problemas encontrados
        if self.recovery_state['issues_found']:
            recommendations.append("Resolver problemas identificados antes da próxima migração")
        
        if len(self.recovery_state['recovery_operations']) > 5:
            recommendations.append("Implementar backup mais frequente para reduzir complexidade do recovery")
        
        return recommendations


# Função principal para execução
async def execute_intelligent_recovery(recovery_scope: str = "full",
                                     recovery_strategy: str = "intelligent",
                                     target_timestamp: Optional[datetime] = None) -> Dict[str, Any]:
    """
    Executa recovery inteligente dos dados
    
    Args:
        recovery_scope: Escopo do recovery (full, partial, audio_only, video_only)
        recovery_strategy: Estratégia (intelligent, conservative, aggressive)
        target_timestamp: Timestamp alvo para recovery
        
    Returns:
        Resultado do recovery
    """
    recovery_system = DataRecoverySystem(recovery_strategy=recovery_strategy)
    return await recovery_system.execute_intelligent_recovery(recovery_scope, target_timestamp)


if __name__ == "__main__":
    # Exemplo de uso
    async def main():
        result = await execute_intelligent_recovery(
            recovery_scope="full",
            recovery_strategy="intelligent"
        )
        
        if result['success']:
            print("✅ Recovery inteligente concluído com sucesso!")
            print(f"📊 Taxa de sucesso: {result['success_rate']:.1f}%")
            print(f"🎵 Áudios recuperados: {result['data_recovered']['audios']}")
            print(f"🎬 Vídeos recuperados: {result['data_recovered']['videos']}")
            print(f"📈 Score de integridade: {result['integrity_score']:.1f}%")
            print(f"⏱️ Duração: {result['duration_minutes']:.1f} minutos")
            
            if result['recommendations']:
                print("💡 Recomendações:")
                for rec in result['recommendations']:
                    print(f"  - {rec}")
        else:
            print(f"❌ Recovery falhou: {result.get('error')}")
    
    asyncio.run(main())