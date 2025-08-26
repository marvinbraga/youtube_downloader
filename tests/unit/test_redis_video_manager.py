"""
Testes unitários para RedisVideoManager
Cobertura completa de todas as funcionalidades do gerenciador de vídeos
"""

import asyncio
import json
import pytest
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

from app.models.video import VideoSource, SortOption
from app.services.redis_video_manager import RedisVideoManager


@pytest.mark.unit
@pytest.mark.asyncio
class TestRedisVideoManager:
    """Testes unitários para RedisVideoManager"""
    
    async def test_initialization(self):
        """Testa inicialização do manager"""
        manager = RedisVideoManager()
        
        assert manager._redis is None
        assert 'source' in manager.INDEX_PATTERNS
        assert 'created' in manager.SORT_PATTERNS
        assert 'scan' in manager.CACHE_PATTERNS
        assert manager.DEFAULT_CACHE_TTL == 300
    
    async def test_generate_video_key(self):
        """Testa geração de chave Redis"""
        manager = RedisVideoManager()
        
        video_id = "test_video_123"
        expected_key = "video:test_video_123"
        
        result = manager._generate_video_key(video_id)
        assert result == expected_key
    
    async def test_generate_video_id(self):
        """Testa geração de ID único"""
        manager = RedisVideoManager()
        
        path1 = Path("/downloads/video1.mp4")
        path2 = Path("/downloads/video2.mp4")
        url1 = "https://youtube.com/watch?v=123"
        
        id1 = manager._generate_video_id(path1)
        id2 = manager._generate_video_id(path2)
        id3 = manager._generate_video_id(url1)
        
        assert len(id1) == 8  # MD5 truncado
        assert len(id2) == 8
        assert len(id3) == 8
        assert id1 != id2  # IDs diferentes para paths diferentes
        
        # Mesmo input deve gerar mesmo ID
        id1_repeat = manager._generate_video_id(path1)
        assert id1 == id1_repeat
    
    async def test_get_clean_filename(self):
        """Testa limpeza de nome de arquivo"""
        manager = RedisVideoManager()
        
        # Teste com .mp4
        path_mp4 = Path("/downloads/video.mp4")
        clean_mp4 = manager._get_clean_filename(path_mp4)
        assert clean_mp4 == "video"
        
        # Teste com .webm
        path_webm = Path("/downloads/video.webm")
        clean_webm = manager._get_clean_filename(path_webm)
        assert clean_webm == "video"
        
        # Teste com extensão maiúscula
        path_upper = Path("/downloads/VIDEO.MP4")
        clean_upper = manager._get_clean_filename(path_upper)
        assert clean_upper == "VIDEO"
        
        # Teste sem extensão de vídeo
        path_other = Path("/downloads/video.txt")
        clean_other = manager._get_clean_filename(path_other)
        assert clean_other == "video.txt"
    
    async def test_to_timestamp_conversion(self):
        """Testa conversão de data para timestamp"""
        manager = RedisVideoManager()
        
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
    
    async def test_calculate_name_score(self):
        """Testa cálculo de score por nome"""
        manager = RedisVideoManager()
        
        name1 = "Python Tutorial"
        name2 = "JavaScript Guide"
        name3 = ""
        
        score1 = manager._calculate_name_score(name1)
        score2 = manager._calculate_name_score(name2)
        score3 = manager._calculate_name_score(name3)
        
        assert 0 <= score1 <= 1
        assert 0 <= score2 <= 1
        assert score3 == 0.0
        
        # Nomes iguais devem ter scores iguais
        score1_repeat = manager._calculate_name_score(name1)
        assert score1 == score1_repeat
    
    @patch('pathlib.Path.stat')
    async def test_get_video_info_from_path(self, mock_stat):
        """Testa extração de informações de arquivo"""
        manager = RedisVideoManager()
        
        # Mock stat result
        mock_stat_result = MagicMock()
        mock_stat_result.st_ctime = 1692955200.0  # 2023-08-25T10:00:00
        mock_stat_result.st_mtime = 1692958800.0  # 2023-08-25T11:00:00
        mock_stat_result.st_size = 104857600  # 100MB
        mock_stat.return_value = mock_stat_result
        
        # Mock VIDEO_DIR
        with patch('app.services.redis_video_manager.VIDEO_DIR', Path('/downloads')):
            video_path = Path('/downloads/test_video.mp4')
            
            video_info = await manager.get_video_info_from_path(video_path)
            
            assert video_info['name'] == 'test_video'
            assert video_info['path'] == 'test_video.mp4'
            assert video_info['type'] == 'mp4'
            assert video_info['size'] == 104857600
            assert video_info['source'] == VideoSource.LOCAL
            assert video_info['url'] is None
            assert 'id' in video_info
            assert 'created_date' in video_info
            assert 'modified_date' in video_info
    
    async def test_create_video_success(self, redis_video_manager, sample_video_data):
        """Testa criação de vídeo com sucesso"""
        manager = redis_video_manager
        
        # Mock do pipeline
        mock_pipeline = AsyncMock()
        manager.redis_manager = MagicMock()
        manager.redis_manager.get_pipeline.return_value.__aenter__.return_value = mock_pipeline
        manager.redis_manager.get_pipeline.return_value.__aexit__.return_value = None
        
        # Executar criação
        result = await manager.create_video(sample_video_data)
        
        # Verificações
        assert result == sample_video_data["id"]
        mock_pipeline.hset.assert_called()
        mock_pipeline.execute.assert_called()
    
    async def test_create_video_missing_id(self, redis_video_manager):
        """Testa criação de vídeo sem ID"""
        manager = redis_video_manager
        
        video_data_no_id = {
            "name": "Test Video",
            "path": "/downloads/test.mp4"
        }
        
        with pytest.raises(ValueError, match="ID do vídeo é obrigatório"):
            await manager.create_video(video_data_no_id)
    
    async def test_get_video_success(self, redis_video_manager, sample_video_data):
        """Testa obtenção de vídeo com sucesso"""
        manager = redis_video_manager
        
        # Mock redis response
        redis_response = {
            b'id': b'test_video_456',
            b'name': b'Test Video Title',
            b'path': b'/downloads/test.mp4',
            b'size': b'104857600',
            b'type': b'mp4'
        }
        
        manager._redis.hgetall.return_value = redis_response
        
        result = await manager.get_video(sample_video_data["id"])
        
        assert result is not None
        assert result["id"] == "test_video_456"
        assert result["name"] == "Test Video Title"
        assert result["size"] == 104857600
    
    async def test_get_video_not_found(self, redis_video_manager):
        """Testa obtenção de vídeo não encontrado"""
        manager = redis_video_manager
        
        manager._redis.hgetall.return_value = {}
        
        result = await manager.get_video("nonexistent_id")
        assert result is None
    
    async def test_update_video_success(self, redis_video_manager, sample_video_data):
        """Testa atualização de vídeo com sucesso"""
        manager = redis_video_manager
        
        # Mock existing video
        manager.get_video = AsyncMock(return_value=sample_video_data)
        manager._redis.exists.return_value = True
        
        # Mock pipeline
        mock_pipeline = AsyncMock()
        manager.redis_manager = MagicMock()
        manager.redis_manager.get_pipeline.return_value.__aenter__.return_value = mock_pipeline
        manager.redis_manager.get_pipeline.return_value.__aexit__.return_value = None
        
        updates = {"name": "Updated Video", "size": 209715200}
        
        result = await manager.update_video(sample_video_data["id"], updates)
        
        assert result is True
        mock_pipeline.hset.assert_called()
        mock_pipeline.execute.assert_called()
    
    async def test_update_video_not_found(self, redis_video_manager):
        """Testa atualização de vídeo não encontrado"""
        manager = redis_video_manager
        
        manager._redis.exists.return_value = False
        
        result = await manager.update_video("nonexistent_id", {"name": "New Name"})
        assert result is False
    
    async def test_delete_video_success(self, redis_video_manager, sample_video_data):
        """Testa remoção de vídeo com sucesso"""
        manager = redis_video_manager
        
        # Mock existing video
        manager.get_video = AsyncMock(return_value=sample_video_data)
        
        # Mock pipeline
        mock_pipeline = AsyncMock()
        manager.redis_manager = MagicMock()
        manager.redis_manager.get_pipeline.return_value.__aenter__.return_value = mock_pipeline
        manager.redis_manager.get_pipeline.return_value.__aexit__.return_value = None
        
        result = await manager.delete_video(sample_video_data["id"])
        
        assert result is True
        mock_pipeline.delete.assert_called()
        mock_pipeline.execute.assert_called()
    
    async def test_delete_video_not_found(self, redis_video_manager):
        """Testa remoção de vídeo não encontrado"""
        manager = redis_video_manager
        
        manager.get_video = AsyncMock(return_value=None)
        
        result = await manager.delete_video("nonexistent_id")
        assert result is False
    
    async def test_get_videos_by_source_local(self, redis_video_manager):
        """Testa obtenção de vídeos por fonte LOCAL"""
        manager = redis_video_manager
        
        # Mock video IDs for LOCAL source
        video_ids = [b"video1", b"video2"]
        manager._redis.smembers.return_value = video_ids
        
        # Mock get_video calls
        video_data1 = {"id": "video1", "source": VideoSource.LOCAL, "name": "Local Video 1"}
        video_data2 = {"id": "video2", "source": VideoSource.LOCAL, "name": "Local Video 2"}
        manager.get_video = AsyncMock(side_effect=[video_data1, video_data2])
        
        result = await manager.get_videos_by_source(VideoSource.LOCAL)
        
        assert len(result) == 2
        assert all(video["source"] == VideoSource.LOCAL for video in result)
    
    async def test_get_videos_by_source_youtube(self, redis_video_manager):
        """Testa obtenção de vídeos por fonte YOUTUBE"""
        manager = redis_video_manager
        
        # Mock video IDs for YOUTUBE source
        video_ids = [b"video3", b"video4"]
        manager._redis.smembers.return_value = video_ids
        
        # Mock get_video calls
        video_data3 = {"id": "video3", "source": VideoSource.YOUTUBE, "url": "https://youtube.com/1"}
        video_data4 = {"id": "video4", "source": VideoSource.YOUTUBE, "url": "https://youtube.com/2"}
        manager.get_video = AsyncMock(side_effect=[video_data3, video_data4])
        
        result = await manager.get_videos_by_source(VideoSource.YOUTUBE)
        
        assert len(result) == 2
        assert all(video["source"] == VideoSource.YOUTUBE for video in result)
    
    async def test_sort_videos_by_title(self, redis_video_manager):
        """Testa ordenação por título"""
        manager = redis_video_manager
        
        video_list = [
            {"name": "Zebra Video", "modified_date": "2024-08-25T10:00:00"},
            {"name": "Alpha Video", "modified_date": "2024-08-24T10:00:00"},
            {"name": "Beta Video", "modified_date": "2024-08-26T10:00:00"}
        ]
        
        sorted_videos = manager._sort_videos(video_list, SortOption.TITLE)
        
        assert len(sorted_videos) == 3
        assert sorted_videos[0]["name"] == "Alpha Video"
        assert sorted_videos[1]["name"] == "Beta Video"
        assert sorted_videos[2]["name"] == "Zebra Video"
    
    async def test_sort_videos_by_date(self, redis_video_manager):
        """Testa ordenação por data"""
        manager = redis_video_manager
        
        video_list = [
            {"name": "Old Video", "modified_date": "2024-08-23T10:00:00"},
            {"name": "New Video", "modified_date": "2024-08-26T10:00:00"},
            {"name": "Mid Video", "modified_date": "2024-08-25T10:00:00"}
        ]
        
        sorted_videos = manager._sort_videos(video_list, SortOption.DATE)
        
        assert len(sorted_videos) == 3
        assert sorted_videos[0]["name"] == "New Video"  # Mais recente primeiro
        assert sorted_videos[1]["name"] == "Mid Video"
        assert sorted_videos[2]["name"] == "Old Video"
    
    async def test_sort_videos_none(self, redis_video_manager):
        """Testa sem ordenação"""
        manager = redis_video_manager
        
        video_list = [
            {"name": "Video 1", "modified_date": "2024-08-25T10:00:00"},
            {"name": "Video 2", "modified_date": "2024-08-24T10:00:00"}
        ]
        
        sorted_videos = manager._sort_videos(video_list, SortOption.NONE)
        
        # Deve manter ordem original
        assert sorted_videos == video_list
    
    async def test_get_all_videos_with_cache_hit(self, redis_video_manager):
        """Testa obtenção de todos os vídeos com cache hit"""
        manager = redis_video_manager
        
        # Mock cache hit
        cached_videos = [
            {"id": "video1", "name": "Cached Video 1"},
            {"id": "video2", "name": "Cached Video 2"}
        ]
        manager._redis.get.return_value = json.dumps(cached_videos).encode()
        
        result = await manager.get_all_videos(SortOption.NONE)
        
        assert len(result) == 2
        assert result[0]["name"] == "Cached Video 1"
        manager._redis.get.assert_called()
    
    async def test_get_all_videos_with_cache_miss(self, redis_video_manager):
        """Testa obtenção de todos os vídeos com cache miss"""
        manager = redis_video_manager
        
        # Mock cache miss
        manager._redis.get.return_value = None
        
        # Mock scan_iter to return video keys
        video_keys = [b"video:video1", b"video:video2"]
        
        async def mock_scan_iter(*args, **kwargs):
            for key in video_keys:
                yield key
        
        manager._redis.scan_iter = mock_scan_iter
        
        # Mock pipeline for data loading
        mock_pipeline = AsyncMock()
        video_data = [
            {b'id': b'video1', b'name': b'Video 1', b'size': b'1000'},
            {b'id': b'video2', b'name': b'Video 2', b'size': b'2000'}
        ]
        mock_pipeline.execute.return_value = video_data
        
        manager.redis_manager = MagicMock()
        manager.redis_manager.get_pipeline.return_value.__aenter__.return_value = mock_pipeline
        manager.redis_manager.get_pipeline.return_value.__aexit__.return_value = None
        
        result = await manager.get_all_videos(SortOption.NONE)
        
        assert len(result) == 2
        manager._redis.setex.assert_called()  # Cache result
    
    async def test_get_statistics_with_cache(self, redis_video_manager):
        """Testa obtenção de estatísticas com cache"""
        manager = redis_video_manager
        
        # Mock cached stats
        cached_stats = {
            "total_count": 50,
            "total_size": 5368709120,
            "source_local": 30,
            "source_youtube": 20
        }
        manager._redis.get.return_value = json.dumps(cached_stats).encode()
        
        result = await manager.get_statistics()
        
        assert result == cached_stats
        manager._redis.get.assert_called()
    
    async def test_get_statistics_without_cache(self, redis_video_manager):
        """Testa obtenção de estatísticas sem cache"""
        manager = redis_video_manager
        
        # Mock cache miss
        manager._redis.get.return_value = None
        
        # Mock basic stats
        basic_stats = {b'total_count': b'50', b'total_size': b'5368709120'}
        manager._redis.hgetall.return_value = basic_stats
        
        # Mock source counts
        manager._redis.scard.return_value = 25
        
        result = await manager.get_statistics()
        
        assert result["total_count"] == 50
        assert result["total_size"] == 5368709120
        assert "source_local" in result
        assert "source_youtube" in result
        assert "type_mp4" in result
        assert "type_webm" in result
        assert "last_updated" in result
        
        manager._redis.setex.assert_called()  # Cache result
    
    @patch('app.services.redis_video_manager.VIDEO_DIR')
    @patch('pathlib.Path.rglob')
    @patch('pathlib.Path.is_file')
    async def test_scan_video_directory(self, mock_is_file, mock_rglob, mock_video_dir, redis_video_manager):
        """Testa scan do diretório de vídeos"""
        manager = redis_video_manager
        
        # Mock cache miss
        manager._redis.get.return_value = None
        
        # Mock directory structure
        video_files = [
            Path('/downloads/video1.mp4'),
            Path('/downloads/video2.webm')
        ]
        mock_rglob.return_value = video_files
        mock_is_file.return_value = True
        
        # Mock get_video_info_from_path
        video_info1 = {"id": "vid1", "name": "Video 1", "source": VideoSource.LOCAL}
        video_info2 = {"id": "vid2", "name": "Video 2", "source": VideoSource.LOCAL}
        
        manager.get_video_info_from_path = AsyncMock(side_effect=[video_info1, video_info2])
        manager.get_video = AsyncMock(return_value=None)  # New videos
        manager.create_video = AsyncMock()
        manager.get_videos_by_source = AsyncMock(return_value=[])  # No remote videos
        
        result = await manager.scan_video_directory(SortOption.NONE)
        
        assert len(result) == 2
        assert manager.create_video.call_count == 2
        manager._redis.setex.assert_called()  # Cache result
    
    async def test_error_handling_create_video(self, redis_video_manager, sample_video_data):
        """Testa tratamento de erros na criação de vídeo"""
        manager = redis_video_manager
        
        # Mock pipeline error
        mock_pipeline = AsyncMock()
        mock_pipeline.execute.side_effect = Exception("Redis error")
        
        manager.redis_manager = MagicMock()
        manager.redis_manager.get_pipeline.return_value.__aenter__.return_value = mock_pipeline
        manager.redis_manager.get_pipeline.return_value.__aexit__.return_value = None
        
        with pytest.raises(Exception):
            await manager.create_video(sample_video_data)
    
    async def test_error_handling_get_video(self, redis_video_manager):
        """Testa tratamento de erros na obtenção de vídeo"""
        manager = redis_video_manager
        
        manager._redis.hgetall.side_effect = Exception("Redis error")
        
        result = await manager.get_video("test_id")
        assert result is None
    
    async def test_concurrent_operations(self, redis_video_manager):
        """Testa operações concorrentes"""
        manager = redis_video_manager
        
        # Mock successful operations
        manager._redis.hgetall.return_value = {
            b'id': b'test_video',
            b'name': b'Test Video',
            b'size': b'1000'
        }
        
        # Executar múltiplas operações concorrentes
        tasks = [
            manager.get_video(f"video_{i}")
            for i in range(10)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verificar que todas as operações foram bem-sucedidas
        assert len(results) == 10
        assert all(not isinstance(result, Exception) for result in results)
    
    async def test_data_type_handling(self, redis_video_manager):
        """Testa tratamento de diferentes tipos de dados"""
        manager = redis_video_manager
        
        # Dados com diferentes tipos
        video_data = {
            "id": "test_video",
            "name": "Test Video",
            "size": 104857600,
            "metadata": {"key": "value"},
            "tags": ["python", "tutorial"],
            "is_favorite": True,
            "duration": 300.5,
            "source": VideoSource.LOCAL
        }
        
        # Mock pipeline
        mock_pipeline = AsyncMock()
        manager.redis_manager = MagicMock()
        manager.redis_manager.get_pipeline.return_value.__aenter__.return_value = mock_pipeline
        manager.redis_manager.get_pipeline.return_value.__aexit__.return_value = None
        
        await manager.create_video(video_data)
        
        # Verificar que os dados foram processados corretamente
        mock_pipeline.hset.assert_called()
        call_args = mock_pipeline.hset.call_args[1]["mapping"]
        
        # Verificar serialização JSON para objetos complexos
        assert "metadata" in call_args
        assert isinstance(call_args["metadata"], str)
        
        # Verificar conversão para string
        assert call_args["size"] == "104857600"
        assert call_args["duration"] == "300.5"
        assert call_args["source"] == str(VideoSource.LOCAL)


@pytest.mark.unit
@pytest.mark.asyncio
class TestRedisVideoManagerIndexing:
    """Testes específicos para sistema de indexação de vídeos"""
    
    async def test_add_to_indexes(self, redis_video_manager, sample_video_data):
        """Testa adição aos índices"""
        manager = redis_video_manager
        mock_pipe = AsyncMock()
        
        # Configurar dados de teste
        sample_video_data["source"] = VideoSource.LOCAL
        sample_video_data["type"] = "mp4"
        sample_video_data["created_date"] = "2024-08-25T10:00:00"
        
        await manager._add_to_indexes(mock_pipe, sample_video_data["id"], sample_video_data)
        
        # Verificar chamadas para índices
        assert mock_pipe.sadd.call_count >= 3  # source + type + date
        
        # Verificar chamadas específicas
        mock_pipe.sadd.assert_any_call("video:index:source:LOCAL", sample_video_data["id"])
        mock_pipe.sadd.assert_any_call("video:index:type:mp4", sample_video_data["id"])
        mock_pipe.sadd.assert_any_call("video:index:date:2024-08", sample_video_data["id"])
    
    async def test_add_to_sorted_sets(self, redis_video_manager, sample_video_data):
        """Testa adição aos conjuntos ordenados"""
        manager = redis_video_manager
        mock_pipe = AsyncMock()
        
        sample_video_data["created_date"] = "2024-08-25T10:00:00"
        sample_video_data["modified_date"] = "2024-08-25T11:00:00"
        sample_video_data["size"] = 104857600
        sample_video_data["name"] = "Test Video"
        
        await manager._add_to_sorted_sets(mock_pipe, sample_video_data["id"], sample_video_data)
        
        # Verificar chamadas para conjuntos ordenados
        assert mock_pipe.zadd.call_count == 4  # created, modified, size, name
    
    async def test_remove_from_indexes(self, redis_video_manager, sample_video_data):
        """Testa remoção dos índices"""
        manager = redis_video_manager
        mock_pipe = AsyncMock()
        
        sample_video_data["source"] = VideoSource.LOCAL
        sample_video_data["type"] = "mp4"
        sample_video_data["created_date"] = "2024-08-25T10:00:00"
        
        await manager._remove_from_indexes(mock_pipe, sample_video_data["id"], sample_video_data)
        
        # Verificar chamadas de remoção
        mock_pipe.srem.assert_any_call("video:index:source:LOCAL", sample_video_data["id"])
        mock_pipe.srem.assert_any_call("video:index:type:mp4", sample_video_data["id"])
        mock_pipe.srem.assert_any_call("video:index:date:2024-08", sample_video_data["id"])
    
    async def test_update_indexes(self, redis_video_manager):
        """Testa atualização de índices"""
        manager = redis_video_manager
        mock_pipe = AsyncMock()
        
        old_data = {
            "source": VideoSource.LOCAL,
            "type": "mp4"
        }
        
        new_data = {
            "source": VideoSource.YOUTUBE,
            "type": "webm"
        }
        
        await manager._update_indexes(mock_pipe, "test_id", old_data, new_data)
        
        # Verificar remoção de índices antigos
        mock_pipe.srem.assert_any_call("video:index:source:LOCAL", "test_id")
        mock_pipe.srem.assert_any_call("video:index:type:mp4", "test_id")
        
        # Verificar adição aos novos índices
        mock_pipe.sadd.assert_any_call("video:index:source:YOUTUBE", "test_id")
        mock_pipe.sadd.assert_any_call("video:index:type:webm", "test_id")


@pytest.mark.unit
@pytest.mark.asyncio
class TestRedisVideoManagerCache:
    """Testes específicos para sistema de cache de vídeos"""
    
    async def test_cache_invalidation(self, redis_video_manager):
        """Testa invalidação de cache"""
        manager = redis_video_manager
        mock_pipe = AsyncMock()
        
        # Mock scan_iter para retornar chaves de cache
        cache_keys = [
            b"video:cache:scan:none",
            b"video:cache:stats",
            b"video:cache:all"
        ]
        
        async def mock_scan_iter(*args, **kwargs):
            for key in cache_keys:
                yield key
        
        manager._redis.scan_iter = mock_scan_iter
        
        await manager._invalidate_caches(mock_pipe)
        
        # Verificar que tentou deletar as chaves de cache
        mock_pipe.delete.assert_called()
    
    async def test_cache_key_generation(self, redis_video_manager):
        """Testa geração de chaves de cache"""
        manager = redis_video_manager
        
        # Testar diferentes padrões de cache
        scan_key = manager.CACHE_PATTERNS['scan'].format("title")
        stats_key = manager.CACHE_PATTERNS['stats']
        all_key = manager.CACHE_PATTERNS['all']
        
        assert scan_key == "video:cache:scan:title"
        assert stats_key == "video:cache:stats"
        assert all_key == "video:cache:all"
    
    async def test_cache_ttl_settings(self, redis_video_manager):
        """Testa configurações de TTL do cache"""
        manager = redis_video_manager
        
        assert manager.DEFAULT_CACHE_TTL == 300  # 5 minutos
        
        # Mock para verificar chamadas de setex com TTL correto
        manager._redis.setex = AsyncMock()
        
        # Mock scan_iter to return no keys
        async def mock_scan_iter(*args, **kwargs):
            for _ in range(0):  # Empty iterator
                yield
        
        manager._redis.scan_iter = mock_scan_iter
        manager._redis.get.return_value = None
        
        await manager.get_all_videos()
        
        # Verificar se setex foi chamado com TTL padrão
        manager._redis.setex.assert_called_with(
            "video:cache:all",
            300,
            json.dumps([], ensure_ascii=False)
        )


@pytest.mark.unit
@pytest.mark.asyncio
class TestRedisVideoManagerFileSystem:
    """Testes específicos para integração com sistema de arquivos"""
    
    @patch('pathlib.Path.stat')
    async def test_get_video_info_error_handling(self, mock_stat, redis_video_manager):
        """Testa tratamento de erros ao obter info do arquivo"""
        manager = redis_video_manager
        
        # Mock stat error
        mock_stat.side_effect = FileNotFoundError("File not found")
        
        video_path = Path('/downloads/nonexistent.mp4')
        
        video_info = await manager.get_video_info_from_path(video_path)
        
        assert video_info == {}
    
    @patch('pathlib.Path.suffix', new_callable=lambda: '.MP4')
    @patch('pathlib.Path.stat')
    async def test_case_insensitive_extension(self, mock_stat, redis_video_manager):
        """Testa tratamento de extensões em maiúscula"""
        manager = redis_video_manager
        
        # Mock stat result
        mock_stat_result = MagicMock()
        mock_stat_result.st_ctime = 1692955200.0
        mock_stat_result.st_mtime = 1692958800.0
        mock_stat_result.st_size = 104857600
        mock_stat.return_value = mock_stat_result
        
        with patch('app.services.redis_video_manager.VIDEO_DIR', Path('/downloads')):
            video_path = Path('/downloads/test_video.MP4')
            
            # Mock propriedades do Path
            with patch.object(Path, 'suffix', '.MP4'), \
                 patch.object(Path, 'name', 'test_video.MP4'):
                
                video_info = await manager.get_video_info_from_path(video_path)
                
                assert video_info['type'] == 'mp4'  # Deve ser minúsculo
                assert video_info['name'] == 'test_video'  # Sem extensão
    
    async def test_video_source_enum_handling(self, redis_video_manager):
        """Testa tratamento de enum VideoSource"""
        manager = redis_video_manager
        mock_pipe = AsyncMock()
        
        # Dados com enum
        video_data = {
            "id": "test_video",
            "source": VideoSource.YOUTUBE,
            "type": "mp4"
        }
        
        await manager._add_to_indexes(mock_pipe, "test_video", video_data)
        
        # Verificar que enum foi convertido para string
        mock_pipe.sadd.assert_any_call("video:index:source:YOUTUBE", "test_video")
    
    async def test_path_relative_handling(self):
        """Testa tratamento de caminhos relativos"""
        manager = RedisVideoManager()
        
        with patch('app.services.redis_video_manager.VIDEO_DIR', Path('/downloads')):
            video_path = Path('/downloads/subdir/video.mp4')
            
            # Mock stat
            with patch.object(video_path, 'stat') as mock_stat:
                mock_stat_result = MagicMock()
                mock_stat_result.st_ctime = 1692955200.0
                mock_stat_result.st_mtime = 1692958800.0
                mock_stat_result.st_size = 104857600
                mock_stat.return_value = mock_stat_result
                
                video_info = await manager.get_video_info_from_path(video_path)
                
                assert video_info['path'] == 'subdir/video.mp4'  # Caminho relativo