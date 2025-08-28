#!/usr/bin/env python
"""
Teste da nova configuração yt-dlp com estratégias anti-bot
"""

import requests
import json

# Token válido
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ5b3VyX2NsaWVudF9pZCIsImV4cCI6MTc1NjQwNzcwOH0._8sPC6glunOqUftuB5-jK6h5JSmW_Uucxst_B3o-gvo"

# URLs de teste
test_urls = [
    "https://www.youtube.com/watch?v=LX_LDCv1_nM",  # URL que falhou
    "https://www.youtube.com/watch?v=UL9NHOD-Xfo",  # URL que já funcionou antes
]

print("=" * 70)
print("TESTE DA NOVA CONFIGURAÇÃO YT-DLP")
print("=" * 70)

for i, url in enumerate(test_urls, 1):
    print(f"\n[TESTE {i}/2] {url}")
    
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "url": url,
        "high_quality": True
    }
    
    try:
        response = requests.post(
            "http://localhost:8000/audio/download",
            headers=headers,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Download iniciado!")
            print(f"      Audio ID: {result.get('audio_id', 'N/A')}")
            print(f"      Task ID: {result.get('task_id', 'N/A')}")
        else:
            print(f"   ❌ Erro: {response.status_code}")
            try:
                error = response.json()
                print(f"      Detalhe: {error.get('detail', response.text[:100])}")
            except:
                print(f"      Resposta: {response.text[:100]}...")
                
    except requests.exceptions.ConnectionError:
        print("   ❌ Servidor offline")
    except requests.exceptions.Timeout:
        print("   ❌ Timeout")
    except Exception as e:
        print(f"   ❌ Erro: {e}")

print(f"\n{'=' * 70}")
print("TESTE CONCLUÍDO")
print("=" * 70)