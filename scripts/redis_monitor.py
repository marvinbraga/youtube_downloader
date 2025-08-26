#!/usr/bin/env python3
"""
Redis Monitoring Script for YouTube Downloader
Agent-Infrastructure - FASE 1 do Plano de Migração Redis

Este script monitora a saúde e performance do Redis para o projeto YouTube Downloader.
Gera relatórios de status e alertas quando necessário.
"""

import json
import time
import subprocess
from datetime import datetime
from typing import Dict, Any

class RedisMonitor:
    def __init__(self, container_name: str = "gecon_backend-redis"):
        self.container_name = container_name
        self.alert_thresholds = {
            'memory_usage_mb': 100,  # Alert se usar mais que 100MB
            'max_latency_ms': 5.0,   # Alert se latência > 5ms
            'min_hit_rate': 0.9      # Alert se hit rate < 90%
        }
    
    def execute_redis_command(self, command: str) -> str:
        """Executa comando Redis via docker exec"""
        try:
            cmd = f'docker exec {self.container_name} redis-cli {command}'
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return result.stdout.strip()
        except Exception as e:
            return f"Error: {e}"
    
    def get_server_info(self) -> Dict[str, Any]:
        """Coleta informações básicas do servidor Redis"""
        info_sections = ['server', 'memory', 'stats', 'replication']
        redis_info = {}
        
        for section in info_sections:
            output = self.execute_redis_command(f'info {section}')
            section_data = {}
            
            for line in output.split('\n'):
                if line and not line.startswith('#'):
                    key, value = line.split(':', 1)
                    section_data[key] = value
            
            redis_info[section] = section_data
        
        return redis_info
    
    def check_latency(self, samples: int = 100) -> Dict[str, float]:
        """Testa latência do Redis"""
        output = self.execute_redis_command(f'--latency -i 1 -c {samples}')
        
        # Parse da saída de latência
        lines = output.split('\n')
        latencies = []
        
        for line in lines:
            if 'avg' in line:
                parts = line.split()
                avg_latency = float(parts[5])  # avg latency em ms
                max_latency = float(parts[7])  # max latency em ms
                
                return {
                    'avg_latency_ms': avg_latency,
                    'max_latency_ms': max_latency,
                    'samples': samples
                }
        
        return {'avg_latency_ms': 0.0, 'max_latency_ms': 0.0, 'samples': 0}
    
    def generate_health_report(self) -> Dict[str, Any]:
        """Gera relatório completo de saúde do Redis"""
        timestamp = datetime.now().isoformat()
        
        # Coleta informações
        info = self.get_server_info()
        latency = self.check_latency()
        
        # Calcula métricas importantes
        memory_used_mb = int(info['memory'].get('used_memory', 0)) / (1024 * 1024)
        memory_peak_mb = int(info['memory'].get('used_memory_peak', 0)) / (1024 * 1024)
        
        hits = int(info['stats'].get('keyspace_hits', 0))
        misses = int(info['stats'].get('keyspace_misses', 0))
        hit_rate = hits / (hits + misses) if (hits + misses) > 0 else 1.0
        
        # Status de saúde
        health_status = "healthy"
        alerts = []
        
        if memory_used_mb > self.alert_thresholds['memory_usage_mb']:
            health_status = "warning"
            alerts.append(f"High memory usage: {memory_used_mb:.1f}MB")
        
        if latency['max_latency_ms'] > self.alert_thresholds['max_latency_ms']:
            health_status = "warning"
            alerts.append(f"High latency: {latency['max_latency_ms']:.2f}ms")
        
        if hit_rate < self.alert_thresholds['min_hit_rate']:
            health_status = "warning"
            alerts.append(f"Low hit rate: {hit_rate:.1%}")
        
        report = {
            'timestamp': timestamp,
            'container': self.container_name,
            'health_status': health_status,
            'alerts': alerts,
            'redis_info': {
                'version': info['server'].get('redis_version', 'unknown'),
                'uptime_days': int(info['server'].get('uptime_in_days', 0)),
                'tcp_port': info['server'].get('tcp_port', 'unknown')
            },
            'memory': {
                'used_mb': round(memory_used_mb, 2),
                'peak_mb': round(memory_peak_mb, 2),
                'fragmentation_ratio': float(info['memory'].get('mem_fragmentation_ratio', 0))
            },
            'performance': {
                'avg_latency_ms': latency['avg_latency_ms'],
                'max_latency_ms': latency['max_latency_ms'],
                'hit_rate_percent': round(hit_rate * 100, 2),
                'ops_per_sec': int(info['stats'].get('instantaneous_ops_per_sec', 0))
            },
            'stats': {
                'total_connections': int(info['stats'].get('total_connections_received', 0)),
                'total_commands': int(info['stats'].get('total_commands_processed', 0)),
                'connected_clients': int(info['server'].get('connected_clients', 0))
            }
        }
        
        return report
    
    def save_report(self, report: Dict[str, Any], filepath: str):
        """Salva relatório em arquivo JSON"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving report: {e}")
            return False
    
    def print_summary(self, report: Dict[str, Any]):
        """Imprime resumo do relatório"""
        print(f"\n{'='*50}")
        print(f"Redis Health Report - {report['timestamp']}")
        print(f"{'='*50}")
        print(f"Status: {report['health_status'].upper()}")
        print(f"Redis Version: {report['redis_info']['version']}")
        print(f"Uptime: {report['redis_info']['uptime_days']} days")
        print(f"Memory Used: {report['memory']['used_mb']} MB")
        print(f"Avg Latency: {report['performance']['avg_latency_ms']:.3f} ms")
        print(f"Hit Rate: {report['performance']['hit_rate_percent']:.1f}%")
        
        if report['alerts']:
            print(f"\nALERTS:")
            for alert in report['alerts']:
                print(f"   * {alert}")
        else:
            print(f"\nAll systems green!")
        
        print(f"{'='*50}\n")

def main():
    """Função principal"""
    monitor = RedisMonitor()
    
    print("Starting Redis health check...")
    
    # Gera relatório
    report = monitor.generate_health_report()
    
    # Salva relatório
    report_file = f"redis_health_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    if monitor.save_report(report, report_file):
        print(f"Report saved to: {report_file}")
    
    # Exibe resumo
    monitor.print_summary(report)
    
    return 0 if report['health_status'] == 'healthy' else 1

if __name__ == "__main__":
    exit(main())