"""
Redis Monitor - Advanced Redis Monitoring for Production
Sistema avançado de monitoramento Redis com métricas detalhadas e análise de performance

Agent-Infrastructure - FASE 4 Production Monitoring
"""

import asyncio
import json
import time
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
import statistics

from loguru import logger

from app.services.redis_connection import get_redis_client


@dataclass
class RedisMetric:
    """Métrica individual do Redis"""
    timestamp: datetime
    name: str
    value: float
    unit: str
    category: str  # memory, performance, connections, persistence, stats
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class RedisSlowQuery:
    """Query lenta detectada"""
    id: int
    timestamp: datetime
    duration_ms: float
    command: str
    key_pattern: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class RedisHealthSnapshot:
    """Snapshot completo da saúde do Redis"""
    timestamp: datetime
    
    # Memory metrics
    used_memory_mb: float
    used_memory_peak_mb: float
    used_memory_rss_mb: float
    mem_fragmentation_ratio: float
    maxmemory_mb: float
    used_memory_percent: float
    
    # Performance metrics  
    keyspace_hits: int
    keyspace_misses: int
    hit_rate: float
    ops_per_sec: int
    avg_ttl: float
    expired_keys: int
    evicted_keys: int
    
    # Connection metrics
    connected_clients: int
    blocked_clients: int
    client_recent_max_input_buffer: int
    client_recent_max_output_buffer: int
    
    # Persistence metrics
    rdb_changes_since_last_save: int
    rdb_last_save_time: int
    aof_current_size: int
    aof_base_size: int
    
    # Latency metrics
    avg_latency_ms: float
    max_latency_ms: float
    p95_latency_ms: float
    slow_queries_count: int
    
    # Keyspace metrics
    total_keys: int
    expired_keys_per_sec: float
    evicted_keys_per_sec: float
    
    # Replication metrics (if applicable)
    role: str
    connected_slaves: int
    repl_backlog_size: int
    
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


