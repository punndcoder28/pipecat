# Voice Agent Recording UI

A real-time voice agent application built with [Pipecat](https://github.com/pipecat-ai/pipecat) that records conversations, tracks turn latencies, and simulates/detects bot freezes. Designed for analyzing voice agent performance and user experience.

## Features

- **Real-time Voice Conversations**: WebRTC-based voice interactions with smart turn detection
- **Configurable AI Services**: Swappable STT, LLM, and TTS providers via environment variables
- **Session Recording**: Stereo audio capture (user on left channel, bot on right)
- **Transcript Storage**: Full conversation history with timestamps
- **Turn Latency Tracking**: Measures response time for each conversation turn
- **Freeze Simulation & Detection**: Simulates random bot freezes for testing UI resilience
- **REST API**: Query sessions, transcripts, latencies, and freeze events
- **Interactive API Docs**: Swagger UI and ReDoc documentation

## Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Client (Browser)                                │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     Prebuilt WebRTC UI                               │    │
│  │                  (pipecat-ai-small-webrtc)                          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │ WebRTC (Audio/Data)
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            FastAPI Backend                                   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐  │
│  │   /api/sessions  │  │  /start (WebRTC) │  │   /client (Static UI)    │  │
│  │   REST Endpoints │  │   Bot Pipeline   │  │   Prebuilt Interface     │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PostgreSQL Database                                │
│  ┌──────────┐  ┌─────────────┐  ┌───────────────┐  ┌───────────────────┐   │
│  │ Sessions │  │ Transcripts │  │ Turn Latencies│  │   Freeze Events   │   │
│  └──────────┘  └─────────────┘  └───────────────┘  └───────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Voice Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Pipecat Voice Pipeline                             │
│                                                                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │  WebRTC     │    │  Deepgram   │    │   User      │    │   Google    │  │
│  │  Transport  │───▶│    STT      │───▶│ Aggregator  │───▶│   Gemini    │  │
│  │   Input     │    │             │    │             │    │    LLM      │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│                                                                    │         │
│                                                                    ▼         │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │  Assistant  │    │  WebRTC     │    │   Session   │    │  Cartesia   │  │
│  │ Aggregator  │◀───│  Transport  │◀───│  Recorder   │◀───│    TTS      │  │
│  │             │    │   Output    │    │             │    │             │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│                                               │                    ▲         │
│                                               │            ┌───────┴───────┐│
│                                               │            │    Freeze     ││
│                                               │            │   Simulator   ││
│                                               ▼            └───────────────┘│
│                                        ┌─────────────┐                      │
│                                        │  Database   │                      │
│                                        │  (Postgres) │                      │
│                                        └─────────────┘                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```mermaid
sequenceDiagram
    participant User
    participant WebRTC
    participant STT as Deepgram STT
    participant LLM as Google Gemini
    participant TTS as Cartesia TTS
    participant Freeze as Freeze Simulator
    participant Recorder as Session Recorder
    participant DB as PostgreSQL

    User->>WebRTC: Audio Input
    WebRTC->>STT: Audio Frames
    STT->>LLM: Transcribed Text
    Note over Recorder,DB: User transcript saved
    LLM->>TTS: Generated Response
    Note over Recorder,DB: Assistant transcript saved
    TTS->>Freeze: Audio Frames
    Note over Freeze: 30% chance of freeze (1-5s)
    Freeze->>Recorder: Audio Frames
    Note over Recorder,DB: Audio + Latency recorded
    Recorder->>WebRTC: Audio Output
    WebRTC->>User: Bot Response
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Framework | [Pipecat](https://github.com/pipecat-ai/pipecat) |
| Web Server | FastAPI + Uvicorn |
| Database | PostgreSQL + SQLAlchemy (async) |
| STT | Deepgram |
| LLM | Google Gemini (default) / OpenAI GPT |
| TTS | Cartesia |
| Transport | WebRTC (aiortc) |
| Turn Detection | LocalSmartTurnAnalyzerV3 |

## Prerequisites

- Python 3.11+
- PostgreSQL 14+
- API Keys for:
  - [Deepgram](https://deepgram.com/) (Speech-to-Text)
  - [Google AI Studio](https://aistudio.google.com/) (Gemini LLM)
  - [Cartesia](https://cartesia.ai/) (Text-to-Speech)

## Quick Start

### 1. Clone and Setup

```bash
cd examples/voice-agent-recording-ui

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy example configuration
cp .env.example .env

# Edit .env with your API keys
```

Required environment variables:
```env
DEEPGRAM_API_KEY=your_deepgram_api_key
GOOGLE_API_KEY=your_google_api_key
CARTESIA_API_KEY=your_cartesia_api_key
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/voice_agent_db
```

### 3. Setup Database

```bash
# Start PostgreSQL (if using Docker)
docker run -d \
  --name voice-agent-db \
  -e POSTGRES_USER=user \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=voice_agent_db \
  -p 5432:5432 \
  postgres:16

# Run migrations
alembic upgrade head
```

### 4. Start the Server

```bash
python -m backend.main
```

The server starts at `http://localhost:8000`:
- **Voice UI**: http://localhost:8000/client
- **API Docs**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Docker Compose (Recommended)

The easiest way to run the application is with Docker Compose:

### 1. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 2. Start Services

```bash
# Start all services (database + backend)
docker-compose up -d

# View logs
docker-compose logs -f backend

# Stop services
docker-compose down
```

### 3. Access the Application

- **Voice UI**: http://localhost:8000/client
- **API Docs**: http://localhost:8000/docs

### Docker Compose Services

| Service | Description | Port |
|---------|-------------|------|
| `db` | PostgreSQL 16 database | 5432 |
| `backend` | FastAPI application | 8000 |
| `migrations` | One-time Alembic migration runner | - |

### Useful Commands

```bash
# Rebuild after code changes
docker-compose up -d --build backend

# Run migrations manually
docker-compose run --rm migrations

# View database
docker-compose exec db psql -U user -d voice_agent_db

# Reset everything (including data)
docker-compose down -v
```

## Configuration

### Service Providers

The application supports swappable AI service providers via environment variables:

```env
# Provider Selection
STT_PROVIDER=deepgram          # Speech-to-Text (default: deepgram)
LLM_PROVIDER=google            # LLM: google, openai
TTS_PROVIDER=cartesia          # Text-to-Speech (default: cartesia)

# Model Configuration (optional - uses defaults if empty)
LLM_MODEL=gemini-2.5-flash     # Google default
# LLM_MODEL=gpt-4o             # OpenAI default
TTS_VOICE_ID=71a7ad14-091c-4e8e-a314-022ece01c121  # British Reading Lady
```

### Using OpenAI Instead of Google

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_openai_api_key
LLM_MODEL=gpt-4o  # Optional, defaults to gpt-4o
```

## API Reference

### Sessions

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/sessions` | GET | List all sessions (paginated) |
| `/api/sessions/{id}` | GET | Get session details with transcripts, latencies, freeze events |
| `/api/sessions/{id}/audio` | GET | Download session audio (WAV) |

### Query Parameters

**GET /api/sessions**
- `limit` (int, 1-100): Maximum sessions to return (default: 50)
- `offset` (int): Number of sessions to skip (default: 0)
- `status` (string): Filter by status: `active`, `completed`, `error`

### Response Models

**Session Detail**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "created_at": "2024-01-15T10:30:00Z",
  "ended_at": "2024-01-15T10:35:00Z",
  "status": "completed",
  "audio_file_path": "/storage/recordings/session_550e8400.wav",
  "transcripts": [
    {
      "id": "...",
      "role": "user",
      "content": "Hello, how are you?",
      "timestamp": "2024-01-15T10:30:05Z",
      "turn_number": 1
    }
  ],
  "turn_latencies": [
    {
      "id": "...",
      "turn_number": 1,
      "latency_ms": 1250.5,
      "was_interrupted": false,
      "created_at": "2024-01-15T10:30:06Z"
    }
  ],
  "freeze_events": [
    {
      "id": "...",
      "start_time_ms": 15000,
      "duration_ms": 3500,
      "detected_at": "2024-01-15T10:30:18Z"
    }
  ]
}
```

## Development

### Running Tests

```bash
# Activate virtual environment
source venv/bin/activate

