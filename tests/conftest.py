"""
Configuração global de testes para a suíte de QA do Redis
Fixtures compartilhadas e configurações de teste
"""

import asyncio
import json
import os
import pytest
import shutil
import tempfile
from typing import Dict, Any, AsyncGenerator, List
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis
import redis.asyncio as redis
from loguru import logger

# Import do projeto
from app.services.redis_connection import RedisConnectionManager
from app.services.redis_audio_manager import RedisAudioManager
from app.services.redis_video_manager import RedisVideoManager
from app.services.redis_progress_manager import RedisProgressManager


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def fake_redis():
    """Fixture que fornece uma instância fakeredis para testes unitários"""
    server = fakeredis.aioredis.FakeRedis()
    yield server
    await server.flushall()
    await server.close()


@pytest.fixture
async def real_redis():
    """
    Fixture para testes de integração com Redis real
    Só é usada quando REDIS_INTEGRATION_TESTS=1
    """
    if not os.getenv('REDIS_INTEGRATION_TESTS'):
        pytest.skip("Redis integration tests disabled")
    
    # Função para conversão segura
    def safe_int(value, default):
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    # Usar database dedicado para testes
    test_db = safe_int(os.getenv('REDIS_TEST_DB', '15'), 15)
    client = redis.Redis(
        host=os.getenv('REDIS_HOST', 'localhost'),
        port=safe_int(os.getenv('REDIS_PORT', '6379'), 6379),
        db=test_db,
        password=os.getenv('REDIS_PASSWORD')
    )
    
    # Limpar database de teste
    await client.flushdb()
    yield client
    
    # Cleanup
    await client.flushdb()
    await client.close()


@pytest.fixture
async def redis_manager_mock():
    """Mock do RedisConnectionManager para testes unitários"""
    manager = MagicMock(spec=RedisConnectionManager)
    manager.get_client = AsyncMock()
    manager.health_check = AsyncMock()
    manager.execute_with_retry = AsyncMock()
    yield manager


@pytest.fixture
async def redis_audio_manager(fake_redis):
    """Instância do RedisAudioManager com fakeredis"""
    manager = RedisAudioManager()
    # Substituir o cliente Redis interno por fakeredis
    manager._redis = fake_redis
    manager.redis_manager.get_client = AsyncMock(return_value=fake_redis)
    yield manager


@pytest.fixture
async def redis_video_manager(fake_redis):
    """Instância do RedisVideoManager com fakeredis"""
    manager = RedisVideoManager()
    # Substituir o cliente Redis interno por fakeredis
    manager._redis = fake_redis
    manager.redis_manager.get_client = AsyncMock(return_value=fake_redis)
    yield manager


@pytest.fixture
async def redis_progress_manager(fake_redis):
    """Instância do RedisProgressManager com fakeredis"""
    manager = RedisProgressManager()
    # Substituir o cliente Redis interno por fakeredis
    manager._redis = fake_redis
    manager.redis_manager.get_client = AsyncMock(return_value=fake_redis)
    yield manager


@pytest.fixture
def sample_audio_data() -> Dict[str, Any]:
    """Dados de áudio de exemplo para testes"""
    return {
        "id": "test_audio_123",
        "title": "Test Audio Title",
        "url": "https://youtube.com/watch?v=test123",
        "duration": 300,
        "file_path": "/downloads/test_audio.mp3",
        "file_size": 5242880,
        "format": "mp3",
        "status": "completed",
        "created_at": "2024-08-25T10:00:00Z",
        "updated_at": "2024-08-25T10:05:00Z",
        "metadata": {
            "artist": "Test Artist",
            "album": "Test Album",
            "bitrate": "128k"
        }
    }


@pytest.fixture
def sample_video_data() -> Dict[str, Any]:
    """Dados de vídeo de exemplo para testes"""
    return {
        "id": "test_video_456",
        "title": "Test Video Title",
        "url": "https://youtube.com/watch?v=test456",
        "duration": 600,
        "file_path": "/downloads/test_video.mp4",
        "file_size": 104857600,
        "format": "mp4",
        "quality": "720p",
        "status": "completed",
        "created_at": "2024-08-25T10:00:00Z",
        "updated_at": "2024-08-25T10:10:00Z",
        "metadata": {
            "resolution": "1280x720",
            "fps": 30,
            "codec": "h264"
        }
    }


