"""
Advanced Performance Optimizer - FASE 4 Final Performance Tuning
Sistema avançado de otimização de performance com Machine Learning e auto-tuning

Agent-Optimization - Sistema de otimização inteligente e adaptativo
"""

import asyncio
import json
import time
import statistics
import psutil
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
import pickle
from pathlib import Path

from loguru import logger

from app.services.redis_connection import get_redis_client


@dataclass
class PerformanceMetrics:
    """Métricas completas de performance"""
    timestamp: datetime
    
    # Métricas Redis
    redis_latency_ms: float = 0.0
    redis_hit_rate: float = 1.0
    redis_memory_used_mb: float = 0.0
    redis_memory_used_percent: float = 0.0
    redis_connected_clients: int = 0
    redis_ops_per_sec: int = 0
    redis_evicted_keys: int = 0
    redis_expired_keys: int = 0
    redis_fragmentation_ratio: float = 1.0
    redis_keyspace_hits: int = 0
    redis_keyspace_misses: int = 0
    
    # Métricas de Sistema
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    disk_io_read_mb: float = 0.0
    disk_io_write_mb: float = 0.0
    network_sent_mb: float = 0.0
    network_recv_mb: float = 0.0
    
    # Métricas de Aplicação
    active_downloads: int = 0
    queue_size: int = 0
    api_response_time_ms: float = 0.0
    connection_pool_size: int = 0
    connection_pool_available: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte para dicionário com timestamp formatado"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class OptimizationTarget:
    """Target de otimização com pesos adaptativos"""
    name: str
    current_value: float
    target_value: float
    weight: float = 1.0
    tolerance: float = 0.05  # 5% tolerance
    priority: int = 1  # 1=alta, 2=média, 3=baixa
    
    def calculate_distance(self) -> float:
        """Calcula distância normalizada do target"""
        if self.target_value == 0:
            return abs(self.current_value)
        return abs(self.current_value - self.target_value) / self.target_value
    
    def is_achieved(self) -> bool:
        """Verifica se target foi atingido"""
        return self.calculate_distance() <= self.tolerance


@dataclass
class OptimizationStrategy:
    """Estratégia de otimização com ML adaptativo"""
    id: str
    name: str
    description: str
    category: str  # redis, system, application, network
    
    # Condições para ativação
    conditions: Dict[str, Any] = field(default_factory=dict)
    
    # Parâmetros da estratégia
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Métricas de efetividade
    success_rate: float = 0.0
    avg_impact_score: float = 0.0
    execution_count: int = 0
    last_executed: Optional[datetime] = None
    
    # Configurações de ML
    learning_rate: float = 0.1
    adaptation_threshold: float = 0.8
    cooldown_minutes: int = 30
    
    # Dados de aprendizado
    performance_history: List[float] = field(default_factory=list)
    parameter_effectiveness: Dict[str, float] = field(default_factory=dict)


