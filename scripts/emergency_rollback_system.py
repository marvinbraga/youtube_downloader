"""
Sistema de Rollback de Emergência para Migração Redis
Implementa recuperação completa em caso de falhas críticas

Autor: Claude Code Agent
Data: 2025-08-26
Versão: 1.0.0 - FASE 2 Emergency Recovery System
"""

import asyncio
import json
import os
import shutil
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

import redis.asyncio as redis
from loguru import logger

# Importar componentes do sistema
import sys
sys.path.append(str(Path(__file__).parent.parent))

from app.services.redis_connection import get_redis_client, init_redis
from scripts.migration_backup_system import MigrationBackupSystem


class EmergencyRollbackSystem:
    """
    Sistema de rollback de emergência com restauração completa
    Garante recuperação total em caso de falhas críticas
    """
    
    def __init__(self, 
                 backup_dir: str = "E:\\python\\youtube_downloader\\backups",
                 data_dir: str = "E:\\python\\youtube_downloader\\data"):
        
        self.backup_dir = Path(backup_dir)
        self.data_dir = Path(data_dir)
        self.redis_client: Optional[redis.Redis] = None
        
        # Estado do rollback
        self.rollback_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.rollback_state = {
            'rollback_id': self.rollback_id,
            'start_time': None,
            'end_time': None,
            'status': 'initialized',
            'phase': 'setup',
            'operations_performed': [],
            'errors_encountered': [],
            'recovery_success': False,
            'backup_restored': False,
            'redis_cleaned': False,
            'files_restored': False
        }
        
        # Configuração de logs de emergência
        self._setup_emergency_logging()
        
        logger.critical(f"🚨 Sistema de Rollback de Emergência ativado: {self.rollback_id}")
    
    def _setup_emergency_logging(self):
        """Configura logs de emergência com máxima prioridade"""
        log_dir = Path("E:\\python\\youtube_downloader\\logs\\emergency")
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Log principal de emergência
        emergency_log = log_dir / f"emergency_rollback_{self.rollback_id}.log"
        
        # Log com rotação para garantir espaço
        logger.add(
            str(emergency_log),
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | EMERGENCY | {message}",
            level="DEBUG",
            retention="90 days",
            compression="zip",
            backtrace=True,
            diagnose=True
        )
        
        # Log crítico separado
        critical_log = log_dir / f"critical_errors_{self.rollback_id}.log"
        logger.add(
            str(critical_log),
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | CRITICAL | {message}",
            level="CRITICAL",
            filter=lambda record: record["level"].name == "CRITICAL"
        )
        
        logger.critical(f"🚨 Logs de emergência: {emergency_log}")
    
    async def execute_emergency_rollback(self, 
                                       migration_session_id: Optional[str] = None,
                                       rollback_reason: str = "Unknown") -> Dict[str, Any]:
        """
        Executa rollback completo de emergência
        
        Args:
            migration_session_id: ID da sessão de migração para rollback específico
            rollback_reason: Motivo do rollback
            
        Returns:
            Resultado do rollback de emergência
        """
        logger.critical(f"🚨 INICIANDO ROLLBACK DE EMERGÊNCIA")
        logger.critical(f"🚨 Motivo: {rollback_reason}")
        
        self.rollback_state['start_time'] = time.time()
        self.rollback_state['status'] = 'in_progress'
        
        try:
            # FASE 1: Identificar backup para restauração
            backup_info = await self._identify_backup_for_rollback(migration_session_id)
            
            # FASE 2: Parar operações críticas (se necessário)
            await self._emergency_stop_operations()
            
            # FASE 3: Limpar Redis completamente
            await self._emergency_redis_cleanup()
            
            # FASE 4: Restaurar arquivos de backup
            await self._restore_backup_files(backup_info)
            
            # FASE 5: Verificar integridade da restauração
            await self._verify_rollback_integrity()
            
            # FASE 6: Finalização e relatório
            await self._finalize_rollback()
            
            self.rollback_state['status'] = 'completed'
            self.rollback_state['recovery_success'] = True
            self.rollback_state['end_time'] = time.time()
            
            rollback_report = await self._generate_rollback_report(rollback_reason)
            
            logger.critical("✅ ROLLBACK DE EMERGÊNCIA CONCLUÍDO COM SUCESSO")
            return rollback_report
            
        except Exception as e:
            logger.critical(f"❌ FALHA CRÍTICA NO ROLLBACK DE EMERGÊNCIA: {e}")
            
            self.rollback_state['status'] = 'failed'
            self.rollback_state['recovery_success'] = False
            self.rollback_state['end_time'] = time.time()
            self.rollback_state['errors_encountered'].append({
                'error': str(e),
                'timestamp': time.time(),
                'phase': self.rollback_state['phase']
            })
            
            # Tentar rollback do rollback (última tentativa)
            final_attempt = await self._last_resort_recovery()
            
            return {
                'success': False,
                'rollback_id': self.rollback_id,
                'error': str(e),
                'rollback_reason': rollback_reason,
                'rollback_state': self.rollback_state,
                'final_recovery_attempt': final_attempt,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
    
    async def _identify_backup_for_rollback(self, migration_session_id: Optional[str]) -> Dict[str, Any]:
        """Identifica o backup mais apropriado para rollback"""
        logger.critical("🔍 Identificando backup para rollback...")
        self.rollback_state['phase'] = 'backup_identification'
        
        backup_candidates = []
        
        # Procurar por backups de migração específicos
        if migration_session_id:
            specific_backup = self.backup_dir / f"migration_{migration_session_id}"
            if specific_backup.exists():
                backup_candidates.append({
                    'path': specific_backup,
                    'type': 'migration_specific',
                    'session_id': migration_session_id,
                    'priority': 1
                })
                logger.critical(f"📁 Backup específico encontrado: {specific_backup}")
        
        # Procurar por backups recentes
        for backup_item in self.backup_dir.glob("migration_*"):
            if backup_item.is_dir() and backup_item.name != f"migration_{migration_session_id}":
                try:
                    # Extrair timestamp do nome
                    timestamp_str = backup_item.name.replace("migration_", "")
                    backup_time = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    
                    backup_candidates.append({
                        'path': backup_item,
                        'type': 'migration_recent',
                        'timestamp': backup_time,
                        'priority': 2
                    })
                except ValueError:
                    continue
        
        # Procurar por backups comprimidos
        for zip_file in self.backup_dir.glob("backup_*.zip"):
            backup_candidates.append({
                'path': zip_file,
                'type': 'compressed',
                'priority': 3
            })
        
        if not backup_candidates:
            raise Exception("CRÍTICO: Nenhum backup encontrado para rollback!")
        
        # Ordenar por prioridade e recência
        backup_candidates.sort(key=lambda x: (x['priority'], x.get('timestamp', datetime.min)))
        selected_backup = backup_candidates[0]
        
        logger.critical(f"✅ Backup selecionado: {selected_backup['path']}")
        
        self.rollback_state['operations_performed'].append({
            'operation': 'backup_identified',
            'backup_path': str(selected_backup['path']),
            'backup_type': selected_backup['type'],
            'timestamp': time.time()
        })
        
        return selected_backup
    
    async def _emergency_stop_operations(self):
        """Para operações críticas em andamento"""
        logger.critical("⏹️ Parando operações críticas...")
        self.rollback_state['phase'] = 'stopping_operations'
        
        try:
            # Tentar conectar ao Redis para parar operações
            if not self.redis_client:
                await init_redis()
                self.redis_client = await get_redis_client()
            
            # Marcar sistema como em manutenção (se aplicável)
            await self.redis_client.set("youtube_downloader:maintenance_mode", "emergency_rollback", ex=3600)
            
            # Dar tempo para operações pendentes terminarem
            await asyncio.sleep(2)
            
            self.rollback_state['operations_performed'].append({
                'operation': 'operations_stopped',
                'timestamp': time.time()
            })
            
            logger.critical("✅ Operações críticas pausadas")
            
        except Exception as e:
            logger.warning(f"⚠️ Não foi possível parar operações graciosamente: {e}")
            # Continuar mesmo se não conseguir parar operações
    
    async def _emergency_redis_cleanup(self):
        """Limpa completamente dados Redis relacionados"""
        logger.critical("🧹 Limpando dados Redis...")
        self.rollback_state['phase'] = 'redis_cleanup'
        
        try:
            if not self.redis_client:
                await init_redis()
                self.redis_client = await get_redis_client()
            
            # Encontrar todas as chaves do projeto
            keys_to_delete = await self.redis_client.keys("youtube_downloader:*")
            
            if keys_to_delete:
                # Deletar em batches para não sobrecarregar
                batch_size = 100
                deleted_count = 0
                
                for i in range(0, len(keys_to_delete), batch_size):
                    batch = keys_to_delete[i:i + batch_size]
                    await self.redis_client.delete(*batch)
                    deleted_count += len(batch)
                    
                    logger.critical(f"🗑️ Deletadas {deleted_count}/{len(keys_to_delete)} chaves")
                
                self.rollback_state['redis_cleaned'] = True
                self.rollback_state['operations_performed'].append({
                    'operation': 'redis_cleanup',
                    'keys_deleted': deleted_count,
                    'timestamp': time.time()
                })
                
                logger.critical(f"✅ Redis limpo: {deleted_count} chaves removidas")
            else:
                logger.critical("ℹ️ Nenhuma chave Redis encontrada para remoção")
                self.rollback_state['redis_cleaned'] = True
                
        except Exception as e:
            logger.critical(f"❌ Falha na limpeza Redis: {e}")
            self.rollback_state['errors_encountered'].append({
                'error': f"Redis cleanup failed: {str(e)}",
                'timestamp': time.time(),
                'phase': 'redis_cleanup'
            })
            # Não falhar completamente - continuar com restauração de arquivos
    
    async def _restore_backup_files(self, backup_info: Dict[str, Any]):
        """Restaura arquivos do backup selecionado"""
        logger.critical("📁 Restaurando arquivos de backup...")
        self.rollback_state['phase'] = 'file_restoration'
        
        backup_path = Path(backup_info['path'])
        
        try:
            if backup_info['type'] == 'compressed':
                # Extrair backup comprimido
                extract_dir = self.backup_dir / f"extracted_{self.rollback_id}"
                extract_dir.mkdir(parents=True, exist_ok=True)
                
                with zipfile.ZipFile(backup_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
                
                backup_source = extract_dir
                logger.critical(f"📦 Backup extraído para: {extract_dir}")
            else:
                backup_source = backup_path
            
            # Restaurar dados JSON
            json_backup_dir = backup_source / 'json_data'
            if json_backup_dir.exists():
                for json_file in json_backup_dir.glob('*.json'):
                    target_file = self.data_dir / json_file.name
                    
                    # Fazer backup do arquivo atual (se existir)
                    if target_file.exists():
                        backup_current = target_file.with_suffix(f'.rollback_backup_{self.rollback_id}.json')
                        shutil.copy2(target_file, backup_current)
                        logger.critical(f"🔒 Backup atual salvo: {backup_current}")
                    
                    # Restaurar arquivo
                    shutil.copy2(json_file, target_file)
                    logger.critical(f"✅ Restaurado: {json_file.name}")
            
            # Restaurar configurações (se existirem no backup)
            config_backup_dir = backup_source / 'configurations'
            if config_backup_dir.exists():
                project_root = Path("E:\\python\\youtube_downloader")
                
                for config_file in config_backup_dir.glob('*'):
                    if config_file.is_file():
                        target_config = project_root / config_file.name
                        
                        # Backup do arquivo atual
                        if target_config.exists():
                            backup_current = target_config.with_suffix(f'.rollback_backup_{self.rollback_id}')
                            shutil.copy2(target_config, backup_current)
                        
                        # Restaurar
                        shutil.copy2(config_file, target_config)
                        logger.critical(f"⚙️ Configuração restaurada: {config_file.name}")
            
            self.rollback_state['files_restored'] = True
            self.rollback_state['operations_performed'].append({
                'operation': 'files_restored',
                'backup_source': str(backup_source),
                'timestamp': time.time()
            })
            
            logger.critical("✅ Arquivos restaurados do backup")
            
        except Exception as e:
            logger.critical(f"❌ Falha na restauração de arquivos: {e}")
            self.rollback_state['errors_encountered'].append({
                'error': f"File restoration failed: {str(e)}",
                'timestamp': time.time(),
                'phase': 'file_restoration'
            })
            raise
    
    async def _verify_rollback_integrity(self):
        """Verifica integridade do rollback realizado"""
        logger.critical("🔍 Verificando integridade do rollback...")
        self.rollback_state['phase'] = 'integrity_verification'
        
        integrity_checks = []
        
        try:
            # Verificar se arquivos JSON existem
            audios_file = self.data_dir / 'audios.json'
            videos_file = self.data_dir / 'videos.json'
            
            if audios_file.exists():
                # Verificar se JSON é válido
                with open(audios_file, 'r', encoding='utf-8') as f:
                    audios_data = json.load(f)
                
                audios_count = len(audios_data.get('audios', []))
                integrity_checks.append({
                    'check': 'audios_json_restored',
                    'status': 'pass',
                    'details': f'{audios_count} áudios encontrados'
                })
                
                logger.critical(f"✅ audios.json: {audios_count} registros")
            else:
                integrity_checks.append({
                    'check': 'audios_json_restored',
                    'status': 'fail',
                    'details': 'Arquivo não encontrado'
                })
            
            if videos_file.exists():
                with open(videos_file, 'r', encoding='utf-8') as f:
                    videos_data = json.load(f)
                
                videos_count = len(videos_data.get('videos', []))
                integrity_checks.append({
                    'check': 'videos_json_restored',
                    'status': 'pass',
                    'details': f'{videos_count} vídeos encontrados'
                })
                
                logger.critical(f"✅ videos.json: {videos_count} registros")
            else:
                integrity_checks.append({
                    'check': 'videos_json_restored',
                    'status': 'fail',
                    'details': 'Arquivo não encontrado'
                })
            
            # Verificar se Redis foi limpo
            if self.redis_client:
                remaining_keys = await self.redis_client.keys("youtube_downloader:*")
                if len(remaining_keys) == 0:
                    integrity_checks.append({
                        'check': 'redis_cleaned',
                        'status': 'pass',
                        'details': 'Redis completamente limpo'
                    })
                    logger.critical("✅ Redis limpo")
                else:
                    integrity_checks.append({
                        'check': 'redis_cleaned',
                        'status': 'warning',
                        'details': f'{len(remaining_keys)} chaves ainda presentes'
                    })
                    logger.warning(f"⚠️ {len(remaining_keys)} chaves ainda no Redis")
            
            # Calcular score de integridade
            passed_checks = sum(1 for check in integrity_checks if check['status'] == 'pass')
            total_checks = len(integrity_checks)
            integrity_score = (passed_checks / total_checks) * 100 if total_checks > 0 else 0
            
            self.rollback_state['operations_performed'].append({
                'operation': 'integrity_verification',
                'integrity_score': integrity_score,
                'checks': integrity_checks,
                'timestamp': time.time()
            })
            
            logger.critical(f"📊 Integridade do rollback: {integrity_score:.1f}% ({passed_checks}/{total_checks})")
            
            if integrity_score < 80:
                raise Exception(f"Integridade do rollback abaixo do aceitável: {integrity_score:.1f}%")
            
        except Exception as e:
            logger.critical(f"❌ Falha na verificação de integridade: {e}")
            self.rollback_state['errors_encountered'].append({
                'error': f"Integrity verification failed: {str(e)}",
                'timestamp': time.time(),
                'phase': 'integrity_verification'
            })
            raise
    
    async def _finalize_rollback(self):
        """Finaliza o processo de rollback"""
        logger.critical("🏁 Finalizando rollback...")
        self.rollback_state['phase'] = 'finalization'
        
        try:
            # Remover modo de manutenção
            if self.redis_client:
                await self.redis_client.delete("youtube_downloader:maintenance_mode")
            
            # Criar marcador de rollback concluído
            rollback_marker = self.data_dir / f'.rollback_completed_{self.rollback_id}'
            rollback_marker.write_text(
                json.dumps({
                    'rollback_id': self.rollback_id,
                    'completion_time': datetime.now(timezone.utc).isoformat(),
                    'status': 'completed'
                }, indent=2)
            )
            
            self.rollback_state['operations_performed'].append({
                'operation': 'rollback_finalized',
                'timestamp': time.time()
            })
            
            logger.critical("✅ Rollback finalizado")
            
        except Exception as e:
            logger.warning(f"⚠️ Aviso na finalização: {e}")
            # Não falhar na finalização
    
    async def _last_resort_recovery(self) -> Dict[str, Any]:
        """Última tentativa de recovery se rollback principal falhar"""
        logger.critical("🆘 EXECUTANDO RECOVERY DE ÚLTIMA INSTÂNCIA...")
        
        last_resort_operations = []
        
        try:
            # 1. Tentar encontrar qualquer backup disponível
            available_backups = list(self.backup_dir.glob("*"))
            if available_backups:
                logger.critical(f"📁 {len(available_backups)} backups encontrados")
                
                # Pegar o mais recente
                latest_backup = max(available_backups, key=lambda p: p.stat().st_mtime)
                logger.critical(f"📁 Usando backup mais recente: {latest_backup}")
                
                # Tentar restauração básica
                if latest_backup.name.endswith('.zip'):
                    extract_dir = self.backup_dir / f"emergency_extract_{self.rollback_id}"
                    extract_dir.mkdir(parents=True, exist_ok=True)
                    
                    with zipfile.ZipFile(latest_backup, 'r') as zip_ref:
                        zip_ref.extractall(extract_dir)
                    
                    # Procurar por arquivos JSON
                    for json_file in extract_dir.rglob('*.json'):
                        if json_file.name in ['audios.json', 'videos.json']:
                            target = self.data_dir / json_file.name
                            shutil.copy2(json_file, target)
                            last_resort_operations.append(f"Restored {json_file.name}")
                            logger.critical(f"🔄 {json_file.name} restaurado")
                
                elif latest_backup.is_dir():
                    # Diretório de backup
                    for json_file in latest_backup.rglob('*.json'):
                        if json_file.name in ['audios.json', 'videos.json']:
                            target = self.data_dir / json_file.name
                            shutil.copy2(json_file, target)
                            last_resort_operations.append(f"Restored {json_file.name}")
                            logger.critical(f"🔄 {json_file.name} restaurado")
            
            # 2. Tentar limpar Redis novamente
            try:
                if self.redis_client:
                    keys = await self.redis_client.keys("youtube_downloader:*")
                    if keys:
                        await self.redis_client.delete(*keys)
                        last_resort_operations.append(f"Deleted {len(keys)} Redis keys")
                        logger.critical(f"🧹 {len(keys)} chaves Redis removidas")
            except:
                pass
            
            # 3. Verificar estado final
            audios_exists = (self.data_dir / 'audios.json').exists()
            videos_exists = (self.data_dir / 'videos.json').exists()
            
            success = audios_exists or videos_exists
            
            return {
                'success': success,
                'operations_performed': last_resort_operations,
                'files_recovered': {
                    'audios_json': audios_exists,
                    'videos_json': videos_exists
                },
                'timestamp': time.time()
            }
            
        except Exception as e:
            logger.critical(f"🆘 FALHA TOTAL NO RECOVERY: {e}")
            return {
                'success': False,
                'error': str(e),
                'operations_performed': last_resort_operations,
                'timestamp': time.time()
            }
    
    async def _generate_rollback_report(self, rollback_reason: str) -> Dict[str, Any]:
        """Gera relatório completo do rollback"""
        duration = self.rollback_state['end_time'] - self.rollback_state['start_time']
        
        report = {
            'success': self.rollback_state['recovery_success'],
            'rollback_id': self.rollback_id,
            'rollback_reason': rollback_reason,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'duration_seconds': round(duration, 2),
            'duration_minutes': round(duration / 60, 2),
            'rollback_state': self.rollback_state,
            'summary': {
                'redis_cleaned': self.rollback_state['redis_cleaned'],
                'files_restored': self.rollback_state['files_restored'],
                'operations_count': len(self.rollback_state['operations_performed']),
                'errors_count': len(self.rollback_state['errors_encountered'])
            },
            'operations_performed': self.rollback_state['operations_performed'],
            'errors_encountered': self.rollback_state['errors_encountered']
        }
        
        # Salvar relatório de rollback
        report_dir = Path("E:\\python\\youtube_downloader\\reports\\rollback")
        report_dir.mkdir(parents=True, exist_ok=True)
        
        report_file = report_dir / f"emergency_rollback_{self.rollback_id}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        # Também salvar cópia na raiz para fácil acesso
        emergency_report = Path("E:\\python\\youtube_downloader") / f"EMERGENCY_ROLLBACK_REPORT_{self.rollback_id}.json"
        with open(emergency_report, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        logger.critical(f"📊 Relatório de rollback salvo: {report_file}")
        logger.critical(f"📊 Relatório de emergência: {emergency_report}")
        
        return report


# Funções utilitárias para uso direto
async def execute_emergency_rollback(migration_session_id: Optional[str] = None,
                                   reason: str = "Manual emergency rollback") -> Dict[str, Any]:
    """
    Executa rollback de emergência
    
    Args:
        migration_session_id: ID da migração para rollback específico
        reason: Motivo do rollback
        
    Returns:
        Resultado do rollback
    """
    rollback_system = EmergencyRollbackSystem()
    return await rollback_system.execute_emergency_rollback(migration_session_id, reason)


async def quick_redis_cleanup() -> Dict[str, Any]:
    """
    Limpeza rápida apenas do Redis
    
    Returns:
        Resultado da limpeza
    """
    try:
        await init_redis()
        redis_client = await get_redis_client()
        
        keys = await redis_client.keys("youtube_downloader:*")
        if keys:
            await redis_client.delete(*keys)
            
        return {
            'success': True,
            'keys_deleted': len(keys),
            'timestamp': time.time()
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'timestamp': time.time()
        }


if __name__ == "__main__":
    # Exemplo de uso de emergência
    async def main():
        # Simulação de rollback de emergência
        result = await execute_emergency_rollback(
            migration_session_id=None,  # Usar backup mais recente
            reason="Teste de sistema de rollback"
        )
        
        if result['success']:
            print("✅ Rollback de emergência concluído com sucesso!")
            print(f"⏱️ Duração: {result['duration_minutes']:.1f} minutos")
            print(f"🔧 Operações: {result['summary']['operations_count']}")
            
            if result['summary']['errors_count'] > 0:
                print(f"⚠️ Erros encontrados: {result['summary']['errors_count']}")
        else:
            print(f"❌ Rollback de emergência falhou: {result.get('error')}")
            
            if 'final_recovery_attempt' in result:
                recovery = result['final_recovery_attempt']
                if recovery['success']:
                    print("🆘 Recovery de última instância teve sucesso parcial")
                else:
                    print("🆘 Recovery de última instância também falhou")
    
    asyncio.run(main())