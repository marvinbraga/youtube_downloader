"""
Monitor em Tempo Real do Sistema Redis - FASE 2
Monitoramento avançado com dashboard em terminal
"""

import asyncio
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
import json

from loguru import logger

# Adicionar path para importar módulos
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.services.redis_system_init import redis_system_manager, get_redis_system_status
from app.services.redis_connection import redis_manager


class RedisSystemMonitor:
    """
    Monitor avançado do Sistema Redis com dashboard em terminal
    Exibe métricas em tempo real, estatísticas e alertas
    """
    
    def __init__(self):
        self.running = False
        self.refresh_interval = 2.0  # segundos
        self.history_size = 100
        self.metrics_history: List[Dict[str, Any]] = []
        self.alert_thresholds = {
            "latency_ms": 50,
            "error_rate_percent": 5,
            "memory_usage_mb": 500,
            "connection_count": 200
        }
        
    async def start_monitoring(self):
        """Inicia monitoramento contínuo"""
        try:
            self.running = True
            
            logger.info("🔍 Iniciando Redis System Monitor...")
            logger.info("Pressione Ctrl+C para parar")
            
            while self.running:
                await self._update_and_display()
                await asyncio.sleep(self.refresh_interval)
                
        except KeyboardInterrupt:
            logger.info("⏹️ Monitor interrompido pelo usuário")
        except Exception as e:
            logger.error(f"Erro no monitor: {e}")
        finally:
            self.running = False
    
    async def _update_and_display(self):
        """Atualiza métricas e exibe dashboard"""
        try:
            # Coletar métricas
            metrics = await self._collect_metrics()
            
            # Adicionar ao histórico
            self._add_to_history(metrics)
            
            # Limpar tela e exibir dashboard
            self._clear_screen()
            self._display_dashboard(metrics)
            
        except Exception as e:
            logger.error(f"Erro ao atualizar display: {e}")
    
    async def _collect_metrics(self) -> Dict[str, Any]:
        """Coleta todas as métricas do sistema"""
        try:
            start_time = time.time()
            
            # Status do sistema
            system_status = await get_redis_system_status()
            
            # Health do Redis
            redis_health = await redis_manager.health_check()
            
            # Métricas de tempo
            collection_time = (time.time() - start_time) * 1000  # ms
            
            return {
                "timestamp": datetime.now(),
                "collection_time_ms": round(collection_time, 2),
                "system": system_status,
                "redis": redis_health,
                "alerts": self._check_alerts(system_status, redis_health)
            }
            
        except Exception as e:
            logger.error(f"Erro ao coletar métricas: {e}")
            return {
                "timestamp": datetime.now(),
                "error": str(e),
                "alerts": [{"type": "error", "message": f"Falha na coleta: {e}"}]
            }
    
    def _add_to_history(self, metrics: Dict[str, Any]):
        """Adiciona métricas ao histórico"""
        self.metrics_history.append(metrics)
        
        # Manter tamanho do histórico
        if len(self.metrics_history) > self.history_size:
            self.metrics_history.pop(0)
    
    def _check_alerts(self, system_status: Dict[str, Any], redis_health: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Verifica condições de alerta"""
        alerts = []
        
        try:
            # Alert de latência
            ping_time = redis_health.get('ping_time_ms', 0)
            if ping_time > self.alert_thresholds["latency_ms"]:
                alerts.append({
                    "type": "warning",
                    "category": "latency",
                    "message": f"Alta latência Redis: {ping_time}ms",
                    "threshold": self.alert_thresholds["latency_ms"]
                })
            
            # Alert de componentes não saudáveis
            components = system_status.get('components', {})
            unhealthy = [name for name, comp in components.items() 
                        if comp.get('status') != 'healthy']
            
            if unhealthy:
                alerts.append({
                    "type": "error",
                    "category": "components",
                    "message": f"Componentes não saudáveis: {', '.join(unhealthy)}",
                    "count": len(unhealthy)
                })
            
            # Alert de uso de memória
            used_memory = redis_health.get('used_memory', 0)
            if used_memory > self.alert_thresholds["memory_usage_mb"] * 1024 * 1024:
                alerts.append({
                    "type": "warning",
                    "category": "memory",
                    "message": f"Alto uso de memória: {redis_health.get('used_memory_human', 'N/A')}",
                    "value": used_memory
                })
            
            # Alert de conexões
            connected_clients = redis_health.get('connected_clients', 0)
            if connected_clients > self.alert_thresholds["connection_count"]:
                alerts.append({
                    "type": "warning",
                    "category": "connections",
                    "message": f"Muitas conexões: {connected_clients}",
                    "threshold": self.alert_thresholds["connection_count"]
                })
                
        except Exception as e:
            alerts.append({
                "type": "error",
                "category": "monitor",
                "message": f"Erro na verificação de alertas: {e}"
            })
        
        return alerts
    
    def _clear_screen(self):
        """Limpa a tela do terminal"""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def _display_dashboard(self, metrics: Dict[str, Any]):
        """Exibe dashboard principal"""
        try:
            timestamp = metrics["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
            
            print("=" * 80)
            print("🔍 REDIS SYSTEM MONITOR - FASE 2".center(80))
            print(f"⏰ {timestamp} | 🔄 Atualizando a cada {self.refresh_interval}s".center(80))
            print("=" * 80)
            
            # Status geral
            self._display_system_overview(metrics)
            
            # Componentes
            self._display_components_status(metrics)
            
            # Redis health
            self._display_redis_health(metrics)
            
            # Estatísticas de performance
            self._display_performance_stats(metrics)
            
            # Alertas
            self._display_alerts(metrics)
            
            # Histórico de latência
            self._display_latency_graph()
            
            print("=" * 80)
            print("💡 Pressione Ctrl+C para parar o monitor".center(80))
            print("=" * 80)
            
        except Exception as e:
            print(f"❌ Erro ao exibir dashboard: {e}")
    
    def _display_system_overview(self, metrics: Dict[str, Any]):
        """Exibe overview geral do sistema"""
        try:
            system = metrics.get("system", {})
            system_health = system.get("system_health", {})
            
            status = system_health.get("status", "unknown")
            healthy_components = system_health.get("healthy_components", 0)
            total_components = system_health.get("total_components", 0)
            uptime_seconds = system_health.get("uptime_seconds", 0)
            
            # Converter uptime
            uptime_str = self._format_uptime(uptime_seconds)
            
            # Status emoji
            status_emoji = {
                "healthy": "✅",
                "degraded": "⚠️",
                "unhealthy": "❌",
                "unknown": "❓"
            }.get(status, "❓")
            
            print("\n📊 VISÃO GERAL DO SISTEMA")
            print("-" * 40)
            print(f"Status: {status_emoji} {status.upper()}")
            print(f"Componentes: {healthy_components}/{total_components} saudáveis")
            print(f"Uptime: {uptime_str}")
            print(f"Inicializado: {'✅ Sim' if system.get('initialized') else '❌ Não'}")
            
        except Exception as e:
            print(f"❌ Erro no overview: {e}")
    
    def _display_components_status(self, metrics: Dict[str, Any]):
        """Exibe status dos componentes"""
        try:
            components = metrics.get("system", {}).get("components", {})
            
            print("\n🔧 COMPONENTES")
            print("-" * 40)
            
            if not components:
                print("Nenhum componente encontrado")
                return
            
            for name, info in components.items():
                status = info.get("status", "unknown")
                
                status_emoji = {
                    "healthy": "✅",
                    "unhealthy": "❌",
                    "failed": "💥",
                    "shutdown": "⏹️"
                }.get(status, "❓")
                
                init_time = info.get("init_time_ms", 0)
                error_count = info.get("error_count", 0)
                
                print(f"{status_emoji} {name:<20} | Init: {init_time:>6.1f}ms | Erros: {error_count}")
                
        except Exception as e:
            print(f"❌ Erro nos componentes: {e}")
    
    def _display_redis_health(self, metrics: Dict[str, Any]):
        """Exibe saúde do Redis"""
        try:
            redis_health = metrics.get("redis", {})
            
            print("\n🗄️ REDIS HEALTH")
            print("-" * 40)
            
            if redis_health.get("status") != "healthy":
                print(f"❌ Status: {redis_health.get('status', 'unknown')}")
                if "error" in redis_health:
                    print(f"   Erro: {redis_health['error']}")
                return
            
            ping_time = redis_health.get("ping_time_ms", 0)
            version = redis_health.get("redis_version", "unknown")
            memory = redis_health.get("used_memory_human", "unknown")
            clients = redis_health.get("connected_clients", 0)
            
            # Pool stats se disponível
            pool_stats = redis_health.get("pool_stats", {})
            max_conn = pool_stats.get("max_connections", 0)
            created_conn = pool_stats.get("created_connections", 0)
            available_conn = pool_stats.get("available_connections", 0)
            
            print(f"✅ Status: HEALTHY | Ping: {ping_time:.2f}ms")
            print(f"📝 Versão: {version} | Memória: {memory}")
            print(f"👥 Clientes: {clients} | Pool: {created_conn}/{max_conn} (disponível: {available_conn})")
            
            # Cache hit rate
            hits = redis_health.get("keyspace_hits", 0)
            misses = redis_health.get("keyspace_misses", 0)
            total_ops = hits + misses
            
            if total_ops > 0:
                hit_rate = (hits / total_ops) * 100
                print(f"🎯 Cache Hit Rate: {hit_rate:.1f}% ({hits} hits, {misses} misses)")
            
        except Exception as e:
            print(f"❌ Erro no Redis health: {e}")
    
    def _display_performance_stats(self, metrics: Dict[str, Any]):
        """Exibe estatísticas de performance"""
        try:
            stats = metrics.get("system", {}).get("statistics", {})
            
            print("\n⚡ PERFORMANCE")
            print("-" * 40)
            
            # Stats de progresso
            progress_stats = stats.get("progress", {})
            if progress_stats:
                tasks_by_status = progress_stats.get("tasks_by_status", {})
                active_tasks = progress_stats.get("active_tasks", 0)
                total_events = progress_stats.get("total_events", 0)
                
                print(f"📋 Tarefas Ativas: {active_tasks}")
                print(f"📊 Total de Eventos: {total_events}")
                
                # Status breakdown
                status_summary = []
                for status, count in tasks_by_status.items():
                    if count > 0:
                        status_summary.append(f"{status}: {count}")
                
                if status_summary:
                    print(f"📈 Status: {' | '.join(status_summary)}")
            
            # Stats de notificações
            notification_stats = stats.get("notifications", {})
            if notification_stats:
                clients = notification_stats.get("clients_connected", 0)
                messages_sent = notification_stats.get("messages_sent", 0)
                delivery_rate = notification_stats.get("performance", {}).get("delivery_rate", "N/A")
                
                print(f"📱 Clientes Conectados: {clients}")
                print(f"📤 Mensagens Enviadas: {messages_sent}")
                print(f"📊 Taxa de Entrega: {delivery_rate}")
            
            # Tempo de coleta
            collection_time = metrics.get("collection_time_ms", 0)
            print(f"⏱️ Tempo de Coleta: {collection_time:.2f}ms")
            
        except Exception as e:
            print(f"❌ Erro nas estatísticas: {e}")
    
    def _display_alerts(self, metrics: Dict[str, Any]):
        """Exibe alertas ativos"""
        try:
            alerts = metrics.get("alerts", [])
            
            if not alerts:
                print("\n✅ ALERTAS: Nenhum alerta ativo")
                return
            
            print(f"\n🚨 ALERTAS ({len(alerts)} ativos)")
            print("-" * 40)
            
            for alert in alerts:
                alert_type = alert.get("type", "info")
                message = alert.get("message", "Alerta sem mensagem")
                category = alert.get("category", "unknown")
                
                type_emoji = {
                    "error": "❌",
                    "warning": "⚠️",
                    "info": "ℹ️"
                }.get(alert_type, "❓")
                
                print(f"{type_emoji} [{category.upper()}] {message}")
                
        except Exception as e:
            print(f"❌ Erro nos alertas: {e}")
    
    def _display_latency_graph(self):
        """Exibe gráfico simples de latência"""
        try:
            if len(self.metrics_history) < 2:
                return
            
            print("\n📈 LATÊNCIA REDIS (últimos 20 pontos)")
            print("-" * 40)
            
            # Pegar últimos 20 pontos
            recent_metrics = self.metrics_history[-20:]
            latencies = []
            
            for m in recent_metrics:
                redis_health = m.get("redis", {})
                ping = redis_health.get("ping_time_ms", 0)
                latencies.append(ping)
            
            if not latencies:
                print("Sem dados de latência")
                return
            
            max_latency = max(latencies)
            min_latency = min(latencies)
            avg_latency = sum(latencies) / len(latencies)
            
            # Gráfico ASCII simples
            print(f"Min: {min_latency:.1f}ms | Max: {max_latency:.1f}ms | Avg: {avg_latency:.1f}ms")
            
            # Barra de escala
            scale_max = max(max_latency, 50)  # Pelo menos 50ms de escala
            bar_width = 60
            
            graph_line = ""
            for latency in latencies[-bar_width:]:
                if latency == 0:
                    char = "▁"
                elif latency < scale_max * 0.2:
                    char = "▂"
                elif latency < scale_max * 0.4:
                    char = "▃"
                elif latency < scale_max * 0.6:
                    char = "▅"
                elif latency < scale_max * 0.8:
                    char = "▆"
                else:
                    char = "▇"
                
                graph_line += char
            
            print(f"Gráfico: {graph_line}")
            print(f"Escala: 0ms ────────────────────────────── {scale_max:.0f}ms")
            
        except Exception as e:
            print(f"❌ Erro no gráfico: {e}")
    
    def _format_uptime(self, seconds: float) -> str:
        """Formata tempo de uptime"""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m{secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h{minutes}m"
    
    def stop_monitoring(self):
        """Para o monitoramento"""
        self.running = False


async def main():
    """Função principal do monitor"""
    monitor = RedisSystemMonitor()
    
    try:
        await monitor.start_monitoring()
    except Exception as e:
        logger.error(f"Erro no monitor principal: {e}")


if __name__ == "__main__":
    # Configurar logger para não interferir com o display
    logger.remove()
    logger.add(
        "logs/redis_monitor.log",
        rotation="1 day",
        retention="7 days",
        level="INFO"
    )
    
    # Executar monitor
    asyncio.run(main())