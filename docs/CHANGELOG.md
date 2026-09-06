# Changelog

All notable changes to Auto-DFA are documented here.

## [1.2.0] - 2026-09-06

### Added
- **Reverse Engineering Pipeline**: 3-Phase neuro-symbolic engine converting diagram images to verified DFAs, Right-Linear Regular Grammars, and natural language descriptions.
- **Grammar Engine (`core/grammar.py`)**: Mathematical `GrammarBuilder` computing formal Right-Linear Grammars ($S \to aA, A \to \varepsilon$) from DFAs.
- **Multimodal Providers (`core/providers.py`)**: Unified VLM providers for Google Gemini and OpenRouter with rate-limit and quota handling.
- **Agents (`core/agents.py`)**: `VisionAgent` for visual state extraction and `DescriberAgent` for language synthesis.
- **API**: `POST /reverse-engineer` endpoint supporting `multipart/form-data` uploads (`PNG`, `JPEG`, `WEBP`) with 10MB limit and error handling.
- **Testing**: Added `tests/test_grammar.py` and `tests/test_reverse_engineer.py`, expanding test suite to 421 tests.
- **Design System (`DESIGN.md`)**: Formal aesthetic direction, color tokens, and contrast specifications.
- **Accessibility & Mobile**: Touch pan gesture support, WCAG AA color tokens, `<kbd>Ctrl+Enter</kbd>` keyboard shortcut hint, and responsive mobile layout.

### Changed
- Replaced all bare `except:` clauses with explicit exception tuples.
- Enforced prompt injection hardening and production error detail masking.
- Updated Docker Compose to Compose V2 format.
- Refactored comments to explain permanent architectural intent.

## [1.1.0] - 2026-02-27

### Added
- **Security**: Input sanitization with max length (500 chars) and control character stripping.
- **Security**: Rate limiting via slowapi (10 req/min on `/generate`, 60/min on `/health`).
- **Security**: Optional API key authentication (`X-API-Key` header, enable via `API_KEY` env var).
- **Reliability**: LLM retry with exponential backoff (3 attempts, 1s/2s/4s delay) for Ollama outages.
- **API**: `/export/json` endpoint to download DFA definitions as JSON files.
- **API**: `/export/dot` endpoint to download DFAs in Graphviz DOT format.
- **API**: Performance timing in `/generate` response (`total_ms`, `analysis_ms`, `architecture_ms`, `validation_ms`).
- **Frontend**: `ErrorBoundary` component wrapping Canvas for crash recovery.
- **Frontend**: ARIA accessibility attributes on SVG canvas (`role="img"`, `aria-label`, `<title>`).
- **Frontend**: Keyboard zoom controls (`+`/`-`/`0` keys on focused diagram).
- **Frontend**: Accessible zoom buttons with `aria-label` and `title` attributes.
- **Testing**: `tests/test_api.py` covering validation, authentication, and execution metrics.
- **Testing**: `requirements-dev.txt` with pytest-cov, ruff, mypy.
- **CI**: Coverage reporting in GitHub Actions unit-test job.
- **Docs**: `DEPLOYMENT.md` production deployment guide.
- **Docs**: `CONTRIBUTING.md` guide for code style, PR process, and branch conventions.

### Changed
- Structured logging with request IDs and timestamps in `api.py`.
- CI now runs `tests/` suite with `pytest --cov` instead of standalone scripts.

## [1.0.0] - 2026-01-01

### Features
- Multi-agent DFA generation (Analyst + Architect + Validator + Repair).
- Natural language parsing for 15+ logic types.
- Product construction for AND/OR/NOT compositions.
- DFA optimizer (unreachable/non-productive state removal).
- React frontend with custom SVG visualization (zoom/pan).
- Docker Compose deployment.
- GitHub Actions CI/CD pipeline.
- Oracle QA pipeline with automated test generation.

---

## Roadmap

### Upcoming (v1.3.0)
- [ ] Interactive UI modal for image-based DFA upload and grammar inspection.
- [ ] Ambiguity clarification prompt builder (Analyst asks follow-up questions for vague inputs).
- [ ] Model selector toggle in UI (switch between local Ollama and cloud providers).
- [ ] Extended custom alphabet support in frontend (beyond binary `{a,b}` and `{0,1}`).

### Planned (v2.0.0)
- [ ] JWT-based user authentication with saved DFA templates.
- [ ] API versioning (`/v1/generate`, `/v2/generate`).
- [ ] D3.js / Cytoscape.js interactive visualization engine.
- [ ] Web Workers for off-main-thread diagram rendering.
- [ ] Internationalization (i18n) for multilingual prompts.
- [ ] Prometheus/Grafana telemetry metrics integration.
- [ ] CLI module (`cli.py`) for batch and headless DFA generation.
