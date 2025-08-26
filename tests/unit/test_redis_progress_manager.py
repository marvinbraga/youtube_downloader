"""
Testes unitários para RedisProgressManager
Cobertura completa do sistema de tracking de progresso com pub/sub
"""

import asyncio
import json
import pytest
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.redis_progress_manager import (
    RedisProgressManager,
    TaskType,
    TaskStatus,
    ProgressMetrics,
    TaskEvent,
    TaskInfo
)


@pytest.mark.unit
@pytest.mark.asyncio
class TestRedisProgressManager:
    """Testes unitários para RedisProgressManager"""
    
    async def test_initialization(self):
        """Testa inicialização do manager"""
        manager = RedisProgressManager()
        
        assert manager.sse_manager is None
        assert manager._redis is None
        assert manager._pubsub is None
        assert manager._subscribers == {}
        assert manager._listening is False
        assert manager.max_events_per_task == 1000
        assert manager.cleanup_interval_hours == 24
        assert manager.completed_task_ttl_days == 7
    
    async def test_initialization_with_sse(self):
        """Testa inicialização com SSE manager"""
        mock_sse = MagicMock()
        manager = RedisProgressManager(sse_manager=mock_sse)
        
        assert manager.sse_manager is mock_sse
    
    async def test_task_creation(self, fake_redis):
        """Testa criação de tarefa"""
        manager = RedisProgressManager()
        manager._redis = fake_redis
        
        # Mock hset and sadd operations
        fake_redis.hset = AsyncMock()
        fake_redis.sadd = AsyncMock()
        fake_redis.expire = AsyncMock()
        
        task_id = "test_task_123"
        task_type = TaskType.DOWNLOAD
        metadata = {"url": "https://example.com", "format": "mp4"}
        
        task_info = await manager.create_task(task_id, task_type, metadata)
        
        # Verificações
        assert task_info.task_id == task_id
        assert task_info.task_type == task_type
        assert task_info.status == TaskStatus.PENDING
        assert task_info.metadata == metadata
        assert task_info.created_at is not None
        assert isinstance(task_info.progress, ProgressMetrics)
        
        # Verificar chamadas Redis
        fake_redis.hset.assert_called_once()
        fake_redis.sadd.assert_called_once_with(manager.ACTIVE_TASKS_KEY, task_id)
        fake_redis.expire.assert_called_once()
    
    async def test_start_task(self, fake_redis):
        """Testa início de tarefa"""
        manager = RedisProgressManager()
        manager._redis = fake_redis
        
        # Mock task info
        task_info = TaskInfo(
            task_id="test_task",
            task_type=TaskType.DOWNLOAD,
            status=TaskStatus.PENDING,
            progress=ProgressMetrics(),
            created_at=datetime.now().isoformat()
        )
        
        manager.get_task_info = AsyncMock(return_value=task_info)
        manager._publish_event = AsyncMock()
        manager._store_event = AsyncMock()
        fake_redis.hset = AsyncMock()
        
        await manager.start_task("test_task", "Starting download")
        
        # Verificar que status foi atualizado para RUNNING
        fake_redis.hset.assert_called()
        manager._publish_event.assert_called()
        manager._store_event.assert_called()
    
    async def test_update_progress_with_float(self, fake_redis):
        """Testa atualização de progresso com valor float"""
        manager = RedisProgressManager()
        manager._redis = fake_redis
        
        # Mock task info
        task_info = TaskInfo(
            task_id="test_task",
            task_type=TaskType.DOWNLOAD,
            status=TaskStatus.RUNNING,
            progress=ProgressMetrics(),
            created_at=datetime.now().isoformat()
        )
        
        manager.get_task_info = AsyncMock(return_value=task_info)
        manager._update_task_progress = AsyncMock()
        
        await manager.update_progress("test_task", 75.5, "75% complete")
        
        # Verificar que foi convertido para ProgressMetrics
        manager._update_task_progress.assert_called()
        call_args = manager._update_task_progress.call_args[1]
        assert isinstance(call_args['progress'], ProgressMetrics)
        assert call_args['progress'].percentage == 75.5
    
    async def test_update_progress_with_metrics(self, fake_redis):
        """Testa atualização de progresso com ProgressMetrics"""
        manager = RedisProgressManager()
        manager._redis = fake_redis
        
        # Mock task info
        task_info = TaskInfo(
            task_id="test_task",
            task_type=TaskType.DOWNLOAD,
            status=TaskStatus.RUNNING,
            progress=ProgressMetrics(),
            created_at=datetime.now().isoformat()
        )
        
        manager.get_task_info = AsyncMock(return_value=task_info)
        manager._update_task_progress = AsyncMock()
        
        progress = ProgressMetrics(
            percentage=85.0,
            bytes_downloaded=8500,
            total_bytes=10000,
            speed_bps=1000.0,
            current_step="Downloading video",
            total_steps=3,
            step_progress=2.0
        )
        
        await manager.update_progress("test_task", progress, "Download in progress")
        
        # Verificar que ETA foi calculado
        expected_eta = (10000 - 8500) / 1000.0  # 1.5 seconds
        assert progress.eta_seconds == int(expected_eta)
        
        manager._update_task_progress.assert_called()
    
    async def test_complete_task(self, fake_redis):
        """Testa conclusão de tarefa"""
        manager = RedisProgressManager()
        manager._redis = fake_redis
        
        # Mock task info
        task_info = TaskInfo(
            task_id="test_task",
            task_type=TaskType.DOWNLOAD,
            status=TaskStatus.RUNNING,
            progress=ProgressMetrics(percentage=100.0),
            created_at=datetime.now().isoformat(),
            started_at=datetime.now().isoformat()
        )
        
        manager.get_task_info = AsyncMock(return_value=task_info)
        manager._publish_event = AsyncMock()
        manager._store_event = AsyncMock()
        fake_redis.hset = AsyncMock()
        fake_redis.srem = AsyncMock()
        
        await manager.complete_task("test_task", "Download completed successfully")
        
        # Verificações
        fake_redis.hset.assert_called()
        fake_redis.srem.assert_called_with(manager.ACTIVE_TASKS_KEY, "test_task")
        manager._publish_event.assert_called()
        manager._store_event.assert_called()
    
    async def test_fail_task(self, fake_redis):
        """Testa falha de tarefa"""
        manager = RedisProgressManager()
        manager._redis = fake_redis
        
        # Mock task info
        task_info = TaskInfo(
            task_id="test_task",
            task_type=TaskType.DOWNLOAD,
            status=TaskStatus.RUNNING,
            progress=ProgressMetrics(percentage=45.0),
            created_at=datetime.now().isoformat(),
            started_at=datetime.now().isoformat()
        )
        
        manager.get_task_info = AsyncMock(return_value=task_info)
        manager._publish_event = AsyncMock()
        manager._store_event = AsyncMock()
        fake_redis.hset = AsyncMock()
        fake_redis.srem = AsyncMock()
        
        error_msg = "Network connection failed"
        await manager.fail_task("test_task", error_msg, "Download failed")
        
        # Verificações
        fake_redis.hset.assert_called()
        fake_redis.srem.assert_called_with(manager.ACTIVE_TASKS_KEY, "test_task")
        manager._publish_event.assert_called()
        manager._store_event.assert_called()
    
    async def test_cancel_task(self, fake_redis):
        """Testa cancelamento de tarefa"""
        manager = RedisProgressManager()
        manager._redis = fake_redis
        
        # Mock task info
        task_info = TaskInfo(
            task_id="test_task",
            task_type=TaskType.DOWNLOAD,
            status=TaskStatus.RUNNING,
            progress=ProgressMetrics(percentage=30.0),
            created_at=datetime.now().isoformat(),
            started_at=datetime.now().isoformat()
        )
        
        manager.get_task_info = AsyncMock(return_value=task_info)
        manager._publish_event = AsyncMock()
        manager._store_event = AsyncMock()
        fake_redis.hset = AsyncMock()
        fake_redis.srem = AsyncMock()
        
        await manager.cancel_task("test_task", "User requested cancellation")
        
        # Verificações
        fake_redis.hset.assert_called()
        fake_redis.srem.assert_called_with(manager.ACTIVE_TASKS_KEY, "test_task")
        manager._publish_event.assert_called()
        manager._store_event.assert_called()
    
    async def test_get_task_info_found(self, fake_redis):
        """Testa obtenção de informações de tarefa existente"""
        manager = RedisProgressManager()
        manager._redis = fake_redis
        
        # Mock task data
        task_info = TaskInfo(
            task_id="test_task",
            task_type=TaskType.DOWNLOAD,
            status=TaskStatus.COMPLETED,
            progress=ProgressMetrics(percentage=100.0),
            created_at="2024-08-25T10:00:00",
            completed_at="2024-08-25T10:05:00"
        )
        
        fake_redis.hget = AsyncMock(return_value=json.dumps(task_info.__dict__))
        
        result = await manager.get_task_info("test_task")
        
        assert result is not None
        assert result.task_id == "test_task"
        assert result.status == TaskStatus.COMPLETED
        assert result.progress.percentage == 100.0
    
    async def test_get_task_info_not_found(self, fake_redis):
        """Testa obtenção de informações de tarefa não encontrada"""
        manager = RedisProgressManager()
        manager._redis = fake_redis
        
        fake_redis.hget = AsyncMock(return_value=None)
        
        result = await manager.get_task_info("nonexistent_task")
        assert result is None
    
    async def test_get_task_events(self, fake_redis):
        """Testa obtenção de eventos de tarefa"""
        manager = RedisProgressManager()
        manager._redis = fake_redis
        
        # Mock events data
        events_data = [
            json.dumps({
                "task_id": "test_task",
                "task_type": "download",
                "event_type": "started",
                "status": "running",
                "progress": {"percentage": 0.0, "bytes_downloaded": 0, "total_bytes": 0, "speed_bps": 0.0},
                "message": "Download started",
                "error": None,
                "metadata": {},
                "timestamp": "2024-08-25T10:00:00"
            }).encode(),
            json.dumps({
                "task_id": "test_task",
                "task_type": "download",
                "event_type": "completed",
                "status": "completed",
                "progress": {"percentage": 100.0, "bytes_downloaded": 10000, "total_bytes": 10000, "speed_bps": 1000.0},
                "message": "Download completed",
                "error": None,
                "metadata": {},
                "timestamp": "2024-08-25T10:05:00"
            }).encode()
        ]
        
        fake_redis.lrange = AsyncMock(return_value=events_data)
        
        events = await manager.get_task_events("test_task", limit=10)
        
        assert len(events) == 2
        assert all(isinstance(event, TaskEvent) for event in events)
        assert events[0].event_type == "started"
        assert events[1].event_type == "completed"
    
    async def test_get_active_tasks(self, fake_redis):
        """Testa obtenção de tarefas ativas"""
        manager = RedisProgressManager()
        manager._redis = fake_redis
        
        # Mock active tasks
        active_tasks = [b"task1", b"task2", b"task3"]
        fake_redis.smembers = AsyncMock(return_value=active_tasks)
        
        result = await manager.get_active_tasks()
        
        assert result == ["task1", "task2", "task3"]
        fake_redis.smembers.assert_called_with(manager.ACTIVE_TASKS_KEY)
    
    async def test_publish_event(self, fake_redis):
        """Testa publicação de evento"""
        manager = RedisProgressManager()
        manager._redis = fake_redis
        
        fake_redis.publish = AsyncMock()
        
        event = TaskEvent(
            task_id="test_task",
            task_type=TaskType.DOWNLOAD,
            event_type="progress",
            status=TaskStatus.RUNNING,
            progress=ProgressMetrics(percentage=50.0),
            message="50% complete"
        )
        
        await manager._publish_event(event)
        
        fake_redis.publish.assert_called_once()
        call_args = fake_redis.publish.call_args
        assert call_args[0][0] == manager.PROGRESS_CHANNEL
        
        # Verificar que o evento foi serializado corretamente
        event_data = json.loads(call_args[0][1])
        assert event_data["task_id"] == "test_task"
        assert event_data["progress"]["percentage"] == 50.0
    
    async def test_store_event(self, fake_redis):
        """Testa armazenamento de evento"""
        manager = RedisProgressManager()
        manager._redis = fake_redis
        
        fake_redis.lpush = AsyncMock()
        fake_redis.ltrim = AsyncMock()
        fake_redis.hincrby = AsyncMock()
        
        event = TaskEvent(
            task_id="test_task",
            task_type=TaskType.DOWNLOAD,
            event_type="progress",
            status=TaskStatus.RUNNING,
            progress=ProgressMetrics(percentage=75.0),
            message="75% complete"
        )
        
        await manager._store_event(event)
        
        # Verificações
        events_key = f"{manager.EVENTS_KEY_PREFIX}test_task"
        fake_redis.lpush.assert_called_once_with(events_key, json.dumps(event.__dict__))
        fake_redis.ltrim.assert_called_once_with(events_key, 0, manager.max_events_per_task - 1)
        
        task_key = f"{manager.TASK_KEY_PREFIX}test_task"
        fake_redis.hincrby.assert_called_once_with(task_key, "events_count", 1)
    
    async def test_subscribe_to_task(self):
        """Testa inscrição para eventos de tarefa específica"""
        manager = RedisProgressManager()
        
        callback = AsyncMock()
        await manager.subscribe_to_task("test_task", callback)
        
        assert "test_task" in manager._subscribers
        assert callback in manager._subscribers["test_task"]
    
    async def test_subscribe_to_all(self):
        """Testa inscrição para todos os eventos"""
        manager = RedisProgressManager()
        
        callback = AsyncMock()
        await manager.subscribe_to_all(callback)
        
        assert "all" in manager._subscribers
        assert callback in manager._subscribers["all"]
    
    async def test_notify_subscribers(self):
        """Testa notificação de subscribers"""
        manager = RedisProgressManager()
        
        # Configurar callbacks
        task_callback = AsyncMock()
        global_callback = AsyncMock()
        sync_callback = MagicMock()
        
        await manager.subscribe_to_task("test_task", task_callback)
        await manager.subscribe_to_all(global_callback)
        await manager.subscribe_to_all(sync_callback)
        
        event = TaskEvent(
            task_id="test_task",
            task_type=TaskType.DOWNLOAD,
            event_type="progress",
            status=TaskStatus.RUNNING,
            progress=ProgressMetrics(percentage=50.0),
            message="50% complete"
        )
        
        await manager._notify_subscribers(event)
        
        # Verificar chamadas
        task_callback.assert_called_once_with(event)
        global_callback.assert_called_once_with(event)
        sync_callback.assert_called_once_with(event)
    
    async def test_cleanup_old_data(self, fake_redis):
        """Testa limpeza de dados antigos"""
        manager = RedisProgressManager()
        manager._redis = fake_redis
        manager.completed_task_ttl_days = 1  # 1 dia para teste
        
        # Mock scan_iter para retornar chaves de tarefas
        old_completed_task = TaskInfo(
            task_id="old_task",
            task_type=TaskType.DOWNLOAD,
            status=TaskStatus.COMPLETED,
            progress=ProgressMetrics(percentage=100.0),
            created_at="2024-08-20T10:00:00",
            completed_at="2024-08-20T10:05:00"  # Mais de 1 dia atrás
        )
        
        recent_completed_task = TaskInfo(
            task_id="recent_task",
            task_type=TaskType.DOWNLOAD,
            status=TaskStatus.COMPLETED,
            progress=ProgressMetrics(percentage=100.0),
            created_at="2024-08-25T10:00:00",
            completed_at=datetime.now().isoformat()  # Recente
        )
        
        task_keys = [b"task:old_task", b"task:recent_task"]
        
        async def mock_scan_iter(*args, **kwargs):
            for key in task_keys:
                yield key
        
        fake_redis.scan_iter = mock_scan_iter
        fake_redis.hget = AsyncMock(side_effect=[
            json.dumps(old_completed_task.__dict__),
            json.dumps(recent_completed_task.__dict__)
        ])
        fake_redis.delete = AsyncMock()
        fake_redis.srem = AsyncMock()
        
        cleaned_count = await manager.cleanup_old_data()
        
        # Verificar que apenas a tarefa antiga foi limpa
        assert cleaned_count == 1
        fake_redis.delete.assert_any_call("task:old_task")
        fake_redis.delete.assert_any_call("events:old_task")
        fake_redis.srem.assert_called_with(manager.ACTIVE_TASKS_KEY, "old_task")
    
    async def test_get_statistics(self, fake_redis):
        """Testa obtenção de estatísticas"""
        manager = RedisProgressManager()
        manager._redis = fake_redis
        
        # Mock tasks data
        task_data = [
            TaskInfo(
                task_id="task1",
                task_type=TaskType.DOWNLOAD,
                status=TaskStatus.COMPLETED,
                progress=ProgressMetrics(),
                created_at="2024-08-25T10:00:00"
            ).__dict__,
            TaskInfo(
                task_id="task2",
                task_type=TaskType.TRANSCRIPTION,
                status=TaskStatus.RUNNING,
                progress=ProgressMetrics(),
                created_at="2024-08-25T10:01:00"
            ).__dict__,
            TaskInfo(
                task_id="task3",
                task_type=TaskType.DOWNLOAD,
                status=TaskStatus.FAILED,
                progress=ProgressMetrics(),
                created_at="2024-08-25T10:02:00"
            ).__dict__
        ]
        
        task_keys = [b"task:task1", b"task:task2", b"task:task3"]
        
        async def mock_scan_iter(*args, **kwargs):
            for key in task_keys:
                yield key
        
        fake_redis.scan_iter = mock_scan_iter
        fake_redis.hget = AsyncMock(side_effect=[
            # Para cada task: data, events_count
            json.dumps(task_data[0]), "10",
            json.dumps(task_data[1]), "5", 
            json.dumps(task_data[2]), "3"
        ])
        fake_redis.scard = AsyncMock(return_value=1)  # 1 tarefa ativa
        
        # Mock redis health check
        with patch('app.services.redis_progress_manager.redis_manager') as mock_redis_manager:
            mock_redis_manager.health_check = AsyncMock(return_value={"status": "healthy"})
            
            stats = await manager.get_statistics()
            
            assert "tasks_by_status" in stats
            assert "tasks_by_type" in stats
            assert "active_tasks" in stats
            assert "total_events" in stats
            assert "redis_health" in stats
            assert "cleanup_config" in stats
            
            # Verificar contadores
            assert stats["tasks_by_status"]["completed"] == 1
            assert stats["tasks_by_status"]["running"] == 1
            assert stats["tasks_by_status"]["failed"] == 1
            assert stats["tasks_by_type"]["download"] == 2
            assert stats["tasks_by_type"]["transcription"] == 1
            assert stats["active_tasks"] == 1
            assert stats["total_events"] == 18  # 10 + 5 + 3
    
    async def test_map_to_sse_event_download(self):
        """Testa mapeamento de eventos de download para SSE"""
        manager = RedisProgressManager()
        
        # Evento de início de download
        start_event = TaskEvent(
            task_id="test_task",
            task_type=TaskType.DOWNLOAD,
            event_type="started",
            status=TaskStatus.RUNNING,
            progress=ProgressMetrics()
        )
        
        sse_event_type = manager._map_to_sse_event(start_event)
        assert sse_event_type == "download_started"
        
        # Evento de progresso de download
        progress_event = TaskEvent(
            task_id="test_task",
            task_type=TaskType.DOWNLOAD,
            event_type="progress",
            status=TaskStatus.RUNNING,
            progress=ProgressMetrics(percentage=50.0)
        )
        
        sse_event_type = manager._map_to_sse_event(progress_event)
        assert sse_event_type == "download_progress"
        
        # Evento de conclusão de download
        complete_event = TaskEvent(
            task_id="test_task",
            task_type=TaskType.DOWNLOAD,
            event_type="completed",
            status=TaskStatus.COMPLETED,
            progress=ProgressMetrics(percentage=100.0)
        )
        
        sse_event_type = manager._map_to_sse_event(complete_event)
        assert sse_event_type == "download_completed"
        
        # Evento de erro de download
        error_event = TaskEvent(
            task_id="test_task",
            task_type=TaskType.DOWNLOAD,
            event_type="failed",
            status=TaskStatus.FAILED,
            progress=ProgressMetrics(),
            error="Network error"
        )
        
        sse_event_type = manager._map_to_sse_event(error_event)
        assert sse_event_type == "download_error"
    
    async def test_map_to_sse_event_transcription(self):
        """Testa mapeamento de eventos de transcrição para SSE"""
        manager = RedisProgressManager()
        
        # Evento de início de transcrição
        start_event = TaskEvent(
            task_id="test_task",
            task_type=TaskType.TRANSCRIPTION,
            event_type="started",
            status=TaskStatus.RUNNING,
            progress=ProgressMetrics()
        )
        
        sse_event_type = manager._map_to_sse_event(start_event)
        assert sse_event_type == "transcription_started"
        
        # Evento não mapeado
        unknown_event = TaskEvent(
            task_id="test_task",
            task_type=TaskType.CONVERSION,
            event_type="started",
            status=TaskStatus.RUNNING,
            progress=ProgressMetrics()
        )
        
        sse_event_type = manager._map_to_sse_event(unknown_event)
        assert sse_event_type is None
    
    async def test_error_handling_task_not_found(self, fake_redis):
        """Testa tratamento de erro quando tarefa não é encontrada"""
        manager = RedisProgressManager()
        manager._redis = fake_redis
        
        manager.get_task_info = AsyncMock(return_value=None)
        
        # Tentar atualizar tarefa inexistente não deve gerar erro
        await manager.start_task("nonexistent_task")
        await manager.update_progress("nonexistent_task", 50.0)
        await manager.complete_task("nonexistent_task")
        await manager.fail_task("nonexistent_task", "error")
        await manager.cancel_task("nonexistent_task")
        
        # Verificar que get_task_info foi chamado
        assert manager.get_task_info.call_count == 5
    
    async def test_concurrent_operations(self, fake_redis):
        """Testa operações concorrentes"""
        manager = RedisProgressManager()
        manager._redis = fake_redis
        
        # Mock successful operations
        fake_redis.hset = AsyncMock()
        fake_redis.sadd = AsyncMock()
        fake_redis.expire = AsyncMock()
        
        # Criar múltiplas tarefas concorrentemente
        tasks = [
            manager.create_task(f"task_{i}", TaskType.DOWNLOAD)
            for i in range(10)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verificar que todas as operações foram bem-sucedidas
        assert len(results) == 10
        assert all(not isinstance(result, Exception) for result in results)
        assert all(isinstance(result, TaskInfo) for result in results)
    
    async def test_close_manager(self):
        """Testa fechamento do manager"""
        manager = RedisProgressManager()
        
        # Mock components
        mock_cleanup_task = AsyncMock()
        mock_pubsub = AsyncMock()
        
        manager._cleanup_task = mock_cleanup_task
        manager._pubsub = mock_pubsub
        manager._listening = True
        
        await manager.close()
        
        assert manager._listening is False
        mock_cleanup_task.cancel.assert_called()
        mock_pubsub.unsubscribe.assert_called()
        mock_pubsub.close.assert_called()


@pytest.mark.unit
@pytest.mark.asyncio
class TestTaskEventAndInfo:
    """Testes para estruturas de dados TaskEvent e TaskInfo"""
    
    async def test_task_event_creation(self):
        """Testa criação de TaskEvent"""
        progress = ProgressMetrics(percentage=50.0, bytes_downloaded=5000, total_bytes=10000)
        
        event = TaskEvent(
            task_id="test_task",
            task_type=TaskType.DOWNLOAD,
            event_type="progress",
            status=TaskStatus.RUNNING,
            progress=progress,
            message="50% complete"
        )
        
        assert event.task_id == "test_task"
        assert event.task_type == TaskType.DOWNLOAD
        assert event.status == TaskStatus.RUNNING
        assert event.progress.percentage == 50.0
        assert event.timestamp is not None  # Auto-gerado
        assert event.metadata == {}  # Default
    
    async def test_task_info_creation(self):
        """Testa criação de TaskInfo"""
        progress = ProgressMetrics(percentage=100.0)
        
        task_info = TaskInfo(
            task_id="test_task",
            task_type=TaskType.TRANSCRIPTION,
            status=TaskStatus.COMPLETED,
            progress=progress,
            created_at="2024-08-25T10:00:00"
        )
        
        assert task_info.task_id == "test_task"
        assert task_info.task_type == TaskType.TRANSCRIPTION
        assert task_info.status == TaskStatus.COMPLETED
        assert task_info.metadata == {}  # Default
        assert task_info.events_count == 0  # Default
    
    async def test_progress_metrics_eta_calculation(self):
        """Testa cálculo de ETA nas métricas"""
        progress = ProgressMetrics(
            percentage=50.0,
            bytes_downloaded=5000,
            total_bytes=10000,
            speed_bps=1000.0
        )
        
        # ETA deve ser calculado externamente
        remaining_bytes = progress.total_bytes - progress.bytes_downloaded
        expected_eta = int(remaining_bytes / progress.speed_bps)
        
        assert expected_eta == 5  # 5 segundos restantes
    
    async def test_enums_values(self):
        """Testa valores dos enums"""
        # TaskType
        assert TaskType.DOWNLOAD == "download"
        assert TaskType.TRANSCRIPTION == "transcription"
        assert TaskType.CONVERSION == "conversion"
        assert TaskType.UPLOAD == "upload"
        
        # TaskStatus
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.PAUSED == "paused"
        assert TaskStatus.COMPLETED == "completed"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.CANCELLED == "cancelled"


@pytest.mark.unit
@pytest.mark.asyncio
class TestRedisProgressManagerPubSub:
    """Testes específicos para funcionalidade pub/sub"""
    
    async def test_pubsub_message_processing(self):
        """Testa processamento de mensagem pub/sub"""
        manager = RedisProgressManager()
        manager._subscribers = {}
        manager.sse_manager = None
        
        # Mock notify_subscribers
        manager._notify_subscribers = AsyncMock()
        
        # Simular mensagem pub/sub
        event_data = {
            "task_id": "test_task",
            "task_type": "download",
            "event_type": "progress", 
            "status": "running",
            "progress": {"percentage": 75.0, "bytes_downloaded": 7500, "total_bytes": 10000, "speed_bps": 1000.0},
            "message": "75% complete",
            "error": None,
            "metadata": {},
            "timestamp": "2024-08-25T10:00:00"
        }
        
        message = {
            'type': 'message',
            'data': json.dumps(event_data).encode()
        }
        
        # Simular processamento da mensagem
        event = TaskEvent(**event_data)
        await manager._notify_subscribers(event)
        
        manager._notify_subscribers.assert_called_once()
    
    async def test_sse_integration(self):
        """Testa integração com SSE"""
        mock_sse_manager = AsyncMock()
        manager = RedisProgressManager(sse_manager=mock_sse_manager)
        
        event = TaskEvent(
            task_id="audio_123",
            task_type=TaskType.DOWNLOAD,
            event_type="progress",
            status=TaskStatus.RUNNING,
            progress=ProgressMetrics(percentage=60.0),
            message="60% complete",
            timestamp="2024-08-25T10:00:00"
        )
        
        await manager._integrate_with_sse(event)
        
        # Verificar que evento SSE foi criado e enviado
        mock_sse_manager.broadcast_event.assert_called_once()
        
        # Verificar estrutura do evento SSE
        call_args = mock_sse_manager.broadcast_event.call_args[0][0]
        assert call_args.audio_id == "audio_123"
        assert call_args.event_type == "download_progress"
        assert call_args.progress == 60
        assert call_args.message == "60% complete"


@pytest.mark.unit
@pytest.mark.asyncio
class TestRedisProgressManagerGlobalFunctions:
    """Testes para funções globais do módulo"""
    
    @patch('app.services.redis_progress_manager.redis_progress_manager', None)
    async def test_get_progress_manager_first_call(self):
        """Testa primeira chamada para get_progress_manager"""
        with patch('app.services.redis_progress_manager.RedisProgressManager') as MockManager:
            mock_instance = AsyncMock()
            MockManager.return_value = mock_instance
            
            from app.services.redis_progress_manager import get_progress_manager
            
            result = await get_progress_manager()
            
            assert result == mock_instance
            MockManager.assert_called_once()
            mock_instance.initialize.assert_called_once()
    
    async def test_init_progress_manager(self):
        """Testa init_progress_manager"""
        with patch('app.services.redis_progress_manager.get_progress_manager') as mock_get:
            from app.services.redis_progress_manager import init_progress_manager
            
            mock_sse = MagicMock()
            await init_progress_manager(mock_sse)
            
            mock_get.assert_called_once_with(mock_sse)
    
    async def test_close_progress_manager(self):
        """Testa close_progress_manager"""
        mock_manager = AsyncMock()
        
        with patch('app.services.redis_progress_manager.redis_progress_manager', mock_manager):
            from app.services.redis_progress_manager import close_progress_manager
            
            await close_progress_manager()
            
            mock_manager.close.assert_called_once()