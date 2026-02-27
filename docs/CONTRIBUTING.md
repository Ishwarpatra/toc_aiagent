# Contributing to Auto-DFA

Thanks for your interest in contributing! This guide covers everything you need to get started.

## Development Setup

```bash
# 1. Clone the repo
git clone https://github.com/Ishwarpatra/toc_aiagent.git
cd toc_aiagent

# 2. Backend setup
cd backend/python_imply
pip install -r requirements-dev.txt

# 3. Frontend setup
cd ../../frontend
npm install

# 4. Start Ollama (required for LLM features)
ollama serve
ollama pull qwen2.5-coder:1.5b
```

## Code Style

### Python (Backend)
- **Linter**: Ruff (`ruff check .`)
- **Type hints**: Use type annotations on all public functions
- **Docstrings**: Required for classes and public methods (Google style)
- **Models**: Use Pydantic v2 `BaseModel` for data structures

### JavaScript (Frontend)
- **Linter**: ESLint (`npm run lint`)
- **Framework**: React with functional components and hooks
- **Styling**: Vanilla CSS (no Tailwind)

## Branch Naming

| Type | Pattern | Example |
|------|---------|---------|
| Feature | `feat/short-description` | `feat/add-export-dot` |
| Bug fix | `fix/short-description` | `fix/kmp-off-by-one` |
| Docs | `docs/short-description` | `docs/add-api-examples` |
| Refactor | `refactor/short-description` | `refactor/agent-retry` |

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add DOT export endpoint
fix: correct KMP parsing for ENDS_WITH patterns
docs: add edge-case examples to TESTING.md
test: add API input validation tests
```

## Pull Request Process

1. Create a feature branch from `main`
2. Write/update tests for your changes
3. Ensure all tests pass: `python -m pytest test/ -v`
4. Ensure linting passes: `ruff check .` and `npm run lint`
5. Update documentation if needed
6. Open a PR with a clear description

## Testing Requirements

- All PRs must pass existing tests
- New features require corresponding test cases
- Core logic changes require oracle validation: `python scripts/batch_verify.py`
- Coverage should not decrease — run `pytest --cov` to check

## Reporting Issues

When filing an issue, include:
1. Steps to reproduce
2. Expected vs. actual behavior
3. Prompt text (if DFA-related)
4. Error logs from the backend console

## Architecture Overview

```
User Prompt → AnalystAgent → LogicSpec → ArchitectAgent → DFA → Validator → Response
                                              ↓ (if invalid)
                                        RepairEngine → Re-validate
```

See [dfa.md](dfa.md) for detailed architecture and pattern documentation.
