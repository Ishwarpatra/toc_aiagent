# Auto-DFA Production Deployment Guide

## Quick Start (Docker Compose)

Deploy both frontend and backend services:

```bash
# 1. Ensure Ollama is running on the host
ollama serve

# 2. Pull the required model
ollama pull qwen2.5-coder:1.5b

# 3. Start all services
docker compose up -d --build

# 4. Verify service health
curl http://localhost:8000/health
```

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000

---

## Environment Variable Reference

| Variable | Default | Description |
|---|---|---|
| `AUTO_DFA_MODEL` | `qwen2.5-coder:1.5b` | Ollama model name |
| `AUTO_DFA_MAX_PRODUCT_STATES` | `2000` | Max product DFA states (safety limit) |
| `OLLAMA_URL` | `http://localhost:11434/api/generate` | Ollama API endpoint |
| `GEMINI_API_KEY` | *(unset)* | Google Gemini API key for image-to-DFA vision pipeline |
| `OPENROUTER_API_KEY` | *(unset)* | OpenRouter API key (fallback vision provider) |
| `API_HOST` | `0.0.0.0` | API bind address |
| `API_PORT` | `8000` | API port |
| `API_KEY` | *(unset = auth disabled)* | Set to enable API key authentication |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173,...` | Comma-separated allowed origins |
| `ENVIRONMENT` | `production` | Set to `development` for permissive CORS |
| `VITE_API_URL` | *(empty in prod)* | Frontend API URL (empty = nginx proxy) |

---

## Security Checklist

1. **Set an API key** in production:
   ```bash
   export API_KEY="your-secure-random-key"
   ```
   Clients must include the `X-API-Key: your-secure-random-key` header.

2. **Lock down CORS**: set `CORS_ALLOWED_ORIGINS` to your production domain:
   ```bash
   export CORS_ALLOWED_ORIGINS="https://yourdomain.com"
   ```

3. **Rate limiting** is enabled by default:
   - `/generate`: 10 requests/minute per IP
   - `/reverse-engineer`: 10 requests/minute per IP
   - `/health`: 60 requests/minute per IP

4. **Input sanitization** is enforced:
   - Max prompt length: 500 characters
   - Control characters are stripped
   - Empty or whitespace-only prompts are rejected

---

## Monitoring

### Health Check

```bash
curl http://localhost:8000/health
```

Returns:
```json
{
  "status": "healthy",
  "system_initialized": true,
  "message": "Auto-DFA API is running",
  "version": "1.2.0"
}
```

Docker Compose includes automatic healthchecks with 30s intervals.

### Logs

API requests log structured request IDs and timestamps:

```
2026-09-06 20:00:00 [INFO] __main__: [API][a1b2c3d4] Received request: 'ends with a'
2026-09-06 20:00:01 [INFO] __main__: [API][a1b2c3d4] Completed in 1234.5ms (valid=True)
```

### Performance Metrics

Every `/generate` response includes a timing breakdown:

```json
{
  "performance": {
    "total_ms": 1234.5,
    "analysis_ms": 50.2,
    "architecture_ms": 1100.0,
    "validation_ms": 84.3
  }
}
```

---

## Backup Strategy

Auto-DFA is stateless except for cache and output artifacts:

| Data | Location | Backup Method |
|---|---|---|
| Generated DFA JSON exports | `backend/output/` | Copy periodically or mount a volume |
| QA test results and logs | `backend/qa/qa_output/` | CI artifacts (auto-uploaded) |
| Failed prompt bank | `backend/qa/failed_prompts_bank.csv` | Commit to repo or persistent volume |

For Docker deployments, mount these as volumes:

```yaml
volumes:
  - ./data/output:/app/output
  - ./data/qa_output:/app/qa/qa_output
```

---

## Scaling Notes

- The backend forward pipeline is CPU-bound during local Ollama inference. Scale horizontally with multiple workers:
  ```bash
  uvicorn api:app --workers 4 --host 0.0.0.0 --port 8000
  ```
- The frontend is compiled into static assets served via Nginx.
- For higher inference throughput, run Ollama on GPU hardware or configure Gemini API keys for cloud acceleration.
