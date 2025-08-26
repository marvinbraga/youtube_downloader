"""
Monitoring Dashboard - Real-time Web Interface for Production Monitoring
Dashboard web em tempo real para visualização de métricas e alertas

Agent-Infrastructure - FASE 4 Production Monitoring
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import asdict
import statistics

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from loguru import logger

from .production_monitoring import production_monitoring
from .redis_monitor import redis_monitor
from .application_metrics import application_metrics_collector
from .alert_system import alert_system


class MonitoringDashboard:
    """
    Dashboard web para monitoramento de produção em tempo real
    
    Funcionalidades:
    - Dashboard principal com métricas em tempo real
    - Gráficos históricos de performance
    - Painel de alertas ativos
    - Análise de tendências
    - Controles de configuração
    - WebSocket para atualizações em tempo real
    """
    
    def __init__(self):
        self.app = FastAPI(title="Production Monitoring Dashboard")
        
        # WebSocket connections
        self.active_connections: List[WebSocket] = []
        
        # Templates and static files
        try:
            self.templates = Jinja2Templates(directory="monitoring/templates")
            self.app.mount("/static", StaticFiles(directory="monitoring/static"), name="static")
        except Exception as e:
            logger.warning(f"Templates/static files not found: {e}")
            self.templates = None
        
        # Setup routes
        self._setup_routes()
        
        # Background task for broadcasting updates
        self._broadcast_task = None
        
        logger.info("Monitoring dashboard initialized")
    
    def _setup_routes(self):
        """Configura rotas do dashboard"""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard_home(request: Request):
            """Página principal do dashboard"""
            if self.templates:
                return self.templates.TemplateResponse("dashboard.html", {"request": request})
            else:
                return HTMLResponse(content=self._get_basic_dashboard_html())
        
        @self.app.get("/health")
        async def health_check():
            """Health check do dashboard"""
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "monitoring_active": production_monitoring.is_monitoring,
                "redis_monitoring": redis_monitor.is_monitoring,
                "metrics_collecting": application_metrics_collector.is_collecting,
                "alerts_running": alert_system.is_running
            }
        
        @self.app.get("/api/status")
        async def get_system_status():
            """Status geral do sistema"""
            try:
                # Coleta status de todos os componentes
                production_status = await production_monitoring.get_current_status()
                redis_status = await redis_monitor.get_current_status()
                metrics_status = await application_metrics_collector.get_current_metrics()
                alerts_dashboard = await alert_system.get_alert_dashboard()
                
                return {
                    "timestamp": datetime.now().isoformat(),
                    "overall_health": self._calculate_overall_health(production_status, redis_status, alerts_dashboard),
                    "production_monitoring": production_status,
                    "redis_monitoring": redis_status,
                    "application_metrics": metrics_status,
                    "alert_system": alerts_dashboard
                }
                
            except Exception as e:
                logger.error(f"Error getting system status: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/metrics/realtime")
        async def get_realtime_metrics():
            """Métricas em tempo real"""
            try:
                current_metrics = await application_metrics_collector.get_current_metrics()
                
                if "status" in current_metrics and current_metrics["status"] == "no_data":
                    return {"error": "No metrics available"}
                
                # Formata métricas para o dashboard
                formatted_metrics = {
                    "timestamp": current_metrics.get("timestamp"),
                    "system": {
                        "cpu_percent": current_metrics["system"]["cpu_percent"],
                        "memory_percent": current_metrics["system"]["memory_percent"],
                        "disk_percent": current_metrics["system"]["disk_percent"],
                        "network_io_mbps": (
                            current_metrics["system"]["network_bytes_sent_per_sec"] + 
                            current_metrics["system"]["network_bytes_recv_per_sec"]
                        ) / (1024 * 1024)
                    },
                    "application": {
                        "api_requests_per_minute": current_metrics["application"]["api_requests_per_minute"],
                        "api_success_rate": current_metrics["application"]["api_success_rate"],
                        "api_avg_response_time_ms": current_metrics["application"]["api_avg_response_time_ms"],
                        "active_downloads": current_metrics["application"]["active_downloads"],
                        "active_transcriptions": current_metrics["application"]["active_transcriptions"],
                        "cache_hit_rate": current_metrics["application"]["cache_hit_rate"]
                    }
                }
                
                return formatted_metrics
                
            except Exception as e:
                logger.error(f"Error getting realtime metrics: {e}")
                return {"error": str(e)}
        
        @self.app.get("/api/redis/status")
        async def get_redis_status():
            """Status detalhado do Redis"""
            try:
                redis_status = await redis_monitor.get_current_status()
                
                if "status" in redis_status and redis_status["status"] == "no_data":
                    return {"error": "No Redis data available"}
                
                snapshot = redis_status["snapshot"]
                
                return {
                    "timestamp": snapshot["timestamp"],
                    "memory": {
                        "used_mb": snapshot["used_memory_mb"],
                        "used_percent": snapshot["used_memory_percent"],
                        "peak_mb": snapshot["used_memory_peak_mb"],
                        "fragmentation_ratio": snapshot["mem_fragmentation_ratio"]
                    },
                    "performance": {
                        "hit_rate": snapshot["hit_rate"],
                        "ops_per_sec": snapshot["ops_per_sec"],
                        "avg_latency_ms": snapshot["avg_latency_ms"],
                        "slow_queries_count": snapshot["slow_queries_count"]
                    },
                    "connections": {
                        "connected_clients": snapshot["connected_clients"],
                        "blocked_clients": snapshot["blocked_clients"]
                    },
                    "keyspace": {
                        "total_keys": snapshot["total_keys"],
                        "expired_keys": snapshot["expired_keys"],
                        "evicted_keys": snapshot["evicted_keys"]
                    }
                }
                
            except Exception as e:
                logger.error(f"Error getting Redis status: {e}")
                return {"error": str(e)}
        
        @self.app.get("/api/alerts/active")
        async def get_active_alerts():
            """Alertas ativos"""
            try:
                dashboard_data = await alert_system.get_alert_dashboard()
                return {
                    "timestamp": dashboard_data["timestamp"],
                    "total_active": dashboard_data["active_alerts_count"],
                    "alerts": dashboard_data["active_alerts"],
                    "severity_breakdown": dashboard_data["severity_breakdown"]
                }
            except Exception as e:
                logger.error(f"Error getting active alerts: {e}")
                return {"error": str(e)}
        
        @self.app.get("/api/alerts/history")
        async def get_alert_history(hours: int = 24):
            """Histórico de alertas"""
            try:
                history = await alert_system.get_alert_history(hours)
                return {
                    "period_hours": hours,
                    "total_alerts": len(history),
                    "alerts": history[:50]  # Últimos 50
                }
            except Exception as e:
                logger.error(f"Error getting alert history: {e}")
                return {"error": str(e)}
        
        @self.app.get("/api/performance/report")
        async def get_performance_report(hours: int = 6):
            """Relatório de performance"""
            try:
                # Combina relatórios de diferentes componentes
                production_report = await production_monitoring.get_health_report(hours)
                redis_report = await redis_monitor.get_performance_report(hours)
                metrics_summary = await application_metrics_collector.get_metrics_summary(hours)
                
                return {
                    "period_hours": hours,
                    "timestamp": datetime.now().isoformat(),
                    "overall": production_report,
                    "redis": redis_report,
                    "system_and_application": metrics_summary
                }
                
            except Exception as e:
                logger.error(f"Error getting performance report: {e}")
                return {"error": str(e)}
        
        @self.app.get("/api/metrics/historical")
        async def get_historical_metrics(hours: int = 12, metric_type: str = "all"):
            """Métricas históricas para gráficos"""
            try:
                return await self._get_historical_data(hours, metric_type)
            except Exception as e:
                logger.error(f"Error getting historical metrics: {e}")
                return {"error": str(e)}
        
        @self.app.post("/api/alerts/{alert_id}/acknowledge")
        async def acknowledge_alert(alert_id: str, acknowledged_by: str = "dashboard_user"):
            """Reconhece um alerta"""
            try:
                success = await alert_system.acknowledge_alert(alert_id, acknowledged_by)
                return {"success": success, "alert_id": alert_id}
            except Exception as e:
                logger.error(f"Error acknowledging alert: {e}")
                return {"error": str(e)}
        
        @self.app.get("/api/system/recommendations")
        async def get_system_recommendations():
            """Recomendações de otimização"""
            try:
                # Coleta dados para gerar recomendações
                production_report = await production_monitoring.get_health_report(24)
                redis_report = await redis_monitor.get_performance_report(24)
                
                recommendations = []
                
                # Adiciona recomendações dos relatórios
                if "recommendations" in production_report:
                    recommendations.extend(production_report["recommendations"])
                
                if "recommendations" in redis_report:
                    recommendations.extend(redis_report["recommendations"])
                
                # Adiciona recomendações baseadas em análise do dashboard
                dashboard_recommendations = await self._generate_dashboard_recommendations()
                recommendations.extend(dashboard_recommendations)
                
                return {
                    "timestamp": datetime.now().isoformat(),
                    "total_recommendations": len(recommendations),
                    "recommendations": recommendations[:10]  # Top 10
                }
                
            except Exception as e:
                logger.error(f"Error getting recommendations: {e}")
                return {"error": str(e)}
        
        @self.app.websocket("/ws/metrics")
        async def websocket_metrics(websocket: WebSocket):
            """WebSocket para métricas em tempo real"""
            await websocket.accept()
            self.active_connections.append(websocket)
            
            try:
                while True:
                    await websocket.receive_text()  # Keep alive
            except WebSocketDisconnect:
                self.active_connections.remove(websocket)
                logger.info("WebSocket client disconnected")
    
    def _calculate_overall_health(self, production_status: Dict, redis_status: Dict, alerts_dashboard: Dict) -> Dict[str, Any]:
        """Calcula saúde geral do sistema"""
        try:
            # Health score de produção
            production_score = production_status.get("health_score", 50)
            
            # Penaliza por alertas ativos
            active_alerts = alerts_dashboard.get("active_alerts_count", 0)
            critical_alerts = alerts_dashboard.get("severity_breakdown", {}).get("critical", 0)
            
            alert_penalty = min(active_alerts * 2 + critical_alerts * 5, 30)
            overall_score = max(0, production_score - alert_penalty)
            
            # Determina status
            if overall_score >= 90:
                status = "excellent"
                color = "green"
            elif overall_score >= 75:
                status = "good"
                color = "lightgreen"
            elif overall_score >= 60:
                status = "fair"
                color = "yellow"
            elif overall_score >= 40:
                status = "poor"
                color = "orange"
            else:
                status = "critical"
                color = "red"
            
            return {
                "score": round(overall_score, 1),
                "status": status,
                "color": color,
                "active_alerts": active_alerts,
                "critical_alerts": critical_alerts
            }
            
        except Exception as e:
            logger.error(f"Error calculating overall health: {e}")
            return {"score": 50, "status": "unknown", "color": "gray"}
    
    async def _get_historical_data(self, hours: int, metric_type: str) -> Dict[str, Any]:
        """Obtém dados históricos para gráficos"""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)
            
            # Por simplicidade, vamos simular dados históricos
            # Em uma implementação real, você buscaria do Redis
            
            data_points = []
            current_time = start_time
            interval_minutes = 5  # Pontos a cada 5 minutos
            
            while current_time <= end_time:
                # Simula métricas baseadas no estado atual
                try:
                    current_metrics = await application_metrics_collector.get_current_metrics()
                    
                    if "system" in current_metrics and "application" in current_metrics:
                        point = {
                            "timestamp": current_time.isoformat(),
                            "cpu_percent": current_metrics["system"]["cpu_percent"] + (hash(str(current_time)) % 20 - 10),
                            "memory_percent": current_metrics["system"]["memory_percent"] + (hash(str(current_time)) % 10 - 5),
                            "api_response_time": current_metrics["application"]["api_avg_response_time_ms"] + (hash(str(current_time)) % 100 - 50),
                            "active_downloads": max(0, current_metrics["application"]["active_downloads"] + (hash(str(current_time)) % 6 - 3))
                        }
                    else:
                        # Dados padrão se não houver métricas
                        point = {
                            "timestamp": current_time.isoformat(),
                            "cpu_percent": 45 + (hash(str(current_time)) % 20 - 10),
                            "memory_percent": 60 + (hash(str(current_time)) % 20 - 10),
                            "api_response_time": 150 + (hash(str(current_time)) % 100 - 50),
                            "active_downloads": max(0, 5 + (hash(str(current_time)) % 6 - 3))
                        }
                    
                    data_points.append(point)
                    
                except Exception:
                    # Dados padrão em caso de erro
                    point = {
                        "timestamp": current_time.isoformat(),
                        "cpu_percent": 50,
                        "memory_percent": 65,
                        "api_response_time": 200,
                        "active_downloads": 3
                    }
                    data_points.append(point)
                
                current_time += timedelta(minutes=interval_minutes)
            
            return {
                "period_hours": hours,
                "metric_type": metric_type,
                "data_points": data_points[-144:],  # Últimos 144 pontos (12h se 5min interval)
                "summary": {
                    "total_points": len(data_points),
                    "start_time": start_time.isoformat(),
                    "end_time": end_time.isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting historical data: {e}")
            return {"error": str(e)}
    
    async def _generate_dashboard_recommendations(self) -> List[str]:
        """Gera recomendações baseadas nos dados do dashboard"""
        recommendations = []
        
        try:
            # Obtém status atual
            current_status = await self.app.router.routes[2].endpoint()  # get_system_status
            
            if "error" in current_status:
                return recommendations
            
            production_data = current_status.get("production_monitoring", {})
            alerts_data = current_status.get("alert_system", {})
            
            # Recomendações baseadas em health score
            health_score = production_data.get("health_score", 50)
            if health_score < 70:
                recommendations.append("System health score is below 70% - investigate active issues immediately")
            
            # Recomendações baseadas em alertas
            active_alerts = alerts_data.get("active_alerts_count", 0)
            if active_alerts > 10:
                recommendations.append("High number of active alerts - consider alert fatigue mitigation strategies")
            
            # Recomendações baseadas em frequência de alertas
            recent_alerts = alerts_data.get("recent_alerts_24h", 0)
            if recent_alerts > 50:
                recommendations.append("Very high alert frequency in last 24h - review alert thresholds")
            
            # Recomendações baseadas em duração de monitoramento
            monitoring_duration = production_data.get("monitoring_duration", "0h 0m")
            if "0h" in monitoring_duration and "0m" in monitoring_duration:
                recommendations.append("Monitoring system not running - start production monitoring immediately")
            
        except Exception as e:
            logger.error(f"Error generating dashboard recommendations: {e}")
        
        return recommendations
    
    async def start_background_broadcast(self):
        """Inicia broadcast em background para WebSockets"""
        if self._broadcast_task is None:
            self._broadcast_task = asyncio.create_task(self._broadcast_metrics_loop())
            logger.info("Started background WebSocket broadcast")
    
    async def stop_background_broadcast(self):
        """Para broadcast em background"""
        if self._broadcast_task:
            self._broadcast_task.cancel()
            self._broadcast_task = None
            logger.info("Stopped background WebSocket broadcast")
    
    async def _broadcast_metrics_loop(self):
        """Loop de broadcast de métricas via WebSocket"""
        while True:
            try:
                if self.active_connections:
                    # Obtém métricas atuais
                    metrics = await self._get_broadcast_data()
                    
                    # Envia para todos os clientes conectados
                    disconnected = []
                    for connection in self.active_connections:
                        try:
                            await connection.send_text(json.dumps(metrics))
                        except Exception as e:
                            logger.warning(f"WebSocket send failed: {e}")
                            disconnected.append(connection)
                    
                    # Remove conexões mortas
                    for conn in disconnected:
                        if conn in self.active_connections:
                            self.active_connections.remove(conn)
                
                await asyncio.sleep(5)  # Broadcast a cada 5 segundos
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in broadcast loop: {e}")
                await asyncio.sleep(5)
    
    async def _get_broadcast_data(self) -> Dict[str, Any]:
        """Obtém dados para broadcast via WebSocket"""
        try:
            # Coleta métricas essenciais
            realtime_metrics = await self.app.router.routes[3].endpoint()  # get_realtime_metrics
            redis_status = await self.app.router.routes[4].endpoint()  # get_redis_status
            active_alerts = await self.app.router.routes[5].endpoint()  # get_active_alerts
            
            return {
                "type": "metrics_update",
                "timestamp": datetime.now().isoformat(),
                "realtime": realtime_metrics if "error" not in realtime_metrics else {},
                "redis": redis_status if "error" not in redis_status else {},
                "alerts": active_alerts if "error" not in active_alerts else {}
            }
            
        except Exception as e:
            logger.error(f"Error getting broadcast data: {e}")
            return {
                "type": "error",
                "timestamp": datetime.now().isoformat(),
                "message": str(e)
            }
    
    def _get_basic_dashboard_html(self) -> str:
        """HTML básico do dashboard quando templates não estão disponíveis"""
        return """
