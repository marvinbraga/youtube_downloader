"""
Intensive Monitoring Scheduler - 48-Hour Post-Cutover Monitoring Automation
Sistema de agendamento para monitoramento intensivo pós-cutover de 48 horas

Agent-Infrastructure - FASE 4 Production Monitoring
"""

import asyncio
import json
import schedule
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum
import threading

from loguru import logger

from .production_monitoring import production_monitoring
from .redis_monitor import redis_monitor
from .application_metrics import application_metrics_collector
from .alert_system import alert_system
from .performance_optimizer import performance_optimizer
from .monitoring_dashboard import monitoring_dashboard


class MonitoringPhase(Enum):
    """Fases do monitoramento intensivo"""
    PHASE_1_CRITICAL = "phase_1_critical"      # 0-12h: Crítico
    PHASE_2_HIGH = "phase_2_high"              # 12-24h: Alto
    PHASE_3_NORMAL = "phase_3_normal"          # 24-48h: Normal
    PHASE_4_MAINTENANCE = "phase_4_maintenance" # 48h+: Manutenção


@dataclass
class MonitoringConfiguration:
    """Configuração de monitoramento por fase"""
    phase: MonitoringPhase
    duration_hours: int
    monitoring_interval_seconds: int
    alert_sensitivity: str  # critical, high, medium, low
    optimization_enabled: bool
    dashboard_update_interval_seconds: int
    health_report_interval_hours: int
    automatic_actions_enabled: bool
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['phase'] = self.phase.value
        return data


@dataclass
class MonitoringSchedule:
    """Agendamento completo do monitoramento"""
    cutover_timestamp: datetime
    current_phase: MonitoringPhase
    phase_start_time: datetime
    total_monitoring_hours: int = 48
    phases_configuration: Dict[MonitoringPhase, MonitoringConfiguration] = field(default_factory=dict)
    
    @property
    def hours_since_cutover(self) -> float:
        return (datetime.now() - self.cutover_timestamp).total_seconds() / 3600
    
    @property
    def current_phase_elapsed_hours(self) -> float:
        return (datetime.now() - self.phase_start_time).total_seconds() / 3600
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['cutover_timestamp'] = self.cutover_timestamp.isoformat()
        data['current_phase'] = self.current_phase.value
        data['phase_start_time'] = self.phase_start_time.isoformat()
        data['phases_configuration'] = {
            phase.value: config.to_dict() 
            for phase, config in self.phases_configuration.items()
        }
        return data


