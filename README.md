# Auto-DFA: AI-Powered DFA Generator

Auto-DFA is an intelligent system that translates natural language descriptions (e.g., "strings ending in '01'") into fully functional and visualized Deterministic Finite Automata (DFA). It uses a multi-agent architecture with specialized AI agents for analysis and design, backed by a deterministic validation engine.

## 🚀 Features

* **Natural Language to DFA**: Describe your logic in plain English.
* **AI Agent Architecture**: Utilizes an **Analyst Agent** for requirement extraction and an **Architect Agent** for state-machine design.
* **Deterministic Validation**: Every generated DFA is checked against the original specifications for correctness.
* **DFA Optimizer**: Automatically removes unreachable and non-productive states for clean, minimal DFAs.
* **Responsive Visualization**: Real-time rendering of DFA diagrams using Mermaid.js, optimized for any screen size.
* **Flexible UI**: A modern, mobile-friendly interface with a dedicated question area and toolbar.

## 🏗️ Architecture

```
┌──────────────────┐         HTTP POST         ┌───────────────────┐
│   React Frontend │ ──────────────────────►   │   FastAPI Backend │
│   (port 5173)    │    /generate endpoint     │   (port 8000)     │
│                  │ ◄──────────────────────   │                   │
│   App.jsx        │    JSON Response          │   api.py          │
│   Canvas.jsx     │    (DFA states/edges)     │      ↓            │
└──────────────────┘                           │ DFAGeneratorSystem│
                                               │      ↓            │
                                               │   Ollama LLM      │
                                               └───────────────────┘
```

### Core Modules

| Module | Description |
|--------|-------------|
| `api.py` | FastAPI REST server exposing `/generate` and `/health` endpoints |
| `main.py` | DFAGeneratorSystem orchestrating the pipeline |
| `core/agents.py` | AnalystAgent (NL → LogicSpec) and ArchitectAgent (LogicSpec → DFA) |
| `core/models.py` | Pydantic models for `LogicSpec` and `DFA` |
| `core/repair.py` | Auto-repair engine ensuring DFA completeness |
| `core/optimizer.py` | **NEW** - Removes unreachable/non-productive states |
| `core/validator.py` | Deterministic validation against test cases |
| `core/product.py` | Product construction for AND/OR/NOT operations |

## 🛠️ Tech Stack

### Frontend
* **Framework**: React (Vite)
* **Visualization**: Mermaid.js
* **Icons**: Lucide-React
* **Styling**: Flexbox-based responsive CSS

### Backend
* **Language**: Python 3.x
* **API Framework**: FastAPI
* **LLM**: Ollama (qwen2.5-coder:1.5b)
* **Data Validation**: Pydantic
* **Logic Engine**: Custom multi-agent system (Analyst, Architect, Validator)

## 🏁 Getting Started

### 1. Prerequisites
* Node.js and npm
* Python 3.10+
* [Ollama](https://ollama.ai/) with `qwen2.5-coder:1.5b` model
* Graphviz (optional, for local CLI visualization)

### 2. Backend Setup

Navigate to the backend directory and install dependencies:

```bash
cd backend/python_imply
pip install -r requirements.txt
```

Start Ollama (if not already running):
```bash
ollama serve
```

Start the FastAPI server:
```bash
python api.py
```

The backend will run at http://localhost:8000.

### 3. Frontend Setup

Navigate to the frontend directory and install dependencies:

```bash
cd frontend
npm install
```

Start the development server:

```bash
npm run dev
```

Open your browser to http://localhost:5173.

## 📖 Usage

1. Enter a DFA description in the **Question Area** at the top:
   - `"ends with a"` or `"ends with 'a'"`
   - `"contains '01'"`
   - `"starts with a or ends with b"`
   - `"even number of 1s"`
   - `"divisible by 3"`

2. Click the **▶ Play** button at the bottom.

3. The system will:
   - Analyze the prompt (Analyst Agent)
   - Design the state machine (Architect Agent)
   - Optimize the DFA (remove unreachable states)
   - Validate against test cases
   - Display the diagram on the Canvas

## 🔧 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check - returns system status |
| `/generate` | POST | Generate DFA from prompt |

### Example Request

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "ends with a"}'
```

### Example Response

```json
{
  "valid": true,
  "message": "DFA generated successfully",
  "dfa": {
    "states": ["q0", "q1"],
    "alphabet": ["a", "b"],
    "start_state": "q0",
    "accept_states": ["q1"],
    "transitions": {
      "q0": {"a": "q1", "b": "q0"},
      "q1": {"a": "q1", "b": "q0"}
    }
  },
  "spec": {
    "logic_type": "ENDS_WITH",
    "target": "a",
    "alphabet": ["a", "b"]
  }
}
```

## 🧹 DFA Optimizer

The optimizer module (`core/optimizer.py`) ensures clean, minimal DFAs by:

1. **Finding Reachable States**: BFS from start state
2. **Finding Productive States**: Reverse BFS from accept states
3. **Computing Useful States**: Intersection of reachable ∩ productive
4. **Removing Dead States**: Only keeps `q_dead` if actually needed for completeness

Example optimization:
- Before: `['q0', 'q1', 'q_dead']` (3 states)
- After: `['q0', 'q1']` (2 states) - orphaned dead state removed

## 📝 License

MIT License
