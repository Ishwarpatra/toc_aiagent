# Changelog

All notable changes to Auto-DFA are documented here.

## [1.1.0] - 2026-02-27

### Added
- **Security**: Input sanitization with max length (500 chars) and control character stripping
- **Security**: Rate limiting via slowapi (10 req/min on `/generate`, 60/min on `/health`)
- **Security**: Optional API key authentication (`X-API-Key` header, enable via `API_KEY` env var)
- **Reliability**: LLM retry with exponential backoff (3 attempts, 1s/2s/4s delay) for Ollama outages
- **API**: `/export/json` endpoint — download DFA definition as JSON file
- **API**: `/export/dot` endpoint — download DFA as Graphviz DOT format
- **API**: Performance timing in `/generate` response (`total_ms`, `analysis_ms`, `architecture_ms`, `validation_ms`)
- **Frontend**: `ErrorBoundary` component wrapping Canvas for crash recovery
- **Frontend**: ARIA accessibility attributes on SVG canvas (`role="img"`, `aria-label`, `<title>`)
- **Frontend**: Keyboard zoom controls (`+`/`-`/`0` keys on focused diagram)
- **Frontend**: Accessible zoom buttons with `aria-label` and `title` attributes
- **Testing**: `test/test_api.py` — 12 API-level tests (validation, auth, timing)
- **Testing**: `requirements-dev.txt` with pytest-cov, ruff, mypy
- **CI**: Coverage reporting in GitHub Actions unit-test job
- **Docs**: `DEPLOYMENT.md` — production deployment guide with Docker, env vars, security checklist
- **Docs**: `CONTRIBUTING.md` — code style, PR process, branch conventions
- **Docs**: `CHANGELOG.md` — this file
- **Docs**: Edge-case test examples in `TESTING.md`
- **Docs**: Advanced usage examples and sequence diagram in `dfa.md`

### Changed
- Structured logging with request IDs and timestamps in `api.py`
- CI now runs `test/` suite with `pytest --cov` instead of standalone scripts

## [1.0.0] - 2026-01-01

### Features
- Multi-agent DFA generation (Analyst + Architect + Validator + Repair)
- Natural language parsing for 15+ logic types
- Product construction for AND/OR/NOT compositions
- DFA optimizer (unreachable/non-productive state removal)
- React frontend with custom SVG visualization (zoom/pan)
- Docker Compose deployment
- GitHub Actions CI/CD pipeline
- Oracle QA pipeline with automated test generation

---

## Roadmap

### Planned (v1.2.0)
- [ ] Ambiguity clarification system (Analyst asks follow-up questions for vague prompts)
- [ ] Model configuration UI (switch between Ollama models)
- [ ] Positional logic support (`"3rd symbol is 'a'"`)
- [ ] Custom alphabet support in frontend (beyond binary `{a,b}` / `{0,1}`)

### Planned (v2.0.0)
- [ ] JWT-based user authentication with saved DFA templates
- [ ] API versioning (`/v1/generate`, `/v2/generate`)
- [ ] D3.js / Cytoscape.js interactive visualization (replacing custom SVG)
- [ ] Web Workers for off-main-thread diagram rendering
- [ ] Internationalization (i18n) for non-English users
- [ ] Prometheus/Grafana metrics integration
- [ ] CLI module (`cli.py`) for batch/headless DFA generation
- [ ] Optimizer benchmarks for large DFAs (1000+ states)
