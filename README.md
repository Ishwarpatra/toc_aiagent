# Auto-DFA: AI-Powered Automata Generator 🤖

**Auto-DFA** is a local, privacy-focused tool that uses a **Multi-Agent Large Language Model (LLM)** architecture to generate, validate, and visualize Deterministic Finite Automata (DFA) from natural language descriptions.

![Project Status](https://img.shields.io/badge/Status-Prototype_Complete-success)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![AI Engine](https://img.shields.io/badge/AI_Engine-Ollama-orange)

## 📖 Overview

Students often struggle to visualize abstract concepts in **Theory of Computation (ToC)**. Auto-DFA solves this by employing a "Teacher-Architect-Validator" loop:
1.  **Analyst:** Parses natural language (e.g., "strings starting with 'ab'") into logical constraints.
2.  **Architect:** Designs the DFA states and transitions using a local LLM (`qwen2.5-coder`).
3.  **Validator:** A **deterministic Python engine** (not AI) verifies the logic against test cases and "heals" the graph if errors are found.

---

## ⚙️ Prerequisites & System Requirements

Before running the Python code, you must have the following system-level tools installed:

### 1. Ollama (AI Backend)
This project runs locally using Ollama.
1.  Download and install [Ollama](https://ollama.com).
2.  Pull the specific model used in the configuration:
    ```bash
    ollama pull qwen2.5-coder:1.5b
    ```

### 2. Graphviz (Visualization Engine)
Required to render the DFA diagrams.
* **Windows:** Download the installer from [Graphviz.org](https://graphviz.org/download/).
    * ⚠️ **Important:** During installation, select **"Add Graphviz to the system PATH for all users"**.
* **Linux:** `sudo apt-get install graphviz`
* **Mac:** `brew install graphviz`

---

## 🛠️ Installation & Setup

### 1. Fork & Clone the Repository
Click the **Fork** button on the top right of this page to save a copy to your account, then clone it:


git clone [https://github.com/YOUR_USERNAME/toc_aiagent.git](https://github.com/YOUR_USERNAME/toc_aiagent.git)
cd toc_aiagent
2. Set Up Virtual Environment
It is recommended to use a virtual environment to manage dependencies.



# Create virtual environment
```bash
python -m venv .venv

# Activate it
# Windows:
.\.venv\Scripts\Activate
# Mac/Linux:
source .venv/bin/activate
```
3. Install Python Dependencies
The following libraries are imported and required for the project to run.
```bash
pip install ollama pydantic graphviz streamlit pytest
```