class RedisMonitor:
    """
    Monitor avançado do Redis para produção
    
    Funcionalidades:
    - Métricas detalhadas de memory, performance e conexões
    - Detecção de slow queries
    - Análise de padrões de uso
    - Alertas específicos do Redis
    - Otimizações baseadas em métricas
    - Relatórios de capacidade
    """
    
    def __init__(self, sample_interval: int = 30):
        self.sample_interval = sample_interval
        self.is_monitoring = False
        self._stop_monitoring = False
        
        # Storage
        self._snapshots: deque[RedisHealthSnapshot] = deque(maxlen=2880)  # 24h de dados
        self._metrics_buffer: deque[RedisMetric] = deque(maxlen=10000)
        self._slow_queries: deque[RedisSlowQuery] = deque(maxlen=1000)
        
        # Redis client
        self._redis_client = None
        
        # Latency tracking
        self._latency_samples = deque(maxlen=100)
        
        # Performance tracking
        self._last_stats = {}
        self._performance_baseline = {}
        
        # Container name para comandos docker (se aplicável)
        self.container_name = "gecon_backend-redis"
        
        logger.info(f"RedisMonitor initialized (interval: {sample_interval}s)")
    
    async def initialize(self) -> bool:
        """Inicializa o monitor Redis"""
        try:
            self._redis_client = await get_redis_client()
            if not self._redis_client:
                logger.error("Failed to connect to Redis")
                return False
            
            # Estabelece baseline de performance
            await self._establish_performance_baseline()
            
            logger.info("Redis monitor initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis monitor: {e}")
            return False
    
    async def start_monitoring(self):
        """Inicia monitoramento intensivo do Redis"""
        if self.is_monitoring:
            logger.warning("Redis monitoring already running")
            return
        
        if not await self.initialize():
            logger.error("Cannot start Redis monitoring - initialization failed")
            return
        
        self.is_monitoring = True
        self._stop_monitoring = False
        
        logger.info("Starting intensive Redis monitoring")
        
        # Tasks de monitoramento
        snapshot_task = asyncio.create_task(self._snapshot_loop())
        slow_query_task = asyncio.create_task(self._slow_query_loop())
        latency_task = asyncio.create_task(self._latency_monitoring_loop())
        analysis_task = asyncio.create_task(self._analysis_loop())
        
        try:
            await asyncio.gather(
                snapshot_task,
                slow_query_task,
                latency_task,
                analysis_task
            )
        except Exception as e:
            logger.error(f"Error in Redis monitoring tasks: {e}")
        finally:
            self.is_monitoring = False
            logger.info("Redis monitoring stopped")
    
    async def stop_monitoring(self):
        """Para o monitoramento Redis"""
        self._stop_monitoring = True
        self.is_monitoring = False
        logger.info("Stopping Redis monitoring...")
    
    async def _snapshot_loop(self):
        """Loop principal de coleta de snapshots"""
        while not self._stop_monitoring:
            try:
                snapshot = await self._collect_health_snapshot()
                
                if snapshot:
                    self._snapshots.append(snapshot)
                    
                    # Log status a cada 5 minutos
                    if len(self._snapshots) % 10 == 0:  # 5 min / 30s = 10
                        await self._log_redis_status(snapshot)
                
                await asyncio.sleep(self.sample_interval)
                
            except Exception as e:
                logger.error(f"Error in Redis snapshot loop: {e}")
                await asyncio.sleep(self.sample_interval)
    
    async def _collect_health_snapshot(self) -> Optional[RedisHealthSnapshot]:
        """Coleta snapshot completo da saúde do Redis"""
        if not self._redis_client:
            return None
        
        try:
            # Coleta info do Redis
            info = await self._redis_client.info()
            
            # Calcula métricas derivadas
            used_memory = int(info.get('used_memory', 0))
            maxmemory = int(info.get('maxmemory', 0))
            used_memory_percent = (used_memory / maxmemory * 100) if maxmemory > 0 else 0.0
            
            hits = int(info.get('keyspace_hits', 0))
            misses = int(info.get('keyspace_misses', 0))
            hit_rate = hits / (hits + misses) if (hits + misses) > 0 else 1.0
            
            # Latência
            latency_stats = await self._measure_latency()
            
            # Contagem de chaves
            total_keys = await self._count_total_keys()
            
            # Cria snapshot
            snapshot = RedisHealthSnapshot(
                timestamp=datetime.now(),
                
                # Memory metrics
                used_memory_mb=used_memory / 1024 / 1024,
                used_memory_peak_mb=int(info.get('used_memory_peak', 0)) / 1024 / 1024,
                used_memory_rss_mb=int(info.get('used_memory_rss', 0)) / 1024 / 1024,
                mem_fragmentation_ratio=float(info.get('mem_fragmentation_ratio', 1.0)),
                maxmemory_mb=maxmemory / 1024 / 1024,
                used_memory_percent=used_memory_percent,
                
                # Performance metrics
                keyspace_hits=hits,
                keyspace_misses=misses,
                hit_rate=hit_rate,
                ops_per_sec=int(info.get('instantaneous_ops_per_sec', 0)),
                avg_ttl=await self._calculate_avg_ttl(),
                expired_keys=int(info.get('expired_keys', 0)),
                evicted_keys=int(info.get('evicted_keys', 0)),
                
                # Connection metrics
                connected_clients=int(info.get('connected_clients', 0)),
                blocked_clients=int(info.get('blocked_clients', 0)),
                client_recent_max_input_buffer=int(info.get('client_recent_max_input_buffer', 0)),
                client_recent_max_output_buffer=int(info.get('client_recent_max_output_buffer', 0)),
                
                # Persistence metrics
                rdb_changes_since_last_save=int(info.get('rdb_changes_since_last_save', 0)),
                rdb_last_save_time=int(info.get('rdb_last_save_time', 0)),
                aof_current_size=int(info.get('aof_current_size', 0)),
                aof_base_size=int(info.get('aof_base_size', 0)),
                
                # Latency metrics
                avg_latency_ms=latency_stats['avg'],
                max_latency_ms=latency_stats['max'],
                p95_latency_ms=latency_stats['p95'],
                slow_queries_count=len(self._slow_queries),
                
                # Keyspace metrics
                total_keys=total_keys,
                expired_keys_per_sec=await self._calculate_rate('expired_keys', int(info.get('expired_keys', 0))),
                evicted_keys_per_sec=await self._calculate_rate('evicted_keys', int(info.get('evicted_keys', 0))),
                
                # Replication metrics
                role=info.get('role', 'unknown'),
                connected_slaves=int(info.get('connected_slaves', 0)),
                repl_backlog_size=int(info.get('repl_backlog_size', 0))
            )
            
            return snapshot
            
        except Exception as e:
            logger.error(f"Error collecting Redis health snapshot: {e}")
            return None
    
    async def _measure_latency(self) -> Dict[str, float]:
        """Mede latência do Redis com múltiplas amostras"""
        latencies = []
        
        for _ in range(10):  # 10 amostras
            start_time = time.time()
            await self._redis_client.ping()
            latency_ms = (time.time() - start_time) * 1000
            latencies.append(latency_ms)
        
        # Adiciona ao buffer
        self._latency_samples.extend(latencies)
        
        return {
            'avg': statistics.mean(latencies),
            'max': max(latencies),
            'min': min(latencies),
            'p95': statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies)
        }
    
    async def _count_total_keys(self) -> int:
        """Conta total de chaves no Redis"""
        try:
            info = await self._redis_client.info('keyspace')
            total = 0
            
            for key, value in info.items():
                if key.startswith('db'):
                    # Parse "keys=123,expires=45,avg_ttl=67890"
                    keys_part = value.split(',')[0]
                    keys_count = int(keys_part.split('=')[1])
                    total += keys_count
            
            return total
            
        except Exception:
            return 0
    
    async def _calculate_avg_ttl(self) -> float:
        """Calcula TTL médio das chaves"""
        try:
            info = await self._redis_client.info('keyspace')
            total_ttl = 0
            total_keys_with_ttl = 0
            
            for key, value in info.items():
                if key.startswith('db') and 'avg_ttl' in value:
                    parts = value.split(',')
                    for part in parts:
                        if part.startswith('avg_ttl='):
                            avg_ttl = int(part.split('=')[1])
                            expires_part = [p for p in parts if p.startswith('expires=')]
                            if expires_part:
                                expires_count = int(expires_part[0].split('=')[1])
                                total_ttl += avg_ttl * expires_count
                                total_keys_with_ttl += expires_count
            
            return total_ttl / total_keys_with_ttl if total_keys_with_ttl > 0 else 0.0
            
        except Exception:
            return 0.0
    
    async def _calculate_rate(self, metric_name: str, current_value: int) -> float:
        """Calcula taxa por segundo de uma métrica"""
        now = time.time()
        
        if metric_name in self._last_stats:
            last_value, last_time = self._last_stats[metric_name]
            time_diff = now - last_time
            value_diff = current_value - last_value
            
            rate = value_diff / time_diff if time_diff > 0 else 0.0
        else:
            rate = 0.0
        
        self._last_stats[metric_name] = (current_value, now)
        return max(0.0, rate)
    
    async def _slow_query_loop(self):
        """Loop de detecção de slow queries"""
        while not self._stop_monitoring:
            try:
                await self._detect_slow_queries()
                await asyncio.sleep(60)  # Verifica a cada minuto
                
            except Exception as e:
                logger.error(f"Error in slow query detection: {e}")
                await asyncio.sleep(60)
    
    async def _detect_slow_queries(self):
        """Detecta e registra slow queries"""
        if not self._redis_client:
            return
        
        try:
            # Obtém slow log
            slowlog = await self._redis_client.slowlog_get(10)
            
            for entry in slowlog:
                slow_query = RedisSlowQuery(
                    id=entry['id'],
                    timestamp=datetime.fromtimestamp(entry['start_time']),
                    duration_ms=entry['duration'] / 1000,  # Convert microseconds to ms
                    command=' '.join(str(arg) for arg in entry['command'][:3]),  # Primeiros 3 args
                    key_pattern=self._extract_key_pattern(entry['command'])
                )
                
                # Evita duplicatas
                existing_ids = [sq.id for sq in self._slow_queries]
                if slow_query.id not in existing_ids:
                    self._slow_queries.append(slow_query)
                    
                    # Log slow query crítica (> 100ms)
                    if slow_query.duration_ms > 100:
                        logger.warning(
                            f"SLOW QUERY DETECTED: {slow_query.command} took {slow_query.duration_ms:.2f}ms"
                        )
            
        except Exception as e:
            logger.error(f"Error detecting slow queries: {e}")
    
    def _extract_key_pattern(self, command: List) -> Optional[str]:
        """Extrai padrão da chave do comando"""
        try:
            if len(command) < 2:
                return None
            
            key = str(command[1])
            
            # Remove IDs específicos para encontrar padrão
            import re
            
            # Substitui números por *
            pattern = re.sub(r'\d+', '*', key)
            
            # Substitui UUIDs por *
            pattern = re.sub(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', '*', pattern)
            
            return pattern if pattern != key else None
            
        except Exception:
            return None
    
    async def _latency_monitoring_loop(self):
        """Loop contínuo de monitoramento de latência"""
        while not self._stop_monitoring:
            try:
                # Teste de latência mais frequente
                await self._measure_latency()
                await asyncio.sleep(10)  # A cada 10 segundos
                
            except Exception as e:
                logger.error(f"Error in latency monitoring: {e}")
                await asyncio.sleep(10)
    
    async def _analysis_loop(self):
        """Loop de análise e alertas específicos do Redis"""
        while not self._stop_monitoring:
            try:
                await asyncio.sleep(300)  # A cada 5 minutos
                await self._analyze_redis_patterns()
                
            except Exception as e:
                logger.error(f"Error in Redis analysis: {e}")
    
    async def _analyze_redis_patterns(self):
        """Analisa padrões de uso do Redis"""
        if len(self._snapshots) < 10:  # Precisa de pelo menos 5 minutos de dados
            return
        
        recent_snapshots = list(self._snapshots)[-10:]
        
        # Análise de memory fragmentation
        avg_fragmentation = statistics.mean([s.mem_fragmentation_ratio for s in recent_snapshots])
        if avg_fragmentation > 1.5:
            logger.warning(
                f"HIGH MEMORY FRAGMENTATION: {avg_fragmentation:.2f} "
                f"(consider Redis restart or memory defragmentation)"
            )
        
        # Análise de hit rate degradation
        hit_rates = [s.hit_rate for s in recent_snapshots]
        if len(hit_rates) >= 5:
            recent_hit_rate = statistics.mean(hit_rates[-5:])
            older_hit_rate = statistics.mean(hit_rates[:5])
            
            if recent_hit_rate < older_hit_rate - 0.05:  # 5% degradation
                logger.warning(
                    f"HIT RATE DEGRADATION: {recent_hit_rate:.1%} vs {older_hit_rate:.1%} "
                    f"(may indicate cache warming needed)"
                )
        
        # Análise de eviction patterns
        eviction_rates = [s.evicted_keys_per_sec for s in recent_snapshots]
        avg_eviction_rate = statistics.mean(eviction_rates)
        
        if avg_eviction_rate > 100:  # Mais de 100 evictions/sec
            logger.warning(
                f"HIGH EVICTION RATE: {avg_eviction_rate:.1f} keys/sec "
                f"(consider increasing memory or reviewing TTL policies)"
            )
        
        # Análise de slow queries
        recent_slow_queries = [sq for sq in self._slow_queries if (datetime.now() - sq.timestamp).total_seconds() < 300]
        
        if len(recent_slow_queries) > 10:
            # Agrupa por padrão de comando
            command_patterns = defaultdict(list)
            for sq in recent_slow_queries:
                command_type = sq.command.split()[0] if sq.command else 'unknown'
                command_patterns[command_type].append(sq.duration_ms)
            
            for command_type, durations in command_patterns.items():
                if len(durations) >= 3:  # Pelo menos 3 ocorrências
                    avg_duration = statistics.mean(durations)
                    logger.warning(
                        f"FREQUENT SLOW QUERIES: {command_type} command "
                        f"averaging {avg_duration:.2f}ms ({len(durations)} occurrences)"
                    )
    
    async def _establish_performance_baseline(self):
        """Estabelece baseline de performance para comparações"""
        try:
            # Coleta várias amostras para estabelecer baseline
            baseline_samples = []
            
            for _ in range(5):
                snapshot = await self._collect_health_snapshot()
                if snapshot:
                    baseline_samples.append(snapshot)
                await asyncio.sleep(2)
            
            if baseline_samples:
                self._performance_baseline = {
                    'hit_rate': statistics.mean([s.hit_rate for s in baseline_samples]),
                    'avg_latency_ms': statistics.mean([s.avg_latency_ms for s in baseline_samples]),
                    'ops_per_sec': statistics.mean([s.ops_per_sec for s in baseline_samples]),
                    'memory_usage_percent': statistics.mean([s.used_memory_percent for s in baseline_samples]),
                    'established_at': datetime.now().isoformat()
                }
                
                logger.info(
                    f"Redis performance baseline established: "
                    f"hit_rate={self._performance_baseline['hit_rate']:.1%}, "
                    f"latency={self._performance_baseline['avg_latency_ms']:.2f}ms, "
                    f"ops/sec={self._performance_baseline['ops_per_sec']:.0f}"
                )
        
        except Exception as e:
            logger.error(f"Failed to establish performance baseline: {e}")
    
    async def _log_redis_status(self, snapshot: RedisHealthSnapshot):
        """Log resumo do status Redis"""
        logger.info(
            f"REDIS STATUS - Memory: {snapshot.used_memory_percent:.1f}% ({snapshot.used_memory_mb:.1f}MB) | "
            f"Hit Rate: {snapshot.hit_rate:.1%} | Latency: {snapshot.avg_latency_ms:.2f}ms | "
            f"OPS/sec: {snapshot.ops_per_sec} | Clients: {snapshot.connected_clients} | "
            f"Keys: {snapshot.total_keys:,} | Slow Queries: {snapshot.slow_queries_count}"
        )
    
    # Métodos públicos para consultas e relatórios
    
    async def get_current_status(self) -> Dict[str, Any]:
        """Obtém status atual do Redis"""
        if not self._snapshots:
            return {"status": "no_data"}
        
        latest = self._snapshots[-1]
        
        return {
            "timestamp": latest.timestamp.isoformat(),
            "snapshot": latest.to_dict(),
            "monitoring_duration": self._get_monitoring_duration(),
            "is_monitoring": self.is_monitoring,
            "baseline_comparison": self._compare_to_baseline(latest) if self._performance_baseline else None
        }
    
    async def get_performance_report(self, hours: int = 24) -> Dict[str, Any]:
        """Gera relatório de performance detalhado"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        period_snapshots = [
            s for s in self._snapshots
            if s.timestamp >= cutoff_time
        ]
        
        if not period_snapshots:
            return {"error": f"No data available for last {hours} hours"}
        
        # Slow queries do período
        period_slow_queries = [
            sq for sq in self._slow_queries
            if sq.timestamp >= cutoff_time
        ]
        
        # Estatísticas
        memory_usage = [s.used_memory_percent for s in period_snapshots]
        hit_rates = [s.hit_rate for s in period_snapshots]
        latencies = [s.avg_latency_ms for s in period_snapshots]
        ops_rates = [s.ops_per_sec for s in period_snapshots]
        
        return {
            "period_hours": hours,
            "timestamp": datetime.now().isoformat(),
            "data_points": len(period_snapshots),
            "memory_analysis": {
                "avg_usage_percent": round(statistics.mean(memory_usage), 1),
                "peak_usage_percent": round(max(memory_usage), 1),
                "min_usage_percent": round(min(memory_usage), 1),
                "current_usage_percent": round(memory_usage[-1], 1)
            },
            "performance_analysis": {
                "avg_hit_rate": round(statistics.mean(hit_rates) * 100, 1),
                "min_hit_rate": round(min(hit_rates) * 100, 1),
                "avg_latency_ms": round(statistics.mean(latencies), 2),
                "max_latency_ms": round(max(latencies), 2),
                "p95_latency_ms": round(statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies), 2),
                "avg_ops_per_sec": round(statistics.mean(ops_rates), 0),
                "peak_ops_per_sec": round(max(ops_rates), 0)
            },
            "slow_queries_analysis": {
                "total_slow_queries": len(period_slow_queries),
                "avg_slow_query_duration_ms": round(statistics.mean([sq.duration_ms for sq in period_slow_queries]), 2) if period_slow_queries else 0,
                "slowest_query_ms": round(max([sq.duration_ms for sq in period_slow_queries], default=0), 2),
                "most_common_slow_commands": self._analyze_slow_query_patterns(period_slow_queries)
            },
            "capacity_analysis": {
                "current_keys": period_snapshots[-1].total_keys,
                "key_growth_rate": self._calculate_key_growth_rate(period_snapshots),
                "memory_growth_rate": self._calculate_memory_growth_rate(period_snapshots),
                "projected_capacity": self._project_capacity_usage(period_snapshots)
            },
            "recommendations": self._generate_redis_recommendations(period_snapshots, period_slow_queries)
        }
    
    def _compare_to_baseline(self, snapshot: RedisHealthSnapshot) -> Dict[str, Any]:
        """Compara snapshot atual com baseline"""
        if not self._performance_baseline:
            return {}
        
        return {
            "hit_rate_change": round((snapshot.hit_rate - self._performance_baseline['hit_rate']) * 100, 1),
            "latency_change_ms": round(snapshot.avg_latency_ms - self._performance_baseline['avg_latency_ms'], 2),
            "ops_change": round(snapshot.ops_per_sec - self._performance_baseline['ops_per_sec'], 0),
            "memory_change_percent": round(snapshot.used_memory_percent - self._performance_baseline['memory_usage_percent'], 1)
        }
    
    def _analyze_slow_query_patterns(self, slow_queries: List[RedisSlowQuery]) -> List[Dict[str, Any]]:
        """Analisa padrões de slow queries"""
        if not slow_queries:
            return []
        
        command_stats = defaultdict(lambda: {'count': 0, 'total_duration': 0.0})
        
        for sq in slow_queries:
            command_type = sq.command.split()[0] if sq.command else 'unknown'
            command_stats[command_type]['count'] += 1
            command_stats[command_type]['total_duration'] += sq.duration_ms
        
        # Ordena por frequência
        sorted_commands = sorted(
            command_stats.items(),
            key=lambda x: x[1]['count'],
            reverse=True
        )[:5]  # Top 5
        
        return [
            {
                "command": cmd,
                "count": stats['count'],
                "avg_duration_ms": round(stats['total_duration'] / stats['count'], 2)
            }
            for cmd, stats in sorted_commands
        ]
    
    def _calculate_key_growth_rate(self, snapshots: List[RedisHealthSnapshot]) -> float:
        """Calcula taxa de crescimento de chaves por hora"""
        if len(snapshots) < 2:
            return 0.0
        
        start_keys = snapshots[0].total_keys
        end_keys = snapshots[-1].total_keys
        time_diff_hours = (snapshots[-1].timestamp - snapshots[0].timestamp).total_seconds() / 3600
        
        if time_diff_hours > 0 and start_keys > 0:
            growth_rate = ((end_keys - start_keys) / start_keys) / time_diff_hours * 100
            return round(growth_rate, 2)
        
        return 0.0
    
    def _calculate_memory_growth_rate(self, snapshots: List[RedisHealthSnapshot]) -> float:
        """Calcula taxa de crescimento de memória por hora"""
        if len(snapshots) < 2:
            return 0.0
        
        start_memory = snapshots[0].used_memory_mb
        end_memory = snapshots[-1].used_memory_mb
        time_diff_hours = (snapshots[-1].timestamp - snapshots[0].timestamp).total_seconds() / 3600
        
        if time_diff_hours > 0 and start_memory > 0:
            growth_rate = ((end_memory - start_memory) / start_memory) / time_diff_hours * 100
            return round(growth_rate, 2)
        
        return 0.0
    
    def _project_capacity_usage(self, snapshots: List[RedisHealthSnapshot]) -> Dict[str, Any]:
        """Projeta uso de capacidade baseado em tendências"""
        if len(snapshots) < 10:
            return {"status": "insufficient_data"}
        
        # Calcula tendência de uso de memória
        memory_usage = [s.used_memory_percent for s in snapshots]
        memory_trend = self._calculate_trend_slope(memory_usage)
        
        current_usage = memory_usage[-1]
        
        # Projeta quando atingirá 85% e 95%
        if memory_trend > 0:
            hours_to_85 = (85 - current_usage) / memory_trend if current_usage < 85 else 0
            hours_to_95 = (95 - current_usage) / memory_trend if current_usage < 95 else 0
            
            return {
                "current_usage_percent": round(current_usage, 1),
                "trend_per_hour": round(memory_trend, 2),
                "hours_to_85_percent": max(0, round(hours_to_85, 1)),
                "hours_to_95_percent": max(0, round(hours_to_95, 1)),
                "projected_full_in_days": round(hours_to_95 / 24, 1) if hours_to_95 > 0 else None
            }
        else:
            return {
                "current_usage_percent": round(current_usage, 1),
                "trend_per_hour": round(memory_trend, 2),
                "status": "stable_or_decreasing"
            }
    
    def _calculate_trend_slope(self, values: List[float]) -> float:
        """Calcula tendência usando regressão linear"""
        if len(values) < 2:
            return 0.0
        
        n = len(values)
        x = list(range(n))
        
        sum_x = sum(x)
        sum_y = sum(values)
        sum_xy = sum(x[i] * values[i] for i in range(n))
        sum_x2 = sum(x_val * x_val for x_val in x)
        
        denominator = n * sum_x2 - sum_x * sum_x
        if denominator == 0:
            return 0.0
        
        slope = (n * sum_xy - sum_x * sum_y) / denominator
        return slope
    
    def _generate_redis_recommendations(
        self,
        snapshots: List[RedisHealthSnapshot],
        slow_queries: List[RedisSlowQuery]
    ) -> List[str]:
        """Gera recomendações específicas para Redis"""
        recommendations = []
        
        if not snapshots:
            return recommendations
        
        latest = snapshots[-1]
        
        # Recomendações de memória
        if latest.used_memory_percent > 85:
            recommendations.append("Consider increasing Redis maxmemory or implementing more aggressive eviction policies")
        
        if latest.mem_fragmentation_ratio > 1.5:
            recommendations.append("High memory fragmentation detected - consider Redis restart during maintenance window")
        
        # Recomendações de performance
        if latest.hit_rate < 0.90:
            recommendations.append("Hit rate is below 90% - review cache warming strategies and data access patterns")
        
        if len(slow_queries) > 50:
            recommendations.append("High number of slow queries detected - review command patterns and consider query optimization")
        
        # Recomendações de conexões
        if latest.connected_clients > 5000:
            recommendations.append("High number of client connections - consider connection pooling optimization")
        
        # Recomendações de eviction
        avg_eviction_rate = statistics.mean([s.evicted_keys_per_sec for s in snapshots])
        if avg_eviction_rate > 50:
            recommendations.append("High key eviction rate - consider increasing memory or reviewing TTL policies")
        
        # Recomendações de latência
        avg_latency = statistics.mean([s.avg_latency_ms for s in snapshots])
        if avg_latency > 10:
            recommendations.append("Average latency is elevated - check network and Redis configuration")
        
        return recommendations
    
    def _get_monitoring_duration(self) -> str:
        """Retorna duração do monitoramento"""
        if not self._snapshots:
            return "0 minutes"
        
        start_time = self._snapshots[0].timestamp
        duration = datetime.now() - start_time
        
        hours = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)
        
        return f"{hours}h {minutes}m"


# Instância global do monitor Redis
redis_monitor = RedisMonitor()