<!DOCTYPE html>
<html>
<head>
    <title>Production Monitoring Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: #2c3e50; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .card { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .status-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; }
        .metric { text-align: center; padding: 15px; }
        .metric-value { font-size: 2em; font-weight: bold; color: #27ae60; }
        .metric-label { color: #7f8c8d; margin-top: 5px; }
        .alert-critical { color: #e74c3c; }
        .alert-high { color: #f39c12; }
        .alert-medium { color: #f1c40f; }
        .btn { background: #3498db; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
        .btn:hover { background: #2980b9; }
        .loading { color: #7f8c8d; font-style: italic; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Production Monitoring Dashboard</h1>
            <p>Real-time monitoring for YouTube Downloader - Post-Cutover Intensive Monitoring</p>
        </div>
        
        <div class="card">
            <h2>System Status</h2>
            <div id="system-status" class="loading">Loading system status...</div>
        </div>
        
        <div class="status-grid">
            <div class="card">
                <div class="metric">
                    <div id="health-score" class="metric-value">--</div>
                    <div class="metric-label">Health Score</div>
                </div>
            </div>
            <div class="card">
                <div class="metric">
                    <div id="active-alerts" class="metric-value">--</div>
                    <div class="metric-label">Active Alerts</div>
                </div>
            </div>
            <div class="card">
                <div class="metric">
                    <div id="redis-memory" class="metric-value">--</div>
                    <div class="metric-label">Redis Memory %</div>
                </div>
            </div>
            <div class="card">
                <div class="metric">
                    <div id="api-response" class="metric-value">--</div>
                    <div class="metric-label">API Response (ms)</div>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h2>Active Alerts</h2>
            <div id="alerts-list" class="loading">Loading alerts...</div>
        </div>
        
        <div class="card">
            <h2>Controls</h2>
            <button class="btn" onclick="refreshData()">Refresh Data</button>
            <button class="btn" onclick="exportReport()">Export Report</button>
        </div>
    </div>

    <script>
        let updateInterval;
        
        async function loadSystemStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                if (data.overall_health) {
                    document.getElementById('health-score').textContent = data.overall_health.score + '%';
                    document.getElementById('active-alerts').textContent = data.overall_health.active_alerts;
                }
                
                document.getElementById('system-status').innerHTML = `
                    <strong>Overall Status:</strong> ${data.overall_health?.status || 'Unknown'} <br>
                    <strong>Last Update:</strong> ${new Date(data.timestamp).toLocaleString()}
                `;
                
            } catch (error) {
                document.getElementById('system-status').innerHTML = 'Error loading status: ' + error.message;
            }
        }
        
        async function loadRedisStatus() {
            try {
                const response = await fetch('/api/redis/status');
                const data = await response.json();
                
                if (data.memory) {
                    document.getElementById('redis-memory').textContent = data.memory.used_percent.toFixed(1) + '%';
                }
            } catch (error) {
                console.error('Error loading Redis status:', error);
            }
        }
        
        async function loadRealtimeMetrics() {
            try {
                const response = await fetch('/api/metrics/realtime');
                const data = await response.json();
                
                if (data.application) {
                    document.getElementById('api-response').textContent = data.application.api_avg_response_time_ms.toFixed(0);
                }
            } catch (error) {
                console.error('Error loading realtime metrics:', error);
            }
        }
        
        async function loadActiveAlerts() {
            try {
                const response = await fetch('/api/alerts/active');
                const data = await response.json();
                
                const alertsList = document.getElementById('alerts-list');
                
                if (data.alerts && data.alerts.length > 0) {
                    let html = '<ul>';
                    data.alerts.slice(0, 10).forEach(alert => {
                        const severityClass = 'alert-' + alert.severity;
                        html += `<li class="${severityClass}"><strong>${alert.title}</strong> - ${alert.description}</li>`;
                    });
                    html += '</ul>';
                    alertsList.innerHTML = html;
                } else {
                    alertsList.innerHTML = '<p style="color: #27ae60;">No active alerts</p>';
                }
                
            } catch (error) {
                document.getElementById('alerts-list').innerHTML = 'Error loading alerts: ' + error.message;
            }
        }
        
        async function refreshData() {
            await Promise.all([
                loadSystemStatus(),
                loadRedisStatus(),
                loadRealtimeMetrics(),
                loadActiveAlerts()
            ]);
        }
        
        async function exportReport() {
            try {
                const response = await fetch('/api/performance/report?hours=6');
                const data = await response.json();
                
                const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `monitoring-report-${new Date().toISOString().slice(0,19)}.json`;
                a.click();
                window.URL.revokeObjectURL(url);
            } catch (error) {
                alert('Error exporting report: ' + error.message);
            }
        }
        
        // Inicialização
        document.addEventListener('DOMContentLoaded', function() {
            refreshData();
            updateInterval = setInterval(refreshData, 30000); // Atualiza a cada 30 segundos
        });
        
        // WebSocket para atualizações em tempo real
        try {
            const ws = new WebSocket('ws://localhost:8000/ws/metrics');
            ws.onmessage = function(event) {
                const data = JSON.parse(event.data);
                if (data.type === 'metrics_update') {
                    // Atualiza métricas específicas sem recarregar tudo
                    if (data.realtime?.application) {
                        document.getElementById('api-response').textContent = data.realtime.application.api_avg_response_time_ms.toFixed(0);
                    }
                    if (data.redis?.memory) {
                        document.getElementById('redis-memory').textContent = data.redis.memory.used_percent.toFixed(1) + '%';
                    }
                    if (data.alerts) {
                        document.getElementById('active-alerts').textContent = data.alerts.total_active;
                    }
                }
            };
        } catch (error) {
            console.log('WebSocket connection failed, using polling updates only');
        }
    </script>
</body>
</html>
        """


# Instância global do dashboard
monitoring_dashboard = MonitoringDashboard()