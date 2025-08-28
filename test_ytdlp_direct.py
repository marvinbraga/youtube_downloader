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

# Configuração simples baseada no manager original funcionando
ydl_opts = {
    'format': 'bestaudio/best',
    'outtmpl': str(test_dir / '%(title)s.%(ext)s'),
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'm4a',
        'preferredquality': '192',
    }],
    'socket_timeout': 30,
    'retries': 10,
    'fragment_retries': 10,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'verbose': True,
    'noplaylist': True,
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'DNT': '1',
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
            print(f"   SUCCESS - INFO EXTRAIDA!")
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
    print(f"   ERROR YT-DLP: {error_msg[:150]}...")
    
    if "player response" in error_msg.lower():
        print(f"   ℹ️  CAUSA: Problema com extração do player response do YouTube")
        print(f"   💡 SUGESTAO: YouTube está bloqueando este tipo de acesso")
    elif "unavailable" in error_msg.lower():
        print(f"   ℹ️  CAUSA: Video não disponível ou privado")
    elif "sign in" in error_msg.lower():
        print(f"   ℹ️  CAUSA: Video requer login")
        
except Exception as e:
    print(f"   ERROR INESPERADO: {str(e)[:150]}...")

print(f"\n{'=' * 60}")
print("TESTE DIRETO CONCLUIDO")
print("=" * 60)