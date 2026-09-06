# Contributing to Auto-DFA
 
Thanks for your interest in contributing. This guide covers setup, code conventions, testing, and pull requests.

## Development Setup

```bash
# 1. Clone the repo
git clone https://github.com/Ishwarpatra/toc_aiagent.git
cd toc_aiagent

# 2. Backend setup
cd backend/src
pip install -r requirements-dev.txt

# 3. Frontend setup
cd ../../frontend
npm install

# 4. Start Ollama (required for local forward pipeline inference)
ollama serve
ollama pull qwen2.5-coder:1.5b
```

## Code Style

### Python (Backend)
- **Linter**: Ruff (`ruff check .`)
- **Type hints**: Type annotations on public functions
- **Docstrings**: Google-style docstrings for modules, classes, and public methods
- **Models**: Pydantic v2 `BaseModel` schemas

### JavaScript (Frontend)
- **Linter**: ESLint (`npm run lint`)
- **Framework**: React with functional components and hooks
- **Styling**: Vanilla CSS adhering to `DESIGN.md` tokens

## Branch Naming

| Type | Pattern | Example |
|---|---|---|
| Feature | `feat/short-description` | `feat/add-export-dot` |
| Bug fix | `fix/short-description` | `fix/kmp-off-by-one` |
| Docs | `docs/short-description` | `docs/add-api-examples` |
| Refactor | `refactor/short-description` | `refactor/agent-retry` |

## Commit Messages

Follow Conventional Commits:

```
feat: add reverse engineering vision provider
fix: handle specific exception types in logic evaluations
docs: update architecture and testing guides
test: add Right-Linear Grammar test cases
```

## Pull Request Process

1. Create a feature branch from `main`.
2. Write or update tests for your changes.
3. Ensure all tests pass: `python -m pytest tests/ -v`.
4. Ensure linting passes: `ruff check .` and `npm run lint`.
5. Update documentation in `docs/` and `README.md` if public APIs or architecture change.
6. Open a PR with a clear summary of changes.

## Testing Requirements

- All PRs must pass the test suite.
- New features require dedicated unit or integration tests.
- Core logic changes should be validated against the test oracle: `python backend/qa/batch_verify.py`.
- Test coverage should not decrease.

## Reporting Issues

When filing an issue, include:
1. Steps to reproduce
2. Expected vs. actual behavior
3. Input prompt or uploaded image (if pipeline-related)
4. Error logs from the backend console

## Architecture Overview

```
=== Forward Pipeline ===
Prompt -> AnalystAgent -> LogicSpec -> ArchitectAgent -> DFA -> Validator -> Optimizer

=== Reverse Pipeline ===
Diagram Image -> VisionAgent -> DeterministicValidator -> GrammarBuilder -> DescriberAgent
```

See [docs/architecture.md](docs/architecture.md) for detailed architecture and component interactions.
