# Auto-DFA 🤖
### A Multi-Agent AI System for Visualizing Theory of Computation

**Auto-DFA** is a local, privacy-focused software tool that uses a **Multi-Agent Large Language Model (LLM) architecture** to convert natural language problem statements (e.g., *"strings ending in 'ab'"*) into mathematically rigorous, visual Deterministic Finite Automata (DFA).

![Project Status](https://img.shields.io/badge/Status-Prototype_Complete-success)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![AI Engine](https://img.shields.io/badge/AI_Engine-Ollama-orange)

---

## 📖 Table of Contents
- [Executive Summary](#-executive-summary)
- [Problem Statement](#-problem-statement)
- [System Architecture](#-system-architecture)
- [Tech Stack](#-tech-stack)
- [Installation & Setup](#-installation--setup)
- [How to Run](#-how-to-run)
- [Troubleshooting](#-troubleshooting)

---

## 🚀 Executive Summary
Students often struggle to visualize abstract concepts in **Theory of Computation (ToC)**. Existing tools (like JFLAP) require manual input and do not assist with the *logic* of design. 

**Auto-DFA** solves this by employing a "Teacher-Architect-Tester" loop. It uses small, efficient local LLMs (`qwen2.5-coder`) to design the logic, but relies on **deterministic Python code** to verify that logic, ensuring 100% mathematical accuracy before rendering the final graph.

---

## 🎯 Problem Statement
* **The Challenge:** Designing DFAs requires strict precision. Novice students often miss edge cases (e.g., dead states, resetting transitions).
* **The Solution:** An AI assistant that doesn't just give the answer but "thinks" through the design, verifies it against ground-truth code, and renders the visual graph automatically.

---

## 🏗 System Architecture

The system uses an **Iterative Feedback Loop** consisting of three specialized AI agents and one deterministic code engine.

### The Agent Roles

* **Agent 1: The Analyst**
    * **Engine:** Qwen 2.5-Coder (1.5B)
    * **Responsibility:** Parses user text into formal set-builder notation ($L=\{w | ...\}$) and constraints.

* **Agent 2: The Architect**
    * **Engine:** Qwen 2.5-Coder (1.5B)
    * **Responsibility:** Converts requirements into a JSON structure defining States ($Q$), Alphabet ($\Sigma$), and Transitions ($\delta$).

* **Agent 3: The Validator**
    * **Engine:** Python Code (Ground Truth)
    * **Responsibility:** Generates test strings and uses deterministic logic (e.g., `string.endswith()`) to strictly grade Agent 2's work.

### The "Self-Healing" Workflow
1.  **Drafting:** Agent 2 creates the initial JSON structure.
2.  **Auto-Repair:** Python script detects missing transitions and routes them to the start state (Reset Logic).
3.  **Verification:** Python runs a simulation against test cases. If a test fails, the error log is fed back to Agent 2.
4.  **Visualization:** Graphviz renders the final valid `.dot` file to a PNG image.

---

## 🛠 Tech Stack
* **Language:** Python 3.10+
* **Local Inference:** [Ollama](https://ollama.com/)
* **AI Model:** `qwen2.5-coder:1.5b` (Optimized for logic/code)
* **Data Validation:** [Pydantic](https://docs.pydantic.dev/) (Enforces strict JSON schemas)
* **Visualization:** [Graphviz](https://graphviz.org/)

---

## ⚙ Installation & Setup

### 1. Install Prerequisites
* **Python:** Ensure Python 3.10 or newer is installed.
* **Graphviz:** Download and install [Graphviz for Windows](https://graphviz.org/download/).  
    * *Critical:* Select **"Add Graphviz to the system PATH for all users"** during installation.
* **Ollama:** Download from [ollama.com](https://ollama.com).

### 2. Clone the Project
```bash
mkdir Auto-DFA
cd Auto-DFA
python -m venv .venv
# Activate Virtual Environment (Windows)
.\.venv\Scripts\Activate