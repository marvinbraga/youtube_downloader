#!/usr/bin/env python3
"""
Script para inspeção detalhada dos dados Redis vs arquivos físicos
Verifica sincronização entre Redis e sistema de arquivos
"""

import asyncio
import json
import os
import glob
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import redis.asyncio as redis

# Adicionar o diretório atual ao PYTHONPATH para importar os módulos
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.redis_connection import get_redis_client, is_redis_available


class RedisInspector:
    """Classe para inspeção dos dados Redis"""
    
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.downloads_path = self.base_path / "downloads"
        self.report = {
            "timestamp": datetime.now().isoformat(),
            "redis_status": None,
            "physical_files": [],
            "redis_data": {},
            "inconsistencies": [],
            "summary": {}
        }
    
    async def inspect_redis_connection(self) -> bool:
        """Verifica se Redis está disponível e conectável"""
        try:
            available = await is_redis_available()
            if available:
                client = await get_redis_client()
                await client.ping()
                self.report["redis_status"] = {
                    "available": True,
                    "connection": "success",
                    "message": "Redis is available and responding"
                }
                return True
        except Exception as e:
            self.report["redis_status"] = {
                "available": False,
                "connection": "failed",
                "error": str(e),
                "message": f"Failed to connect to Redis: {str(e)}"
            }
        return False
    
    def scan_physical_audio_files(self) -> List[Dict[str, Any]]:
        """Escaneia arquivos de áudio físicos no sistema"""
        audio_files = []
        
        # Padrões de áudio suportados
        audio_patterns = ['*.m4a', '*.mp3', '*.wav', '*.aac', '*.ogg', '*.flac']
        
        # Procurar recursivamente em downloads/audio/
        audio_base = self.downloads_path / "audio"
        
        if audio_base.exists():
            for pattern in audio_patterns:
                for audio_file in audio_base.rglob(pattern):
                    try:
                        # Extrair ID do vídeo do caminho
                        video_id = audio_file.parent.name
                        
                        # Verificar se há arquivo de metadados
                        metadata_file = audio_file.parent / f"{audio_file.stem}.md"
                        metadata = None
                        if metadata_file.exists():
                            try:
                                with open(metadata_file, 'r', encoding='utf-8') as f:
                                    # Assumir que metadados estão em formato markdown/texto simples
                                    metadata = f.read().strip()
                            except Exception as e:
                                metadata = f"Error reading metadata: {str(e)}"
                        
                        file_info = {
                            "video_id": video_id,
                            "file_path": str(audio_file),
                            "file_name": audio_file.name,
                            "file_size": audio_file.stat().st_size,
                            "created": datetime.fromtimestamp(audio_file.stat().st_ctime).isoformat(),
                            "modified": datetime.fromtimestamp(audio_file.stat().st_mtime).isoformat(),
                            "has_metadata": metadata is not None,
                            "metadata_preview": metadata[:200] + "..." if metadata and len(metadata) > 200 else metadata
                        }
                        audio_files.append(file_info)
                        
                    except Exception as e:
                        # Registrar arquivos com problemas
                        audio_files.append({
                            "video_id": "UNKNOWN",
                            "file_path": str(audio_file),
                            "file_name": audio_file.name,
                            "error": f"Failed to process: {str(e)}"
                        })
        
        self.report["physical_files"] = audio_files
        return audio_files
    
    async def scan_redis_audio_data(self) -> Dict[str, Any]:
        """Escaneia dados de áudio no Redis"""
        redis_data = {
            "audio_keys": [],
            "audio_info": {},
            "audio_progress": {},
            "audio_mappings": {},
            "other_audio_keys": [],
            "key_patterns": {}
        }
        
        try:
            client = await get_redis_client()
            
            # Escanear todas as chaves relacionadas a áudio
            patterns_to_check = [
                "audio:*",
                "audio_info:*", 
                "audio_progress:*",
                "audio_mapping:*",
                "progress:*:audio",
                "*:audio:*"
            ]
            
            all_audio_keys = set()
            
            for pattern in patterns_to_check:
                keys = await client.keys(pattern)
                redis_data["key_patterns"][pattern] = len(keys) if keys else 0
                if keys:
                    all_audio_keys.update(keys)
            
            # Converter para lista ordenada
            all_audio_keys = sorted(list(all_audio_keys))
            redis_data["audio_keys"] = all_audio_keys
            
            # Para cada chave, obter o tipo e valor
            for key in all_audio_keys:
                try:
                    key_type = await client.type(key)
                    
                    def convert_bytes_to_str(obj):
                        """Converte bytes para string recursivamente"""
                        if isinstance(obj, bytes):
                            return obj.decode('utf-8', errors='replace')
                        elif isinstance(obj, dict):
                            return {k.decode('utf-8', errors='replace') if isinstance(k, bytes) else k: 
                                   convert_bytes_to_str(v) for k, v in obj.items()}
                        elif isinstance(obj, list):
                            return [convert_bytes_to_str(item) for item in obj]
                        elif isinstance(obj, set):
                            return [convert_bytes_to_str(item) for item in obj]
                        return obj
                    
                    if key_type == "hash":
                        value = await client.hgetall(key)
                        value = convert_bytes_to_str(value)
                        if key.startswith("audio_info:"):
                            video_id = key.replace("audio_info:", "")
                            redis_data["audio_info"][video_id] = value
                        elif key.startswith("audio_progress:"):
                            video_id = key.replace("audio_progress:", "")
                            redis_data["audio_progress"][video_id] = value
                        else:
                            redis_data["other_audio_keys"].append({
                                "key": key,
                                "type": key_type,
                                "value": value
                            })
                    
                    elif key_type == "string":
                        value = await client.get(key)
                        value = convert_bytes_to_str(value)
                        if key.startswith("audio_mapping:"):
                            video_id = key.replace("audio_mapping:", "")
                            redis_data["audio_mappings"][video_id] = value
                        else:
                            redis_data["other_audio_keys"].append({
                                "key": key,
                                "type": key_type,
                                "value": value
                            })
                    
                    elif key_type == "list":
                        value = await client.lrange(key, 0, -1)
                        value = convert_bytes_to_str(value)
                        redis_data["other_audio_keys"].append({
                            "key": key,
                            "type": key_type,
                            "value": value
                        })
                    
                    elif key_type == "set":
                        value = await client.smembers(key)
                        value = convert_bytes_to_str(value)
                        redis_data["other_audio_keys"].append({
                            "key": key,
                            "type": key_type,
                            "value": value
                        })
                    
                except Exception as e:
                    redis_data["other_audio_keys"].append({
                        "key": key,
                        "error": f"Failed to read key: {str(e)}"
                    })
            
        except Exception as e:
            redis_data["error"] = f"Failed to scan Redis: {str(e)}"
        
        self.report["redis_data"] = redis_data
        return redis_data
    
    def analyze_inconsistencies(self) -> List[Dict[str, Any]]:
        """Analisa inconsistências entre Redis e arquivos físicos"""
        inconsistencies = []
        
        # Obter listas de IDs
        physical_video_ids = set()
        for file_info in self.report["physical_files"]:
            if "video_id" in file_info and file_info["video_id"] != "UNKNOWN":
                physical_video_ids.add(file_info["video_id"])
        
        redis_video_ids = set()
        if "audio_info" in self.report["redis_data"]:
            redis_video_ids.update(self.report["redis_data"]["audio_info"].keys())
        if "audio_progress" in self.report["redis_data"]:
            redis_video_ids.update(self.report["redis_data"]["audio_progress"].keys())
        if "audio_mappings" in self.report["redis_data"]:
            redis_video_ids.update(self.report["redis_data"]["audio_mappings"].keys())
        
        # Arquivos físicos sem dados no Redis
        orphaned_files = physical_video_ids - redis_video_ids
        if orphaned_files:
            inconsistencies.append({
                "type": "orphaned_physical_files",
                "description": "Arquivos físicos existem mas não há dados correspondentes no Redis",
                "video_ids": list(orphaned_files),
                "count": len(orphaned_files),
                "severity": "high"
            })
        
        # Dados Redis sem arquivos físicos
        orphaned_redis_data = redis_video_ids - physical_video_ids
        if orphaned_redis_data:
            inconsistencies.append({
                "type": "orphaned_redis_data", 
                "description": "Dados existem no Redis mas arquivos físicos correspondentes não foram encontrados",
                "video_ids": list(orphaned_redis_data),
                "count": len(orphaned_redis_data),
                "severity": "high"
            })
        
        # Verificar consistência interna do Redis
        redis_data = self.report["redis_data"]
        if "audio_info" in redis_data and "audio_progress" in redis_data:
            info_ids = set(redis_data["audio_info"].keys())
            progress_ids = set(redis_data["audio_progress"].keys())
            
            info_without_progress = info_ids - progress_ids
            if info_without_progress:
                inconsistencies.append({
                    "type": "missing_progress_data",
                    "description": "Áudios com informações mas sem dados de progresso no Redis",
                    "video_ids": list(info_without_progress),
                    "count": len(info_without_progress),
                    "severity": "medium"
                })
            
            progress_without_info = progress_ids - info_ids
            if progress_without_info:
                inconsistencies.append({
                    "type": "missing_info_data",
                    "description": "Áudios com dados de progresso mas sem informações no Redis",
                    "video_ids": list(progress_without_info),
                    "count": len(progress_without_info),
                    "severity": "medium"
                })
        
        self.report["inconsistencies"] = inconsistencies
        return inconsistencies
    
    def generate_summary(self) -> Dict[str, Any]:
        """Gera resumo da análise"""
        summary = {
            "redis_available": self.report["redis_status"]["available"] if self.report["redis_status"] else False,
            "total_physical_files": len(self.report["physical_files"]),
            "total_redis_keys": len(self.report["redis_data"].get("audio_keys", [])),
            "redis_audio_info_count": len(self.report["redis_data"].get("audio_info", {})),
            "redis_audio_progress_count": len(self.report["redis_data"].get("audio_progress", {})),
            "redis_audio_mappings_count": len(self.report["redis_data"].get("audio_mappings", {})),
            "total_inconsistencies": len(self.report["inconsistencies"]),
            "high_severity_issues": len([i for i in self.report["inconsistencies"] if i.get("severity") == "high"]),
            "medium_severity_issues": len([i for i in self.report["inconsistencies"] if i.get("severity") == "medium"]),
        }
        
        # Determinar status geral
        if not summary["redis_available"]:
            summary["overall_status"] = "redis_unavailable"
            summary["status_message"] = "Redis não está disponível - não é possível verificar sincronização"
        elif summary["high_severity_issues"] > 0:
            summary["overall_status"] = "critical_inconsistencies"
            summary["status_message"] = f"Encontradas {summary['high_severity_issues']} inconsistências críticas"
        elif summary["medium_severity_issues"] > 0:
            summary["overall_status"] = "minor_inconsistencies"
            summary["status_message"] = f"Encontradas {summary['medium_severity_issues']} inconsistências menores"
        else:
            summary["overall_status"] = "synchronized"
            summary["status_message"] = "Redis e arquivos físicos estão sincronizados"
        
        # Estatísticas por padrão de chave Redis
        if "key_patterns" in self.report["redis_data"]:
            summary["redis_key_patterns"] = self.report["redis_data"]["key_patterns"]
        
        self.report["summary"] = summary
        return summary
    
    async def run_full_inspection(self) -> Dict[str, Any]:
        """Executa inspeção completa"""
        print("Iniciando inspeção Redis vs Arquivos Físicos...")
        
        # 1. Verificar conexão Redis
        print("1. Verificando conexão Redis...")
        redis_available = await self.inspect_redis_connection()
        
        # 2. Escanear arquivos físicos
        print("2. Escaneando arquivos de áudio físicos...")
        physical_files = self.scan_physical_audio_files()
        
        # 3. Escanear dados Redis (se disponível)
        if redis_available:
            print("3. Escaneando dados Redis...")
            await self.scan_redis_audio_data()
        else:
            print("3. SKIP - Pulando scan Redis - não disponível")
        
        # 4. Analisar inconsistências
        print("4. Analisando inconsistências...")
        self.analyze_inconsistencies()
        
        # 5. Gerar resumo
        print("5. Gerando resumo...")
        self.generate_summary()
        
        return self.report


