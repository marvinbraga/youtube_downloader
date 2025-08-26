"""
Production Monitoring System - FASE 4 Implementation
Sistema completo de monitoramento intensivo pós-cutover

Agent-Infrastructure - Production Monitoring Intensivo 48h Pós-Cutover
"""

from .production_monitoring import production_monitoring, ProductionMonitoring
from .redis_monitor import redis_monitor, RedisMonitor
from .application_metrics import application_metrics_collector, ApplicationMetricsCollector
from .alert_system import alert_system, AlertSystem
from .performance_optimizer import performance_optimizer, PerformanceOptimizer
from .monitoring_dashboard import monitoring_dashboard, MonitoringDashboard
from .intensive_monitoring_scheduler import intensive_monitoring_scheduler, IntensiveMonitoringScheduler

__version__ = "4.0.0"
__author__ = "Agent-Infrastructure"

__all__ = [
    # Core monitoring components
    'production_monitoring',
    'ProductionMonitoring',
    'redis_monitor',
    'RedisMonitor',
    'application_metrics_collector',
    'ApplicationMetricsCollector',
    'alert_system',
    'AlertSystem',
    'performance_optimizer',
    'PerformanceOptimizer',
    'monitoring_dashboard',
    'MonitoringDashboard',
    'intensive_monitoring_scheduler',
    'IntensiveMonitoringScheduler'
]

# System information
MONITORING_SYSTEM_INFO = {
    "name": "Production Monitoring System",
    "version": __version__,
    "description": "Intensive 48-hour post-cutover monitoring system",
    "phase": "FASE 4 - Production Monitoring",
    "agent": "Agent-Infrastructure",
    "components": [
        "ProductionMonitoring",
        "RedisMonitor", 
        "ApplicationMetricsCollector",
        "AlertSystem",
        "PerformanceOptimizer",
        "MonitoringDashboard",
        "IntensiveMonitoringScheduler"
    ],
    "capabilities": [
        "Real-time system monitoring",
        "Redis performance analysis",
        "Application metrics collection",
        "Automated alert system",
        "Performance optimization",
        "Web dashboard interface",
        "48-hour intensive monitoring automation"
    ]
}


def get_system_info():
    """Returns monitoring system information"""
    return MONITORING_SYSTEM_INFO


async def initialize_monitoring_system():
    """Initialize all monitoring components"""
    components = [
        production_monitoring,
        redis_monitor,
        application_metrics_collector,
        alert_system,
        performance_optimizer
    ]
    
    initialized_components = []
    
    for component in components:
        try:
            if hasattr(component, 'initialize'):
                success = await component.initialize()
                if success:
                    initialized_components.append(component.__class__.__name__)
                else:
                    print(f"Failed to initialize {component.__class__.__name__}")
            else:
                initialized_components.append(component.__class__.__name__)
        except Exception as e:
            print(f"Error initializing {component.__class__.__name__}: {e}")
    
    return initialized_components


async def start_intensive_monitoring():
    """Start 48-hour intensive monitoring"""
    return await intensive_monitoring_scheduler.start_intensive_monitoring()


async def stop_intensive_monitoring():
    """Stop intensive monitoring"""
    return await intensive_monitoring_scheduler.stop_intensive_monitoring()


async def get_monitoring_status():
    """Get status of all monitoring components"""
    status = {
        "system_info": get_system_info(),
        "components_status": {
            "production_monitoring": {
                "active": production_monitoring.is_monitoring,
                "status": await production_monitoring.get_current_status()
            },
            "redis_monitor": {
                "active": redis_monitor.is_monitoring,
                "status": await redis_monitor.get_current_status()
            },
            "application_metrics": {
                "active": application_metrics_collector.is_collecting,
                "status": await application_metrics_collector.get_current_metrics()
            },
            "alert_system": {
                "active": alert_system.is_running,
                "status": await alert_system.get_alert_dashboard()
            },
            "performance_optimizer": {
                "active": performance_optimizer.is_optimizing,
                "status": await performance_optimizer.get_optimization_status()
            },
            "intensive_scheduler": {
                "active": intensive_monitoring_scheduler.is_running,
                "status": await intensive_monitoring_scheduler.get_monitoring_status()
            }
        }
    }
    
    return status