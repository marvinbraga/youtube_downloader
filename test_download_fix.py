#!/usr/bin/env python
"""
Teste para o erro de download de áudio
"""

import requests
import json

# Token e dados de teste
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ5b3VyX2NsaWVudF9pZCIsImV4cCI6MTc1NjQwNDc5MH0.1CAMp0hqneURLT9DnlprT5cQpJx40ZCJ5_cMuaR_W_A"
URL_TESTE = "https://www.youtube.com/watch?v=UL9NHOD-Xfo"  # URL do teste que falhou

def test_download():
    """Testar download de áudio"""
    print("="*60)
    print("TESTE DE DOWNLOAD DE AUDIO")
    print("="*60)
    
    # Dados do request
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "url": URL_TESTE,
        "high_quality": True
    }
    
    try:
        print(f"[INFO] Testando download: {URL_TESTE}")
        
        # Fazer requisição de download
        response = requests.post(
            "http://localhost:8000/audio/download",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"[OK] Download iniciado com sucesso!")
            print(f"     Audio ID: {result.get('audio_id', 'N/A')}")
            print(f"     Task ID: {result.get('task_id', 'N/A')}")
            print(f"     Mensagem: {result.get('message', 'N/A')}")
        elif response.status_code == 500:
            print(f"[ERRO] Erro interno do servidor (500)")
            try:
                error_data = response.json()
                print(f"       Detalhe: {error_data.get('detail', 'N/A')}")
            except:
                print(f"       Resposta raw: {response.text}")
        else:
            print(f"[ERRO] Status: {response.status_code}")
            print(f"       Resposta: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("[OFFLINE] Servidor não está rodando em localhost:8000")
    except requests.exceptions.Timeout:
        print("[TIMEOUT] Requisição demorou mais que 30 segundos")
    except Exception as e:
        print(f"[ERRO] Erro inesperado: {e}")

    print("\n" + "="*60)
    print("TESTE CONCLUÍDO")
    print("="*60)

if __name__ == "__main__":
    test_download()