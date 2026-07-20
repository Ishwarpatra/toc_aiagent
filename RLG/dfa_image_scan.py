import os
import time
import base64
import json
from collections import Counter
from typing import Iterable, List, Dict, Optional, Any

import argparse
import mimetypes

from dotenv import load_dotenv
from core.models import DFA, DeterministicValidator
from core.providers import GeminiProvider, OpenRouterProvider, VisionProvider


DOTENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path=DOTENV_PATH)


# ── Method 2: Enhanced System Prompt ──────────────────────────────────────────
SYSTEM_PROMPT = """You are a precise automata extraction engine.
Read the provided DFA state-diagram image and return ONLY valid JSON with this exact schema:
{
  "states": ["q0", "q1"],
  "alphabet": ["0", "1"],
  "transitions": {
    "q0": {"0": "q0", "1": "q1"},
    "q1": {"0": "q0", "1": "q1"}
  },
  "start_state": "q0",
  "accept_states": ["q1"]
}

Extraction Rules:
- Include every detected state name exactly as written in the diagram.
- Start state is the state pointed to by the incoming start arrow (an arrow with no source state).
- Accept states are states drawn with a double-circle boundary. A state can be both start and accept.
- Use deterministic transition mapping: transitions[state][symbol] = next_state.

Edge-Tracing Instructions (follow carefully):
1. For EACH state, trace EVERY outgoing arrow to its destination. Read the symbol label on the arrow very carefully.
2. If the alphabet is binary {0, 1}, every state MUST have exactly 2 outgoing transitions — one for '0' and one for '1'. Verify this.
3. When arrows cross or overlap, trace each arrow from its source circle to its arrowhead destination carefully.
4. Self-loops (arrows that start and end at the same state) are valid transitions — do not skip them.
5. Double-check that the symbol on each arrow matches the transition you record.

Return JSON only. No markdown fences. No explanation."""


CORRECTION_PROMPT = """You previously extracted a DFA from this image, but the result has issues.

Here is the DFA you extracted:
{extracted_json}

Issues found:
{issues}

Please re-examine the image carefully and output a CORRECTED DFA in the same JSON format.
Focus specifically on the issues listed above. Trace each arrow carefully from source to destination.
Return JSON only. No markdown. No explanation."""


