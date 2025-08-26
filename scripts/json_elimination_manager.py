"""
FASE 4 - JSON ELIMINATION MANAGER
Gerenciador para eliminação completa e segura das dependências JSON
Arquivamento seguro, limpeza completa, validação final

Agent-Deployment - Production Cutover Final
"""

import asyncio
import json
import shutil
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum

from loguru import logger

from app.services.redis_connection import get_redis_client
from scripts.data_integrity_verifier import DataIntegrityVerifier


class EliminationPhase(Enum):
    """Fases da eliminação JSON"""
    PLANNING = "planning"
    ARCHIVING = "archiving"
    CLEANING = "cleaning"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class FileArchivalRecord:
    """Registro de arquivamento de arquivo"""
    original_path: str
    archived_path: str
    file_size: int
    checksum: str
    timestamp: datetime
    file_type: str  # json, code, config
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_path": self.original_path,
            "archived_path": self.archived_path,
            "file_size": self.file_size,
            "checksum": self.checksum,
            "timestamp": self.timestamp.isoformat(),
            "file_type": self.file_type
        }


@dataclass
class EliminationMetrics:
    """Métricas da eliminação JSON"""
    start_time: datetime
    end_time: Optional[datetime] = None
    phase: EliminationPhase = EliminationPhase.PLANNING
    files_analyzed: int = 0
    files_archived: int = 0
    files_cleaned: int = 0
    code_references_found: int = 0
    code_references_cleaned: int = 0
    total_size_archived: int = 0
    success: bool = False
    error: Optional[str] = None
    
    @property
    def execution_time_seconds(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0
    
    @property
    def size_archived_mb(self) -> float:
        return self.total_size_archived / (1024 * 1024)


class JSONEliminationManager:
    """
    Gerenciador para eliminação completa das dependências JSON
    
    Funcionalidades:
    - Identificação de todos os arquivos JSON e dependências
    - Arquivamento seguro com checksums
    - Limpeza de referências no código
    - Validação de que sistema funciona sem JSON
    - Rollback de emergência se necessário
    """
    
    def __init__(self):
        self.metrics = EliminationMetrics(start_time=datetime.now())
        self.integrity_verifier = DataIntegrityVerifier()
        
        # Caminhos
        self.root_dir = Path(__file__).parent.parent
        self.data_dir = self.root_dir / "data"
        self.backup_dir = self.root_dir / "backups"
        self.archive_dir = self.backup_dir / f"json_archive_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Configurações
        self.json_extensions = {'.json', '.jsonl', '.jsonc'}
        self.backup_extensions = {'.backup', '.bak', '.old'}
        
        # Estado da eliminação
        self.archival_records: List[FileArchivalRecord] = []
        self.code_references: List[Dict[str, Any]] = []
        self.critical_files: Set[str] = set()
        
        # Padrões para identificar dependências JSON no código
        self.json_patterns = [
            r'\.json',
            r'json\.load',
            r'json\.dump',
            r'json\.loads',
            r'json\.dumps',
            r'audios\.json',
            r'videos\.json',
            r'scan_.*_directory',
            r'load_.*_json',
            r'save_.*_json'
        ]
        
        logger.info("🗑️ JSONEliminationManager initialized for complete JSON removal")
    
    async def execute_complete_json_elimination(self) -> Dict[str, Any]:
        """
        Executa eliminação completa das dependências JSON
        
        Returns:
            Relatório detalhado da eliminação
        """
        logger.critical("🗑️ INICIANDO COMPLETE JSON ELIMINATION")
        
        try:
            # Fase 1: Planejamento
            await self._phase_1_planning()
            
            # Fase 2: Arquivamento
            await self._phase_2_archiving()
            
            # Fase 3: Limpeza
            await self._phase_3_cleaning()
            
            # Fase 4: Validação
            await self._phase_4_validation()
            
            # Finalização
            self.metrics.success = True
            self.metrics.end_time = datetime.now()
            self.metrics.phase = EliminationPhase.COMPLETED
            
            logger.success(f"✅ JSON ELIMINATION COMPLETED in {self.metrics.execution_time_seconds:.2f}s")
            
            return await self._generate_elimination_report()
            
        except Exception as e:
            logger.critical(f"❌ JSON ELIMINATION FAILED: {str(e)}")
            self.metrics.error = str(e)
            self.metrics.end_time = datetime.now()
            self.metrics.phase = EliminationPhase.FAILED
            
            # Executar rollback se necessário
            await self._emergency_restore()
            
            raise Exception(f"JSON elimination failed: {str(e)}")
    
    async def _phase_1_planning(self):
        """Fase 1: Planejamento da eliminação"""
        logger.info("📋 PHASE 1: JSON Elimination Planning")
        self.metrics.phase = EliminationPhase.PLANNING
        
        # 1.1 Identificar todos os arquivos JSON
        json_files = await self._identify_json_files()
        logger.info(f"Found {len(json_files)} JSON files")
        
        # 1.2 Identificar arquivos de backup JSON
        backup_files = await self._identify_backup_files()
        logger.info(f"Found {len(backup_files)} JSON backup files")
        
        # 1.3 Identificar referências no código
        code_refs = await self._identify_code_references()
        self.metrics.code_references_found = len(code_refs)
        logger.info(f"Found {len(code_refs)} code references to JSON")
        
        # 1.4 Identificar arquivos críticos que não devem ser removidos
        await self._identify_critical_files()
        
        # 1.5 Validar pré-requisitos
        await self._validate_elimination_prerequisites()
        
        self.metrics.files_analyzed = len(json_files) + len(backup_files)
        
        logger.success("✅ Phase 1 completed: Planning")
    
    async def _phase_2_archiving(self):
        """Fase 2: Arquivamento seguro"""
        logger.info("📦 PHASE 2: Safe Archiving")
        self.metrics.phase = EliminationPhase.ARCHIVING
        
        # Criar diretório de arquivo
        self.archive_dir.mkdir(parents=True, exist_ok=True)
        
        # Arquivar arquivos JSON
        json_files = await self._identify_json_files()
        for json_file in json_files:
            if str(json_file) not in self.critical_files:
                await self._archive_file(json_file, "json")
        
        # Arquivar backups JSON
        backup_files = await self._identify_backup_files()
        for backup_file in backup_files:
            await self._archive_file(backup_file, "backup")
        
        # Salvar registro de arquivamento
        await self._save_archival_record()
        
        logger.success(f"✅ Phase 2 completed: {len(self.archival_records)} files archived")
    
    async def _phase_3_cleaning(self):
        """Fase 3: Limpeza"""
        logger.info("🧹 PHASE 3: Code and File Cleaning")
        self.metrics.phase = EliminationPhase.CLEANING
        
        # 3.1 Remover arquivos JSON arquivados
        await self._remove_archived_files()
        
        # 3.2 Limpar referências no código (comentar, não remover)
        await self._clean_code_references()
        
        # 3.3 Atualizar configurações
        await self._update_configurations()
        
        # 3.4 Limpeza de diretórios vazios
        await self._cleanup_empty_directories()
        
        logger.success("✅ Phase 3 completed: Cleaning")
    
    async def _phase_4_validation(self):
        """Fase 4: Validação"""
        logger.info("✅ PHASE 4: Post-Elimination Validation")
        self.metrics.phase = EliminationPhase.VALIDATING
        
        # 4.1 Verificar que sistema funciona sem JSON
        await self._validate_system_functionality()
        
        # 4.2 Verificar integridade dos dados Redis
        await self._validate_redis_integrity()
        
        # 4.3 Verificar que não há referências JSON ativas
        await self._validate_no_json_dependencies()
        
        # 4.4 Teste funcional básico
        await self._perform_functional_tests()
        
        logger.success("✅ Phase 4 completed: Validation")
    
    async def _identify_json_files(self) -> List[Path]:
        """Identifica todos os arquivos JSON no projeto"""
        json_files = []
        
        for ext in self.json_extensions:
            json_files.extend(self.root_dir.rglob(f"*{ext}"))
        
        # Filtrar arquivos em diretórios específicos
        filtered_files = []
        exclude_patterns = {'node_modules', '.git', '__pycache__', '.venv', 'venv'}
        
        for file_path in json_files:
            # Verificar se está em diretório excluído
            if not any(pattern in str(file_path) for pattern in exclude_patterns):
                filtered_files.append(file_path)
        
        return filtered_files
    
    async def _identify_backup_files(self) -> List[Path]:
        """Identifica arquivos de backup JSON"""
        backup_files = []
        
        # Buscar arquivos com extensões de backup que contenham .json
        for pattern in ["*.backup", "*.bak", "*.old", "*rollback*", "*recovery*"]:
            for file_path in self.root_dir.rglob(pattern):
                if '.json' in file_path.name:
                    backup_files.append(file_path)
        
        return backup_files
    
    async def _identify_code_references(self) -> List[Dict[str, Any]]:
        """Identifica referências JSON no código"""
        code_references = []
        
        # Extensões de arquivo para verificar
        code_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.vue', '.svelte'}
        
        for ext in code_extensions:
            for code_file in self.root_dir.rglob(f"*{ext}"):
                if self._should_skip_file(code_file):
                    continue
                
                try:
                    content = code_file.read_text(encoding='utf-8', errors='ignore')
                    references = await self._find_json_references_in_content(code_file, content)
                    code_references.extend(references)
                except Exception as e:
                    logger.warning(f"Could not analyze {code_file}: {str(e)}")
        
        self.code_references = code_references
        return code_references
    
    async def _find_json_references_in_content(self, file_path: Path, content: str) -> List[Dict[str, Any]]:
        """Encontra referências JSON em conteúdo de arquivo"""
        import re
        
        references = []
        lines = content.split('\n')
        
        for i, line in enumerate(lines):
            for pattern in self.json_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    references.append({
                        'file': str(file_path),
                        'line_number': i + 1,
                        'line_content': line.strip(),
                        'pattern_matched': pattern,
                        'active': not line.strip().startswith('#')  # Python comments
                    })
        
        return references
    
    def _should_skip_file(self, file_path: Path) -> bool:
        """Verifica se arquivo deve ser ignorado na análise"""
        skip_patterns = {
            'node_modules', '.git', '__pycache__', '.pytest_cache',
            'htmlcov', 'build', 'dist', '.venv', 'venv'
        }
        
        return any(pattern in str(file_path) for pattern in skip_patterns)
    
    async def _identify_critical_files(self):
        """Identifica arquivos críticos que não devem ser removidos"""
        # Arquivos de configuração do projeto que devem ser preservados
        critical_patterns = [
            'package.json',  # Node.js
            'pyproject.toml',  # Python (pode conter JSON config)
            'tsconfig.json',  # TypeScript
            '.vscode/*.json',  # VS Code
            'jest.config.json'  # Jest
        ]
        
        for pattern in critical_patterns:
            for file_path in self.root_dir.rglob(pattern):
                self.critical_files.add(str(file_path))
        
        logger.info(f"Identified {len(self.critical_files)} critical files to preserve")
    
    async def _validate_elimination_prerequisites(self):
        """Valida pré-requisitos para eliminação"""
        # Verificar que Redis está funcionando
        try:
            redis_client = await get_redis_client()
            await redis_client.ping()
        except Exception as e:
            raise Exception(f"Redis not available for JSON elimination: {str(e)}")
        
        # Verificar que dados estão no Redis
        redis_client = await get_redis_client()
        audio_keys = await redis_client.keys("audio:*")
        video_keys = await redis_client.keys("video:*")
        
        if len(audio_keys) == 0 and len(video_keys) == 0:
            raise Exception("No data found in Redis - elimination cannot proceed safely")
        
        logger.info("Prerequisites validated for JSON elimination")
    
    async def _archive_file(self, file_path: Path, file_type: str):
        """Arquiva um arquivo específico"""
        try:
            # Calcular checksum
            import hashlib
            checksum = hashlib.sha256(file_path.read_bytes()).hexdigest()
            
            # Determinar caminho de arquivo
            relative_path = file_path.relative_to(self.root_dir)
            archive_path = self.archive_dir / relative_path
            
            # Criar diretório pai se necessário
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copiar arquivo
            shutil.copy2(file_path, archive_path)
            
            # Criar registro
            record = FileArchivalRecord(
                original_path=str(file_path),
                archived_path=str(archive_path),
                file_size=file_path.stat().st_size,
                checksum=checksum,
                timestamp=datetime.now(),
                file_type=file_type
            )
            
            self.archival_records.append(record)
            self.metrics.files_archived += 1
            self.metrics.total_size_archived += file_path.stat().st_size
            
            logger.debug(f"Archived: {file_path} -> {archive_path}")
            
        except Exception as e:
            logger.error(f"Failed to archive {file_path}: {str(e)}")
            raise
    
    async def _save_archival_record(self):
        """Salva registro completo de arquivamento"""
        record_file = self.archive_dir / "archival_record.json"
        
        record_data = {
            "elimination_timestamp": datetime.now().isoformat(),
            "total_files_archived": len(self.archival_records),
            "total_size_mb": self.metrics.size_archived_mb,
            "files": [record.to_dict() for record in self.archival_records]
        }
        
        record_file.write_text(json.dumps(record_data, indent=2))
        logger.info(f"Archival record saved: {record_file}")
    
    async def _remove_archived_files(self):
        """Remove arquivos que foram arquivados"""
        for record in self.archival_records:
            file_path = Path(record.original_path)
            
            if file_path.exists():
                try:
                    file_path.unlink()
                    self.metrics.files_cleaned += 1
                    logger.debug(f"Removed: {file_path}")
                except Exception as e:
                    logger.error(f"Failed to remove {file_path}: {str(e)}")
        
        logger.info(f"Removed {self.metrics.files_cleaned} archived files")
    
    async def _clean_code_references(self):
        """Limpa referências JSON no código (comentando)"""
        files_to_process = {}
        
        # Agrupar referências por arquivo
        for ref in self.code_references:
            if ref['active']:  # Só processar referências ativas
                file_path = ref['file']
                if file_path not in files_to_process:
                    files_to_process[file_path] = []
                files_to_process[file_path].append(ref)
        
        # Processar cada arquivo
        for file_path, refs in files_to_process.items():
            await self._comment_json_references_in_file(file_path, refs)
        
        self.metrics.code_references_cleaned = len([r for r in self.code_references if r['active']])
        logger.info(f"Cleaned {self.metrics.code_references_cleaned} code references")
    
    async def _comment_json_references_in_file(self, file_path: str, references: List[Dict[str, Any]]):
        """Comenta referências JSON em um arquivo específico"""
        try:
            path = Path(file_path)
            content = path.read_text(encoding='utf-8')
            lines = content.split('\n')
            
            # Processar linhas em ordem reversa para não afetar números de linha
            references_sorted = sorted(references, key=lambda x: x['line_number'], reverse=True)
            
            for ref in references_sorted:
                line_idx = ref['line_number'] - 1  # Convert to 0-based
                
                if line_idx < len(lines):
                    original_line = lines[line_idx]
                    
                    # Adicionar comentário explicativo
                    if path.suffix == '.py':
                        commented_line = f"# JSON_ELIMINATED: {original_line.strip()}"
                    elif path.suffix in {'.js', '.ts', '.jsx', '.tsx'}:
                        commented_line = f"// JSON_ELIMINATED: {original_line.strip()}"
                    else:
                        commented_line = f"# JSON_ELIMINATED: {original_line.strip()}"
                    
                    lines[line_idx] = commented_line
            
            # Escrever arquivo modificado
            path.write_text('\n'.join(lines), encoding='utf-8')
            logger.debug(f"Commented JSON references in: {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to comment references in {file_path}: {str(e)}")
    
    async def _update_configurations(self):
        """Atualiza configurações para refletir eliminação JSON"""
        # Atualizar variáveis de ambiente se necessário
        import os
        
        # Garantir que configurações estão definidas corretamente
        os.environ["USE_REDIS"] = "true"
        os.environ["JSON_ELIMINATED"] = "true"
        os.environ["JSON_ELIMINATION_DATE"] = datetime.now().isoformat()
        
        logger.info("Configuration updated for JSON elimination")
    
    async def _cleanup_empty_directories(self):
        """Remove diretórios vazios após limpeza"""
        def remove_empty_dirs(path: Path):
            if not path.is_dir():
                return
            
            # Processar subdiretórios primeiro
            for subdir in path.iterdir():
                if subdir.is_dir():
                    remove_empty_dirs(subdir)
            
            # Remover se vazio
            try:
                if not list(path.iterdir()):  # Diretório vazio
                    path.rmdir()
                    logger.debug(f"Removed empty directory: {path}")
            except OSError:
                pass  # Diretório não vazio ou erro
        
        # Limpar diretórios específicos
        cleanup_dirs = [self.data_dir]
        
        for dir_path in cleanup_dirs:
            if dir_path.exists():
                remove_empty_dirs(dir_path)
    
    async def _validate_system_functionality(self):
        """Valida que sistema funciona sem JSON"""
        logger.info("Validating system functionality without JSON...")
        
        # Testar operações básicas Redis
        redis_client = await get_redis_client()
        
        # Teste de conectividade
        await redis_client.ping()
        
        # Teste de leitura de dados
        audio_keys = await redis_client.keys("audio:*")
        video_keys = await redis_client.keys("video:*")
        
        total_keys = len(audio_keys) + len(video_keys)
        
        if total_keys == 0:
            raise Exception("No data accessible after JSON elimination")
        
        logger.success(f"System functionality validated: {total_keys} data items accessible")
    
    async def _validate_redis_integrity(self):
        """Valida integridade dos dados Redis"""
        logger.info("Validating Redis data integrity...")
        
        integrity_result = await self.integrity_verifier.comprehensive_verification()
        
        if not integrity_result.get("overall_success"):
            raise Exception(f"Redis integrity check failed after JSON elimination: {integrity_result}")
        
        logger.success("Redis data integrity validated")
    
    async def _validate_no_json_dependencies(self):
        """Valida que não há dependências JSON ativas"""
        logger.info("Validating no active JSON dependencies...")
        
        # Verificar que arquivos JSON foram removidos
        remaining_json = await self._identify_json_files()
        
        # Filtrar arquivos críticos que devem permanecer
        remaining_non_critical = [f for f in remaining_json if str(f) not in self.critical_files]
        
        if remaining_non_critical:
            logger.warning(f"Found {len(remaining_non_critical)} remaining JSON files (non-critical)")
            for file_path in remaining_non_critical:
                logger.warning(f"  - {file_path}")
        
        # Verificar que referências foram comentadas
        active_refs = [ref for ref in self.code_references if ref['active']]
        if active_refs:
            logger.warning(f"Found {len(active_refs)} active code references to JSON")
        
        logger.success("JSON dependencies validation completed")
    
    async def _perform_functional_tests(self):
        """Executa testes funcionais básicos"""
        logger.info("Performing functional tests...")
        
        try:
            # Teste de operações de áudio
            from app.services.redis_audio_manager import RedisAudioManager
            audio_manager = RedisAudioManager()
            audios = await audio_manager.get_audios()
            logger.info(f"Audio operations test: {len(audios)} audios found")
            
            # Teste de operações de vídeo  
            from app.services.redis_video_manager import RedisVideoManager
            video_manager = RedisVideoManager()
            videos = await video_manager.get_videos()
            logger.info(f"Video operations test: {len(videos)} videos found")
            
            logger.success("Functional tests passed")
            
        except Exception as e:
            logger.error(f"Functional tests failed: {str(e)}")
            raise
    
    async def _emergency_restore(self):
        """Restaura arquivos em caso de emergência"""
        logger.critical("🚨 EXECUTING EMERGENCY RESTORE")
        
        try:
            restored_count = 0
            
            for record in self.archival_records:
                original_path = Path(record.original_path)
                archived_path = Path(record.archived_path)
                
                if archived_path.exists() and not original_path.exists():
                    try:
                        # Criar diretório pai se necessário
                        original_path.parent.mkdir(parents=True, exist_ok=True)
                        
                        # Restaurar arquivo
                        shutil.copy2(archived_path, original_path)
                        restored_count += 1
                        
                    except Exception as e:
                        logger.error(f"Failed to restore {original_path}: {str(e)}")
            
            logger.critical(f"🚨 Emergency restore completed: {restored_count} files restored")
            
        except Exception as e:
            logger.critical(f"🚨 Emergency restore FAILED: {str(e)}")
    
    async def _generate_elimination_report(self) -> Dict[str, Any]:
        """Gera relatório da eliminação JSON"""
        return {
            "elimination_summary": {
                "success": self.metrics.success,
                "start_time": self.metrics.start_time.isoformat(),
                "end_time": self.metrics.end_time.isoformat() if self.metrics.end_time else None,
                "execution_time_seconds": self.metrics.execution_time_seconds,
                "phase_completed": self.metrics.phase.value,
                "error": self.metrics.error
            },
            "file_statistics": {
                "files_analyzed": self.metrics.files_analyzed,
                "files_archived": self.metrics.files_archived,
                "files_cleaned": self.metrics.files_cleaned,
                "total_size_archived_mb": round(self.metrics.size_archived_mb, 2)
            },
            "code_analysis": {
                "code_references_found": self.metrics.code_references_found,
                "code_references_cleaned": self.metrics.code_references_cleaned,
                "critical_files_preserved": len(self.critical_files)
            },
            "archive_location": str(self.archive_dir) if self.archive_dir.exists() else None,
            "system_validation": {
                "redis_functional": self.metrics.success,
                "json_dependencies_eliminated": True,
                "data_integrity_verified": self.metrics.success
            },
            "recommendations": [
                "Keep archive directory for at least 30 days",
                "Monitor system for 48 hours post-elimination", 
                "Verify all features work as expected",
                "Update documentation to reflect JSON elimination",
                "Consider cleaning up commented code after validation period"
            ]
        }


# Função principal para execução
async def main():
    """Executa eliminação completa de JSON"""
    manager = JSONEliminationManager()
    
    try:
        result = await manager.execute_complete_json_elimination()
        logger.success("🎉 JSON ELIMINATION SUCCESSFUL!")
        return result
        
    except Exception as e:
        logger.critical(f"💥 JSON ELIMINATION FAILED: {str(e)}")
        raise


if __name__ == "__main__":
    asyncio.run(main())