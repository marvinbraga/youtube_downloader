"""
Testes unitários para RedisAudioManager
Cobertura completa de todas as funcionalidades do gerenciador de áudios
"""

import asyncio
import json
import pytest
import time
from datetime import datetime
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.redis_audio_manager import RedisAudioManager


@pytest.mark.unit
@pytest.mark.asyncio
class TestRedisAudioManager:
    """Testes unitários para RedisAudioManager"""
    
    async def test_initialization(self):
        """Testa inicialização do manager"""
        manager = RedisAudioManager()
        
        assert manager._redis is None
        assert 'keyword' in manager.INDEX_PATTERNS
        assert 'created' in manager.SORT_PATTERNS
        assert 'search' in manager.CACHE_PATTERNS
        assert manager.DEFAULT_CACHE_TTL == 300
    
    async def test_generate_audio_key(self):
        """Testa geração de chave Redis"""
        manager = RedisAudioManager()
        
        audio_id = "test_audio_123"
        expected_key = "audio:test_audio_123"
        
        result = manager._generate_audio_key(audio_id)
        assert result == expected_key
    
    async def test_extract_keywords(self):
        """Testa extração de palavras-chave"""
        manager = RedisAudioManager()
        
        # Teste básico
        title = "Como Aprender Python Rapidamente"
        keywords = manager._extract_keywords(title)
        
        expected = ["como", "aprender", "python", "rapidamente", "como_aprender_python_rapidamente"]
        assert set(keywords) == set(expected)
        
        # Teste com caracteres especiais
        title_special = "Tutorial: Machine Learning & AI - Parte 1"
        keywords_special = manager._extract_keywords(title_special)
        
        assert "tutorial" in keywords_special
        assert "machine" in keywords_special
        assert "learning" in keywords_special
        
        # Teste com título vazio
        assert manager._extract_keywords("") == []
        assert manager._extract_keywords(None) == []
    
    async def test_to_timestamp_conversion(self):
        """Testa conversão de data para timestamp"""
        manager = RedisAudioManager()
        
        # Teste com ISO format
        iso_date = "2024-08-25T10:00:00"
        timestamp = manager._to_timestamp(iso_date)
        
        assert isinstance(timestamp, float)
        assert timestamp > 0
        
        # Teste com formato inválido
        invalid_date = "invalid_date"
        timestamp_invalid = manager._to_timestamp(invalid_date)
        
        # Deve retornar timestamp atual para datas inválidas
        current_time = time.time()
        assert abs(timestamp_invalid - current_time) < 60  # Diferença menor que 1 minuto
    
    async def test_from_timestamp_conversion(self):
        """Testa conversão de timestamp para ISO"""
        manager = RedisAudioManager()
        
        timestamp = 1692955200.0  # 2023-08-25T10:00:00
        iso_date = manager._from_timestamp(timestamp)
        
        assert isinstance(iso_date, str)
        assert "2023-08-25" in iso_date
        assert "10:00:00" in iso_date
        
        # Teste com timestamp inválido
        invalid_timestamp = "invalid"
        iso_invalid = manager._from_timestamp(invalid_timestamp)
        
        # Deve retornar data atual para timestamps inválidos
        assert isinstance(iso_invalid, str)
        assert len(iso_invalid) > 10
    
    async def test_calculate_title_score(self):
        """Testa cálculo de score por título"""
        manager = RedisAudioManager()
        
        title1 = "Python Tutorial"
        title2 = "JavaScript Guide"
        title3 = ""
        
        score1 = manager._calculate_title_score(title1)
        score2 = manager._calculate_title_score(title2)
        score3 = manager._calculate_title_score(title3)
        
        assert 0 <= score1 <= 1
        assert 0 <= score2 <= 1
        assert score3 == 0.0
        
        # Títulos iguais devem ter scores iguais
        score1_repeat = manager._calculate_title_score(title1)
        assert score1 == score1_repeat
    
    async def test_create_audio_success(self, redis_audio_manager, sample_audio_data):
        """Testa criação de áudio com sucesso"""
        manager = redis_audio_manager
        
        # Mock do pipeline
        mock_pipeline = AsyncMock()
        manager.redis_manager = MagicMock()
        manager.redis_manager.get_pipeline.return_value.__aenter__.return_value = mock_pipeline
        manager.redis_manager.get_pipeline.return_value.__aexit__.return_value = None
        
        # Executar criação
        result = await manager.create_audio(sample_audio_data)
        
        # Verificações
        assert result == sample_audio_data["id"]
        mock_pipeline.hset.assert_called()
        mock_pipeline.execute.assert_called()
    
    async def test_create_audio_missing_id(self, redis_audio_manager):
        """Testa criação de áudio sem ID"""
        manager = redis_audio_manager
        
        audio_data_no_id = {
            "title": "Test Audio",
            "url": "https://test.com"
        }
        
        with pytest.raises(ValueError, match="ID do áudio é obrigatório"):
            await manager.create_audio(audio_data_no_id)
    
    async def test_get_audio_success(self, redis_audio_manager, sample_audio_data):
        """Testa obtenção de áudio com sucesso"""
        manager = redis_audio_manager
        
        # Mock redis response
        redis_response = {
            b'id': b'test_audio_123',
            b'title': b'Test Audio Title',
            b'url': b'https://youtube.com/watch?v=test123',
            b'duration': b'300',
            b'keywords': b'["test", "audio"]'
        }
        
        manager._redis.hgetall.return_value = redis_response
        
        result = await manager.get_audio(sample_audio_data["id"])
        
        assert result is not None
        assert result["id"] == "test_audio_123"
        assert result["title"] == "Test Audio Title"
        assert result["keywords"] == ["test", "audio"]
    
    async def test_get_audio_not_found(self, redis_audio_manager):
        """Testa obtenção de áudio não encontrado"""
        manager = redis_audio_manager
        
        manager._redis.hgetall.return_value = {}
        
        result = await manager.get_audio("nonexistent_id")
        assert result is None
    
    async def test_update_audio_success(self, redis_audio_manager, sample_audio_data):
        """Testa atualização de áudio com sucesso"""
        manager = redis_audio_manager
        
        # Mock existing audio
        manager.get_audio = AsyncMock(return_value=sample_audio_data)
        manager._redis.exists.return_value = True
        
        # Mock pipeline
        mock_pipeline = AsyncMock()
        manager.redis_manager = MagicMock()
        manager.redis_manager.get_pipeline.return_value.__aenter__.return_value = mock_pipeline
        manager.redis_manager.get_pipeline.return_value.__aexit__.return_value = None
        
        updates = {"title": "Updated Title", "duration": 400}
        
        result = await manager.update_audio(sample_audio_data["id"], updates)
        
        assert result is True
        mock_pipeline.hset.assert_called()
        mock_pipeline.execute.assert_called()
    
    async def test_update_audio_not_found(self, redis_audio_manager):
        """Testa atualização de áudio não encontrado"""
        manager = redis_audio_manager
        
        manager._redis.exists.return_value = False
        
        result = await manager.update_audio("nonexistent_id", {"title": "New Title"})
        assert result is False
    
    async def test_delete_audio_success(self, redis_audio_manager, sample_audio_data):
        """Testa remoção de áudio com sucesso"""
        manager = redis_audio_manager
        
        # Mock existing audio
        manager.get_audio = AsyncMock(return_value=sample_audio_data)
        
        # Mock pipeline
        mock_pipeline = AsyncMock()
        manager.redis_manager = MagicMock()
        manager.redis_manager.get_pipeline.return_value.__aenter__.return_value = mock_pipeline
        manager.redis_manager.get_pipeline.return_value.__aexit__.return_value = None
        
        result = await manager.delete_audio(sample_audio_data["id"])
        
        assert result is True
        mock_pipeline.delete.assert_called()
        mock_pipeline.execute.assert_called()
    
    async def test_delete_audio_not_found(self, redis_audio_manager):
        """Testa remoção de áudio não encontrado"""
        manager = redis_audio_manager
        
        manager.get_audio = AsyncMock(return_value=None)
        
        result = await manager.delete_audio("nonexistent_id")
        assert result is False
    
    async def test_search_by_keyword_with_cache_hit(self, redis_audio_manager):
        """Testa busca por palavra-chave com cache hit"""
        manager = redis_audio_manager
        
        # Mock cache hit
        cached_data = [{"id": "audio1", "title": "Cached Audio"}]
        manager._redis.get.return_value = json.dumps(cached_data).encode()
        
        result = await manager.search_by_keyword("python")
        
        assert result == cached_data
        manager._redis.get.assert_called()
    
    async def test_search_by_keyword_with_cache_miss(self, redis_audio_manager):
        """Testa busca por palavra-chave com cache miss"""
        manager = redis_audio_manager
        
        # Mock cache miss
        manager._redis.get.return_value = None
        
        # Mock search results
        audio_ids = [b"audio1", b"audio2"]
        manager._redis.smembers.return_value = audio_ids
        
        # Mock pipeline for data loading
        mock_pipeline = AsyncMock()
        audio_data = [
            {b'id': b'audio1', b'title': b'Audio 1'},
            {b'id': b'audio2', b'title': b'Audio 2'}
        ]
        mock_pipeline.execute.return_value = audio_data
        
        manager.redis_manager = MagicMock()
        manager.redis_manager.get_pipeline.return_value.__aenter__.return_value = mock_pipeline
        manager.redis_manager.get_pipeline.return_value.__aexit__.return_value = None
        
        result = await manager.search_by_keyword("python")
        
        assert len(result) == 2
        manager._redis.smembers.assert_called()
        manager._redis.setex.assert_called()  # Cache result
    
    async def test_search_by_keyword_no_results(self, redis_audio_manager):
        """Testa busca por palavra-chave sem resultados"""
        manager = redis_audio_manager
        
        manager._redis.get.return_value = None
        manager._redis.smembers.return_value = set()
        
        result = await manager.search_by_keyword("nonexistent")
        
        assert result == []
        manager._redis.setex.assert_called()  # Cache empty result
    
    async def test_get_all_audios_with_sorting(self, redis_audio_manager):
        """Testa obtenção de todos os áudios com ordenação"""
        manager = redis_audio_manager
        
        # Mock cache miss
        manager._redis.get.return_value = None
        
        # Mock sorted results
        audio_ids = [b"audio1", b"audio2"]
        manager._redis.zrevrange.return_value = audio_ids
        
        # Mock pipeline for data loading
        mock_pipeline = AsyncMock()
        audio_data = [
            {b'id': b'audio1', b'title': b'Audio 1', b'modified_date': b'2024-08-25T10:00:00'},
            {b'id': b'audio2', b'title': b'Audio 2', b'modified_date': b'2024-08-24T10:00:00'}
        ]
        mock_pipeline.execute.return_value = audio_data
        
        manager.redis_manager = MagicMock()
        manager.redis_manager.get_pipeline.return_value.__aenter__.return_value = mock_pipeline
        manager.redis_manager.get_pipeline.return_value.__aexit__.return_value = None
        
        result = await manager.get_all_audios(sort_by="modified", limit=2)
        
        assert len(result) == 2
        manager._redis.zrevrange.assert_called()
    
    async def test_get_by_status_transcription(self, redis_audio_manager):
        """Testa obtenção por status de transcrição"""
        manager = redis_audio_manager
        
        # Mock audio IDs with status
        audio_ids = [b"audio1", b"audio2"]
        manager._redis.smembers.return_value = audio_ids
        
        # Mock get_audio calls
        audio_data1 = {"id": "audio1", "transcription_status": "ended"}
        audio_data2 = {"id": "audio2", "transcription_status": "ended"}
        manager.get_audio = AsyncMock(side_effect=[audio_data1, audio_data2])
        
        result = await manager.get_by_status("ended", "transcription")
        
        assert len(result) == 2
        assert all(audio["transcription_status"] == "ended" for audio in result)
    
    async def test_update_transcription_status_success(self, redis_audio_manager, sample_audio_data):
        """Testa atualização de status de transcrição com sucesso"""
        manager = redis_audio_manager
        
        # Mock existing audio
        manager.get_audio = AsyncMock(return_value=sample_audio_data)
        
        # Mock pipeline
        mock_pipeline = AsyncMock()
        manager.redis_manager = MagicMock()
        manager.redis_manager.get_pipeline.return_value.__aenter__.return_value = mock_pipeline
        manager.redis_manager.get_pipeline.return_value.__aexit__.return_value = None
        
        result = await manager.update_transcription_status(
            sample_audio_data["id"], 
            "ended", 
            "/path/to/transcription.txt"
        )
        
        assert result is True
        mock_pipeline.hset.assert_called()
        mock_pipeline.execute.assert_called()
    
    async def test_update_transcription_status_invalid_status(self, redis_audio_manager):
        """Testa atualização com status inválido"""
        manager = redis_audio_manager
        
        result = await manager.update_transcription_status("audio_id", "invalid_status")
        assert result is False
    
    async def test_get_statistics_with_cache(self, redis_audio_manager):
        """Testa obtenção de estatísticas com cache"""
        manager = redis_audio_manager
        
        # Mock cached stats
        cached_stats = {
            "total_count": 100,
            "total_size": 1048576,
            "transcription_ended": 50
        }
        manager._redis.get.return_value = json.dumps(cached_stats).encode()
        
        result = await manager.get_statistics()
        
        assert result == cached_stats
        manager._redis.get.assert_called()
    
    async def test_get_statistics_without_cache(self, redis_audio_manager):
        """Testa obtenção de estatísticas sem cache"""
        manager = redis_audio_manager
        
        # Mock cache miss
        manager._redis.get.return_value = None
        
        # Mock basic stats
        basic_stats = {b'total_count': b'100', b'total_size': b'1048576'}
        manager._redis.hgetall.return_value = basic_stats
        
        # Mock status counts
        manager._redis.scard.return_value = 25
        
        result = await manager.get_statistics()
        
        assert result["total_count"] == 100
        assert result["total_size"] == 1048576
        assert "transcription_none" in result
        assert "last_updated" in result
        
        manager._redis.setex.assert_called()  # Cache result
    
    @pytest.mark.parametrize("sort_by,expected_method", [
        ("created", "zrevrange"),
        ("modified", "zrevrange"), 
        ("filesize", "zrevrange"),
        ("title", "zrange")
    ])
    async def test_sorting_methods(self, redis_audio_manager, sort_by, expected_method):
        """Testa diferentes métodos de ordenação"""
        manager = redis_audio_manager
        
        manager._redis.get.return_value = None
        manager._redis.zrevrange.return_value = []
        manager._redis.zrange.return_value = []
        
        await manager.get_all_audios(sort_by=sort_by)
        
        if expected_method == "zrevrange":
            manager._redis.zrevrange.assert_called()
        else:
            manager._redis.zrange.assert_called()
    
    async def test_error_handling_create_audio(self, redis_audio_manager, sample_audio_data):
        """Testa tratamento de erros na criação de áudio"""
        manager = redis_audio_manager
        
        # Mock pipeline error
        mock_pipeline = AsyncMock()
        mock_pipeline.execute.side_effect = Exception("Redis error")
        
        manager.redis_manager = MagicMock()
        manager.redis_manager.get_pipeline.return_value.__aenter__.return_value = mock_pipeline
        manager.redis_manager.get_pipeline.return_value.__aexit__.return_value = None
        
        with pytest.raises(Exception):
            await manager.create_audio(sample_audio_data)
    
    async def test_error_handling_get_audio(self, redis_audio_manager):
        """Testa tratamento de erros na obtenção de áudio"""
        manager = redis_audio_manager
        
        manager._redis.hgetall.side_effect = Exception("Redis error")
        
        result = await manager.get_audio("test_id")
        assert result is None
    
    async def test_complex_keyword_extraction(self):
        """Testa extração complexa de palavras-chave"""
        manager = RedisAudioManager()
        
        complex_titles = [
            "Python 3.9: Novidades e Recursos Avançados",
            "Machine Learning com TensorFlow 2.0 - Tutorial Completo",
            "React.js vs Vue.js: Comparação Detalhada (2024)",
            "Como criar um Bot do Discord em Python - Parte 1"
        ]
        
        for title in complex_titles:
            keywords = manager._extract_keywords(title)
            
            # Verificar que extraiu palavras relevantes
            assert len(keywords) > 0
            
            # Verificar que não há palavras muito curtas
            assert not any(len(word) <= 2 for word in keywords if "_" not in word)
            
            # Verificar que o título completo foi adicionado
            title_normalized = title.lower().replace(' ', '_')
            # Remove pontuação para comparação
            import re
            title_clean = re.sub(r'[^\w\s]', ' ', title.lower())
            title_clean = re.sub(r'\s+', ' ', title_clean).strip().replace(' ', '_')
            assert title_clean in keywords
    
    async def test_concurrent_operations(self, redis_audio_manager):
        """Testa operações concorrentes"""
        manager = redis_audio_manager
        
        # Mock successful operations
        manager._redis.hgetall.return_value = {
            b'id': b'test_audio',
            b'title': b'Test Audio'
        }
        
        # Executar múltiplas operações concorrentes
        tasks = [
            manager.get_audio(f"audio_{i}")
            for i in range(10)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verificar que todas as operações foram bem-sucedidas
        assert len(results) == 10
        assert all(not isinstance(result, Exception) for result in results)
    
    async def test_data_type_handling(self, redis_audio_manager):
        """Testa tratamento de diferentes tipos de dados"""
        manager = redis_audio_manager
        
        # Dados com diferentes tipos
        audio_data = {
            "id": "test_audio",
            "title": "Test Audio",
            "duration": 300,
            "metadata": {"key": "value"},
            "keywords": ["python", "tutorial"],
            "is_favorite": True,
            "file_size": 1024.5
        }
        
        # Mock pipeline
        mock_pipeline = AsyncMock()
        manager.redis_manager = MagicMock()
        manager.redis_manager.get_pipeline.return_value.__aenter__.return_value = mock_pipeline
        manager.redis_manager.get_pipeline.return_value.__aexit__.return_value = None
        
        await manager.create_audio(audio_data)
        
        # Verificar que os dados foram processados corretamente
        mock_pipeline.hset.assert_called()
        call_args = mock_pipeline.hset.call_args[1]["mapping"]
        
        # Verificar serialização JSON para objetos complexos
        assert "metadata" in call_args
        assert isinstance(call_args["metadata"], str)
        
        # Verificar conversão para string
        assert call_args["duration"] == "300"
        assert call_args["file_size"] == "1024.5"


@pytest.mark.unit
@pytest.mark.asyncio
class TestRedisAudioManagerIndexing:
    """Testes específicos para sistema de indexação"""
    
    async def test_add_to_indexes(self, redis_audio_manager, sample_audio_data):
        """Testa adição aos índices"""
        manager = redis_audio_manager
        mock_pipe = AsyncMock()
        
        # Adicionar keywords aos dados
        sample_audio_data["keywords"] = ["python", "tutorial", "programming"]
        sample_audio_data["transcription_status"] = "ended"
        sample_audio_data["format"] = "mp3"
        sample_audio_data["created_date"] = "2024-08-25T10:00:00"
        
        await manager._add_to_indexes(mock_pipe, sample_audio_data["id"], sample_audio_data)
        
        # Verificar chamadas para índices de keywords
        assert mock_pipe.sadd.call_count >= 3  # keywords + status + format
        
        # Verificar chamadas específicas
        mock_pipe.sadd.assert_any_call("audio:index:keyword:python", sample_audio_data["id"])
        mock_pipe.sadd.assert_any_call("audio:index:transcription_status:ended", sample_audio_data["id"])
        mock_pipe.sadd.assert_any_call("audio:index:format:mp3", sample_audio_data["id"])
    
    async def test_add_to_sorted_sets(self, redis_audio_manager, sample_audio_data):
        """Testa adição aos conjuntos ordenados"""
        manager = redis_audio_manager
        mock_pipe = AsyncMock()
        
        sample_audio_data["created_date"] = "2024-08-25T10:00:00"
        sample_audio_data["modified_date"] = "2024-08-25T11:00:00"
        sample_audio_data["filesize"] = 1024
        sample_audio_data["title"] = "Test Audio"
        
        await manager._add_to_sorted_sets(mock_pipe, sample_audio_data["id"], sample_audio_data)
        
        # Verificar chamadas para conjuntos ordenados
        assert mock_pipe.zadd.call_count == 4  # created, modified, filesize, title
    
    async def test_remove_from_indexes(self, redis_audio_manager, sample_audio_data):
        """Testa remoção dos índices"""
        manager = redis_audio_manager
        mock_pipe = AsyncMock()
        
        sample_audio_data["keywords"] = ["python", "tutorial"]
        sample_audio_data["transcription_status"] = "ended"
        sample_audio_data["format"] = "mp3"
        sample_audio_data["created_date"] = "2024-08-25T10:00:00"
        
        await manager._remove_from_indexes(mock_pipe, sample_audio_data["id"], sample_audio_data)
        
        # Verificar chamadas de remoção
        mock_pipe.srem.assert_any_call("audio:index:keyword:python", sample_audio_data["id"])
        mock_pipe.srem.assert_any_call("audio:index:transcription_status:ended", sample_audio_data["id"])
    
    async def test_update_indexes(self, redis_audio_manager):
        """Testa atualização de índices"""
        manager = redis_audio_manager
        mock_pipe = AsyncMock()
        
        old_data = {
            "keywords": ["python", "old_keyword"],
            "transcription_status": "started"
        }
        
        new_data = {
            "keywords": ["python", "new_keyword"],
            "transcription_status": "ended"
        }
        
        await manager._update_indexes(mock_pipe, "test_id", old_data, new_data)
        
        # Verificar remoção de keywords antigas
        mock_pipe.srem.assert_any_call("audio:index:keyword:old_keyword", "test_id")
        
        # Verificar adição de keywords novas
        mock_pipe.sadd.assert_any_call("audio:index:keyword:new_keyword", "test_id")
        
        # Verificar atualização de status
        mock_pipe.srem.assert_any_call("audio:index:transcription_status:started", "test_id")
        mock_pipe.sadd.assert_any_call("audio:index:transcription_status:ended", "test_id")


@pytest.mark.unit
@pytest.mark.asyncio  
class TestRedisAudioManagerCache:
    """Testes específicos para sistema de cache"""
    
    async def test_cache_invalidation(self, redis_audio_manager):
        """Testa invalidação de cache"""
        manager = redis_audio_manager
        mock_pipe = AsyncMock()
        
        # Mock scan_iter para retornar chaves de cache
        cache_keys = [
            b"audio:cache:search:python",
            b"audio:cache:stats",
            b"audio:cache:recent"
        ]
        
        async def mock_scan_iter(*args, **kwargs):
            for key in cache_keys:
                yield key
        
        manager._redis.scan_iter = mock_scan_iter
        
        await manager._invalidate_caches(mock_pipe)
        
        # Verificar que tentou deletar as chaves de cache
        mock_pipe.delete.assert_called()
    
    async def test_cache_key_generation(self, redis_audio_manager):
        """Testa geração de chaves de cache"""
        manager = redis_audio_manager
        
        # Testar diferentes padrões de cache
        search_key = manager.CACHE_PATTERNS['search'].format("python:10")
        stats_key = manager.CACHE_PATTERNS['stats']
        recent_key = manager.CACHE_PATTERNS['recent']
        
        assert search_key == "audio:cache:search:python:10"
        assert stats_key == "audio:cache:stats"
        assert recent_key == "audio:cache:recent"
    
    async def test_cache_ttl_settings(self, redis_audio_manager):
        """Testa configurações de TTL do cache"""
        manager = redis_audio_manager
        
        assert manager.DEFAULT_CACHE_TTL == 300  # 5 minutos
        
        # Mock para verificar chamadas de setex com TTL correto
        manager._redis.setex = AsyncMock()
        
        # Simular cache de busca
        manager._redis.get.return_value = None
        manager._redis.smembers.return_value = set()
        
        await manager.search_by_keyword("python")
        
        # Verificar se setex foi chamado com TTL para resultado vazio (60s)
        manager._redis.setex.assert_called_with(
            "audio:cache:search:python:all",
            60,
            json.dumps([])
        )