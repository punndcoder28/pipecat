# Voice Agent Recording UI

A full-stack example demonstrating a voice agent with real-time recording capabilities and freeze detection. This example showcases how to build a production-ready voice assistant using Pipecat with WebRTC transport, audio recording, and a web-based UI.

## Features

- Real-time voice conversations with an AI agent
- Audio recording of all conversations
- Freeze detection to identify and handle pipeline stalls
- WebRTC-based low-latency audio streaming
- PostgreSQL database for conversation metadata storage
- FastAPI backend with async support

## Architecture

```
┌─────────────────┐     WebRTC      ┌─────────────────┐
│    Frontend     │◄───────────────►│     Backend     │
│   (Web UI)      │                 │    (FastAPI)    │
└─────────────────┘                 └────────┬────────┘
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    │                        │                        │
                    ▼                        ▼                        ▼
            ┌───────────────┐      ┌─────────────────┐      ┌─────────────────┐
            │   Deepgram    │      │  Google Gemini  │      │    Cartesia     │
            │    (STT)      │      │     (LLM)       │      │     (TTS)       │
            └───────────────┘      └─────────────────┘      └─────────────────┘
```

## Prerequisites

### API Keys

You will need API keys from the following services:

- **Deepgram**: Speech-to-text transcription - [Get API Key](https://console.deepgram.com/)
- **Google AI**: Gemini LLM for conversation - [Get API Key](https://makersuite.google.com/app/apikey)
- **Cartesia**: Text-to-speech synthesis - [Get API Key](https://cartesia.ai/)

### Database

This example uses PostgreSQL for storing conversation metadata and recordings information.

```bash
# Using Docker
docker run --name voice-agent-db -e POSTGRES_USER=user -e POSTGRES_PASSWORD=password -e POSTGRES_DB=voice_agent_db -p 5432:5432 -d postgres:16

# Or install PostgreSQL locally and create the database
createdb voice_agent_db
```

### Python

- Python 3.10 or higher

## Setup

1. **Clone the repository** (if not already done):
   ```bash
   cd pipecat/examples/voice-agent-recording-ui
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and database URL
   ```

5. **Run database migrations** (when available):
   ```bash
   alembic upgrade head
   ```

## Running the Application

Start the backend server:

```bash
cd backend
uvicorn main:app --host localhost --port 8000 --reload
```

The API will be available at `http://localhost:8000`.

## Project Structure

```
voice-agent-recording-ui/
├── backend/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Settings management with pydantic-settings
│   ├── bot/                 # Pipecat bot configuration
│   │   └── __init__.py
│   ├── api/                 # FastAPI routes and endpoints
│   │   └── __init__.py
│   ├── db/                  # Database models and sessions
│   │   └── __init__.py
│   └── storage/
│       └── recordings/      # Local audio recordings storage
├── frontend/                # Web UI (to be implemented)
├── requirements.txt
├── .env.example
└── README.md
```

## Storage Considerations

### Local Development

By default, audio recordings are stored locally in the `storage/recordings/` directory. This is suitable for development and testing.

### Production Deployment

For production deployments, consider using cloud storage solutions:

- **AWS S3**: Scalable object storage with lifecycle policies
- **Google Cloud Storage**: Integrated well with other GCP services
- **Azure Blob Storage**: Good for Azure-based deployments

To switch to cloud storage, you would need to:

1. Add the appropriate cloud SDK to `requirements.txt`
2. Implement a storage adapter interface
3. Update the recording save logic to use the cloud provider

## Configuration

All configuration is managed through environment variables. See `.env.example` for available options:

| Variable | Description | Default |
|----------|-------------|---------|
| `DEEPGRAM_API_KEY` | Deepgram API key for STT | Required |
| `GOOGLE_API_KEY` | Google AI API key for LLM | Required |
| `CARTESIA_API_KEY` | Cartesia API key for TTS | Required |
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `HOST` | Server host | `localhost` |
| `PORT` | Server port | `8000` |
| `RECORDINGS_PATH` | Path for audio recordings | `./storage/recordings` |

## License

See the main Pipecat repository for license information.
