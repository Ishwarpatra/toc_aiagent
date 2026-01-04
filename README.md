# Auto-DFA: AI-Powered DFA Generator

Auto-DFA is an intelligent system that translates natural language descriptions (e.g., "strings ending in '01'") into fully functional and visualized Deterministic Finite Automata (DFA). It uses a multi-agent architecture with specialized AI agents for analysis and design, backed by a deterministic validation engine.

## 🚀 Features

* **Natural Language to DFA**: Describe your logic in plain English.
* **AI Agent Architecture**: Utilizes an **Analyst Agent** for requirement extraction and an **Architect Agent** for state-machine design.
* **Deterministic Validation**: Every generated DFA is checked against the original specifications for correctness.
* **Responsive Visualization**: Real-time rendering of DFA diagrams using Mermaid.js, optimized for any screen size.
* **Flexible UI**: A modern, mobile-friendly interface with a dedicated question area and toolbar.

## 🛠️ Tech Stack

### Frontend
* **Framework**: React (Vite)
* **Visualization**: Mermaid.js
* **Icons**: Lucide-React
* **Styling**: Flexbox-based responsive CSS

### Backend
* **Language**: Python 3.x
* **API Framework**: FastAPI
* **Data Validation**: Pydantic
* **Logic Engine**: Custom multi-agent system (Analyst, Architect, Validator)

## 🏁 Getting Started

### 1. Prerequisites
* Node.js and npm
* Python 3.10+
* Graphviz (optional, for local CLI visualization)

### 2. Backend Setup
Navigate to the backend directory and install dependencies:
```bash
cd backend/python_imply
pip install -r requirements.txt
# Alternatively, install core dependencies:
pip install fastapi uvicorn pydantic
Start the FastAPI server:

Bash

python api.py
The backend will run at http://localhost:8000.

3. Frontend Setup
Navigate to the frontend directory and install dependencies:

Bash

cd frontend
npm install
Start the development server:

Bash

npm run dev
Open your browser to the URL provided (typically http://localhost:5173).

📖 Usage
Enter a DFA description in the Question Area at the top (e.g., "contains an even number of 1s").

Click the ▶ Play button at the bottom.

The system will analyze the prompt, architect the state machine, and display the resulting diagram on the Canvas.
