#!/usr/bin/env python3
"""
Script para inspeção detalhada específica dos dados Redis
Foca nos padrões de dados encontrados e estrutura das chaves
"""

import asyncio
import json
import os
from typing import Dict, List, Any
import redis.asyncio as redis
from datetime import datetime

# Adicionar o diretório atual ao PYTHONPATH
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.redis_connection import get_redis_client


async def inspect_redis_audio_structure():
    """Inspeção detalhada da estrutura dos dados de áudio no Redis"""
    
    try:
        client = await get_redis_client()
        
        print("INSPEÇÃO DETALHADA DOS DADOS REDIS")
        print("="*60)
        
        # 1. Verificar padrão audio:*
        audio_keys = await client.keys("audio:*")
        print(f"\n1. Chaves audio:* encontradas: {len(audio_keys)}")
        
        # Analisar diferentes tipos de chaves audio:
        audio_ids = []
        audio_special_keys = []
        
        for key_bytes in audio_keys:
            # Converter bytes para string
            key = key_bytes.decode('utf-8') if isinstance(key_bytes, bytes) else key_bytes
            
            if key.startswith("audio:") and not key.startswith("audio:index:") and key != "audio:all_ids":
                # Extrair ID do vídeo
                video_id = key.replace("audio:", "")
                if len(video_id) == 11:  # YouTube video IDs têm 11 caracteres
                    audio_ids.append(video_id)
                else:
                    audio_special_keys.append(key)
            else:
                audio_special_keys.append(key)
        
        print(f"   - IDs de vídeos: {len(audio_ids)}")
        print(f"   - Chaves especiais: {len(audio_special_keys)}")
        
        # Mostrar algumas chaves especiais
        if audio_special_keys:
            print("   Chaves especiais (primeiras 10):")
            for key in sorted(audio_special_keys)[:10]:
                print(f"     {key}")
            if len(audio_special_keys) > 10:
                print(f"     ... e mais {len(audio_special_keys) - 10}")
        
        # 2. Examinar estrutura de dados para alguns IDs
        print(f"\n2. Estrutura de dados para IDs de vídeo:")
        sample_ids = audio_ids[:5]  # Pegar 5 IDs para análise
        
        for video_id in sample_ids:
            print(f"\n   ID: {video_id}")
            audio_key = f"audio:{video_id}"
            
            # Verificar tipo da chave
            key_type = await client.type(audio_key)
            print(f"     Tipo: {key_type}")
            
            if key_type == "hash":
                # Obter todos os campos do hash
                hash_data = await client.hgetall(audio_key)
                if hash_data:
                    # Converter bytes para string
                    clean_data = {}
                    for k, v in hash_data.items():
                        key_str = k.decode('utf-8') if isinstance(k, bytes) else k
                        val_str = v.decode('utf-8') if isinstance(v, bytes) else v
                        clean_data[key_str] = val_str
                    
                    print(f"     Campos ({len(clean_data)}):")
                    for field, value in list(clean_data.items())[:5]:  # Mostrar 5 primeiros
                        value_preview = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                        print(f"       {field}: {value_preview}")
                    if len(clean_data) > 5:
                        print(f"       ... e mais {len(clean_data) - 5} campos")
            
            elif key_type == "string":
                value = await client.get(audio_key)
                if value:
                    val_str = value.decode('utf-8') if isinstance(value, bytes) else value
                    value_preview = val_str[:100] + "..." if len(val_str) > 100 else val_str
                    print(f"     Valor: {value_preview}")
        
        # 3. Verificar se há dados nos padrões esperados
        print(f"\n3. Verificando padrões de dados esperados:")
        
        patterns_to_check = [
            "audio_info:*",
            "audio_progress:*", 
            "audio_mapping:*",
            "progress:*:audio"
        ]
        
        for pattern in patterns_to_check:
            keys_bytes = await client.keys(pattern)
            keys = [k.decode('utf-8') if isinstance(k, bytes) else k for k in keys_bytes]
            print(f"   {pattern}: {len(keys)} chaves")
            if keys:
                print(f"     Exemplos: {keys[:3]}")
        
        # 4. Verificar chaves de índice
        print(f"\n4. Chaves de índice/metadados:")
        
        index_keys = []
        for key_bytes in audio_keys:
            key = key_bytes.decode('utf-8') if isinstance(key_bytes, bytes) else key_bytes
            if key.startswith("audio:index:"):
                index_keys.append(key)
        if index_keys:
            print(f"   Total de índices: {len(index_keys)}")
            
            # Agrupar por tipo de índice
            index_types = {}
            for key in index_keys:
                parts = key.split(":")
                if len(parts) >= 3:
                    index_type = parts[2]
                    if index_type not in index_types:
                        index_types[index_type] = []
                    index_types[index_type].append(key)
            
            for idx_type, keys in index_types.items():
                print(f"     {idx_type}: {len(keys)} índices")
                if len(keys) <= 5:
                    for key in keys:
                        print(f"       {key}")
                else:
                    print(f"       {keys[0]}")
                    print(f"       {keys[1]}")
                    print(f"       ... e mais {len(keys) - 2}")
        
        # 5. Verificar chave especial audio:all_ids
        print(f"\n5. Chave especial audio:all_ids:")
        all_ids_key = "audio:all_ids"
        if all_ids_key in audio_keys:
            key_type = await client.type(all_ids_key)
            print(f"   Tipo: {key_type}")
            
            if key_type == "set":
                count = await client.scard(all_ids_key)
                print(f"   Número de IDs: {count}")
                if count > 0:
                    # Mostrar alguns IDs
                    sample_ids = await client.srandmember(all_ids_key, 5)
                    clean_ids = [id.decode('utf-8') if isinstance(id, bytes) else id for id in sample_ids]
                    print(f"   Exemplos: {clean_ids}")
            elif key_type == "list":
                count = await client.llen(all_ids_key)
                print(f"   Número de IDs: {count}")
                if count > 0:
                    sample_ids = await client.lrange(all_ids_key, 0, 4)
                    clean_ids = [id.decode('utf-8') if isinstance(id, bytes) else id for id in sample_ids]
                    print(f"   Exemplos: {clean_ids}")
        
        # 6. Comparar com arquivos físicos
        print(f"\n6. Comparação rápida:")
        print(f"   IDs no Redis (audio:*): {len(audio_ids)}")
        
        # Contar arquivos físicos
        import os
        from pathlib import Path
        
        base_path = os.path.dirname(os.path.abspath(__file__))
        audio_path = Path(base_path) / "downloads" / "audio"
        
        physical_ids = set()
        if audio_path.exists():
            for item in audio_path.iterdir():
                if item.is_dir() and len(item.name) == 11:
                    physical_ids.add(item.name)
        
        print(f"   IDs físicos encontrados: {len(physical_ids)}")
        print(f"   IDs apenas no Redis: {len(set(audio_ids) - physical_ids)}")
        print(f"   IDs apenas em arquivos: {len(physical_ids - set(audio_ids))}")
        print(f"   IDs em ambos: {len(set(audio_ids) & physical_ids)}")
        
    except Exception as e:
        print(f"ERRO: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(inspect_redis_audio_structure())