async def main():
    """Função principal"""
    base_path = os.path.dirname(os.path.abspath(__file__))
    inspector = RedisInspector(base_path)
    
    try:
        report = await inspector.run_full_inspection()
        
        # Converter todos os bytes para string antes de salvar
        def clean_for_json(obj):
            """Converte recursivamente bytes para string para serialização JSON"""
            if isinstance(obj, bytes):
                return obj.decode('utf-8', errors='replace')
            elif isinstance(obj, dict):
                return {
                    (k.decode('utf-8', errors='replace') if isinstance(k, bytes) else k): clean_for_json(v)
                    for k, v in obj.items()
                }
            elif isinstance(obj, (list, tuple)):
                return [clean_for_json(item) for item in obj]
            elif isinstance(obj, set):
                return [clean_for_json(item) for item in obj]
            return obj

        clean_report = clean_for_json(report)
        
        # Salvar relatório
        report_path = Path(base_path) / f"redis_inspection_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(clean_report, f, indent=2, ensure_ascii=False)
        
        # Imprimir resumo
        print("\n" + "="*80)
        print("RELATÓRIO DE SINCRONIZAÇÃO REDIS vs ARQUIVOS FÍSICOS")
        print("="*80)
        
        summary = report["summary"]
        redis_status = report["redis_status"]
        
        print(f"Redis Status: {'DISPONÍVEL' if redis_status['available'] else 'INDISPONÍVEL'}")
        if not redis_status['available']:
            print(f"   Erro: {redis_status.get('error', 'Unknown error')}")
        
        print(f"Arquivos físicos encontrados: {summary['total_physical_files']}")
        print(f"Chaves Redis encontradas: {summary['total_redis_keys']}")
        print(f"Dados audio_info no Redis: {summary['redis_audio_info_count']}")
        print(f"Dados audio_progress no Redis: {summary['redis_audio_progress_count']}")
        print(f"Mapeamentos Redis: {summary['redis_audio_mappings_count']}")
        
        print(f"\nStatus Geral: {summary['overall_status']}")
        print(f"Mensagem: {summary['status_message']}")
        
        print(f"\nInconsistências Encontradas: {summary['total_inconsistencies']}")
        print(f"   Alta prioridade: {summary['high_severity_issues']}")
        print(f"   Média prioridade: {summary['medium_severity_issues']}")
        
        if report["inconsistencies"]:
            print("\nDETALHES DAS INCONSISTÊNCIAS:")
            for i, inconsistency in enumerate(report["inconsistencies"], 1):
                severity_icon = "[HIGH]" if inconsistency["severity"] == "high" else "[MED]"
                print(f"\n{i}. {severity_icon} {inconsistency['type']}")
                print(f"   {inconsistency['description']}")
                print(f"   Afetados: {inconsistency['count']} itens")
                if inconsistency["count"] <= 10:  # Mostrar IDs se poucos
                    print(f"   IDs: {', '.join(inconsistency['video_ids'][:5])}")
                    if len(inconsistency["video_ids"]) > 5:
                        print(f"   ... e mais {len(inconsistency['video_ids']) - 5}")
        
        if redis_status['available'] and "key_patterns" in summary:
            print("\nPADRÕES DE CHAVES REDIS:")
            for pattern, count in summary["redis_key_patterns"].items():
                print(f"   {pattern}: {count} chaves")
        
        print(f"\nRelatório detalhado salvo em: {report_path}")
        print("="*80)
        
    except Exception as e:
        print(f"ERRO durante inspeção: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())