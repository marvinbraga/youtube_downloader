"""
Script de Migração: JSON para Redis
Migra todos os dados existentes do sistema JSON para Redis
"""

import asyncio
import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

# Adicionar o diretório pai ao Python path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from app.services.redis_connection import init_redis, close_redis, get_redis_client
from app.services.redis_audio_manager import redis_audio_manager
from app.services.redis_video_manager import redis_video_manager
from app.services.configs import AUDIO_CONFIG_PATH, JSON_CONFIG_PATH


class JSONToRedisMigrator:
    """
    Orchestrador da migração completa de dados JSON para Redis
    """
    
    def __init__(self):
        self.start_time = time.time()
        self.stats = {
            'audios_migrated': 0,
            'audios_failed': 0,
            'videos_migrated': 0,
            'videos_failed': 0,
            'total_errors': []
        }
    
    async def run_full_migration(self, create_backup: bool = True) -> bool:
        """
        Executa migração completa dos dados
        
        Args:
            create_backup: Se True, cria backup dos arquivos JSON antes da migração
            
        Returns:
            True se migração foi bem-sucedida
        """
        try:
            logger.info("🚀 Iniciando migração completa JSON → Redis...")
            
            # 1. Inicializar Redis
            await self._init_redis_connection()
            
            # 2. Criar backup se solicitado
            if create_backup:
                self._create_backup()
            
            # 3. Verificar integridade dos arquivos JSON
            await self._verify_json_integrity()
            
            # 4. Migrar dados de áudios
            await self._migrate_audio_data()
            
            # 5. Migrar dados de vídeos
            await self._migrate_video_data()
            
            # 6. Verificar integridade da migração
            await self._verify_migration_integrity()
            
            # 7. Exibir relatório final
            self._display_final_report()
            
            logger.success("🎉 Migração completa realizada com sucesso!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erro durante migração: {str(e)}")
            self.stats['total_errors'].append(f"Erro geral: {str(e)}")
            return False
        finally:
            await close_redis()
    
    async def _init_redis_connection(self):
        """Inicializa conexão Redis"""
        logger.info("🔌 Inicializando conexão Redis...")
        
        try:
            await init_redis()
            
            # Teste de conectividade
            redis_client = await get_redis_client()
            await redis_client.ping()
            
            logger.success("✅ Conexão Redis estabelecida")
            
        except Exception as e:
            logger.error(f"❌ Falha na conexão Redis: {str(e)}")
            raise
    
    def _create_backup(self):
        """Cria backup dos arquivos JSON"""
        logger.info("📦 Criando backup dos arquivos JSON...")
        
        backup_dir = Path("data/backup") / f"migration_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Backup do arquivo de áudios
            if AUDIO_CONFIG_PATH.exists():
                backup_audio_path = backup_dir / "audios.json"
                shutil.copy2(AUDIO_CONFIG_PATH, backup_audio_path)
                logger.debug(f"Backup de áudios: {backup_audio_path}")
            
            # Backup do arquivo de vídeos
            if JSON_CONFIG_PATH.exists():
                backup_video_path = backup_dir / "videos.json"
                shutil.copy2(JSON_CONFIG_PATH, backup_video_path)
                logger.debug(f"Backup de vídeos: {backup_video_path}")
            
            logger.success(f"✅ Backup criado em: {backup_dir}")
            
        except Exception as e:
            logger.error(f"❌ Erro ao criar backup: {str(e)}")
            raise
    
    async def _verify_json_integrity(self):
        """Verifica integridade dos arquivos JSON"""
        logger.info("🔍 Verificando integridade dos arquivos JSON...")
        
        # Verificar arquivo de áudios
        if AUDIO_CONFIG_PATH.exists():
            try:
                with open(AUDIO_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    audio_data = json.load(f)
                
                audios_count = len(audio_data.get('audios', []))
                mappings_count = len(audio_data.get('mappings', {}))
                
                logger.info(f"📊 Arquivo de áudios: {audios_count} áudios, {mappings_count} mapeamentos")
                
            except Exception as e:
                logger.error(f"❌ Arquivo de áudios corrompido: {str(e)}")
                raise
        else:
            logger.warning("⚠️ Arquivo de áudios não encontrado")
        
        # Verificar arquivo de vídeos
        if JSON_CONFIG_PATH.exists():
            try:
                with open(JSON_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    video_data = json.load(f)
                
                videos_count = len(video_data.get('videos', []))
                logger.info(f"📊 Arquivo de vídeos: {videos_count} vídeos")
                
            except Exception as e:
                logger.error(f"❌ Arquivo de vídeos corrompido: {str(e)}")
                raise
        else:
            logger.warning("⚠️ Arquivo de vídeos não encontrado")
        
        logger.success("✅ Integridade dos arquivos JSON verificada")
    
    async def _migrate_audio_data(self):
        """Migra dados de áudios para Redis"""
        logger.info("🎵 Migrando dados de áudios...")
        
        if not AUDIO_CONFIG_PATH.exists():
            logger.warning("⚠️ Arquivo de áudios não encontrado, pulando migração")
            return
        
        try:
            # Carregar dados JSON
            with open(AUDIO_CONFIG_PATH, 'r', encoding='utf-8') as f:
                audio_data = json.load(f)
            
            audios = audio_data.get('audios', [])
            total_audios = len(audios)
            
            if total_audios == 0:
                logger.info("ℹ️ Nenhum áudio para migrar")
                return
            
            logger.info(f"📊 Migrando {total_audios} áudios...")
            
            # Migrar em lotes para melhor performance
            batch_size = 10
            for i in range(0, total_audios, batch_size):
                batch = audios[i:i+batch_size]
                
                for j, audio in enumerate(batch):
                    try:
                        # Converter timestamps se necessário
                        if isinstance(audio.get('created_date'), str):
                            # Já está no formato correto
                            pass
                        
                        # Garantir que keywords é uma lista
                        if not isinstance(audio.get('keywords'), list):
                            audio['keywords'] = []
                        
                        # Garantir campos obrigatórios
                        if 'transcription_status' not in audio:
                            if audio.get('has_transcription', False):
                                audio['transcription_status'] = 'ended'
                            else:
                                audio['transcription_status'] = 'none'
                        
                        # Migrar para Redis
                        await redis_audio_manager.create_audio(audio)
                        
                        self.stats['audios_migrated'] += 1
                        
                        # Log de progresso
                        current_total = i + j + 1
                        if current_total % 5 == 0 or current_total == total_audios:
                            percentage = (current_total / total_audios) * 100
                            logger.info(f"📈 Progresso áudios: {current_total}/{total_audios} ({percentage:.1f}%)")
                        
                    except Exception as e:
                        error_msg = f"Erro ao migrar áudio {audio.get('id', 'unknown')}: {str(e)}"
                        logger.error(f"❌ {error_msg}")
                        self.stats['audios_failed'] += 1
                        self.stats['total_errors'].append(error_msg)
                
                # Pequena pausa para não sobrecarregar o Redis
                await asyncio.sleep(0.1)
            
            logger.success(f"✅ Migração de áudios concluída: {self.stats['audios_migrated']} sucessos, {self.stats['audios_failed']} falhas")
            
        except Exception as e:
            logger.error(f"❌ Erro na migração de áudios: {str(e)}")
            raise
    
    async def _migrate_video_data(self):
        """Migra dados de vídeos para Redis"""
        logger.info("🎬 Migrando dados de vídeos...")
        
        if not JSON_CONFIG_PATH.exists():
            logger.warning("⚠️ Arquivo de vídeos não encontrado, pulando migração")
            return
        
        try:
            # Carregar dados JSON
            with open(JSON_CONFIG_PATH, 'r', encoding='utf-8') as f:
                video_data = json.load(f)
            
            videos = video_data.get('videos', [])
            total_videos = len(videos)
            
            if total_videos == 0:
                logger.info("ℹ️ Nenhum vídeo para migrar")
                return
            
            logger.info(f"📊 Migrando {total_videos} vídeos...")
            
            for i, video in enumerate(videos):
                try:
                    # Garantir ID único
                    if 'id' not in video and 'url' in video:
                        import hashlib
                        video['id'] = hashlib.md5(video['url'].encode()).hexdigest()[:8]
                    
                    # Garantir campos obrigatórios
                    if 'source' not in video:
                        video['source'] = 'YOUTUBE' if 'url' in video else 'LOCAL'
                    
                    if 'created_date' not in video:
                        video['created_date'] = datetime.now().isoformat()
                    
                    if 'modified_date' not in video:
                        video['modified_date'] = video.get('created_date', datetime.now().isoformat())
                    
                    # Migrar para Redis
                    await redis_video_manager.create_video(video)
                    
                    self.stats['videos_migrated'] += 1
                    
                    # Log de progresso
                    current = i + 1
                    if current % 5 == 0 or current == total_videos:
                        percentage = (current / total_videos) * 100
                        logger.info(f"📈 Progresso vídeos: {current}/{total_videos} ({percentage:.1f}%)")
                    
                except Exception as e:
                    error_msg = f"Erro ao migrar vídeo {video.get('id', video.get('url', 'unknown'))}: {str(e)}"
                    logger.error(f"❌ {error_msg}")
                    self.stats['videos_failed'] += 1
                    self.stats['total_errors'].append(error_msg)
            
            logger.success(f"✅ Migração de vídeos concluída: {self.stats['videos_migrated']} sucessos, {self.stats['videos_failed']} falhas")
            
        except Exception as e:
            logger.error(f"❌ Erro na migração de vídeos: {str(e)}")
            raise
    
    async def _verify_migration_integrity(self):
        """Verifica integridade da migração"""
        logger.info("🔍 Verificando integridade da migração...")
        
        try:
            # Verificar áudios
            redis_audios = await redis_audio_manager.get_all_audios()
            redis_audio_count = len(redis_audios)
            
            # Contar áudios originais no JSON
            json_audio_count = 0
            if AUDIO_CONFIG_PATH.exists():
                with open(AUDIO_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    audio_data = json.load(f)
                json_audio_count = len(audio_data.get('audios', []))
            
            logger.info(f"📊 Áudios - JSON: {json_audio_count}, Redis: {redis_audio_count}")
            
            # Verificar vídeos
            redis_videos = await redis_video_manager.get_all_videos()
            redis_video_count = len(redis_videos)
            
            # Contar vídeos originais no JSON
            json_video_count = 0
            if JSON_CONFIG_PATH.exists():
                with open(JSON_CONFIG_PATH, 'r', encoding='utf-8') as f:
                    video_data = json.load(f)
                json_video_count = len(video_data.get('videos', []))
            
            logger.info(f"📊 Vídeos - JSON: {json_video_count}, Redis: {redis_video_count}")
            
            # Verificar discrepâncias
            if redis_audio_count != self.stats['audios_migrated']:
                logger.warning(f"⚠️ Discrepância de áudios: migrados={self.stats['audios_migrated']}, encontrados no Redis={redis_audio_count}")
            
            if redis_video_count != self.stats['videos_migrated']:
                logger.warning(f"⚠️ Discrepância de vídeos: migrados={self.stats['videos_migrated']}, encontrados no Redis={redis_video_count}")
            
            # Teste de amostra: verificar alguns registros aleatórios
            await self._sample_verification(redis_audios[:3] if redis_audios else [])
            
            logger.success("✅ Verificação de integridade concluída")
            
        except Exception as e:
            logger.error(f"❌ Erro na verificação de integridade: {str(e)}")
            raise
    
    async def _sample_verification(self, sample_audios: list):
        """Verifica amostra de registros"""
        if not sample_audios:
            return
        
        logger.info(f"🔍 Verificando amostra de {len(sample_audios)} registros...")
        
        for audio in sample_audios:
            try:
                audio_id = audio.get('id')
                if not audio_id:
                    continue
                
                # Buscar no Redis
                redis_audio = await redis_audio_manager.get_audio(audio_id)
                
                if not redis_audio:
                    logger.error(f"❌ Áudio {audio_id} não encontrado no Redis")
                    continue
                
                # Verificar campos críticos
                if redis_audio.get('title') != audio.get('title'):
                    logger.warning(f"⚠️ Discrepância no título do áudio {audio_id}")
                
                if redis_audio.get('url') != audio.get('url'):
                    logger.warning(f"⚠️ Discrepância na URL do áudio {audio_id}")
                
                logger.debug(f"✅ Áudio {audio_id} verificado")
                
            except Exception as e:
                logger.error(f"❌ Erro ao verificar áudio {audio.get('id', 'unknown')}: {str(e)}")
    
    def _display_final_report(self):
        """Exibe relatório final da migração"""
        elapsed_time = time.time() - self.start_time
        
        logger.info("=" * 50)
        logger.info("📋 RELATÓRIO FINAL DE MIGRAÇÃO")
        logger.info("=" * 50)
        logger.info(f"⏱️ Tempo total: {elapsed_time:.2f} segundos")
        logger.info(f"🎵 Áudios migrados: {self.stats['audios_migrated']}")
        logger.info(f"❌ Áudios com erro: {self.stats['audios_failed']}")
        logger.info(f"🎬 Vídeos migrados: {self.stats['videos_migrated']}")
        logger.info(f"❌ Vídeos com erro: {self.stats['videos_failed']}")
        logger.info(f"📊 Total de registros: {self.stats['audios_migrated'] + self.stats['videos_migrated']}")
        
        if self.stats['total_errors']:
            logger.info(f"⚠️ Total de erros: {len(self.stats['total_errors'])}")
            for error in self.stats['total_errors'][:5]:  # Mostrar apenas os primeiros 5 erros
                logger.error(f"  - {error}")
            if len(self.stats['total_errors']) > 5:
                logger.info(f"  ... e mais {len(self.stats['total_errors']) - 5} erros")
        
        success_rate = ((self.stats['audios_migrated'] + self.stats['videos_migrated']) / 
                       max(1, self.stats['audios_migrated'] + self.stats['videos_migrated'] + 
                           self.stats['audios_failed'] + self.stats['videos_failed'])) * 100
        
        logger.info(f"📈 Taxa de sucesso: {success_rate:.1f}%")
        logger.info("=" * 50)


async def main():
    """Função principal"""
    print("🚀 Script de Migração JSON → Redis")
    print("=" * 50)
    
    migrator = JSONToRedisMigrator()
    
    # Executar migração
    success = await migrator.run_full_migration(create_backup=True)
    
    if success:
        print("\n🎉 Migração realizada com sucesso!")
        print("✅ Agora você pode habilitar o modo Redis definindo USE_REDIS=true")
        return 0
    else:
        print("\n❌ Migração falhou. Verifique os logs acima.")
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))