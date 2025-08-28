#!/usr/bin/env python
"""
Teste direto do yt-dlp com nova configuração
"""

import yt_dlp
from pathlib import Path

# URL de teste
test_url = "https://www.youtube.com/watch?v=LX_LDCv1_nM"
test_dir = Path("E:/python/youtube_downloader/test_downloads")
test_dir.mkdir(exist_ok=True)

print("=" * 60)
print("TESTE DIRETO YT-DLP - NOVA CONFIGURACAO")
print("=" * 60)
print(f"URL: {test_url}")
print(f"Diretorio: {test_dir}")

# Configuração robusta anti-bot
ydl_opts = {
    'format': 'ba[ext=m4a]/ba[ext=webm]/ba[ext=mp4]/ba/bestaudio/best',
    'outtmpl': str(test_dir / '%(title)s.%(ext)s'),
    
    # Configurações de timeout e retry robustas
    'socket_timeout': 30,
    'retries': 15,
    'fragment_retries': 15,
    'retry_sleep': 'linear:1:3',
    'skip_unavailable_fragments': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'verbose': True,
    'noplaylist': True,
    
    # Rate limiting para evitar detecção de bot
    'sleep_interval': 2,
    'sleep_interval_requests': 1,
    'max_sleep_interval': 5,
    
    # Headers HTTP modernizados
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'pt-PT,pt;q=0.9,en-US;q=0.8,en;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'DNT': '1',
        'Upgrade-Insecure-Requests': '1',
    },
    
    # Configurações avançadas do extrator YouTube
    'extractor_args': {
        'youtube': {
            'skip': ['dash', 'hls'],
            'player_client': ['android_creator', 'web'],  # Usar clients mais estáveis
            'player_skip': ['configs'],
            'lang': ['pt-PT', 'pt', 'en'],
        }
    }
}

try:
    print("\n[INFO] Iniciando teste direto do yt-dlp...")
    print("[INFO] Extraindo apenas informações primeiro...")
    
    # Primeiro, tentar extrair apenas as informações
    info_opts = ydl_opts.copy()
    del info_opts['outtmpl']  # Remover template de saída
    
    with yt_dlp.YoutubeDL(info_opts) as ydl:
        print("[INFO] Tentando extrair info da URL...")
        info = ydl.extract_info(test_url, download=False)
        
        if info:
            print(f"   ✅ INFO EXTRAIDA COM SUCESSO!")
            print(f"      Titulo: {info.get('title', 'N/A')}")
            print(f"      Duracao: {info.get('duration', 'N/A')} segundos")
            print(f"      Formatos disponiveis: {len(info.get('formats', []))}")
            
            # Tentar download se info funcionou
            print(f"\n[INFO] Tentando download...")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl_download:
                ydl_download.download([test_url])
                print(f"   ✅ DOWNLOAD CONCLUIDO!")
        else:
            print(f"   ❌ Nenhuma info extraida")

except yt_dlp.DownloadError as e:
    error_msg = str(e)
    print(f"   ❌ ERRO YT-DLP: {error_msg[:150]}...")
    
    if "player response" in error_msg.lower():
        print(f"   ℹ️  CAUSA: Problema com extração do player response do YouTube")
        print(f"   💡 SUGESTAO: YouTube está bloqueando este tipo de acesso")
    elif "unavailable" in error_msg.lower():
        print(f"   ℹ️  CAUSA: Video não disponível ou privado")
    elif "sign in" in error_msg.lower():
        print(f"   ℹ️  CAUSA: Video requer login")
        
except Exception as e:
    print(f"   ❌ ERRO INESPERADO: {str(e)[:150]}...")

print(f"\n{'=' * 60}")
print("TESTE DIRETO CONCLUIDO")
print("=" * 60)