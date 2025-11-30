# YouTube Downloader

Serviço FastAPI para download e streaming de vídeos/áudio do YouTube com suporte a transcrição.

## Funcionalidades

- Download de vídeos e áudio do YouTube via yt-dlp
- Streaming de vídeo/áudio em tempo real
- Fila de downloads assíncrona com prioridade e retry
- Progresso em tempo real via Server-Sent Events (SSE)
- Transcrição de áudio (Groq/OpenAI)
- Autenticação JWT
- Persistência em SQLite
- Interface web para gerenciamento

## Requisitos

- Python 3.10 - 3.12
- [uv](https://docs.astral.sh/uv/) (gerenciador de pacotes)

## Instalação

```bash
# Clonar repositório
git clone <repo-url>
cd youtube_downloader

# Instalar dependências
uv sync

# Instalar com dependências de desenvolvimento
uv sync --extra dev
```

## Configuração

Crie um arquivo `.env` na raiz do projeto:

```env
JWT_SECRET=sua_chave_secreta
GROQ_API_KEY=sua_chave_groq      # opcional, para transcrição
OPENAI_API_KEY=sua_chave_openai  # opcional, para transcrição
```

## Execução

```bash
# Iniciar servidor
uv run uvicorn app.uwtv.main:app --reload --host 0.0.0.0 --port 8000
```

O servidor estará disponível em `http://localhost:8000`.

## Endpoints Principais

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/auth/token` | Autenticação (retorna JWT) |
| POST | `/audio/download` | Iniciar download de áudio |
| GET | `/audio/download-status/{id}` | Status do download |
| GET | `/audio/stream/{id}` | Stream de áudio |
| GET | `/audio/list` | Listar áudios baixados |
| POST | `/video/download` | Iniciar download de vídeo |
| GET | `/video/stream/{id}` | Stream de vídeo |
| POST | `/transcription/transcribe` | Transcrever áudio |
| GET | `/downloads/events` | SSE para progresso |

## Arquitetura

```
app/
├── core/           # Logging e configurações gerais
├── db/             # Database (SQLite + SQLAlchemy)
│   ├── database.py # Engine e sessões
│   ├── models.py   # Modelos Audio/Video
│   └── repositories.py
├── models/         # Pydantic models (request/response)
├── services/       # Lógica de negócio
│   ├── managers.py # Gerenciadores de stream/download
│   ├── download_queue.py # Fila assíncrona
│   ├── sse_manager.py    # Server-Sent Events
│   └── transcription/    # Serviço de transcrição
└── uwtv/
    └── main.py     # FastAPI app e endpoints
```

## Estrutura de Dados

```
data/
└── youtube_downloader.db    # SQLite database

downloads/
├── audio/{youtube_id}/      # Áudios baixados
└── video/{youtube_id}/      # Vídeos baixados
```

## Cliente Web

O diretório `web_client/` contém uma interface web para interagir com a API.

## Tecnologias

- **FastAPI** - Framework web
- **yt-dlp** - Download de vídeos
- **SQLAlchemy** + **aiosqlite** - ORM e banco de dados
- **SSE-Starlette** - Server-Sent Events
- **Groq/OpenAI** - Transcrição de áudio
- **PyJWT** - Autenticação

## Licença

MIT
