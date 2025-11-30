import os
import re
from pathlib import Path
from typing import List, Optional, Union, Dict, Iterable, Any

from loguru import logger
from langchain_community.document_loaders.blob_loaders import FileSystemBlobLoader
from langchain_community.document_loaders.blob_loaders.schema import Blob, BlobLoader
from langchain_community.document_loaders.generic import GenericLoader

from app.services.transcription.parsers import TranscriptionProvider, TranscriptionFactory
from app.services.configs import AUDIO_DIR, audio_mapping, AUDIO_CONFIG_PATH
from app.services.managers import AudioDownloadManager


class AudioLoader(BlobLoader):
    """Carrega arquivos de áudio do sistema de arquivos."""

    def __init__(
            self,
            file_path: str
    ):
        self.file_path = file_path
        logger.debug(f"AudioLoader inicializado com file_path: {file_path}")

    def yield_blobs(self) -> Iterable[Blob]:
        """Retorna blobs de áudio."""
        file = Path(self.file_path)
        logger.debug(f"Verificando arquivo: {file} (existe: {file.exists()})")
        
        if not file.exists():
            logger.error(f"Arquivo não encontrado: {self.file_path}")
            raise FileNotFoundError(f"Arquivo não encontrado: {self.file_path}")
        
        directory = file.parent
        filename = file.name
        
        logger.debug(f"Buscando arquivo em: {directory} com padrão: {filename}")
        
        # Simplificando a busca para exatamente o arquivo especificado
        loader = FileSystemBlobLoader(
            directory.as_posix(),
            glob=filename,
        )
        
        blobs = list(loader.yield_blobs())
        logger.debug(f"Encontrados {len(blobs)} blobs")
        
        if not blobs:
            logger.error(f"Nenhum blob encontrado para o padrão: {filename} em {directory}")
            raise FileNotFoundError(f"Nenhum blob encontrado para o arquivo: {file}")
            
        return blobs


