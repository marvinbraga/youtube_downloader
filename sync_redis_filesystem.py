#!/usr/bin/env python
"""
Script para sincronizar o Redis com o diretório físico de áudio.
Garante que a base do Redis reflita perfeitamente o estado dos arquivos.
"""

import os
import json
import redis
import asyncio
from pathlib import Path
from typing import Dict, List, Set
from datetime import datetime
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RedisFilesystemSync:
    def __init__(self):
        self.redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        self.audio_dir = Path("E:/python/youtube_downloader/downloads/audio")
        self.json_file = Path("E:/python/youtube_downloader/data/audios.json")
        
    def scan_physical_files(self) -> Dict[str, Dict]:
        """Escaneia o diretório físico e retorna dados dos arquivos"""
        logger.info("Escaneando diretório físico...")
        physical_files = {}
        
        if not self.audio_dir.exists():
            logger.warning(f"Diretório de áudio não encontrado: {self.audio_dir}")
            return physical_files
            
        for audio_folder in self.audio_dir.iterdir():
            if not audio_folder.is_dir():
                continue
                
            audio_id = audio_folder.name
            m4a_files = list(audio_folder.glob("*.m4a"))
            md_files = list(audio_folder.glob("*.md"))
            
            if m4a_files:
                m4a_file = m4a_files[0]
                title = m4a_file.stem
                
                # Ler metadados do arquivo .md se existir
                metadata = {}
                if md_files:
                    try:
                        with open(md_files[0], 'r', encoding='utf-8') as f:
                            content = f.read()
                            # Parse básico do metadata
                            if 'URL:' in content:
                                url_line = [line for line in content.split('\n') if 'URL:' in line]
                                if url_line:
                                    metadata['url'] = url_line[0].split('URL:', 1)[1].strip()
                    except Exception as e:
                        logger.warning(f"Erro ao ler metadata de {audio_id}: {e}")
                
                physical_files[audio_id] = {
                    'id': audio_id,
                    'title': title,
                    'file_path': str(m4a_file),
                    'folder_path': str(audio_folder),
                    'download_status': 'completed',
                    'file_size': m4a_file.stat().st_size,
                    'created_at': datetime.fromtimestamp(m4a_file.stat().st_ctime).isoformat(),
                    'url': metadata.get('url', f'https://www.youtube.com/watch?v={audio_id}')
                }
                
        logger.info(f"Encontrados {len(physical_files)} arquivos físicos")
        return physical_files
    
    def scan_redis_data(self) -> Dict[str, Dict]:
        """Escaneia dados do Redis"""
        logger.info("Escaneando dados do Redis...")
        redis_data = {}
        
        try:
            # Buscar todas as chaves de áudio
            audio_keys = self.redis_client.keys("audio:*")
            
            for key in audio_keys:
                # Ignorar chaves de índice e auxiliares
                if any(pattern in key for pattern in [':index:', ':sorted:', ':all_ids', ':transcription:']):
                    continue
                    
                # Ignorar chaves que não são hash (dados dos áudios)
                try:
                    key_type = self.redis_client.type(key)
                    if key_type != 'hash':
                        continue
                        
                    data = self.redis_client.hgetall(key)
                    if data and 'id' in data:  # Validar que é um registro de áudio válido
                        audio_id = key.replace("audio:", "")
                        redis_data[audio_id] = data
                except Exception as e:
                    logger.debug(f"Pulando chave Redis {key}: {e}")
                    continue
                    
        except redis.ConnectionError:
            logger.error("Erro de conexão com Redis")
            return {}
        except Exception as e:
            logger.error(f"Erro ao escanear Redis: {e}")
            return {}
            
        logger.info(f"Encontrados {len(redis_data)} registros no Redis")
        return redis_data
    
    def sync_redis_with_filesystem(self, physical_files: Dict, redis_data: Dict) -> Dict:
        """Sincroniza Redis com arquivos físicos"""
        logger.info("Sincronizando Redis com sistema de arquivos...")
        sync_stats = {
            'added_to_redis': 0,
            'updated_in_redis': 0,
            'marked_as_pending': 0,
            'kept_as_is': 0
        }
        
        # 1. Adicionar/atualizar arquivos físicos no Redis
        for audio_id, file_data in physical_files.items():
            redis_key = f"audio:{audio_id}"
            
            if audio_id in redis_data:
                # Atualizar dados existentes
                existing_data = redis_data[audio_id]
                
                # Manter alguns campos existentes se disponíveis
                updated_data = {
                    'id': audio_id,
                    'title': existing_data.get('title', file_data['title']),
                    'url': existing_data.get('url', file_data['url']),
                    'file_path': file_data['file_path'],
                    'download_status': 'completed',  # Arquivo existe fisicamente
                    'file_size': str(file_data['file_size']),
                    'created_at': existing_data.get('created_at', file_data['created_at']),
                    'updated_at': datetime.now().isoformat()
                }
                
                # Manter campos adicionais se existirem
                for key, value in existing_data.items():
                    if key not in updated_data and value:
                        updated_data[key] = value
                        
                self.redis_client.hset(redis_key, mapping=updated_data)
                sync_stats['updated_in_redis'] += 1
                logger.info(f"Atualizado no Redis: {audio_id}")
                
            else:
                # Adicionar novo arquivo
                new_data = {
                    'id': audio_id,
                    'title': file_data['title'],
                    'url': file_data['url'],
                    'file_path': file_data['file_path'],
                    'download_status': 'completed',
                    'file_size': str(file_data['file_size']),
                    'created_at': file_data['created_at'],
                    'updated_at': datetime.now().isoformat()
                }
                
                self.redis_client.hset(redis_key, mapping=new_data)
                sync_stats['added_to_redis'] += 1
                logger.info(f"Adicionado ao Redis: {audio_id}")
        
        # 2. Marcar arquivos faltantes como 'pending' para redownload
        for audio_id in redis_data:
            if audio_id not in physical_files:
                redis_key = f"audio:{audio_id}"
                existing_data = redis_data[audio_id]
                
                # Marcar como pendente se não estava já
                if existing_data.get('download_status') != 'pending':
                    self.redis_client.hset(redis_key, 'download_status', 'pending')
                    self.redis_client.hset(redis_key, 'updated_at', datetime.now().isoformat())
                    sync_stats['marked_as_pending'] += 1
                    logger.info(f"Marcado como pending: {audio_id}")
                else:
                    sync_stats['kept_as_is'] += 1
        
        return sync_stats
    
    def update_json_file(self, physical_files: Dict):
        """Atualiza o arquivo JSON com dados sincronizados"""
        logger.info("Atualizando arquivo JSON...")
        
        # Preparar dados para JSON
        json_data = []
        for audio_id, file_data in physical_files.items():
            json_data.append({
                'id': audio_id,
                'title': file_data['title'],
                'file_path': file_data['file_path'],
                'download_status': 'completed',
                'created_at': file_data['created_at'],
                'url': file_data['url']
            })
        
        # Garantir que o diretório existe
        self.json_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Salvar JSON
        with open(self.json_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"Arquivo JSON atualizado com {len(json_data)} registros")
    
    def run_sync(self) -> Dict:
        """Executa sincronização completa"""
        logger.info("=" * 60)
        logger.info("INICIANDO SINCRONIZAÇÃO REDIS <-> FILESYSTEM")
        logger.info("=" * 60)
        
        try:
            # 1. Escanear arquivos físicos
            physical_files = self.scan_physical_files()
            
            # 2. Escanear dados do Redis
            redis_data = self.scan_redis_data()
            
            # 3. Sincronizar Redis
            sync_stats = self.sync_redis_with_filesystem(physical_files, redis_data)
            
            # 4. Atualizar JSON
            self.update_json_file(physical_files)
            
            # 5. Relatório final
            report = {
                'timestamp': datetime.now().isoformat(),
                'physical_files_found': len(physical_files),
                'redis_records_found': len(redis_data),
                'sync_statistics': sync_stats
            }
            
            logger.info("=" * 60)
            logger.info("SINCRONIZAÇÃO CONCLUÍDA")
            logger.info(f"Arquivos físicos: {report['physical_files_found']}")
            logger.info(f"Registros Redis: {report['redis_records_found']}")
            logger.info(f"Adicionados ao Redis: {sync_stats['added_to_redis']}")
            logger.info(f"Atualizados no Redis: {sync_stats['updated_in_redis']}")
            logger.info(f"Marcados como pending: {sync_stats['marked_as_pending']}")
            logger.info("=" * 60)
            
            return report
            
        except Exception as e:
            logger.error(f"Erro durante sincronização: {e}")
            return {'error': str(e)}

def main():
    """Função principal"""
    syncer = RedisFilesystemSync()
    result = syncer.run_sync()
    
    # Salvar relatório
    report_file = f"sync_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"Relatório salvo em: {report_file}")

if __name__ == "__main__":
    main()