# Run all tests
pytest

# Run with coverage
pytest --cov=backend --cov-report=term-missing

# Run specific test file
pytest tests/test_config.py -v
```

### Project Structure

```
voice-agent-recording-ui/
├── backend/
│   ├── api/
│   │   ├── routes.py          # REST API endpoints
│   │   └── schemas.py         # Pydantic response models
│   ├── bot/
│   │   ├── freeze_simulator.py # Freeze simulation processor
│   │   ├── pipeline.py        # Pipecat voice pipeline
│   │   ├── services.py        # Service factories with retry
│   │   └── session_recorder.py # Audio recording & latency tracking
│   ├── db/
│   │   ├── database.py        # Async SQLAlchemy setup
│   │   └── models.py          # Database models
│   ├── utils/
│   │   └── retry.py           # Retry utilities with tenacity
│   ├── config.py              # Settings management
│   └── main.py                # FastAPI application
├── tests/
│   ├── test_api.py            # API endpoint tests
│   ├── test_config.py         # Configuration tests
│   ├── test_freeze_simulator.py
│   ├── test_retry.py
│   └── test_schemas.py
├── alembic/                   # Database migrations
├── storage/recordings/        # Audio file storage
├── .env.example              # Example configuration
├── docker-compose.yml        # Docker Compose configuration
├── Dockerfile                # Backend container definition
├── requirements.txt
└── pytest.ini
```

### Key Components

#### Freeze Simulator

The `FreezeSimulatorProcessor` introduces random delays to simulate bot freezes:

```python
freeze_simulator = FreezeSimulatorProcessor(
    freeze_probability=0.3,  # 30% chance per turn
    min_freeze_duration=1.0,  # Minimum 1 second
    max_freeze_duration=5.0,  # Maximum 5 seconds
)
```

This intentionally uses randomization rather than deterministic patterns to create realistic, unpredictable freeze scenarios for testing UI resilience.

#### Session Recorder

Records audio in stereo format:
- **Left channel**: User audio
- **Right channel**: Bot audio
- **Format**: 16-bit PCM WAV at 16kHz

#### Retry Mechanism

External services use exponential backoff retry logic:

```python
@service_retry(config=RetryConfig(max_attempts=3, base_delay=0.5))
async def create_stt_service(settings: Settings) -> STTService:
    ...
```

## Troubleshooting

### Common Issues

**Connection Refused to Database**
```
sqlalchemy.exc.OperationalError: connection refused
```
Ensure PostgreSQL is running and `DATABASE_URL` port matches your database port.

**Missing API Keys**
```
ValueError: Missing required API keys: DEEPGRAM_API_KEY
```
Check your `.env` file has all required keys configured.

**WebRTC Connection Failed**
- Ensure you're accessing via `localhost` (not `127.0.0.1`)
- Check browser permissions for microphone access
- Try a different browser if issues persist

## License

This project is part of the [Pipecat](https://github.com/pipecat-ai/pipecat) examples collection.
