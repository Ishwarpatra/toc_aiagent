# Auto-DFA Design Direction

> This file satisfies R-37 of the antislop system. It exists so every future UI decision has a written reason, not a default.

## Identity

**Auto-DFA** is a precision tool for computer science and formal language theory. It takes natural language and produces mathematically exact state machines. The experience should feel like a high-end technical instrument — not a consumer SaaS product.

**The user:** a CS student, researcher, or engineer who knows what a DFA is. They trust the tool to be correct. They do not need to be charmed.

**The promise:** describe a language, get a verified diagram. Fast, correct, no noise.

---

## Palette

| Token | Value | Ratio (on white) | Reason |
|-------|-------|------------------|--------|
| `--bg-primary` | `#f5f5f5` | — | Warm off-white; easier on the eye than pure white for long sessions |
| `--bg-secondary` | `#ffffff` | — | Canvas and card surfaces |
| `--text-primary` | `#333333` | 12.63:1 PASS | Near-black; not pure black (softer) |
| `--text-secondary` | `#666666` | 5.74:1 PASS | Supporting labels |
| `--text-muted` | `#767676` | 4.54:1 PASS | Minimum AA compliant muted text |
| `--accent-primary` | `#4a90d9` | decorative only | Borders, icons, focus rings |
| `--accent-text` | `#2878c8` | 5.50:1 PASS | Interactive text (hover states, links) |
| `--error-text` | `#b91c1c` | 5.28:1 on error-bg PASS | Error messages, text-first |

**Sidebar gradient:** `#1e2d4a to #2c3e6b` (deep navy).
**Reason:** navy communicates precision, logic, and technical authority. The generic blue-purple (#667eea to #764ba2) was rejected because it is the most common AI-generated UI gradient and carries no identity.

---

## Typography

- **Font:** Inter (loaded from system or Google Fonts)
- **Reason:** Inter is designed for UI screens. Its optical sizing and tabular numbers make state/transition counts readable at small sizes.
- **Base size:** 14px (comfortable for a data-dense tool)
- **Labels:** 12px, uppercase, 0.5px letter-spacing (section headers, not headings)

---

## Mood Dials

| Dial | Setting | Why |
|------|---------|-----|
| ENERGY | Low | This is not a consumer app. Calm precision. |
| RHYTHM | Minimal | Animations only where they carry meaning (spinner during generation, pan/zoom feedback). |
| MOTION | Functional | One animation: the loading spinner. |
| BRAND LOUDNESS | Quiet | The DFA diagram is the hero. No element competes with it. |

---

## Component Rules

1. **The SVG canvas is the product.** Everything else is scaffolding.
2. **No decorative animations.** `transform: translateY(-2px)` on buttons is the ceiling.
3. **Error states are text-first.** Color supports; it does not carry.
4. **Mobile is supported, not optimized.** Primary use case is desktop.

---

## Anti-patterns (banned)

- Generic blue-purple or indigo-violet gradients
- Glassmorphism (backdrop-filter blur on cards, navbars, and modals simultaneously)
- Glow on more than the active node in the DFA diagram
- Emoji in UI copy
- Placeholder empty states that say only "No data"
