# Auto-DFA: Deterministic Finite Automaton Generator

Auto-DFA is a neuro-symbolic framework for formal language theory and automata computation. It provides bidirectional translation between natural language, Deterministic Finite Automata (DFA), Right-Linear Regular Grammars, and visual state diagrams.

---

## Capabilities

* **Natural Language to DFA (Forward Pipeline)**: Translates plain English specifications (e.g. "strings ending in '01'", "even number of 1s and divisible by 3") into validated, minimal state machines.
* **Image to Grammar & Language (Reverse Pipeline)**: Ingests uploaded DFA diagram images, parses graph structure into strict schemas, derives formal Right-Linear Regular Grammars ($S \to aA, A \to \varepsilon$), and synthesizes natural language descriptions.
* **Multi-Agent Neuro-Symbolic Architecture**: Separates statistical AI perception from exact mathematical computation (DeterministicValidator, GrammarBuilder, DFAOptimizer).
* **Deterministic Minimization & Composition**: Performs Hopcroft/BFS minimization, product construction (AND/OR/NOT), and truth oracle verification.
* **Interactive Visualization**: Real-time SVG rendering with zoom, pan, touch gestures, and Graphviz DOT / JSON export formats.

---

## Bidirectional Pipeline Architecture

```
=== Forward Pipeline: Natural Language to DFA ===
[User Prompt] 
      │
      ▼
AnalystAgent ──► LogicSpec (AST) ──► ArchitectAgent ──► DFA Model
                                                          │
                                                          ▼
                                                DeterministicValidator
                                                          │
                                                          ▼
                                                     DFAOptimizer

=== Reverse Pipeline: Diagram Image to Grammar & Language ===
[Diagram Image]
      │
      ▼
VisionAgent (Multimodal VLM) ──► DeterministicValidator (Structure Check)
      │
      ▼
GrammarBuilder (Deterministic Math: S -> aA, A -> ε)
      │
      ▼
DescriberAgent (Natural Language Synthesis)
```

---

## Project Structure

```
toc_aiagent/
├── README.md                       # Project overview and quick start
├── DESIGN.md                       # Design tokens, palette, and style direction
├── docker-compose.yml              # Docker orchestration (V2 compatible)
├── .github/workflows/qa.yml        # CI test workflow
│
├── docs/                           # Architecture and operational guides
│   ├── architecture.md             # System design & bidirectional pipelines
│   ├── deployment.md               # Production deployment guide
│   ├── testing.md                  # Test suites and QA oracle framework
│   ├── changelog.md                # Version history and milestone logs
│   └── commit_history.md           # Repository commit record
│
├── backend/
│   ├── src/                        # FastAPI service and core engines
│   │   ├── api.py                  # REST API server (/generate, /reverse-engineer, /health)
│   │   ├── main.py                 # DFAGeneratorSystem orchestrator & lifecycle manager
│   │   ├── core/                   # Mathematical and agent modules
│   │   │   ├── models.py           # Pydantic schemas: LogicSpec, DFA
│   │   │   ├── grammar.py          # DFA to Right-Linear Grammar engine
│   │   │   ├── providers.py        # Gemini and OpenRouter vision providers
│   │   │   ├── agents.py           # Analyst, Architect, Vision, and Describer agents
│   │   │   ├── validator.py        # Graph integrity and semantic validation
│   │   │   ├── repair.py           # LLM-guided auto-repair engine
│   │   │   ├── optimizer.py        # State minimization (unreachable/dead state removal)
│   │   │   ├── product.py          # Product construction for AND/OR/NOT
│   │   │   ├── oracle.py           # Ground-truth test oracle
│   │   │   ├── normalizer.py       # Prompt pre-processing and synonym mapping
│   │   │   └── pattern_parser.py   # Atomic logic regex extractor
│   │   └── tests/                  # 421 unit and integration tests
│   └── requirements.txt            # Python dependencies
│
└── frontend/                       # React + Vite client interface
    ├── src/
    │   ├── App.jsx                 # Main application UI
    │   ├── App.css                 # Component layout and styling
    │   ├── index.css               # WCAG 2.1 AA design tokens
    │   └── components/
    │       ├── Canvas.jsx          # SVG visualization with pan and zoom
    │       └── ErrorBoundary.jsx   # Error fallback container
    └── package.json
```

---

## Core Modules

| Module | Location | Description |
| :--- | :--- | :--- |
| `api.py` | `backend/src/` | REST endpoints: `/generate`, `/reverse-engineer`, `/export/*`, `/oracle/verify` |
| `grammar.py` | `backend/src/core/` | Right-Linear Regular Grammar builder ($S \to aA, A \to \varepsilon$) |
| `providers.py` | `backend/src/core/` | Unified multimodal vision providers (Gemini, OpenRouter) |
| `agents.py` | `backend/src/core/` | Analyst, Architect, Vision, and Describer agent implementations |
| `validator.py` | `backend/src/core/` | Graph structural validation and truth simulation |
| `optimizer.py` | `backend/src/core/` | State minimization and reachability analysis |
| `product.py` | `backend/src/core/` | Product automata construction for boolean composition |
| `repair.py` | `backend/src/core/` | Fault localization and repair routines for generated automata |

---

## Quick Start

### 1. Backend Setup

```bash
cd backend/src
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Run the backend development server:

```bash
uvicorn api:app --reload --port 8000
```

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173`.

---

## API Reference

### 1. `POST /generate`
Generate a DFA from a natural language prompt.

**Request:**
```json
{
  "prompt": "strings over {0,1} ending in 01"
}
```

**Response (200 OK):**
```json
{
  "valid": true,
  "dfa": {
    "states": ["q0", "q1", "q2"],
    "alphabet": ["0", "1"],
    "transitions": {
      "q0": {"0": "q1", "1": "q0"},
      "q1": {"0": "q1", "1": "q2"},
      "q2": {"0": "q1", "1": "q0"}
    },
    "start_state": "q0",
    "accept_states": ["q2"]
  },
  "metrics": {
    "state_count": 3,
    "transition_count": 6
  }
}
```

### 2. `POST /reverse-engineer`
Upload a DFA state diagram image to extract its model, grammar, and description.

**Request:** `multipart/form-data` with `file=@diagram.png`

**Response (200 OK):**
```json
{
  "success": true,
  "valid": true,
  "dfa": {
    "states": ["q0", "q1"],
    "alphabet": ["0", "1"],
    "transitions": {
      "q0": {"0": "q0", "1": "q1"},
      "q1": {"0": "q0", "1": "q1"}
    },
    "start_state": "q0",
    "accept_states": ["q1"]
  },
  "grammar": {
    "S": ["0S", "1A"],
    "A": ["0S", "1A", ""]
  },
  "grammar_formatted": "Start symbol: S\nProductions:\n  S -> 0S | 1A\n  A -> 0S | 1A | ε",
  "description": "Accepts binary strings ending with 1."
}
```

---

## Testing

Run the full pytest suite:

```bash
cd backend/src
python -m pytest tests/ -v
```

**Test suite result:** `421 passed in 6.95s`
