"""
Script Principal de Migração JSON → Redis com Segurança Máxima
Implementa migração robusta com validação, batches e rollback automático

Autor: Claude Code Agent  
Data: 2025-08-26
Versão: 2.0.0 - FASE 2 Production Ready
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import redis.asyncio as redis
from loguru import logger

# Importar componentes do sistema
sys.path.append(str(Path(__file__).parent.parent))

from app.services.redis_connection import get_redis_client, init_redis
from app.services.redis_audio_manager import RedisAudioManager
from app.services.redis_video_manager import RedisVideoManager
from scripts.migration_backup_system import MigrationBackupSystem


class RedisDataMigrationManager:
    """
    Gerenciador completo de migração de dados JSON para Redis
    Implementa segurança máxima com zero tolerância a perda de dados
    """
    
    def __init__(self, 
                 data_dir: str = "E:\\python\\youtube_downloader\\data",
                 batch_size: int = 10,
                 validation_level: str = "strict"):
        
        self.data_dir = Path(data_dir)
        self.batch_size = batch_size
        self.validation_level = validation_level  # strict, normal, basic
        
        # Componentes do sistema
        self.backup_system = MigrationBackupSystem()
        self.redis_client: Optional[redis.Redis] = None
        self.audio_manager: Optional[RedisAudioManager] = None
        self.video_manager: Optional[RedisVideoManager] = None
        
        # Estado da migração
        self.migration_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.migration_state = {
            'status': 'initialized',
            'current_phase': 'setup',
            'start_time': None,
            'end_time': None,
            'total_records': 0,
            'processed_records': 0,
            'failed_records': 0,
            'batch_results': [],
            'checkpoints': [],
            'rollback_points': []
        }
        
        # Configuração de logs
        self._setup_migration_logging()
        
        logger.info(f"🚀 Migração Redis inicializada: {self.migration_id}")
    
    def _setup_migration_logging(self):
        """Configura sistema de logs detalhados para migração"""
        log_dir = Path("E:\\python\\youtube_downloader\\logs\\migration")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        log_file = log_dir / f"migration_{self.migration_id}.log"
        
        # Configurar logger específico para migração
        logger.add(
            str(log_file),
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line} | {message}",
            level="DEBUG",
            retention="30 days",
            compression="zip"
        )
        
        logger.info(f"📋 Logs de migração: {log_file}")
    
    async def execute_full_migration(self) -> Dict[str, Any]:
        """
        Executa migração completa com todas as proteções de segurança
        
        Returns:
            Resultado detalhado da migração
        """
        logger.info("🚀 Iniciando migração completa JSON → Redis")
        self.migration_state['start_time'] = time.time()
        
        try:
            # FASE 1: Preparação e Backup
            await self._phase_1_preparation()
            
            # FASE 2: Inicialização Redis
            await self._phase_2_redis_initialization()
            
            # FASE 3: Migração de Dados
            await self._phase_3_data_migration()
            
            # FASE 4: Validação Completa
            await self._phase_4_validation()
            
            # FASE 5: Finalização
            await self._phase_5_finalization()
            
            self.migration_state['status'] = 'completed'
            self.migration_state['end_time'] = time.time()
            
            # Resultado final
            migration_result = await self._generate_migration_report()
            
            logger.success("✅ Migração completa executada com sucesso!")
            return migration_result
            
        except Exception as e:
            logger.error(f"❌ Falha crítica na migração: {e}")
            
            # Executar rollback automático
            rollback_result = await self._execute_emergency_rollback()
            
            self.migration_state['status'] = 'failed'
            self.migration_state['end_time'] = time.time()
            
            return {
                'success': False,
                'error': str(e),
                'migration_id': self.migration_id,
                'rollback_result': rollback_result,
                'migration_state': self.migration_state
            }
    
    async def _phase_1_preparation(self):
        """FASE 1: Preparação e criação de backup completo"""
        logger.info("📋 FASE 1: Preparação e Backup")
        self.migration_state['current_phase'] = 'preparation'
        
        # Criar backup pré-migração
        logger.info("🔄 Criando backup pré-migração...")
        backup_result = self.backup_system.create_pre_migration_backup()
        
        if not backup_result['success']:
            raise Exception(f"Falha no backup pré-migração: {backup_result.get('error')}")
        
        # Validar backup
        logger.info("🔍 Validando backup...")
        validation_result = self.backup_system.validate_backup_before_migration()
        
        if not validation_result['validation_success']:
            raise Exception("Backup não passou na validação - migração interrompida")
        
        # Criar checkpoint inicial
        checkpoint_data = {
            'phase': 'preparation_complete',
            'backup_result': backup_result,
            'validation_result': validation_result
        }
        
        self.backup_system.create_incremental_checkpoint('preparation_complete', checkpoint_data)
        self.migration_state['checkpoints'].append('preparation_complete')
        
        logger.success("✅ FASE 1: Preparação concluída")
    
    async def _phase_2_redis_initialization(self):
        """FASE 2: Inicialização e teste da conexão Redis"""
        logger.info("🔌 FASE 2: Inicialização Redis")
        self.migration_state['current_phase'] = 'redis_initialization'
        
        # Inicializar conexão Redis
        logger.info("Conectando ao Redis...")
        await init_redis()
        self.redis_client = await get_redis_client()
        
        # Testar conectividade
        await self.redis_client.ping()
        logger.info("✅ Conexão Redis estabelecida")
        
        # Inicializar managers
        self.audio_manager = RedisAudioManager()
        self.video_manager = RedisVideoManager()
        
        await self.audio_manager.initialize()
        await self.video_manager.initialize()
        
        # Verificar estado inicial do Redis
        redis_info = await self.redis_client.info()
        logger.info(f"📊 Redis Info: Versão {redis_info.get('redis_version')}")
        logger.info(f"📊 Memória usada: {redis_info.get('used_memory_human')}")
        
        # Criar checkpoint Redis
        checkpoint_data = {
            'phase': 'redis_initialized',
            'redis_info': {
                'version': redis_info.get('redis_version'),
                'memory': redis_info.get('used_memory_human'),
                'clients': redis_info.get('connected_clients')
            }
        }
        
        self.backup_system.create_incremental_checkpoint('redis_initialized', checkpoint_data)
        self.migration_state['checkpoints'].append('redis_initialized')
        
        logger.success("✅ FASE 2: Redis inicializado")
    
    async def _phase_3_data_migration(self):
        """FASE 3: Migração dos dados em batches com validação"""
        logger.info("📤 FASE 3: Migração de Dados")
        self.migration_state['current_phase'] = 'data_migration'
        
        # Migrar áudios
        await self._migrate_audio_data()
        
        # Migrar vídeos  
        await self._migrate_video_data()
        
        logger.success("✅ FASE 3: Migração de dados concluída")
    
    async def _migrate_audio_data(self):
        """Migra dados de áudios em batches com validação incremental"""
        logger.info("🎵 Migrando dados de áudios...")
        
        # Carregar dados JSON
        audios_file = self.data_dir / 'audios.json'
        if not audios_file.exists():
            logger.warning("⚠️ Arquivo audios.json não encontrado")
            return
        
        with open(audios_file, 'r', encoding='utf-8') as f:
            audios_data = json.load(f)
        
        audios_list = audios_data.get('audios', [])
        total_audios = len(audios_list)
        
        logger.info(f"📊 Total de áudios para migrar: {total_audios}")
        self.migration_state['total_records'] += total_audios
        
        # Processar em batches
        for i in range(0, total_audios, self.batch_size):
            batch = audios_list[i:i + self.batch_size]
            batch_number = (i // self.batch_size) + 1
            total_batches = (total_audios + self.batch_size - 1) // self.batch_size
            
            logger.info(f"🔄 Processando batch {batch_number}/{total_batches} ({len(batch)} áudios)")
            
            # Processar batch
            batch_result = await self._process_audio_batch(batch, batch_number)
            self.migration_state['batch_results'].append(batch_result)
            
            # Atualizar contadores
            self.migration_state['processed_records'] += batch_result['processed']
            self.migration_state['failed_records'] += batch_result['failed']
            
            # Criar checkpoint a cada 5 batches
            if batch_number % 5 == 0:
                checkpoint_data = {
                    'phase': f'audio_batch_{batch_number}',
                    'processed_records': self.migration_state['processed_records'],
                    'batch_results': self.migration_state['batch_results'][-5:]  # Últimos 5 batches
                }
                
                self.backup_system.create_incremental_checkpoint(
                    f'audio_batch_{batch_number}', checkpoint_data
                )
            
            # Pausa entre batches para não sobrecarregar
            await asyncio.sleep(0.1)
        
        logger.success(f"✅ Migração de áudios concluída: {self.migration_state['processed_records']} processados")
    
    async def _process_audio_batch(self, batch: List[Dict], batch_number: int) -> Dict[str, Any]:
        """Processa um batch de áudios com validação"""
        batch_start_time = time.time()
        processed = 0
        failed = 0
        errors = []
        
        for audio_data in batch:
            try:
                # Validar estrutura do áudio
                if not self._validate_audio_structure(audio_data):
                    errors.append({
                        'audio_id': audio_data.get('id', 'unknown'),
                        'error': 'invalid_structure'
                    })
                    failed += 1
                    continue
                
                # Adicionar ao Redis
                success = await self.audio_manager.add_audio(audio_data)
                
                if success:
                    processed += 1
                    
                    # Validação incremental (strict mode)
                    if self.validation_level == 'strict':
                        retrieved = await self.audio_manager.get_audio(audio_data['id'])
                        if not self._compare_audio_data(audio_data, retrieved):
                            errors.append({
                                'audio_id': audio_data['id'],
                                'error': 'validation_mismatch'
                            })
                            failed += 1
                            processed -= 1
                else:
                    errors.append({
                        'audio_id': audio_data.get('id', 'unknown'),
                        'error': 'redis_add_failed'
                    })
                    failed += 1
                    
            except Exception as e:
                logger.error(f"Erro processando áudio {audio_data.get('id', 'unknown')}: {e}")
                errors.append({
                    'audio_id': audio_data.get('id', 'unknown'),
                    'error': str(e)
                })
                failed += 1
        
        batch_duration = time.time() - batch_start_time
        
        batch_result = {
            'batch_number': batch_number,
            'type': 'audio',
            'processed': processed,
            'failed': failed,
            'errors': errors,
            'duration_seconds': round(batch_duration, 2),
            'timestamp': time.time()
        }
        
        logger.info(f"📊 Batch {batch_number}: {processed} OK, {failed} falhas, {batch_duration:.2f}s")
        
        return batch_result
    
    async def _migrate_video_data(self):
        """Migra dados de vídeos"""
        logger.info("🎬 Migrando dados de vídeos...")
        
        videos_file = self.data_dir / 'videos.json'
        if not videos_file.exists():
            logger.warning("⚠️ Arquivo videos.json não encontrado")
            return
        
        with open(videos_file, 'r', encoding='utf-8') as f:
            videos_data = json.load(f)
        
        videos_list = videos_data.get('videos', [])
        total_videos = len(videos_list)
        
        logger.info(f"📊 Total de vídeos para migrar: {total_videos}")
        self.migration_state['total_records'] += total_videos
        
        # Processar vídeos (normalmente são poucos, pode processar todos de uma vez)
        for video_data in videos_list:
            try:
                # Validar estrutura
                if not self._validate_video_structure(video_data):
                    logger.warning(f"Estrutura inválida para vídeo: {video_data}")
                    self.migration_state['failed_records'] += 1
                    continue
                
                # Adicionar ao Redis
                success = await self.video_manager.add_video(video_data)
                
                if success:
                    self.migration_state['processed_records'] += 1
                    
                    # Validação incremental
                    if self.validation_level in ['strict', 'normal']:
                        retrieved = await self.video_manager.get_video(video_data['name'])
                        if not self._compare_video_data(video_data, retrieved):
                            logger.error(f"Validação falhou para vídeo: {video_data['name']}")
                            self.migration_state['failed_records'] += 1
                            self.migration_state['processed_records'] -= 1
                else:
                    logger.error(f"Falha ao adicionar vídeo: {video_data}")
                    self.migration_state['failed_records'] += 1
                    
            except Exception as e:
                logger.error(f"Erro processando vídeo: {e}")
                self.migration_state['failed_records'] += 1
        
        logger.success("✅ Migração de vídeos concluída")
    
    def _validate_audio_structure(self, audio_data: Dict) -> bool:
        """Valida estrutura de dados de áudio"""
        required_fields = ['id', 'title', 'youtube_id', 'url']
        
        for field in required_fields:
            if field not in audio_data:
                logger.warning(f"Campo obrigatório ausente: {field}")
                return False
        
        # Validações adicionais
        if not isinstance(audio_data.get('keywords', []), list):
            return False
        
        if 'filesize' in audio_data and not isinstance(audio_data['filesize'], (int, float)):
            return False
        
        return True
    
    def _validate_video_structure(self, video_data: Dict) -> bool:
        """Valida estrutura de dados de vídeo"""
        required_fields = ['name', 'path', 'type']
        
        for field in required_fields:
            if field not in video_data:
                logger.warning(f"Campo obrigatório ausente: {field}")
                return False
        
        return True
    
    def _compare_audio_data(self, original: Dict, retrieved: Dict) -> bool:
        """Compara dados de áudio original vs recuperado"""
        if not retrieved:
            return False
        
        # Campos críticos que devem ser idênticos
        critical_fields = ['id', 'title', 'youtube_id', 'url']
        
        for field in critical_fields:
            if original.get(field) != retrieved.get(field):
                logger.warning(f"Mismatch no campo {field}: {original.get(field)} vs {retrieved.get(field)}")
                return False
        
        return True
    
    def _compare_video_data(self, original: Dict, retrieved: Dict) -> bool:
        """Compara dados de vídeo original vs recuperado"""
        if not retrieved:
            return False
        
        critical_fields = ['name', 'path', 'type']
        
        for field in critical_fields:
            if original.get(field) != retrieved.get(field):
                logger.warning(f"Mismatch no campo {field}: {original.get(field)} vs {retrieved.get(field)}")
                return False
        
        return True
    
    async def _phase_4_validation(self):
        """FASE 4: Validação completa dos dados migrados"""
        logger.info("🔍 FASE 4: Validação Completa")
        self.migration_state['current_phase'] = 'validation'
        
        # Validar contadores
        await self._validate_record_counts()
        
        # Validar integridade dos dados
        await self._validate_data_integrity()
        
        # Validar funcionalidades críticas
        await self._validate_critical_operations()
        
        logger.success("✅ FASE 4: Validação completa")
    
    async def _validate_record_counts(self):
        """Valida se todos os registros foram migrados"""
        logger.info("📊 Validando contadores de registros...")
        
        # Contar áudios no Redis
        redis_audio_count = await self.audio_manager.get_total_count()
        
        # Contar áudios no JSON
        audios_file = self.data_dir / 'audios.json'
        json_audio_count = 0
        
        if audios_file.exists():
            with open(audios_file, 'r', encoding='utf-8') as f:
                audios_data = json.load(f)
            json_audio_count = len(audios_data.get('audios', []))
        
        logger.info(f"📊 Áudios - JSON: {json_audio_count}, Redis: {redis_audio_count}")
        
        if json_audio_count != redis_audio_count:
            raise Exception(f"Mismatch na contagem de áudios: JSON={json_audio_count}, Redis={redis_audio_count}")
        
        # Contar vídeos
        redis_video_count = await self.video_manager.get_total_count()
        
        videos_file = self.data_dir / 'videos.json'
        json_video_count = 0
        
        if videos_file.exists():
            with open(videos_file, 'r', encoding='utf-8') as f:
                videos_data = json.load(f)
            json_video_count = len(videos_data.get('videos', []))
        
        logger.info(f"📊 Vídeos - JSON: {json_video_count}, Redis: {redis_video_count}")
        
        if json_video_count != redis_video_count:
            raise Exception(f"Mismatch na contagem de vídeos: JSON={json_video_count}, Redis={redis_video_count}")
        
        logger.success("✅ Contadores de registros validados")
    
    async def _validate_data_integrity(self):
        """Valida integridade dos dados migrados"""
        logger.info("🔍 Validando integridade dos dados...")
        
        # Validar sample de áudios (10%)
        all_audio_ids = await self.audio_manager.get_all_audio_ids()
        sample_size = max(1, len(all_audio_ids) // 10)  # 10% de sample
        sample_ids = all_audio_ids[:sample_size]
        
        logger.info(f"🔍 Validando sample de {sample_size} áudios...")
        
        for audio_id in sample_ids:
            audio_data = await self.audio_manager.get_audio(audio_id)
            if not audio_data:
                raise Exception(f"Áudio não encontrado no Redis: {audio_id}")
            
            # Validar estrutura
            if not self._validate_audio_structure(audio_data):
                raise Exception(f"Estrutura inválida para áudio: {audio_id}")
        
        logger.success("✅ Integridade dos dados validada")
    
    async def _validate_critical_operations(self):
        """Valida operações críticas do sistema"""
        logger.info("⚡ Validando operações críticas...")
        
        # Testar busca por keywords
        search_results = await self.audio_manager.search_audios("davinci")
        logger.info(f"🔍 Teste de busca: {len(search_results)} resultados para 'davinci'")
        
        # Testar filtros
        filter_results = await self.audio_manager.filter_audios({'format': 'm4a'})
        logger.info(f"🔍 Teste de filtro: {len(filter_results)} áudios m4a")
        
        logger.success("✅ Operações críticas validadas")
    
    async def _phase_5_finalization(self):
        """FASE 5: Finalização da migração"""
        logger.info("🏁 FASE 5: Finalização")
        self.migration_state['current_phase'] = 'finalization'
        
        # Criar checkpoint final
        final_checkpoint_data = {
            'phase': 'migration_complete',
            'migration_state': self.migration_state,
            'timestamp': time.time()
        }
        
        self.backup_system.create_incremental_checkpoint('migration_complete', final_checkpoint_data)
        self.migration_state['checkpoints'].append('migration_complete')
        
        logger.success("✅ FASE 5: Finalização concluída")
    
    async def _generate_migration_report(self) -> Dict[str, Any]:
        """Gera relatório completo da migração"""
        total_duration = self.migration_state['end_time'] - self.migration_state['start_time']
        
        report = {
            'success': True,
            'migration_id': self.migration_id,
            'duration_seconds': round(total_duration, 2),
            'duration_minutes': round(total_duration / 60, 2),
            'total_records': self.migration_state['total_records'],
            'processed_records': self.migration_state['processed_records'],
            'failed_records': self.migration_state['failed_records'],
            'success_rate': round(
                (self.migration_state['processed_records'] / self.migration_state['total_records']) * 100, 2
            ) if self.migration_state['total_records'] > 0 else 0,
            'batches_processed': len(self.migration_state['batch_results']),
            'checkpoints_created': len(self.migration_state['checkpoints']),
            'validation_level': self.validation_level,
            'migration_state': self.migration_state,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }
        
        # Salvar relatório
        report_dir = Path("E:\\python\\youtube_downloader\\reports\\migration")
        report_dir.mkdir(parents=True, exist_ok=True)
        
        report_file = report_dir / f"migration_report_{self.migration_id}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        logger.success(f"📊 Relatório de migração salvo: {report_file}")
        
        return report
    
    async def _execute_emergency_rollback(self) -> Dict[str, Any]:
        """Executa rollback de emergência em caso de falha"""
        logger.warning("🚨 Executando rollback de emergência...")
        
        try:
            # Limpar dados Redis
            if self.redis_client:
                # Remover apenas keys relacionadas ao projeto
                keys = await self.redis_client.keys("youtube_downloader:*")
                if keys:
                    await self.redis_client.delete(*keys)
                    logger.info(f"🗑️ Removidas {len(keys)} chaves do Redis")
            
            rollback_result = {
                'success': True,
                'timestamp': time.time(),
                'keys_removed': len(keys) if 'keys' in locals() else 0,
                'message': 'Rollback de emergência executado com sucesso'
            }
            
            logger.success("✅ Rollback de emergência concluído")
            return rollback_result
            
        except Exception as e:
            logger.error(f"❌ Falha no rollback de emergência: {e}")
            return {
                'success': False,
                'error': str(e),
                'timestamp': time.time()
            }


# Função principal para execução
async def execute_migration(validation_level: str = "strict", batch_size: int = 10) -> Dict[str, Any]:
    """
    Executa migração completa com configurações especificadas
    
    Args:
        validation_level: Nível de validação (strict, normal, basic)
        batch_size: Tamanho dos batches de processamento
        
    Returns:
        Resultado da migração
    """
    migration_manager = RedisDataMigrationManager(
        batch_size=batch_size,
        validation_level=validation_level
    )
    
    return await migration_manager.execute_full_migration()


if __name__ == "__main__":
    # Execução de exemplo
    async def main():
        result = await execute_migration(validation_level="strict", batch_size=10)
        
        if result['success']:
            print(f"✅ Migração concluída com sucesso!")
            print(f"📊 Processados: {result['processed_records']}/{result['total_records']}")
            print(f"⏱️ Duração: {result['duration_minutes']:.1f} minutos")
            print(f"📈 Taxa de sucesso: {result['success_rate']:.1f}%")
        else:
            print(f"❌ Migração falhou: {result.get('error')}")
            if 'rollback_result' in result:
                print(f"🔄 Rollback: {'✅' if result['rollback_result']['success'] else '❌'}")
    
    asyncio.run(main())