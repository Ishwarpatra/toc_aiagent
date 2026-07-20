"""
DFA Accuracy Comparison
-----------------------
Compares VLM-extracted DFA JSON outputs against ground-truth DFA JSONs.

Metrics per test file:
  - Transition Accuracy  : % of (state, symbol) pairs with correct target state
  - Start State Detection : 1.0 if correct, 0.0 otherwise
  - Accept State Detection: Jaccard similarity between predicted and actual accept sets

Overall accuracy is the average across all test files.

Usage:
    python test_accuracy/compare.py
"""

import json
import os
import sys

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
VLM_DIR = os.path.join(PROJECT_ROOT, "outputs", "dfa_json")
GT_DIR = os.path.join(PROJECT_ROOT, "ground_truth")
REPORT_PATH = os.path.join(SCRIPT_DIR, "accuracy_report.txt")


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def transition_accuracy(vlm: dict, gt: dict) -> tuple[float, str]:
    """
    Compare transitions for every (state, symbol) pair present in the
    ground truth.  Returns (accuracy_float, detail_string).
    """
    gt_trans = gt.get("transitions", {})
    vlm_trans = vlm.get("transitions", {})

    total = 0
    correct = 0
    mismatches: list[str] = []

    for state, symbols in gt_trans.items():
        for symbol, expected_target in symbols.items():
            total += 1
            vlm_target = vlm_trans.get(state, {}).get(symbol)
            if vlm_target == expected_target:
                correct += 1
            else:
                mismatches.append(
                    f"    δ({state},{symbol}): expected {expected_target}, got {vlm_target}"
                )

    acc = correct / total if total else 1.0
    detail = f"{correct}/{total} correct"
    if mismatches:
        detail += "\n" + "\n".join(mismatches)
    return acc, detail


def start_state_accuracy(vlm: dict, gt: dict) -> tuple[float, str]:
    expected = gt.get("start_state")
    predicted = vlm.get("start_state")
    match = expected == predicted
    detail = f"expected {expected}, got {predicted}" + (" ✓" if match else " ✗")
    return (1.0 if match else 0.0), detail


def accept_state_accuracy(vlm: dict, gt: dict) -> tuple[float, str]:
    """
    Jaccard similarity: |intersection| / |union|.
    If both sets are empty ⇒ 1.0 (model correctly predicted no accept states).
    """
    expected = set(gt.get("accept_states", []))
    predicted = set(vlm.get("accept_states", []))

    if not expected and not predicted:
        return 1.0, "both empty ✓"

    intersection = expected & predicted
    union = expected | predicted
    acc = len(intersection) / len(union) if union else 1.0

    detail = f"expected {sorted(expected)}, got {sorted(predicted)}"
    if expected == predicted:
        detail += " ✓"
    else:
        missing = expected - predicted
        extra = predicted - expected
        parts = []
        if missing:
            parts.append(f"missing {sorted(missing)}")
        if extra:
            parts.append(f"extra {sorted(extra)}")
        detail += f" ✗ ({', '.join(parts)})"

    return acc, detail


def main() -> None:
    # Discover matching test files
    gt_files = {
        f for f in os.listdir(GT_DIR) if f.endswith(".json")
    }
    vlm_files = {
        f for f in os.listdir(VLM_DIR) if f.endswith(".json")
    }
    common = sorted(gt_files & vlm_files)

    if not common:
        print("ERROR: No matching JSON files found between ground_truth/ and outputs/dfa_json/")
        sys.exit(1)

    # ── Per-file results ───────────────────────────────────────────────────────
    all_trans_acc: list[float] = []
    all_start_acc: list[float] = []
    all_accept_acc: list[float] = []

    lines: list[str] = []
    lines.append("=" * 80)
    lines.append("DFA ACCURACY REPORT — VLM Outputs vs Ground Truth")
    lines.append("=" * 80)

    for filename in common:
        gt_data = load_json(os.path.join(GT_DIR, filename))
        vlm_data = load_json(os.path.join(VLM_DIR, filename))

        t_acc, t_detail = transition_accuracy(vlm_data, gt_data)
        s_acc, s_detail = start_state_accuracy(vlm_data, gt_data)
        a_acc, a_detail = accept_state_accuracy(vlm_data, gt_data)

        file_overall = (t_acc + s_acc + a_acc) / 3.0

        all_trans_acc.append(t_acc)
        all_start_acc.append(s_acc)
        all_accept_acc.append(a_acc)

        lines.append("")
        lines.append(f"─── {filename} ─── Overall: {file_overall * 100:.1f}%")
        lines.append(f"  Transition Accuracy   : {t_acc * 100:.1f}%  ({t_detail})")
        lines.append(f"  Start State Detection : {s_acc * 100:.1f}%  ({s_detail})")
        lines.append(f"  Accept State Detection: {a_acc * 100:.1f}%  ({a_detail})")

    # ── Overall summary ────────────────────────────────────────────────────────
    n = len(common)
    avg_trans = sum(all_trans_acc) / n
    avg_start = sum(all_start_acc) / n
    avg_accept = sum(all_accept_acc) / n
    avg_overall = (avg_trans + avg_start + avg_accept) / 3.0

    lines.append("")
    lines.append("=" * 80)
    lines.append(f"OVERALL ACCURACY  ({n} test files)")
    lines.append("=" * 80)
    lines.append(f"  Transition Accuracy   : {avg_trans * 100:.1f}%")
    lines.append(f"  Start State Detection : {avg_start * 100:.1f}%")
    lines.append(f"  Accept State Detection: {avg_accept * 100:.1f}%")
    lines.append(f"  ── Combined Average ──: {avg_overall * 100:.1f}%")
    lines.append("=" * 80)

    report = "\n".join(lines)

    # Print to console
    print(report)

    # Save to file
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report + "\n")
    print(f"\nReport saved to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
