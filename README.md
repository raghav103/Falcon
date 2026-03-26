# Falcon

Open-source repository documentation and chat agent powered by FastAPI, PostgreSQL, and OpenAI.

## Features

- **Git Repository Ingestion**: Clone and index any public Git repository into PostgreSQL
- **AI-Powered Chat**: Ask questions about codebases using natural language
- **Virtual Shell Tools**: LLM agent can explore repos using `list_files`, `read_file`, `search_code`
- **PostgreSQL Backend**: Efficient storage with pg_trgm full-text search
- **Server-Sent Events**: Real-time streaming responses
- **Secure by Default**: API key authentication, input validation, sanitized errors

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 14+
- OpenAI API key

### Installation

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd Falcon
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your values:
   # - DATABASE_URL (PostgreSQL connection string)
   # - OPENAI_API_KEY (required - get from https://platform.openai.com/api-keys)
   # - API_KEY (optional for development, required for production)
   ```

5. **Create database:**
   ```bash
   createdb falcon
   ```

6. **Run the server:**
   ```bash
   uvicorn backend.main:app --reload
   ```

   Server starts at `http://localhost:8000`

### Verify Installation

Check health endpoint:
```bash
curl http://localhost:8000/health
```

Expected response: `{"status":"ok"}`

## API Usage

### Authentication

All endpoints require an `X-API-Key` header (except `/health`).

In development mode without `API_KEY` set, authentication is skipped for easier testing.

### Ingest Repository

```bash
curl -X POST http://localhost:8000/repos \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"url": "https://github.com/expressjs/express"}'
```

Response:
```json
{
  "repo_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "ready",
  "file_count": 142
}
```

### List Repositories

```bash
curl http://localhost:8000/repos \
  -H "X-API-Key: your-api-key"
```

### Get Repository Details

```bash
curl http://localhost:8000/repos/{repo_id} \
  -H "X-API-Key: your-api-key"
```

### Chat with Repository

```bash
curl -N -X POST http://localhost:8000/repos/{repo_id}/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "question": "How does authentication work in this codebase?",
    "history": null
  }'
```

The response is a Server-Sent Events stream with events:
- `tool_start`: Agent starts executing a tool
- `tool_end`: Tool execution complete
- `text_delta`: Streamed text response
- `done`: Response complete
- `error`: Error occurred

### Delete Repository

```bash
curl -X DELETE http://localhost:8000/repos/{repo_id} \
  -H "X-API-Key: your-api-key"
```

## Architecture

```
backend/
├── main.py              # FastAPI app entry point
├── config.py            # Environment configuration with validation
├── db.py                # PostgreSQL connection pool
├── auth.py              # API key authentication
├── exceptions.py        # Custom exception hierarchy
├── logging_config.py    # Structured logging setup
├── routers/
│   └── repos.py         # API endpoints
├── services/
│   ├── agent.py         # ReAct agent loop (OpenAI function calling)
│   └── ingestion.py     # Git clone & file indexing
└── tools/
    ├── definitions.py   # OpenAI function schemas
    └── shell.py         # Virtual shell tools
```

### How It Works

1. **Ingestion**: Clone repo → Walk files → Filter (skip binaries, node_modules, etc.) → Batch insert into PostgreSQL → Delete clone
2. **Chat**: User question → LLM decides which tools to call → Backend executes SQL queries → LLM synthesizes answer → Stream to client
3. **Tools**: `list_files` (ls/find), `read_file` (cat/head/tail), `search_code` (ripgrep with pg_trgm)

No disk storage after ingestion. Everything lives in PostgreSQL.

## Development

### Run Tests

```bash
pytest
```

### Code Formatting & Linting

```bash
# Format code
black backend/

# Lint code
ruff check backend/

# Type check
mypy backend/
```

### Install Dev Dependencies

```bash
pip install -r requirements-dev.txt
```

## Configuration

See `.env.example` for all configuration options.

### Required

- `DATABASE_URL`: PostgreSQL connection string (e.g., `postgresql://localhost:5432/falcon`)
- `OPENAI_API_KEY`: Your OpenAI API key

### Optional

- `API_KEY`: API key for authentication (optional in development, required in production)
- `CORS_ORIGINS`: Comma-separated list of allowed origins (default: `http://localhost:3000,http://127.0.0.1:3000`)
- `LOG_LEVEL`: Logging level - DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)
- `ENVIRONMENT`: Environment name - development or production (default: development)
- `DB_MIN_CONNECTIONS`: Minimum pool size (default: 2)
- `DB_MAX_CONNECTIONS`: Maximum pool size (default: 10)
- `MAX_FILE_SIZE`: Maximum file size to index in bytes (default: 512000 = 500KB)

## Database Schema

The application automatically creates the schema on startup (idempotent).

### Tables

**repos**
- `id` (UUID): Primary key
- `url` (TEXT): Git repository URL (unique)
- `name` (TEXT): Repository name (e.g., "owner/repo")
- `status` (TEXT): "pending", "ingesting", "ready", or "error"
- `ingested_at` (TIMESTAMP): When ingestion started

**files**
- `id` (BIGSERIAL): Primary key
- `repo_id` (UUID): Foreign key to repos (CASCADE on delete)
- `path` (TEXT): File path (e.g., "src/auth/login.py")
- `name` (TEXT): File name (e.g., "login.py")
- `extension` (TEXT): File extension (e.g., ".py")
- `parent_path` (TEXT): Parent directory path
- `depth` (INTEGER): Directory depth
- `is_directory` (BOOLEAN): True for directories
- `content` (TEXT): File content (NULL for directories)

### Indexes

Optimized for virtual shell tools:
- `idx_dir_listing`: For `list_files` in directory mode
- `idx_file_name`: For `list_files` in find mode
- `idx_file_ext`: For `search_code` with glob filters
- `idx_content_search`: GIN index with pg_trgm for full-text search
- `idx_path_search`: GIN index for path glob matching

## Security

- **API Key Authentication**: All endpoints require `X-API-Key` header (except `/health`)
- **Input Validation**: Git URLs validated to prevent command injection
- **Safe Error Messages**: Internal errors logged, generic messages returned to clients
- **CORS**: Configurable origins, explicit methods and headers
- **Structured Logging**: All requests and errors logged with context

## Roadmap

See `architecture.md` for long-term architectural plans:
- Background job queue for async ingestion
- Incremental indexing for large repositories
- Advanced authentication (OAuth, JWT, user management)
- Observability improvements (metrics, tracing)
- Rate limiting
- Private repository support (SSH keys, tokens)

## License

MIT

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## Security

See [SECURITY.md](SECURITY.md) for security policy and vulnerability reporting.

---

**Built with:**
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [PostgreSQL](https://www.postgresql.org/) + [pg_trgm](https://www.postgresql.org/docs/current/pgtrgm.html) - Database with full-text search
- [asyncpg](https://github.com/MagicStack/asyncpg) - Fast async PostgreSQL driver
- [OpenAI](https://platform.openai.com/) - LLM API for agent functionality
