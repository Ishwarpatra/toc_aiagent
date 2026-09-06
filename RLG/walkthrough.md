# Unified DFA Extraction & RLG Pipeline (Resilient v2)

The pipeline is now fully operational with corrected model mapping and robust fallback logic for both direct API limits and OpenRouter credit constraints.

## Recent Fixes
- **Resolved 404 Errors**: Updated Gemini model IDs to use verified API strings (e.g., `models/gemini-flash-latest`).
- **Resolved 400/404 on OpenRouter**: Identified and implemented verified free vision slugs like `google/gemma-3-27b-it:free`.
- **402 Credit Handling**: Added logic to detect and skip OpenRouter models when credit limits are hit.
- **Removed Groq**: Cleaned up all legacy `groq` code to resolve `ModuleNotFoundError`.

## How to Run

```bash
venv\Scripts\python.exe rlg.py
```

## Resilient Hierarchy

The system automatically traverses this list until success:

1.  **Direct Gemini (Primary Tier)**:
    - `gemini-flash-latest` (1.5 Flash)
    - `gemini-2.0-flash-lite`
    - `gemini-2.5-flash-lite`
2.  **Direct Gemini (Secondary Tier)**:
    - `gemini-2.0-flash`
    - `gemini-2.5-pro`
3.  **OpenRouter (Failsafe Tier)**:
    - `google/gemma-3-27b-it:free` (Verified Vision)
    - `nvidia/nemotron-nano-12b-v2-vl:free` (Verified Vision)

## Verification Results
In recent testing, when direct Gemini quotas were reached, the system **successfully failed over to OpenRouter** and completed the image scan using `google/gemma-3-27b-it:free`.
