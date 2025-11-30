# app/db/database.py
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.db.models import Base, Audio
from app.services.configs import DATA_DIR

# Caminho do banco de dados SQLite
DATABASE_PATH = DATA_DIR / "youtube_downloader.db"
DATABASE_URL = f"sqlite+aiosqlite:///{DATABASE_PATH}"

# Engine assíncrono
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False}
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def init_db() -> None:
    """Inicializa o banco de dados criando as tabelas"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info(f"Banco de dados inicializado em: {DATABASE_PATH}")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency para obter uma sessão do banco"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """Context manager para obter uma sessão do banco"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def migrate_json_to_sqlite() -> None:
    """
    Migra os dados do arquivo JSON para SQLite.
    Apenas executa se o banco estiver vazio.
    """
    from app.services.configs import AUDIO_CONFIG_PATH

    async with get_db_context() as session:
        # Verifica se já existem dados
        from sqlalchemy import select, func
        result = await session.execute(select(func.count()).select_from(Audio))
        count = result.scalar()

        if count > 0:
            logger.info(f"Banco já contém {count} registros de áudio. Migração ignorada.")
            return

        # Carrega dados do JSON
        if not AUDIO_CONFIG_PATH.exists():
            logger.info("Arquivo JSON de áudios não encontrado. Nada para migrar.")
            return

        try:
            with open(AUDIO_CONFIG_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)

            audios = data.get("audios", [])
            if not audios:
                logger.info("Nenhum áudio encontrado no JSON para migrar.")
                return

            # Migra cada áudio
            for audio_data in audios:
                audio = Audio(
                    id=audio_data.get("id", ""),
                    title=audio_data.get("title", ""),
                    name=audio_data.get("name", ""),
                    youtube_id=audio_data.get("youtube_id"),
                    url=audio_data.get("url"),
                    path=audio_data.get("path", ""),
                    directory=audio_data.get("directory", ""),
                    format=audio_data.get("format", "m4a"),
                    filesize=audio_data.get("filesize", 0),
                    download_status=audio_data.get("download_status", "ready"),
                    download_progress=audio_data.get("download_progress", 100),
                    download_error=audio_data.get("download_error"),
                    transcription_status=audio_data.get("transcription_status", "none"),
                    transcription_path=audio_data.get("transcription_path", ""),
                    keywords=json.dumps(audio_data.get("keywords", [])),
                )

                # Parse das datas
                from datetime import datetime
                if audio_data.get("created_date"):
                    try:
                        audio.created_date = datetime.fromisoformat(audio_data["created_date"])
                    except:
                        audio.created_date = datetime.now()

                if audio_data.get("modified_date"):
                    try:
                        audio.modified_date = datetime.fromisoformat(audio_data["modified_date"])
                    except:
                        audio.modified_date = datetime.now()

                session.add(audio)

            await session.commit()
            logger.success(f"Migração concluída: {len(audios)} áudios migrados do JSON para SQLite")

        except Exception as e:
            logger.error(f"Erro durante migração JSON -> SQLite: {str(e)}")
            raise
