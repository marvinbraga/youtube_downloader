"""
Advanced Progress Manager - FASE 3 Sistema de Progresso Avançado
Sistema granular de tracking com multi-stages, ETA, velocidade e métricas avançadas
"""

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Union, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum

import redis.asyncio as redis
from loguru import logger

from .redis_connection import get_redis_client, redis_manager
from .redis_progress_manager import RedisProgressManager, TaskType, TaskStatus, ProgressMetrics, TaskEvent
from .sse_manager import SSEManager


class DownloadStage(str, Enum):
    """Estágios específicos do download"""
    METADATA = "metadata"           # Extraindo metadados do vídeo
    DOWNLOADING = "downloading"     # Download do arquivo
    EXTRACTING = "extracting"       # Extração de áudio (se necessário)
    FINALIZING = "finalizing"       # Finalizando e movendo arquivo


class TranscriptionStage(str, Enum):
    """Estágios específicos da transcrição"""
    PREPARING = "preparing"         # Preparando arquivo para upload
    UPLOADING = "uploading"         # Enviando para serviço de transcrição
    PROCESSING = "processing"       # Processamento remoto
    DOWNLOADING_RESULT = "downloading_result"  # Baixando resultado
    FINALIZING = "finalizing"       # Salvando e indexando resultado


@dataclass
class StageProgress:
    """Progresso de um estágio específico"""
    stage: str
    percentage: float = 0.0
    bytes_processed: int = 0
    total_bytes: int = 0
    speed_bps: float = 0.0
    eta_seconds: Optional[int] = None
    message: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    def __post_init__(self):
        if not self.started_at and self.percentage > 0:
            self.started_at = datetime.now().isoformat()


@dataclass
class AdvancedProgressMetrics(ProgressMetrics):
    """Métricas de progresso expandidas com multi-stage"""
    current_stage: str = ""
    stages: Dict[str, StageProgress] = field(default_factory=dict)
    overall_eta_seconds: Optional[int] = None
    average_speed_bps: float = 0.0
    peak_speed_bps: float = 0.0
    total_duration_seconds: Optional[int] = None
    stage_weights: Dict[str, float] = field(default_factory=dict)  # Peso de cada estágio
    
    def calculate_overall_progress(self) -> float:
        """Calcula progresso geral baseado nos pesos dos estágios"""
        if not self.stages or not self.stage_weights:
            return self.percentage
        
        total_weighted_progress = 0.0
        total_weight = 0.0
        
        for stage_name, weight in self.stage_weights.items():
            if stage_name in self.stages:
                stage_progress = self.stages[stage_name].percentage
                total_weighted_progress += stage_progress * weight
                total_weight += weight
        
        if total_weight > 0:
            return total_weighted_progress / total_weight
        
        return self.percentage
    
    def calculate_overall_eta(self) -> Optional[int]:
        """Calcula ETA geral baseado no progresso e velocidade"""
        overall_progress = self.calculate_overall_progress()
        
        if overall_progress > 0 and self.average_speed_bps > 0:
            remaining_progress = 100.0 - overall_progress
            if remaining_progress > 0:
                # Estima baseado na velocidade média e progresso restante
                total_estimated_bytes = sum(
                    stage.total_bytes for stage in self.stages.values() 
                    if stage.total_bytes > 0
                )
                if total_estimated_bytes > 0:
                    remaining_bytes = (remaining_progress / 100.0) * total_estimated_bytes
                    return int(remaining_bytes / self.average_speed_bps)
        
        return self.overall_eta_seconds


@dataclass
class TaskTimeline:
    """Timeline de eventos de uma tarefa"""
    task_id: str
    events: List[Dict[str, Any]] = field(default_factory=list)
    milestones: Dict[str, str] = field(default_factory=dict)  # stage -> timestamp
    
    def add_event(self, event_type: str, stage: str, message: str, metadata: Dict = None):
        """Adiciona evento à timeline"""
        timestamp = datetime.now().isoformat()
        event = {
            "timestamp": timestamp,
            "event_type": event_type,
            "stage": stage,
            "message": message,
            "metadata": metadata or {}
        }
        self.events.append(event)
        
        # Atualizar milestones
        if event_type in ["stage_started", "stage_completed"]:
            self.milestones[f"{stage}_{event_type}"] = timestamp


