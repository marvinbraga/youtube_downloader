"""
Redis Audio Manager - Gerenciador de Áudios usando Redis
Substitui completamente as operações JSON por Redis com performance superior
"""

import asyncio
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any, Union, Set

from loguru import logger

from app.services.redis_connection import get_redis_client, redis_manager
from app.services.configs import AUDIO_DIR


class RedisAudioManager:
    """
    Gerenciador de áudios usando Redis como backend de dados.
    Implementa todas as operações do sistema atual com performance superior.
    """
    
    def __init__(self):
        self._redis = None
        
        # Configurações de índices
        self.INDEX_PATTERNS = {
            'keyword': 'audio:index:keyword:{}',
            'status': 'audio:index:status:{}',
            'transcription_status': 'audio:index:transcription:{}',
            'format': 'audio:index:format:{}',
            'date': 'audio:index:date:{}',  # Por ano-mês
        }
        
        # Configurações de ordenação
        self.SORT_PATTERNS = {
            'created': 'audio:sorted:created',
            'modified': 'audio:sorted:modified',
            'filesize': 'audio:sorted:filesize',
            'title': 'audio:sorted:title',  # Score baseado em hash do título
        }
        
        # Configurações de cache
        self.CACHE_PATTERNS = {
            'search': 'audio:cache:search:{}',
            'stats': 'audio:cache:stats',
            'recent': 'audio:cache:recent',
        }
        
        # TTL padrão para cache (5 minutos)
        self.DEFAULT_CACHE_TTL = 300
    
    async def _get_redis(self):
        """Obtém cliente Redis lazy loading"""
        if self._redis is None:
            self._redis = await get_redis_client()
        return self._redis
    
    def _generate_audio_key(self, audio_id: str) -> str:
        """Gera chave Redis para áudio específico"""
        return f'audio:{audio_id}'
    
    def _extract_keywords(self, title: str) -> List[str]:
        """
        Extrai palavras-chave de um título para indexação
        
        Args:
            title: Título do áudio
            
        Returns:
            Lista de palavras-chave normalizadas
        """
        if not title:
            return []
        
        # Normalizar título
        normalized = re.sub(r'[^\w\s]', ' ', title.lower())
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        # Extrair palavras
        words = normalized.split()
        
        # Filtrar palavras muito curtas e stopwords básicas
        stopwords = {'de', 'da', 'do', 'em', 'na', 'no', 'com', 'por', 'para', 'uma', 'um', 'the', 'and', 'or', 'but'}
        keywords = [word for word in words if len(word) > 2 and word not in stopwords]
        
        # Adicionar título completo normalizado
        if normalized:
            keywords.append(normalized.replace(' ', '_'))
        
        return list(set(keywords))  # Remove duplicatas
    
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
    
    def _from_timestamp(self, timestamp: float) -> str:
        """
        Converte timestamp Unix para string ISO
        
        Args:
            timestamp: Timestamp Unix
            
        Returns:
            String de data em formato ISO
        """
        try:
            return datetime.fromtimestamp(timestamp).isoformat()
        except (ValueError, TypeError):
            return datetime.now().isoformat()
    
    def _calculate_title_score(self, title: str) -> float:
        """
        Calcula score para ordenação por título (baseado em hash)
        
        Args:
            title: Título do áudio
            
        Returns:
            Score numérico para ordenação
        """
        if not title:
            return 0.0
        
        # Usar hash do título normalizado para criar score consistente
        normalized = title.lower().strip()
        hash_value = hash(normalized)
        # Converter para float positivo entre 0 e 1
        return abs(hash_value) / (2**31)
    
    async def create_audio(self, audio_data: Dict[str, Any]) -> str:
        """
        Cria novo registro de áudio no Redis com todos os índices
        
        Args:
            audio_data: Dados do áudio
            
        Returns:
            ID do áudio criado
        """
        redis_client = await self._get_redis()
        
        try:
            audio_id = audio_data.get('id')
            if not audio_id:
                raise ValueError("ID do áudio é obrigatório")
            
            # Preparar dados para Redis
            redis_data = {}
            for key, value in audio_data.items():
                if isinstance(value, (list, dict)):
                    redis_data[key] = json.dumps(value, ensure_ascii=False)
                elif value is not None:
                    redis_data[key] = str(value)
            
            # Usar pipeline para operações atômicas
            async with redis_manager.get_pipeline(transaction=True) as pipe:
                audio_key = self._generate_audio_key(audio_id)
                
                # 1. Armazenar dados principais
                await pipe.hset(audio_key, mapping=redis_data)
                
                # 2. Adicionar aos índices
                await self._add_to_indexes(pipe, audio_id, audio_data)
                
                # 3. Adicionar às ordenações
                await self._add_to_sorted_sets(pipe, audio_id, audio_data)
                
                # 4. Atualizar estatísticas
                await pipe.hincrby('audio:stats', 'total_count', 1)
                if audio_data.get('filesize'):
                    await pipe.hincrby('audio:stats', 'total_size', int(audio_data['filesize']))
                
                # 5. Invalidar caches relacionados
                await self._invalidate_caches(pipe)
                
                # Executar pipeline
                await pipe.execute()
            
            logger.info(f"Áudio criado no Redis: {audio_id}")
            return audio_id
            
        except Exception as e:
            logger.error(f"Erro ao criar áudio no Redis: {str(e)}")
            raise
    
    async def get_audio(self, audio_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtém dados de um áudio pelo ID
        
        Args:
            audio_id: ID do áudio
            
        Returns:
            Dados do áudio ou None se não encontrado
        """
        redis_client = await self._get_redis()
        
        try:
            audio_key = self._generate_audio_key(audio_id)
            audio_data = await redis_client.hgetall(audio_key)
            
            if not audio_data:
                return None
            
            # Converter dados Redis de volta para Python
            result = {}
            for key, value in audio_data.items():
                key = key.decode() if isinstance(key, bytes) else key
                value = value.decode() if isinstance(value, bytes) else value
                
                # Tentar deserializar JSON para listas/dicts
                if key in ['keywords']:
                    try:
                        result[key] = json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        result[key] = []
                else:
                    result[key] = value
            
            return result
            
        except Exception as e:
            logger.error(f"Erro ao obter áudio do Redis: {str(e)}")
            return None
    
    async def update_audio(self, audio_id: str, updates: Dict[str, Any]) -> bool:
        """
        Atualiza dados de um áudio existente
        
        Args:
            audio_id: ID do áudio
            updates: Dados a serem atualizados
            
        Returns:
            True se atualizado com sucesso
        """
        redis_client = await self._get_redis()
        
        try:
            audio_key = self._generate_audio_key(audio_id)
            
            # Verificar se áudio existe
            exists = await redis_client.exists(audio_key)
            if not exists:
                logger.warning(f"Áudio não encontrado para atualização: {audio_id}")
                return False
            
            # Obter dados atuais para comparação de índices
            current_data = await self.get_audio(audio_id)
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
                await pipe.hset(audio_key, mapping=redis_updates)
                
                # 2. Atualizar índices se necessário
                merged_data = {**current_data, **updates}
                await self._update_indexes(pipe, audio_id, current_data, merged_data)
                
                # 3. Atualizar ordenações
                await self._update_sorted_sets(pipe, audio_id, current_data, merged_data)
                
                # 4. Invalidar caches
                await self._invalidate_caches(pipe)
                
                await pipe.execute()
            
            logger.info(f"Áudio atualizado no Redis: {audio_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao atualizar áudio no Redis: {str(e)}")
            return False
    
    async def delete_audio(self, audio_id: str) -> bool:
        """
        Remove um áudio completamente do Redis
        
        Args:
            audio_id: ID do áudio
            
        Returns:
            True se removido com sucesso
        """
        redis_client = await self._get_redis()
        
        try:
            # Obter dados antes de deletar para limpar índices
            audio_data = await self.get_audio(audio_id)
            if not audio_data:
                logger.warning(f"Áudio não encontrado para remoção: {audio_id}")
                return False
            
            async with redis_manager.get_pipeline(transaction=True) as pipe:
                audio_key = self._generate_audio_key(audio_id)
                
                # 1. Remover dados principais
                await pipe.delete(audio_key)
                
                # 2. Remover de todos os índices
                await self._remove_from_indexes(pipe, audio_id, audio_data)
                
                # 3. Remover das ordenações
                await self._remove_from_sorted_sets(pipe, audio_id)
                
                # 4. Atualizar estatísticas
                await pipe.hincrby('audio:stats', 'total_count', -1)
                if audio_data.get('filesize'):
                    await pipe.hincrby('audio:stats', 'total_size', -int(audio_data['filesize']))
                
                # 5. Invalidar caches
                await self._invalidate_caches(pipe)
                
                await pipe.execute()
            
            logger.info(f"Áudio removido do Redis: {audio_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao remover áudio do Redis: {str(e)}")
            return False
    
    async def search_by_keyword(self, keyword: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Busca áudios por palavra-chave com cache
        
        Args:
            keyword: Palavra-chave para busca
            limit: Limite de resultados (opcional)
            
        Returns:
            Lista de áudios encontrados
        """
        redis_client = await self._get_redis()
        
        try:
            # Normalizar keyword
            normalized_keyword = keyword.lower().strip()
            cache_key = self.CACHE_PATTERNS['search'].format(f"{normalized_keyword}:{limit or 'all'}")
            
            # Verificar cache primeiro
            cached_result = await redis_client.get(cache_key)
            if cached_result:
                try:
                    cached_data = json.loads(cached_result.decode())
                    logger.debug(f"Cache hit para busca: {normalized_keyword}")
                    return cached_data
                except (json.JSONDecodeError, AttributeError):
                    # Cache corrompido, seguir com busca normal
                    pass
            
            # Buscar nos índices
            index_key = self.INDEX_PATTERNS['keyword'].format(normalized_keyword)
            audio_ids = await redis_client.smembers(index_key)
            
            if not audio_ids:
                # Cache resultado vazio por tempo menor
                await redis_client.setex(cache_key, 60, json.dumps([]))
                return []
            
            # Converter bytes para string se necessário
            if audio_ids and isinstance(next(iter(audio_ids)), bytes):
                audio_ids = [aid.decode() for aid in audio_ids]
            
            # Aplicar limite se especificado
            if limit:
                audio_ids = list(audio_ids)[:limit]
            
            # Carregar dados dos áudios
            results = []
            async with redis_manager.get_pipeline(transaction=False) as pipe:
                for audio_id in audio_ids:
                    audio_key = self._generate_audio_key(audio_id)
                    await pipe.hgetall(audio_key)
                
                audio_data_list = await pipe.execute()
            
            # Processar resultados
            for i, audio_data in enumerate(audio_data_list):
                if audio_data:
                    processed_audio = {}
                    for key, value in audio_data.items():
                        key = key.decode() if isinstance(key, bytes) else key
                        value = value.decode() if isinstance(value, bytes) else value
                        
                        if key == 'keywords':
                            try:
                                processed_audio[key] = json.loads(value)
                            except (json.JSONDecodeError, TypeError):
                                processed_audio[key] = []
                        else:
                            processed_audio[key] = value
                    
                    processed_audio['id'] = audio_ids[i]
                    results.append(processed_audio)
            
            # Ordenar por data de modificação (mais recente primeiro)
            results.sort(key=lambda x: x.get('modified_date', ''), reverse=True)
            
            # Cache resultado
            await redis_client.setex(cache_key, self.DEFAULT_CACHE_TTL, 
                                   json.dumps(results, ensure_ascii=False))
            
            logger.debug(f"Busca por keyword '{normalized_keyword}' retornou {len(results)} resultados")
            return results
            
        except Exception as e:
            logger.error(f"Erro na busca por keyword: {str(e)}")
            return []
    
    async def get_all_audios(self, sort_by: str = 'modified', limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Obtém todos os áudios com ordenação
        
        Args:
            sort_by: Campo para ordenação ('created', 'modified', 'filesize', 'title')
            limit: Limite de resultados (opcional)
            
        Returns:
            Lista de todos os áudios ordenados
        """
        redis_client = await self._get_redis()
        
        try:
            # Verificar cache
            cache_key = self.CACHE_PATTERNS['recent'] if not limit else f"audio:cache:all:{sort_by}:{limit}"
            cached_result = await redis_client.get(cache_key)
            
            if cached_result and not limit:  # Cache apenas para consultas completas
                try:
                    return json.loads(cached_result.decode())
                except (json.JSONDecodeError, AttributeError):
                    pass
            
            # Obter IDs ordenados
            sort_key = self.SORT_PATTERNS.get(sort_by, self.SORT_PATTERNS['modified'])
            
            if sort_by in ['created', 'modified', 'filesize']:
                # Ordenação numérica (maior para menor)
                audio_ids = await redis_client.zrevrange(sort_key, 0, limit - 1 if limit else -1)
            else:
                # Ordenação por título (menor para maior)
                audio_ids = await redis_client.zrange(sort_key, 0, limit - 1 if limit else -1)
            
            if not audio_ids:
                return []
            
            # Converter bytes para string se necessário
            if isinstance(next(iter(audio_ids)), bytes):
                audio_ids = [aid.decode() for aid in audio_ids]
            
            # Carregar dados dos áudios
            results = []
            async with redis_manager.get_pipeline(transaction=False) as pipe:
                for audio_id in audio_ids:
                    audio_key = self._generate_audio_key(audio_id)
                    await pipe.hgetall(audio_key)
                
                audio_data_list = await pipe.execute()
            
            # Processar resultados
            for i, audio_data in enumerate(audio_data_list):
                if audio_data:
                    processed_audio = {}
                    for key, value in audio_data.items():
                        key = key.decode() if isinstance(key, bytes) else key
                        value = value.decode() if isinstance(value, bytes) else value
                        
                        if key == 'keywords':
                            try:
                                processed_audio[key] = json.loads(value)
                            except (json.JSONDecodeError, TypeError):
                                processed_audio[key] = []
                        else:
                            processed_audio[key] = value
                    
                    processed_audio['id'] = audio_ids[i]
                    results.append(processed_audio)
            
            # Cache resultado apenas se for consulta completa
            if not limit:
                await redis_client.setex(cache_key, self.DEFAULT_CACHE_TTL, 
                                       json.dumps(results, ensure_ascii=False))
            
            logger.debug(f"Retornando {len(results)} áudios ordenados por {sort_by}")
            return results
            
        except Exception as e:
            logger.error(f"Erro ao obter todos os áudios: {str(e)}")
            return []
    
    async def get_by_status(self, status: str, status_type: str = 'transcription') -> List[Dict[str, Any]]:
        """
        Obtém áudios por status específico
        
        Args:
            status: Status a buscar ('none', 'started', 'ended', 'error', etc.)
            status_type: Tipo de status ('transcription', 'download')
            
        Returns:
            Lista de áudios com o status especificado
        """
        redis_client = await self._get_redis()
        
        try:
            # Determinar chave do índice
            if status_type == 'transcription':
                index_key = self.INDEX_PATTERNS['transcription_status'].format(status)
            else:
                index_key = self.INDEX_PATTERNS['status'].format(status)
            
            # Obter IDs dos áudios
            audio_ids = await redis_client.smembers(index_key)
            
            if not audio_ids:
                return []
            
            # Converter bytes para string se necessário
            if isinstance(next(iter(audio_ids)), bytes):
                audio_ids = [aid.decode() for aid in audio_ids]
            
            # Carregar dados
            results = []
            for audio_id in audio_ids:
                audio_data = await self.get_audio(audio_id)
                if audio_data:
                    results.append(audio_data)
            
            # Ordenar por data de modificação
            results.sort(key=lambda x: x.get('modified_date', ''), reverse=True)
            
            logger.debug(f"Retornando {len(results)} áudios com status '{status}' ({status_type})")
            return results
            
        except Exception as e:
            logger.error(f"Erro ao obter áudios por status: {str(e)}")
            return []
    
    async def update_transcription_status(self, audio_id: str, status: str, transcription_path: str = None) -> bool:
        """
        Atualiza status de transcrição com manutenção de índices
        
        Args:
            audio_id: ID do áudio
            status: Novo status ('none', 'started', 'ended', 'error')
            transcription_path: Caminho do arquivo de transcrição (opcional)
            
        Returns:
            True se atualizado com sucesso
        """
        redis_client = await self._get_redis()
        
        try:
            # Validar status
            valid_statuses = ['none', 'started', 'ended', 'error']
            if status not in valid_statuses:
                logger.error(f"Status inválido: {status}. Deve ser um de: {valid_statuses}")
                return False
            
            # Obter dados atuais
            current_data = await self.get_audio(audio_id)
            if not current_data:
                logger.warning(f"Áudio não encontrado para atualização de status: {audio_id}")
                return False
            
            old_status = current_data.get('transcription_status', 'none')
            
            # Preparar updates
            updates = {
                'transcription_status': status,
                'modified_date': datetime.now().isoformat()
            }
            
            if transcription_path:
                updates['transcription_path'] = transcription_path
            
            # Se status for 'ended', marcar como tendo transcrição
            if status == 'ended':
                updates['has_transcription'] = 'true'
            elif status == 'none':
                updates['has_transcription'] = 'false'
            
            async with redis_manager.get_pipeline(transaction=True) as pipe:
                audio_key = self._generate_audio_key(audio_id)
                
                # 1. Atualizar dados principais
                await pipe.hset(audio_key, mapping=updates)
                
                # 2. Atualizar índices de status de transcrição
                if old_status != status:
                    # Remover do índice antigo
                    if old_status:
                        old_index_key = self.INDEX_PATTERNS['transcription_status'].format(old_status)
                        await pipe.srem(old_index_key, audio_id)
                    
                    # Adicionar ao novo índice
                    new_index_key = self.INDEX_PATTERNS['transcription_status'].format(status)
                    await pipe.sadd(new_index_key, audio_id)
                
                # 3. Atualizar ordenação por data modificada
                modified_timestamp = time.time()
                await pipe.zadd(self.SORT_PATTERNS['modified'], {audio_id: modified_timestamp})
                
                # 4. Invalidar caches
                await self._invalidate_caches(pipe)
                
                await pipe.execute()
            
            logger.info(f"Status de transcrição atualizado para '{status}' no áudio {audio_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao atualizar status de transcrição: {str(e)}")
            return False
    
    async def get_statistics(self) -> Dict[str, Any]:
        """
        Obtém estatísticas dos áudios
        
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
            basic_stats = await redis_client.hgetall('audio:stats')
            for key, value in basic_stats.items():
                key = key.decode() if isinstance(key, bytes) else key
                value = value.decode() if isinstance(value, bytes) else value
                stats[key] = int(value) if value.isdigit() else value
            
            # Contadores por status de transcrição
            transcription_statuses = ['none', 'started', 'ended', 'error']
            for status in transcription_statuses:
                index_key = self.INDEX_PATTERNS['transcription_status'].format(status)
                count = await redis_client.scard(index_key)
                stats[f'transcription_{status}'] = count
            
            # Contadores por formato
            formats = ['m4a', 'mp3', 'wav']
            for format_type in formats:
                index_key = self.INDEX_PATTERNS['format'].format(format_type)
                count = await redis_client.scard(index_key)
                stats[f'format_{format_type}'] = count
            
            # Adicionar timestamp
            stats['last_updated'] = datetime.now().isoformat()
            
            # Cache por 2 minutos
            await redis_client.setex(cache_key, 120, json.dumps(stats, ensure_ascii=False))
            
            return stats
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {str(e)}")
            return {}
    
    async def _add_to_indexes(self, pipe, audio_id: str, audio_data: Dict[str, Any]):
        """Adiciona áudio aos índices"""
        # Índice de keywords
        keywords = audio_data.get('keywords', [])
        if isinstance(keywords, str):
            try:
                keywords = json.loads(keywords)
            except json.JSONDecodeError:
                keywords = []
        
        for keyword in keywords:
            index_key = self.INDEX_PATTERNS['keyword'].format(keyword.lower())
            await pipe.sadd(index_key, audio_id)
        
        # Índice de status de transcrição
        transcription_status = audio_data.get('transcription_status', 'none')
        index_key = self.INDEX_PATTERNS['transcription_status'].format(transcription_status)
        await pipe.sadd(index_key, audio_id)
        
        # Índice de formato
        format_type = audio_data.get('format', 'm4a')
        index_key = self.INDEX_PATTERNS['format'].format(format_type)
        await pipe.sadd(index_key, audio_id)
        
        # Índice por data (ano-mês)
        created_date = audio_data.get('created_date', '')
        if created_date:
            try:
                date_key = created_date[:7]  # YYYY-MM
                index_key = self.INDEX_PATTERNS['date'].format(date_key)
                await pipe.sadd(index_key, audio_id)
            except (ValueError, IndexError):
                pass
    
    async def _add_to_sorted_sets(self, pipe, audio_id: str, audio_data: Dict[str, Any]):
        """Adiciona áudio aos conjuntos ordenados"""
        # Ordenação por data de criação
        created_date = audio_data.get('created_date', '')
        if created_date:
            timestamp = self._to_timestamp(created_date)
            await pipe.zadd(self.SORT_PATTERNS['created'], {audio_id: timestamp})
        
        # Ordenação por data de modificação
        modified_date = audio_data.get('modified_date', created_date)
        if modified_date:
            timestamp = self._to_timestamp(modified_date)
            await pipe.zadd(self.SORT_PATTERNS['modified'], {audio_id: timestamp})
        
        # Ordenação por tamanho
        filesize = audio_data.get('filesize', 0)
        try:
            size_value = float(filesize)
            await pipe.zadd(self.SORT_PATTERNS['filesize'], {audio_id: size_value})
        except (ValueError, TypeError):
            await pipe.zadd(self.SORT_PATTERNS['filesize'], {audio_id: 0})
        
        # Ordenação por título
        title = audio_data.get('title', '')
        if title:
            title_score = self._calculate_title_score(title)
            await pipe.zadd(self.SORT_PATTERNS['title'], {audio_id: title_score})
    
    async def _remove_from_indexes(self, pipe, audio_id: str, audio_data: Dict[str, Any]):
        """Remove áudio de todos os índices"""
        # Remover de índices de keywords
        keywords = audio_data.get('keywords', [])
        if isinstance(keywords, list):
            for keyword in keywords:
                index_key = self.INDEX_PATTERNS['keyword'].format(keyword.lower())
                await pipe.srem(index_key, audio_id)
        
        # Remover de índice de status
        transcription_status = audio_data.get('transcription_status', 'none')
        index_key = self.INDEX_PATTERNS['transcription_status'].format(transcription_status)
        await pipe.srem(index_key, audio_id)
        
        # Remover de índice de formato
        format_type = audio_data.get('format', 'm4a')
        index_key = self.INDEX_PATTERNS['format'].format(format_type)
        await pipe.srem(index_key, audio_id)
        
        # Remover de índice de data
        created_date = audio_data.get('created_date', '')
        if created_date:
            try:
                date_key = created_date[:7]
                index_key = self.INDEX_PATTERNS['date'].format(date_key)
                await pipe.srem(index_key, audio_id)
            except (ValueError, IndexError):
                pass
    
    async def _remove_from_sorted_sets(self, pipe, audio_id: str):
        """Remove áudio de todos os conjuntos ordenados"""
        for sort_key in self.SORT_PATTERNS.values():
            await pipe.zrem(sort_key, audio_id)
    
    async def _update_indexes(self, pipe, audio_id: str, old_data: Dict[str, Any], new_data: Dict[str, Any]):
        """Atualiza índices quando dados são alterados"""
        # Atualizar keywords se mudaram
        old_keywords = set(old_data.get('keywords', []))
        new_keywords = set(new_data.get('keywords', []))
        
        # Remover keywords antigas
        for keyword in old_keywords - new_keywords:
            index_key = self.INDEX_PATTERNS['keyword'].format(keyword.lower())
            await pipe.srem(index_key, audio_id)
        
        # Adicionar keywords novas
        for keyword in new_keywords - old_keywords:
            index_key = self.INDEX_PATTERNS['keyword'].format(keyword.lower())
            await pipe.sadd(index_key, audio_id)
        
        # Atualizar status de transcrição se mudou
        old_status = old_data.get('transcription_status', 'none')
        new_status = new_data.get('transcription_status', old_status)
        
        if old_status != new_status:
            # Remover do índice antigo
            old_index_key = self.INDEX_PATTERNS['transcription_status'].format(old_status)
            await pipe.srem(old_index_key, audio_id)
            
            # Adicionar ao novo índice
            new_index_key = self.INDEX_PATTERNS['transcription_status'].format(new_status)
            await pipe.sadd(new_index_key, audio_id)
    
    async def _update_sorted_sets(self, pipe, audio_id: str, old_data: Dict[str, Any], new_data: Dict[str, Any]):
        """Atualiza conjuntos ordenados quando dados são alterados"""
        # Atualizar ordenação por modificação sempre
        await pipe.zadd(self.SORT_PATTERNS['modified'], {audio_id: time.time()})
        
        # Atualizar ordenação por tamanho se mudou
        old_size = old_data.get('filesize', 0)
        new_size = new_data.get('filesize', old_size)
        
        if old_size != new_size:
            try:
                await pipe.zadd(self.SORT_PATTERNS['filesize'], {audio_id: float(new_size)})
            except (ValueError, TypeError):
                await pipe.zadd(self.SORT_PATTERNS['filesize'], {audio_id: 0})
        
        # Atualizar ordenação por título se mudou
        old_title = old_data.get('title', '')
        new_title = new_data.get('title', old_title)
        
        if old_title != new_title and new_title:
            title_score = self._calculate_title_score(new_title)
            await pipe.zadd(self.SORT_PATTERNS['title'], {audio_id: title_score})
    
    async def _invalidate_caches(self, pipe):
        """Invalida todos os caches relacionados"""
        # Padrões de cache para invalidar
        cache_patterns = [
            'audio:cache:search:*',
            'audio:cache:stats',
            'audio:cache:recent',
            'audio:cache:all:*'
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
redis_audio_manager = RedisAudioManager()