class IntensiveMonitoringScheduler:
    """
    Agendador para monitoramento intensivo pós-cutover
    
    Funcionalidades:
    - Monitoramento em fases com diferentes intensidades
    - Automação completa por 48 horas
    - Ajuste automático de parâmetros por fase
    - Relatórios automáticos
    - Escalação de alertas
    - Dashboard em tempo real
    - Otimização automática baseada em fase
    """
    
    def __init__(self):
        self.is_running = False
        self._stop_monitoring = False
        self._monitoring_schedule: Optional[MonitoringSchedule] = None
        
        # Tasks em execução
        self._monitoring_tasks: List[asyncio.Task] = []
        self._scheduler_thread: Optional[threading.Thread] = None
        
        # Configurações por fase
        self._phase_configurations = {
            MonitoringPhase.PHASE_1_CRITICAL: MonitoringConfiguration(
                phase=MonitoringPhase.PHASE_1_CRITICAL,
                duration_hours=12,
                monitoring_interval_seconds=15,  # Muito frequente
                alert_sensitivity="critical",
                optimization_enabled=True,
                dashboard_update_interval_seconds=5,
                health_report_interval_hours=2,
                automatic_actions_enabled=True
            ),
            MonitoringPhase.PHASE_2_HIGH: MonitoringConfiguration(
                phase=MonitoringPhase.PHASE_2_HIGH,
                duration_hours=12,
                monitoring_interval_seconds=30,  # Frequente
                alert_sensitivity="high",
                optimization_enabled=True,
                dashboard_update_interval_seconds=10,
                health_report_interval_hours=4,
                automatic_actions_enabled=True
            ),
            MonitoringPhase.PHASE_3_NORMAL: MonitoringConfiguration(
                phase=MonitoringPhase.PHASE_3_NORMAL,
                duration_hours=24,
                monitoring_interval_seconds=60,  # Normal
                alert_sensitivity="medium",
                optimization_enabled=True,
                dashboard_update_interval_seconds=30,
                health_report_interval_hours=6,
                automatic_actions_enabled=False
            ),
            MonitoringPhase.PHASE_4_MAINTENANCE: MonitoringConfiguration(
                phase=MonitoringPhase.PHASE_4_MAINTENANCE,
                duration_hours=0,  # Contínuo
                monitoring_interval_seconds=300,  # 5 minutos
                alert_sensitivity="low",
                optimization_enabled=False,
                dashboard_update_interval_seconds=60,
                health_report_interval_hours=24,
                automatic_actions_enabled=False
            )
        }
        
        # Estatísticas
        self._monitoring_stats = {
            'total_monitoring_time_hours': 0.0,
            'phases_completed': [],
            'total_alerts_generated': 0,
            'total_optimizations_applied': 0,
            'total_health_reports_generated': 0,
            'system_stability_score': 0.0
        }
        
        logger.info("IntensiveMonitoringScheduler initialized")
    
    async def start_intensive_monitoring(self, cutover_timestamp: Optional[datetime] = None):
        """Inicia monitoramento intensivo pós-cutover"""
        if self.is_running:
            logger.warning("Intensive monitoring already running")
            return
        
        cutover_time = cutover_timestamp or datetime.now()
        
        # Cria cronograma de monitoramento
        self._monitoring_schedule = MonitoringSchedule(
            cutover_timestamp=cutover_time,
            current_phase=MonitoringPhase.PHASE_1_CRITICAL,
            phase_start_time=cutover_time,
            phases_configuration=self._phase_configurations
        )
        
        self.is_running = True
        self._stop_monitoring = False
        
        logger.info(
            f"Starting intensive 48-hour monitoring at {cutover_time.isoformat()} "
            f"(Phase 1: Critical - 0-12h)"
        )
        
        # Inicia todos os componentes de monitoramento
        await self._start_monitoring_components()
        
        # Inicia tasks principais
        await self._start_monitoring_tasks()
        
        # Inicia scheduler em thread separada
        self._start_scheduler_thread()
    
    async def stop_intensive_monitoring(self):
        """Para monitoramento intensivo"""
        if not self.is_running:
            return
        
        self._stop_monitoring = True
        self.is_running = False
        
        logger.info("Stopping intensive monitoring...")
        
        # Para scheduler
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            schedule.clear()
            self._scheduler_thread = None
        
        # Para tasks de monitoramento
        for task in self._monitoring_tasks:
            if not task.done():
                task.cancel()
        
        self._monitoring_tasks.clear()
        
        # Para componentes de monitoramento
        await self._stop_monitoring_components()
        
        # Gera relatório final
        await self._generate_final_report()
        
        logger.info("Intensive monitoring stopped")
    
    async def _start_monitoring_components(self):
        """Inicia todos os componentes de monitoramento"""
        try:
            # Production monitoring
            if not production_monitoring.is_monitoring:
                monitoring_task = asyncio.create_task(production_monitoring.start_monitoring())
                self._monitoring_tasks.append(monitoring_task)
            
            # Redis monitor
            if not redis_monitor.is_monitoring:
                redis_task = asyncio.create_task(redis_monitor.start_monitoring())
                self._monitoring_tasks.append(redis_task)
            
            # Application metrics collector
            if not application_metrics_collector.is_collecting:
                metrics_task = asyncio.create_task(application_metrics_collector.start_collection())
                self._monitoring_tasks.append(metrics_task)
            
            # Alert system
            if not alert_system.is_running:
                alert_task = asyncio.create_task(alert_system.start_monitoring())
                self._monitoring_tasks.append(alert_task)
            
            # Performance optimizer
            if not performance_optimizer.is_optimizing:
                optimizer_task = asyncio.create_task(performance_optimizer.start_optimization())
                self._monitoring_tasks.append(optimizer_task)
            
            # Monitoring dashboard
            await monitoring_dashboard.start_background_broadcast()
            
            logger.info("All monitoring components started successfully")
            
        except Exception as e:
            logger.error(f"Error starting monitoring components: {e}")
            raise
    
    async def _stop_monitoring_components(self):
        """Para todos os componentes de monitoramento"""
        try:
            # Para componentes
            if production_monitoring.is_monitoring:
                await production_monitoring.stop_monitoring()
            
            if redis_monitor.is_monitoring:
                await redis_monitor.stop_monitoring()
            
            if application_metrics_collector.is_collecting:
                await application_metrics_collector.stop_collection()
            
            if alert_system.is_running:
                await alert_system.stop_monitoring()
            
            if performance_optimizer.is_optimizing:
                await performance_optimizer.stop_optimization()
            
            await monitoring_dashboard.stop_background_broadcast()
            
            logger.info("All monitoring components stopped")
            
        except Exception as e:
            logger.error(f"Error stopping monitoring components: {e}")
    
    async def _start_monitoring_tasks(self):
        """Inicia tasks específicas do scheduler"""
        # Task de gerenciamento de fases
        phase_manager_task = asyncio.create_task(self._phase_management_loop())
        self._monitoring_tasks.append(phase_manager_task)
        
        # Task de coleta de estatísticas
        stats_task = asyncio.create_task(self._statistics_collection_loop())
        self._monitoring_tasks.append(stats_task)
        
        # Task de verificação de saúde
        health_check_task = asyncio.create_task(self._health_check_loop())
        self._monitoring_tasks.append(health_check_task)
        
        logger.info("Scheduler monitoring tasks started")
    
    def _start_scheduler_thread(self):
        """Inicia thread do scheduler"""
        def run_scheduler():
            while not self._stop_monitoring:
                schedule.run_pending()
                time.sleep(1)
        
        self._scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        self._scheduler_thread.start()
        
        # Agenda tarefas automáticas
        self._schedule_automatic_tasks()
    
    def _schedule_automatic_tasks(self):
        """Agenda tarefas automáticas baseadas na configuração atual"""
        if not self._monitoring_schedule:
            return
        
        config = self._monitoring_schedule.phases_configuration.get(
            self._monitoring_schedule.current_phase
        )
        
        if not config:
            return
        
        # Limpa agendamentos anteriores
        schedule.clear()
        
        # Agenda relatórios de saúde
        schedule.every(config.health_report_interval_hours).hours.do(
            self._schedule_health_report
        )
        
        # Agenda backup de configuração
        schedule.every(6).hours.do(self._schedule_configuration_backup)
        
        # Agenda limpeza de logs antigos
        schedule.every(12).hours.do(self._schedule_log_cleanup)
        
        # Agenda verificação de conectividade
        schedule.every(30).minutes.do(self._schedule_connectivity_check)
        
        logger.info(f"Scheduled automatic tasks for phase {self._monitoring_schedule.current_phase.value}")
    
    def _schedule_health_report(self):
        """Agenda geração de relatório de saúde"""
        asyncio.create_task(self._generate_health_report())
    
    def _schedule_configuration_backup(self):
        """Agenda backup de configuração"""
        asyncio.create_task(self._backup_configuration())
    
    def _schedule_log_cleanup(self):
        """Agenda limpeza de logs"""
        asyncio.create_task(self._cleanup_old_logs())
    
    def _schedule_connectivity_check(self):
        """Agenda verificação de conectividade"""
        asyncio.create_task(self._check_system_connectivity())
    
    async def _phase_management_loop(self):
        """Loop de gerenciamento de fases"""
        while not self._stop_monitoring:
            try:
                await self._check_phase_transition()
                await asyncio.sleep(60)  # Verifica a cada minuto
                
            except Exception as e:
                logger.error(f"Error in phase management loop: {e}")
                await asyncio.sleep(60)
    
    async def _check_phase_transition(self):
        """Verifica se deve transicionar para próxima fase"""
        if not self._monitoring_schedule:
            return
        
        current_phase = self._monitoring_schedule.current_phase
        phase_config = self._monitoring_schedule.phases_configuration.get(current_phase)
        
        if not phase_config:
            return
        
        elapsed_hours = self._monitoring_schedule.current_phase_elapsed_hours
        
        # Verifica se deve transicionar
        if elapsed_hours >= phase_config.duration_hours:
            await self._transition_to_next_phase()
    
    async def _transition_to_next_phase(self):
        """Transiciona para próxima fase"""
        if not self._monitoring_schedule:
            return
        
        current_phase = self._monitoring_schedule.current_phase
        next_phase = None
        
        # Determina próxima fase
        if current_phase == MonitoringPhase.PHASE_1_CRITICAL:
            next_phase = MonitoringPhase.PHASE_2_HIGH
        elif current_phase == MonitoringPhase.PHASE_2_HIGH:
            next_phase = MonitoringPhase.PHASE_3_NORMAL
        elif current_phase == MonitoringPhase.PHASE_3_NORMAL:
            next_phase = MonitoringPhase.PHASE_4_MAINTENANCE
        
        if not next_phase:
            # Monitoramento intensivo completado
            logger.info("48-hour intensive monitoring completed - transitioning to maintenance mode")
            await self._complete_intensive_monitoring()
            return
        
        # Atualiza cronograma
        self._monitoring_schedule.current_phase = next_phase
        self._monitoring_schedule.phase_start_time = datetime.now()
        
        # Atualiza estatísticas
        self._monitoring_stats['phases_completed'].append(current_phase.value)
        
        # Reconfigura componentes para nova fase
        await self._reconfigure_for_phase(next_phase)
        
        # Reagenda tarefas automáticas
        self._schedule_automatic_tasks()
        
        # Gera relatório de transição
        await self._generate_phase_transition_report(current_phase, next_phase)
        
        logger.info(
            f"PHASE TRANSITION: {current_phase.value} -> {next_phase.value} "
            f"(Total monitoring time: {self._monitoring_schedule.hours_since_cutover:.1f}h)"
        )
    
    async def _reconfigure_for_phase(self, phase: MonitoringPhase):
        """Reconfigura componentes para nova fase"""
        config = self._phase_configurations.get(phase)
        if not config:
            return
        
        try:
            # Ajusta intervalos de monitoramento (seria necessário modificar os componentes)
            # Por ora, apenas logamos as mudanças
            logger.info(
                f"Reconfiguring for {phase.value}: "
                f"monitoring_interval={config.monitoring_interval_seconds}s, "
                f"alert_sensitivity={config.alert_sensitivity}, "
                f"optimization_enabled={config.optimization_enabled}"
            )
            
            # Ajusta sensibilidade de alertas
            await self._adjust_alert_sensitivity(config.alert_sensitivity)
            
            # Habilita/desabilita otimização automática
            if config.optimization_enabled and not performance_optimizer.is_optimizing:
                optimizer_task = asyncio.create_task(performance_optimizer.start_optimization())
                self._monitoring_tasks.append(optimizer_task)
            elif not config.optimization_enabled and performance_optimizer.is_optimizing:
                await performance_optimizer.stop_optimization()
            
        except Exception as e:
            logger.error(f"Error reconfiguring for phase {phase.value}: {e}")
    
    async def _adjust_alert_sensitivity(self, sensitivity: str):
        """Ajusta sensibilidade dos alertas"""
        # Mapeia sensibilidade para multiplicadores de threshold
        sensitivity_multipliers = {
            'critical': 0.8,  # 20% mais sensível
            'high': 0.9,      # 10% mais sensível
            'medium': 1.0,    # Padrão
            'low': 1.2        # 20% menos sensível
        }
        
        multiplier = sensitivity_multipliers.get(sensitivity, 1.0)
        
        # Em uma implementação completa, ajustaria os thresholds dos alertas
        logger.info(f"Alert sensitivity adjusted to: {sensitivity} (multiplier: {multiplier})")
    
    async def _complete_intensive_monitoring(self):
        """Completa monitoramento intensivo e transiciona para modo de manutenção"""
        if self._monitoring_schedule:
            self._monitoring_schedule.current_phase = MonitoringPhase.PHASE_4_MAINTENANCE
            self._monitoring_schedule.phase_start_time = datetime.now()
        
        # Gera relatório final do monitoramento intensivo
        await self._generate_final_report()
        
        # Reconfigura para modo de manutenção
        await self._reconfigure_for_phase(MonitoringPhase.PHASE_4_MAINTENANCE)
        
        logger.info("Intensive monitoring completed - system in maintenance monitoring mode")
    
    async def _statistics_collection_loop(self):
        """Loop de coleta de estatísticas"""
        while not self._stop_monitoring:
            try:
                await self._update_monitoring_statistics()
                await asyncio.sleep(300)  # A cada 5 minutos
                
            except Exception as e:
                logger.error(f"Error in statistics collection: {e}")
                await asyncio.sleep(300)
    
    async def _update_monitoring_statistics(self):
        """Atualiza estatísticas de monitoramento"""
        if not self._monitoring_schedule:
            return
        
        try:
            # Atualiza tempo total
            self._monitoring_stats['total_monitoring_time_hours'] = self._monitoring_schedule.hours_since_cutover
            
            # Coleta estatísticas dos componentes
            alert_dashboard = await alert_system.get_alert_dashboard()
            self._monitoring_stats['total_alerts_generated'] = alert_dashboard.get('recent_alerts_24h', 0)
            
            optimizer_status = await performance_optimizer.get_optimization_status()
            self._monitoring_stats['total_optimizations_applied'] = optimizer_status['optimization_stats']['total_optimizations']
            
            # Calcula score de estabilidade do sistema
            production_status = await production_monitoring.get_current_status()
            health_score = production_status.get('health_score', 50)
            active_alerts = alert_dashboard.get('active_alerts_count', 0)
            
            # Score baseado em saúde e número de alertas
            stability_score = max(0, health_score - (active_alerts * 2))
            self._monitoring_stats['system_stability_score'] = round(stability_score, 1)
            
        except Exception as e:
            logger.error(f"Error updating monitoring statistics: {e}")
    
    async def _health_check_loop(self):
        """Loop de verificação de saúde dos componentes"""
        while not self._stop_monitoring:
            try:
                await self._perform_health_checks()
                await asyncio.sleep(120)  # A cada 2 minutos
                
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(120)
    
    async def _perform_health_checks(self):
        """Executa verificações de saúde dos componentes"""
        health_status = {
            'timestamp': datetime.now().isoformat(),
            'components': {}
        }
        
        # Verifica production monitoring
        health_status['components']['production_monitoring'] = {
            'running': production_monitoring.is_monitoring,
            'status': 'healthy' if production_monitoring.is_monitoring else 'stopped'
        }
        
        # Verifica Redis monitor
        health_status['components']['redis_monitor'] = {
            'running': redis_monitor.is_monitoring,
            'status': 'healthy' if redis_monitor.is_monitoring else 'stopped'
        }
        
        # Verifica application metrics collector
        health_status['components']['application_metrics'] = {
            'running': application_metrics_collector.is_collecting,
            'status': 'healthy' if application_metrics_collector.is_collecting else 'stopped'
        }
        
        # Verifica alert system
        health_status['components']['alert_system'] = {
            'running': alert_system.is_running,
            'status': 'healthy' if alert_system.is_running else 'stopped'
        }
        
        # Verifica performance optimizer
        health_status['components']['performance_optimizer'] = {
            'running': performance_optimizer.is_optimizing,
            'status': 'healthy' if performance_optimizer.is_optimizing else 'stopped'
        }
        
        # Verifica se algum componente crítico está parado
        critical_components = ['production_monitoring', 'alert_system']
        failed_components = [
            name for name, status in health_status['components'].items()
            if name in critical_components and not status['running']
        ]
        
        if failed_components:
            logger.error(f"CRITICAL: Components stopped: {failed_components}")
            
            # Tenta reiniciar componentes críticos
            await self._attempt_component_restart(failed_components)
    
    async def _attempt_component_restart(self, failed_components: List[str]):
        """Tenta reiniciar componentes que falharam"""
        for component in failed_components:
            try:
                if component == 'production_monitoring' and not production_monitoring.is_monitoring:
                    monitoring_task = asyncio.create_task(production_monitoring.start_monitoring())
                    self._monitoring_tasks.append(monitoring_task)
                    logger.info(f"Restarted component: {component}")
                
                elif component == 'alert_system' and not alert_system.is_running:
                    alert_task = asyncio.create_task(alert_system.start_monitoring())
                    self._monitoring_tasks.append(alert_task)
                    logger.info(f"Restarted component: {component}")
                
            except Exception as e:
                logger.error(f"Failed to restart component {component}: {e}")
    
    async def _generate_health_report(self):
        """Gera relatório de saúde automático"""
        try:
            if not self._monitoring_schedule:
                return
            
            report = {
                'report_type': 'automated_health_report',
                'timestamp': datetime.now().isoformat(),
                'monitoring_schedule': self._monitoring_schedule.to_dict(),
                'monitoring_statistics': self._monitoring_stats,
                'system_health': await production_monitoring.get_current_status(),
                'redis_performance': await redis_monitor.get_current_status(),
                'application_metrics': await application_metrics_collector.get_current_metrics(),
                'active_alerts': await alert_system.get_alert_dashboard(),
                'optimization_status': await performance_optimizer.get_optimization_status()
            }
            
            # Salva relatório
            report_filename = f"health_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(f"reports/monitoring/{report_filename}", 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            self._monitoring_stats['total_health_reports_generated'] += 1
            
            logger.info(f"Generated automated health report: {report_filename}")
            
        except Exception as e:
            logger.error(f"Error generating health report: {e}")
    
    async def _generate_phase_transition_report(self, from_phase: MonitoringPhase, to_phase: MonitoringPhase):
        """Gera relatório de transição de fase"""
        try:
            report = {
                'report_type': 'phase_transition_report',
                'timestamp': datetime.now().isoformat(),
                'from_phase': from_phase.value,
                'to_phase': to_phase.value,
                'transition_time': datetime.now().isoformat(),
                'total_monitoring_hours': self._monitoring_schedule.hours_since_cutover if self._monitoring_schedule else 0,
                'phase_summary': {
                    'alerts_generated': self._monitoring_stats['total_alerts_generated'],
                    'optimizations_applied': self._monitoring_stats['total_optimizations_applied'],
                    'stability_score': self._monitoring_stats['system_stability_score']
                },
                'recommendations': await self._generate_phase_recommendations(to_phase)
            }
            
            # Salva relatório
            report_filename = f"phase_transition_{from_phase.value}_to_{to_phase.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(f"reports/monitoring/{report_filename}", 'w') as f:
                json.dump(report, f, indent=2, default=str)
            
            logger.info(f"Generated phase transition report: {report_filename}")
            
        except Exception as e:
            logger.error(f"Error generating phase transition report: {e}")
    
    async def _generate_final_report(self):
        """Gera relatório final do monitoramento intensivo"""
        try:
            # Coleta dados finais de todos os componentes
            final_data = {
                'report_type': 'final_intensive_monitoring_report',
                'timestamp': datetime.now().isoformat(),
                'monitoring_duration_hours': self._monitoring_schedule.hours_since_cutover if self._monitoring_schedule else 0,
                'phases_completed': self._monitoring_stats['phases_completed'],
                'final_statistics': self._monitoring_stats,
                'final_system_status': await production_monitoring.get_current_status(),
                'redis_final_report': await redis_monitor.get_performance_report(48),
                'application_final_metrics': await application_metrics_collector.get_metrics_summary(48),
                'alerts_summary': await alert_system.get_alert_history(48),
                'optimizations_summary': await performance_optimizer.get_optimization_report(48),
                'overall_assessment': await self._generate_overall_assessment()
            }
            
            # Salva relatório final
            report_filename = f"final_intensive_monitoring_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(f"reports/monitoring/{report_filename}", 'w') as f:
                json.dump(final_data, f, indent=2, default=str)
            
            logger.info(f"Generated final intensive monitoring report: {report_filename}")
            
        except Exception as e:
            logger.error(f"Error generating final report: {e}")
    
    async def _generate_phase_recommendations(self, phase: MonitoringPhase) -> List[str]:
        """Gera recomendações para a fase"""
        recommendations = []
        
        if phase == MonitoringPhase.PHASE_2_HIGH:
            recommendations.extend([
                "Monitor Redis memory usage closely as system stabilizes",
                "Review alert patterns from Phase 1 for threshold adjustments",
                "Validate that all critical optimizations were applied successfully"
            ])
        
        elif phase == MonitoringPhase.PHASE_3_NORMAL:
            recommendations.extend([
                "Begin planning for long-term monitoring strategy",
                "Review and document effective optimization patterns",
                "Consider reducing alert sensitivity for stable metrics"
            ])
        
        elif phase == MonitoringPhase.PHASE_4_MAINTENANCE:
            recommendations.extend([
                "Transition to standard monitoring intervals",
                "Archive intensive monitoring data",
                "Plan regular performance reviews based on learned patterns"
            ])
        
        return recommendations
    
    async def _generate_overall_assessment(self) -> Dict[str, Any]:
        """Gera avaliação geral do período de monitoramento"""
        try:
            stability_score = self._monitoring_stats['system_stability_score']
            total_alerts = self._monitoring_stats['total_alerts_generated']
            
            # Determina classificação geral
            if stability_score >= 90 and total_alerts < 10:
                assessment = "excellent"
                confidence = "high"
            elif stability_score >= 75 and total_alerts < 25:
                assessment = "good"
                confidence = "high"
            elif stability_score >= 60 and total_alerts < 50:
                assessment = "fair"
                confidence = "medium"
            else:
                assessment = "needs_attention"
                confidence = "low"
            
            return {
                'overall_assessment': assessment,
                'confidence_level': confidence,
                'stability_score': stability_score,
                'key_metrics': {
                    'total_alerts': total_alerts,
                    'optimizations_applied': self._monitoring_stats['total_optimizations_applied'],
                    'monitoring_duration_hours': self._monitoring_stats['total_monitoring_time_hours']
                },
                'recommendations': [
                    "System showed stable performance during cutover period" if assessment == "excellent"
                    else "Some performance issues detected - continue monitoring",
                    "Redis optimization patterns successful" if self._monitoring_stats['total_optimizations_applied'] > 0
                    else "No optimizations required - good baseline performance",
                    "Alert thresholds appropriate for production" if total_alerts < 30
                    else "Review alert thresholds - possible false positives"
                ]
            }
            
        except Exception as e:
            logger.error(f"Error generating overall assessment: {e}")
            return {"error": str(e)}
    
    async def _backup_configuration(self):
        """Backup da configuração atual"""
        try:
            config_backup = {
                'timestamp': datetime.now().isoformat(),
                'monitoring_schedule': self._monitoring_schedule.to_dict() if self._monitoring_schedule else None,
                'phase_configurations': {
                    phase.value: config.to_dict()
                    for phase, config in self._phase_configurations.items()
                },
                'monitoring_statistics': self._monitoring_stats
            }
            
            backup_filename = f"monitoring_config_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(f"backups/monitoring/{backup_filename}", 'w') as f:
                json.dump(config_backup, f, indent=2)
            
            logger.info(f"Configuration backup created: {backup_filename}")
            
        except Exception as e:
            logger.error(f"Error creating configuration backup: {e}")
    
    async def _cleanup_old_logs(self):
        """Limpa logs antigos"""
        try:
            import os
            import glob
            
            # Remove logs mais antigos que 7 dias
            cutoff_time = time.time() - (7 * 24 * 3600)
            
            log_patterns = [
                "logs/monitoring/*.log",
                "reports/monitoring/*.json",
                "backups/monitoring/*.json"
            ]
            
            files_removed = 0
            for pattern in log_patterns:
                for filepath in glob.glob(pattern):
                    try:
                        if os.path.getctime(filepath) < cutoff_time:
                            os.remove(filepath)
                            files_removed += 1
                    except OSError:
                        continue
            
            if files_removed > 0:
                logger.info(f"Cleaned up {files_removed} old log files")
            
        except Exception as e:
            logger.error(f"Error cleaning up old logs: {e}")
    
    async def _check_system_connectivity(self):
        """Verifica conectividade do sistema"""
        try:
            # Verifica Redis
            from app.services.redis_connection import get_redis_client
            redis_client = await get_redis_client()
            
            if redis_client:
                await redis_client.ping()
                redis_status = "connected"
            else:
                redis_status = "disconnected"
            
            connectivity_status = {
                'timestamp': datetime.now().isoformat(),
                'redis': redis_status,
                'monitoring_components': {
                    'production_monitoring': production_monitoring.is_monitoring,
                    'redis_monitor': redis_monitor.is_monitoring,
                    'alert_system': alert_system.is_running
                }
            }
            
            # Log apenas se houver problemas
            if redis_status == "disconnected" or not all(connectivity_status['monitoring_components'].values()):
                logger.warning(f"Connectivity issues detected: {connectivity_status}")
            
        except Exception as e:
            logger.error(f"Error checking system connectivity: {e}")
    
    # Métodos públicos para consultas
    
    async def get_monitoring_status(self) -> Dict[str, Any]:
        """Obtém status do monitoramento intensivo"""
        return {
            'timestamp': datetime.now().isoformat(),
            'is_running': self.is_running,
            'monitoring_schedule': self._monitoring_schedule.to_dict() if self._monitoring_schedule else None,
            'monitoring_statistics': self._monitoring_stats,
            'active_tasks': len(self._monitoring_tasks),
            'scheduler_running': self._scheduler_thread.is_alive() if self._scheduler_thread else False
        }
    
    async def force_phase_transition(self) -> Dict[str, Any]:
        """Força transição para próxima fase (para testes)"""
        if not self._monitoring_schedule:
            return {"error": "No active monitoring schedule"}
        
        try:
            await self._transition_to_next_phase()
            return {
                "success": True,
                "new_phase": self._monitoring_schedule.current_phase.value,
                "transition_time": datetime.now().isoformat()
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def generate_immediate_report(self, report_type: str = "health") -> Dict[str, Any]:
        """Gera relatório imediato"""
        try:
            if report_type == "health":
                await self._generate_health_report()
            elif report_type == "final":
                await self._generate_final_report()
            else:
                return {"error": f"Unknown report type: {report_type}"}
            
            return {
                "success": True,
                "report_type": report_type,
                "generated_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {"error": str(e)}


# Instância global do scheduler de monitoramento intensivo
intensive_monitoring_scheduler = IntensiveMonitoringScheduler()