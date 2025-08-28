#!/usr/bin/env python
"""
Script para testar o endpoint de streaming de áudio
"""

import requests
import json

# Token de teste
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ5b3VyX2NsaWVudF9pZCIsImV4cCI6MTc1NjQwMjkxN30.W4qQxajRqR2cFaNGeeuyh3wjXK9Y6SyXECCMOiVVdEI"

# IDs de áudio para testar (baseados nos logs de erro)
test_ids = [
    "fYHCwZo0_sI",  # BRENO ALTMAN vs GUSTAVO MACHADO
    "yQ_AI3y7dfg",  # DaVinci Resolve para Iniciantes
    "zx4Ar2CN-_g",  # O Magistério Católico
    "invalid_id_test"  # ID inválido para testar erro 404
]

print("="*60)
print("TESTANDO ENDPOINT DE STREAMING DE ÁUDIO")
print("="*60)

for audio_id in test_ids:
    url = f"http://localhost:8000/audio/stream/{audio_id}?token={TOKEN}"
    
    try:
        # Fazer requisição GET
        response = requests.get(url, stream=True, timeout=5)
        
        if response.status_code == 200:
            # Obter informações do cabeçalho
            content_type = response.headers.get('Content-Type', 'Unknown')
            content_length = response.headers.get('Content-Length', 'Unknown')
            
            # Converter tamanho para MB se disponível
            if content_length != 'Unknown':
                size_mb = int(content_length) / (1024 * 1024)
                size_str = f"{size_mb:.2f} MB"
            else:
                size_str = "Unknown"
            
            print(f"[OK] {audio_id}: OK (Status: {response.status_code}, Tipo: {content_type}, Tamanho: {size_str})")
        elif response.status_code == 404:
            print(f"[ERRO] {audio_id}: NAO ENCONTRADO (Status: 404)")
        else:
            print(f"[AVISO] {audio_id}: ERRO (Status: {response.status_code})")
            
    except requests.exceptions.Timeout:
        print(f"[TIMEOUT] {audio_id}: TIMEOUT")
    except requests.exceptions.ConnectionError:
        print(f"[OFFLINE] {audio_id}: ERRO DE CONEXAO (servidor pode estar offline)")
    except Exception as e:
        print(f"[ERRO] {audio_id}: ERRO INESPERADO: {e}")

print("\n" + "="*60)
print("TESTE CONCLUÍDO")
print("="*60)