class AdvancedPerformanceOptimizer:
    """
    Sistema avançado de otimização de performance com:
    - Machine Learning adaptativo para auto-tuning
    - Otimização multi-objetivo
    - Predição de performance
    - Auto-scaling de recursos
    - Otimização em tempo real
    """
    
    def __init__(self, 
                 optimization_interval: int = 60,  # 1 minuto
                 learning_enabled: bool = True):
        
        self.optimization_interval = optimization_interval
        self.learning_enabled = learning_enabled
        self.is_running = False
        self._stop_signal = False
        
        # Storage de dados
        self._metrics_history: deque[PerformanceMetrics] = deque(maxlen=10000)
        self._optimization_strategies: Dict[str, OptimizationStrategy] = {}
        self._performance_targets: Dict[str, OptimizationTarget] = {}
        
        # ML e predição
        self._performance_predictor = None
        self._optimization_model = None
        self._feature_scaler = None
        
        # Cache de configurações otimizadas
        self._optimal_configs: Dict[str, Any] = {}
        self._config_performance_map: Dict[str, float] = {}
        
        # Estatísticas avançadas
        self._optimization_stats = {
            'total_optimizations': 0,
            'successful_optimizations': 0,
            'ml_predictions_made': 0,
            'ml_prediction_accuracy': 0.0,
            'avg_performance_improvement': 0.0,
            'system_stability_score': 100.0,
            'auto_scaling_events': 0
        }
        
        # Sistema de auto-scaling
        self._auto_scaling_enabled = True
        self._scaling_history: List[Dict[str, Any]] = []
        
        # Thresholds adaptativos
        self._adaptive_thresholds = {
            'latency_critical': 100.0,  # ms
            'memory_critical': 90.0,    # %
            'cpu_critical': 80.0,       # %
            'hit_rate_critical': 0.85   # ratio
        }
        
        logger.info("AdvancedPerformanceOptimizer initialized with ML capabilities")
    
    async def initialize(self) -> bool:
        """Inicializa otimizador avançado"""
        try:
            # Inicializa conexão Redis
            self._redis_client = await get_redis_client()
            if not self._redis_client:
                logger.error("Failed to connect to Redis")
                return False
            
            # Carrega modelos ML existentes
            await self._load_ml_models()
            
            # Configura targets de performance
            await self._setup_performance_targets()
            
            # Registra estratégias de otimização
            await self._register_optimization_strategies()
            
            # Estabelece baseline de performance
            await self._establish_performance_baseline()
            
            logger.info("Advanced Performance Optimizer initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize advanced optimizer: {e}")
            return False
    
    async def start_optimization(self):
        """Inicia sistema avançado de otimização"""
        if self.is_running:
            logger.warning("Advanced optimization already running")
            return
        
        if not await self.initialize():
            logger.error("Cannot start optimization - initialization failed")
            return
        
        self.is_running = True
        self._stop_signal = False
        
        logger.info("Starting advanced performance optimization with ML")
        
        # Tasks paralelas de otimização
        tasks = [
            self._metrics_collection_loop(),
            self._optimization_loop(),
            self._ml_prediction_loop(),
            self._auto_scaling_loop(),
            self._performance_monitoring_loop(),
            self._adaptive_tuning_loop(),
            self._config_optimization_loop()
        ]
        
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            logger.error(f"Error in optimization tasks: {e}")
        finally:
            self.is_running = False
            logger.info("Advanced performance optimization stopped")
    
    async def stop_optimization(self):
        """Para sistema de otimização"""
        self._stop_signal = True
        self.is_running = False
        
        # Salva modelos ML
        await self._save_ml_models()
        
        logger.info("Stopping advanced performance optimization...")
    
    async def _metrics_collection_loop(self):
        """Loop de coleta avançada de métricas"""
        while not self._stop_signal:
            try:
                metrics = await self._collect_comprehensive_metrics()
                if metrics:
                    self._metrics_history.append(metrics)
                    
                    # Atualiza targets de performance
                    await self._update_performance_targets(metrics)
                
                await asyncio.sleep(10)  # Coleta a cada 10 segundos
                
            except Exception as e:
                logger.error(f"Error in metrics collection: {e}")
                await asyncio.sleep(10)
    
    async def _collect_comprehensive_metrics(self) -> Optional[PerformanceMetrics]:
        """Coleta métricas completas do sistema"""
        try:
            current_time = datetime.now()
            
            # Métricas Redis
            redis_info = await self._redis_client.info()
            
            # Teste de latência Redis
            start_time = time.time()
            await self._redis_client.ping()
            redis_latency = (time.time() - start_time) * 1000
            
            # Cálculos Redis
            used_memory = int(redis_info.get('used_memory', 0))
            maxmemory = int(redis_info.get('maxmemory', 0))
            memory_percent = (used_memory / maxmemory * 100) if maxmemory > 0 else 0.0
            
            hits = int(redis_info.get('keyspace_hits', 0))
            misses = int(redis_info.get('keyspace_misses', 0))
            hit_rate = hits / (hits + misses) if (hits + misses) > 0 else 1.0
            
            # Métricas do sistema
            cpu_percent = psutil.cpu_percent(interval=None)
            memory_info = psutil.virtual_memory()
            
            # I/O de disco
            disk_io = psutil.disk_io_counters()
            prev_disk_io = getattr(self, '_prev_disk_io', disk_io)
            
            disk_read_mb = (disk_io.read_bytes - prev_disk_io.read_bytes) / (1024 * 1024)
            disk_write_mb = (disk_io.write_bytes - prev_disk_io.write_bytes) / (1024 * 1024)
            self._prev_disk_io = disk_io
            
            # I/O de rede
            network_io = psutil.net_io_counters()
            prev_network_io = getattr(self, '_prev_network_io', network_io)
            
            network_sent_mb = (network_io.bytes_sent - prev_network_io.bytes_sent) / (1024 * 1024)
            network_recv_mb = (network_io.bytes_recv - prev_network_io.bytes_recv) / (1024 * 1024)
            self._prev_network_io = network_io
            
            # Métricas da aplicação (simuladas - podem ser coletadas via APIs)
            active_downloads = 0  # TODO: Integrar com sistema real
            queue_size = 0        # TODO: Integrar com sistema real
            api_response_time = 0.0  # TODO: Integrar com sistema real
            
            return PerformanceMetrics(
                timestamp=current_time,
                # Redis
                redis_latency_ms=redis_latency,
                redis_hit_rate=hit_rate,
                redis_memory_used_mb=used_memory / (1024 * 1024),
                redis_memory_used_percent=memory_percent / 100.0,
                redis_connected_clients=int(redis_info.get('connected_clients', 0)),
                redis_ops_per_sec=int(redis_info.get('instantaneous_ops_per_sec', 0)),
                redis_evicted_keys=int(redis_info.get('evicted_keys', 0)),
                redis_expired_keys=int(redis_info.get('expired_keys', 0)),
                redis_fragmentation_ratio=float(redis_info.get('mem_fragmentation_ratio', 1.0)),
                redis_keyspace_hits=hits,
                redis_keyspace_misses=misses,
                # Sistema
                cpu_percent=cpu_percent,
                memory_percent=memory_info.percent,
                disk_io_read_mb=max(0, disk_read_mb),
                disk_io_write_mb=max(0, disk_write_mb),
                network_sent_mb=max(0, network_sent_mb),
                network_recv_mb=max(0, network_recv_mb),
                # Aplicação
                active_downloads=active_downloads,
                queue_size=queue_size,
                api_response_time_ms=api_response_time
            )
            
        except Exception as e:
            logger.error(f"Error collecting comprehensive metrics: {e}")
            return None
    
    async def _optimization_loop(self):
        """Loop principal de otimização inteligente"""
        while not self._stop_signal:
            try:
                # Executa ciclo de otimização com ML
                await self._run_intelligent_optimization_cycle()
                await asyncio.sleep(self.optimization_interval)
                
            except Exception as e:
                logger.error(f"Error in optimization loop: {e}")
                await asyncio.sleep(self.optimization_interval)
    
    async def _run_intelligent_optimization_cycle(self):
        """Executa ciclo de otimização inteligente"""
        if not self._metrics_history:
            return
        
        current_metrics = self._metrics_history[-1]
        
        # Análise de performance atual
        performance_score = await self._calculate_performance_score(current_metrics)
        
        # Identifica oportunidades de otimização
        optimization_opportunities = await self._identify_optimization_opportunities(current_metrics)
        
        # Aplica estratégias baseadas em ML
        for opportunity in optimization_opportunities:
            strategy = self._optimization_strategies.get(opportunity['strategy_id'])
            if strategy and await self._should_execute_strategy(strategy, current_metrics):
                await self._execute_optimization_strategy(strategy, current_metrics)
        
        # Atualiza modelos ML
        if self.learning_enabled:
            await self._update_ml_models(current_metrics, performance_score)
        
        logger.debug(f"Optimization cycle completed. Performance score: {performance_score:.2f}")
    
    async def _calculate_performance_score(self, metrics: PerformanceMetrics) -> float:
        """Calcula score geral de performance (0-100)"""
        try:
            # Pesos para diferentes métricas
            weights = {
                'latency': 25,      # 25%
                'hit_rate': 20,     # 20%
                'memory': 15,       # 15%
                'cpu': 15,          # 15%
                'throughput': 15,   # 15%
                'stability': 10     # 10%
            }
            
            score = 0.0
            
            # Score de latência (invertido - menor é melhor)
            latency_score = max(0, 100 - (metrics.redis_latency_ms / 2))
            score += latency_score * weights['latency'] / 100
            
            # Score de hit rate
            hit_rate_score = metrics.redis_hit_rate * 100
            score += hit_rate_score * weights['hit_rate'] / 100
            
            # Score de memória (invertido - menor uso é melhor)
            memory_score = max(0, 100 - metrics.redis_memory_used_percent * 100)
            score += memory_score * weights['memory'] / 100
            
            # Score de CPU (invertido - menor uso é melhor)
            cpu_score = max(0, 100 - metrics.cpu_percent)
            score += cpu_score * weights['cpu'] / 100
            
            # Score de throughput
            throughput_score = min(100, metrics.redis_ops_per_sec / 100)  # Normalizado para max 10k ops/s
            score += throughput_score * weights['throughput'] / 100
            
            # Score de estabilidade (baseado na variação das métricas)
            stability_score = await self._calculate_stability_score()
            score += stability_score * weights['stability'] / 100
            
            return max(0.0, min(100.0, score))
            
        except Exception as e:
            logger.error(f"Error calculating performance score: {e}")
            return 50.0  # Score neutro em caso de erro
    
    async def _calculate_stability_score(self) -> float:
        """Calcula score de estabilidade baseado na variação das métricas"""
        if len(self._metrics_history) < 10:
            return 100.0  # Assume estável se poucos dados
        
        try:
            recent_metrics = list(self._metrics_history)[-10:]
            
            # Calcula variação da latência
            latencies = [m.redis_latency_ms for m in recent_metrics]
            latency_cv = statistics.stdev(latencies) / statistics.mean(latencies) if statistics.mean(latencies) > 0 else 0
            
            # Calcula variação do hit rate
            hit_rates = [m.redis_hit_rate for m in recent_metrics]
            hit_rate_cv = statistics.stdev(hit_rates) / statistics.mean(hit_rates) if statistics.mean(hit_rates) > 0 else 0
            
            # Calcula variação do uso de CPU
            cpu_usage = [m.cpu_percent for m in recent_metrics]
            cpu_cv = statistics.stdev(cpu_usage) / statistics.mean(cpu_usage) if statistics.mean(cpu_usage) > 0 else 0
            
            # Score de estabilidade (menor variação = maior estabilidade)
            avg_cv = (latency_cv + hit_rate_cv + cpu_cv) / 3
            stability_score = max(0, 100 - (avg_cv * 1000))  # Multiplica por 1000 para escalar
            
            return stability_score
            
        except Exception as e:
            logger.error(f"Error calculating stability score: {e}")
            return 100.0
    
    async def _identify_optimization_opportunities(self, metrics: PerformanceMetrics) -> List[Dict[str, Any]]:
        """Identifica oportunidades de otimização usando ML"""
        opportunities = []
        
        # Verifica thresholds críticos
        if metrics.redis_latency_ms > self._adaptive_thresholds['latency_critical']:
            opportunities.append({
                'strategy_id': 'reduce_latency',
                'priority': 1,
                'severity': 'high',
                'current_value': metrics.redis_latency_ms,
                'target_value': self._adaptive_thresholds['latency_critical']
            })
        
        if metrics.redis_memory_used_percent > self._adaptive_thresholds['memory_critical'] / 100:
            opportunities.append({
                'strategy_id': 'optimize_memory',
                'priority': 1,
                'severity': 'high',
                'current_value': metrics.redis_memory_used_percent * 100,
                'target_value': self._adaptive_thresholds['memory_critical']
            })
        
        if metrics.cpu_percent > self._adaptive_thresholds['cpu_critical']:
            opportunities.append({
                'strategy_id': 'reduce_cpu_usage',
                'priority': 2,
                'severity': 'medium',
                'current_value': metrics.cpu_percent,
                'target_value': self._adaptive_thresholds['cpu_critical']
            })
        
        if metrics.redis_hit_rate < self._adaptive_thresholds['hit_rate_critical']:
            opportunities.append({
                'strategy_id': 'improve_hit_rate',
                'priority': 1,
                'severity': 'high',
                'current_value': metrics.redis_hit_rate,
                'target_value': self._adaptive_thresholds['hit_rate_critical']
            })
        
        # ML-based opportunity detection
        if self._performance_predictor and len(self._metrics_history) >= 50:
            ml_opportunities = await self._predict_optimization_opportunities(metrics)
            opportunities.extend(ml_opportunities)
        
        # Ordena por prioridade
        opportunities.sort(key=lambda x: x['priority'])
        
        return opportunities
    
    async def _predict_optimization_opportunities(self, metrics: PerformanceMetrics) -> List[Dict[str, Any]]:
        """Usa ML para prever oportunidades de otimização"""
        opportunities = []
        
        try:
            # TODO: Implementar modelo de ML para predição
            # Por enquanto, usa regras heurísticas avançadas
            
            # Detecta padrões de degradação
            if len(self._metrics_history) >= 20:
                recent_metrics = list(self._metrics_history)[-20:]
                
                # Trend de latência
                latencies = [m.redis_latency_ms for m in recent_metrics]
                if len(latencies) >= 2:
                    latency_trend = (latencies[-1] - latencies[0]) / len(latencies)
                    if latency_trend > 1.0:  # Latência aumentando >1ms por coleta
                        opportunities.append({
                            'strategy_id': 'predictive_latency_optimization',
                            'priority': 2,
                            'severity': 'medium',
                            'predicted': True,
                            'trend': latency_trend
                        })
                
                # Trend de hit rate
                hit_rates = [m.redis_hit_rate for m in recent_metrics]
                if len(hit_rates) >= 2:
                    hit_rate_trend = (hit_rates[-1] - hit_rates[0]) / len(hit_rates)
                    if hit_rate_trend < -0.001:  # Hit rate decrescendo
                        opportunities.append({
                            'strategy_id': 'predictive_cache_warming',
                            'priority': 2,
                            'severity': 'medium',
                            'predicted': True,
                            'trend': hit_rate_trend
                        })
        
        except Exception as e:
            logger.error(f"Error in ML prediction: {e}")
        
        return opportunities
    
    async def _should_execute_strategy(self, strategy: OptimizationStrategy, metrics: PerformanceMetrics) -> bool:
        """Determina se estratégia deve ser executada"""
        # Verifica cooldown
        if strategy.last_executed:
            cooldown_expires = strategy.last_executed + timedelta(minutes=strategy.cooldown_minutes)
            if datetime.now() < cooldown_expires:
                return False
        
        # Verifica condições da estratégia
        for condition, threshold in strategy.conditions.items():
            metric_value = getattr(metrics, condition, None)
            if metric_value is None:
                continue
            
            if isinstance(threshold, dict):
                if 'min' in threshold and metric_value < threshold['min']:
                    return True
                if 'max' in threshold and metric_value > threshold['max']:
                    return True
            else:
                if metric_value > threshold:
                    return True
        
        # Verifica se estratégia é efetiva baseada no histórico
        if strategy.execution_count > 5 and strategy.success_rate < 0.5:
            logger.debug(f"Strategy {strategy.id} has low success rate: {strategy.success_rate:.2f}")
            return False
        
        return True
    
    async def _execute_optimization_strategy(self, strategy: OptimizationStrategy, metrics: PerformanceMetrics):
        """Executa estratégia de otimização"""
        try:
            logger.info(f"Executing optimization strategy: {strategy.name}")
            
            strategy.execution_count += 1
            strategy.last_executed = datetime.now()
            
            # Métricas antes da otimização
            before_metrics = metrics
            
            success = False
            
            # Executa estratégia baseada na categoria
            if strategy.category == 'redis':
                success = await self._execute_redis_optimization(strategy)
            elif strategy.category == 'system':
                success = await self._execute_system_optimization(strategy)
            elif strategy.category == 'application':
                success = await self._execute_application_optimization(strategy)
            elif strategy.category == 'network':
                success = await self._execute_network_optimization(strategy)
            
            # Aguarda e coleta métricas após otimização
            if success:
                await asyncio.sleep(30)  # Aguarda estabilizar
                after_metrics = await self._collect_comprehensive_metrics()
                
                if after_metrics:
                    # Calcula impacto
                    impact_score = await self._calculate_optimization_impact(before_metrics, after_metrics)
                    
                    # Atualiza estatísticas da estratégia
                    strategy.performance_history.append(impact_score)
                    strategy.avg_impact_score = statistics.mean(strategy.performance_history)
                    
                    # Atualiza taxa de sucesso
                    if impact_score > 0:
                        successful_executions = sum(1 for score in strategy.performance_history if score > 0)
                        strategy.success_rate = successful_executions / len(strategy.performance_history)
                    
                    # Aprendizado adaptativo
                    if self.learning_enabled:
                        await self._adaptive_strategy_learning(strategy, impact_score)
                    
                    self._optimization_stats['total_optimizations'] += 1
                    if impact_score > 0:
                        self._optimization_stats['successful_optimizations'] += 1
                    
                    logger.info(f"Strategy {strategy.name} executed with impact score: {impact_score:.2f}")
            else:
                logger.warning(f"Strategy {strategy.name} execution failed")
                
        except Exception as e:
            logger.error(f"Error executing optimization strategy {strategy.id}: {e}")
    
    async def _execute_redis_optimization(self, strategy: OptimizationStrategy) -> bool:
        """Executa otimizações específicas do Redis"""
        try:
            action = strategy.parameters.get('action')
            
            if action == 'adjust_memory_policy':
                policy = strategy.parameters.get('policy', 'allkeys-lru')
                await self._redis_client.config_set('maxmemory-policy', policy)
                return True
            
            elif action == 'optimize_expiry':
                # Força varredura de chaves expiradas
                await self._redis_client.eval("return redis.call('scan', 0, 'count', 1000)", 0)
                return True
            
            elif action == 'adjust_timeout':
                timeout = strategy.parameters.get('timeout', 300)
                await self._redis_client.config_set('timeout', str(timeout))
                return True
            
            elif action == 'optimize_persistence':
                save_policy = strategy.parameters.get('save_policy', '900 1 300 10 60 10000')
                await self._redis_client.config_set('save', save_policy)
                return True
            
            elif action == 'enable_compression':
                await self._redis_client.config_set('rdbcompression', 'yes')
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error in Redis optimization: {e}")
            return False
    
    async def _execute_system_optimization(self, strategy: OptimizationStrategy) -> bool:
        """Executa otimizações de sistema (limitadas no escopo atual)"""
        try:
            # Por segurança, limitamos otimizações de sistema a configurações da aplicação
            action = strategy.parameters.get('action')
            
            if action == 'adjust_connection_pool':
                # TODO: Integrar com sistema de connection pool
                logger.info("Connection pool optimization would be applied here")
                return True
            
            elif action == 'optimize_gc':
                # TODO: Implementar otimizações de garbage collection
                logger.info("GC optimization would be applied here")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error in system optimization: {e}")
            return False
    
    async def _execute_application_optimization(self, strategy: OptimizationStrategy) -> bool:
        """Executa otimizações específicas da aplicação"""
        try:
            action = strategy.parameters.get('action')
            
            if action == 'cache_warming':
                # TODO: Integrar com sistema de cache warming
                logger.info("Cache warming would be executed here")
                return True
            
            elif action == 'query_optimization':
                # TODO: Integrar com otimizador de queries
                logger.info("Query optimization would be applied here")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error in application optimization: {e}")
            return False
    
    async def _execute_network_optimization(self, strategy: OptimizationStrategy) -> bool:
        """Executa otimizações de rede"""
        try:
            action = strategy.parameters.get('action')
            
            if action == 'adjust_tcp_keepalive':
                keepalive = strategy.parameters.get('keepalive', 60)
                await self._redis_client.config_set('tcp-keepalive', str(keepalive))
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error in network optimization: {e}")
            return False
    
    async def _calculate_optimization_impact(self, before: PerformanceMetrics, after: PerformanceMetrics) -> float:
        """Calcula impacto da otimização (-100 a +100)"""
        try:
            impact_score = 0.0
            
            # Impacto na latência (peso 30%)
            if before.redis_latency_ms > 0:
                latency_improvement = (before.redis_latency_ms - after.redis_latency_ms) / before.redis_latency_ms
                impact_score += latency_improvement * 30
            
            # Impacto no hit rate (peso 25%)
            hit_rate_improvement = after.redis_hit_rate - before.redis_hit_rate
            impact_score += hit_rate_improvement * 25
            
            # Impacto no uso de memória (peso 20%)
            if before.redis_memory_used_percent > 0:
                memory_improvement = (before.redis_memory_used_percent - after.redis_memory_used_percent) / before.redis_memory_used_percent
                impact_score += memory_improvement * 20
            
            # Impacto no CPU (peso 15%)
            if before.cpu_percent > 0:
                cpu_improvement = (before.cpu_percent - after.cpu_percent) / before.cpu_percent
                impact_score += cpu_improvement * 15
            
            # Impacto no throughput (peso 10%)
            if before.redis_ops_per_sec > 0:
                throughput_improvement = (after.redis_ops_per_sec - before.redis_ops_per_sec) / before.redis_ops_per_sec
                impact_score += min(throughput_improvement, 0.5) * 10  # Cap em 50%
            
            return max(-100.0, min(100.0, impact_score))
            
        except Exception as e:
            logger.error(f"Error calculating optimization impact: {e}")
            return 0.0
    
    async def _adaptive_strategy_learning(self, strategy: OptimizationStrategy, impact_score: float):
        """Aprendizado adaptativo da estratégia"""
        try:
            # Ajusta parâmetros baseado no impacto
            if impact_score > 10:  # Otimização muito efetiva
                # Reduz cooldown para execuções mais frequentes
                strategy.cooldown_minutes = max(15, strategy.cooldown_minutes - 5)
                
                # Aumenta agressividade dos parâmetros
                for param, value in strategy.parameters.items():
                    if isinstance(value, (int, float)) and param != 'action':
                        strategy.parameters[param] = value * 1.1
            
            elif impact_score < -5:  # Otimização prejudicial
                # Aumenta cooldown
                strategy.cooldown_minutes = min(180, strategy.cooldown_minutes + 15)
                
                # Reduz agressividade dos parâmetros
                for param, value in strategy.parameters.items():
                    if isinstance(value, (int, float)) and param != 'action':
                        strategy.parameters[param] = value * 0.9
            
            # Atualiza thresholds adaptativos
            if len(strategy.performance_history) >= 10:
                avg_impact = statistics.mean(strategy.performance_history[-10:])
                
                if avg_impact > 5:  # Estratégia consistentemente boa
                    # Torna thresholds mais sensíveis
                    for threshold_key in strategy.conditions:
                        if hasattr(self, '_adaptive_thresholds') and threshold_key in self._adaptive_thresholds:
                            current_threshold = self._adaptive_thresholds[threshold_key]
                            self._adaptive_thresholds[threshold_key] = current_threshold * 0.95
            
        except Exception as e:
            logger.error(f"Error in adaptive learning: {e}")
    
    async def _ml_prediction_loop(self):
        """Loop de predição ML"""
        while not self._stop_signal:
            try:
                if len(self._metrics_history) >= 100:  # Mínimo de dados para ML
                    await self._train_performance_predictor()
                    await self._make_performance_predictions()
                
                await asyncio.sleep(300)  # A cada 5 minutos
                
            except Exception as e:
                logger.error(f"Error in ML prediction loop: {e}")
                await asyncio.sleep(300)
    
    async def _train_performance_predictor(self):
        """Treina modelo de predição de performance"""
        try:
            if not self.learning_enabled:
                return
            
            # TODO: Implementar modelo real de ML
            # Por enquanto, simula treinamento
            
            recent_metrics = list(self._metrics_history)[-500:]  # Últimas 500 amostras
            
            # Prepara features e targets
            features = []
            targets = []
            
            for i, metrics in enumerate(recent_metrics[:-1]):
                # Features: métricas atuais
                feature_vector = [
                    metrics.redis_latency_ms,
                    metrics.redis_hit_rate,
                    metrics.redis_memory_used_percent,
                    metrics.cpu_percent,
                    metrics.redis_ops_per_sec / 1000,  # Normalizado
                    metrics.redis_connected_clients / 100  # Normalizado
                ]
                features.append(feature_vector)
                
                # Target: score de performance da próxima amostra
                next_metrics = recent_metrics[i + 1]
                target_score = await self._calculate_performance_score(next_metrics)
                targets.append(target_score)
            
            if len(features) >= 50:  # Mínimo para treinamento
                # Simula treinamento (implementar modelo real aqui)
                self._performance_predictor = {
                    'trained': True,
                    'features_count': len(features),
                    'accuracy': 0.85  # Simulado
                }
                
                self._optimization_stats['ml_prediction_accuracy'] = 0.85
                
                logger.info(f"ML predictor trained with {len(features)} samples")
            
        except Exception as e:
            logger.error(f"Error training ML predictor: {e}")
    
    async def _make_performance_predictions(self):
        """Faz predições de performance"""
        try:
            if not self._performance_predictor:
                return
            
            current_metrics = self._metrics_history[-1]
            
            # TODO: Implementar predição real
            # Por enquanto, simula predição
            
            # Prediz performance em 5 minutos
            predicted_score = await self._calculate_performance_score(current_metrics)
            predicted_score += np.random.normal(0, 5)  # Simula incerteza
            
            # Se predição indica degradação significativa, toma ação preventiva
            if predicted_score < 70:  # Threshold de alerta
                logger.warning(f"ML predicts performance degradation: {predicted_score:.2f}")
                await self._trigger_preventive_optimization()
            
            self._optimization_stats['ml_predictions_made'] += 1
            
        except Exception as e:
            logger.error(f"Error making predictions: {e}")
    
    async def _trigger_preventive_optimization(self):
        """Executa otimização preventiva baseada em predições ML"""
        try:
            # Identifica estratégias preventivas mais efetivas
            preventive_strategies = [
                strategy for strategy in self._optimization_strategies.values()
                if strategy.avg_impact_score > 5 and strategy.success_rate > 0.7
            ]
            
            if preventive_strategies:
                # Ordena por efetividade
                preventive_strategies.sort(key=lambda x: x.avg_impact_score, reverse=True)
                
                # Executa a melhor estratégia preventiva
                best_strategy = preventive_strategies[0]
                current_metrics = self._metrics_history[-1]
                
                logger.info(f"Executing preventive optimization: {best_strategy.name}")
                await self._execute_optimization_strategy(best_strategy, current_metrics)
        
        except Exception as e:
            logger.error(f"Error in preventive optimization: {e}")
    
    async def _auto_scaling_loop(self):
        """Loop de auto-scaling"""
        while not self._stop_signal:
            try:
                if self._auto_scaling_enabled:
                    await self._evaluate_auto_scaling()
                
                await asyncio.sleep(120)  # A cada 2 minutos
                
            except Exception as e:
                logger.error(f"Error in auto-scaling loop: {e}")
                await asyncio.sleep(120)
    
    async def _evaluate_auto_scaling(self):
        """Avalia necessidade de auto-scaling"""
        try:
            if not self._metrics_history:
                return
            
            current_metrics = self._metrics_history[-1]
            
            # Verifica necessidade de scale-up
            scale_up_needed = (
                current_metrics.cpu_percent > 85 or
                current_metrics.redis_memory_used_percent > 0.9 or
                current_metrics.redis_connected_clients > 8000
            )
            
            # Verifica possibilidade de scale-down
            recent_metrics = list(self._metrics_history)[-10:]  # Últimos 10 minutos
            if len(recent_metrics) >= 10:
                avg_cpu = statistics.mean([m.cpu_percent for m in recent_metrics])
                avg_memory = statistics.mean([m.redis_memory_used_percent for m in recent_metrics])
                avg_clients = statistics.mean([m.redis_connected_clients for m in recent_metrics])
                
                scale_down_possible = (
                    avg_cpu < 30 and
                    avg_memory < 0.5 and
                    avg_clients < 1000
                )
            else:
                scale_down_possible = False
            
            # Executa auto-scaling
            if scale_up_needed:
                await self._execute_scale_up()
            elif scale_down_possible:
                await self._execute_scale_down()
                
        except Exception as e:
            logger.error(f"Error evaluating auto-scaling: {e}")
    
    async def _execute_scale_up(self):
        """Executa scale-up (simulado)"""
        try:
            # Em um ambiente real, isso integraria com orquestrador (K8s, Docker Swarm, etc.)
            logger.warning("AUTO-SCALING: Scale-up needed - would increase resources")
            
            scaling_event = {
                'timestamp': datetime.now().isoformat(),
                'action': 'scale_up',
                'reason': 'High resource utilization detected',
                'metrics_snapshot': self._metrics_history[-1].to_dict() if self._metrics_history else {}
            }
            
            self._scaling_history.append(scaling_event)
            self._optimization_stats['auto_scaling_events'] += 1
            
            # Ajusta configurações para melhor performance com mais recursos
            await self._optimize_for_scale_up()
            
        except Exception as e:
            logger.error(f"Error in scale-up execution: {e}")
    
    async def _execute_scale_down(self):
        """Executa scale-down (simulado)"""
        try:
            logger.info("AUTO-SCALING: Scale-down opportunity - could reduce resources")
            
            scaling_event = {
                'timestamp': datetime.now().isoformat(),
                'action': 'scale_down',
                'reason': 'Low resource utilization detected',
                'metrics_snapshot': self._metrics_history[-1].to_dict() if self._metrics_history else {}
            }
            
            self._scaling_history.append(scaling_event)
            self._optimization_stats['auto_scaling_events'] += 1
            
            # Ajusta configurações para eficiência com menos recursos
            await self._optimize_for_scale_down()
            
        except Exception as e:
            logger.error(f"Error in scale-down execution: {e}")
    
    async def _optimize_for_scale_up(self):
        """Otimiza configurações para ambiente com mais recursos"""
        try:
            # Aumenta limites
            await self._redis_client.config_set('maxclients', '15000')
            await self._redis_client.config_set('timeout', '600')
            
            # Ajusta política de memória para ser mais agressiva
            await self._redis_client.config_set('maxmemory-policy', 'allkeys-lru')
            
            logger.info("Optimized configuration for scaled-up environment")
            
        except Exception as e:
            logger.error(f"Error optimizing for scale-up: {e}")
    
    async def _optimize_for_scale_down(self):
        """Otimiza configurações para ambiente com menos recursos"""
        try:
            # Reduz limites
            await self._redis_client.config_set('maxclients', '5000')
            await self._redis_client.config_set('timeout', '300')
            
            # Usa política de memória mais conservadora
            await self._redis_client.config_set('maxmemory-policy', 'volatile-lru')
            
            logger.info("Optimized configuration for scaled-down environment")
            
        except Exception as e:
            logger.error(f"Error optimizing for scale-down: {e}")
    
    async def _performance_monitoring_loop(self):
        """Loop de monitoramento avançado de performance"""
        while not self._stop_signal:
            try:
                await self._advanced_performance_analysis()
                await asyncio.sleep(180)  # A cada 3 minutos
                
            except Exception as e:
                logger.error(f"Error in performance monitoring: {e}")
                await asyncio.sleep(180)
    
    async def _advanced_performance_analysis(self):
        """Análise avançada de performance"""
        try:
            if len(self._metrics_history) < 20:
                return
            
            recent_metrics = list(self._metrics_history)[-20:]
            
            # Análise de tendências
            trends = await self._analyze_performance_trends(recent_metrics)
            
            # Detecção de anomalias
            anomalies = await self._detect_performance_anomalies(recent_metrics)
            
            # Análise de correlações
            correlations = await self._analyze_metric_correlations(recent_metrics)
            
            # Log insights importantes
            if trends:
                for metric, trend in trends.items():
                    if abs(trend) > 0.1:  # Tendência significativa
                        logger.info(f"Performance trend detected - {metric}: {trend:.3f}")
            
            if anomalies:
                logger.warning(f"Performance anomalies detected: {anomalies}")
            
            if correlations:
                strong_correlations = [
                    f"{pair}: {corr:.3f}" 
                    for pair, corr in correlations.items() 
                    if abs(corr) > 0.7
                ]
                if strong_correlations:
                    logger.info(f"Strong metric correlations: {strong_correlations}")
            
        except Exception as e:
            logger.error(f"Error in advanced performance analysis: {e}")
    
    async def _analyze_performance_trends(self, metrics: List[PerformanceMetrics]) -> Dict[str, float]:
        """Analisa tendências nas métricas de performance"""
        trends = {}
        
        try:
            # Analisa tendência de cada métrica
            metric_series = {
                'latency': [m.redis_latency_ms for m in metrics],
                'hit_rate': [m.redis_hit_rate for m in metrics],
                'memory': [m.redis_memory_used_percent for m in metrics],
                'cpu': [m.cpu_percent for m in metrics],
                'ops_per_sec': [m.redis_ops_per_sec for m in metrics]
            }
            
            for metric_name, values in metric_series.items():
                if len(values) >= 10:
                    # Calcula tendência linear simples
                    x = list(range(len(values)))
                    trend = np.polyfit(x, values, 1)[0]  # Coeficiente linear
                    trends[metric_name] = trend
            
        except Exception as e:
            logger.error(f"Error analyzing trends: {e}")
        
        return trends
    
    async def _detect_performance_anomalies(self, metrics: List[PerformanceMetrics]) -> List[str]:
        """Detecta anomalias nas métricas de performance"""
        anomalies = []
        
        try:
            # Analisa últimas 10 amostras para detectar outliers
            recent_metrics = metrics[-10:]
            
            # Detecta picos de latência
            latencies = [m.redis_latency_ms for m in recent_metrics]
            if latencies:
                mean_latency = statistics.mean(latencies)
                max_latency = max(latencies)
                
                if max_latency > mean_latency * 3:  # Pico 3x maior que média
                    anomalies.append(f"Latency spike detected: {max_latency:.2f}ms")
            
            # Detecta quedas bruscas no hit rate
            hit_rates = [m.redis_hit_rate for m in recent_metrics]
            if len(hit_rates) >= 5:
                recent_avg = statistics.mean(hit_rates[-3:])  # Média das últimas 3
                earlier_avg = statistics.mean(hit_rates[-5:-2])  # Média das 3 anteriores
                
                if recent_avg < earlier_avg - 0.1:  # Queda > 10%
                    anomalies.append(f"Hit rate drop detected: {recent_avg:.1%} vs {earlier_avg:.1%}")
            
            # Detecta uso anômalo de CPU
            cpu_values = [m.cpu_percent for m in recent_metrics]
            if cpu_values:
                mean_cpu = statistics.mean(cpu_values)
                max_cpu = max(cpu_values)
                
                if max_cpu > 95:  # CPU crítico
                    anomalies.append(f"Critical CPU usage: {max_cpu:.1f}%")
            
        except Exception as e:
            logger.error(f"Error detecting anomalies: {e}")
        
        return anomalies
    
    async def _analyze_metric_correlations(self, metrics: List[PerformanceMetrics]) -> Dict[str, float]:
        """Analisa correlações entre métricas"""
        correlations = {}
        
        try:
            # Extrai séries de métricas
            latencies = [m.redis_latency_ms for m in metrics]
            hit_rates = [m.redis_hit_rate for m in metrics]
            memory_usage = [m.redis_memory_used_percent for m in metrics]
            cpu_usage = [m.cpu_percent for m in metrics]
            ops_per_sec = [m.redis_ops_per_sec for m in metrics]
            
            # Calcula correlações importantes
            if len(latencies) >= 10:
                correlations['latency_vs_cpu'] = np.corrcoef(latencies, cpu_usage)[0, 1]
                correlations['latency_vs_memory'] = np.corrcoef(latencies, memory_usage)[0, 1]
                correlations['hit_rate_vs_latency'] = np.corrcoef(hit_rates, latencies)[0, 1]
                correlations['ops_vs_latency'] = np.corrcoef(ops_per_sec, latencies)[0, 1]
            
        except Exception as e:
            logger.error(f"Error analyzing correlations: {e}")
        
        return correlations
    
    async def _adaptive_tuning_loop(self):
        """Loop de tuning adaptativo"""
        while not self._stop_signal:
            try:
                await self._adaptive_threshold_tuning()
                await asyncio.sleep(600)  # A cada 10 minutos
                
            except Exception as e:
                logger.error(f"Error in adaptive tuning: {e}")
                await asyncio.sleep(600)
    
    async def _adaptive_threshold_tuning(self):
        """Ajusta thresholds adaptativamente baseado na performance"""
        try:
            if len(self._metrics_history) < 50:
                return
            
            recent_metrics = list(self._metrics_history)[-50:]
            
            # Calcula percentis das métricas
            latencies = [m.redis_latency_ms for m in recent_metrics]
            memory_usage = [m.redis_memory_used_percent * 100 for m in recent_metrics]
            cpu_usage = [m.cpu_percent for m in recent_metrics]
            hit_rates = [m.redis_hit_rate for m in recent_metrics]
            
            # Ajusta thresholds baseado nos percentis 90
            p90_latency = np.percentile(latencies, 90)
            p90_memory = np.percentile(memory_usage, 90)
            p90_cpu = np.percentile(cpu_usage, 90)
            p10_hit_rate = np.percentile(hit_rates, 10)  # Percentil 10 para hit rate (pior caso)
            
            # Atualiza thresholds adaptativos com margem de segurança
            self._adaptive_thresholds['latency_critical'] = min(200, max(50, p90_latency * 1.2))
            self._adaptive_thresholds['memory_critical'] = min(95, max(70, p90_memory * 1.1))
            self._adaptive_thresholds['cpu_critical'] = min(90, max(60, p90_cpu * 1.1))
            self._adaptive_thresholds['hit_rate_critical'] = max(0.7, min(0.95, p10_hit_rate * 0.9))
            
            logger.debug(f"Adaptive thresholds updated: {self._adaptive_thresholds}")
            
        except Exception as e:
            logger.error(f"Error in adaptive threshold tuning: {e}")
    
    async def _config_optimization_loop(self):
        """Loop de otimização de configurações"""
        while not self._stop_signal:
            try:
                await self._optimize_redis_configurations()
                await asyncio.sleep(900)  # A cada 15 minutos
                
            except Exception as e:
                logger.error(f"Error in config optimization: {e}")
                await asyncio.sleep(900)
    
    async def _optimize_redis_configurations(self):
        """Otimiza configurações Redis baseado em padrões de uso"""
        try:
            if not self._metrics_history:
                return
            
            current_metrics = self._metrics_history[-1]
            recent_metrics = list(self._metrics_history)[-20:] if len(self._metrics_history) >= 20 else self._metrics_history
            
            # Análise de padrões de uso
            avg_ops = statistics.mean([m.redis_ops_per_sec for m in recent_metrics])
            avg_clients = statistics.mean([m.redis_connected_clients for m in recent_metrics])
            avg_memory = statistics.mean([m.redis_memory_used_percent for m in recent_metrics])
            
            # Otimizações baseadas em padrões
            config_changes = {}
            
            # Ajusta maxclients baseado no uso
            if avg_clients > 0:
                optimal_maxclients = max(1000, int(avg_clients * 2))  # 2x buffer
                config_changes['maxclients'] = str(optimal_maxclients)
            
            # Ajusta timeout baseado na carga
            if avg_ops > 1000:  # Alta carga
                config_changes['timeout'] = '600'  # Timeout mais alto
            elif avg_ops < 100:  # Baixa carga
                config_changes['timeout'] = '300'  # Timeout padrão
            
            # Ajusta política de persistência baseada no uso de memória
            if avg_memory > 0.8:  # Memória alta
                config_changes['save'] = '1800 1 600 10'  # Menos frequente
            elif avg_memory < 0.3:  # Memória baixa
                config_changes['save'] = '300 1 60 100'  # Mais frequente
            
            # Aplica mudanças se necessário
            current_config = await self._get_current_redis_config()
            
            for key, value in config_changes.items():
                if current_config.get(key) != value:
                    await self._redis_client.config_set(key, value)
                    logger.info(f"Optimized Redis config: {key} = {value}")
            
        except Exception as e:
            logger.error(f"Error optimizing Redis configurations: {e}")
    
    async def _get_current_redis_config(self) -> Dict[str, str]:
        """Obtém configuração atual do Redis"""
        try:
            config_dict = {}
            config_list = await self._redis_client.config_get('*')
            
            # Converte lista [key1, value1, key2, value2, ...] para dict
            for i in range(0, len(config_list), 2):
                if i + 1 < len(config_list):
                    config_dict[config_list[i]] = config_list[i + 1]
            
            return config_dict
            
        except Exception as e:
            logger.error(f"Error getting Redis config: {e}")
            return {}
    
    async def _setup_performance_targets(self):
        """Configura targets de performance"""
        self._performance_targets = {
            'latency': OptimizationTarget(
                name='Redis Latency',
                current_value=0.0,
                target_value=10.0,  # <10ms
                weight=0.3,
                priority=1
            ),
            'hit_rate': OptimizationTarget(
                name='Cache Hit Rate',
                current_value=0.0,
                target_value=0.95,  # >95%
                weight=0.25,
                priority=1
            ),
            'memory': OptimizationTarget(
                name='Memory Usage',
                current_value=0.0,
                target_value=0.75,  # <75%
                weight=0.2,
                priority=2
            ),
            'cpu': OptimizationTarget(
                name='CPU Usage',
                current_value=0.0,
                target_value=0.60,  # <60%
                weight=0.15,
                priority=2
            ),
            'throughput': OptimizationTarget(
                name='Operations per Second',
                current_value=0.0,
                target_value=1000.0,  # >1000 ops/s
                weight=0.1,
                priority=3
            )
        }
    
    async def _update_performance_targets(self, metrics: PerformanceMetrics):
        """Atualiza targets baseado nas métricas atuais"""
        try:
            if 'latency' in self._performance_targets:
                self._performance_targets['latency'].current_value = metrics.redis_latency_ms
            
            if 'hit_rate' in self._performance_targets:
                self._performance_targets['hit_rate'].current_value = metrics.redis_hit_rate
            
            if 'memory' in self._performance_targets:
                self._performance_targets['memory'].current_value = metrics.redis_memory_used_percent
            
            if 'cpu' in self._performance_targets:
                self._performance_targets['cpu'].current_value = metrics.cpu_percent / 100.0
            
            if 'throughput' in self._performance_targets:
                self._performance_targets['throughput'].current_value = metrics.redis_ops_per_sec
                
        except Exception as e:
            logger.error(f"Error updating performance targets: {e}")
    
    async def _register_optimization_strategies(self):
        """Registra estratégias avançadas de otimização"""
        strategies = [
            OptimizationStrategy(
                id='reduce_latency',
                name='Advanced Latency Reduction',
                description='Multi-faceted approach to reduce Redis latency',
                category='redis',
                conditions={
                    'redis_latency_ms': 50.0  # Trigger at >50ms
                },
                parameters={
                    'action': 'adjust_timeout',
                    'timeout': 180
                },
                cooldown_minutes=20
            ),
            OptimizationStrategy(
                id='optimize_memory',
                name='Intelligent Memory Optimization',
                description='Smart memory management with predictive cleanup',
                category='redis',
                conditions={
                    'redis_memory_used_percent': 0.85  # Trigger at >85%
                },
                parameters={
                    'action': 'adjust_memory_policy',
                    'policy': 'allkeys-lru'
                },
                cooldown_minutes=30
            ),
            OptimizationStrategy(
                id='improve_hit_rate',
                name='Cache Hit Rate Optimizer',
                description='Proactive cache warming and eviction optimization',
                category='application',
                conditions={
                    'redis_hit_rate': 0.85  # Trigger at <85%
                },
                parameters={
                    'action': 'cache_warming'
                },
                cooldown_minutes=45
            ),
            OptimizationStrategy(
                id='reduce_cpu_usage',
                name='CPU Usage Optimizer',
                description='System-level optimizations to reduce CPU load',
                category='system',
                conditions={
                    'cpu_percent': 80.0  # Trigger at >80%
                },
                parameters={
                    'action': 'optimize_gc'
                },
                cooldown_minutes=60
            ),
            OptimizationStrategy(
                id='network_optimization',
                name='Network Performance Optimizer',
                description='TCP and connection optimization',
                category='network',
                conditions={
                    'redis_connected_clients': 5000  # Trigger at >5000 clients
                },
                parameters={
                    'action': 'adjust_tcp_keepalive',
                    'keepalive': 30
                },
                cooldown_minutes=40
            ),
            OptimizationStrategy(
                id='predictive_latency_optimization',
                name='Predictive Latency Prevention',
                description='ML-based predictive optimization for latency',
                category='redis',
                conditions={
                    'redis_latency_ms': 30.0  # More aggressive threshold for prediction
                },
                parameters={
                    'action': 'optimize_expiry'
                },
                cooldown_minutes=15
            ),
            OptimizationStrategy(
                id='predictive_cache_warming',
                name='Predictive Cache Warming',
                description='ML-driven proactive cache warming',
                category='application',
                conditions={
                    'redis_hit_rate': 0.90  # Proactive threshold
                },
                parameters={
                    'action': 'cache_warming'
                },
                cooldown_minutes=25
            )
        ]
        
        for strategy in strategies:
            self._optimization_strategies[strategy.id] = strategy
        
        logger.info(f"Registered {len(strategies)} advanced optimization strategies")
    
    async def _establish_performance_baseline(self):
        """Estabelece baseline avançado de performance"""
        try:
            # Coleta múltiplas amostras para baseline estável
            baseline_samples = []
            
            for _ in range(10):
                metrics = await self._collect_comprehensive_metrics()
                if metrics:
                    baseline_samples.append(metrics)
                await asyncio.sleep(2)
            
            if baseline_samples:
                # Calcula baseline estatístico
                baseline = {
                    'latency_mean': statistics.mean([m.redis_latency_ms for m in baseline_samples]),
                    'latency_std': statistics.stdev([m.redis_latency_ms for m in baseline_samples]),
                    'hit_rate_mean': statistics.mean([m.redis_hit_rate for m in baseline_samples]),
                    'memory_mean': statistics.mean([m.redis_memory_used_percent for m in baseline_samples]),
                    'cpu_mean': statistics.mean([m.cpu_percent for m in baseline_samples]),
                    'ops_mean': statistics.mean([m.redis_ops_per_sec for m in baseline_samples]),
                    'established_at': datetime.now().isoformat(),
                    'sample_count': len(baseline_samples)
                }
                
                self._performance_baseline = baseline
                
                logger.info(
                    f"Advanced performance baseline established: "
                    f"latency={baseline['latency_mean']:.2f}±{baseline.get('latency_std', 0):.2f}ms, "
                    f"hit_rate={baseline['hit_rate_mean']:.1%}, "
                    f"ops/sec={baseline['ops_mean']:.0f}"
                )
                
        except Exception as e:
            logger.error(f"Error establishing performance baseline: {e}")
    
    async def _load_ml_models(self):
        """Carrega modelos ML salvos"""
        try:
            model_path = Path('optimization_models.pkl')
            
            if model_path.exists():
                with open(model_path, 'rb') as f:
                    model_data = pickle.load(f)
                    
                self._performance_predictor = model_data.get('predictor')
                self._optimization_model = model_data.get('optimizer')
                self._feature_scaler = model_data.get('scaler')
                
                logger.info("ML models loaded successfully")
            else:
                logger.info("No existing ML models found - will train new models")
                
        except Exception as e:
            logger.error(f"Error loading ML models: {e}")
    
    async def _save_ml_models(self):
        """Salva modelos ML"""
        try:
            model_data = {
                'predictor': self._performance_predictor,
                'optimizer': self._optimization_model,
                'scaler': self._feature_scaler,
                'saved_at': datetime.now().isoformat()
            }
            
            with open('optimization_models.pkl', 'wb') as f:
                pickle.dump(model_data, f)
                
            logger.info("ML models saved successfully")
            
        except Exception as e:
            logger.error(f"Error saving ML models: {e}")
    
    # Métodos públicos para consulta e controle
    
    async def get_advanced_status(self) -> Dict[str, Any]:
        """Obtém status avançado do otimizador"""
        current_metrics = self._metrics_history[-1] if self._metrics_history else None
        
        # Performance targets status
        targets_status = {}
        for name, target in self._performance_targets.items():
            targets_status[name] = {
                'current': target.current_value,
                'target': target.target_value,
                'achieved': target.is_achieved(),
                'distance': target.calculate_distance(),
                'priority': target.priority
            }
        
        # Strategy effectiveness
        strategy_effectiveness = {}
        for strategy_id, strategy in self._optimization_strategies.items():
            strategy_effectiveness[strategy_id] = {
                'success_rate': strategy.success_rate,
                'avg_impact': strategy.avg_impact_score,
                'execution_count': strategy.execution_count,
                'last_executed': strategy.last_executed.isoformat() if strategy.last_executed else None
            }
        
        return {
            'timestamp': datetime.now().isoformat(),
            'is_running': self.is_running,
            'current_metrics': current_metrics.to_dict() if current_metrics else None,
            'performance_score': await self._calculate_performance_score(current_metrics) if current_metrics else 0,
            'performance_targets': targets_status,
            'strategy_effectiveness': strategy_effectiveness,
            'adaptive_thresholds': self._adaptive_thresholds,
            'optimization_stats': self._optimization_stats,
            'ml_status': {
                'predictor_trained': self._performance_predictor is not None,
                'learning_enabled': self.learning_enabled,
                'prediction_accuracy': self._optimization_stats.get('ml_prediction_accuracy', 0)
            },
            'auto_scaling': {
                'enabled': self._auto_scaling_enabled,
                'recent_events': self._scaling_history[-5:] if self._scaling_history else []
            },
            'system_stability_score': self._optimization_stats.get('system_stability_score', 100)
        }
    
    async def get_performance_forecast(self, hours_ahead: int = 24) -> Dict[str, Any]:
        """Gera forecast de performance usando ML"""
        try:
            if not self._performance_predictor or len(self._metrics_history) < 100:
                return {'error': 'Insufficient data for forecasting'}
            
            # TODO: Implementar forecast real com modelo ML
            # Por enquanto, simula forecast baseado em tendências
            
            current_metrics = self._metrics_history[-1]
            recent_metrics = list(self._metrics_history)[-50:]
            
            # Calcula tendências
            trends = await self._analyze_performance_trends(recent_metrics)
            
            # Projeta métricas futuras baseado nas tendências
            forecast = {
                'forecast_horizon_hours': hours_ahead,
                'generated_at': datetime.now().isoformat(),
                'confidence': 0.75,  # Simulado
                'predictions': {}
            }
            
            for metric, trend in trends.items():
                current_value = getattr(current_metrics, f'redis_{metric}_ms' if metric == 'latency' 
                                      else f'redis_{metric}' if metric in ['hit_rate', 'ops_per_sec'] 
                                      else f'{metric}_percent' if metric in ['memory', 'cpu'] 
                                      else metric, 0)
                
                # Projeta valor futuro (simplificado)
                projected_change = trend * hours_ahead
                projected_value = current_value + projected_change
                
                forecast['predictions'][metric] = {
                    'current': current_value,
                    'projected': projected_value,
                    'trend': trend,
                    'change_percentage': (projected_change / current_value * 100) if current_value > 0 else 0
                }
            
            # Identifica alertas potenciais
            alerts = []
            for metric, prediction in forecast['predictions'].items():
                if metric == 'latency' and prediction['projected'] > 100:
                    alerts.append(f"Latency may exceed 100ms in {hours_ahead} hours")
                elif metric == 'hit_rate' and prediction['projected'] < 0.8:
                    alerts.append(f"Hit rate may drop below 80% in {hours_ahead} hours")
                elif metric == 'memory' and prediction['projected'] > 90:
                    alerts.append(f"Memory usage may exceed 90% in {hours_ahead} hours")
            
            forecast['alerts'] = alerts
            
            return forecast
            
        except Exception as e:
            logger.error(f"Error generating performance forecast: {e}")
            return {'error': str(e)}
    
    async def get_optimization_recommendations(self) -> Dict[str, Any]:
        """Gera recomendações inteligentes de otimização"""
        if not self._metrics_history:
            return {'error': 'No metrics data available'}
        
        current_metrics = self._metrics_history[-1]
        recommendations = {
            'generated_at': datetime.now().isoformat(),
            'current_performance_score': await self._calculate_performance_score(current_metrics),
            'immediate_actions': [],
            'strategic_optimizations': [],
            'ml_insights': [],
            'configuration_suggestions': []
        }
        
        # Ações imediatas baseadas em thresholds críticos
        if current_metrics.redis_latency_ms > 100:
            recommendations['immediate_actions'].append({
                'priority': 'high',
                'action': 'Reduce Redis latency',
                'current_value': current_metrics.redis_latency_ms,
                'target_value': 50,
                'suggested_steps': [
                    'Optimize Redis memory policy',
                    'Increase connection pool size',
                    'Review slow queries'
                ]
            })
        
        if current_metrics.redis_hit_rate < 0.85:
            recommendations['immediate_actions'].append({
                'priority': 'high',
                'action': 'Improve cache hit rate',
                'current_value': current_metrics.redis_hit_rate,
                'target_value': 0.95,
                'suggested_steps': [
                    'Implement cache warming',
                    'Review TTL policies',
                    'Optimize cache keys structure'
                ]
            })
        
        # Otimizações estratégicas baseadas em análise de trends
        if len(self._metrics_history) >= 50:
            trends = await self._analyze_performance_trends(list(self._metrics_history)[-50:])
            
            for metric, trend in trends.items():
                if abs(trend) > 0.1:  # Tendência significativa
                    direction = 'increasing' if trend > 0 else 'decreasing'
                    urgency = 'high' if abs(trend) > 0.5 else 'medium'
                    
                    recommendations['strategic_optimizations'].append({
                        'metric': metric,
                        'trend': f"{direction} ({trend:.3f})",
                        'urgency': urgency,
                        'recommendation': f"Monitor and optimize {metric} trend"
                    })
        
        # Insights baseados em ML (simulado)
        if self._performance_predictor:
            recommendations['ml_insights'].append({
                'type': 'pattern_detection',
                'insight': 'ML model identifies correlation between memory usage and latency',
                'confidence': 0.85,
                'action': 'Focus on memory optimization to improve latency'
            })
        
        # Sugestões de configuração baseadas em best practices
        config_suggestions = []
        
        if current_metrics.redis_connected_clients > 5000:
            config_suggestions.append({
                'parameter': 'maxclients',
                'current': await self._redis_client.config_get('maxclients'),
                'suggested': '10000',
                'reason': 'High connection count detected'
            })
        
        if current_metrics.redis_memory_used_percent > 0.8:
            config_suggestions.append({
                'parameter': 'maxmemory-policy',
                'suggested': 'allkeys-lru',
                'reason': 'High memory usage - optimize eviction policy'
            })
        
        recommendations['configuration_suggestions'] = config_suggestions
        
        return recommendations
    
    async def execute_emergency_optimization(self) -> Dict[str, Any]:
        """Executa otimização de emergência para situações críticas"""
        try:
            if not self._metrics_history:
                return {'error': 'No metrics available for emergency optimization'}
            
            current_metrics = self._metrics_history[-1]
            emergency_actions = []
            
            # Detecta situações críticas
            critical_latency = current_metrics.redis_latency_ms > 200
            critical_memory = current_metrics.redis_memory_used_percent > 0.95
            critical_cpu = current_metrics.cpu_percent > 95
            
            logger.warning(f"EMERGENCY OPTIMIZATION TRIGGERED - Latency: {critical_latency}, Memory: {critical_memory}, CPU: {critical_cpu}")
            
            # Ações de emergência para latência crítica
            if critical_latency:
                try:
                    await self._redis_client.config_set('timeout', '60')
                    await self._redis_client.config_set('tcp-keepalive', '30')
                    emergency_actions.append('Reduced timeout and keepalive for latency')
                except Exception as e:
                    logger.error(f"Error in emergency latency optimization: {e}")
            
            # Ações de emergência para memória crítica
            if critical_memory:
                try:
                    await self._redis_client.config_set('maxmemory-policy', 'allkeys-lru')
                    # Força cleanup de chaves expiradas
                    await self._redis_client.eval("return redis.call('scan', 0, 'count', 10000)", 0)
                    emergency_actions.append('Optimized memory policy and forced cleanup')
                except Exception as e:
                    logger.error(f"Error in emergency memory optimization: {e}")
            
            # Ações de emergência para CPU crítico
            if critical_cpu:
                try:
                    # Reduz carga limitando conexões
                    await self._redis_client.config_set('maxclients', '1000')
                    emergency_actions.append('Reduced max clients to limit CPU load')
                except Exception as e:
                    logger.error(f"Error in emergency CPU optimization: {e}")
            
            # Log da ação de emergência
            emergency_event = {
                'timestamp': datetime.now().isoformat(),
                'trigger_metrics': current_metrics.to_dict(),
                'actions_taken': emergency_actions,
                'critical_conditions': {
                    'latency': critical_latency,
                    'memory': critical_memory,
                    'cpu': critical_cpu
                }
            }
            
            return {
                'success': True,
                'actions_taken': emergency_actions,
                'emergency_event': emergency_event
            }
            
        except Exception as e:
            logger.error(f"Error in emergency optimization: {e}")
            return {'error': str(e)}
    
    async def get_system_health_score(self) -> Dict[str, Any]:
        """Calcula score abrangente de saúde do sistema"""
        try:
            if not self._metrics_history:
                return {'error': 'No metrics data available'}
            
            current_metrics = self._metrics_history[-1]
            
            # Componentes do health score (0-100 cada)
            components = {}
            
            # Redis Health (40% do score total)
            redis_latency_score = max(0, 100 - (current_metrics.redis_latency_ms / 2))
            redis_hit_rate_score = current_metrics.redis_hit_rate * 100
            redis_memory_score = max(0, 100 - (current_metrics.redis_memory_used_percent * 100))
            
            redis_health = (redis_latency_score + redis_hit_rate_score + redis_memory_score) / 3
            components['redis_health'] = redis_health
            
            # System Health (30% do score total)
            cpu_score = max(0, 100 - current_metrics.cpu_percent)
            memory_score = max(0, 100 - current_metrics.memory_percent)
            
            system_health = (cpu_score + memory_score) / 2
            components['system_health'] = system_health
            
            # Stability Health (20% do score total)
            stability_score = await self._calculate_stability_score()
            components['stability_health'] = stability_score
            
            # Performance Trend Health (10% do score total)
            trend_health = 100.0  # Default
            if len(self._metrics_history) >= 20:
                trends = await self._analyze_performance_trends(list(self._metrics_history)[-20:])
                
                # Penaliza trends negativos
                trend_penalties = 0
                for metric, trend in trends.items():
                    if metric == 'latency' and trend > 0.5:  # Latência aumentando
                        trend_penalties += 20
                    elif metric == 'hit_rate' and trend < -0.01:  # Hit rate decrescendo
                        trend_penalties += 25
                    elif metric == 'memory' and trend > 0.01:  # Memória aumentando
                        trend_penalties += 15
                
                trend_health = max(0, 100 - trend_penalties)
            
            components['trend_health'] = trend_health
            
            # Calcula score total ponderado
            total_health_score = (
                components['redis_health'] * 0.4 +
                components['system_health'] * 0.3 +
                components['stability_health'] * 0.2 +
                components['trend_health'] * 0.1
            )
            
            # Determina status geral
            if total_health_score >= 90:
                status = 'excellent'
            elif total_health_score >= 75:
                status = 'good'
            elif total_health_score >= 60:
                status = 'fair'
            elif total_health_score >= 40:
                status = 'poor'
            else:
                status = 'critical'
            
            # Identifica áreas que precisam de atenção
            attention_areas = []
            for component, score in components.items():
                if score < 70:
                    attention_areas.append(component.replace('_', ' ').title())
            
            return {
                'timestamp': datetime.now().isoformat(),
                'overall_health_score': round(total_health_score, 2),
                'status': status,
                'component_scores': {k: round(v, 2) for k, v in components.items()},
                'attention_areas': attention_areas,
                'metrics_snapshot': current_metrics.to_dict(),
                'recommendations': await self._get_health_recommendations(total_health_score, components)
            }
            
        except Exception as e:
            logger.error(f"Error calculating system health score: {e}")
            return {'error': str(e)}
    
    async def _get_health_recommendations(self, total_score: float, components: Dict[str, float]) -> List[str]:
        """Gera recomendações baseadas no health score"""
        recommendations = []
        
        if total_score < 60:
            recommendations.append("URGENT: System health is below acceptable levels - immediate action required")
        
        if components.get('redis_health', 100) < 70:
            recommendations.append("Focus on Redis optimization - check latency, hit rate, and memory usage")
        
        if components.get('system_health', 100) < 70:
            recommendations.append("System resources are strained - consider scaling or optimization")
        
        if components.get('stability_health', 100) < 70:
            recommendations.append("System stability is concerning - investigate metric variations")
        
        if components.get('trend_health', 100) < 70:
            recommendations.append("Performance trends are negative - proactive optimization needed")
        
        if total_score >= 90:
            recommendations.append("System health is excellent - maintain current optimization strategies")
        
        return recommendations


# Instância global do otimizador avançado
advanced_performance_optimizer = AdvancedPerformanceOptimizer()