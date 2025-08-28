#!/usr/bin/env python
"""
Script de Diagnóstico e Correção de Integridade de Áudios
Verifica e corrige inconsistências entre Redis, JSON e arquivos físicos
"""

import os
import json
import redis
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Tuple
import hashlib

class AudioIntegrityChecker:
    def __init__(self):
        self.redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)
        self.audio_dir = Path(r"E:\python\youtube_downloader\downloads\audio")
        self.json_file = Path(r"E:\python\youtube_downloader\data\audios.json")
        self.report = {
            "timestamp": datetime.now().isoformat(),
            "issues": [],
            "fixes_applied": [],
            "statistics": {}
        }
        
    def check_redis_connection(self) -> bool:
        """Verifica se Redis está disponível"""
        try:
            self.redis_client.ping()
            print("[OK] Redis conectado com sucesso")
            return True
        except Exception as e:
            print(f"[ERRO] Erro ao conectar ao Redis: {e}")
            return False
    
    def scan_physical_files(self) -> Dict[str, Dict]:
        """Escaneia arquivos físicos de áudio"""
        audio_files = {}
        
        for dir_path in self.audio_dir.iterdir():
            if dir_path.is_dir():
                video_id = dir_path.name
                audio_file = None
                metadata_file = None
                
                for file in dir_path.iterdir():
                    if file.suffix in ['.m4a', '.mp3', '.webm']:
                        audio_file = file
                    elif file.suffix == '.md':
                        metadata_file = file
                
                audio_files[video_id] = {
                    "has_audio": audio_file is not None,
                    "audio_path": str(audio_file) if audio_file else None,
                    "audio_size": audio_file.stat().st_size if audio_file else 0,
                    "has_metadata": metadata_file is not None,
                    "metadata_path": str(metadata_file) if metadata_file else None,
                    "directory": str(dir_path)
                }
        
        print(f"[INFO] Encontrados {len(audio_files)} diretorios de audio")
        return audio_files
    
    def scan_redis_data(self) -> Dict[str, Dict]:
        """Escaneia dados no Redis"""
        redis_data = {}
        
        # Buscar todos os hashes audio:[ID]
        audio_keys = self.redis_client.keys("audio:*")
        
        for key in audio_keys:
            if ":" in key and key.count(":") == 1:  # Pattern audio:[ID]
                video_id = key.split(":")[1]
                if not video_id.startswith("all") and not video_id.startswith("index"):
                    try:
                        data = self.redis_client.hgetall(key)
                        redis_data[video_id] = data
                    except:
                        pass
        
        # Verificar set all_ids
        all_ids = self.redis_client.smembers("audio:all_ids")
        
        print(f"[Redis] {len(redis_data)} registros de audio")
        print(f"[Redis] set 'all_ids': {len(all_ids)} IDs")
        
        return redis_data
    
    def scan_json_data(self) -> Dict[str, Dict]:
        """Escaneia dados no arquivo JSON"""
        json_data = {}
        
        if self.json_file.exists():
            with open(self.json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for audio in data.get("audios", []):
                    json_data[audio["id"]] = audio
        
        print(f"[JSON] {len(json_data)} registros de audio")
        return json_data
    
    def analyze_discrepancies(self, physical: Dict, redis_data: Dict, json_data: Dict) -> Dict:
        """Analisa discrepâncias entre as três fontes"""
        all_ids = set(physical.keys()) | set(redis_data.keys()) | set(json_data.keys())
        
        discrepancies = {
            "only_physical": [],
            "only_redis": [],
            "only_json": [],
            "missing_in_redis": [],
            "missing_in_json": [],
            "empty_directories": [],
            "corrupted_entries": []
        }
        
        for video_id in all_ids:
            in_physical = video_id in physical
            in_redis = video_id in redis_data
            in_json = video_id in json_data
            
            # Verificar onde existe
            if in_physical and not in_redis and not in_json:
                discrepancies["only_physical"].append(video_id)
            elif in_redis and not in_physical and not in_json:
                discrepancies["only_redis"].append(video_id)
            elif in_json and not in_physical and not in_redis:
                discrepancies["only_json"].append(video_id)
            
            # Verificar falta de sincronização
            if in_physical and not in_redis:
                discrepancies["missing_in_redis"].append(video_id)
            if in_physical and not in_json:
                discrepancies["missing_in_json"].append(video_id)
            
            # Verificar diretórios vazios
            if in_physical and not physical[video_id]["has_audio"]:
                discrepancies["empty_directories"].append(video_id)
        
        return discrepancies
    
    def fix_json_sync(self, physical: Dict, redis_data: Dict) -> int:
        """Reconstrói o arquivo JSON baseado em arquivos físicos e Redis"""
        new_audios = []
        mappings = {}
        
        # Priorizar dados do Redis, usar físico como fallback
        for video_id, phys_data in physical.items():
            if not phys_data["has_audio"]:
                continue  # Pular diretórios vazios
                
            audio_entry = {
                "id": video_id,
                "path": phys_data["audio_path"],
                "filesize": phys_data["audio_size"],
                "format": Path(phys_data["audio_path"]).suffix[1:] if phys_data["audio_path"] else "m4a"
            }
            
            # Enriquecer com dados do Redis se disponível
            if video_id in redis_data:
                redis_entry = redis_data[video_id]
                audio_entry.update({
                    "title": redis_entry.get("title", ""),
                    "url": redis_entry.get("url", f"https://youtube.com/watch?v={video_id}"),
                    "created_date": redis_entry.get("created_date", datetime.now().isoformat()),
                    "modified_date": redis_entry.get("modified_date", datetime.now().isoformat()),
                    "download_status": redis_entry.get("download_status", "ready"),
                    "has_transcription": redis_entry.get("has_transcription", "0") == "1",
                    "transcription_status": redis_entry.get("transcription_status", "pending"),
                    "transcription_path": redis_entry.get("transcription_path", ""),
                    "keywords": json.loads(redis_entry.get("keywords", "[]"))
                })
            else:
                # Dados mínimos se não houver no Redis
                title = Path(phys_data["audio_path"]).stem if phys_data["audio_path"] else f"Audio {video_id}"
                audio_entry.update({
                    "title": title,
                    "url": f"https://youtube.com/watch?v={video_id}",
                    "created_date": datetime.now().isoformat(),
                    "modified_date": datetime.now().isoformat(),
                    "download_status": "ready",
                    "has_transcription": phys_data["has_metadata"],
                    "transcription_status": "completed" if phys_data["has_metadata"] else "pending",
                    "transcription_path": phys_data["metadata_path"] or "",
                    "keywords": []
                })
            
            new_audios.append(audio_entry)
            mappings[video_id] = phys_data["audio_path"]
        
        # Salvar novo JSON
        new_json = {
            "audios": new_audios,
            "mappings": mappings,
            "last_sync": datetime.now().isoformat(),
            "total_count": len(new_audios)
        }
        
        # Backup do JSON antigo se existir
        if self.json_file.exists():
            backup_path = self.json_file.with_suffix(f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            self.json_file.rename(backup_path)
            print(f"[BACKUP] Criado: {backup_path}")
        
        # Salvar novo JSON
        with open(self.json_file, 'w', encoding='utf-8') as f:
            json.dump(new_json, f, indent=2, ensure_ascii=False)
        
        print(f"[OK] JSON reconstruido com {len(new_audios)} entradas")
        return len(new_audios)
    
    def fix_redis_sync(self, physical: Dict, json_data: Dict) -> int:
        """Sincroniza Redis com arquivos físicos"""
        fixes_applied = 0
        
        for video_id, phys_data in physical.items():
            if not phys_data["has_audio"]:
                continue
                
            redis_key = f"audio:{video_id}"
            
            # Se não existe no Redis, criar
            if not self.redis_client.exists(redis_key):
                # Usar dados do JSON se disponível
                if video_id in json_data:
                    json_entry = json_data[video_id]
                    redis_data = {
                        "id": video_id,
                        "title": json_entry.get("title", ""),
                        "url": json_entry.get("url", f"https://youtube.com/watch?v={video_id}"),
                        "path": phys_data["audio_path"],
                        "filesize": str(phys_data["audio_size"]),
                        "format": Path(phys_data["audio_path"]).suffix[1:],
                        "created_date": json_entry.get("created_date", datetime.now().isoformat()),
                        "modified_date": datetime.now().isoformat(),
                        "download_status": "ready",
                        "has_transcription": "1" if phys_data["has_metadata"] else "0",
                        "transcription_status": "completed" if phys_data["has_metadata"] else "pending",
                        "transcription_path": phys_data["metadata_path"] or "",
                        "keywords": json.dumps(json_entry.get("keywords", []))
                    }
                else:
                    # Criar entrada mínima
                    title = Path(phys_data["audio_path"]).stem if phys_data["audio_path"] else f"Audio {video_id}"
                    redis_data = {
                        "id": video_id,
                        "title": title,
                        "url": f"https://youtube.com/watch?v={video_id}",
                        "path": phys_data["audio_path"],
                        "filesize": str(phys_data["audio_size"]),
                        "format": Path(phys_data["audio_path"]).suffix[1:],
                        "created_date": datetime.now().isoformat(),
                        "modified_date": datetime.now().isoformat(),
                        "download_status": "ready",
                        "has_transcription": "1" if phys_data["has_metadata"] else "0",
                        "transcription_status": "completed" if phys_data["has_metadata"] else "pending",
                        "transcription_path": phys_data["metadata_path"] or "",
                        "keywords": "[]"
                    }
                
                self.redis_client.hset(redis_key, mapping=redis_data)
                fixes_applied += 1
        
        # Atualizar set all_ids
        all_physical_ids = [vid for vid, data in physical.items() if data["has_audio"]]
        if all_physical_ids:
            self.redis_client.delete("audio:all_ids")
            self.redis_client.sadd("audio:all_ids", *all_physical_ids)
            print(f"[OK] Redis set 'all_ids' atualizado com {len(all_physical_ids)} IDs")
        
        print(f"[OK] Redis sincronizado: {fixes_applied} novos registros adicionados")
        return fixes_applied
    
    def clean_empty_directories(self, physical: Dict) -> int:
        """Remove diretórios vazios"""
        removed = 0
        for video_id, data in physical.items():
            if not data["has_audio"]:
                try:
                    Path(data["directory"]).rmdir()
                    print(f"[LIMPO] Removido diretorio vazio: {video_id}")
                    removed += 1
                except Exception as e:
                    print(f"[AVISO] Nao foi possivel remover {video_id}: {e}")
        return removed
    
    def generate_report(self) -> str:
        """Gera relatório completo"""
        report_file = f"redis_audio_integrity_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(self.report, f, indent=2, ensure_ascii=False)
        return report_file
    
    def run(self, fix_issues: bool = False):
        """Executa verificação e correção de integridade"""
        print("\n" + "="*60)
        print("VERIFICACAO DE INTEGRIDADE DE AUDIOS")
        print("="*60 + "\n")
        
        # 1. Verificar conexões
        if not self.check_redis_connection():
            return
        
        # 2. Escanear todas as fontes
        print("\n[INFO] ESCANEANDO FONTES DE DADOS...")
        physical = self.scan_physical_files()
        redis_data = self.scan_redis_data()
        json_data = self.scan_json_data()
        
        # 3. Analisar discrepâncias
        print("\n[INFO] ANALISANDO DISCREPANCIAS...")
        discrepancies = self.analyze_discrepancies(physical, redis_data, json_data)
        
        # Estatísticas
        total_physical = len([v for v in physical.values() if v["has_audio"]])
        self.report["statistics"] = {
            "total_physical_files": total_physical,
            "total_redis_records": len(redis_data),
            "total_json_records": len(json_data),
            "empty_directories": len(discrepancies["empty_directories"]),
            "missing_in_redis": len(discrepancies["missing_in_redis"]),
            "missing_in_json": len(discrepancies["missing_in_json"])
        }
        
        # Exibir relatório
        print("\n" + "="*60)
        print("RELATORIO DE INTEGRIDADE")
        print("="*60)
        print(f"[OK] Arquivos fisicos validos: {total_physical}")
        print(f"[OK] Registros no Redis: {len(redis_data)}")
        print(f"[OK] Registros no JSON: {len(json_data)}")
        print(f"[AVISO] Diretorios vazios: {len(discrepancies['empty_directories'])}")
        print(f"[AVISO] Faltando no Redis: {len(discrepancies['missing_in_redis'])}")
        print(f"[AVISO] Faltando no JSON: {len(discrepancies['missing_in_json'])}")
        
        # Aplicar correções se solicitado
        if fix_issues:
            print("\n" + "="*60)
            print("APLICANDO CORRECOES")
            print("="*60 + "\n")
            
            # Corrigir JSON
            if discrepancies["missing_in_json"]:
                print("[INFO] Reconstruindo arquivo JSON...")
                fixed_json = self.fix_json_sync(physical, redis_data)
                self.report["fixes_applied"].append({
                    "type": "json_sync",
                    "entries_fixed": fixed_json
                })
            
            # Corrigir Redis
            if discrepancies["missing_in_redis"]:
                print("[INFO] Sincronizando Redis...")
                fixed_redis = self.fix_redis_sync(physical, json_data)
                self.report["fixes_applied"].append({
                    "type": "redis_sync",
                    "entries_fixed": fixed_redis
                })
            
            # Limpar diretórios vazios
            if discrepancies["empty_directories"]:
                print("[INFO] Limpando diretorios vazios...")
                cleaned = self.clean_empty_directories(physical)
                self.report["fixes_applied"].append({
                    "type": "clean_empty_dirs",
                    "directories_removed": cleaned
                })
            
            print("\n[OK] TODAS AS CORRECOES APLICADAS!")
        
        # Salvar relatório
        report_file = self.generate_report()
        print(f"\n[INFO] Relatorio salvo em: {report_file}")
        
        return self.report

if __name__ == "__main__":
    import sys
    
    # Verificar argumentos
    fix_mode = "--fix" in sys.argv or "-f" in sys.argv
    
    checker = AudioIntegrityChecker()
    
    if fix_mode:
        print("[MODO] Correcao ATIVADA - problemas serao corrigidos automaticamente")
        response = input("\n[AVISO] Isso ira modificar dados. Continuar? (s/n): ")
        if response.lower() != 's':
            print("Operação cancelada.")
            sys.exit(0)
    
    report = checker.run(fix_issues=fix_mode)
    
    if not fix_mode and report.get("statistics", {}).get("missing_in_json", 0) > 0:
        print("\n[DICA] Execute com --fix para corrigir automaticamente os problemas encontrados")
        print("   python redis_audio_integrity_test.py --fix")