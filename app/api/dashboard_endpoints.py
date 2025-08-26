"""
Dashboard API Endpoints - FASE 3 REST API Integration
Endpoints REST para integração completa do dashboard
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request

from loguru import logger

from app.services.progress_dashboard import get_progress_dashboard
from app.services.advanced_progress_manager import get_advanced_progress_manager
from app.services.progress_metrics_collector import get_metrics_collector
from app.api.websocket_progress import websocket_manager, websocket_progress_endpoint, websocket_stats_endpoint
from app.api.sse_integration import create_progress_stream
from app.services.securities import verify_token_async, get_current_user_optional


# Configurar router
router = APIRouter()

# Configurar templates (se não existir globalmente)
try:
    templates = Jinja2Templates(directory="templates")
except Exception as e:
    logger.warning(f"Templates directory not found: {e}")
    templates = None


@router.get("/", response_class=HTMLResponse)
async def dashboard_home(request: Request):
    """Página principal do dashboard"""
    if not templates:
        return HTMLResponse("""
        <html>
            <head><title>Dashboard Not Available</title></head>
            <body>
                <h1>Dashboard Not Available</h1>
                <p>Templates not configured. Please check template directory.</p>
            </body>
        </html>
        """)
    
    return templates.TemplateResponse("progress_dashboard.html", {"request": request})


@router.get("/data")
async def get_dashboard_data():
    """
    Obtém todos os dados do dashboard
    
    Returns:
        DashboardData: Dados completos do dashboard
    """
    try:
        dashboard = await get_progress_dashboard()
        data = await dashboard.get_dashboard_data(use_cache=False)
        
        return {
            "timestamp": data.timestamp,
            "summary": data.summary,
            "active_tasks": data.active_tasks,
            "recent_completed": data.recent_completed,
            "system_metrics": data.system_metrics,
            "performance_stats": data.performance_stats,
            "alerts": data.alerts,
            "system_health": data.system_health,
            "uptime_stats": data.uptime_stats
        }
        
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_dashboard_summary():
    """
    Obtém resumo do dashboard
    
    Returns:
        Dict: Resumo executivo do sistema
    """
    try:
        dashboard = await get_progress_dashboard()
        data = await dashboard.get_dashboard_data(use_cache=True)
        
        return {
            "timestamp": data.timestamp,
            "summary": data.summary,
            "system_health": data.system_health,
            "alerts_count": len(data.alerts),
            "active_tasks_count": len(data.active_tasks)
        }
        
    except Exception as e:
        logger.error(f"Error getting dashboard summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{task_id}/details")
async def get_task_details(task_id: str):
    """
    Obtém detalhes completos de uma tarefa
    
    Args:
        task_id: ID da tarefa
        
    Returns:
        Dict: Detalhes da tarefa incluindo timeline e eventos
    """
    try:
        dashboard = await get_progress_dashboard()
        details = await dashboard.get_task_details(task_id)
        
        if not details:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return details
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task details for {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/active")
async def get_active_tasks():
    """
    Obtém lista de tarefas ativas
    
    Returns:
        List: Lista de tarefas ativas
    """
    try:
        progress_manager = await get_advanced_progress_manager()
        active_task_ids = await progress_manager.get_active_tasks()
        
        active_tasks = []
        for task_id in active_task_ids:
            task_info = await progress_manager.get_advanced_task_info(task_id)
            if task_info:
                active_tasks.append({
                    "task_id": task_info.task_id,
                    "task_type": task_info.task_type,
                    "status": task_info.status,
                    "progress": task_info.progress.calculate_overall_progress(),
                    "current_stage": task_info.progress.current_stage,
                    "eta_seconds": task_info.progress.calculate_overall_eta(),
                    "created_at": task_info.created_at,
                    "started_at": task_info.started_at
                })
        
        return active_tasks
        
    except Exception as e:
        logger.error(f"Error getting active tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
async def get_system_metrics():
    """
    Obtém métricas do sistema
    
    Returns:
        Dict: Métricas do sistema
    """
    try:
        metrics_collector = await get_metrics_collector()
        metrics_summary = await metrics_collector.get_all_metrics_summary(3600)  # 1 hora
        
        return {
            "timestamp": datetime.now().isoformat(),
            "metrics": metrics_summary,
            "available_metrics": metrics_collector.get_metrics_list()
        }
        
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/{metric_name}")
async def get_metric_details(
    metric_name: str,
    time_window: int = Query(3600, description="Time window in seconds")
):
    """
    Obtém detalhes de uma métrica específica
    
    Args:
        metric_name: Nome da métrica
        time_window: Janela de tempo em segundos
        
    Returns:
        Dict: Detalhes da métrica
    """
    try:
        metrics_collector = await get_metrics_collector()
        summary = await metrics_collector.get_metric_summary(metric_name, time_window)
        
        if not summary:
            raise HTTPException(status_code=404, detail="Metric not found")
        
        return {
            "metric_name": metric_name,
            "time_window_seconds": time_window,
            "summary": summary,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting metric details for {metric_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics/{metric_name}/history")
async def get_metric_history(
    metric_name: str,
    hours: int = Query(1, description="Number of hours of history"),
    resolution: int = Query(60, description="Number of data points")
):
    """
    Obtém histórico de uma métrica
    
    Args:
        metric_name: Nome da métrica
        hours: Número de horas de histórico
        resolution: Número de pontos de dados
        
    Returns:
        List: Histórico da métrica
    """
    try:
        dashboard = await get_progress_dashboard()
        history = await dashboard.get_metrics_history(metric_name, hours)
        
        if history is None:
            raise HTTPException(status_code=404, detail="Metric not found")
        
        return history
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting metric history for {metric_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
async def get_system_alerts(
    limit: int = Query(50, description="Maximum number of alerts"),
    level: Optional[str] = Query(None, description="Filter by alert level")
):
    """
    Obtém alertas do sistema
    
    Args:
        limit: Número máximo de alertas
        level: Filtro por nível (critical, warning, info)
        
    Returns:
        List: Lista de alertas
    """
    try:
        dashboard = await get_progress_dashboard()
        data = await dashboard.get_dashboard_data(use_cache=True)
        
        alerts = data.alerts
        
        # Filtrar por nível se especificado
        if level:
            alerts = [alert for alert in alerts if alert.get("level") == level]
        
        # Limitar número de alertas
        alerts = alerts[:limit]
        
        return {
            "alerts": alerts,
            "total_count": len(data.alerts),
            "filtered_count": len(alerts),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting system alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def get_system_health():
    """
    Obtém status de saúde do sistema
    
    Returns:
        Dict: Status de saúde de todos os componentes
    """
    try:
        dashboard = await get_progress_dashboard()
        data = await dashboard.get_dashboard_data(use_cache=True)
        
        # Adicionar informações de conexões WebSocket
        websocket_stats = websocket_manager.get_stats() if websocket_manager else {}
        
        return {
            "timestamp": datetime.now().isoformat(),
            "overall_status": data.system_health.get("overall", "unknown"),
            "components": data.system_health,
            "uptime_stats": data.uptime_stats,
            "websocket_stats": websocket_stats,
            "performance_summary": data.performance_stats
        }
        
    except Exception as e:
        logger.error(f"Error getting system health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report")
async def generate_system_report():
    """
    Gera relatório completo do sistema
    
    Returns:
        Dict: Relatório detalhado do sistema
    """
    try:
        dashboard = await get_progress_dashboard()
        report = await dashboard.generate_system_report()
        
        return report
        
    except Exception as e:
        logger.error(f"Error generating system report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{task_id}/subscribe")
async def subscribe_to_task(
    task_id: str,
    user = Depends(get_current_user_optional)
):
    """
    Subscreve aos updates de uma tarefa (via WebSocket)
    
    Args:
        task_id: ID da tarefa
        
    Returns:
        Dict: Confirmação da subscrição
    """
    try:
        # Esta é uma operação que requer WebSocket ativo
        # Aqui apenas retornamos instruções
        return {
            "message": "To subscribe to task updates, connect via WebSocket",
            "websocket_url": "/ws/progress",
            "task_id": task_id,
            "instructions": {
                "1": "Connect to WebSocket endpoint",
                "2": f"Send: {{\"type\": \"subscribe\", \"data\": {{\"task_ids\": [\"{task_id}\"]}}}}",
                "3": "Receive real-time updates"
            }
        }
        
    except Exception as e:
        logger.error(f"Error subscribing to task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/alerts")
async def clear_alerts():
    """
    Limpa todos os alertas
    
    Returns:
        Dict: Confirmação da limpeza
    """
    try:
        dashboard = await get_progress_dashboard()
        dashboard.clear_cache()
        
        return {
            "message": "Alerts cleared successfully",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error clearing alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh")
async def refresh_dashboard():
    """
    Força refresh dos dados do dashboard
    
    Returns:
        Dict: Confirmação do refresh
    """
    try:
        dashboard = await get_progress_dashboard()
        dashboard.clear_cache()
        
        # Obter dados atualizados
        data = await dashboard.get_dashboard_data(use_cache=False)
        
        return {
            "message": "Dashboard refreshed successfully",
            "timestamp": data.timestamp,
            "summary": data.summary
        }
        
    except Exception as e:
        logger.error(f"Error refreshing dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/connections")
async def get_connection_stats():
    """
    Obtém estatísticas de conexões
    
    Returns:
        Dict: Estatísticas de WebSocket e SSE
    """
    try:
        websocket_stats = websocket_manager.get_stats() if websocket_manager else {}
        
        # Adicionar estatísticas do progress manager
        progress_manager = await get_advanced_progress_manager()
        progress_stats = await progress_manager.get_system_metrics()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "websocket": websocket_stats,
            "progress_manager": {
                "active_tasks": progress_stats.get("active_tasks", 0),
                "redis_health": progress_stats.get("redis_health", {}),
                "advanced_metrics": progress_stats.get("advanced_metrics", {})
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting connection stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket endpoints (delegados para websocket_progress.py)
@router.websocket("/ws/progress")
async def websocket_progress_handler(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    client_id: Optional[str] = Query(None)
):
    """WebSocket endpoint para progresso em tempo real"""
    await websocket_progress_endpoint(websocket, token, client_id)


@router.websocket("/ws/stats")
async def websocket_stats_handler(websocket: WebSocket):
    """WebSocket endpoint para estatísticas em tempo real"""
    await websocket_stats_endpoint(websocket)


# SSE endpoint (delegado para sse_integration.py)
@router.get("/stream")
async def sse_progress_stream(
    token: str = Query(None),
    channels: str = Query("progress,system")
):
    """SSE endpoint para stream de progresso"""
    return await create_progress_stream(token=token, channels=channels)


# Validation and testing endpoints
@router.get("/validation/test")
async def run_validation_test():
    """
    Executa teste de validação do sistema completo
    
    Returns:
        Dict: Resultados dos testes de validação
    """
    try:
        validation_results = {
            "timestamp": datetime.now().isoformat(),
            "tests": {},
            "overall_status": "unknown",
            "performance_targets": {}
        }
        
        # Test 1: Progress Manager
        try:
            progress_manager = await get_advanced_progress_manager()
            stats = await progress_manager.get_system_metrics()
            validation_results["tests"]["progress_manager"] = {
                "status": "pass",
                "redis_connected": stats.get("redis_health", {}).get("connected", False),
                "active_tasks": stats.get("active_tasks", 0)
            }
        except Exception as e:
            validation_results["tests"]["progress_manager"] = {
                "status": "fail",
                "error": str(e)
            }
        
        # Test 2: Metrics Collector
        try:
            metrics_collector = await get_metrics_collector()
            metrics = await metrics_collector.get_all_metrics_summary(300)  # 5 min
            validation_results["tests"]["metrics_collector"] = {
                "status": "pass",
                "metrics_count": len(metrics),
                "has_data": len(metrics) > 0
            }
        except Exception as e:
            validation_results["tests"]["metrics_collector"] = {
                "status": "fail",
                "error": str(e)
            }
        
        # Test 3: Dashboard
        try:
            dashboard = await get_progress_dashboard()
            data = await dashboard.get_dashboard_data(use_cache=False)
            validation_results["tests"]["dashboard"] = {
                "status": "pass",
                "data_loaded": data is not None,
                "health_status": data.system_health.get("overall", "unknown")
            }
        except Exception as e:
            validation_results["tests"]["dashboard"] = {
                "status": "fail",
                "error": str(e)
            }
        
        # Test 4: WebSocket Manager
        try:
            if websocket_manager:
                ws_stats = websocket_manager.get_stats()
                validation_results["tests"]["websocket"] = {
                    "status": "pass",
                    "initialized": True,
                    "active_connections": ws_stats.get("connections", {}).get("active", 0)
                }
            else:
                validation_results["tests"]["websocket"] = {
                    "status": "fail",
                    "error": "WebSocket manager not initialized"
                }
        except Exception as e:
            validation_results["tests"]["websocket"] = {
                "status": "fail",
                "error": str(e)
            }
        
        # Calcular status geral
        test_results = [test["status"] for test in validation_results["tests"].values()]
        if all(status == "pass" for status in test_results):
            validation_results["overall_status"] = "pass"
        elif any(status == "pass" for status in test_results):
            validation_results["overall_status"] = "partial"
        else:
            validation_results["overall_status"] = "fail"
        
        # Performance targets validation
        validation_results["performance_targets"] = {
            "websocket_latency_target": "<5ms",
            "websocket_concurrent_connections": "1000+",
            "dashboard_refresh_time": "<100ms",
            "progress_update_latency": "<5ms",
            "eta_accuracy": "±10%"
        }
        
        return validation_results
        
    except Exception as e:
        logger.error(f"Error running validation test: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/validation/performance")
async def run_performance_test():
    """
    Executa teste de performance do sistema
    
    Returns:
        Dict: Resultados do teste de performance
    """
    try:
        import time
        import asyncio
        
        performance_results = {
            "timestamp": datetime.now().isoformat(),
            "tests": {},
            "targets_met": {}
        }
        
        # Test 1: Dashboard Data Load Time
        start_time = time.time()
        dashboard = await get_progress_dashboard()
        await dashboard.get_dashboard_data(use_cache=False)
        load_time = (time.time() - start_time) * 1000  # ms
        
        performance_results["tests"]["dashboard_load_time"] = {
            "value": round(load_time, 2),
            "unit": "ms",
            "target": 100,
            "passed": load_time < 100
        }
        
        # Test 2: Metrics Collection Time
        start_time = time.time()
        metrics_collector = await get_metrics_collector()
        await metrics_collector.get_all_metrics_summary(300)
        metrics_time = (time.time() - start_time) * 1000  # ms
        
        performance_results["tests"]["metrics_collection_time"] = {
            "value": round(metrics_time, 2),
            "unit": "ms",
            "target": 50,
            "passed": metrics_time < 50
        }
        
        # Test 3: Progress Manager Response Time
        start_time = time.time()
        progress_manager = await get_advanced_progress_manager()
        await progress_manager.get_system_metrics()
        progress_time = (time.time() - start_time) * 1000  # ms
        
        performance_results["tests"]["progress_manager_time"] = {
            "value": round(progress_time, 2),
            "unit": "ms",
            "target": 10,
            "passed": progress_time < 10
        }
        
        # Calcular targets met
        all_tests = performance_results["tests"]
        total_tests = len(all_tests)
        passed_tests = len([test for test in all_tests.values() if test["passed"]])
        
        performance_results["targets_met"] = {
            "total_tests": total_tests,
            "passed_tests": passed_tests,
            "pass_rate": round((passed_tests / total_tests) * 100, 1) if total_tests > 0 else 0,
            "overall_performance": "excellent" if passed_tests == total_tests else 
                                  "good" if passed_tests >= total_tests * 0.8 else 
                                  "needs_improvement"
        }
        
        return performance_results
        
    except Exception as e:
        logger.error(f"Error running performance test: {e}")
        raise HTTPException(status_code=500, detail=str(e))