# app/db/database.py
import json
from contextlib import asynccontextmanager
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
    DATABASE_URL, echo=False, connect_args={"check_same_thread": False}
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def init_db() -> None:
    """Inicializa o banco de dados criando as tabelas e aplicando migrações de schema."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _apply_schema_migrations(conn)
    logger.info(f"Banco de dados inicializado em: {DATABASE_PATH}")


async def _add_column_if_missing(
    conn, table: str, column: str, ddl_fragment: str, existing_cols: set
) -> None:
    """Adds a column via ALTER TABLE. Tolerates concurrent-startup race.

    The PRAGMA-read + ALTER write window is not atomic across SQLite
    connections — two workers can both observe the column missing and race
    on ADD COLUMN. The "duplicate column name" OperationalError is therefore
    treated as success: by the time we get it, the other worker won.
    """
    from sqlalchemy.exc import OperationalError

    if column in existing_cols:
        return
    try:
        await conn.exec_driver_sql(
            f"ALTER TABLE {table} ADD COLUMN {column} {ddl_fragment}"
        )
        logger.info(f"Coluna '{column}' adicionada em {table}")
    except OperationalError as exc:
        if "duplicate column name" in str(exc).lower():
            logger.info(f"Coluna '{column}' já existe em {table} (race resolvida)")
            return
        raise


async def _apply_schema_migrations(conn) -> None:
    """Aplica migrações idempotentes de schema para suporte multi-plataforma.

    Adiciona colunas `source` e `external_id` em `audios` e `external_id` em
    `videos`. Faz backfill de `external_id = youtube_id` e `source = 'youtube'`
    para linhas pré-existentes. Seguro para rodar em todo startup e para
    inicializações concorrentes (multi-worker uvicorn).
    """
    # --- audios ---
    result = await conn.exec_driver_sql("PRAGMA table_info(audios)")
    audio_cols = {row[1] for row in result.fetchall()}
    audio_needs_backfill = "source" not in audio_cols or "external_id" not in audio_cols

    await _add_column_if_missing(
        conn,
        "audios",
        "source",
        "VARCHAR(50) NOT NULL DEFAULT 'youtube'",
        audio_cols,
    )
    await _add_column_if_missing(
        conn, "audios", "external_id", "VARCHAR(100)", audio_cols
    )

    if audio_needs_backfill:
        await conn.exec_driver_sql(
            "UPDATE audios SET external_id = youtube_id "
            "WHERE external_id IS NULL AND youtube_id IS NOT NULL"
        )

    await conn.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_audios_source ON audios(source)"
    )
    await conn.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_audios_external_id ON audios(external_id)"
    )

    # --- videos ---
    result = await conn.exec_driver_sql("PRAGMA table_info(videos)")
    video_cols = {row[1] for row in result.fetchall()}
    video_needs_backfill = "external_id" not in video_cols

    await _add_column_if_missing(
        conn, "videos", "external_id", "VARCHAR(100)", video_cols
    )

    if video_needs_backfill:
        await conn.exec_driver_sql(
            "UPDATE videos SET external_id = youtube_id "
            "WHERE external_id IS NULL AND youtube_id IS NOT NULL"
        )

    await conn.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_videos_source ON videos(source)"
    )
    await conn.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_videos_external_id ON videos(external_id)"
    )

    # TODO(review): the two storage-column blocks below are near-identical
    # copy-paste. If a third storage-bearing table ever appears, extract
    # _add_storage_columns(conn, table_name). For two tables, inline is fine.
    # (code-reviewer, 2026-05-13, Severity: Low)
    # --- audios.storage_backend, audios.s3_key ---
    result = await conn.exec_driver_sql("PRAGMA table_info(audios)")
    audio_cols = {row[1] for row in result.fetchall()}
    await _add_column_if_missing(
        conn,
        "audios",
        "storage_backend",
        "VARCHAR(20) NOT NULL DEFAULT 'local'",
        audio_cols,
    )
    await _add_column_if_missing(conn, "audios", "s3_key", "VARCHAR(1000)", audio_cols)
    await conn.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_audios_storage_backend ON audios(storage_backend)"
    )

    # --- videos.storage_backend, videos.s3_key ---
    result = await conn.exec_driver_sql("PRAGMA table_info(videos)")
    video_cols = {row[1] for row in result.fetchall()}
    await _add_column_if_missing(
        conn,
        "videos",
        "storage_backend",
        "VARCHAR(20) NOT NULL DEFAULT 'local'",
        video_cols,
    )
    await _add_column_if_missing(conn, "videos", "s3_key", "VARCHAR(1000)", video_cols)
    await conn.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_videos_storage_backend ON videos(storage_backend)"
    )


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
            logger.info(
                f"Banco já contém {count} registros de áudio. Migração ignorada."
            )
            return

        # Carrega dados do JSON
        if not AUDIO_CONFIG_PATH.exists():
            logger.info("Arquivo JSON de áudios não encontrado. Nada para migrar.")
            return

        try:
            with open(AUDIO_CONFIG_PATH, "r", encoding="utf-8") as f:
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
                        audio.created_date = datetime.fromisoformat(
                            audio_data["created_date"]
                        )
                    except (ValueError, TypeError):
                        audio.created_date = datetime.now()

                if audio_data.get("modified_date"):
                    try:
                        audio.modified_date = datetime.fromisoformat(
                            audio_data["modified_date"]
                        )
                    except (ValueError, TypeError):
                        audio.modified_date = datetime.now()

                session.add(audio)

            await session.commit()
            logger.success(
                f"Migração concluída: {len(audios)} áudios migrados do JSON para SQLite"
            )

        except Exception as e:
            logger.error(f"Erro durante migração JSON -> SQLite: {str(e)}")
            raise
