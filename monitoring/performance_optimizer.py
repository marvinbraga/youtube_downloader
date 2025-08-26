"""
Performance Optimizer - Automatic Redis Tuning and Optimization
Sistema de otimização automática do Redis baseado em métricas de performance

Agent-Infrastructure - FASE 4 Production Monitoring
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
import statistics

from loguru import logger

from app.services.redis_connection import get_redis_client


@dataclass
class OptimizationRule:
    """Regra de otimização"""
    id: str
    name: str
    description: str
    condition: str  # memory_high, hit_rate_low, latency_high, connections_high
    threshold: float
    action: str  # config_change, memory_cleanup, connection_limit, etc.
    parameters: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    cooldown_minutes: int = 30
    last_applied: Optional[datetime] = None
    
    def can_apply(self) -> bool:
        """Verifica se a regra pode ser aplicada (cooldown)"""
        if not self.enabled:
            return False
        
        if self.last_applied is None:
            return True
        
        cooldown_expires = self.last_applied + timedelta(minutes=self.cooldown_minutes)
        return datetime.now() > cooldown_expires


@dataclass
class OptimizationAction:
    """Ação de otimização executada"""
    id: str
    rule_id: str
    action_type: str
    description: str
    parameters: Dict[str, Any]
    timestamp: datetime
    success: bool = False
    error_message: Optional[str] = None
    before_metrics: Dict[str, Any] = field(default_factory=dict)
    after_metrics: Dict[str, Any] = field(default_factory=dict)
    impact_score: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class PerformanceOptimizer:
    """
    Sistema de otimização automática de performance
    
    Funcionalidades:
    - Monitoramento contínuo de métricas de performance
    - Aplicação automática de otimizações baseadas em regras
    - Análise de impacto das otimizações
    - Rollback automático de otimizações que degradam performance
    - Relatórios de otimização
    - Aprendizado de padrões para otimização proativa
    """
    
    def __init__(self, optimization_interval: int = 300):  # 5 minutos
        self.optimization_interval = optimization_interval
        self.is_optimizing = False
        self._stop_optimizing = False
        
        # Storage
        self._optimization_rules: Dict[str, OptimizationRule] = {}
        self._optimization_history: deque[OptimizationAction] = deque(maxlen=1000)
        self._performance_baseline: Dict[str, float] = {}
        self._current_metrics: Dict[str, Any] = {}
        
        # Redis client
        self._redis_client = None
        
        # Configurações padrão do Redis
        self._default_redis_config = {
            'maxmemory-policy': 'allkeys-lru',
            'tcp-keepalive': '60',
            'timeout': '300',
            'maxclients': '10000',
            'save': '900 1 300 10 60 10000',
            'stop-writes-on-bgsave-error': 'no',
            'rdbcompression': 'yes',
            'rdbchecksum': 'yes'
        }
        
        # Limites de segurança para evitar configurações perigosas
        self._safety_limits = {
            'maxmemory': {'min_gb': 0.5, 'max_gb': 32.0},
            'maxclients': {'min': 100, 'max': 50000},
            'timeout': {'min': 60, 'max': 3600},
            'tcp-keepalive': {'min': 30, 'max': 300}
        }
        
        # Estatísticas
        self._optimization_stats = {
            'total_optimizations': 0,
            'successful_optimizations': 0,
            'failed_optimizations': 0,
            'rollbacks_performed': 0,
            'avg_impact_score': 0.0
        }
        
        logger.info(f"PerformanceOptimizer initialized (interval: {optimization_interval}s)")
    
    async def initialize(self) -> bool:
        """Inicializa o otimizador de performance"""
        try:
            # Conecta ao Redis
            self._redis_client = await get_redis_client()
            if not self._redis_client:
                logger.error("Failed to connect to Redis")
                return False
            
            # Estabelece baseline de performance
            await self._establish_performance_baseline()
            
            # Registra regras padrão
            await self._register_default_optimization_rules()
            
            logger.info("Performance optimizer initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize performance optimizer: {e}")
            return False
    
    async def start_optimization(self):
        """Inicia otimização automática"""
        if self.is_optimizing:
            logger.warning("Performance optimization already running")
            return
        
        if not await self.initialize():
            logger.error("Cannot start performance optimization - initialization failed")
            return
        
        self.is_optimizing = True
        self._stop_optimizing = False
        
        logger.info("Starting automatic performance optimization")
        
        # Tasks principais
        optimization_task = asyncio.create_task(self._optimization_loop())
        monitoring_task = asyncio.create_task(self._monitoring_loop())
        analysis_task = asyncio.create_task(self._analysis_loop())
        rollback_task = asyncio.create_task(self._rollback_monitor_loop())
        
        try:
            await asyncio.gather(
                optimization_task,
                monitoring_task,
                analysis_task,
                rollback_task
            )
        except Exception as e:
            logger.error(f"Error in optimization tasks: {e}")
        finally:
            self.is_optimizing = False
            logger.info("Performance optimization stopped")
    
    async def stop_optimization(self):
        """Para otimização automática"""
        self._stop_optimizing = True
        self.is_optimizing = False
        logger.info("Stopping performance optimization...")
    
    async def _optimization_loop(self):
        """Loop principal de otimização"""
        while not self._stop_optimizing:
            try:
                await self._run_optimization_cycle()
                await asyncio.sleep(self.optimization_interval)
                
            except Exception as e:
                logger.error(f"Error in optimization loop: {e}")
                await asyncio.sleep(self.optimization_interval)
    
    async def _run_optimization_cycle(self):
        """Executa um ciclo completo de otimização"""
        # Atualiza métricas atuais
        await self._update_current_metrics()
        
        # Avalia todas as regras
        for rule in self._optimization_rules.values():
            if not rule.can_apply():
                continue
            
            try:
                if await self._evaluate_rule_condition(rule):
                    await self._apply_optimization_rule(rule)
            except Exception as e:
                logger.error(f"Error applying optimization rule '{rule.id}': {e}")
    
    async def _update_current_metrics(self):
        """Atualiza métricas atuais do Redis"""
        if not self._redis_client:
            return
        
        try:
            # Coleta info do Redis
            info = await self._redis_client.info()
            
            # Teste de latência
            start_time = time.time()
            await self._redis_client.ping()
            latency_ms = (time.time() - start_time) * 1000
            
            # Calcula métricas derivadas
            used_memory = int(info.get('used_memory', 0))
            maxmemory = int(info.get('maxmemory', 0))
            memory_percent = (used_memory / maxmemory * 100) if maxmemory > 0 else 0.0
            
            hits = int(info.get('keyspace_hits', 0))
            misses = int(info.get('keyspace_misses', 0))
            hit_rate = hits / (hits + misses) if (hits + misses) > 0 else 1.0
            
            self._current_metrics = {
                'memory_used_mb': used_memory / (1024 * 1024),
                'memory_used_percent': memory_percent / 100.0,
                'hit_rate': hit_rate,
                'latency_ms': latency_ms,
                'connected_clients': int(info.get('connected_clients', 0)),
                'ops_per_sec': int(info.get('instantaneous_ops_per_sec', 0)),
                'evicted_keys': int(info.get('evicted_keys', 0)),
                'expired_keys': int(info.get('expired_keys', 0)),
                'fragmentation_ratio': float(info.get('mem_fragmentation_ratio', 1.0)),
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error updating current metrics: {e}")
    
    async def _evaluate_rule_condition(self, rule: OptimizationRule) -> bool:
        """Avalia se condição da regra está atendida"""
        if not self._current_metrics:
            return False
        
        condition = rule.condition
        threshold = rule.threshold
        
        if condition == 'memory_high':
            return self._current_metrics.get('memory_used_percent', 0) > threshold
        
        elif condition == 'hit_rate_low':
            return self._current_metrics.get('hit_rate', 1.0) < threshold
        
        elif condition == 'latency_high':
            return self._current_metrics.get('latency_ms', 0) > threshold
        
        elif condition == 'connections_high':
            return self._current_metrics.get('connected_clients', 0) > threshold
        
        elif condition == 'fragmentation_high':
            return self._current_metrics.get('fragmentation_ratio', 1.0) > threshold
        
        elif condition == 'eviction_rate_high':
            # Para taxa de eviction, precisamos calcular a taxa por segundo
            # Por simplicidade, vamos usar o valor absoluto
            return self._current_metrics.get('evicted_keys', 0) > threshold
        
        return False
    
    async def _apply_optimization_rule(self, rule: OptimizationRule):
        """Aplica uma regra de otimização"""
        action_id = f"{rule.id}_{int(time.time())}"
        
        # Captura métricas antes da otimização
        before_metrics = dict(self._current_metrics)
        
        action = OptimizationAction(
            id=action_id,
            rule_id=rule.id,
            action_type=rule.action,
            description=f"Applied rule: {rule.name}",
            parameters=rule.parameters,
            timestamp=datetime.now(),
            before_metrics=before_metrics
        )
        
        try:
            success = False
            
            if rule.action == 'adjust_maxmemory_policy':
                success = await self._adjust_maxmemory_policy(rule.parameters)
            
            elif rule.action == 'adjust_connection_timeout':
                success = await self._adjust_connection_timeout(rule.parameters)
            
            elif rule.action == 'adjust_maxclients':
                success = await self._adjust_maxclients(rule.parameters)
            
            elif rule.action == 'trigger_memory_cleanup':
                success = await self._trigger_memory_cleanup(rule.parameters)
            
            elif rule.action == 'adjust_save_policy':
                success = await self._adjust_save_policy(rule.parameters)
            
            elif rule.action == 'enable_compression':
                success = await self._enable_compression(rule.parameters)
            
            action.success = success
            
            if success:
                # Atualiza timestamp da regra
                rule.last_applied = datetime.now()
                
                # Aguarda um pouco e coleta métricas após otimização
                await asyncio.sleep(30)
                await self._update_current_metrics()
                action.after_metrics = dict(self._current_metrics)
                
                # Calcula impacto
                action.impact_score = await self._calculate_optimization_impact(action)
                
                # Atualiza estatísticas
                self._optimization_stats['total_optimizations'] += 1
                self._optimization_stats['successful_optimizations'] += 1
                
                # Recalcula impacto médio
                impacts = [a.impact_score for a in self._optimization_history if a.success]
                if impacts:
                    self._optimization_stats['avg_impact_score'] = statistics.mean(impacts)
                
                logger.info(
                    f"OPTIMIZATION APPLIED: {rule.name} "
                    f"(impact score: {action.impact_score:.2f})"
                )
            else:
                self._optimization_stats['total_optimizations'] += 1
                self._optimization_stats['failed_optimizations'] += 1
                logger.warning(f"OPTIMIZATION FAILED: {rule.name}")
            
        except Exception as e:
            action.success = False
            action.error_message = str(e)
            
            self._optimization_stats['total_optimizations'] += 1
            self._optimization_stats['failed_optimizations'] += 1
            
            logger.error(f"Error applying optimization rule '{rule.id}': {e}")
        
        finally:
            # Adiciona ao histórico
            self._optimization_history.append(action)
    
    async def _adjust_maxmemory_policy(self, parameters: Dict[str, Any]) -> bool:
        """Ajusta política de maxmemory do Redis"""
        try:
            policy = parameters.get('policy', 'allkeys-lru')
            
            # Valida política
            valid_policies = [
                'noeviction', 'allkeys-lru', 'volatile-lru',
                'allkeys-random', 'volatile-random', 'volatile-ttl'
            ]
            
            if policy not in valid_policies:
                logger.error(f"Invalid maxmemory policy: {policy}")
                return False
            
            # Aplica configuração
            await self._redis_client.config_set('maxmemory-policy', policy)
            
            logger.info(f"Adjusted maxmemory-policy to: {policy}")
            return True
            
        except Exception as e:
            logger.error(f"Error adjusting maxmemory policy: {e}")
            return False
    
    async def _adjust_connection_timeout(self, parameters: Dict[str, Any]) -> bool:
        """Ajusta timeout de conexão"""
        try:
            timeout = parameters.get('timeout_seconds', 300)
            
            # Valida limites de segurança
            min_timeout = self._safety_limits['timeout']['min']
            max_timeout = self._safety_limits['timeout']['max']
            
            if not (min_timeout <= timeout <= max_timeout):
                logger.error(f"Timeout {timeout} outside safety limits [{min_timeout}, {max_timeout}]")
                return False
            
            await self._redis_client.config_set('timeout', str(timeout))
            
            logger.info(f"Adjusted connection timeout to: {timeout}s")
            return True
            
        except Exception as e:
            logger.error(f"Error adjusting connection timeout: {e}")
            return False
    
    async def _adjust_maxclients(self, parameters: Dict[str, Any]) -> bool:
        """Ajusta número máximo de clientes"""
        try:
            maxclients = parameters.get('maxclients', 10000)
            
            # Valida limites de segurança
            min_clients = self._safety_limits['maxclients']['min']
            max_clients = self._safety_limits['maxclients']['max']
            
            if not (min_clients <= maxclients <= max_clients):
                logger.error(f"Maxclients {maxclients} outside safety limits [{min_clients}, {max_clients}]")
                return False
            
            await self._redis_client.config_set('maxclients', str(maxclients))
            
            logger.info(f"Adjusted maxclients to: {maxclients}")
            return True
            
        except Exception as e:
            logger.error(f"Error adjusting maxclients: {e}")
            return False
    
    async def _trigger_memory_cleanup(self, parameters: Dict[str, Any]) -> bool:
        """Executa limpeza de memória"""
        try:
            cleanup_type = parameters.get('cleanup_type', 'expire_scan')
            
            if cleanup_type == 'expire_scan':
                # Força expiração de chaves TTL vencidas
                await self._redis_client.eval("return redis.call('scan', 0, 'count', 1000)", 0)
                
            elif cleanup_type == 'memory_usage_scan':
                # Executa MEMORY USAGE em algumas chaves para forçar garbage collection
                keys = await self._redis_client.keys("*")
                for key in keys[:100]:  # Primeiras 100 chaves
                    try:
                        await self._redis_client.memory_usage(key)
                    except Exception:
                        continue
            
            elif cleanup_type == 'defrag':
                # Tenta executar defragmentação (se suportado)
                try:
                    await self._redis_client.execute_command('MEMORY', 'PURGE')
                except Exception:
                    pass  # Comando pode não estar disponível em todas as versões
            
            logger.info(f"Executed memory cleanup: {cleanup_type}")
            return True
            
        except Exception as e:
            logger.error(f"Error triggering memory cleanup: {e}")
            return False
    
    async def _adjust_save_policy(self, parameters: Dict[str, Any]) -> bool:
        """Ajusta política de persistência"""
        try:
            save_policy = parameters.get('save_policy', '900 1 300 10 60 10000')
            
            await self._redis_client.config_set('save', save_policy)
            
            logger.info(f"Adjusted save policy to: {save_policy}")
            return True
            
        except Exception as e:
            logger.error(f"Error adjusting save policy: {e}")
            return False
    
    async def _enable_compression(self, parameters: Dict[str, Any]) -> bool:
        """Habilita compressão de dados"""
        try:
            rdb_compression = parameters.get('rdb_compression', 'yes')
            
            await self._redis_client.config_set('rdbcompression', rdb_compression)
            
            logger.info(f"Set RDB compression to: {rdb_compression}")
            return True
            
        except Exception as e:
            logger.error(f"Error enabling compression: {e}")
            return False
    
    async def _calculate_optimization_impact(self, action: OptimizationAction) -> float:
        """Calcula impacto da otimização na performance"""
        try:
            before = action.before_metrics
            after = action.after_metrics
            
            if not before or not after:
                return 0.0
            
            impact_score = 0.0
            
            # Impacto na latência (peso 30%)
            before_latency = before.get('latency_ms', 0)
            after_latency = after.get('latency_ms', 0)
            
            if before_latency > 0 and after_latency < before_latency:
                latency_improvement = (before_latency - after_latency) / before_latency
                impact_score += latency_improvement * 30
            
            # Impacto no hit rate (peso 25%)
            before_hit_rate = before.get('hit_rate', 0)
            after_hit_rate = after.get('hit_rate', 0)
            
            if after_hit_rate > before_hit_rate:
                hit_rate_improvement = after_hit_rate - before_hit_rate
                impact_score += hit_rate_improvement * 25
            
            # Impacto no uso de memória (peso 20%)
            before_memory = before.get('memory_used_percent', 0)
            after_memory = after.get('memory_used_percent', 0)
            
            if before_memory > 0 and after_memory < before_memory:
                memory_improvement = (before_memory - after_memory) / before_memory
                impact_score += memory_improvement * 20
            
            # Impacto na fragmentação (peso 15%)
            before_frag = before.get('fragmentation_ratio', 1.0)
            after_frag = after.get('fragmentation_ratio', 1.0)
            
            if before_frag > 1.0 and after_frag < before_frag:
                frag_improvement = (before_frag - after_frag) / (before_frag - 1.0)
                impact_score += frag_improvement * 15
            
            # Impacto nas operações por segundo (peso 10%)
            before_ops = before.get('ops_per_sec', 0)
            after_ops = after.get('ops_per_sec', 0)
            
            if before_ops > 0 and after_ops > before_ops:
                ops_improvement = (after_ops - before_ops) / before_ops
                impact_score += min(ops_improvement, 0.5) * 10  # Cap em 50% de melhoria
            
            return max(0.0, min(100.0, impact_score))  # Normaliza entre 0-100
            
        except Exception as e:
            logger.error(f"Error calculating optimization impact: {e}")
            return 0.0
    
    async def _monitoring_loop(self):
        """Loop de monitoramento contínuo"""
        while not self._stop_optimizing:
            try:
                await self._update_current_metrics()
                await asyncio.sleep(60)  # Atualiza métricas a cada minuto
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(60)
    
    async def _analysis_loop(self):
        """Loop de análise de performance e aprendizado"""
        while not self._stop_optimizing:
            try:
                await asyncio.sleep(600)  # A cada 10 minutos
                await self._analyze_optimization_effectiveness()
                
            except Exception as e:
                logger.error(f"Error in analysis loop: {e}")
    
    async def _analyze_optimization_effectiveness(self):
        """Analisa efetividade das otimizações"""
        if len(self._optimization_history) < 5:
            return
        
        recent_optimizations = list(self._optimization_history)[-10:]  # Últimas 10
        
        # Análise por tipo de otimização
        optimization_effectiveness = defaultdict(list)
        
        for action in recent_optimizations:
            if action.success:
                optimization_effectiveness[action.action_type].append(action.impact_score)
        
        # Identifica otimizações mais efetivas
        effective_optimizations = []
        for action_type, scores in optimization_effectiveness.items():
            if scores:
                avg_score = statistics.mean(scores)
                if avg_score > 10.0:  # Score mínimo para ser considerado efetivo
                    effective_optimizations.append((action_type, avg_score))
        
        if effective_optimizations:
            effective_optimizations.sort(key=lambda x: x[1], reverse=True)
            logger.info(f"Most effective optimizations: {effective_optimizations[:3]}")
        
        # Análise de degradação de performance
        await self._detect_performance_degradation()
    
    async def _detect_performance_degradation(self):
        """Detecta degradação de performance que pode requerer rollback"""
        if not self._performance_baseline or not self._current_metrics:
            return
        
        degradations = []
        
        # Verifica latência
        baseline_latency = self._performance_baseline.get('latency_ms', 0)
        current_latency = self._current_metrics.get('latency_ms', 0)
        
        if baseline_latency > 0 and current_latency > baseline_latency * 2:
            degradations.append(f"Latency increased from {baseline_latency:.2f}ms to {current_latency:.2f}ms")
        
        # Verifica hit rate
        baseline_hit_rate = self._performance_baseline.get('hit_rate', 1.0)
        current_hit_rate = self._current_metrics.get('hit_rate', 1.0)
        
        if current_hit_rate < baseline_hit_rate - 0.1:  # 10% degradation
            degradations.append(f"Hit rate decreased from {baseline_hit_rate:.1%} to {current_hit_rate:.1%}")
        
        # Verifica ops/sec
        baseline_ops = self._performance_baseline.get('ops_per_sec', 0)
        current_ops = self._current_metrics.get('ops_per_sec', 0)
        
        if baseline_ops > 0 and current_ops < baseline_ops * 0.5:  # 50% degradation
            degradations.append(f"Operations/sec decreased from {baseline_ops} to {current_ops}")
        
        if degradations:
            logger.warning(f"PERFORMANCE DEGRADATION DETECTED: {'; '.join(degradations)}")
            
            # Considera rollback se houver otimizações recentes
            recent_optimizations = [
                a for a in self._optimization_history
                if a.success and (datetime.now() - a.timestamp).total_seconds() < 1800  # Últimos 30 min
            ]
            
            if recent_optimizations:
                logger.warning("Considering rollback of recent optimizations due to performance degradation")
                await self._consider_rollback(recent_optimizations)
    
    async def _rollback_monitor_loop(self):
        """Loop de monitoramento para rollbacks automáticos"""
        while not self._stop_optimizing:
            try:
                await asyncio.sleep(300)  # A cada 5 minutos
                await self._check_for_automatic_rollbacks()
                
            except Exception as e:
                logger.error(f"Error in rollback monitor loop: {e}")
    
    async def _check_for_automatic_rollbacks(self):
        """Verifica necessidade de rollbacks automáticos"""
        # Procura por otimizações com impacto negativo
        recent_optimizations = [
            a for a in self._optimization_history
            if a.success and (datetime.now() - a.timestamp).total_seconds() < 3600  # Última hora
        ]
        
        negative_impact_optimizations = [
            a for a in recent_optimizations
            if a.impact_score < -10.0  # Impacto significativamente negativo
        ]
        
        if negative_impact_optimizations:
            logger.warning(f"Found {len(negative_impact_optimizations)} optimizations with negative impact")
            await self._perform_automatic_rollback(negative_impact_optimizations)
    
    async def _consider_rollback(self, optimizations: List[OptimizationAction]):
        """Considera rollback de otimizações baseado em degradação"""
        # Por segurança, só faz rollback de otimizações de configuração
        safe_rollback_actions = [
            'adjust_maxmemory_policy', 'adjust_connection_timeout',
            'adjust_maxclients', 'adjust_save_policy'
        ]
        
        rollback_candidates = [
            opt for opt in optimizations
            if opt.action_type in safe_rollback_actions
        ]
        
        if rollback_candidates:
            await self._perform_automatic_rollback(rollback_candidates)
    
    async def _perform_automatic_rollback(self, optimizations: List[OptimizationAction]):
        """Executa rollback automático de otimizações"""
        for optimization in optimizations:
            try:
                success = await self._rollback_optimization(optimization)
                
                if success:
                    self._optimization_stats['rollbacks_performed'] += 1
                    logger.warning(f"AUTOMATIC ROLLBACK: {optimization.description}")
                else:
                    logger.error(f"Failed to rollback optimization: {optimization.id}")
                    
            except Exception as e:
                logger.error(f"Error performing rollback for {optimization.id}: {e}")
    
    async def _rollback_optimization(self, action: OptimizationAction) -> bool:
        """Executa rollback de uma otimização específica"""
        try:
            # Recupera configuração anterior dos before_metrics ou usa padrões
            before_metrics = action.before_metrics
            
            if action.action_type == 'adjust_maxmemory_policy':
                # Volta para política padrão
                await self._redis_client.config_set('maxmemory-policy', 'allkeys-lru')
                return True
            
            elif action.action_type == 'adjust_connection_timeout':
                # Volta para timeout padrão
                await self._redis_client.config_set('timeout', '300')
                return True
            
            elif action.action_type == 'adjust_maxclients':
                # Volta para maxclients padrão
                await self._redis_client.config_set('maxclients', '10000')
                return True
            
            elif action.action_type == 'adjust_save_policy':
                # Volta para save policy padrão
                await self._redis_client.config_set('save', '900 1 300 10 60 10000')
                return True
            
            # Outros tipos de otimização não suportam rollback automático
            logger.warning(f"Rollback not supported for action type: {action.action_type}")
            return False
            
        except Exception as e:
            logger.error(f"Error in rollback execution: {e}")
            return False
    
    async def _establish_performance_baseline(self):
        """Estabelece baseline de performance"""
        try:
            # Coleta várias amostras para estabelecer baseline estável
            samples = []
            
            for _ in range(5):
                await self._update_current_metrics()
                if self._current_metrics:
                    samples.append(dict(self._current_metrics))
                await asyncio.sleep(2)
            
            if samples:
                # Calcula médias para baseline
                self._performance_baseline = {
                    'latency_ms': statistics.mean([s.get('latency_ms', 0) for s in samples]),
                    'hit_rate': statistics.mean([s.get('hit_rate', 0) for s in samples]),
                    'ops_per_sec': statistics.mean([s.get('ops_per_sec', 0) for s in samples]),
                    'memory_used_percent': statistics.mean([s.get('memory_used_percent', 0) for s in samples]),
                    'fragmentation_ratio': statistics.mean([s.get('fragmentation_ratio', 1.0) for s in samples]),
                    'established_at': datetime.now().isoformat()
                }
                
                logger.info(
                    f"Performance baseline established: "
                    f"latency={self._performance_baseline['latency_ms']:.2f}ms, "
                    f"hit_rate={self._performance_baseline['hit_rate']:.1%}, "
                    f"ops/sec={self._performance_baseline['ops_per_sec']:.0f}"
                )
                
        except Exception as e:
            logger.error(f"Failed to establish performance baseline: {e}")
    
    async def _register_default_optimization_rules(self):
        """Registra regras padrão de otimização"""
        default_rules = [
            OptimizationRule(
                id="memory_high_adjust_policy",
                name="Adjust Memory Policy for High Usage",
                description="Changes memory eviction policy when usage is high",
                condition="memory_high",
                threshold=0.85,  # 85% memory usage
                action="adjust_maxmemory_policy",
                parameters={'policy': 'allkeys-lru'},
                cooldown_minutes=60
            ),
            OptimizationRule(
                id="hit_rate_low_cleanup",
                name="Memory Cleanup for Low Hit Rate",
                description="Triggers memory cleanup when hit rate is low",
                condition="hit_rate_low",
                threshold=0.80,  # 80% hit rate
                action="trigger_memory_cleanup",
                parameters={'cleanup_type': 'expire_scan'},
                cooldown_minutes=30
            ),
            OptimizationRule(
                id="latency_high_timeout_adjust",
                name="Adjust Timeout for High Latency",
                description="Reduces connection timeout when latency is high",
                condition="latency_high",
                threshold=50.0,  # 50ms latency
                action="adjust_connection_timeout",
                parameters={'timeout_seconds': 180},
                cooldown_minutes=45
            ),
            OptimizationRule(
                id="connections_high_limit",
                name="Adjust Max Clients for High Connection Count",
                description="Reduces max clients when connection count is high",
                condition="connections_high",
                threshold=8000,  # 8000 connections
                action="adjust_maxclients",
                parameters={'maxclients': 12000},
                cooldown_minutes=90
            ),
            OptimizationRule(
                id="fragmentation_high_cleanup",
                name="Memory Defragmentation for High Fragmentation",
                description="Triggers defragmentation when fragmentation ratio is high",
                condition="fragmentation_high",
                threshold=1.5,  # 1.5 fragmentation ratio
                action="trigger_memory_cleanup",
                parameters={'cleanup_type': 'defrag'},
                cooldown_minutes=120
            ),
            OptimizationRule(
                id="memory_critical_compression",
                name="Enable Compression for Critical Memory Usage",
                description="Enables RDB compression when memory usage is critical",
                condition="memory_high",
                threshold=0.95,  # 95% memory usage
                action="enable_compression",
                parameters={'rdb_compression': 'yes'},
                cooldown_minutes=180
            )
        ]
        
        for rule in default_rules:
            self._optimization_rules[rule.id] = rule
        
        logger.info(f"Registered {len(default_rules)} default optimization rules")
    
    # Métodos públicos para consultas e controle
    
    async def get_optimization_status(self) -> Dict[str, Any]:
        """Obtém status do sistema de otimização"""
        return {
            "timestamp": datetime.now().isoformat(),
            "is_optimizing": self.is_optimizing,
            "current_metrics": self._current_metrics,
            "performance_baseline": self._performance_baseline,
            "total_rules": len(self._optimization_rules),
            "active_rules": len([r for r in self._optimization_rules.values() if r.enabled]),
            "optimization_stats": self._optimization_stats,
            "recent_optimizations": [
                action.to_dict() for action in list(self._optimization_history)[-10:]
            ]
        }
    
    async def get_optimization_report(self, hours: int = 24) -> Dict[str, Any]:
        """Gera relatório de otimizações"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        period_optimizations = [
            action for action in self._optimization_history
            if action.timestamp > cutoff_time
        ]
        
        if not period_optimizations:
            return {"error": f"No optimizations in last {hours} hours"}
        
        # Estatísticas do período
        successful_optimizations = [a for a in period_optimizations if a.success]
        failed_optimizations = [a for a in period_optimizations if not a.success]
        
        # Análise por tipo de ação
        action_stats = defaultdict(lambda: {'count': 0, 'success_count': 0, 'avg_impact': 0.0})
        
        for action in period_optimizations:
            stats = action_stats[action.action_type]
            stats['count'] += 1
            if action.success:
                stats['success_count'] += 1
                stats['avg_impact'] += action.impact_score
        
        # Calcula médias de impacto
        for stats in action_stats.values():
            if stats['success_count'] > 0:
                stats['avg_impact'] /= stats['success_count']
                stats['success_rate'] = stats['success_count'] / stats['count'] * 100
            else:
                stats['avg_impact'] = 0.0
                stats['success_rate'] = 0.0
        
        return {
            "period_hours": hours,
            "timestamp": datetime.now().isoformat(),
            "summary": {
                "total_optimizations": len(period_optimizations),
                "successful_optimizations": len(successful_optimizations),
                "failed_optimizations": len(failed_optimizations),
                "success_rate": len(successful_optimizations) / len(period_optimizations) * 100,
                "avg_impact_score": statistics.mean([a.impact_score for a in successful_optimizations]) if successful_optimizations else 0.0
            },
            "action_breakdown": dict(action_stats),
            "top_optimizations": sorted(
                [a.to_dict() for a in successful_optimizations],
                key=lambda x: x['impact_score'],
                reverse=True
            )[:10],
            "performance_trend": await self._analyze_performance_trend(period_optimizations)
        }
    
    async def _analyze_performance_trend(self, optimizations: List[OptimizationAction]) -> Dict[str, Any]:
        """Analisa tendência de performance baseada nas otimizações"""
        if not optimizations:
            return {"status": "no_data"}
        
        # Ordena por timestamp
        sorted_optimizations = sorted(optimizations, key=lambda x: x.timestamp)
        
        # Coleta métricas antes e depois
        before_metrics = []
        after_metrics = []
        
        for opt in sorted_optimizations:
            if opt.success and opt.before_metrics and opt.after_metrics:
                before_metrics.append(opt.before_metrics)
                after_metrics.append(opt.after_metrics)
        
        if not before_metrics or not after_metrics:
            return {"status": "insufficient_data"}
        
        # Calcula tendências
        def calculate_trend(before_values: List[float], after_values: List[float]) -> Dict[str, float]:
            if not before_values or not after_values:
                return {"trend": 0.0, "improvement_percent": 0.0}
            
            avg_before = statistics.mean(before_values)
            avg_after = statistics.mean(after_values)
            
            if avg_before == 0:
                return {"trend": 0.0, "improvement_percent": 0.0}
            
            improvement = (avg_after - avg_before) / avg_before * 100
            return {"trend": avg_after - avg_before, "improvement_percent": improvement}
        
        return {
            "status": "success",
            "latency_trend": calculate_trend(
                [m.get('latency_ms', 0) for m in before_metrics],
                [m.get('latency_ms', 0) for m in after_metrics]
            ),
            "hit_rate_trend": calculate_trend(
                [m.get('hit_rate', 0) for m in before_metrics],
                [m.get('hit_rate', 0) for m in after_metrics]
            ),
            "memory_usage_trend": calculate_trend(
                [m.get('memory_used_percent', 0) for m in before_metrics],
                [m.get('memory_used_percent', 0) for m in after_metrics]
            ),
            "ops_per_sec_trend": calculate_trend(
                [m.get('ops_per_sec', 0) for m in before_metrics],
                [m.get('ops_per_sec', 0) for m in after_metrics]
            )
        }
    
    async def manual_optimization(self, rule_id: str) -> Dict[str, Any]:
        """Executa otimização manual de uma regra específica"""
        rule = self._optimization_rules.get(rule_id)
        if not rule:
            return {"error": f"Optimization rule '{rule_id}' not found"}
        
        # Força aplicação mesmo se cooldown não expirou
        original_last_applied = rule.last_applied
        rule.last_applied = None
        
        try:
            await self._update_current_metrics()
            await self._apply_optimization_rule(rule)
            
            return {
                "success": True,
                "rule_id": rule_id,
                "message": f"Manual optimization '{rule.name}' executed"
            }
            
        except Exception as e:
            # Restaura timestamp original em caso de erro
            rule.last_applied = original_last_applied
            return {"error": f"Error executing manual optimization: {e}"}


# Instância global do otimizador de performance
performance_optimizer = PerformanceOptimizer()