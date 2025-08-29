"""
Módulo de locks compartilhados para sincronização de acesso a recursos críticos
"""
import threading

# Lock global para compatibilidade (audios.json removido)
# Usando RLock para permitir re-entradas da mesma thread
audio_file_lock = threading.RLock()