def _image_to_data_url(image_path: str) -> str:
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found: {image_path}")

    mime_type, _ = mimetypes.guess_type(image_path)
    if mime_type not in {"image/png", "image/jpeg", "image/jpg", "image/webp"}:
        raise ValueError("Supported image types: PNG, JPEG/JPG, WEBP.")

    with open(image_path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def _clean_json_text(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Model response did not contain a JSON object.")
    return cleaned[start : end + 1]


def _get_providers() -> List[VisionProvider]:
    """Initialize available providers based on environment variables."""
    providers = []
    
    # 1. Gemini (Primary/Secondary/Fallback)
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        providers.append(GeminiProvider(gemini_key.strip('"').strip("'").strip()))
        
    # 2. OpenRouter (Failsafe)
    or_key = os.environ.get("OPENROUTER_API_KEY")
    if or_key:
        providers.append(OpenRouterProvider(or_key.strip('"').strip("'").strip()))
        
    return providers

def _single_vlm_call(
    providers: List[VisionProvider],
    image_b64: str,
    system_prompt: str = SYSTEM_PROMPT,
    user_text: str = "Extract DFA structure from this diagram image.",
    model_override: Optional[str] = None
) -> DFA:
    """Make a VLM call across available providers and their candidate models."""
    last_error = None
    
    # Resolve candidate models per provider
    for provider in providers:
        if model_override:
            models = [model_override]
        else:
            models = provider.get_models()

        for model_name in models:
            for attempt in range(3):
                try:
                    payload = provider.call(model_name, system_prompt, user_text, image_b64)
                    dfa = DFA(**payload)
                    if not DeterministicValidator.validate(dfa):
                        raise ValueError("Extracted DFA failed deterministic validation.")
                    print(f"    Success: [{provider.__class__.__name__}] {model_name}")
                    return dfa
                except Exception as e:
                    last_error = e
                    if provider.is_rate_limit_daily(e):
                        print(f"    Daily limit reached for {model_name} on {provider.__class__.__name__}.")
                        break # Try next model or provider
                    
                    if "429" in str(e) or "rate limit" in str(e).lower():
                        print(f"    Minute rate limit on {model_name}. Retrying in 15s...")
                        time.sleep(15)
                    else:
                        print(f"    Error with {model_name}: {e}")
                        break # Try next model

    raise ValueError(f"All VLM providers and models failed. Last error: {last_error}")


# ── Method 1: Multi-Pass Consensus Voting ─────────────────────────────────────

def _majority(items: list[str]) -> str:
    """Return the most common item (majority vote)."""
    return Counter(items).most_common(1)[0][0]


def consensus_scan(
    image_path: str,
    model: str | None = None,
    num_passes: int = 3,
) -> DFA:
    """
    Run the VLM multiple times on the same image and merge results via
    majority voting per (state, symbol) -> target transition.
    """
    providers = _get_providers()
    if not providers:
        raise ValueError("No VLM providers configured (GROQ_API_KEY, GEMINI_API_KEY, etc.)")
    
    with open(image_path, "rb") as image_file:
        image_b64 = base64.b64encode(image_file.read()).decode("utf-8")

    # Collect individual DFA results
    results: list[DFA] = []
    for i in range(num_passes):
        try:
            dfa = _single_vlm_call(providers, image_b64, model_override=model)
            results.append(dfa)
            print(f"  Pass {i + 1}/{num_passes}: OK ({len(dfa.states)} states)")
        except Exception as e:
            print(f"  Pass {i + 1}/{num_passes}: FAILED ({e})")

    if not results:
        raise ValueError("All consensus passes failed.")

    # --- Consensus: States & Alphabet ---
    # Use union of all detected states/alphabet (don't lose any detections)
    all_states: set[str] = set()
    all_alphabet: set[str] = set()
    for dfa in results:
        all_states.update(dfa.states)
        all_alphabet.update(dfa.alphabet)

    # --- Consensus: Start State ---
    start_votes = [dfa.start_state for dfa in results]
    consensus_start = _majority(start_votes)

    # --- Consensus: Accept States ---
    # Include a state as accepting if >= half of the runs agree
    accept_counter: Counter[str] = Counter()
    for dfa in results:
        for state in dfa.accept_states:
            accept_counter[state] += 1
    threshold = len(results) / 2
    consensus_accept = {s for s, c in accept_counter.items() if c >= threshold}

    # --- Consensus: Transitions (majority vote per cell) ---
    consensus_transitions: Dict[str, Dict[Any, str]] = {}
    for state in all_states:
        consensus_transitions[state] = {}
        state_dict: Dict[Any, str] = consensus_transitions[state]
        for symbol in all_alphabet:
            votes: list[str] = []
            for result_dfa in results:
                target = result_dfa.transitions.get(state, {}).get(symbol)
                if target is not None:
                    votes.append(target)
            if votes:
                state_dict[symbol] = _majority(votes)

    consensus_dfa = DFA(
        states=all_states,
        alphabet=all_alphabet,
        transitions=consensus_transitions,
        start_state=consensus_start,
        accept_states=consensus_accept,
    )
    return consensus_dfa


# ── Method 3: Completeness Validation + Self-Correction ───────────────────────

def _find_dfa_issues(dfa: DFA) -> list[str]:
    """Check a DFA for completeness issues. Returns a list of issue descriptions."""
    issues: list[str] = []

    # Check that every state has a transition for every alphabet symbol
    for state in sorted(dfa.states):
        for symbol in sorted(dfa.alphabet):
            if symbol not in dfa.transitions.get(state, {}):
                issues.append(
                    f"State '{state}' is missing a transition on symbol '{symbol}'."
                )

    # Check that all transition targets are valid states
    for state, trans in dfa.transitions.items():
        for symbol, target in trans.items():
            if target not in dfa.states:
                issues.append(
                    f"Transition d({state},{symbol}) -> '{target}' targets an unknown state."
                )

    return issues


def self_correct_dfa(
    dfa: DFA,
    image_path: str,
    model: str | None = None,
) -> DFA:
    """
    Validate a DFA for completeness. If issues are found, send the image
    back to the VLM with the partial result for correction.
    Only fills in MISSING transitions — does not overwrite consensus results.
    """
    issues = _find_dfa_issues(dfa)

    if not issues:
        print("  Self-correction: DFA is complete, no issues found.")
        return dfa

    print(f"  Self-correction: Found {len(issues)} issue(s), requesting VLM correction...")
    for issue in issues:
        print(f"    - {issue}")

    providers = _get_providers()
    with open(image_path, "rb") as image_file:
        image_b64 = base64.b64encode(image_file.read()).decode("utf-8")

    correction_text = CORRECTION_PROMPT.format(
        extracted_json=json.dumps(dfa.model_dump(mode="json"), indent=2),
        issues="\n".join(f"- {i}" for i in issues),
    )

    try:
        corrected_dfa = _single_vlm_call(
            providers, image_b64,
            system_prompt=SYSTEM_PROMPT,
            user_text=correction_text,
            model_override=model
        )

        # Merge: only fill in missing transitions, keep consensus values
        merged_transitions: Dict[str, Dict[Any, str]] = {s: dict(t) for s, t in dfa.transitions.items()}
        for state in dfa.states:
            if state not in merged_transitions:
                merged_transitions[state] = {}
            state_trans: Dict[Any, str] = merged_transitions[state]
            for symbol in dfa.alphabet:
                if symbol not in state_trans:
                    # Use corrected value if available
                    corrected_target = corrected_dfa.transitions.get(state, {}).get(symbol)
                    if corrected_target and corrected_target in dfa.states:
                        state_trans[symbol] = corrected_target
                        print(f"    Filled d({state},{symbol}) -> {corrected_target}")

        # Also merge accept states: if correction adds any that are valid states
        merged_accept = set(dfa.accept_states)
        for state in corrected_dfa.accept_states:
            if state in dfa.states and state not in merged_accept:
                merged_accept.add(state)
                print(f"    Added accept state: {state}")

        return DFA(
            states=dfa.states,
            alphabet=dfa.alphabet,
            transitions=merged_transitions,
            start_state=dfa.start_state,
            accept_states=merged_accept,
        )
    except Exception as e:
        print(f"  Self-correction failed: {e}. Using consensus result as-is.")
        return dfa


# ── Combined Pipeline ─────────────────────────────────────────────────────────

def scan_dfa_image(
    image_path: str,
    model: str | None = None,
    num_passes: int = 3,
    use_consensus: bool = True,
) -> DFA:
    """
    Full pipeline: Enhanced Prompt + Multi-Pass Consensus + Self-Correction.

    Args:
        image_path: Path to DFA diagram image.
        model: Optional Groq vision model override.
        num_passes: Number of consensus passes (default 3).
        use_consensus: If False, fall back to single-pass extraction.
    """
    if not use_consensus or num_passes <= 1:
        # Single-pass mode (original behaviour with enhanced prompt)
        providers = _get_providers()
        with open(image_path, "rb") as image_file:
            image_b64 = base64.b64encode(image_file.read()).decode("utf-8")
        return _single_vlm_call(providers, image_b64, model_override=model)

    # Method 1: Multi-pass consensus
    dfa = consensus_scan(image_path, model=model, num_passes=num_passes)

    # Method 3: Self-correction for any remaining gaps
    dfa = self_correct_dfa(dfa, image_path, model=model)

    # Final validation
    if not DeterministicValidator.validate(dfa):
        print("  WARNING: Final DFA did not pass deterministic validation.")

    return dfa


# ── CLI helpers ───────────────────────────────────────────────────────────────

def _to_output_json_path(image_path: str, input_root: str, output_dir: str) -> str:
    rel = os.path.relpath(image_path, input_root) if os.path.isdir(input_root) else os.path.basename(image_path)
    base, _ = os.path.splitext(rel)
    return os.path.join(output_dir, f"{base}.json")


def _iter_image_files(path: str) -> Iterable[str]:
    if os.path.isfile(path):
        yield path
        return

    allowed_ext = {".png", ".jpg", ".jpeg", ".webp"}
    for root, _, files in os.walk(path):
        for name in sorted(files):
            _, ext = os.path.splitext(name.lower())
            if ext in allowed_ext:
                yield os.path.join(root, name)


def run_batch_scan(
    input_path: str = "images/input",
    output_dir: str = "outputs/dfa_json",
    model: Optional[str] = None,
    num_passes: int = 3,
    use_consensus: bool = True
) -> int:
    """
    Run the DFA scanning pipeline on a file or directory of images.
    Returns the count of successfully scanned images.
    """
    image_files = list(_iter_image_files(input_path))
    if not image_files:
        print(f"No supported image files found at: {input_path}")
        return 0

    mode_label = f"Consensus ({num_passes} passes) + Self-Correction" if use_consensus else "Single-pass"
    print(f"Mode: {mode_label}")

    os.makedirs(output_dir, exist_ok=True)
    success_count = 0
    for index, image_path in enumerate(image_files, start=1):
        print("=" * 80)
        print(f"[{index}/{len(image_files)}] Scanning image: {image_path}")
        try:
            dfa = scan_dfa_image(
                image_path,
                model=model,
                num_passes=num_passes,
                use_consensus=use_consensus,
            )
            output_json_path = _to_output_json_path(image_path, input_path, output_dir)
            os.makedirs(os.path.dirname(output_json_path), exist_ok=True)
            with open(output_json_path, "w", encoding="utf-8") as f:
                json.dump(dfa.model_dump(mode="json"), f, indent=2)
            print(f"Saved DFA JSON: {output_json_path}")
            success_count += 1
        except Exception as e:
            print(f"\nFailed to scan {image_path}: {e}")

    print("=" * 80)
    print(f"Completed Scan. Successfully scanned {success_count}/{len(image_files)} image(s).")
    return success_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan DFA image(s) with VLM and output structured DFA JSON files."
    )
    parser.add_argument(
        "input_path",
        nargs="?",
        default="images/input",
        help="Path to DFA image(s) [Default: images/input]",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/dfa_json",
        help="Folder for DFA JSON output [Default: outputs/dfa_json]",
    )
    parser.add_argument("--model", default=None, help="Optional vision model override")
    parser.add_argument(
        "--passes",
        type=int,
        default=3,
        help="Number of consensus passes per image (default: 3)",
    )
    parser.add_argument(
        "--no-consensus",
        action="store_true",
        help="Disable multi-pass consensus (single-pass mode)",
    )
    args = parser.parse_args()

    run_batch_scan(
        input_path=args.input_path,
        output_dir=args.output_dir,
        model=args.model,
        num_passes=args.passes,
        use_consensus=not args.no_consensus
    )


if __name__ == "__main__":
    main()
