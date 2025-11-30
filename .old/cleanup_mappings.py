#!/usr/bin/env python3
"""
Script to clean up the mappings section in audios.json
Removes old/invalid entries and creates proper mappings for all audio files
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any

# Configurações
AUDIO_CONFIG_PATH = Path("data/audios.json")
DOWNLOADS_BASE = Path("E:/python/youtube_downloader/downloads")

def normalize_filename(filename: str) -> str:
    """
    Normaliza um nome de arquivo para ser usado como ID.
    Remove caracteres especiais e converte para minúsculas.
    """
    # Remove caracteres especiais, deixando apenas letras, números e espaços
    normalized = re.sub(r'[^\w\s]', ' ', filename.lower())
    # Substitui espaços múltiplos por um único espaço
    normalized = re.sub(r'\s+', ' ', normalized)
    # Substituir espaços por underscores para um ID mais limpo
    normalized = normalized.strip().replace(' ', '_')
    return normalized

def extract_keywords(title: str) -> List[str]:
    """
    Extrai palavras-chave de um título para facilitar a busca
    """
    # Normaliza o título
    normalized = normalize_filename(title)
    
    # Extrai as palavras
    words = normalized.split('_')
    
    # Filtra palavras muito curtas
    keywords = [word for word in words if len(word) > 3]
    
    # Adiciona o título normalizado completo
    keywords.append(normalized)
    
    return keywords

def cleanup_mappings():
    """
    Limpa e reconstrói a seção mappings do audios.json
    """
    print("=== Limpeza da Seção Mappings ===")
    
    # Carregar dados atuais
    if not AUDIO_CONFIG_PATH.exists():
        print(f"Arquivo não encontrado: {AUDIO_CONFIG_PATH}")
        return
    
    with open(AUDIO_CONFIG_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"Carregados {len(data['audios'])} arquivos de áudio")
    print(f"Mappings atuais: {len(data.get('mappings', {}))}")
    
    # Limpar mappings antigos
    old_mappings = data.get('mappings', {})
    data['mappings'] = {}
    
    # Estatísticas
    old_relative_removed = 0
    new_mappings_created = 0
    
    # Processar cada áudio e criar mappings corretos
    for audio in data.get('audios', []):
        audio_id = audio.get('id')
        title = audio.get('title', '')
        path = audio.get('path', '')
        
        if not audio_id or not path:
            print(f"AVISO: Áudio sem ID ou path válido: {audio.get('title', 'Desconhecido')}")
            continue
        
        # Caminho absoluto do arquivo
        absolute_path = str(DOWNLOADS_BASE / path)
        
        # 1. Mapping por ID do YouTube
        data['mappings'][audio_id] = absolute_path
        new_mappings_created += 1
        
        # 2. Mapping por título normalizado
        title_normalized = normalize_filename(title)
        if title_normalized and title_normalized != audio_id:
            data['mappings'][title_normalized] = absolute_path
            new_mappings_created += 1
        
        # 3. Mapping por nome do arquivo (sem extensão)
        if path:
            filename = Path(path).stem
            filename_normalized = normalize_filename(filename)
            if filename_normalized and filename_normalized not in [audio_id, title_normalized]:
                data['mappings'][filename_normalized] = absolute_path
                new_mappings_created += 1
        
        # 4. Mappings por palavras-chave (apenas as mais relevantes)
        keywords = extract_keywords(title)
        for keyword in keywords[:3]:  # Limitar a 3 palavras-chave mais relevantes
            if keyword not in data['mappings'] and len(keyword) > 4:
                data['mappings'][keyword] = absolute_path
                new_mappings_created += 1
    
    # Contar mappings antigos removidos (caminhos relativos antigos)
    for key in old_mappings:
        if old_mappings[key].startswith("audio/2025-"):
            old_relative_removed += 1
    
    print(f"\n=== Resultados da Limpeza ===")
    print(f"Mappings antigos removidos: {len(old_mappings)}")
    print(f"  - Caminhos relativos antigos: {old_relative_removed}")
    print(f"Novos mappings criados: {new_mappings_created}")
    print(f"Total final de mappings: {len(data['mappings'])}")
    
    # Backup do arquivo original
    backup_path = Path(str(AUDIO_CONFIG_PATH) + '.backup')
    with open(backup_path, 'w', encoding='utf-8') as f:
        json.dump({**data, 'mappings': old_mappings}, f, ensure_ascii=False, indent=2)
    print(f"Backup salvo em: {backup_path}")
    
    # Salvar dados limpos
    with open(AUDIO_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"Arquivo atualizado salvo em: {AUDIO_CONFIG_PATH}")
    
    # Relatório de verificação
    print(f"\n=== Verificação ===")
    missing_mappings = []
    for audio in data['audios']:
        audio_id = audio.get('id')
        if audio_id and audio_id not in data['mappings']:
            missing_mappings.append(audio_id)
    
    if missing_mappings:
        print(f"AVISO: {len(missing_mappings)} áudios sem mapeamento de ID:")
        for missing in missing_mappings[:5]:  # Mostrar apenas os primeiros 5
            print(f"  - {missing}")
        if len(missing_mappings) > 5:
            print(f"  ... e mais {len(missing_mappings) - 5}")
    else:
        print("✓ Todos os áudios têm mapeamento por ID")
    
    # Verificar arquivos com path/directory vazios
    empty_paths = []
    for audio in data['audios']:
        if not audio.get('path') or not audio.get('directory'):
            empty_paths.append(audio.get('id', 'Unknown'))
    
    if empty_paths:
        print(f"\nAVISO: {len(empty_paths)} áudios com path/directory vazio:")
        for empty in empty_paths:
            print(f"  - {empty}")
    
    print("\n=== Limpeza Concluída ===")

if __name__ == "__main__":
    cleanup_mappings()