"""
FASE 4 - CUTOVER HEALTH CHECKER
Monitoramento contínuo da saúde do sistema durante cutover
Real-time monitoring, alertas automáticos, detecção de anomalias

Agent-Deployment - Production Cutover Final
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable, Set
from dataclasses import dataclass, field
from enum import Enum
import statistics

from loguru import logger

from app.services.redis_connection import get_redis_client, redis_manager
from app.services.hybrid_mode_manager import hybrid_mode_manager
from scripts.redis_system_monitor import RedisSystemMonitor


class HealthStatus(Enum):
    """Status de saúde do sistema"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class AlertLevel(Enum):
    """Níveis de alerta"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class HealthMetric:
    """Métrica de saúde do sistema"""
    name: str
    value: Any
    threshold_warning: Optional[float] = None
    threshold_critical: Optional[float] = None
    status: HealthStatus = HealthStatus.HEALTHY
    timestamp: datetime = field(default_factory=datetime.now)
    trend: Optional[str] = None  # "increasing", "decreasing", "stable"
    
    def evaluate_status(self) -> HealthStatus:
        """Avalia status baseado nos thresholds"""
        if not isinstance(self.value, (int, float)):
            return HealthStatus.UNKNOWN
        
        if self.threshold_critical and self.value >= self.threshold_critical:
            self.status = HealthStatus.CRITICAL
        elif self.threshold_warning and self.value >= self.threshold_warning:
            self.status = HealthStatus.WARNING
        else:
            self.status = HealthStatus.HEALTHY
        
        return self.status


@dataclass
class HealthAlert:
    """Alerta de saúde do sistema"""
    level: AlertLevel
    message: str
    metric_name: str
    current_value: Any
    threshold_value: Optional[float]
    timestamp: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level.value,
            "message": self.message,
            "metric_name": self.metric_name,
            "current_value": self.current_value,
            "threshold_value": self.threshold_value,
            "timestamp": self.timestamp.isoformat(),
            "resolved": self.resolved
        }


@dataclass
class HealthCheckResult:
    """Resultado de uma verificação de saúde"""
    overall_status: HealthStatus
    metrics: Dict[str, HealthMetric]
    alerts: List[HealthAlert]
    timestamp: datetime = field(default_factory=datetime.now)
    execution_time_ms: float = 0
    
    @property
    def critical_alerts_count(self) -> int:
        return len([a for a in self.alerts if a.level == AlertLevel.CRITICAL and not a.resolved])
    
    @property
    def warning_alerts_count(self) -> int:
        return len([a for a in self.alerts if a.level == AlertLevel.WARNING and not a.resolved])


class CutoverHealthChecker:
    """
    Monitor de saúde contínuo durante cutover de produção
    
    Funcionalidades:
    - Monitoramento em tempo real de métricas críticas
    - Detecção automática de anomalias
    - Sistema de alertas em níveis
    - Análise de tendências
    - Dashboard de saúde em tempo real
    - Integração com sistemas de rollback
    """
    
    def __init__(self):
        # Configurações de monitoramento
        self.monitoring_interval_seconds = 5
        self.metric_history_size = 100
        self.alert_cooldown_minutes = 5
        
        # Estado do monitor
        self.is_monitoring = False
        self.monitoring_task: Optional[asyncio.Task] = None
        
        # Histórico de métricas
        self.metric_history: Dict[str, List[HealthMetric]] = {}
        
        # Sistema de alertas
        self.active_alerts: List[HealthAlert] = []
        self.alert_history: List[HealthAlert] = []
        self.alert_callbacks: List[Callable] = []
        
        # Métricas críticas para monitorar
        self.critical_metrics = {
            "redis_ping_time": {"warning": 10, "critical": 50},  # ms
            "redis_memory_usage": {"warning": 0.8, "critical": 0.9},  # percentual
            "system_cpu_usage": {"warning": 80, "critical": 95},  # percentual  
            "system_memory_usage": {"warning": 85, "critical": 95},  # percentual
            "redis_connected_clients": {"warning": 90, "critical": 100},  # count
            "operation_success_rate": {"warning": 0.95, "critical": 0.90},  # percentual (inverted)
            "data_consistency_score": {"warning": 0.95, "critical": 0.90},  # percentual (inverted)
        }
        
        # Componentes auxiliares
        self.redis_monitor = RedisSystemMonitor()
        
        # Dashboard em tempo real
        self.dashboard_data = {}
        
        logger.info("🏥 CutoverHealthChecker initialized for continuous monitoring")
    
    async def start_monitoring(self, duration_minutes: Optional[int] = None):
        """
        Inicia monitoramento contínuo
        
        Args:
            duration_minutes: Duração do monitoramento (None = indefinido)
        """
        if self.is_monitoring:
            logger.warning("Health monitoring already active")
            return
        
        logger.critical("🏥 STARTING CONTINUOUS HEALTH MONITORING")
        
        self.is_monitoring = True
        
        # Iniciar task de monitoramento
        self.monitoring_task = asyncio.create_task(
            self._monitoring_loop(duration_minutes)
        )
        
        logger.success("✅ Health monitoring started")
        
        return self.monitoring_task
    
    async def stop_monitoring(self):
        """Para monitoramento contínuo"""
        if not self.is_monitoring:
            return
        
        logger.info("🛑 Stopping health monitoring")
        
        self.is_monitoring = False
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.success("✅ Health monitoring stopped")
    
    async def _monitoring_loop(self, duration_minutes: Optional[int]):
        """Loop principal de monitoramento"""
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=duration_minutes) if duration_minutes else None
        
        check_count = 0
        
        try:
            while self.is_monitoring:
                # Verificar se deve parar por duração
                if end_time and datetime.now() >= end_time:
                    logger.info(f"Monitoring duration completed: {duration_minutes} minutes")
                    break
                
                # Executar verificação de saúde
                try:
                    health_result = await self._execute_health_check()
                    check_count += 1
                    
                    # Processar resultado
                    await self._process_health_result(health_result)
                    
                    # Atualizar dashboard
                    await self._update_dashboard(health_result)
                    
                    # Log periódico
                    if check_count % 12 == 0:  # A cada minuto (5s * 12 = 60s)
                        logger.info(f"Health monitoring active: {health_result.overall_status.value} "
                                  f"({health_result.critical_alerts_count} critical, "
                                  f"{health_result.warning_alerts_count} warnings)")
                    
                except Exception as e:
                    logger.error(f"Health check failed: {str(e)}")
                    
                    # Criar alerta de falha de monitoramento
                    alert = HealthAlert(
                        level=AlertLevel.WARNING,
                        message=f"Health check execution failed: {str(e)}",
                        metric_name="monitoring_system",
                        current_value=str(e)
                    )
                    await self._handle_alert(alert)
                
                # Aguardar próxima verificação
                await asyncio.sleep(self.monitoring_interval_seconds)
                
        except asyncio.CancelledError:
            logger.info("Health monitoring cancelled")
        except Exception as e:
            logger.error(f"Health monitoring loop error: {str(e)}")
        finally:
            self.is_monitoring = False
    
    async def _execute_health_check(self) -> HealthCheckResult:
        """Executa verificação completa de saúde"""
        check_start = time.time()
        metrics = {}
        alerts = []
        
        # 1. Verificar Redis
        redis_metrics = await self._check_redis_health()
        metrics.update(redis_metrics)
        
        # 2. Verificar sistema
        system_metrics = await self._check_system_health()
        metrics.update(system_metrics)
        
        # 3. Verificar operações
        operation_metrics = await self._check_operation_health()
        metrics.update(operation_metrics)
        
        # 4. Verificar consistência de dados
        data_metrics = await self._check_data_health()
        metrics.update(data_metrics)
        
        # 5. Avaliar métricas e gerar alertas
        for metric_name, metric in metrics.items():
            metric.evaluate_status()
            
            # Gerar alertas se necessário
            if metric.status == HealthStatus.CRITICAL:
                alert = HealthAlert(
                    level=AlertLevel.CRITICAL,
                    message=f"Critical threshold exceeded: {metric_name} = {metric.value}",
                    metric_name=metric_name,
                    current_value=metric.value,
                    threshold_value=metric.threshold_critical
                )
                alerts.append(alert)
                
            elif metric.status == HealthStatus.WARNING:
                alert = HealthAlert(
                    level=AlertLevel.WARNING,
                    message=f"Warning threshold exceeded: {metric_name} = {metric.value}",
                    metric_name=metric_name,
                    current_value=metric.value,
                    threshold_value=metric.threshold_warning
                )
                alerts.append(alert)
        
        # 6. Determinar status geral
        overall_status = self._determine_overall_status(metrics)
        
        execution_time = (time.time() - check_start) * 1000
        
        return HealthCheckResult(
            overall_status=overall_status,
            metrics=metrics,
            alerts=alerts,
            execution_time_ms=execution_time
        )
    
    async def _check_redis_health(self) -> Dict[str, HealthMetric]:
        """Verifica saúde do Redis"""
        metrics = {}
        
        try:
            # Health check Redis
            health = await redis_manager.health_check()
            
            # Ping time
            ping_time = health.get("ping_time_ms", 0)
            metrics["redis_ping_time"] = HealthMetric(
                name="redis_ping_time",
                value=ping_time,
                threshold_warning=self.critical_metrics["redis_ping_time"]["warning"],
                threshold_critical=self.critical_metrics["redis_ping_time"]["critical"]
            )
            
            # Memory usage (percentual)
            used_memory = health.get("used_memory", 0)
            # Assumir 1GB como limite máximo para cálculo percentual
            max_memory = 1073741824  # 1GB
            memory_usage_pct = (used_memory / max_memory) if used_memory else 0
            
            metrics["redis_memory_usage"] = HealthMetric(
                name="redis_memory_usage",
                value=memory_usage_pct,
                threshold_warning=self.critical_metrics["redis_memory_usage"]["warning"],
                threshold_critical=self.critical_metrics["redis_memory_usage"]["critical"]
            )
            
            # Connected clients
            connected_clients = health.get("connected_clients", 0)
            metrics["redis_connected_clients"] = HealthMetric(
                name="redis_connected_clients",
                value=connected_clients,
                threshold_warning=self.critical_metrics["redis_connected_clients"]["warning"],
                threshold_critical=self.critical_metrics["redis_connected_clients"]["critical"]
            )
            
            # Pool stats
            pool_stats = health.get("pool_stats", {})
            created_connections = pool_stats.get("created_connections", 0)
            available_connections = pool_stats.get("available_connections", 0)
            
            metrics["redis_pool_utilization"] = HealthMetric(
                name="redis_pool_utilization",
                value=created_connections,
                threshold_warning=80,
                threshold_critical=95
            )
            
        except Exception as e:
            logger.error(f"Redis health check failed: {str(e)}")
            metrics["redis_availability"] = HealthMetric(
                name="redis_availability",
                value=0,
                threshold_warning=0.5,
                threshold_critical=0
            )
        
        return metrics
    
    async def _check_system_health(self) -> Dict[str, HealthMetric]:
        """Verifica saúde do sistema"""
        metrics = {}
        
        try:
            import psutil
            
            # CPU usage
            cpu_usage = psutil.cpu_percent(interval=0.1)
            metrics["system_cpu_usage"] = HealthMetric(
                name="system_cpu_usage",
                value=cpu_usage,
                threshold_warning=self.critical_metrics["system_cpu_usage"]["warning"],
                threshold_critical=self.critical_metrics["system_cpu_usage"]["critical"]
            )
            
            # Memory usage
            memory = psutil.virtual_memory()
            metrics["system_memory_usage"] = HealthMetric(
                name="system_memory_usage",
                value=memory.percent,
                threshold_warning=self.critical_metrics["system_memory_usage"]["warning"],
                threshold_critical=self.critical_metrics["system_memory_usage"]["critical"]
            )
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_usage_pct = (disk.used / disk.total) * 100
            metrics["system_disk_usage"] = HealthMetric(
                name="system_disk_usage",
                value=disk_usage_pct,
                threshold_warning=80,
                threshold_critical=90
            )
            
            # Network connections (para detectar possíveis vazamentos)
            connections = len(psutil.net_connections())
            metrics["system_network_connections"] = HealthMetric(
                name="system_network_connections",
                value=connections,
                threshold_warning=1000,
                threshold_critical=2000
            )
            
        except Exception as e:
            logger.error(f"System health check failed: {str(e)}")
            metrics["system_availability"] = HealthMetric(
                name="system_availability",
                value=0,
                threshold_critical=0
            )
        
        return metrics
    
    async def _check_operation_health(self) -> Dict[str, HealthMetric]:
        """Verifica saúde das operações"""
        metrics = {}
        
        try:
            # Testar operações básicas
            operation_results = []
            
            # Teste 1: Redis ping
            try:
                redis_client = await get_redis_client()
                await redis_client.ping()
                operation_results.append(True)
            except Exception:
                operation_results.append(False)
            
            # Teste 2: Listar audios
            try:
                from app.services.redis_audio_manager import RedisAudioManager
                audio_manager = RedisAudioManager()
                audios = await audio_manager.get_audios()
                operation_results.append(isinstance(audios, list))
            except Exception:
                operation_results.append(False)
            
            # Teste 3: Listar videos
            try:
                from app.services.redis_video_manager import RedisVideoManager
                video_manager = RedisVideoManager()
                videos = await video_manager.get_videos()
                operation_results.append(isinstance(videos, list))
            except Exception:
                operation_results.append(False)
            
            # Calcular taxa de sucesso
            success_rate = sum(operation_results) / len(operation_results) if operation_results else 0
            
            metrics["operation_success_rate"] = HealthMetric(
                name="operation_success_rate",
                value=success_rate,
                threshold_warning=self.critical_metrics["operation_success_rate"]["warning"],
                threshold_critical=self.critical_metrics["operation_success_rate"]["critical"]
            )
            
            # Tempo de resposta das operações
            start_time = time.time()
            redis_client = await get_redis_client()
            await redis_client.ping()
            response_time = (time.time() - start_time) * 1000
            
            metrics["operation_response_time"] = HealthMetric(
                name="operation_response_time",
                value=response_time,
                threshold_warning=20,
                threshold_critical=100
            )
            
        except Exception as e:
            logger.error(f"Operation health check failed: {str(e)}")
            metrics["operation_availability"] = HealthMetric(
                name="operation_availability",
                value=0,
                threshold_critical=0
            )
        
        return metrics
    
    async def _check_data_health(self) -> Dict[str, HealthMetric]:
        """Verifica saúde dos dados"""
        metrics = {}
        
        try:
            # Contar dados disponíveis
            redis_client = await get_redis_client()
            
            audio_keys = await redis_client.keys("audio:*")
            video_keys = await redis_client.keys("video:*")
            
            total_data_count = len(audio_keys) + len(video_keys)
            
            metrics["data_availability_count"] = HealthMetric(
                name="data_availability_count",
                value=total_data_count,
                threshold_warning=1,  # Pelo menos 1 item
                threshold_critical=0   # Nenhum item é crítico
            )
            
            # Verificar integridade de amostra de dados
            sample_valid = 0
            sample_total = 0
            
            # Verificar até 5 itens de áudio
            sample_keys = audio_keys[:5]
            for key in sample_keys:
                sample_total += 1
                try:
                    data = await redis_client.get(key)
                    if data:
                        json.loads(data)  # Verificar se é JSON válido
                        sample_valid += 1
                except Exception:
                    pass
            
            data_integrity_score = sample_valid / sample_total if sample_total > 0 else 1
            
            metrics["data_consistency_score"] = HealthMetric(
                name="data_consistency_score",
                value=data_integrity_score,
                threshold_warning=self.critical_metrics["data_consistency_score"]["warning"],
                threshold_critical=self.critical_metrics["data_consistency_score"]["critical"]
            )
            
        except Exception as e:
            logger.error(f"Data health check failed: {str(e)}")
            metrics["data_availability"] = HealthMetric(
                name="data_availability",
                value=0,
                threshold_critical=0
            )
        
        return metrics
    
    def _determine_overall_status(self, metrics: Dict[str, HealthMetric]) -> HealthStatus:
        """Determina status geral baseado nas métricas"""
        if not metrics:
            return HealthStatus.UNKNOWN
        
        # Verificar se há métricas críticas
        critical_count = len([m for m in metrics.values() if m.status == HealthStatus.CRITICAL])
        warning_count = len([m for m in metrics.values() if m.status == HealthStatus.WARNING])
        
        if critical_count > 0:
            return HealthStatus.CRITICAL
        elif warning_count > 0:
            return HealthStatus.WARNING
        else:
            return HealthStatus.HEALTHY
    
    async def _process_health_result(self, result: HealthCheckResult):
        """Processa resultado de verificação de saúde"""
        # Armazenar histórico de métricas
        for metric_name, metric in result.metrics.items():
            if metric_name not in self.metric_history:
                self.metric_history[metric_name] = []
            
            self.metric_history[metric_name].append(metric)
            
            # Manter apenas últimas N métricas
            if len(self.metric_history[metric_name]) > self.metric_history_size:
                self.metric_history[metric_name] = self.metric_history[metric_name][-self.metric_history_size:]
            
            # Calcular tendência
            self._calculate_metric_trend(metric_name)
        
        # Processar alertas
        for alert in result.alerts:
            await self._handle_alert(alert)
    
    def _calculate_metric_trend(self, metric_name: str):
        """Calcula tendência de uma métrica"""
        if metric_name not in self.metric_history or len(self.metric_history[metric_name]) < 3:
            return
        
        recent_values = [m.value for m in self.metric_history[metric_name][-10:] if isinstance(m.value, (int, float))]
        
        if len(recent_values) < 3:
            return
        
        # Calcular tendência simples baseada na diferença entre primeiros e últimos valores
        first_half = recent_values[:len(recent_values)//2]
        second_half = recent_values[len(recent_values)//2:]
        
        first_avg = statistics.mean(first_half)
        second_avg = statistics.mean(second_half)
        
        diff_pct = (second_avg - first_avg) / first_avg * 100 if first_avg != 0 else 0
        
        # Atualizar tendência na métrica mais recente
        latest_metric = self.metric_history[metric_name][-1]
        
        if abs(diff_pct) < 5:
            latest_metric.trend = "stable"
        elif diff_pct > 5:
            latest_metric.trend = "increasing"
        else:
            latest_metric.trend = "decreasing"
    
    async def _handle_alert(self, alert: HealthAlert):
        """Processa um alerta"""
        # Verificar cooldown para evitar spam
        recent_similar = [
            a for a in self.alert_history[-10:]
            if (a.metric_name == alert.metric_name and
                a.level == alert.level and
                (datetime.now() - a.timestamp).total_seconds() < self.alert_cooldown_minutes * 60)
        ]
        
        if recent_similar:
            return  # Skip por cooldown
        
        # Adicionar à lista de alertas ativos
        self.active_alerts.append(alert)
        self.alert_history.append(alert)
        
        # Manter apenas últimos 1000 alertas no histórico
        if len(self.alert_history) > 1000:
            self.alert_history = self.alert_history[-1000:]
        
        # Log do alerta
        if alert.level == AlertLevel.CRITICAL:
            logger.critical(f"🚨 CRITICAL ALERT: {alert.message}")
        elif alert.level == AlertLevel.WARNING:
            logger.warning(f"⚠️ WARNING: {alert.message}")
        elif alert.level == AlertLevel.EMERGENCY:
            logger.critical(f"🆘 EMERGENCY: {alert.message}")
        else:
            logger.info(f"ℹ️ INFO: {alert.message}")
        
        # Executar callbacks de alerta
        for callback in self.alert_callbacks:
            try:
                await callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {str(e)}")
    
    async def _update_dashboard(self, result: HealthCheckResult):
        """Atualiza dados do dashboard em tempo real"""
        self.dashboard_data = {
            "timestamp": result.timestamp.isoformat(),
            "overall_status": result.overall_status.value,
            "execution_time_ms": result.execution_time_ms,
            "metrics": {
                name: {
                    "value": metric.value,
                    "status": metric.status.value,
                    "trend": metric.trend
                }
                for name, metric in result.metrics.items()
            },
            "alerts": {
                "active_count": len([a for a in self.active_alerts if not a.resolved]),
                "critical_count": result.critical_alerts_count,
                "warning_count": result.warning_alerts_count,
                "recent_alerts": [a.to_dict() for a in result.alerts]
            },
            "trends": self._get_metric_trends()
        }
    
    def _get_metric_trends(self) -> Dict[str, Any]:
        """Obtém tendências das métricas"""
        trends = {}
        
        for metric_name, history in self.metric_history.items():
            if len(history) >= 5:
                recent_values = [m.value for m in history[-10:] if isinstance(m.value, (int, float))]
                
                if recent_values:
                    trends[metric_name] = {
                        "current": recent_values[-1],
                        "average": statistics.mean(recent_values),
                        "min": min(recent_values),
                        "max": max(recent_values),
                        "trend": history[-1].trend if history else "unknown"
                    }
        
        return trends
    
    def add_alert_callback(self, callback: Callable):
        """Adiciona callback para alertas"""
        self.alert_callbacks.append(callback)
    
    def get_current_health(self) -> Dict[str, Any]:
        """Retorna estado atual de saúde"""
        return self.dashboard_data
    
    def get_active_alerts(self) -> List[HealthAlert]:
        """Retorna alertas ativos"""
        return [a for a in self.active_alerts if not a.resolved]
    
    async def resolve_alert(self, alert_id: int):
        """Resolve um alerta específico"""
        if 0 <= alert_id < len(self.active_alerts):
            self.active_alerts[alert_id].resolved = True
            logger.info(f"Alert resolved: {self.active_alerts[alert_id].message}")
    
    async def get_health_report(self) -> Dict[str, Any]:
        """Gera relatório completo de saúde"""
        active_alerts = self.get_active_alerts()
        
        # Calcular estatísticas
        uptime_seconds = (datetime.now() - datetime.now()).total_seconds()  # Placeholder
        
        report = {
            "report_timestamp": datetime.now().isoformat(),
            "monitoring_status": "active" if self.is_monitoring else "inactive",
            "overall_health": self.dashboard_data.get("overall_status", "unknown"),
            "summary": {
                "active_alerts": len(active_alerts),
                "critical_alerts": len([a for a in active_alerts if a.level == AlertLevel.CRITICAL]),
                "warning_alerts": len([a for a in active_alerts if a.level == AlertLevel.WARNING]),
                "total_metrics_tracked": len(self.metric_history),
                "health_checks_performed": sum(len(history) for history in self.metric_history.values())
            },
            "current_metrics": self.dashboard_data.get("metrics", {}),
            "active_alerts": [alert.to_dict() for alert in active_alerts],
            "metric_trends": self._get_metric_trends(),
            "system_recommendations": self._generate_health_recommendations()
        }
        
        return report
    
    def _generate_health_recommendations(self) -> List[str]:
        """Gera recomendações baseadas na saúde atual"""
        recommendations = []
        active_alerts = self.get_active_alerts()
        
        # Recomendações baseadas em alertas críticos
        critical_alerts = [a for a in active_alerts if a.level == AlertLevel.CRITICAL]
        if critical_alerts:
            recommendations.append("URGENT: Address critical alerts immediately")
            recommendations.append("Consider initiating rollback procedures if issues persist")
        
        # Recomendações baseadas em métricas
        if "redis_ping_time" in self.metric_history:
            recent_ping = self.metric_history["redis_ping_time"][-1]
            if recent_ping.status == HealthStatus.WARNING:
                recommendations.append("Monitor Redis performance - consider connection pool tuning")
        
        if "system_memory_usage" in self.metric_history:
            recent_memory = self.metric_history["system_memory_usage"][-1]
            if recent_memory.status == HealthStatus.WARNING:
                recommendations.append("High memory usage detected - monitor for memory leaks")
        
        # Recomendações gerais
        if not recommendations:
            recommendations.append("System health is good - continue monitoring")
            recommendations.append("Maintain current monitoring frequency")
        
        return recommendations


# Função para criar callback de rollback automático
async def create_rollback_callback(rollback_manager):
    """Cria callback para rollback automático em alertas críticos"""
    async def rollback_on_critical_alert(alert: HealthAlert):
        if alert.level == AlertLevel.EMERGENCY:
            logger.critical("🆘 EMERGENCY ALERT - INITIATING AUTOMATIC ROLLBACK")
            # Aqui seria chamado o rollback manager
            # await rollback_manager.execute_emergency_rollback()
    
    return rollback_on_critical_alert


# Função principal para execução
async def main():
    """Executa monitoramento de saúde"""
    health_checker = CutoverHealthChecker()
    
    try:
        # Iniciar monitoramento por 5 minutos
        await health_checker.start_monitoring(duration_minutes=5)
        
        # Aguardar conclusão
        if health_checker.monitoring_task:
            await health_checker.monitoring_task
        
        # Gerar relatório final
        report = await health_checker.get_health_report()
        logger.info("Health monitoring completed")
        
        return report
        
    finally:
        await health_checker.stop_monitoring()


if __name__ == "__main__":
    asyncio.run(main())