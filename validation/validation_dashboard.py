"""
Validation Dashboard - Agent-QualityAssurance FASE 4
Dashboard em tempo real para validação contínua por 96 horas
"""

import asyncio
import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
import logging
from dataclasses import asdict
import redis.asyncio as redis
from collections import deque, defaultdict

class ValidationDashboard:
    """Dashboard em tempo real para validação contínua"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.redis_client = None
        self.is_running = False
        
        # Dashboard data
        self.current_status = {
            'overall_status': 'initializing',
            'validation_progress': 0.0,
            'active_validations': 0,
            'last_update': None
        }
        
        # Real-time metrics
        self.metrics_history = {
            'data_integrity': deque(maxlen=100),
            'performance': deque(maxlen=100),
            'user_experience': deque(maxlen=100),
            'error_rates': deque(maxlen=100)
        }
        
        # Alert queues
        self.active_alerts = {
            'critical': deque(maxlen=50),
            'warning': deque(maxlen=100),
            'info': deque(maxlen=200)
        }
        
        # Dashboard configuration
        self.dashboard_config = {
            'update_interval': 30,  # 30 seconds
            'chart_history_points': 50,
            'alert_retention_hours': 24,
            'auto_refresh': True
        }
        
        # Create dashboard directory
        self.dashboard_dir = Path("validation/dashboard")
        self.dashboard_dir.mkdir(parents=True, exist_ok=True)
        
        # Dashboard files
        self.dashboard_html_file = self.dashboard_dir / "validation_dashboard.html"
        self.dashboard_data_file = self.dashboard_dir / "dashboard_data.json"
        self.dashboard_css_file = self.dashboard_dir / "dashboard.css"
        self.dashboard_js_file = self.dashboard_dir / "dashboard.js"
        
        # Generate dashboard files
        self._generate_dashboard_files()
    
    async def start(self):
        """Iniciar dashboard"""
        try:
            # Initialize Redis connection
            self.redis_client = redis.Redis(
                host='localhost',
                port=int(os.getenv('REDIS_PORT', 6379)),
                decode_responses=True
            )
            await self.redis_client.ping()
            
            self.is_running = True
            
            # Start dashboard update loop
            asyncio.create_task(self._update_loop())
            
            self.logger.info("Validation dashboard started")
            
        except Exception as e:
            self.logger.error(f"Failed to start validation dashboard: {e}")
            raise
    
    async def stop(self):
        """Parar dashboard"""
        self.is_running = False
        
        if self.redis_client:
            await self.redis_client.close()
        
        self.logger.info("Validation dashboard stopped")
    
    async def update_validation_result(self, result):
        """Atualizar com resultado de validação"""
        try:
            current_time = datetime.now()
            
            # Update metrics history
            if hasattr(result, 'validation_type') and hasattr(result, 'metrics'):
                validation_type = result.validation_type
                
                if validation_type in self.metrics_history:
                    # Extract relevant score from metrics
                    score = self._extract_score_from_metrics(result.metrics, validation_type)
                    
                    self.metrics_history[validation_type].append({
                        'timestamp': current_time.isoformat(),
                        'score': score,
                        'status': result.status
                    })
            
            # Update current status
            self.current_status['last_update'] = current_time.isoformat()
            self.current_status['active_validations'] += 1
            
            # Handle alerts
            if hasattr(result, 'status') and result.status in ['warning', 'critical']:
                await self._add_alert(result)
            
            # Update dashboard data
            await self._update_dashboard_data()
            
        except Exception as e:
            self.logger.error(f"Failed to update validation result in dashboard: {e}")
    
    async def update_health_metrics(self, health_metrics: Dict[str, Any]):
        """Atualizar métricas de saúde do sistema"""
        try:
            current_time = datetime.now()
            
            # Store health metrics in Redis
            await self.redis_client.hset(
                'dashboard:health_metrics',
                mapping={
                    'timestamp': current_time.isoformat(),
                    'validation_uptime': health_metrics.get('validation_uptime', 0),
                    'memory_usage': health_metrics.get('memory_usage', 0),
                    'validation_success_rate': health_metrics.get('validation_success_rate', 0),
                    'average_validation_duration': health_metrics.get('average_validation_duration', 0)
                }
            )
            
            # Update dashboard
            await self._update_dashboard_data()
            
        except Exception as e:
            self.logger.error(f"Failed to update health metrics: {e}")
    
    async def _update_loop(self):
        """Loop principal de atualização do dashboard"""
        while self.is_running:
            try:
                await self._refresh_dashboard_data()
                await self._update_progress()
                await self._cleanup_old_alerts()
                
                await asyncio.sleep(self.dashboard_config['update_interval'])
                
            except Exception as e:
                self.logger.error(f"Dashboard update loop error: {e}")
                await asyncio.sleep(5)  # Wait before retrying
    
    async def _refresh_dashboard_data(self):
        """Atualizar dados do dashboard"""
        try:
            # Get latest validation results from Redis
            latest_results = await self._get_latest_validation_results()
            
            # Get system health metrics
            health_metrics = await self.redis_client.hgetall('dashboard:health_metrics')
            
            # Update dashboard data structure
            dashboard_data = {
                'timestamp': datetime.now().isoformat(),
                'current_status': self.current_status,
                'health_metrics': health_metrics,
                'validation_metrics': self._prepare_metrics_for_dashboard(),
                'active_alerts': self._prepare_alerts_for_dashboard(),
                'charts_data': self._prepare_charts_data(),
                'system_info': await self._get_system_info(),
                'validation_summary': self._get_validation_summary(latest_results)
            }
            
            # Save dashboard data
            with open(self.dashboard_data_file, 'w') as f:
                json.dump(dashboard_data, f, indent=2)
            
        except Exception as e:
            self.logger.error(f"Failed to refresh dashboard data: {e}")
    
    async def _get_latest_validation_results(self) -> List[Dict]:
        """Obter últimos resultados de validação"""
        results = []
        
        validation_types = ['data_integrity', 'performance', 'user_experience', 'error_rates']
        
        for validation_type in validation_types:
            try:
                latest = await self.redis_client.lrange(f'validation:results:{validation_type}', 0, 4)
                for result_json in latest:
                    result = json.loads(result_json)
                    results.append(result)
            except Exception as e:
                self.logger.warning(f"Failed to get results for {validation_type}: {e}")
        
        return results
    
    def _prepare_metrics_for_dashboard(self) -> Dict[str, Any]:
        """Preparar métricas para dashboard"""
        metrics = {}
        
        for validation_type, history in self.metrics_history.items():
            if history:
                latest = history[-1]
                metrics[validation_type] = {
                    'current_score': latest['score'],
                    'status': latest['status'],
                    'last_update': latest['timestamp'],
                    'trend': self._calculate_trend(history),
                    'history_count': len(history)
                }
            else:
                metrics[validation_type] = {
                    'current_score': 0,
                    'status': 'no_data',
                    'last_update': None,
                    'trend': 'stable',
                    'history_count': 0
                }
        
        return metrics
    
    def _prepare_alerts_for_dashboard(self) -> Dict[str, List]:
        """Preparar alertas para dashboard"""
        alerts = {}
        
        for alert_level, alert_queue in self.active_alerts.items():
            alerts[alert_level] = [
                {
                    'timestamp': alert['timestamp'],
                    'validation_type': alert['validation_type'],
                    'message': alert['message'],
                    'severity': alert_level
                }
                for alert in list(alert_queue)[-10:]  # Last 10 alerts
            ]
        
        return alerts
    
    def _prepare_charts_data(self) -> Dict[str, Any]:
        """Preparar dados para gráficos"""
        charts_data = {}
        
        for validation_type, history in self.metrics_history.items():
            if history:
                # Prepare time series data
                timestamps = [point['timestamp'] for point in history]
                scores = [point['score'] for point in history]
                statuses = [point['status'] for point in history]
                
                charts_data[validation_type] = {
                    'timestamps': timestamps[-self.dashboard_config['chart_history_points']:],
                    'scores': scores[-self.dashboard_config['chart_history_points']:],
                    'statuses': statuses[-self.dashboard_config['chart_history_points']:],
                    'min_score': min(scores) if scores else 0,
                    'max_score': max(scores) if scores else 100,
                    'avg_score': sum(scores) / len(scores) if scores else 0
                }
            else:
                charts_data[validation_type] = {
                    'timestamps': [],
                    'scores': [],
                    'statuses': [],
                    'min_score': 0,
                    'max_score': 100,
                    'avg_score': 0
                }
        
        return charts_data
    
    async def _get_system_info(self) -> Dict[str, Any]:
        """Obter informações do sistema"""
        try:
            # Get Redis info
            redis_info = await self.redis_client.info()
            
            # System information
            system_info = {
                'redis_version': redis_info.get('redis_version', 'unknown'),
                'redis_memory_usage': redis_info.get('used_memory_human', '0B'),
                'redis_connected_clients': redis_info.get('connected_clients', 0),
                'redis_total_commands': redis_info.get('total_commands_processed', 0),
                'validation_start_time': await self.redis_client.get('validation:start_time'),
                'validation_duration': await self._calculate_validation_duration(),
                'total_validations': await self.redis_client.get('validation:total_count') or 0
            }
            
            return system_info
            
        except Exception as e:
            self.logger.error(f"Failed to get system info: {e}")
            return {}
    
    def _get_validation_summary(self, latest_results: List[Dict]) -> Dict[str, Any]:
        """Obter resumo das validações"""
        if not latest_results:
            return {
                'total_validations': 0,
                'passed': 0,
                'warnings': 0,
                'critical': 0,
                'success_rate': 0.0
            }
        
        status_counts = {'passed': 0, 'warning': 0, 'critical': 0}
        
        for result in latest_results:
            status = result.get('status', 'unknown')
            if status in status_counts:
                status_counts[status] += 1
        
        total = sum(status_counts.values())
        success_rate = (status_counts['passed'] / total * 100) if total > 0 else 0
        
        return {
            'total_validations': total,
            'passed': status_counts['passed'],
            'warnings': status_counts['warning'],
            'critical': status_counts['critical'],
            'success_rate': success_rate
        }
    
    async def _add_alert(self, result):
        """Adicionar alerta"""
        try:
            alert = {
                'timestamp': datetime.now().isoformat(),
                'validation_type': result.validation_type,
                'message': f"{result.validation_type} validation {result.status}",
                'details': result.issues if hasattr(result, 'issues') else [],
                'metrics': result.metrics if hasattr(result, 'metrics') else {}
            }
            
            # Add to appropriate alert queue
            if result.status == 'critical':
                self.active_alerts['critical'].append(alert)
            elif result.status == 'warning':
                self.active_alerts['warning'].append(alert)
            else:
                self.active_alerts['info'].append(alert)
            
            # Store in Redis for persistence
            await self.redis_client.lpush(
                f'dashboard:alerts:{result.status}',
                json.dumps(alert)
            )
            
            # Trim old alerts
            await self.redis_client.ltrim(f'dashboard:alerts:{result.status}', 0, 100)
            
        except Exception as e:
            self.logger.error(f"Failed to add alert: {e}")
    
    async def _update_progress(self):
        """Atualizar progresso da validação"""
        try:
            start_time_str = await self.redis_client.get('validation:start_time')
            if start_time_str:
                start_time = datetime.fromisoformat(start_time_str)
                elapsed = (datetime.now() - start_time).total_seconds()
                total_duration = 96 * 3600  # 96 hours
                
                progress = min(100.0, (elapsed / total_duration) * 100)
                self.current_status['validation_progress'] = progress
                
                # Update overall status based on progress and results
                if progress >= 100:
                    self.current_status['overall_status'] = 'completed'
                elif progress > 0:
                    self.current_status['overall_status'] = 'running'
                else:
                    self.current_status['overall_status'] = 'initializing'
            
        except Exception as e:
            self.logger.error(f"Failed to update progress: {e}")
    
    async def _cleanup_old_alerts(self):
        """Limpar alertas antigos"""
        try:
            cutoff_time = datetime.now() - timedelta(hours=self.dashboard_config['alert_retention_hours'])
            
            for alert_level, alert_queue in self.active_alerts.items():
                # Remove old alerts
                while alert_queue and datetime.fromisoformat(alert_queue[0]['timestamp']) < cutoff_time:
                    alert_queue.popleft()
            
        except Exception as e:
            self.logger.error(f"Failed to cleanup old alerts: {e}")
    
    async def _calculate_validation_duration(self) -> str:
        """Calcular duração da validação"""
        try:
            start_time_str = await self.redis_client.get('validation:start_time')
            if start_time_str:
                start_time = datetime.fromisoformat(start_time_str)
                duration = datetime.now() - start_time
                
                hours = int(duration.total_seconds() // 3600)
                minutes = int((duration.total_seconds() % 3600) // 60)
                
                return f"{hours}h {minutes}m"
            
            return "0h 0m"
            
        except Exception as e:
            return "unknown"
    
    def _extract_score_from_metrics(self, metrics: Dict, validation_type: str) -> float:
        """Extrair score das métricas"""
        if not metrics:
            return 0.0
        
        # Try to find type-specific score
        score_key = f"overall_{validation_type}_score"
        if score_key in metrics:
            return metrics[score_key]
        
        # Try generic score keys
        generic_keys = ['overall_score', 'success_rate', 'score']
        for key in generic_keys:
            if key in metrics:
                return metrics[key]
        
        # Calculate from available metrics
        numeric_values = [v for v in metrics.values() if isinstance(v, (int, float)) and 0 <= v <= 100]
        if numeric_values:
            return sum(numeric_values) / len(numeric_values)
        
        return 0.0
    
    def _calculate_trend(self, history: deque) -> str:
        """Calcular tendência dos dados"""
        if len(history) < 2:
            return 'stable'
        
        recent_scores = [point['score'] for point in list(history)[-5:]]
        if len(recent_scores) < 2:
            return 'stable'
        
        # Simple trend calculation
        first_half = recent_scores[:len(recent_scores)//2]
        second_half = recent_scores[len(recent_scores)//2:]
        
        if not first_half or not second_half:
            return 'stable'
        
        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)
        
        diff = second_avg - first_avg
        
        if diff > 2:
            return 'improving'
        elif diff < -2:
            return 'declining'
        else:
            return 'stable'
    
    async def _update_dashboard_data(self):
        """Atualizar dados do dashboard"""
        try:
            await self._refresh_dashboard_data()
        except Exception as e:
            self.logger.error(f"Failed to update dashboard data: {e}")
    
    def _generate_dashboard_files(self):
        """Gerar arquivos do dashboard"""
        # Generate HTML file
        self._generate_dashboard_html()
        
        # Generate CSS file
        self._generate_dashboard_css()
        
        # Generate JavaScript file
        self._generate_dashboard_js()
    
    def _generate_dashboard_html(self):
        """Gerar arquivo HTML do dashboard"""
        html_content = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>96-Hour Validation Dashboard</title>
    <link rel="stylesheet" href="dashboard.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
</head>
<body>
    <div class="dashboard-container">
        <header class="dashboard-header">
            <h1>🔍 96-Hour Continuous Validation Dashboard</h1>
            <div class="status-indicator" id="overall-status">
                <span class="status-dot" id="status-dot"></span>
                <span class="status-text" id="status-text">Initializing...</span>
            </div>
        </header>

        <div class="dashboard-grid">
            <!-- Progress Section -->
            <div class="dashboard-card progress-card">
                <h2>Validation Progress</h2>
                <div class="progress-container">
                    <div class="progress-bar">
                        <div class="progress-fill" id="progress-fill"></div>
                    </div>
                    <div class="progress-text" id="progress-text">0% (0h 0m)</div>
                </div>
            </div>

            <!-- Metrics Overview -->
            <div class="dashboard-card metrics-card">
                <h2>Current Metrics</h2>
                <div class="metrics-grid">
                    <div class="metric-item" id="data-integrity-metric">
                        <h3>Data Integrity</h3>
                        <div class="metric-value">--</div>
                        <div class="metric-trend">--</div>
                    </div>
                    <div class="metric-item" id="performance-metric">
                        <h3>Performance</h3>
                        <div class="metric-value">--</div>
                        <div class="metric-trend">--</div>
                    </div>
                    <div class="metric-item" id="user-experience-metric">
                        <h3>User Experience</h3>
                        <div class="metric-value">--</div>
                        <div class="metric-trend">--</div>
                    </div>
                    <div class="metric-item" id="error-rates-metric">
                        <h3>Error Rates</h3>
                        <div class="metric-value">--</div>
                        <div class="metric-trend">--</div>
                    </div>
                </div>
            </div>

            <!-- Charts -->
            <div class="dashboard-card chart-card">
                <h2>Validation Trends</h2>
                <canvas id="validation-chart"></canvas>
            </div>

            <!-- Alerts -->
            <div class="dashboard-card alerts-card">
                <h2>Recent Alerts</h2>
                <div class="alerts-container" id="alerts-container">
                    <p>No alerts</p>
                </div>
            </div>

            <!-- System Info -->
            <div class="dashboard-card system-card">
                <h2>System Information</h2>
                <div class="system-info" id="system-info">
                    <p>Loading system information...</p>
                </div>
            </div>

            <!-- Validation Summary -->
            <div class="dashboard-card summary-card">
                <h2>Validation Summary</h2>
                <div class="summary-stats" id="summary-stats">
                    <div class="stat-item">
                        <span class="stat-label">Total:</span>
                        <span class="stat-value" id="total-validations">0</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Passed:</span>
                        <span class="stat-value passed" id="passed-validations">0</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Warnings:</span>
                        <span class="stat-value warning" id="warning-validations">0</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Critical:</span>
                        <span class="stat-value critical" id="critical-validations">0</span>
                    </div>
                </div>
                <div class="success-rate">
                    <span>Success Rate: </span>
                    <span id="success-rate">0%</span>
                </div>
            </div>
        </div>

        <footer class="dashboard-footer">
            <p>Last Updated: <span id="last-update">Never</span></p>
            <p>Agent-QualityAssurance FASE 4 - Continuous Validation System</p>
        </footer>
    </div>

    <script src="dashboard.js"></script>
</body>
</html>'''
        
        with open(self.dashboard_html_file, 'w') as f:
            f.write(html_content)
    
    def _generate_dashboard_css(self):
        """Gerar arquivo CSS do dashboard"""
        css_content = '''/* Dashboard Styles */
* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: #333;
    min-height: 100vh;
}

.dashboard-container {
    max-width: 1400px;
    margin: 0 auto;
    padding: 20px;
}

.dashboard-header {
    background: white;
    border-radius: 10px;
    padding: 20px;
    margin-bottom: 20px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.dashboard-header h1 {
    color: #333;
    font-size: 28px;
}

.status-indicator {
    display: flex;
    align-items: center;
    gap: 10px;
}

.status-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: #gray;
}

.status-dot.running {
    background: #4caf50;
    animation: pulse 2s infinite;
}

.status-dot.warning {
    background: #ff9800;
}

.status-dot.critical {
    background: #f44336;
}

@keyframes pulse {
    0% { opacity: 1; }
    50% { opacity: 0.5; }
    100% { opacity: 1; }
}

.dashboard-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
    gap: 20px;
}

.dashboard-card {
    background: white;
    border-radius: 10px;
    padding: 20px;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.dashboard-card h2 {
    margin-bottom: 15px;
    color: #333;
    font-size: 18px;
    border-bottom: 2px solid #eee;
    padding-bottom: 10px;
}

/* Progress Card */
.progress-container {
    text-align: center;
}

.progress-bar {
    width: 100%;
    height: 20px;
    background: #eee;
    border-radius: 10px;
    overflow: hidden;
    margin-bottom: 10px;
}

.progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #4caf50, #8bc34a);
    width: 0%;
    transition: width 0.5s ease;
}

.progress-text {
    font-size: 16px;
    font-weight: bold;
    color: #666;
}

/* Metrics Card */
.metrics-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 15px;
}

.metric-item {
    text-align: center;
    padding: 15px;
    border: 1px solid #eee;
    border-radius: 8px;
}

.metric-item h3 {
    font-size: 14px;
    color: #666;
    margin-bottom: 8px;
}

.metric-value {
    font-size: 24px;
    font-weight: bold;
    color: #333;
    margin-bottom: 5px;
}

.metric-trend {
    font-size: 12px;
    color: #666;
}

.metric-trend.improving {
    color: #4caf50;
}

.metric-trend.declining {
    color: #f44336;
}

/* Chart Card */
.chart-card {
    grid-column: span 2;
}

#validation-chart {
    max-height: 300px;
}

/* Alerts Card */
.alerts-container {
    max-height: 300px;
    overflow-y: auto;
}

.alert-item {
    padding: 10px;
    margin-bottom: 8px;
    border-radius: 5px;
    border-left: 4px solid;
    font-size: 14px;
}

.alert-item.critical {
    background: #ffebee;
    border-left-color: #f44336;
}

.alert-item.warning {
    background: #fff3e0;
    border-left-color: #ff9800;
}

.alert-item.info {
    background: #e3f2fd;
    border-left-color: #2196f3;
}

.alert-time {
    font-size: 12px;
    color: #666;
    margin-bottom: 4px;
}

/* System Card */
.system-info {
    font-size: 14px;
    line-height: 1.6;
}

.system-info p {
    margin-bottom: 8px;
    display: flex;
    justify-content: space-between;
}

.system-info strong {
    color: #333;
}

/* Summary Card */
.summary-stats {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
    margin-bottom: 15px;
}

.stat-item {
    display: flex;
    justify-content: space-between;
    padding: 8px;
    background: #f8f9fa;
    border-radius: 5px;
}

.stat-value.passed {
    color: #4caf50;
    font-weight: bold;
}

.stat-value.warning {
    color: #ff9800;
    font-weight: bold;
}

.stat-value.critical {
    color: #f44336;
    font-weight: bold;
}

.success-rate {
    text-align: center;
    font-size: 18px;
    font-weight: bold;
    color: #333;
}

/* Footer */
.dashboard-footer {
    text-align: center;
    margin-top: 40px;
    padding: 20px;
    color: white;
    font-size: 14px;
}

/* Responsive */
@media (max-width: 768px) {
    .dashboard-header {
        flex-direction: column;
        gap: 10px;
        text-align: center;
    }
    
    .dashboard-grid {
        grid-template-columns: 1fr;
    }
    
    .chart-card {
        grid-column: span 1;
    }
    
    .metrics-grid {
        grid-template-columns: 1fr;
    }
}'''
        
        with open(self.dashboard_css_file, 'w') as f:
            f.write(css_content)
    
    def _generate_dashboard_js(self):
        """Gerar arquivo JavaScript do dashboard"""
        js_content = '''// Dashboard JavaScript
class ValidationDashboard {
    constructor() {
        this.chart = null;
        this.refreshInterval = 30000; // 30 seconds
        this.init();
    }

    async init() {
        await this.loadData();
        this.initChart();
        this.startAutoRefresh();
    }

    async loadData() {
        try {
            const response = await fetch('dashboard_data.json');
            const data = await response.json();
            this.updateDashboard(data);
        } catch (error) {
            console.error('Failed to load dashboard data:', error);
        }
    }

    updateDashboard(data) {
        this.updateStatus(data.current_status);
        this.updateProgress(data.current_status);
        this.updateMetrics(data.validation_metrics);
        this.updateAlerts(data.active_alerts);
        this.updateSystemInfo(data.system_info);
        this.updateSummary(data.validation_summary);
        this.updateChart(data.charts_data);
        this.updateLastUpdateTime(data.timestamp);
    }

    updateStatus(status) {
        const statusDot = document.getElementById('status-dot');
        const statusText = document.getElementById('status-text');
        
        const statusMap = {
            'initializing': { text: 'Initializing...', class: '' },
            'running': { text: 'Validation Running', class: 'running' },
            'completed': { text: 'Validation Completed', class: 'running' },
            'warning': { text: 'Warnings Detected', class: 'warning' },
            'critical': { text: 'Critical Issues', class: 'critical' }
        };

        const statusInfo = statusMap[status.overall_status] || statusMap.initializing;
        statusText.textContent = statusInfo.text;
        statusDot.className = `status-dot ${statusInfo.class}`;
    }

    updateProgress(status) {
        const progressFill = document.getElementById('progress-fill');
        const progressText = document.getElementById('progress-text');
        
        const progress = status.validation_progress || 0;
        progressFill.style.width = `${progress}%`;
        
        const duration = this.calculateDuration(status.last_update);
        progressText.textContent = `${progress.toFixed(1)}% (${duration})`;
    }

    updateMetrics(metrics) {
        const metricTypes = ['data-integrity', 'performance', 'user-experience', 'error-rates'];
        
        metricTypes.forEach(type => {
            const hyphenated = type;
            const underscored = type.replace(/-/g, '_');
            
            const metricElement = document.getElementById(`${hyphenated}-metric`);
            if (metricElement && metrics[underscored]) {
                const metric = metrics[underscored];
                const valueElement = metricElement.querySelector('.metric-value');
                const trendElement = metricElement.querySelector('.metric-trend');
                
                valueElement.textContent = metric.current_score ? `${metric.current_score.toFixed(1)}%` : '--';
                trendElement.textContent = this.getTrendText(metric.trend);
                trendElement.className = `metric-trend ${metric.trend}`;
                
                // Color code based on status
                metricElement.className = `metric-item ${metric.status}`;
            }
        });
    }

    updateAlerts(alerts) {
        const alertsContainer = document.getElementById('alerts-container');
        
        let alertsHtml = '';
        const allAlerts = [
            ...(alerts.critical || []),
            ...(alerts.warning || []),
            ...(alerts.info || [])
        ].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

        if (allAlerts.length === 0) {
            alertsHtml = '<p>No alerts</p>';
        } else {
            allAlerts.slice(0, 5).forEach(alert => {
                const time = new Date(alert.timestamp).toLocaleTimeString();
                alertsHtml += `
                    <div class="alert-item ${alert.severity}">
                        <div class="alert-time">${time}</div>
                        <div class="alert-message">${alert.message}</div>
                    </div>
                `;
            });
        }

        alertsContainer.innerHTML = alertsHtml;
    }

    updateSystemInfo(systemInfo) {
        const systemInfoElement = document.getElementById('system-info');
        
        if (!systemInfo || Object.keys(systemInfo).length === 0) {
            systemInfoElement.innerHTML = '<p>Loading system information...</p>';
            return;
        }

        const infoHtml = `
            <p><strong>Redis Version:</strong> <span>${systemInfo.redis_version || 'N/A'}</span></p>
            <p><strong>Memory Usage:</strong> <span>${systemInfo.redis_memory_usage || 'N/A'}</span></p>
            <p><strong>Connected Clients:</strong> <span>${systemInfo.redis_connected_clients || 0}</span></p>
            <p><strong>Total Commands:</strong> <span>${systemInfo.redis_total_commands || 0}</span></p>
            <p><strong>Validation Duration:</strong> <span>${systemInfo.validation_duration || '0h 0m'}</span></p>
            <p><strong>Total Validations:</strong> <span>${systemInfo.total_validations || 0}</span></p>
        `;

        systemInfoElement.innerHTML = infoHtml;
    }

    updateSummary(summary) {
        if (!summary) return;

        document.getElementById('total-validations').textContent = summary.total_validations || 0;
        document.getElementById('passed-validations').textContent = summary.passed || 0;
        document.getElementById('warning-validations').textContent = summary.warnings || 0;
        document.getElementById('critical-validations').textContent = summary.critical || 0;
        document.getElementById('success-rate').textContent = `${(summary.success_rate || 0).toFixed(1)}%`;
    }

    initChart() {
        const ctx = document.getElementById('validation-chart').getContext('2d');
        
        this.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Data Integrity',
                        data: [],
                        borderColor: '#4CAF50',
                        backgroundColor: 'rgba(76, 175, 80, 0.1)',
                        tension: 0.4
                    },
                    {
                        label: 'Performance',
                        data: [],
                        borderColor: '#2196F3',
                        backgroundColor: 'rgba(33, 150, 243, 0.1)',
                        tension: 0.4
                    },
                    {
                        label: 'User Experience',
                        data: [],
                        borderColor: '#FF9800',
                        backgroundColor: 'rgba(255, 152, 0, 0.1)',
                        tension: 0.4
                    },
                    {
                        label: 'Error Health',
                        data: [],
                        borderColor: '#9C27B0',
                        backgroundColor: 'rgba(156, 39, 176, 0.1)',
                        tension: 0.4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 100
                    }
                },
                plugins: {
                    legend: {
                        position: 'top'
                    }
                }
            }
        });
    }

    updateChart(chartsData) {
        if (!this.chart || !chartsData) return;

        const validationTypes = ['data_integrity', 'performance', 'user_experience', 'error_rates'];
        
        // Get the longest timestamp array for labels
        let timestamps = [];
        validationTypes.forEach(type => {
            if (chartsData[type] && chartsData[type].timestamps.length > timestamps.length) {
                timestamps = chartsData[type].timestamps;
            }
        });

        // Format timestamps for display
        const labels = timestamps.map(ts => new Date(ts).toLocaleTimeString());

        this.chart.data.labels = labels;

        // Update datasets
        validationTypes.forEach((type, index) => {
            if (chartsData[type] && this.chart.data.datasets[index]) {
                this.chart.data.datasets[index].data = chartsData[type].scores || [];
            }
        });

        this.chart.update();
    }

    updateLastUpdateTime(timestamp) {
        const lastUpdateElement = document.getElementById('last-update');
        if (timestamp) {
            const updateTime = new Date(timestamp).toLocaleString();
            lastUpdateElement.textContent = updateTime;
        }
    }

    calculateDuration(lastUpdate) {
        if (!lastUpdate) return '0h 0m';
        
        const now = new Date();
        const start = new Date(lastUpdate);
        const diff = now - start;
        
        const hours = Math.floor(diff / (1000 * 60 * 60));
        const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
        
        return `${hours}h ${minutes}m`;
    }

    getTrendText(trend) {
        const trendMap = {
            'improving': '↗ Improving',
            'declining': '↘ Declining',
            'stable': '→ Stable'
        };
        return trendMap[trend] || '— Unknown';
    }

    startAutoRefresh() {
        setInterval(() => {
            this.loadData();
        }, this.refreshInterval);
    }
}

// Initialize dashboard when page loads
document.addEventListener('DOMContentLoaded', () => {
    new ValidationDashboard();
});'''
        
        with open(self.dashboard_js_file, 'w') as f:
            f.write(js_content)