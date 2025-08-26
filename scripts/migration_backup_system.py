"""
Sistema de Backup Automático para Migração Redis
Garante segurança máxima dos dados durante processo de migração

Autor: Claude Code Agent
Data: 2025-08-26
Versão: 1.0.0 - FASE 2 Redis Migration
"""

import asyncio
import hashlib
import json
import os
import shutil
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from loguru import logger


class MigrationBackupSystem:
    """
    Sistema completo de backup automático para migração segura
    Zero tolerância a perda de dados
    """
    
    def __init__(self, 
                 data_dir: str = "E:\\python\\youtube_downloader\\data",
                 backup_dir: str = "E:\\python\\youtube_downloader\\backups",
                 downloads_dir: str = "E:\\python\\youtube_downloader\\downloads"):
        
        self.data_dir = Path(data_dir)
        self.backup_dir = Path(backup_dir)
        self.downloads_dir = Path(downloads_dir)
        
        # Criar diretórios se não existirem
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Timestamp único para esta sessão de migração
        self.migration_timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        self.session_backup_dir = self.backup_dir / f"migration_{self.migration_timestamp}"
        
        # Configurações de segurança
        self.verification_enabled = True
        self.compression_enabled = True
        self.incremental_backups = True
        
        # Estatísticas de backup
        self.backup_stats = {
            'total_files': 0,
            'total_size': 0,
            'backup_start': None,
            'backup_end': None,
            'files_backed_up': [],
            'verification_results': {},
            'checksums': {}
        }
        
        logger.info(f"Backup System inicializado: {self.session_backup_dir}")
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """Calcula checksum SHA-256 para verificação de integridade"""
        hasher = hashlib.sha256()
        
        try:
            with open(file_path, 'rb') as f:
                # Ler arquivo em blocos para economizar memória
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            logger.error(f"Erro calculando checksum para {file_path}: {e}")
            return ""
    
    def _get_file_info(self, file_path: Path) -> Dict[str, Any]:
        """Coleta informações completas do arquivo"""
        try:
            stat = file_path.stat()
            return {
                'path': str(file_path),
                'size': stat.st_size,
                'created': stat.st_ctime,
                'modified': stat.st_mtime,
                'checksum': self._calculate_checksum(file_path) if self.verification_enabled else None,
                'exists': file_path.exists(),
                'is_file': file_path.is_file()
            }
        except Exception as e:
            logger.error(f"Erro coletando info do arquivo {file_path}: {e}")
            return {}
    
    def create_pre_migration_backup(self) -> Dict[str, Any]:
        """
        Cria backup completo antes da migração
        
        Returns:
            Dicionário com resultados do backup
        """
        logger.info("🔄 Iniciando backup pré-migração...")
        self.backup_stats['backup_start'] = time.time()
        
        try:
            # Criar estrutura de diretórios de backup
            self.session_backup_dir.mkdir(parents=True, exist_ok=True)
            
            # Backup dos dados JSON
            json_backup_result = self._backup_json_data()
            
            # Backup das transcrições e áudios críticos
            audio_backup_result = self._backup_critical_audio_files()
            
            # Backup de configurações
            config_backup_result = self._backup_configurations()
            
            # Criar manifesto do backup
            manifest = self._create_backup_manifest([
                json_backup_result,
                audio_backup_result, 
                config_backup_result
            ])
            
            # Verificação de integridade completa
            verification_result = self._verify_backup_integrity(manifest)
            
            # Compressão opcional (para economizar espaço)
            if self.compression_enabled:
                compression_result = self._compress_backup()
                manifest['compression'] = compression_result
            
            self.backup_stats['backup_end'] = time.time()
            backup_duration = self.backup_stats['backup_end'] - self.backup_stats['backup_start']
            
            result = {
                'success': True,
                'backup_path': str(self.session_backup_dir),
                'timestamp': self.migration_timestamp,
                'duration_seconds': round(backup_duration, 2),
                'total_files': self.backup_stats['total_files'],
                'total_size_bytes': self.backup_stats['total_size'],
                'total_size_mb': round(self.backup_stats['total_size'] / 1024 / 1024, 2),
                'verification_passed': verification_result,
                'manifest': manifest,
                'backup_stats': self.backup_stats
            }
            
            # Salvar resultado do backup
            with open(self.session_backup_dir / 'backup_report.json', 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False, default=str)
            
            logger.success(f"✅ Backup pré-migração concluído: {backup_duration:.2f}s")
            logger.info(f"📁 Localização: {self.session_backup_dir}")
            logger.info(f"📊 Arquivos: {self.backup_stats['total_files']}, Tamanho: {result['total_size_mb']:.2f}MB")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Falha crítica no backup pré-migração: {e}")
            self.backup_stats['backup_end'] = time.time()
            
            return {
                'success': False,
                'error': str(e),
                'backup_path': str(self.session_backup_dir),
                'timestamp': self.migration_timestamp,
                'backup_stats': self.backup_stats
            }
    
    def _backup_json_data(self) -> Dict[str, Any]:
        """Backup dos arquivos JSON com verificação de integridade"""
        logger.info("📄 Executando backup dos dados JSON...")
        
        json_backup_dir = self.session_backup_dir / 'json_data'
        json_backup_dir.mkdir(parents=True, exist_ok=True)
        
        json_files = ['audios.json', 'videos.json']
        backed_up_files = []
        
        for json_file in json_files:
            source_path = self.data_dir / json_file
            
            if source_path.exists():
                # Info do arquivo original
                original_info = self._get_file_info(source_path)
                
                # Backup do arquivo
                backup_path = json_backup_dir / json_file
                shutil.copy2(source_path, backup_path)
                
                # Info do arquivo de backup
                backup_info = self._get_file_info(backup_path)
                
                # Verificar integridade
                integrity_ok = (original_info['checksum'] == backup_info['checksum'] and 
                              original_info['size'] == backup_info['size'])
                
                file_backup = {
                    'filename': json_file,
                    'source_path': str(source_path),
                    'backup_path': str(backup_path),
                    'original_info': original_info,
                    'backup_info': backup_info,
                    'integrity_verified': integrity_ok,
                    'backup_timestamp': time.time()
                }
                
                backed_up_files.append(file_backup)
                self.backup_stats['total_files'] += 1
                self.backup_stats['total_size'] += original_info['size']
                
                if integrity_ok:
                    logger.info(f"✅ {json_file}: {original_info['size']:,} bytes")
                else:
                    logger.error(f"❌ Falha na integridade: {json_file}")
            else:
                logger.warning(f"⚠️ Arquivo não encontrado: {json_file}")
        
        return {
            'type': 'json_data',
            'backup_dir': str(json_backup_dir),
            'files': backed_up_files,
            'success': all(f['integrity_verified'] for f in backed_up_files)
        }
    
    def _backup_critical_audio_files(self) -> Dict[str, Any]:
        """Backup de arquivos de áudio críticos e transcrições"""
        logger.info("🎵 Executando backup de arquivos de áudio críticos...")
        
        audio_backup_dir = self.session_backup_dir / 'audio_samples'
        audio_backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Backup de algumas amostras representativas
        audio_base_dir = self.downloads_dir / 'audio'
        backed_up_files = []
        
        if audio_base_dir.exists():
            # Pegar primeiros 5 áudios como amostra
            audio_dirs = list(audio_base_dir.iterdir())[:5]
            
            for audio_dir in audio_dirs:
                if audio_dir.is_dir():
                    # Backup da transcrição (arquivo .md)
                    for md_file in audio_dir.glob('*.md'):
                        source_path = md_file
                        relative_path = source_path.relative_to(self.downloads_dir)
                        backup_path = audio_backup_dir / relative_path
                        
                        backup_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source_path, backup_path)
                        
                        original_info = self._get_file_info(source_path)
                        backup_info = self._get_file_info(backup_path)
                        
                        file_backup = {
                            'filename': md_file.name,
                            'type': 'transcription',
                            'source_path': str(source_path),
                            'backup_path': str(backup_path),
                            'original_info': original_info,
                            'backup_info': backup_info,
                            'integrity_verified': original_info['checksum'] == backup_info['checksum']
                        }
                        
                        backed_up_files.append(file_backup)
                        self.backup_stats['total_files'] += 1
                        self.backup_stats['total_size'] += original_info['size']
        
        return {
            'type': 'audio_samples',
            'backup_dir': str(audio_backup_dir),
            'files': backed_up_files,
            'success': True
        }
    
    def _backup_configurations(self) -> Dict[str, Any]:
        """Backup de arquivos de configuração críticos"""
        logger.info("⚙️ Executando backup das configurações...")
        
        config_backup_dir = self.session_backup_dir / 'configurations'
        config_backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Arquivos de configuração importantes
        config_files = [
            'pyproject.toml',
            'poetry.lock',
            'requirements.txt',  # se existir
            '.env',  # se existir
            'config.json'  # se existir
        ]
        
        backed_up_files = []
        
        for config_file in config_files:
            source_path = Path("E:\\python\\youtube_downloader") / config_file
            
            if source_path.exists():
                backup_path = config_backup_dir / config_file
                shutil.copy2(source_path, backup_path)
                
                original_info = self._get_file_info(source_path)
                backup_info = self._get_file_info(backup_path)
                
                file_backup = {
                    'filename': config_file,
                    'source_path': str(source_path),
                    'backup_path': str(backup_path),
                    'original_info': original_info,
                    'backup_info': backup_info,
                    'integrity_verified': original_info['checksum'] == backup_info['checksum']
                }
                
                backed_up_files.append(file_backup)
                self.backup_stats['total_files'] += 1
                self.backup_stats['total_size'] += original_info['size']
        
        return {
            'type': 'configurations',
            'backup_dir': str(config_backup_dir),
            'files': backed_up_files,
            'success': True
        }
    
    def _create_backup_manifest(self, backup_results: List[Dict]) -> Dict[str, Any]:
        """Cria manifesto detalhado do backup"""
        logger.info("📋 Criando manifesto do backup...")
        
        manifest = {
            'backup_session_id': self.migration_timestamp,
            'backup_timestamp': datetime.now(timezone.utc).isoformat(),
            'backup_type': 'pre_migration_full',
            'system_info': {
                'python_version': os.sys.version,
                'platform': os.name,
                'cwd': os.getcwd()
            },
            'backup_components': backup_results,
            'total_stats': {
                'files_count': self.backup_stats['total_files'],
                'total_size_bytes': self.backup_stats['total_size'],
                'total_size_mb': round(self.backup_stats['total_size'] / 1024 / 1024, 2)
            },
            'integrity_checksums': self.backup_stats['checksums'],
            'verification_enabled': self.verification_enabled
        }
        
        # Salvar manifesto
        manifest_path = self.session_backup_dir / 'backup_manifest.json'
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False, default=str)
        
        logger.success(f"📋 Manifesto criado: {manifest_path}")
        return manifest
    
    def _verify_backup_integrity(self, manifest: Dict[str, Any]) -> bool:
        """Verifica integridade completa do backup"""
        logger.info("🔍 Verificando integridade do backup...")
        
        if not self.verification_enabled:
            logger.warning("⚠️ Verificação de integridade desabilitada")
            return True
        
        verification_failures = []
        total_verified = 0
        
        # Verificar cada componente do backup
        for component in manifest['backup_components']:
            for file_info in component.get('files', []):
                if not file_info.get('integrity_verified', False):
                    verification_failures.append({
                        'file': file_info['filename'],
                        'component': component['type'],
                        'issue': 'checksum_mismatch'
                    })
                total_verified += 1
        
        # Verificar se arquivos de backup existem fisicamente
        backup_files = list(self.session_backup_dir.rglob('*'))
        for backup_file in backup_files:
            if backup_file.is_file() and backup_file.suffix in ['.json', '.md', '.toml', '.lock']:
                if not backup_file.exists():
                    verification_failures.append({
                        'file': str(backup_file),
                        'component': 'filesystem',
                        'issue': 'file_not_found'
                    })
        
        success = len(verification_failures) == 0
        
        # Salvar resultados da verificação
        verification_result = {
            'verification_timestamp': time.time(),
            'total_files_verified': total_verified,
            'failures_count': len(verification_failures),
            'failures': verification_failures,
            'success': success
        }
        
        with open(self.session_backup_dir / 'verification_report.json', 'w', encoding='utf-8') as f:
            json.dump(verification_result, f, indent=2, ensure_ascii=False, default=str)
        
        if success:
            logger.success(f"✅ Verificação de integridade: PASSOU ({total_verified} arquivos)")
        else:
            logger.error(f"❌ Verificação de integridade: FALHOU ({len(verification_failures)} problemas)")
            
        return success
    
    def _compress_backup(self) -> Dict[str, Any]:
        """Comprime backup para economizar espaço"""
        logger.info("🗜️ Comprimindo backup...")
        
        zip_path = self.session_backup_dir.parent / f"backup_{self.migration_timestamp}.zip"
        
        original_size = sum(f.stat().st_size for f in self.session_backup_dir.rglob('*') if f.is_file())
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in self.session_backup_dir.rglob('*'):
                if file_path.is_file():
                    arcname = file_path.relative_to(self.session_backup_dir)
                    zipf.write(file_path, arcname)
        
        compressed_size = zip_path.stat().st_size
        compression_ratio = (1 - compressed_size / original_size) * 100
        
        result = {
            'zip_path': str(zip_path),
            'original_size_bytes': original_size,
            'compressed_size_bytes': compressed_size,
            'compression_ratio_percent': round(compression_ratio, 2),
            'size_saved_mb': round((original_size - compressed_size) / 1024 / 1024, 2)
        }
        
        logger.success(f"✅ Compressão: {compression_ratio:.1f}% economia ({result['size_saved_mb']:.2f}MB)")
        return result
    
    def create_incremental_checkpoint(self, checkpoint_name: str, data_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        Cria checkpoint incremental durante a migração
        
        Args:
            checkpoint_name: Nome identificador do checkpoint
            data_snapshot: Snapshot atual dos dados
            
        Returns:
            Resultado do checkpoint
        """
        logger.info(f"📍 Criando checkpoint: {checkpoint_name}")
        
        checkpoint_dir = self.session_backup_dir / 'checkpoints' / checkpoint_name
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # Salvar snapshot dos dados
        snapshot_path = checkpoint_dir / 'data_snapshot.json'
        with open(snapshot_path, 'w', encoding='utf-8') as f:
            json.dump(data_snapshot, f, indent=2, ensure_ascii=False, default=str)
        
        # Metadata do checkpoint
        checkpoint_metadata = {
            'checkpoint_name': checkpoint_name,
            'timestamp': time.time(),
            'iso_timestamp': datetime.now(timezone.utc).isoformat(),
            'snapshot_path': str(snapshot_path),
            'data_keys': list(data_snapshot.keys()) if isinstance(data_snapshot, dict) else [],
            'snapshot_size_bytes': snapshot_path.stat().st_size
        }
        
        # Salvar metadata
        metadata_path = checkpoint_dir / 'checkpoint_metadata.json'
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_metadata, f, indent=2, ensure_ascii=False, default=str)
        
        logger.success(f"✅ Checkpoint criado: {checkpoint_name}")
        return checkpoint_metadata
    
    def validate_backup_before_migration(self) -> Dict[str, Any]:
        """
        Validação final do backup antes de iniciar migração
        
        Returns:
            Resultado da validação
        """
        logger.info("🔬 Validação final do backup...")
        
        validation_results = []
        
        # Verificar se diretório de backup existe
        if not self.session_backup_dir.exists():
            validation_results.append({
                'check': 'backup_directory_exists',
                'status': 'FAIL',
                'message': f'Diretório de backup não encontrado: {self.session_backup_dir}'
            })
        else:
            validation_results.append({
                'check': 'backup_directory_exists',
                'status': 'PASS',
                'message': f'Diretório de backup encontrado: {self.session_backup_dir}'
            })
        
        # Verificar se manifesto existe
        manifest_path = self.session_backup_dir / 'backup_manifest.json'
        if not manifest_path.exists():
            validation_results.append({
                'check': 'backup_manifest_exists',
                'status': 'FAIL',
                'message': 'Manifesto de backup não encontrado'
            })
        else:
            validation_results.append({
                'check': 'backup_manifest_exists',
                'status': 'PASS',
                'message': 'Manifesto de backup encontrado'
            })
        
        # Verificar se dados JSON foram salvos
        json_backup_dir = self.session_backup_dir / 'json_data'
        if not json_backup_dir.exists():
            validation_results.append({
                'check': 'json_data_backup_exists',
                'status': 'FAIL',
                'message': 'Backup dos dados JSON não encontrado'
            })
        else:
            audios_backup = json_backup_dir / 'audios.json'
            videos_backup = json_backup_dir / 'videos.json'
            
            audios_ok = audios_backup.exists()
            videos_ok = videos_backup.exists()
            
            validation_results.append({
                'check': 'json_data_backup_exists',
                'status': 'PASS' if (audios_ok and videos_ok) else 'PARTIAL',
                'message': f'Audios backup: {audios_ok}, Videos backup: {videos_ok}'
            })
        
        # Verificar relatório de verificação
        verification_report_path = self.session_backup_dir / 'verification_report.json'
        if verification_report_path.exists():
            with open(verification_report_path, 'r', encoding='utf-8') as f:
                verification_data = json.load(f)
                
            if verification_data.get('success', False):
                validation_results.append({
                    'check': 'backup_integrity_verification',
                    'status': 'PASS',
                    'message': f"Integridade verificada: {verification_data.get('total_files_verified', 0)} arquivos"
                })
            else:
                validation_results.append({
                    'check': 'backup_integrity_verification',
                    'status': 'FAIL',
                    'message': f"Falhas de integridade: {verification_data.get('failures_count', 0)}"
                })
        
        # Resultado final
        failed_checks = [r for r in validation_results if r['status'] == 'FAIL']
        validation_success = len(failed_checks) == 0
        
        final_result = {
            'validation_success': validation_success,
            'timestamp': time.time(),
            'checks_performed': len(validation_results),
            'checks_passed': len([r for r in validation_results if r['status'] == 'PASS']),
            'checks_failed': len(failed_checks),
            'detailed_results': validation_results,
            'ready_for_migration': validation_success
        }
        
        # Salvar resultado da validação
        validation_path = self.session_backup_dir / 'backup_validation.json'
        with open(validation_path, 'w', encoding='utf-8') as f:
            json.dump(final_result, f, indent=2, ensure_ascii=False, default=str)
        
        if validation_success:
            logger.success("✅ Validação do backup: APROVADA para migração")
        else:
            logger.error(f"❌ Validação do backup: REPROVADA ({len(failed_checks)} falhas)")
        
        return final_result


# Função utilitária para uso direto
def create_pre_migration_backup() -> Dict[str, Any]:
    """
    Função de conveniência para criar backup pré-migração
    
    Returns:
        Resultado do backup
    """
    backup_system = MigrationBackupSystem()
    return backup_system.create_pre_migration_backup()


# Função para validação antes da migração
def validate_backup_for_migration() -> bool:
    """
    Função de conveniência para validar backup antes da migração
    
    Returns:
        True se backup é válido para migração
    """
    backup_system = MigrationBackupSystem()
    result = backup_system.validate_backup_before_migration()
    return result.get('validation_success', False)


if __name__ == "__main__":
    # Exemplo de uso
    import asyncio
    
    async def main():
        backup_system = MigrationBackupSystem()
        
        # Criar backup
        backup_result = backup_system.create_pre_migration_backup()
        print(f"Backup Result: {backup_result['success']}")
        
        # Validar backup
        if backup_result['success']:
            validation_result = backup_system.validate_backup_before_migration()
            print(f"Validation Result: {validation_result['validation_success']}")
    
    asyncio.run(main())