"""
Alert System - Advanced Alert Management for Production Monitoring
Sistema avançado de alertas com notificações automáticas e escalação

Agent-Infrastructure - FASE 4 Production Monitoring
"""

import asyncio
import json
import smtplib
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Set
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from enum import Enum
import statistics

from loguru import logger
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from app.services.redis_connection import get_redis_client


class AlertSeverity(Enum):
    """Níveis de severidade de alertas"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """Status do alerta"""
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class NotificationChannel(Enum):
    """Canais de notificação"""
    LOG = "log"
    EMAIL = "email"
    WEBHOOK = "webhook"
    SMS = "sms"
    SLACK = "slack"


@dataclass
class AlertRule:
    """Regra de alerta"""
    id: str
    name: str
    description: str
    category: str  # redis, application, system, custom
    metric_name: str
    condition: str  # >, <, ==, !=, >=, <=
    threshold: float
    severity: AlertSeverity
    evaluation_window_minutes: int = 5
    min_occurrences: int = 1
    enabled: bool = True
    notification_channels: List[NotificationChannel] = field(default_factory=list)
    suppression_duration_minutes: int = 60
    escalation_rules: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['severity'] = self.severity.value
        data['notification_channels'] = [nc.value for nc in self.notification_channels]
        return data


@dataclass
class Alert:
    """Instância de alerta"""
    id: str
    rule_id: str
    title: str
    description: str
    severity: AlertSeverity
    status: AlertStatus
    value: float
    threshold: float
    timestamp: datetime
    first_occurrence: datetime
    last_occurrence: datetime
    occurrence_count: int = 1
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    escalated: bool = False
    escalated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def age_minutes(self) -> float:
        return (datetime.now() - self.timestamp).total_seconds() / 60
    
    @property
    def duration_minutes(self) -> float:
        end_time = self.resolved_at or datetime.now()
        return (end_time - self.first_occurrence).total_seconds() / 60
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['severity'] = self.severity.value
        data['status'] = self.status.value
        data['timestamp'] = self.timestamp.isoformat()
        data['first_occurrence'] = self.first_occurrence.isoformat()
        data['last_occurrence'] = self.last_occurrence.isoformat()
        data['acknowledged_at'] = self.acknowledged_at.isoformat() if self.acknowledged_at else None
        data['resolved_at'] = self.resolved_at.isoformat() if self.resolved_at else None
        data['escalated_at'] = self.escalated_at.isoformat() if self.escalated_at else None
        data['age_minutes'] = self.age_minutes
        data['duration_minutes'] = self.duration_minutes
        return data


@dataclass
class NotificationTemplate:
    """Template de notificação"""
    channel: NotificationChannel
    subject_template: str
    body_template: str
    enabled: bool = True


class AlertSystem:
    """
    Sistema avançado de alertas para monitoramento de produção
    
    Funcionalidades:
    - Regras de alerta configuráveis
    - Múltiplos canais de notificação
    - Supressão e agrupamento de alertas
    - Escalação automática
    - Histórico completo de alertas
    - Dashboard de alertas
    - Análise de padrões
    """
    
    def __init__(self):
        self.is_running = False
        self._stop_alerting = False
        
        # Storage
        self._alert_rules: Dict[str, AlertRule] = {}
        self._active_alerts: Dict[str, Alert] = {}
        self._alert_history: deque[Alert] = deque(maxlen=10000)
        self._suppressed_alerts: Set[str] = set()
        self._metrics_buffer: deque[Dict[str, Any]] = deque(maxlen=1000)
        
        # Notification configuration
        self._notification_config = {
            'email': {
                'smtp_server': 'localhost',
                'smtp_port': 587,
                'username': '',
                'password': '',
                'from_address': 'monitoring@youtube-downloader.local',
                'to_addresses': ['admin@youtube-downloader.local']
            },
            'webhook': {
                'urls': [],
                'timeout_seconds': 10
            },
            'slack': {
                'webhook_url': '',
                'channel': '#monitoring',
                'username': 'MonitoringBot'
            }
        }
        
        # Templates de notificação
        self._notification_templates = {
            NotificationChannel.EMAIL: NotificationTemplate(
                channel=NotificationChannel.EMAIL,
                subject_template="[{severity}] {title}",
                body_template="""
Alert: {title}
Severity: {severity}
Description: {description}
Value: {value}
Threshold: {threshold}
Time: {timestamp}
Duration: {duration_minutes:.1f} minutes
Occurrences: {occurrence_count}

Metadata:
{metadata}

