#!/usr/bin/env python3
"""
Examinar dados de hash específicos no Redis
"""

import asyncio
import json
import os
from typing import Dict, Any
import redis.asyncio as redis
from datetime import datetime

# Adicionar o diretório atual ao PYTHONPATH
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.redis_connection import get_redis_client


async def examine_specific_audio_hashes():
    """Examina dados específicos de hash de áudio no Redis"""
    
    try:
        client = await get_redis_client()
        
        print("EXAMINANDO HASHES DE ÁUDIO ESPECÍFICOS")
        print("="*60)
        
        # Obter alguns IDs de exemplo
        audio_keys = await client.keys("audio:*")
        sample_ids = []
        
        for key_bytes in audio_keys:
            key = key_bytes.decode('utf-8') if isinstance(key_bytes, bytes) else key_bytes
            if key.startswith("audio:") and not key.startswith("audio:index:") and key != "audio:all_ids":
                video_id = key.replace("audio:", "")
                if len(video_id) == 11:  # YouTube video IDs
                    sample_ids.append(video_id)
                    if len(sample_ids) >= 3:  # Examinar 3 exemplos
                        break
        
        print(f"Examinando {len(sample_ids)} exemplos de hashes de áudio:")
        print(f"IDs selecionados: {sample_ids}")
        
        for i, video_id in enumerate(sample_ids, 1):
            print(f"\n{'-'*40}")
            print(f"EXEMPLO {i}: {video_id}")
            print(f"{'-'*40}")
            
            audio_key = f"audio:{video_id}"
            
            # Verificar se a chave existe
            exists = await client.exists(audio_key)
            print(f"Chave existe: {exists}")
            
            if exists:
                # Obter tipo
                key_type = await client.type(audio_key)
                type_str = key_type.decode('utf-8') if isinstance(key_type, bytes) else key_type
                print(f"Tipo: {type_str}")
                
                if type_str == "hash":
                    # Obter todos os campos do hash
                    hash_data = await client.hgetall(audio_key)
                    print(f"Número de campos: {len(hash_data)}")
                    
                    # Converter e organizar dados
                    clean_data = {}
                    for k, v in hash_data.items():
                        key_str = k.decode('utf-8', errors='replace') if isinstance(k, bytes) else k
                        val_str = v.decode('utf-8', errors='replace') if isinstance(v, bytes) else v
                        clean_data[key_str] = val_str
                    
                    # Mostrar campos organizados
                    print("\nCampos encontrados:")
                    for field in sorted(clean_data.keys()):
                        value = clean_data[field]
                        
                        # Mostrar preview do valor
                        if len(str(value)) > 100:
                            value_preview = str(value)[:100] + "..."
                        else:
                            value_preview = str(value)
                        
                        print(f"  {field}: {value_preview}")
                        
                        # Se for JSON, tentar parsear
                        if field.endswith('_json') or field in ['metadata', 'transcription', 'info']:
                            try:
                                parsed = json.loads(value)
                                print(f"    JSON parsed: {type(parsed)} com {len(parsed) if hasattr(parsed, '__len__') else 'N/A'} item(s)")
                                if isinstance(parsed, dict):
                                    for json_key in list(parsed.keys())[:3]:
                                        json_val = str(parsed[json_key])[:50] + "..." if len(str(parsed[json_key])) > 50 else str(parsed[json_key])
                                        print(f"      {json_key}: {json_val}")
                                    if len(parsed) > 3:
                                        print(f"      ... e mais {len(parsed) - 3} campos")
                            except:
                                pass
                
                elif type_str == "string":
                    value = await client.get(audio_key)
                    val_str = value.decode('utf-8', errors='replace') if isinstance(value, bytes) else value
                    print(f"Valor string: {val_str[:200]}{'...' if len(val_str) > 200 else ''}")
        
        # Verificar chave especial all_ids
        print(f"\n{'-'*60}")
        print("CHAVE ESPECIAL: audio:all_ids")
        print(f"{'-'*60}")
        
        all_ids_exists = await client.exists("audio:all_ids")
        print(f"audio:all_ids existe: {all_ids_exists}")
        
        if all_ids_exists:
            all_ids_type = await client.type("audio:all_ids")
            type_str = all_ids_type.decode('utf-8') if isinstance(all_ids_type, bytes) else all_ids_type
            print(f"Tipo: {type_str}")
            
            if type_str == "set":
                count = await client.scard("audio:all_ids")
                print(f"Número de IDs no set: {count}")
                if count > 0:
                    # Obter alguns membros
                    members = await client.srandmember("audio:all_ids", min(5, count))
                    clean_members = [m.decode('utf-8') if isinstance(m, bytes) else m for m in members]
                    print(f"Exemplos: {clean_members}")
            elif type_str == "list":
                count = await client.llen("audio:all_ids")
                print(f"Número de IDs na lista: {count}")
                if count > 0:
                    members = await client.lrange("audio:all_ids", 0, 4)
                    clean_members = [m.decode('utf-8') if isinstance(m, bytes) else m for m in members]
                    print(f"Exemplos: {clean_members}")
        
        # Verificar alguns índices de exemplo
        print(f"\n{'-'*60}")
        print("EXEMPLOS DE ÍNDICES")
        print(f"{'-'*60}")
        
        index_examples = [
            "audio:index:format:m4a",
            "audio:index:status:ended",
            "audio:index:date:2025-08"
        ]
        
        for index_key in index_examples:
            exists = await client.exists(index_key)
            print(f"\n{index_key}:")
            print(f"  Existe: {exists}")
            
            if exists:
                key_type = await client.type(index_key)
                type_str = key_type.decode('utf-8') if isinstance(key_type, bytes) else key_type
                print(f"  Tipo: {type_str}")
                
                if type_str == "set":
                    count = await client.scard(index_key)
                    print(f"  Membros: {count}")
                    if count > 0 and count <= 10:
                        members = await client.smembers(index_key)
                        clean_members = [m.decode('utf-8') if isinstance(m, bytes) else m for m in members]
                        print(f"  Lista: {sorted(clean_members)}")
                    elif count > 10:
                        members = await client.srandmember(index_key, 5)
                        clean_members = [m.decode('utf-8') if isinstance(m, bytes) else m for m in members]
                        print(f"  Exemplos (de {count}): {clean_members}")
        
    except Exception as e:
        print(f"ERRO: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(examine_specific_audio_hashes())