class TranscriptionService:
    """Serviço para transcrição de arquivos de áudio."""
    
    @staticmethod
    def normalize_id(file_id: str) -> str:
        """
        Normaliza um ID para busca, removendo caracteres especiais 
        e convertendo para uma forma simplificada.
        
        Args:
            file_id: ID original do arquivo
            
        Returns:
            ID normalizado
        """
        # Remove caracteres não alfanuméricos (mantém apenas letras, números e espaços)
        normalized = re.sub(r'[^\w\s]', '', file_id)
        # Substitui múltiplos espaços por um único espaço
        normalized = re.sub(r'\s+', ' ', normalized)
        # Remove espaços no início e fim e converte para minúsculas
        normalized = normalized.strip().lower()
        return normalized
    
    @staticmethod
    def calculate_similarity(s1: str, s2: str) -> float:
        """
        Calcula a similaridade entre duas strings.
        Maior valor significa maior similaridade.
        
        Args:
            s1: Primeira string
            s2: Segunda string
            
        Returns:
            Valor de similaridade entre 0 e 1
        """
        # Normaliza ambas as strings
        s1 = TranscriptionService.normalize_id(s1)
        s2 = TranscriptionService.normalize_id(s2)
        
        # Se uma das strings estiver contida na outra, aumenta a pontuação
        if s1 in s2 or s2 in s1:
            # Calcula o tamanho da correspondência em relação ao tamanho das strings
            match_length = min(len(s1), len(s2))
            max_length = max(len(s1), len(s2))
            if max_length == 0:
                return 0
            return match_length / max_length
        
        # Se não há correspondência direta, verifica palavras em comum
        words1 = set(s1.split())
        words2 = set(s2.split())
        
        if not words1 or not words2:
            return 0
            
        # Calcula a interseção e união de palavras
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        if not union:
            return 0
            
        # Retorna o coeficiente de Jaccard (interseção/união)
        return len(intersection) / len(union)
    
    @staticmethod
    def get_audio_manager() -> AudioDownloadManager:
        """
        Obtém uma instância do gerenciador de áudio
        
        Returns:
            Instância do AudioDownloadManager
        """
        return AudioDownloadManager()
    
    @staticmethod
    def find_audio_file(file_id: str) -> Path:
        """
        Encontra um arquivo de áudio pelo ID.
        
        Args:
            file_id: ID do arquivo a ser localizado
            
        Returns:
            Caminho para o arquivo
            
        Raises:
            FileNotFoundError: Se o arquivo não for encontrado
        """
        # Primeiro verifica se é um ID de áudio no gerenciador
        audio_manager = TranscriptionService.get_audio_manager()
        audio_info = audio_manager.get_audio_info(file_id)
        
        if audio_info:
            # Se encontrou no gerenciador, retorna o caminho do arquivo
            logger.debug(f"Arquivo encontrado no gerenciador: {audio_info['path']}")
            audio_path = AUDIO_DIR.parent / audio_info['path']
            if audio_path.exists():
                return audio_path
            else:
                logger.warning(f"Caminho no gerenciador existe mas arquivo não encontrado: {audio_path}")
        
        # Primeiro procura no mapeamento de áudios
        if file_id in audio_mapping:
            file_path = audio_mapping[file_id]
            if isinstance(file_path, Path) and file_path.exists():
                return file_path
            elif isinstance(file_path, str) and Path(file_path).exists():
                return Path(file_path)
            else:
                logger.warning(f"Caminho no mapeamento existe mas arquivo não encontrado: {file_path}")
        
        # Normaliza o ID para busca
        normalized_id = TranscriptionService.normalize_id(file_id)
        logger.debug(f"Procurando arquivo com ID normalizado: '{normalized_id}' (original: '{file_id}')")
        
        # Variável para contar quantos arquivos foram verificados
        checked_files = 0
        possible_matches = []
        
        # Procura em todo o diretório de áudio de maneira recursiva (para encontrar arquivos em subdiretórios)
        for audio_file in AUDIO_DIR.glob("**/*.m4a"):
            checked_files += 1
            
            # Para cada arquivo, calcula a similaridade com o ID buscado
            file_name = audio_file.stem
            normalized_name = TranscriptionService.normalize_id(file_name)
            
            # Log detalhado para depuração
            logger.debug(f"Verificando arquivo: '{file_name}' (normalizado: '{normalized_name}')")
            
            # Calcula a similaridade entre o ID procurado e o nome do arquivo
            similarity = TranscriptionService.calculate_similarity(normalized_id, normalized_name)
            
            # Se houver alguma similaridade, adiciona à lista de possíveis correspondências
            if similarity > 0:
                possible_matches.append((audio_file, similarity))
                logger.debug(f"Possível correspondência encontrada: {audio_file} (similaridade: {similarity:.2f})")
        
        logger.debug(f"Verificados {checked_files} arquivos, encontradas {len(possible_matches)} possíveis correspondências")
        
        if possible_matches:
            # Ordena por similaridade (maior para menor)
            sorted_matches = sorted(possible_matches, key=lambda x: x[1], reverse=True)
            best_match = sorted_matches[0][0]
            logger.info(f"Melhor correspondência encontrada: {best_match} (similaridade: {sorted_matches[0][1]:.2f})")
            return best_match
        
        # Se não encontrar, tenta uma busca com critérios mais relaxados
        logger.warning(f"Nenhuma correspondência encontrada com ID normalizado. Tentando busca relaxada...")
        
        # Busca por qualquer parte do ID original em qualquer parte do nome do arquivo
        relaxed_matches = []
        for audio_file in AUDIO_DIR.glob("**/*.m4a"):
            # Verifica se qualquer parte do ID está contida no nome do arquivo
            # ou se qualquer parte do nome do arquivo está contida no ID
            if any(word.lower() in audio_file.stem.lower() for word in file_id.split() if len(word) > 3):
                relaxed_matches.append(audio_file)
                logger.debug(f"Correspondência relaxada encontrada: {audio_file}")
        
        if relaxed_matches:
            logger.info(f"Encontrada correspondência relaxada: {relaxed_matches[0]}")
            return relaxed_matches[0]
            
        # Se não encontrar por similaridade nem critérios relaxados, tenta o primeiro arquivo
        if checked_files > 0:
            logger.warning("Nenhuma correspondência encontrada. Tentando usar o arquivo mais recente.")
            
            # Obtém todos os arquivos de áudio e ordena por data de modificação (mais recente primeiro)
            all_audio_files = list(AUDIO_DIR.glob("**/*.m4a"))
            if all_audio_files:
                newest_file = max(all_audio_files, key=lambda x: x.stat().st_mtime)
                logger.info(f"Usando arquivo mais recente: {newest_file}")
                return newest_file
        
        # Se não encontrar de nenhuma forma, lança exceção
        logger.error(f"Arquivo de áudio não encontrado: {file_id}")
        raise FileNotFoundError(f"Arquivo de áudio não encontrado: {file_id}")
    
    @staticmethod
    def transcribe_audio(
        file_path: str, 
        provider: TranscriptionProvider = TranscriptionProvider.GROQ,
        language: str = "pt",
        **kwargs
    ) -> List[Dict]:
        """
        Transcreve um arquivo de áudio.
        
        Args:
            file_path: Caminho para o arquivo de áudio
            provider: Provedor de transcrição a ser usado
            language: Idioma do áudio
            **kwargs: Argumentos adicionais para o provedor de transcrição
            
        Returns:
            Lista de documentos com a transcrição
        """
        try:
            logger.info(f"Iniciando transcrição de áudio com provedor: {provider}")
            logger.debug(f"Arquivo de áudio: {file_path}")
            
            # Obtém o parser apropriado usando a fábrica
            parser = TranscriptionFactory.get_instance(
                name=provider,
                lang=language,
                **kwargs
            )
            
            loader = GenericLoader(
                blob_loader=AudioLoader(file_path=file_path),
                blob_parser=parser,
            )
            
            docs = loader.load()
            
            if not docs:
                logger.warning("Nenhum documento foi gerado na transcrição")
                return []
            
            logger.success(f"Transcrição concluída com sucesso: {len(docs)} documentos")
            return docs
            
        except Exception as e:
            logger.exception(f"Erro na transcrição: {str(e)}")
            raise

    @staticmethod
    def save_transcription(docs: List[Dict], output_path: Optional[str] = None) -> str:
        """
        Salva a transcrição em um arquivo markdown.
        
        Args:
            docs: Lista de documentos com a transcrição
            output_path: Caminho para o arquivo de saída (opcional)
            
        Returns:
            Caminho do arquivo salvo
        """
        if not docs:
            logger.error("Nenhum documento para salvar")
            raise ValueError("Nenhum documento para salvar")
            
        try:
            # Se não for fornecido um caminho de saída, cria um baseado no primeiro documento
            if not output_path:
                source = docs[0].metadata.get('source')
                if source:
                    output_path = f"{source}.md"
                else:
                    output_path = "transcription.md"
            
            # Concatena o conteúdo de todos os documentos
            text = "\n\n".join([d.page_content for d in docs])
            
            # Salva o arquivo
            filepath = Path(output_path)
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(text)

            logger.success(f"Transcrição salva com sucesso em: {filepath}")
            return str(filepath)
            
        except Exception as e:
            logger.exception(f"Erro ao salvar a transcrição: {str(e)}")
            raise
