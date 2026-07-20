import argparse
import os
import json
from typing import Iterable, List, Dict, Any

from core.models import DFA, DeterministicValidator
from dfa_image_scan import run_batch_scan


def dfa_to_rlg(dfa: DFA) -> Dict[str, List[str]]:
    grammar: Dict[str, List[str]] = {}

    for state in sorted(dfa.transitions):
        for symbol in sorted(dfa.transitions[state]):
            target = dfa.transitions[state][symbol]
            grammar.setdefault(state, []).append(f"{symbol} {target}")

    for state in sorted(dfa.accept_states):
        grammar.setdefault(state, []).append("ε")

    return grammar


def format_grammar(grammar: Dict[str, List[str]], start: str) -> str:
    lines = [f"Start symbol: {start}", "Productions:"]
    # Ensure start symbol is first
    non_terminals = [start] + sorted(k for k in grammar if k != start)
    for non_terminal in non_terminals:
        rhs = " | ".join(grammar[non_terminal])
        lines.append(f"  {non_terminal} -> {rhs}")
    return "\n".join(lines)


def _iter_json_files(path: str) -> Iterable[str]:
    if os.path.isfile(path):
        yield path
        return
    for root, _, files in os.walk(path):
        for name in sorted(files):
            if name.lower().endswith(".json"):
                yield os.path.join(root, name)


def load_dfa(json_path: str) -> DFA:
    with open(json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    dfa = DFA(**payload)
    if not DeterministicValidator.validate(dfa):
        raise ValueError("Loaded DFA failed deterministic validation.")
    return dfa


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Unified Pipeline: Scan DFA images and convert to RLG."
    )
    parser.add_argument(
        "image_source",
        nargs="?",
        default="images/input",
        help="Source folder for DFA images [Default: images/input]",
    )
    parser.add_argument(
        "--json-dir",
        default="outputs/dfa_json",
        help="Intermediate folder for DFA JSONs [Default: outputs/dfa_json]",
    )
    parser.add_argument(
        "--passes",
        type=int,
        default=3,
        help="Number of consensus passes per image [Default: 3]",
    )
    args = parser.parse_args()

    # Step 1: Run DFA Image Scan
    print(">>> STEP 1: Scanning DFA Images...")
    run_batch_scan(
        input_path=args.image_source,
        output_dir=args.json_dir,
        num_passes=args.passes
    )

    # Step 2: Convert to RLG
    print("\n>>> STEP 2: Converting DFAs to Right-Linear Grammar...")
    json_files = list(_iter_json_files(args.json_dir))
    if not json_files:
        print(f"No JSON files found at: {args.json_dir}. Skip RLG generation.")
        return

    for index, json_path in enumerate(json_files, start=1):
        try:
            print("-" * 40)
            print(f"[{index}/{len(json_files)}] Processing: {json_path}")
            dfa = load_dfa(json_path)
            grammar = dfa_to_rlg(dfa)
            print(format_grammar(grammar, dfa.start_state))
        except Exception as e:
            print(f"Error processing {json_path}: {e}")


if __name__ == "__main__":
    main()