@pytest.fixture
def sample_progress_data() -> Dict[str, Any]:
    """Dados de progresso de exemplo para testes"""
    return {
        "download_id": "test_download_789",
        "url": "https://youtube.com/watch?v=test789",
        "title": "Test Download",
        "status": "downloading",
        "progress": 45.5,
        "speed": "1.2MB/s",
        "eta": "00:02:30",
        "file_size": 52428800,
        "downloaded_bytes": 23854080,
        "timestamp": "2024-08-25T10:15:00Z"
    }


@pytest.fixture
def temp_json_files():
    """Cria arquivos JSON temporários para testes de migração"""
    temp_dir = tempfile.mkdtemp()
    
    # Dados de áudio
    audio_data = [
        {
            "id": "audio_1",
            "title": "Audio 1",
            "url": "https://youtube.com/watch?v=audio1",
            "file_path": "/downloads/audio1.mp3",
            "duration": 180
        },
        {
            "id": "audio_2", 
            "title": "Audio 2",
            "url": "https://youtube.com/watch?v=audio2",
            "file_path": "/downloads/audio2.mp3",
            "duration": 240
        }
    ]
    
    # Dados de vídeo
    video_data = [
        {
            "id": "video_1",
            "title": "Video 1",
            "url": "https://youtube.com/watch?v=video1",
            "file_path": "/downloads/video1.mp4",
            "duration": 360
        },
        {
            "id": "video_2",
            "title": "Video 2", 
            "url": "https://youtube.com/watch?v=video2",
            "file_path": "/downloads/video2.mp4",
            "duration": 480
        }
    ]
    
    audio_file = os.path.join(temp_dir, 'audios.json')
    video_file = os.path.join(temp_dir, 'videos.json')
    
    with open(audio_file, 'w', encoding='utf-8') as f:
        json.dump(audio_data, f, indent=2)
    
    with open(video_file, 'w', encoding='utf-8') as f:
        json.dump(video_data, f, indent=2)
    
    yield {
        'temp_dir': temp_dir,
        'audio_file': audio_file,
        'video_file': video_file,
        'audio_data': audio_data,
        'video_data': video_data
    }
    
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def performance_data_generator():
    """Gerador de dados para testes de performance"""
    def generate_audio_batch(count: int) -> List[Dict[str, Any]]:
        return [
            {
                "id": f"perf_audio_{i}",
                "title": f"Performance Audio {i}",
                "url": f"https://youtube.com/watch?v=perf_audio_{i}",
                "duration": 180 + (i % 300),
                "file_path": f"/downloads/perf_audio_{i}.mp3",
                "file_size": 3145728 + (i * 1024),
                "format": "mp3",
                "status": "completed"
            }
            for i in range(count)
        ]
    
    def generate_video_batch(count: int) -> List[Dict[str, Any]]:
        return [
            {
                "id": f"perf_video_{i}",
                "title": f"Performance Video {i}",
                "url": f"https://youtube.com/watch?v=perf_video_{i}",
                "duration": 300 + (i % 600),
                "file_path": f"/downloads/perf_video_{i}.mp4",
                "file_size": 52428800 + (i * 10240),
                "format": "mp4",
                "quality": "720p",
                "status": "completed"
            }
            for i in range(count)
        ]
    
    return {
        'audio_batch': generate_audio_batch,
        'video_batch': generate_video_batch
    }


@pytest.fixture
def mock_download_callbacks():
    """Mock callbacks para testes de progresso"""
    callbacks = {
        'on_progress': AsyncMock(),
        'on_complete': AsyncMock(),
        'on_error': AsyncMock(),
        'on_start': AsyncMock()
    }
    yield callbacks


# Configurações de teste
pytest_plugins = []

# Markers personalizados
def pytest_configure(config):
    """Configure custom markers"""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as a performance test"
    )
    config.addinivalue_line(
        "markers", "load: mark test as a load test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


# Configurar logging para testes
logger.remove()  # Remove default handler
logger.add(
    "tests/logs/test_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="7 days",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
)