"""
FASE 4 - PERFORMANCE TUNING E OTIMIZAÇÃO FINAL
Sistema completo de otimização de performance Redis e aplicação

Agent-Optimization - Módulos de Otimização Final
"""

from .performance_optimizer import AdvancedPerformanceOptimizer
from .redis_config_optimizer import RedisConfigOptimizer
from .connection_pool_optimizer import ConnectionPoolOptimizer
from .cache_warming_system import CacheWarmingSystem
from .query_optimizer import QueryOptimizer
from .system_tuning import SystemTuner
from .optimization_validator import OptimizationValidator

__all__ = [
    'AdvancedPerformanceOptimizer',
    'RedisConfigOptimizer', 
    'ConnectionPoolOptimizer',
    'CacheWarmingSystem',
    'QueryOptimizer',
    'SystemTuner',
    'OptimizationValidator'
]

__version__ = "1.0.0"
__author__ = "Agent-Optimization"
__description__ = "Sistema completo de otimização final de performance"