class AdvancedProgressManager(RedisProgressManager):
    """
    Gerenciador de progresso avançado com suporte a multi-stage
    
    Funcionalidades Avançadas:
    - Tracking granular por estágios
    - Cálculo inteligente de ETA
    - Métricas de velocidade avançadas
    - Timeline de eventos detalhada
    - Suporte a 1000+ clientes simultâneos
    """
    
    # Chaves Redis expandidas
    TIMELINE_KEY_PREFIX = "timeline:"
    METRICS_KEY_PREFIX = "metrics:"
    ACTIVE_STAGES_KEY = "active_stages"
    
    # Configurações avançadas
    DEFAULT_STAGE_WEIGHTS = {
        # Download weights
        DownloadStage.METADATA: 0.05,      # 5%
        DownloadStage.DOWNLOADING: 0.80,   # 80%
        DownloadStage.EXTRACTING: 0.10,    # 10%
        DownloadStage.FINALIZING: 0.05,    # 5%
        
        # Transcription weights
        TranscriptionStage.PREPARING: 0.10,         # 10%
        TranscriptionStage.UPLOADING: 0.20,         # 20%
        TranscriptionStage.PROCESSING: 0.60,        # 60%
        TranscriptionStage.DOWNLOADING_RESULT: 0.05, # 5%
        TranscriptionStage.FINALIZING: 0.05         # 5%
    }
    
    def __init__(self, sse_manager: Optional[SSEManager] = None):
        super().__init__(sse_manager)
        self._stage_timers: Dict[str, float] = {}  # Para calcular velocidades
        self._speed_history: Dict[str, List[Tuple[float, float]]] = {}  # (timestamp, speed)
        logger.info("AdvancedProgressManager inicializado")
    
    async def create_advanced_task(
        self,
        task_id: str,
        task_type: TaskType,
        stages: List[str],
        stage_weights: Optional[Dict[str, float]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> 'AdvancedTaskInfo':
        """Cria uma tarefa avançada com estágios definidos"""
        try:
            # Usar pesos padrão se não fornecidos
            if not stage_weights:
                stage_weights = {
                    stage: self.DEFAULT_STAGE_WEIGHTS.get(stage, 1.0/len(stages))
                    for stage in stages
                }
            
            # Criar métricas avançadas
            advanced_metrics = AdvancedProgressMetrics(
                stage_weights=stage_weights,
                stages={stage: StageProgress(stage=stage) for stage in stages}
            )
            
            # Criar timeline
            timeline = TaskTimeline(task_id=task_id)
            timeline.add_event(
                event_type="task_created",
                stage="initialization",
                message=f"Tarefa {task_type} criada com {len(stages)} estágios",
                metadata={"stages": stages, "weights": stage_weights}
            )
            
            # Criar tarefa base
            base_task = await super().create_task(task_id, task_type, metadata)
            
            # Salvar dados avançados
            await self._save_advanced_data(task_id, advanced_metrics, timeline)
            
            # Converter para AdvancedTaskInfo
            advanced_task = AdvancedTaskInfo(
                task_id=task_id,
                task_type=task_type,
                status=TaskStatus.PENDING,
                progress=advanced_metrics,
                created_at=base_task.created_at,
                metadata=metadata or {},
                timeline=timeline
            )
            
            logger.info(f"Tarefa avançada criada: {task_id} com estágios {stages}")
            return advanced_task
            
        except Exception as e:
            logger.error(f"Erro ao criar tarefa avançada {task_id}: {e}")
            raise
    
    async def start_stage(
        self,
        task_id: str,
        stage: str,
        total_bytes: Optional[int] = None,
        message: str = ""
    ) -> None:
        """Inicia um estágio específico"""
        try:
            advanced_metrics, timeline = await self._load_advanced_data(task_id)
            
            if not advanced_metrics or stage not in advanced_metrics.stages:
                logger.warning(f"Estágio {stage} não encontrado na tarefa {task_id}")
                return
            
            # Atualizar estágio
            stage_progress = advanced_metrics.stages[stage]
            stage_progress.started_at = datetime.now().isoformat()
            if total_bytes:
                stage_progress.total_bytes = total_bytes
            
            # Atualizar métricas globais
            advanced_metrics.current_stage = stage
            
            # Adicionar à timeline
            timeline.add_event(
                event_type="stage_started",
                stage=stage,
                message=message or f"Iniciando estágio: {stage}",
                metadata={"total_bytes": total_bytes}
            )
            
            # Salvar dados
            await self._save_advanced_data(task_id, advanced_metrics, timeline)
            
            # Inicializar timer de velocidade
            self._stage_timers[f"{task_id}:{stage}"] = time.time()
            self._speed_history[f"{task_id}:{stage}"] = []
            
            # Publicar evento
            await self._publish_stage_event(
                task_id=task_id,
                stage=stage,
                event_type="stage_started",
                progress=advanced_metrics,
                message=message or f"Estágio iniciado: {stage}"
            )
            
            logger.info(f"Estágio iniciado: {task_id}:{stage}")
            
        except Exception as e:
            logger.error(f"Erro ao iniciar estágio {task_id}:{stage}: {e}")
            raise
    
    async def update_stage_progress(
        self,
        task_id: str,
        stage: str,
        bytes_processed: int,
        percentage: Optional[float] = None,
        message: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Atualiza progresso de um estágio específico"""
        try:
            advanced_metrics, timeline = await self._load_advanced_data(task_id)
            
            if not advanced_metrics or stage not in advanced_metrics.stages:
                logger.warning(f"Estágio {stage} não encontrado na tarefa {task_id}")
                return
            
            stage_progress = advanced_metrics.stages[stage]
            stage_progress.bytes_processed = bytes_processed
            
            # Calcular percentual se não fornecido
            if percentage is not None:
                stage_progress.percentage = percentage
            elif stage_progress.total_bytes > 0:
                stage_progress.percentage = min(
                    100.0, (bytes_processed / stage_progress.total_bytes) * 100.0
                )
            
            # Calcular velocidade
            current_time = time.time()
            stage_key = f"{task_id}:{stage}"
            
            if stage_key in self._stage_timers and bytes_processed > 0:
                elapsed_time = current_time - self._stage_timers[stage_key]
                if elapsed_time > 0:
                    stage_progress.speed_bps = bytes_processed / elapsed_time
                    
                    # Atualizar histórico de velocidade
                    if stage_key not in self._speed_history:
                        self._speed_history[stage_key] = []
                    
                    self._speed_history[stage_key].append((current_time, stage_progress.speed_bps))
                    
                    # Manter apenas últimos 10 pontos
                    if len(self._speed_history[stage_key]) > 10:
                        self._speed_history[stage_key] = self._speed_history[stage_key][-10:]
                    
                    # Calcular velocidade média
                    recent_speeds = [speed for _, speed in self._speed_history[stage_key][-5:]]
                    if recent_speeds:
                        stage_progress.speed_bps = sum(recent_speeds) / len(recent_speeds)
            
            # Calcular ETA do estágio
            if stage_progress.speed_bps > 0 and stage_progress.total_bytes > 0:
                remaining_bytes = stage_progress.total_bytes - bytes_processed
                if remaining_bytes > 0:
                    stage_progress.eta_seconds = int(remaining_bytes / stage_progress.speed_bps)
            
            # Atualizar métricas globais
            advanced_metrics.percentage = advanced_metrics.calculate_overall_progress()
            advanced_metrics.overall_eta_seconds = advanced_metrics.calculate_overall_eta()
            
            # Calcular velocidade média geral
            all_speeds = [sp.speed_bps for sp in advanced_metrics.stages.values() if sp.speed_bps > 0]
            if all_speeds:
                advanced_metrics.average_speed_bps = sum(all_speeds) / len(all_speeds)
                advanced_metrics.peak_speed_bps = max(advanced_metrics.peak_speed_bps, max(all_speeds))
            
            # Atualizar timeline
            timeline.add_event(
                event_type="stage_progress",
                stage=stage,
                message=message or f"Progresso: {stage_progress.percentage:.1f}%",
                metadata={
                    "bytes_processed": bytes_processed,
                    "percentage": stage_progress.percentage,
                    "speed_bps": stage_progress.speed_bps,
                    "eta_seconds": stage_progress.eta_seconds,
                    **(metadata or {})
                }
            )
            
            # Salvar dados
            await self._save_advanced_data(task_id, advanced_metrics, timeline)
            
            # Publicar evento
            await self._publish_stage_event(
                task_id=task_id,
                stage=stage,
                event_type="stage_progress",
                progress=advanced_metrics,
                message=message or f"Progresso {stage}: {stage_progress.percentage:.1f}%"
            )
            
        except Exception as e:
            logger.error(f"Erro ao atualizar progresso do estágio {task_id}:{stage}: {e}")
            raise
    
    async def complete_stage(
        self,
        task_id: str,
        stage: str,
        message: str = ""
    ) -> None:
        """Completa um estágio específico"""
        try:
            advanced_metrics, timeline = await self._load_advanced_data(task_id)
            
            if not advanced_metrics or stage not in advanced_metrics.stages:
                logger.warning(f"Estágio {stage} não encontrado na tarefa {task_id}")
                return
            
            # Marcar estágio como completo
            stage_progress = advanced_metrics.stages[stage]
            stage_progress.percentage = 100.0
            stage_progress.completed_at = datetime.now().isoformat()
            stage_progress.eta_seconds = 0
            
            # Atualizar métricas globais
            advanced_metrics.percentage = advanced_metrics.calculate_overall_progress()
            
            # Verificar se todos os estágios foram completados
            all_completed = all(
                sp.percentage >= 100.0 for sp in advanced_metrics.stages.values()
            )
            
            # Atualizar timeline
            timeline.add_event(
                event_type="stage_completed",
                stage=stage,
                message=message or f"Estágio concluído: {stage}",
                metadata={"all_stages_completed": all_completed}
            )
            
            # Limpar timer de velocidade
            stage_key = f"{task_id}:{stage}"
            if stage_key in self._stage_timers:
                del self._stage_timers[stage_key]
            if stage_key in self._speed_history:
                del self._speed_history[stage_key]
            
            # Salvar dados
            await self._save_advanced_data(task_id, advanced_metrics, timeline)
            
            # Publicar evento
            await self._publish_stage_event(
                task_id=task_id,
                stage=stage,
                event_type="stage_completed",
                progress=advanced_metrics,
                message=message or f"Estágio concluído: {stage}"
            )
            
            # Se todos os estágios foram concluídos, completar a tarefa
            if all_completed:
                await self.complete_task(
                    task_id, 
                    message="Todos os estágios concluídos com sucesso"
                )
            
            logger.info(f"Estágio concluído: {task_id}:{stage}")
            
        except Exception as e:
            logger.error(f"Erro ao completar estágio {task_id}:{stage}: {e}")
            raise
    
    async def fail_stage(
        self,
        task_id: str,
        stage: str,
        error: str,
        message: str = ""
    ) -> None:
        """Marca um estágio como falhado"""
        try:
            advanced_metrics, timeline = await self._load_advanced_data(task_id)
            
            if not advanced_metrics:
                logger.warning(f"Dados avançados não encontrados para tarefa {task_id}")
                return
            
            # Atualizar timeline
            timeline.add_event(
                event_type="stage_failed",
                stage=stage,
                message=message or f"Estágio falhou: {stage} - {error}",
                metadata={"error": error}
            )
            
            # Limpar timers
            stage_key = f"{task_id}:{stage}"
            if stage_key in self._stage_timers:
                del self._stage_timers[stage_key]
            if stage_key in self._speed_history:
                del self._speed_history[stage_key]
            
            # Salvar dados
            await self._save_advanced_data(task_id, advanced_metrics, timeline)
            
            # Publicar evento
            await self._publish_stage_event(
                task_id=task_id,
                stage=stage,
                event_type="stage_failed",
                progress=advanced_metrics,
                message=message or f"Estágio falhou: {stage}",
                error=error
            )
            
            # Falhar a tarefa completa
            await self.fail_task(
                task_id, 
                error=f"Falha no estágio {stage}: {error}",
                message=message or f"Tarefa falhou no estágio {stage}"
            )
            
            logger.error(f"Estágio falhou: {task_id}:{stage} - {error}")
            
        except Exception as e:
            logger.error(f"Erro ao falhar estágio {task_id}:{stage}: {e}")
            raise
    
    async def get_advanced_task_info(self, task_id: str) -> Optional['AdvancedTaskInfo']:
        """Obtém informações avançadas de uma tarefa"""
        try:
            # Obter informações base
            base_task = await self.get_task_info(task_id)
            if not base_task:
                return None
            
            # Carregar dados avançados
            advanced_metrics, timeline = await self._load_advanced_data(task_id)
            
            if not advanced_metrics:
                # Converter tarefa base para avançada
                advanced_metrics = AdvancedProgressMetrics(
                    percentage=base_task.progress.percentage,
                    bytes_downloaded=base_task.progress.bytes_downloaded,
                    total_bytes=base_task.progress.total_bytes,
                    speed_bps=base_task.progress.speed_bps,
                    eta_seconds=base_task.progress.eta_seconds,
                    current_step=base_task.progress.current_step,
                    total_steps=base_task.progress.total_steps,
                    step_progress=base_task.progress.step_progress
                )
                timeline = TaskTimeline(task_id=task_id)
            
            # Criar AdvancedTaskInfo
            return AdvancedTaskInfo(
                task_id=base_task.task_id,
                task_type=base_task.task_type,
                status=base_task.status,
                progress=advanced_metrics,
                created_at=base_task.created_at,
                started_at=base_task.started_at,
                updated_at=base_task.updated_at,
                completed_at=base_task.completed_at,
                error=base_task.error,
                metadata=base_task.metadata,
                events_count=base_task.events_count,
                timeline=timeline
            )
            
        except Exception as e:
            logger.error(f"Erro ao obter informações avançadas da tarefa {task_id}: {e}")
            return None
    
    async def _save_advanced_data(
        self,
        task_id: str,
        metrics: AdvancedProgressMetrics,
        timeline: TaskTimeline
    ) -> None:
        """Salva dados avançados no Redis"""
        try:
            # Salvar métricas
            metrics_key = f"{self.METRICS_KEY_PREFIX}{task_id}"
            await self._redis.set(
                metrics_key,
                json.dumps(asdict(metrics)),
                ex=30 * 24 * 3600  # 30 dias TTL
            )
            
            # Salvar timeline
            timeline_key = f"{self.TIMELINE_KEY_PREFIX}{task_id}"
            await self._redis.set(
                timeline_key,
                json.dumps(asdict(timeline)),
                ex=30 * 24 * 3600  # 30 dias TTL
            )
            
        except Exception as e:
            logger.error(f"Erro ao salvar dados avançados da tarefa {task_id}: {e}")
            raise
    
    async def _load_advanced_data(
        self, 
        task_id: str
    ) -> Tuple[Optional[AdvancedProgressMetrics], Optional[TaskTimeline]]:
        """Carrega dados avançados do Redis"""
        try:
            # Carregar métricas
            metrics_key = f"{self.METRICS_KEY_PREFIX}{task_id}"
            metrics_data = await self._redis.get(metrics_key)
            
            # Carregar timeline
            timeline_key = f"{self.TIMELINE_KEY_PREFIX}{task_id}"
            timeline_data = await self._redis.get(timeline_key)
            
            metrics = None
            timeline = None
            
            if metrics_data:
                metrics_dict = json.loads(metrics_data)
                # Reconstruir StageProgress objects
                if 'stages' in metrics_dict:
                    stages = {}
                    for stage_name, stage_data in metrics_dict['stages'].items():
                        stages[stage_name] = StageProgress(**stage_data)
                    metrics_dict['stages'] = stages
                
                metrics = AdvancedProgressMetrics(**metrics_dict)
            
            if timeline_data:
                timeline_dict = json.loads(timeline_data)
                timeline = TaskTimeline(**timeline_dict)
            
            return metrics, timeline
            
        except Exception as e:
            logger.error(f"Erro ao carregar dados avançados da tarefa {task_id}: {e}")
            return None, None
    
    async def _publish_stage_event(
        self,
        task_id: str,
        stage: str,
        event_type: str,
        progress: AdvancedProgressMetrics,
        message: str = "",
        error: Optional[str] = None
    ) -> None:
        """Publica evento específico de estágio"""
        try:
            # Obter informações da tarefa para o tipo
            task_info = await self.get_task_info(task_id)
            if not task_info:
                return
            
            # Criar evento expandido
            event = TaskEvent(
                task_id=task_id,
                task_type=task_info.task_type,
                event_type=event_type,
                status=task_info.status,
                progress=progress,
                message=message,
                error=error,
                metadata={
                    "stage": stage,
                    "current_stage": progress.current_stage,
                    "stage_progress": progress.stages.get(stage, StageProgress(stage=stage)).percentage,
                    "overall_progress": progress.calculate_overall_progress(),
                    "eta_seconds": progress.calculate_overall_eta(),
                    "average_speed_bps": progress.average_speed_bps,
                    "peak_speed_bps": progress.peak_speed_bps
                }
            )
            
            # Publicar via canal base
            await self._publish_event(event)
            
        except Exception as e:
            logger.error(f"Erro ao publicar evento de estágio: {e}")
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """Obtém métricas avançadas do sistema"""
        try:
            base_stats = await self.get_statistics()
            
            # Estatísticas avançadas
            advanced_stats = {
                "active_stages": {},
                "average_stage_durations": {},
                "speed_statistics": {
                    "peak_speeds_bps": [],
                    "average_speeds_bps": []
                },
                "stage_completion_rates": {}
            }
            
            # Contar estágios ativos
            stage_counts = {}
            total_speed_samples = []
            
            # Analisar todas as tarefas ativas
            active_tasks = await self.get_active_tasks()
            for task_id in active_tasks:
                metrics, _ = await self._load_advanced_data(task_id)
                if metrics:
                    # Contar estágio atual
                    current_stage = metrics.current_stage
                    if current_stage:
                        stage_counts[current_stage] = stage_counts.get(current_stage, 0) + 1
                    
                    # Coletar estatísticas de velocidade
                    if metrics.average_speed_bps > 0:
                        total_speed_samples.append(metrics.average_speed_bps)
                    
                    # Coletar velocidade pico
                    if metrics.peak_speed_bps > 0:
                        advanced_stats["speed_statistics"]["peak_speeds_bps"].append(metrics.peak_speed_bps)
            
            advanced_stats["active_stages"] = stage_counts
            
            # Calcular estatísticas de velocidade
            if total_speed_samples:
                advanced_stats["speed_statistics"]["average_speeds_bps"] = total_speed_samples
                advanced_stats["speed_statistics"]["overall_average_bps"] = sum(total_speed_samples) / len(total_speed_samples)
                advanced_stats["speed_statistics"]["median_speed_bps"] = sorted(total_speed_samples)[len(total_speed_samples) // 2]
            
            # Combinar com estatísticas base
            return {
                **base_stats,
                "advanced_metrics": advanced_stats,
                "performance": {
                    "concurrent_stages": len(stage_counts),
                    "total_active_stages": sum(stage_counts.values()),
                    "speed_tracking_enabled": len(self._speed_history) > 0
                }
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter métricas do sistema: {e}")
            return await self.get_statistics()  # Fallback para estatísticas base


@dataclass
class AdvancedTaskInfo:
    """Informações completas de uma tarefa avançada"""
    task_id: str
    task_type: TaskType
    status: TaskStatus
    progress: AdvancedProgressMetrics
    created_at: str
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    events_count: int = 0
    timeline: Optional[TaskTimeline] = None


# Instância global
advanced_progress_manager: Optional[AdvancedProgressManager] = None


async def get_advanced_progress_manager(sse_manager: Optional[SSEManager] = None) -> AdvancedProgressManager:
    """Obtém instância global do advanced progress manager"""
    global advanced_progress_manager
    
    if advanced_progress_manager is None:
        advanced_progress_manager = AdvancedProgressManager(sse_manager)
        await advanced_progress_manager.initialize()
    
    return advanced_progress_manager


async def init_advanced_progress_manager(sse_manager: Optional[SSEManager] = None) -> None:
    """Inicializa o advanced progress manager"""
    await get_advanced_progress_manager(sse_manager)


async def close_advanced_progress_manager() -> None:
    """Fecha o advanced progress manager"""
    global advanced_progress_manager
    
    if advanced_progress_manager:
        await advanced_progress_manager.close()
        advanced_progress_manager = None