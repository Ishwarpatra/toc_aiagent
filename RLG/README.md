# DFA to Right-Linear Grammar (RLG) Pipeline

This project automates the extraction of Deterministic Finite Automata (DFA) from images and converts them into formal Right-Linear Grammars. It uses a resilient, high-accuracy pipeline featuring multi-pass consensus and automatic provider failover.

## Workflow

The system operates in a two-stage unified pipeline:

1.  **Stage 1: Image Extraction (VLM)**
    - Scans DFA diagrams using Vision Language Models.
    - Uses **3-Pass Consensus**: Takes three independent "votes" per image to ensure accurate state and transition detection.
    - **Self-Correction**: Automatically detects if a DFA is incomplete and attempts to fill missing transitions using a secondary model pass.
    - **Resilient Fallback**: Automatically switches between Direct Gemini APIs and OpenRouter models if rate limits or credit issues are encountered.

2.  **Stage 2: Grammar Generation**
    - Converts the extracted DFA JSON into a formatted Right-Linear Grammar.
    - Identifies start symbols and productions (e.g., `q0 -> a q1 | ε`).

## Setup

1.  **Environment Variables**: Create a `.env` file in the root directory:
    ```text
    GEMINI_API_KEY="your_google_key"
    OPENROUTER_API_KEY="your_openrouter_key"
    ```
2.  **Python Environment**:
    ```bash
    # Recommended skip if already set up
    pip install -r requirements.txt
    ```

## How to Run

Perform the entire scan-to-grammar process with one command:

```bash
venv\Scripts\python.exe rlg.py
```

- **Input Folder**: `images\input` (Place your PNG/JPG diagrams here)
- **Output Folder**: `outputs\dfa_json` (Extracted JSONs)

## Accuracy Testing

To evaluate the pipeline against ground truth data:

```bash
venv\Scripts\python.exe test_accuracy\compare.py
```

This will compare the generated JSONs in `outputs\dfa_json` against the manual labels in `ground_truth` and output a detailed accuracy report.

## Directory Structure
- `core/`: Core logic (model definitions, providers, agents).
- `images/input/`: Source DFA images.
- `ground_truth/`: Hand-labeled JSON files for accuracy comparison.
- `outputs/dfa_json/`: Machine-extracted DFA JSON files.
- `dfa_image_scan.py`: Low-level image scanning module.
- `rlg.py`: Main entry point and grammar generator.