Dashboard: http://localhost:8000/monitoring/dashboard
                """.strip()
            ),
            NotificationChannel.LOG: NotificationTemplate(
                channel=NotificationChannel.LOG,
                subject_template="{severity} ALERT",
                body_template="{title}: {description} (value={value}, threshold={threshold})"
            )
        }
        
        # Redis client
        self._redis_client = None
        
        # Estatísticas
        self._alert_stats = {
            'total_alerts_created': 0,
            'total_alerts_resolved': 0,
            'total_notifications_sent': 0,
            'avg_resolution_time_minutes': 0.0
        }
        
        logger.info("AlertSystem initialized")
    
    async def initialize(self) -> bool:
        """Inicializa o sistema de alertas"""
        try:
            # Conecta ao Redis
            self._redis_client = await get_redis_client()
            if self._redis_client:
                # Carrega regras e alertas existentes
                await self._load_alert_rules()
                await self._load_active_alerts()
                logger.info("Redis connection established for alert system")
            else:
                logger.warning("Redis not available - alert system will be memory-only")
            
            # Registra regras padrão
            await self._register_default_rules()
            
            logger.info("Alert system initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize alert system: {e}")
            return False
    
    async def start_monitoring(self):
        """Inicia o sistema de alertas"""
        if self.is_running:
            logger.warning("Alert system already running")
            return
        
        if not await self.initialize():
            logger.error("Cannot start alert system - initialization failed")
            return
        
        self.is_running = True
        self._stop_alerting = False
        
        logger.info("Starting alert system monitoring")
        
        # Tasks principais
        evaluation_task = asyncio.create_task(self._evaluation_loop())
        maintenance_task = asyncio.create_task(self._maintenance_loop())
        escalation_task = asyncio.create_task(self._escalation_loop())
        
        try:
            await asyncio.gather(
                evaluation_task,
                maintenance_task,
                escalation_task
            )
        except Exception as e:
            logger.error(f"Error in alert system tasks: {e}")
        finally:
            self.is_running = False
            logger.info("Alert system stopped")
    
    async def stop_monitoring(self):
        """Para o sistema de alertas"""
        self._stop_alerting = True
        self.is_running = False
        logger.info("Stopping alert system...")
    
    async def _evaluation_loop(self):
        """Loop principal de avaliação de regras"""
        while not self._stop_alerting:
            try:
                await self._evaluate_all_rules()
                await asyncio.sleep(30)  # Avalia a cada 30 segundos
                
            except Exception as e:
                logger.error(f"Error in alert evaluation loop: {e}")
                await asyncio.sleep(30)
    
    async def _evaluate_all_rules(self):
        """Avalia todas as regras de alerta ativas"""
        for rule in self._alert_rules.values():
            if not rule.enabled:
                continue
            
            try:
                await self._evaluate_rule(rule)
            except Exception as e:
                logger.error(f"Error evaluating rule '{rule.id}': {e}")
    
    async def _evaluate_rule(self, rule: AlertRule):
        """Avalia uma regra específica"""
        # Obtém métricas para avaliação
        metrics = await self._get_metrics_for_evaluation(rule)
        
        if not metrics:
            return
        
        # Avalia condição
        triggered = self._evaluate_condition(rule, metrics)
        
        existing_alert_id = f"{rule.id}_{rule.metric_name}"
        existing_alert = self._active_alerts.get(existing_alert_id)
        
        if triggered:
            if existing_alert:
                # Atualiza alerta existente
                existing_alert.last_occurrence = datetime.now()
                existing_alert.occurrence_count += 1
                existing_alert.value = metrics[-1]['value']
                
                # Salva atualização
                if self._redis_client:
                    await self._save_alert_to_redis(existing_alert)
            else:
                # Cria novo alerta
                await self._create_alert(rule, metrics[-1]['value'])
        else:
            if existing_alert and existing_alert.status == AlertStatus.ACTIVE:
                # Resolve alerta automaticamente
                await self._resolve_alert(existing_alert.id, "Condition no longer met")
    
    async def _get_metrics_for_evaluation(self, rule: AlertRule) -> List[Dict[str, Any]]:
        """Obtém métricas necessárias para avaliação da regra"""
        if not self._redis_client:
            # Usa buffer em memória como fallback
            return [
                m for m in self._metrics_buffer
                if m.get('metric_name') == rule.metric_name
            ][-rule.evaluation_window_minutes:]
        
        try:
            # Busca métricas no Redis baseado na janela de avaliação
            end_time = datetime.now()
            start_time = end_time - timedelta(minutes=rule.evaluation_window_minutes)
            
            # Chaves de busca baseadas na categoria
            if rule.category == 'redis':
                pattern = f"production:monitoring:current"
                data = await self._redis_client.get(pattern)
                if data:
                    metric_data = json.loads(data)
                    return [{'metric_name': rule.metric_name, 'value': self._extract_metric_value(metric_data, rule.metric_name), 'timestamp': metric_data.get('timestamp')}]
            
            elif rule.category == 'system':
                pattern = f"metrics:system:{start_time.strftime('%Y-%m-%d-%H')}"
                metrics_data = await self._redis_client.lrange(pattern, 0, -1)
                
                results = []
                for data in metrics_data:
                    try:
                        metric_data = json.loads(data)
                        metric_time = datetime.fromisoformat(metric_data['timestamp'])
                        if start_time <= metric_time <= end_time:
                            value = self._extract_metric_value(metric_data, rule.metric_name)
                            if value is not None:
                                results.append({
                                    'metric_name': rule.metric_name,
                                    'value': value,
                                    'timestamp': metric_data['timestamp']
                                })
                    except (json.JSONDecodeError, KeyError):
                        continue
                
                return results[-rule.evaluation_window_minutes:] if results else []
            
            return []
            
        except Exception as e:
            logger.error(f"Error getting metrics for rule {rule.id}: {e}")
            return []
    
    def _extract_metric_value(self, data: Dict[str, Any], metric_name: str) -> Optional[float]:
        """Extrai valor da métrica dos dados"""
        # Mapeia nomes de métricas para paths nos dados
        metric_paths = {
            'redis_memory_used_percent': ['metrics', 'redis_memory_used_percent'],
            'redis_hit_rate': ['metrics', 'redis_hit_rate'],
            'redis_avg_latency_ms': ['metrics', 'redis_avg_latency_ms'],
            'api_error_rate': ['metrics', 'api_error_rate'],
            'api_avg_response_time_ms': ['metrics', 'api_avg_response_time_ms'],
            'cpu_usage_percent': ['cpu_percent'],
            'memory_usage_percent': ['memory_percent'],
            'disk_usage_percent': ['disk_percent'],
            # Adicione mais mapeamentos conforme necessário
        }
        
        path = metric_paths.get(metric_name, [metric_name])
        
        try:
            value = data
            for key in path:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return None
            
            return float(value) if value is not None else None
            
        except (TypeError, ValueError):
            return None
    
    def _evaluate_condition(self, rule: AlertRule, metrics: List[Dict[str, Any]]) -> bool:
        """Avalia condição da regra"""
        if not metrics:
            return False
        
        # Verifica se temos métricas suficientes
        if len(metrics) < rule.min_occurrences:
            return False
        
        # Avalia condição para cada métrica
        triggered_count = 0
        
        for metric in metrics[-rule.min_occurrences:]:
            value = metric['value']
            threshold = rule.threshold
            condition = rule.condition
            
            condition_met = False
            
            if condition == '>':
                condition_met = value > threshold
            elif condition == '<':
                condition_met = value < threshold
            elif condition == '>=':
                condition_met = value >= threshold
            elif condition == '<=':
                condition_met = value <= threshold
            elif condition == '==':
                condition_met = abs(value - threshold) < 0.001  # Floating point comparison
            elif condition == '!=':
                condition_met = abs(value - threshold) >= 0.001
            
            if condition_met:
                triggered_count += 1
        
        # Regra é triggered se todas as ocorrências mínimas foram atendidas
        return triggered_count >= rule.min_occurrences
    
    async def _create_alert(self, rule: AlertRule, current_value: float):
        """Cria um novo alerta"""
        alert_id = f"{rule.id}_{rule.metric_name}_{int(time.time())}"
        
        alert = Alert(
            id=alert_id,
            rule_id=rule.id,
            title=rule.name,
            description=f"{rule.description} (current: {current_value}, threshold: {rule.threshold})",
            severity=rule.severity,
            status=AlertStatus.ACTIVE,
            value=current_value,
            threshold=rule.threshold,
            timestamp=datetime.now(),
            first_occurrence=datetime.now(),
            last_occurrence=datetime.now(),
            metadata={
                'rule_category': rule.category,
                'metric_name': rule.metric_name,
                'condition': rule.condition,
                'evaluation_window_minutes': rule.evaluation_window_minutes
            }
        )
        
        # Verifica se deve ser suprimido
        suppression_key = f"{rule.id}_{rule.metric_name}"
        if suppression_key in self._suppressed_alerts:
            alert.status = AlertStatus.SUPPRESSED
            logger.info(f"Alert suppressed: {alert.title}")
            return
        
        # Adiciona aos alertas ativos
        self._active_alerts[alert.id] = alert
        self._alert_history.append(alert)
        
        # Atualiza estatísticas
        self._alert_stats['total_alerts_created'] += 1
        
        # Salva no Redis
        if self._redis_client:
            await self._save_alert_to_redis(alert)
        
        # Envia notificações
        await self._send_alert_notifications(alert, rule)
        
        logger.warning(f"ALERT CREATED: {alert.title} (severity: {alert.severity.value})")
    
    async def _send_alert_notifications(self, alert: Alert, rule: AlertRule):
        """Envia notificações do alerta pelos canais configurados"""
        for channel in rule.notification_channels:
            try:
                await self._send_notification(alert, channel)
                self._alert_stats['total_notifications_sent'] += 1
            except Exception as e:
                logger.error(f"Error sending notification via {channel.value}: {e}")
    
    async def _send_notification(self, alert: Alert, channel: NotificationChannel):
        """Envia notificação por um canal específico"""
        template = self._notification_templates.get(channel)
        if not template or not template.enabled:
            return
        
        # Formata mensagem
        context = alert.to_dict()
        subject = template.subject_template.format(**context)
        body = template.body_template.format(**context)
        
        if channel == NotificationChannel.LOG:
            logger.warning(f"{subject}: {body}")
        
        elif channel == NotificationChannel.EMAIL:
            await self._send_email_notification(subject, body, alert.severity)
        
        elif channel == NotificationChannel.WEBHOOK:
            await self._send_webhook_notification(alert, subject, body)
        
        elif channel == NotificationChannel.SLACK:
            await self._send_slack_notification(alert, subject, body)
    
    async def _send_email_notification(self, subject: str, body: str, severity: AlertSeverity):
        """Envia notificação por email"""
        try:
            config = self._notification_config['email']
            
            msg = MIMEMultipart()
            msg['From'] = config['from_address']
            msg['To'] = ', '.join(config['to_addresses'])
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'plain'))
            
            # Simula envio de email (em produção, usar SMTP real)
            logger.info(f"EMAIL NOTIFICATION: {subject}")
            
            # Código de envio SMTP comentado para evitar erros em ambiente de desenvolvimento
            # server = smtplib.SMTP(config['smtp_server'], config['smtp_port'])
            # server.starttls()
            # server.login(config['username'], config['password'])
            # server.send_message(msg)
            # server.quit()
            
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")
    
    async def _send_webhook_notification(self, alert: Alert, subject: str, body: str):
        """Envia notificação via webhook"""
        try:
            import aiohttp
            
            config = self._notification_config['webhook']
            
            payload = {
                'alert_id': alert.id,
                'title': subject,
                'description': body,
                'severity': alert.severity.value,
                'status': alert.status.value,
                'timestamp': alert.timestamp.isoformat(),
                'value': alert.value,
                'threshold': alert.threshold
            }
            
            for url in config['urls']:
                if url:  # Só envia se URL está configurada
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            url,
                            json=payload,
                            timeout=aiohttp.ClientTimeout(total=config['timeout_seconds'])
                        ) as response:
                            if response.status == 200:
                                logger.info(f"Webhook notification sent to {url}")
                            else:
                                logger.warning(f"Webhook notification failed: {response.status}")
        
        except Exception as e:
            logger.error(f"Error sending webhook notification: {e}")
    
    async def _send_slack_notification(self, alert: Alert, subject: str, body: str):
        """Envia notificação para Slack"""
        try:
            import aiohttp
            
            config = self._notification_config['slack']
            
            if not config['webhook_url']:
                return
            
            # Mapeia severidade para cores
            color_map = {
                AlertSeverity.LOW: '#36a64f',      # verde
                AlertSeverity.MEDIUM: '#ff9900',   # laranja
                AlertSeverity.HIGH: '#ff4444',    # vermelho
                AlertSeverity.CRITICAL: '#990000' # vermelho escuro
            }
            
            payload = {
                'channel': config['channel'],
                'username': config['username'],
                'attachments': [{
                    'color': color_map.get(alert.severity, '#ff9900'),
                    'title': subject,
                    'text': body,
                    'fields': [
                        {'title': 'Value', 'value': str(alert.value), 'short': True},
                        {'title': 'Threshold', 'value': str(alert.threshold), 'short': True},
                        {'title': 'Occurrences', 'value': str(alert.occurrence_count), 'short': True}
                    ],
                    'timestamp': int(alert.timestamp.timestamp())
                }]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(config['webhook_url'], json=payload) as response:
                    if response.status == 200:
                        logger.info("Slack notification sent")
                    else:
                        logger.warning(f"Slack notification failed: {response.status}")
        
        except Exception as e:
            logger.error(f"Error sending Slack notification: {e}")
    
    async def _resolve_alert(self, alert_id: str, reason: str = "Manually resolved"):
        """Resolve um alerta"""
        alert = self._active_alerts.get(alert_id)
        if not alert:
            return
        
        alert.status = AlertStatus.RESOLVED
        alert.resolved_at = datetime.now()
        alert.metadata['resolution_reason'] = reason
        
        # Remove dos alertas ativos
        del self._active_alerts[alert_id]
        
        # Atualiza estatísticas
        self._alert_stats['total_alerts_resolved'] += 1
        
        # Recalcula tempo médio de resolução
        resolved_alerts = [a for a in self._alert_history if a.resolved_at]
        if resolved_alerts:
            avg_resolution = statistics.mean([a.duration_minutes for a in resolved_alerts])
            self._alert_stats['avg_resolution_time_minutes'] = round(avg_resolution, 1)
        
        # Salva no Redis
        if self._redis_client:
            await self._save_alert_to_redis(alert)
            await self._remove_active_alert_from_redis(alert_id)
        
        logger.info(f"ALERT RESOLVED: {alert.title} (reason: {reason})")
    
    async def _maintenance_loop(self):
        """Loop de manutenção do sistema de alertas"""
        while not self._stop_alerting:
            try:
                await asyncio.sleep(300)  # A cada 5 minutos
                await self._perform_maintenance()
                
            except Exception as e:
                logger.error(f"Error in alert maintenance loop: {e}")
    
    async def _perform_maintenance(self):
        """Executa tarefas de manutenção"""
        # Auto-resolve alertas antigos
        await self._auto_resolve_stale_alerts()
        
        # Limpa supressões expiradas
        await self._cleanup_expired_suppressions()
        
        # Limpa histórico antigo
        await self._cleanup_old_history()
    
    async def _auto_resolve_stale_alerts(self):
        """Resolve automaticamente alertas muito antigos"""
        cutoff_time = datetime.now() - timedelta(hours=24)  # 24 horas
        
        stale_alerts = [
            alert for alert in self._active_alerts.values()
            if alert.timestamp < cutoff_time and alert.status == AlertStatus.ACTIVE
        ]
        
        for alert in stale_alerts:
            await self._resolve_alert(alert.id, "Auto-resolved (stale alert)")
    
    async def _cleanup_expired_suppressions(self):
        """Limpa supressões expiradas"""
        # Em uma implementação real, você manteria timestamps de supressão
        # Por ora, limpa todas as supressões a cada hora
        if len(self._suppressed_alerts) > 0:
            logger.info(f"Clearing {len(self._suppressed_alerts)} alert suppressions")
            self._suppressed_alerts.clear()
    
    async def _cleanup_old_history(self):
        """Limpa histórico antigo de alertas"""
        # O deque já limita automaticamente, mas podemos fazer limpeza adicional
        cutoff_time = datetime.now() - timedelta(days=30)
        
        # Remove alertas muito antigos do histórico
        old_count = len(self._alert_history)
        self._alert_history = deque(
            [alert for alert in self._alert_history if alert.timestamp > cutoff_time],
            maxlen=10000
        )
        
        if len(self._alert_history) < old_count:
            logger.info(f"Cleaned up {old_count - len(self._alert_history)} old alerts from history")
    
    async def _escalation_loop(self):
        """Loop de escalação de alertas"""
        while not self._stop_alerting:
            try:
                await asyncio.sleep(60)  # A cada minuto
                await self._check_escalations()
                
            except Exception as e:
                logger.error(f"Error in escalation loop: {e}")
    
    async def _check_escalations(self):
        """Verifica alertas que precisam ser escalados"""
        for alert in self._active_alerts.values():
            if alert.escalated or alert.status != AlertStatus.ACTIVE:
                continue
            
            rule = self._alert_rules.get(alert.rule_id)
            if not rule or not rule.escalation_rules:
                continue
            
            # Verifica critérios de escalação
            escalation_time = rule.escalation_rules.get('escalation_time_minutes', 60)
            
            if alert.age_minutes >= escalation_time:
                await self._escalate_alert(alert, rule)
    
    async def _escalate_alert(self, alert: Alert, rule: AlertRule):
        """Escala um alerta"""
        alert.escalated = True
        alert.escalated_at = datetime.now()
        
        # Aumenta severidade se configurado
        if rule.escalation_rules.get('increase_severity', False):
            if alert.severity == AlertSeverity.LOW:
                alert.severity = AlertSeverity.MEDIUM
            elif alert.severity == AlertSeverity.MEDIUM:
                alert.severity = AlertSeverity.HIGH
            elif alert.severity == AlertSeverity.HIGH:
                alert.severity = AlertSeverity.CRITICAL
        
        # Envia notificações de escalação
        escalation_channels = rule.escalation_rules.get('notification_channels', [])
        for channel_name in escalation_channels:
            try:
                channel = NotificationChannel(channel_name)
                await self._send_notification(alert, channel)
            except ValueError:
                logger.warning(f"Unknown escalation channel: {channel_name}")
        
        # Salva no Redis
        if self._redis_client:
            await self._save_alert_to_redis(alert)
        
        logger.warning(f"ALERT ESCALATED: {alert.title} (age: {alert.age_minutes:.1f} minutes)")
    
    async def _register_default_rules(self):
        """Registra regras padrão de alerta"""
        default_rules = [
            # Redis alerts
            AlertRule(
                id="redis_memory_critical",
                name="Redis Memory Critical",
                description="Redis memory usage is critically high",
                category="redis",
                metric_name="redis_memory_used_percent",
                condition=">",
                threshold=0.95,
                severity=AlertSeverity.CRITICAL,
                evaluation_window_minutes=5,
                min_occurrences=2,
                notification_channels=[NotificationChannel.LOG, NotificationChannel.EMAIL],
                escalation_rules={
                    'escalation_time_minutes': 30,
                    'increase_severity': False,
                    'notification_channels': ['slack']
                }
            ),
            AlertRule(
                id="redis_memory_warning",
                name="Redis Memory Warning",
                description="Redis memory usage is high",
                category="redis",
                metric_name="redis_memory_used_percent",
                condition=">",
                threshold=0.85,
                severity=AlertSeverity.HIGH,
                evaluation_window_minutes=5,
                min_occurrences=3,
                notification_channels=[NotificationChannel.LOG]
            ),
            AlertRule(
                id="redis_hit_rate_low",
                name="Redis Hit Rate Low",
                description="Redis hit rate is below acceptable threshold",
                category="redis",
                metric_name="redis_hit_rate",
                condition="<",
                threshold=0.85,
                severity=AlertSeverity.MEDIUM,
                evaluation_window_minutes=10,
                min_occurrences=5,
                notification_channels=[NotificationChannel.LOG]
            ),
            AlertRule(
                id="redis_latency_high",
                name="Redis Latency High",
                description="Redis response latency is high",
                category="redis",
                metric_name="redis_avg_latency_ms",
                condition=">",
                threshold=100.0,
                severity=AlertSeverity.HIGH,
                evaluation_window_minutes=5,
                min_occurrences=3,
                notification_channels=[NotificationChannel.LOG]
            ),
            
            # Application alerts
            AlertRule(
                id="api_error_rate_high",
                name="API Error Rate High",
                description="API error rate is elevated",
                category="application",
                metric_name="api_error_rate",
                condition=">",
                threshold=0.05,  # 5%
                severity=AlertSeverity.HIGH,
                evaluation_window_minutes=5,
                min_occurrences=3,
                notification_channels=[NotificationChannel.LOG, NotificationChannel.EMAIL]
            ),
            AlertRule(
                id="api_response_time_slow",
                name="API Response Time Slow",
                description="API response time is slow",
                category="application",
                metric_name="api_avg_response_time_ms",
                condition=">",
                threshold=2000.0,  # 2 seconds
                severity=AlertSeverity.MEDIUM,
                evaluation_window_minutes=5,
                min_occurrences=5,
                notification_channels=[NotificationChannel.LOG]
            ),
            
            # System alerts
            AlertRule(
                id="cpu_usage_high",
                name="CPU Usage High",
                description="System CPU usage is high",
                category="system",
                metric_name="cpu_usage_percent",
                condition=">",
                threshold=90.0,
                severity=AlertSeverity.HIGH,
                evaluation_window_minutes=5,
                min_occurrences=5,
                notification_channels=[NotificationChannel.LOG]
            ),
            AlertRule(
                id="memory_usage_critical",
                name="Memory Usage Critical",
                description="System memory usage is critically high",
                category="system",
                metric_name="memory_usage_percent",
                condition=">",
                threshold=95.0,
                severity=AlertSeverity.CRITICAL,
                evaluation_window_minutes=3,
                min_occurrences=2,
                notification_channels=[NotificationChannel.LOG, NotificationChannel.EMAIL]
            ),
            AlertRule(
                id="disk_usage_high",
                name="Disk Usage High",
                description="System disk usage is high",
                category="system",
                metric_name="disk_usage_percent",
                condition=">",
                threshold=90.0,
                severity=AlertSeverity.HIGH,
                evaluation_window_minutes=10,
                min_occurrences=3,
                notification_channels=[NotificationChannel.LOG]
            )
        ]
        
        for rule in default_rules:
            await self.add_alert_rule(rule)
    
    async def add_alert_rule(self, rule: AlertRule):
        """Adiciona uma regra de alerta"""
        self._alert_rules[rule.id] = rule
        
        # Salva no Redis
        if self._redis_client:
            await self._save_alert_rule_to_redis(rule)
        
        logger.info(f"Alert rule added: {rule.name}")
    
    async def remove_alert_rule(self, rule_id: str):
        """Remove uma regra de alerta"""
        if rule_id in self._alert_rules:
            del self._alert_rules[rule_id]
            
            # Remove do Redis
            if self._redis_client:
                await self._remove_alert_rule_from_redis(rule_id)
            
            logger.info(f"Alert rule removed: {rule_id}")
    
    async def acknowledge_alert(self, alert_id: str, acknowledged_by: str):
        """Reconhece um alerta"""
        alert = self._active_alerts.get(alert_id)
        if not alert:
            return False
        
        alert.status = AlertStatus.ACKNOWLEDGED
        alert.acknowledged_by = acknowledged_by
        alert.acknowledged_at = datetime.now()
        
        # Salva no Redis
        if self._redis_client:
            await self._save_alert_to_redis(alert)
        
        logger.info(f"Alert acknowledged by {acknowledged_by}: {alert.title}")
        return True
    
    async def suppress_alert_rule(self, rule_id: str, metric_name: str, duration_minutes: int = 60):
        """Suprime alertas de uma regra por um período"""
        suppression_key = f"{rule_id}_{metric_name}"
        self._suppressed_alerts.add(suppression_key)
        
        # Em produção, você salvaria isso com timestamp para expiração automática
        logger.info(f"Alert rule suppressed: {rule_id}/{metric_name} for {duration_minutes} minutes")
    
    async def record_metric(self, metric_name: str, value: float, category: str = "custom", metadata: Dict[str, Any] = None):
        """Registra uma métrica personalizada para avaliação"""
        metric_data = {
            'metric_name': metric_name,
            'value': value,
            'category': category,
            'timestamp': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        self._metrics_buffer.append(metric_data)
        
        # Salva no Redis se disponível
        if self._redis_client:
            key = f"custom_metrics:{category}:{datetime.now().strftime('%Y-%m-%d-%H')}"
            await self._redis_client.lpush(key, json.dumps(metric_data))
            await self._redis_client.ltrim(key, 0, 999)
            await self._redis_client.expire(key, 24 * 3600)
    
    # Métodos de persistência Redis
    
    async def _save_alert_rule_to_redis(self, rule: AlertRule):
        """Salva regra de alerta no Redis"""
        try:
            key = f"alert_rules:{rule.id}"
            await self._redis_client.setex(key, 30 * 24 * 3600, json.dumps(rule.to_dict()))
        except Exception as e:
            logger.error(f"Error saving alert rule to Redis: {e}")
    
    async def _remove_alert_rule_from_redis(self, rule_id: str):
        """Remove regra de alerta do Redis"""
        try:
            key = f"alert_rules:{rule_id}"
            await self._redis_client.delete(key)
        except Exception as e:
            logger.error(f"Error removing alert rule from Redis: {e}")
    
    async def _save_alert_to_redis(self, alert: Alert):
        """Salva alerta no Redis"""
        try:
            # Alerta ativo
            if alert.status == AlertStatus.ACTIVE:
                key = f"active_alerts:{alert.id}"
                await self._redis_client.setex(key, 24 * 3600, json.dumps(alert.to_dict()))
            
            # Histórico
            history_key = f"alert_history:{alert.timestamp.strftime('%Y-%m-%d')}"
            await self._redis_client.lpush(history_key, json.dumps(alert.to_dict()))
            await self._redis_client.ltrim(history_key, 0, 999)
            await self._redis_client.expire(history_key, 30 * 24 * 3600)
            
        except Exception as e:
            logger.error(f"Error saving alert to Redis: {e}")
    
    async def _remove_active_alert_from_redis(self, alert_id: str):
        """Remove alerta ativo do Redis"""
        try:
            key = f"active_alerts:{alert_id}"
            await self._redis_client.delete(key)
        except Exception as e:
            logger.error(f"Error removing active alert from Redis: {e}")
    
    async def _load_alert_rules(self):
        """Carrega regras de alerta do Redis"""
        try:
            keys = await self._redis_client.keys("alert_rules:*")
            for key in keys:
                data = await self._redis_client.get(key)
                if data:
                    rule_dict = json.loads(data)
                    rule = AlertRule(**rule_dict)
                    rule.severity = AlertSeverity(rule_dict['severity'])
                    rule.notification_channels = [NotificationChannel(nc) for nc in rule_dict['notification_channels']]
                    self._alert_rules[rule.id] = rule
            
            logger.info(f"Loaded {len(self._alert_rules)} alert rules from Redis")
            
        except Exception as e:
            logger.error(f"Error loading alert rules from Redis: {e}")
    
    async def _load_active_alerts(self):
        """Carrega alertas ativos do Redis"""
        try:
            keys = await self._redis_client.keys("active_alerts:*")
            for key in keys:
                data = await self._redis_client.get(key)
                if data:
                    alert_dict = json.loads(data)
                    
                    # Reconstroi objetos datetime
                    alert_dict['timestamp'] = datetime.fromisoformat(alert_dict['timestamp'])
                    alert_dict['first_occurrence'] = datetime.fromisoformat(alert_dict['first_occurrence'])
                    alert_dict['last_occurrence'] = datetime.fromisoformat(alert_dict['last_occurrence'])
                    if alert_dict['acknowledged_at']:
                        alert_dict['acknowledged_at'] = datetime.fromisoformat(alert_dict['acknowledged_at'])
                    if alert_dict['resolved_at']:
                        alert_dict['resolved_at'] = datetime.fromisoformat(alert_dict['resolved_at'])
                    if alert_dict['escalated_at']:
                        alert_dict['escalated_at'] = datetime.fromisoformat(alert_dict['escalated_at'])
                    
                    alert = Alert(**alert_dict)
                    alert.severity = AlertSeverity(alert_dict['severity'])
                    alert.status = AlertStatus(alert_dict['status'])
                    
                    self._active_alerts[alert.id] = alert
            
            logger.info(f"Loaded {len(self._active_alerts)} active alerts from Redis")
            
        except Exception as e:
            logger.error(f"Error loading active alerts from Redis: {e}")
    
    # Métodos públicos para consultas
    
    async def get_alert_dashboard(self) -> Dict[str, Any]:
        """Obtém dados do dashboard de alertas"""
        active_alerts = list(self._active_alerts.values())
        
        # Estatísticas por severidade
        severity_stats = defaultdict(int)
        for alert in active_alerts:
            severity_stats[alert.severity.value] += 1
        
        # Alertas recentes (últimas 24h)
        recent_cutoff = datetime.now() - timedelta(hours=24)
        recent_alerts = [a for a in self._alert_history if a.timestamp > recent_cutoff]
        
        # Top regras por frequência
        rule_frequency = defaultdict(int)
        for alert in recent_alerts:
            rule_frequency[alert.rule_id] += 1
        
        top_rules = sorted(rule_frequency.items(), key=lambda x: x[1], reverse=True)[:10]
        
        return {
            "timestamp": datetime.now().isoformat(),
            "active_alerts_count": len(active_alerts),
            "active_alerts": [alert.to_dict() for alert in active_alerts[:20]],  # Últimos 20
            "severity_breakdown": dict(severity_stats),
            "recent_alerts_24h": len(recent_alerts),
            "top_triggered_rules": [{"rule_id": rule_id, "count": count} for rule_id, count in top_rules],
            "alert_statistics": self._alert_stats,
            "system_status": "running" if self.is_running else "stopped"
        }
    
    async def get_alert_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Obtém histórico de alertas"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        history_alerts = [
            alert.to_dict() for alert in self._alert_history
            if alert.timestamp > cutoff_time
        ]
        
        return sorted(history_alerts, key=lambda x: x['timestamp'], reverse=True)


# Instância global do sistema de alertas
alert_system = AlertSystem()