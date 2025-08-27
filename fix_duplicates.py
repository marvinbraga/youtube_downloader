#!/usr/bin/env python3
"""
Script para limpar duplicações no arquivo audios.json
"""

import json
from pathlib import Path
from datetime import datetime

def fix_duplicates():
    # Carregar dados
    json_path = Path("data/audios.json")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Dicionário para armazenar áudios únicos
    unique_audios = {}
    
    # Processar cada áudio
    for audio in data["audios"]:
        audio_id = audio["id"]
        
        if audio_id not in unique_audios:
            # Primeira ocorrência, adicionar
            unique_audios[audio_id] = audio
        else:
            # Duplicata encontrada, mesclar dados
            existing = unique_audios[audio_id]
            
            # Priorizar o registro com path preenchido
            if audio.get("path") and not existing.get("path"):
                unique_audios[audio_id] = audio
            elif existing.get("path") and not audio.get("path"):
                # Manter o existente que tem path
                pass
            else:
                # Ambos têm path ou nenhum tem, mesclar dados relevantes
                # Priorizar o mais recente ou com melhor status
                if audio.get("download_status") == "ready" and existing.get("download_status") != "ready":
                    unique_audios[audio_id] = audio
                elif audio.get("filesize", 0) > existing.get("filesize", 0):
                    unique_audios[audio_id] = audio
                elif audio.get("modified_date", "") > existing.get("modified_date", ""):
                    unique_audios[audio_id] = audio
    
    # Reconstruir a estrutura
    data["audios"] = list(unique_audios.values())
    
    # Fazer backup antes de salvar
    backup_path = json_path.with_suffix(f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(backup_path, "w", encoding="utf-8") as f:
        with open(json_path, "r", encoding="utf-8") as orig:
            f.write(orig.read())
    
    print(f"Backup criado: {backup_path}")
    
    # Salvar dados limpos
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Removidas duplicações. Total de áudios únicos: {len(unique_audios)}")
    
if __name__ == "__main__":
    fix_duplicates()