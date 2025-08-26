"""
Redis Video Manager - Gerenciador de Vídeos usando Redis
Substitui completamente as operações JSON por Redis com performance superior
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any, Union

from loguru import logger

from app.models.video import VideoSource, SortOption
from app.services.redis_connection import get_redis_client, redis_manager
from app.services.configs import VIDEO_DIR


class RedisVideoManager:
    """
    Gerenciador de vídeos usando Redis como backend de dados.
    Implementa todas as operações do sistema atual com performance superior.
    """
    
    def __init__(self):
        self._redis = None
        
        # Configurações de índices
        self.INDEX_PATTERNS = {
            'source': 'video:index:source:{}',  # LOCAL, YOUTUBE
            'type': 'video:index:type:{}',      # mp4, webm
            'date': 'video:index:date:{}',      # Por ano-mês
        }
        
        # Configurações de ordenação
        self.SORT_PATTERNS = {
            'created': 'video:sorted:created',
            'modified': 'video:sorted:modified',
            'size': 'video:sorted:size',
            'name': 'video:sorted:name',  # Score baseado em hash do nome
        }
        
        # Configurações de cache
        self.CACHE_PATTERNS = {
            'scan': 'video:cache:scan:{}',
            'stats': 'video:cache:stats',
            'all': 'video:cache:all',
        }
        
        # TTL padrão para cache (5 minutos)
        self.DEFAULT_CACHE_TTL = 300
    
    async def _get_redis(self):
        """Obtém cliente Redis lazy loading"""
        if self._redis is None:
            self._redis = await get_redis_client()
        return self._redis
    
    def _generate_video_key(self, video_id: str) -> str:
        """Gera chave Redis para vídeo específico"""
        return f'video:{video_id}'
    
    def _generate_video_id(self, identifier: Union[Path, str]) -> str:
        """Gera um ID único para um vídeo baseado no caminho ou URL"""
        import hashlib
        identifier_str = str(identifier)
        return hashlib.md5(identifier_str.encode()).hexdigest()[:8]
    
    def _get_clean_filename(self, file_path: Path) -> str:
        """Remove a extensão do nome do arquivo"""
        name = file_path.name
        video_extensions = {'.mp4', '.webm'}
        for ext in video_extensions:
            if name.lower().endswith(ext):
                name = name[:-len(ext)]
                break
        return name
    
    def _to_timestamp(self, date_str: str) -> float:
        """
        Converte string de data para timestamp Unix
        
        Args:
            date_str: String de data em formato ISO
            
        Returns:
            Timestamp Unix
        """
        try:
            if isinstance(date_str, str):
                # Tenta diferentes formatos de data
                formats = ['%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S']
                for fmt in formats:
                    try:
                        return datetime.strptime(date_str, fmt).timestamp()
                    except ValueError:
                        continue
                # Se não conseguiu parse, usa data atual
                logger.warning(f"Formato de data inválido: {date_str}, usando data atual")
                return time.time()
            else:
                return float(date_str)
        except (ValueError, TypeError):
            logger.warning(f"Erro ao converter data: {date_str}, usando data atual")
            return time.time()
    
    def _calculate_name_score(self, name: str) -> float:
        """
        Calcula score para ordenação por nome (baseado em hash)
        
        Args:
            name: Nome do vídeo
            
        Returns:
            Score numérico para ordenação
        """
        if not name:
            return 0.0
        
        # Usar hash do nome normalizado para criar score consistente
        normalized = name.lower().strip()
        hash_value = hash(normalized)
        # Converter para float positivo entre 0 e 1
        return abs(hash_value) / (2**31)
    
    async def get_video_info_from_path(self, video_path: Path) -> Dict[str, Any]:
        """
        Coleta informações sobre um arquivo de vídeo local
        
        Args:
            video_path: Caminho para o arquivo de vídeo
            
        Returns:
            Dicionário com informações do vídeo
        """
        try:
            stats = video_path.stat()
            return {
                'id': self._generate_video_id(video_path),
                'name': self._get_clean_filename(video_path),
                'path': str(video_path.relative_to(VIDEO_DIR)),
                'type': video_path.suffix.lower()[1:],
                'created_date': datetime.fromtimestamp(stats.st_ctime).isoformat(),
                'modified_date': datetime.fromtimestamp(stats.st_mtime).isoformat(),
                'size': stats.st_size,
                'source': VideoSource.LOCAL,
                'url': None
            }
        except Exception as e:
            logger.error(f"Erro ao obter informações do vídeo {video_path}: {str(e)}")
            return {}
    
    async def create_video(self, video_data: Dict[str, Any]) -> str:
        """
        Cria novo registro de vídeo no Redis com todos os índices
        
        Args:
            video_data: Dados do vídeo
            
        Returns:
            ID do vídeo criado
        """
        redis_client = await self._get_redis()
        
        try:
            video_id = video_data.get('id')
            if not video_id:
                raise ValueError("ID do vídeo é obrigatório")
            
            # Preparar dados para Redis
            redis_data = {}
            for key, value in video_data.items():
                if isinstance(value, (list, dict)):
                    redis_data[key] = json.dumps(value, ensure_ascii=False)
                elif value is not None:
                    redis_data[key] = str(value)
            
            # Usar pipeline para operações atômicas
            async with redis_manager.get_pipeline(transaction=True) as pipe:
                video_key = self._generate_video_key(video_id)
                
                # 1. Armazenar dados principais
                await pipe.hset(video_key, mapping=redis_data)
                
                # 2. Adicionar aos índices
                await self._add_to_indexes(pipe, video_id, video_data)
                
                # 3. Adicionar às ordenações
                await self._add_to_sorted_sets(pipe, video_id, video_data)
                
                # 4. Atualizar estatísticas
                await pipe.hincrby('video:stats', 'total_count', 1)
                if video_data.get('size'):
                    await pipe.hincrby('video:stats', 'total_size', int(video_data['size']))
                
                # 5. Invalidar caches relacionados
                await self._invalidate_caches(pipe)
                
                # Executar pipeline
                await pipe.execute()
            
            logger.info(f"Vídeo criado no Redis: {video_id}")
            return video_id
            
        except Exception as e:
            logger.error(f"Erro ao criar vídeo no Redis: {str(e)}")
            raise
    
    async def get_video(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtém dados de um vídeo pelo ID
        
        Args:
            video_id: ID do vídeo
            
        Returns:
            Dados do vídeo ou None se não encontrado
        """
        redis_client = await self._get_redis()
        
        try:
            video_key = self._generate_video_key(video_id)
            video_data = await redis_client.hgetall(video_key)
            
            if not video_data:
                return None
            
            # Converter dados Redis de volta para Python
            result = {}
            for key, value in video_data.items():
                key = key.decode() if isinstance(key, bytes) else key
                value = value.decode() if isinstance(value, bytes) else value
                
                # Converter valores numéricos
                if key == 'size':
                    try:
                        result[key] = int(value)
                    except (ValueError, TypeError):
                        result[key] = 0
                else:
                    result[key] = value
            
            return result
            
        except Exception as e:
            logger.error(f"Erro ao obter vídeo do Redis: {str(e)}")
            return None
    
    async def update_video(self, video_id: str, updates: Dict[str, Any]) -> bool:
        """
        Atualiza dados de um vídeo existente
        
        Args:
            video_id: ID do vídeo
            updates: Dados a serem atualizados
            
        Returns:
            True se atualizado com sucesso
        """
        redis_client = await self._get_redis()
        
        try:
            video_key = self._generate_video_key(video_id)
            
            # Verificar se vídeo existe
            exists = await redis_client.exists(video_key)
            if not exists:
                logger.warning(f"Vídeo não encontrado para atualização: {video_id}")
                return False
            
            # Obter dados atuais para comparação de índices
            current_data = await self.get_video(video_id)
            if not current_data:
                return False
            
            # Preparar updates para Redis
            redis_updates = {}
            for key, value in updates.items():
                if isinstance(value, (list, dict)):
                    redis_updates[key] = json.dumps(value, ensure_ascii=False)
                elif value is not None:
                    redis_updates[key] = str(value)
            
            # Adicionar timestamp de modificação
            redis_updates['modified_date'] = datetime.now().isoformat()
            
            async with redis_manager.get_pipeline(transaction=True) as pipe:
                # 1. Atualizar dados principais
                await pipe.hset(video_key, mapping=redis_updates)
                
                # 2. Atualizar índices se necessário
                merged_data = {**current_data, **updates}
                await self._update_indexes(pipe, video_id, current_data, merged_data)
                
                # 3. Atualizar ordenações
                await self._update_sorted_sets(pipe, video_id, current_data, merged_data)
                
                # 4. Invalidar caches
                await self._invalidate_caches(pipe)
                
                await pipe.execute()
            
            logger.info(f"Vídeo atualizado no Redis: {video_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao atualizar vídeo no Redis: {str(e)}")
            return False
    
    async def delete_video(self, video_id: str) -> bool:
        """
        Remove um vídeo completamente do Redis
        
        Args:
            video_id: ID do vídeo
            
        Returns:
            True se removido com sucesso
        """
        redis_client = await self._get_redis()
        
        try:
            # Obter dados antes de deletar para limpar índices
            video_data = await self.get_video(video_id)
            if not video_data:
                logger.warning(f"Vídeo não encontrado para remoção: {video_id}")
                return False
            
            async with redis_manager.get_pipeline(transaction=True) as pipe:
                video_key = self._generate_video_key(video_id)
                
                # 1. Remover dados principais
                await pipe.delete(video_key)
                
                # 2. Remover de todos os índices
                await self._remove_from_indexes(pipe, video_id, video_data)
                
                # 3. Remover das ordenações
                await self._remove_from_sorted_sets(pipe, video_id)
                
                # 4. Atualizar estatísticas
                await pipe.hincrby('video:stats', 'total_count', -1)
                if video_data.get('size'):
                    await pipe.hincrby('video:stats', 'total_size', -int(video_data['size']))
                
                # 5. Invalidar caches
                await self._invalidate_caches(pipe)
                
                await pipe.execute()
            
            logger.info(f"Vídeo removido do Redis: {video_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao remover vídeo do Redis: {str(e)}")
            return False
    
    async def scan_video_directory(self, sort_by: SortOption = SortOption.NONE) -> List[Dict[str, Any]]:
        """
        Escaneia o diretório de vídeos e sincroniza com Redis, combinando com vídeos remotos
        
        Args:
            sort_by: Opção de ordenação
            
        Returns:
            Lista de vídeos ordenados
        """
        redis_client = await self._get_redis()
        
        try:
            # Verificar cache
            cache_key = self.CACHE_PATTERNS['scan'].format(sort_by.value if sort_by else 'none')
            cached_result = await redis_client.get(cache_key)
            
            if cached_result:
                try:
                    cached_data = json.loads(cached_result.decode())
                    logger.debug(f"Cache hit para scan de vídeos: {sort_by}")
                    return cached_data
                except (json.JSONDecodeError, AttributeError):
                    pass
            
            video_list = []
            local_video_ids = set()
            
            # 1. Escanear arquivos locais
            video_extensions = {'.mp4', '.webm'}
            
            for video_path in VIDEO_DIR.rglob('*'):
                if video_path.is_file() and video_path.suffix.lower() in video_extensions:
                    try:
                        video_info = await self.get_video_info_from_path(video_path)
                        if video_info:
                            video_id = video_info['id']
                            local_video_ids.add(video_id)
                            
                            # Verificar se já existe no Redis
                            existing_video = await self.get_video(video_id)
                            if existing_video:
                                # Atualizar dados se mudaram
                                if (existing_video.get('modified_date') != video_info['modified_date'] or
                                    existing_video.get('size') != video_info['size']):
                                    await self.update_video(video_id, video_info)
                                    video_list.append({**existing_video, **video_info})
                                else:
                                    video_list.append(existing_video)
                            else:
                                # Criar novo registro no Redis
                                await self.create_video(video_info)
                                video_list.append(video_info)
                                
                    except Exception as e:
                        logger.error(f"Erro ao processar vídeo local {video_path}: {str(e)}")
                        continue
            
            # 2. Obter vídeos remotos (YouTube) do Redis
            remote_videos = await self.get_videos_by_source(VideoSource.YOUTUBE)
            video_list.extend(remote_videos)
            
            # 3. Remover vídeos locais que não existem mais no filesystem
            all_local_videos = await self.get_videos_by_source(VideoSource.LOCAL)
            for local_video in all_local_videos:
                if local_video['id'] not in local_video_ids:
                    logger.info(f"Removendo vídeo local inexistente: {local_video['id']}")
                    await self.delete_video(local_video['id'])
            
            # 4. Aplicar ordenação
            video_list = self._sort_videos(video_list, sort_by)
            
            # Cache resultado por 2 minutos
            await redis_client.setex(cache_key, 120, json.dumps(video_list, ensure_ascii=False))
            
            logger.debug(f"Scan de vídeos retornou {len(video_list)} vídeos")
            return video_list
            
        except Exception as e:
            logger.error(f"Erro no scan de vídeos: {str(e)}")
            return []
    
    async def get_all_videos(self, sort_by: SortOption = SortOption.NONE) -> List[Dict[str, Any]]:
        """
        Obtém todos os vídeos do Redis com ordenação
        
        Args:
            sort_by: Opção de ordenação
            
        Returns:
            Lista de todos os vídeos ordenados
        """
        redis_client = await self._get_redis()
        
        try:
            # Verificar cache
            cache_key = self.CACHE_PATTERNS['all']
            cached_result = await redis_client.get(cache_key)
            
            if cached_result:
                try:
                    cached_videos = json.loads(cached_result.decode())
                    return self._sort_videos(cached_videos, sort_by)
                except (json.JSONDecodeError, AttributeError):
                    pass
            
            # Obter todos os vídeos usando scan
            video_keys = []
            async for key in redis_client.scan_iter(match='video:*'):
                key_str = key.decode() if isinstance(key, bytes) else key
                if key_str.startswith('video:') and ':' not in key_str[6:]:  # Evitar chaves de índices
                    video_keys.append(key_str)
            
            if not video_keys:
                return []
            
            # Carregar dados dos vídeos
            video_list = []
            async with redis_manager.get_pipeline(transaction=False) as pipe:
                for video_key in video_keys:
                    await pipe.hgetall(video_key)
                
                video_data_list = await pipe.execute()
            
            # Processar resultados
            for i, video_data in enumerate(video_data_list):
                if video_data:
                    processed_video = {}
                    for key, value in video_data.items():
                        key = key.decode() if isinstance(key, bytes) else key
                        value = value.decode() if isinstance(value, bytes) else value
                        
                        if key == 'size':
                            try:
                                processed_video[key] = int(value)
                            except (ValueError, TypeError):
                                processed_video[key] = 0
                        else:
                            processed_video[key] = value
                    
                    # Extrair ID da chave
                    video_id = video_keys[i].split(':')[1]
                    processed_video['id'] = video_id
                    video_list.append(processed_video)
            
            # Cache resultado por 5 minutos
            await redis_client.setex(cache_key, self.DEFAULT_CACHE_TTL, 
                                   json.dumps(video_list, ensure_ascii=False))
            
            # Aplicar ordenação
            video_list = self._sort_videos(video_list, sort_by)
            
            logger.debug(f"Retornando {len(video_list)} vídeos ordenados por {sort_by}")
            return video_list
            
        except Exception as e:
            logger.error(f"Erro ao obter todos os vídeos: {str(e)}")
            return []
    
    async def get_videos_by_source(self, source: VideoSource) -> List[Dict[str, Any]]:
        """
        Obtém vídeos por fonte específica
        
        Args:
            source: Fonte dos vídeos (LOCAL, YOUTUBE)
            
        Returns:
            Lista de vídeos da fonte especificada
        """
        redis_client = await self._get_redis()
        
        try:
            # Buscar no índice de fonte
            index_key = self.INDEX_PATTERNS['source'].format(source.value)
            video_ids = await redis_client.smembers(index_key)
            
            if not video_ids:
                return []
            
            # Converter bytes para string se necessário
            if isinstance(next(iter(video_ids)), bytes):
                video_ids = [vid.decode() for vid in video_ids]
            
            # Carregar dados dos vídeos
            results = []
            for video_id in video_ids:
                video_data = await self.get_video(video_id)
                if video_data:
                    results.append(video_data)
            
            return results
            
        except Exception as e:
            logger.error(f"Erro ao obter vídeos por fonte: {str(e)}")
            return []
    
    def _sort_videos(self, video_list: List[Dict[str, Any]], sort_by: SortOption) -> List[Dict[str, Any]]:
        """
        Aplica ordenação na lista de vídeos
        
        Args:
            video_list: Lista de vídeos para ordenar
            sort_by: Opção de ordenação
            
        Returns:
            Lista ordenada
        """
        if sort_by == SortOption.TITLE:
            return sorted(video_list, key=lambda x: x.get('name', '').lower())
        elif sort_by == SortOption.DATE:
            return sorted(video_list, key=lambda x: x.get('modified_date', ''), reverse=True)
        else:
            return video_list
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Obtém estatísticas dos vídeos
        
        Returns:
            Dicionário com estatísticas
        """
        redis_client = await self._get_redis()
        
        try:
            # Verificar cache
            cache_key = self.CACHE_PATTERNS['stats']
            cached_stats = await redis_client.get(cache_key)
            
            if cached_stats:
                try:
                    return json.loads(cached_stats.decode())
                except (json.JSONDecodeError, AttributeError):
                    pass
            
            # Calcular estatísticas
            stats = {}
            
            # Estatísticas básicas
            basic_stats = await redis_client.hgetall('video:stats')
            for key, value in basic_stats.items():
                key = key.decode() if isinstance(key, bytes) else key
                value = value.decode() if isinstance(value, bytes) else value
                stats[key] = int(value) if value.isdigit() else value
            
            # Contadores por fonte
            for source in [VideoSource.LOCAL, VideoSource.YOUTUBE]:
                index_key = self.INDEX_PATTERNS['source'].format(source.value)
                count = await redis_client.scard(index_key)
                stats[f'source_{source.value.lower()}'] = count
            
            # Contadores por tipo
            video_types = ['mp4', 'webm']
            for video_type in video_types:
                index_key = self.INDEX_PATTERNS['type'].format(video_type)
                count = await redis_client.scard(index_key)
                stats[f'type_{video_type}'] = count
            
            # Adicionar timestamp
            stats['last_updated'] = datetime.now().isoformat()
            
            # Cache por 2 minutos
            await redis_client.setex(cache_key, 120, json.dumps(stats, ensure_ascii=False))
            
            return stats
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas de vídeos: {str(e)}")
            return {}
    
    async def _add_to_indexes(self, pipe, video_id: str, video_data: Dict[str, Any]):
        """Adiciona vídeo aos índices"""
        # Índice de fonte
        source = video_data.get('source', VideoSource.LOCAL)
        if isinstance(source, VideoSource):
            source = source.value
        index_key = self.INDEX_PATTERNS['source'].format(source)
        await pipe.sadd(index_key, video_id)
        
        # Índice de tipo
        video_type = video_data.get('type', 'mp4')
        index_key = self.INDEX_PATTERNS['type'].format(video_type)
        await pipe.sadd(index_key, video_id)
        
        # Índice por data (ano-mês)
        created_date = video_data.get('created_date', '')
        if created_date:
            try:
                date_key = created_date[:7]  # YYYY-MM
                index_key = self.INDEX_PATTERNS['date'].format(date_key)
                await pipe.sadd(index_key, video_id)
            except (ValueError, IndexError):
                pass
    
    async def _add_to_sorted_sets(self, pipe, video_id: str, video_data: Dict[str, Any]):
        """Adiciona vídeo aos conjuntos ordenados"""
        # Ordenação por data de criação
        created_date = video_data.get('created_date', '')
        if created_date:
            timestamp = self._to_timestamp(created_date)
            await pipe.zadd(self.SORT_PATTERNS['created'], {video_id: timestamp})
        
        # Ordenação por data de modificação
        modified_date = video_data.get('modified_date', created_date)
        if modified_date:
            timestamp = self._to_timestamp(modified_date)
            await pipe.zadd(self.SORT_PATTERNS['modified'], {video_id: timestamp})
        
        # Ordenação por tamanho
        size = video_data.get('size', 0)
        try:
            size_value = float(size)
            await pipe.zadd(self.SORT_PATTERNS['size'], {video_id: size_value})
        except (ValueError, TypeError):
            await pipe.zadd(self.SORT_PATTERNS['size'], {video_id: 0})
        
        # Ordenação por nome
        name = video_data.get('name', '')
        if name:
            name_score = self._calculate_name_score(name)
            await pipe.zadd(self.SORT_PATTERNS['name'], {video_id: name_score})
    
    async def _remove_from_indexes(self, pipe, video_id: str, video_data: Dict[str, Any]):
        """Remove vídeo de todos os índices"""
        # Remover de índice de fonte
        source = video_data.get('source', VideoSource.LOCAL)
        if isinstance(source, VideoSource):
            source = source.value
        index_key = self.INDEX_PATTERNS['source'].format(source)
        await pipe.srem(index_key, video_id)
        
        # Remover de índice de tipo
        video_type = video_data.get('type', 'mp4')
        index_key = self.INDEX_PATTERNS['type'].format(video_type)
        await pipe.srem(index_key, video_id)
        
        # Remover de índice de data
        created_date = video_data.get('created_date', '')
        if created_date:
            try:
                date_key = created_date[:7]
                index_key = self.INDEX_PATTERNS['date'].format(date_key)
                await pipe.srem(index_key, video_id)
            except (ValueError, IndexError):
                pass
    
    async def _remove_from_sorted_sets(self, pipe, video_id: str):
        """Remove vídeo de todos os conjuntos ordenados"""
        for sort_key in self.SORT_PATTERNS.values():
            await pipe.zrem(sort_key, video_id)
    
    async def _update_indexes(self, pipe, video_id: str, old_data: Dict[str, Any], new_data: Dict[str, Any]):
        """Atualiza índices quando dados são alterados"""
        # Atualizar fonte se mudou
        old_source = old_data.get('source', VideoSource.LOCAL)
        new_source = new_data.get('source', old_source)
        
        if isinstance(old_source, VideoSource):
            old_source = old_source.value
        if isinstance(new_source, VideoSource):
            new_source = new_source.value
        
        if old_source != new_source:
            # Remover do índice antigo
            old_index_key = self.INDEX_PATTERNS['source'].format(old_source)
            await pipe.srem(old_index_key, video_id)
            
            # Adicionar ao novo índice
            new_index_key = self.INDEX_PATTERNS['source'].format(new_source)
            await pipe.sadd(new_index_key, video_id)
        
        # Atualizar tipo se mudou
        old_type = old_data.get('type', 'mp4')
        new_type = new_data.get('type', old_type)
        
        if old_type != new_type:
            # Remover do índice antigo
            old_index_key = self.INDEX_PATTERNS['type'].format(old_type)
            await pipe.srem(old_index_key, video_id)
            
            # Adicionar ao novo índice
            new_index_key = self.INDEX_PATTERNS['type'].format(new_type)
            await pipe.sadd(new_index_key, video_id)
    
    async def _update_sorted_sets(self, pipe, video_id: str, old_data: Dict[str, Any], new_data: Dict[str, Any]):
        """Atualiza conjuntos ordenados quando dados são alterados"""
        # Atualizar ordenação por modificação sempre
        await pipe.zadd(self.SORT_PATTERNS['modified'], {video_id: time.time()})
        
        # Atualizar ordenação por tamanho se mudou
        old_size = old_data.get('size', 0)
        new_size = new_data.get('size', old_size)
        
        if old_size != new_size:
            try:
                await pipe.zadd(self.SORT_PATTERNS['size'], {video_id: float(new_size)})
            except (ValueError, TypeError):
                await pipe.zadd(self.SORT_PATTERNS['size'], {video_id: 0})
        
        # Atualizar ordenação por nome se mudou
        old_name = old_data.get('name', '')
        new_name = new_data.get('name', old_name)
        
        if old_name != new_name and new_name:
            name_score = self._calculate_name_score(new_name)
            await pipe.zadd(self.SORT_PATTERNS['name'], {video_id: name_score})
    
    async def _invalidate_caches(self, pipe):
        """Invalida todos os caches relacionados"""
        # Padrões de cache para invalidar
        cache_patterns = [
            'video:cache:scan:*',
            'video:cache:stats',
            'video:cache:all'
        ]
        
        redis_client = await self._get_redis()
        
        # Buscar e deletar chaves de cache
        for pattern in cache_patterns:
            cache_keys = []
            async for key in redis_client.scan_iter(match=pattern):
                cache_keys.append(key)
            
            if cache_keys:
                await pipe.delete(*cache_keys)


# Instância global do manager
redis_video_manager = RedisVideoManager()