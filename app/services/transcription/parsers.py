import os
import io
import time
from pathlib import Path
from typing import Iterator, Optional, List, Union, Literal
from enum import Enum

from loguru import logger
from langchain.document_loaders.blob_loaders import Blob
from langchain.schema import Document
from langchain_core.document_loaders import BaseBlobParser


class TranscriptionProvider(str, Enum):
    GROQ = "groq"
    OPENAI = "openai"
    FAST = "fast"
    LOCAL = "local"


class GroqWhisperParser(BaseBlobParser):
    """Transcribe and parse audio files using Groq's Whisper model."""

    def __init__(self, api_key: Optional[str] = None, language: Optional[str] = "en"):
        if not api_key:
            self.api_key = os.environ.get("GROQ_API_KEY")
        self.api_key = api_key
        self.language = language

    def lazy_parse(self, blob: Blob) -> Iterator[Document]:
        """Lazily parse the blob."""

        try:
            from groq import Groq
        except ImportError:
            raise ImportError(
                "groq package not found, please install it with "
                "`pip install groq`"
            )
        try:
            from pydub import AudioSegment
        except ImportError:
            raise ImportError(
                "pydub package not found, please install it with "
                "`pip install pydub`"
            )

        if not self.api_key:
            raise ValueError("GROQ_API_KEY not set.")

        client = Groq(api_key=self.api_key)

        # Audio file from disk
        audio = AudioSegment.from_file(blob.path)

        # Define the duration of each chunk in minutes
        # Adjust this value based on Groq's size limits if needed
        chunk_duration = 20
        chunk_duration_ms = chunk_duration * 60 * 1000

        # Split the audio into chunk_duration_ms chunks
        for split_number, i in enumerate(range(0, len(audio), chunk_duration_ms)):
            # Audio chunk
            chunk = audio[i: i + chunk_duration_ms]
            file_obj = io.BytesIO(chunk.export(format="mp3").read())
            if blob.source is not None:
                file_obj.name = f"{Path(blob.source).stem}_part_{split_number}.mp3"
            else:
                file_obj.name = f"part_{split_number}.mp3"

            # Transcribe
            logger.info(f"Transcrevendo parte {split_number + 1}!")
            attempts = 0
            while attempts < 3:
                try:
                    transcript = client.audio.transcriptions.create(
                        file=file_obj,
                        model="whisper-large-v3",
                        language=self.language,
                    )
                    break
                except Exception as e:
                    attempts += 1
                    logger.error(f"Tentativa {attempts} falhou. Exceção: {str(e)}")
                    time.sleep(5)
            else:
                logger.error("Falha ao transcrever após 3 tentativas.")
                continue

            yield Document(
                page_content=transcript.text,
                metadata={"source": blob.source, "chunk": split_number},
            )


class TranscriptionFactory:
    """Factory para criar parsers de transcrição baseados no provedor escolhido."""
    
    @staticmethod
    def get_parser_groq(**kwargs) -> GroqWhisperParser:
        api_key = kwargs.pop("api_key", os.environ.get("GROQ_API_KEY"))
        language = kwargs.pop("lang", "pt")
        logger.debug(f"Criando parser Groq com idioma: {language}")
        return GroqWhisperParser(
            api_key=api_key,
            language=language,
        )

    @staticmethod
    def get_parser_openai(**kwargs):
        try:
            from langchain_community.document_loaders.parsers import OpenAIWhisperParser
            api_key = kwargs.pop("api_key", os.environ.get("OPENAI_API_KEY"))
            language = kwargs.pop("lang", "pt")
            logger.debug(f"Criando parser OpenAI com idioma: {language}")
            return OpenAIWhisperParser(
                api_key=api_key,
                language=language,
            )
        except ImportError:
            raise ImportError(
                "langchain_community package not found, please install it with "
                "`pip install langchain_community`"
            )

    @staticmethod
    def get_parser_fast(**kwargs):
        try:
            from langchain_community.document_loaders.parsers.audio import FasterWhisperParser
            model_size = kwargs.pop("model_size", "base")
            device = kwargs.pop("device", "cpu")
            logger.debug(f"Criando parser Faster Whisper com tamanho do modelo: {model_size}, dispositivo: {device}")
            return FasterWhisperParser(
                model_size=model_size,
                device=device,
            )
        except ImportError:
            raise ImportError(
                "langchain_community package not found, please install it with "
                "`pip install langchain_community`"
            )

    @staticmethod
    def get_parser_local(**kwargs):
        try:
            from langchain_community.document_loaders.parsers.audio import OpenAIWhisperParserLocal
            language = kwargs.pop("lang", "pt")
            logger.debug(f"Criando parser Local Whisper com idioma: {language}")
            return OpenAIWhisperParserLocal(
                lang_model=language,
            )
        except ImportError:
            raise ImportError(
                "langchain_community package not found, please install it with "
                "`pip install langchain_community`"
            )

    @staticmethod
    def get_instance(name: TranscriptionProvider, **kwargs):
        logger.info(f"Criando instância de parser do tipo: {name}")
        method = {
            TranscriptionProvider.GROQ: TranscriptionFactory.get_parser_groq,
            TranscriptionProvider.OPENAI: TranscriptionFactory.get_parser_openai,
            TranscriptionProvider.FAST: TranscriptionFactory.get_parser_fast,
            TranscriptionProvider.LOCAL: TranscriptionFactory.get_parser_local,
        }[name]
        return method(**kwargs)
