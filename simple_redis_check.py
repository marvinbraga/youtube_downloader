#!/usr/bin/env python3
"""
Verificação simples dos dados Redis
"""

import asyncio
import json
import os
from typing import Dict, Any
import redis.asyncio as redis

# Adicionar o diretório atual ao PYTHONPATH
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.redis_connection import get_redis_client


def safe_decode(value):
    """Decodifica bytes de forma segura"""
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    return value


def safe_print(text):
    """Print seguro para Windows"""
    try:
        # Remover caracteres problemáticos
        clean_text = str(text).encode('ascii', errors='ignore').decode('ascii')
        print(clean_text)
    except:
        print("--- text encoding error ---")


async def simple_redis_check():
    """Verificação simples dos dados Redis"""
    
    try:
        client = await get_redis_client()
        
        safe_print("=== VERIFICACAO SIMPLES REDIS ===")
        
        # 1. Contar chaves por padrão
        patterns = [
            "audio:*",
            "audio_info:*", 
            "audio_progress:*",
            "progress:*",
            "*progress*",
            "*audio*"
        ]
        
        safe_print("\n1. CONTAGEM DE CHAVES:")
        for pattern in patterns:
            keys = await client.keys(pattern)
            safe_print(f"  {pattern}: {len(keys)} chaves")
        
        # 2. Verificar tipos de dados para algumas chaves audio:*
        audio_keys = await client.keys("audio:*")
        video_id_keys = []
        special_keys = []
        
        for key_bytes in audio_keys:
            key = safe_decode(key_bytes)
            if key.startswith("audio:") and not key.startswith("audio:index:") and key != "audio:all_ids":
                video_id = key.replace("audio:", "")
                if len(video_id) == 11:
                    video_id_keys.append(video_id)
            else:
                special_keys.append(key)
        
        safe_print(f"\n2. ANALISE CHAVES AUDIO:")
        safe_print(f"  IDs de video: {len(video_id_keys)}")
        safe_print(f"  Chaves especiais: {len(special_keys)}")
        
        # 3. Examinar estrutura de dados de 2 IDs
        if video_id_keys:
            safe_print(f"\n3. ESTRUTURA DE DADOS (primeiros 2 IDs):")
            for i, video_id in enumerate(video_id_keys[:2], 1):
                safe_print(f"\n  ID {i}: {video_id}")
                
                audio_key = f"audio:{video_id}"
                key_type = await client.type(audio_key)
                type_str = safe_decode(key_type)
                safe_print(f"    Tipo: {type_str}")
                
                if type_str == "hash":
                    # Obter campos do hash
                    hash_data = await client.hgetall(audio_key)
                    safe_print(f"    Campos: {len(hash_data)}")
                    
                    # Listar campos sem valores para evitar encoding
                    fields = []
                    for k, v in hash_data.items():
                        field_name = safe_decode(k)
                        fields.append(field_name)
                    
                    safe_print(f"    Nomes dos campos: {sorted(fields)}")
        
        # 4. Verificar chave all_ids
        safe_print(f"\n4. CHAVE ALL_IDS:")
        all_ids_exists = await client.exists("audio:all_ids")
        safe_print(f"  audio:all_ids existe: {all_ids_exists}")
        
        if all_ids_exists:
            all_ids_type = await client.type("audio:all_ids")
            type_str = safe_decode(all_ids_type)
            safe_print(f"  Tipo: {type_str}")
            
            if type_str == "set":
                count = await client.scard("audio:all_ids")
                safe_print(f"  Membros no set: {count}")
            elif type_str == "list":
                count = await client.llen("audio:all_ids")
                safe_print(f"  Itens na lista: {count}")
        
        # 5. Verificar alguns índices
        safe_print(f"\n5. INDICES ESPECIAIS:")
        special_indexes = [
            "audio:index:status:ended",
            "audio:index:format:m4a",
            "audio:index:date:2025-08"
        ]
        
        for index_key in special_indexes:
            exists = await client.exists(index_key)
            if exists:
                key_type = await client.type(index_key)
                type_str = safe_decode(key_type)
                
                if type_str == "set":
                    count = await client.scard(index_key)
                    safe_print(f"  {index_key}: {count} membros")
                elif type_str == "list":
                    count = await client.llen(index_key)
                    safe_print(f"  {index_key}: {count} itens")
        
        # 6. Comparação com arquivos
        safe_print(f"\n6. COMPARACAO COM ARQUIVOS:")
        
        from pathlib import Path
        base_path = os.path.dirname(os.path.abspath(__file__))
        audio_path = Path(base_path) / "downloads" / "audio"
        
        physical_ids = set()
        if audio_path.exists():
            for item in audio_path.iterdir():
                if item.is_dir() and len(item.name) == 11:
                    physical_ids.add(item.name)
        
        redis_ids = set(video_id_keys)
        
        safe_print(f"  Arquivos fisicos: {len(physical_ids)} IDs")
        safe_print(f"  Redis audio hashes: {len(redis_ids)} IDs")
        safe_print(f"  Apenas no Redis: {len(redis_ids - physical_ids)}")
        safe_print(f"  Apenas em arquivos: {len(physical_ids - redis_ids)}")
        safe_print(f"  Em ambos: {len(redis_ids & physical_ids)}")
        
        if len(physical_ids - redis_ids) > 0:
            missing_in_redis = list(physical_ids - redis_ids)[:5]
            safe_print(f"  IDs faltando no Redis (primeiros 5): {missing_in_redis}")
        
        if len(redis_ids - physical_ids) > 0:
            missing_files = list(redis_ids - physical_ids)[:5]
            safe_print(f"  IDs sem arquivo (primeiros 5): {missing_files}")
        
    except Exception as e:
        safe_print(f"ERRO: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(simple_redis_check())