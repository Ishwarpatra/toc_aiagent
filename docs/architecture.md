# Auto-DFA Architecture: Bidirectional Neuro-Symbolic Engine

Auto-DFA implements a bidirectional neuro-symbolic framework for formal language theory and automata computation:
1. **Forward Pipeline (Natural Language to DFA)**: Translates natural language descriptions into minimal, validated Deterministic Finite Automata.
2. **Reverse Pipeline (Image to Language & Grammar)**: Ingests state diagram images, parses them into formal schemas, computes Right-Linear Regular Grammars mathematically, and generates natural language descriptions.

---

## 1. Forward Pipeline (Natural Language -> DFA)

```
[User Prompt]
      │
      ▼
AnalystAgent ──► LogicSpec (AST) ──► ArchitectAgent ──► DFA Model
                                                          │
                                                          ▼
                                                DeterministicValidator
                                                    (Truth Check)
                                                          │
                                                          ▼
                                                     DFAOptimizer
                                                 (Minimization/Pruning)
```

### Components:
- **AnalystAgent**: Analyzes the input prompt. If it matches an atomic pattern (prefixes, suffixes, substrings, divisibility, modulo counts, lengths), it constructs an AST representation (`LogicSpec`). For complex multi-clause expressions, it splits top-level boolean operators (`AND`, `OR`, `NOT`).
- **ArchitectAgent**: Constructs DFAs from `LogicSpec` definitions using atomic builders or the product construction engine.
- **DeterministicValidator**: Simulates candidate strings against the semantic truth of the `LogicSpec` to guarantee correctness.
- **DFAOptimizer**: Uses BFS reachability analysis to prune unreachable states and dead states, yielding minimal automata.

---

## 2. Reverse Pipeline (Diagram Image -> Grammar -> Language)

```
[Diagram Image: PNG/JPEG/WEBP]
      │
      ▼ (Perception - AI)
VisionAgent (Gemini / OpenRouter Multimodal VLM)
      │
      ▼
DeterministicValidator (validate_structure)
      │
      ▼ (Formalization - Deterministic Math)
GrammarBuilder (Right-Linear Regular Grammar Engine)
      │
      ▼ (Translation - AI)
DescriberAgent (Natural Language Synthesis)
      │
      ▼
POST /reverse-engineer API Response
```

### Phase 1: Perception (AI)
- `VisionAgent` takes base64 image data and queries vision providers (`GeminiProvider`, `OpenRouterProvider`) with a strict JSON schema.
- The output is validated via `DeterministicValidator.validate_structure()` ensuring:
  - Start state belongs to the states set.
  - Accept states form a valid subset of states.
  - All transition targets and keys belong to valid states and alphabet symbols.

### Phase 2: Formalization (Deterministic Math)
- `GrammarBuilder` (`core/grammar.py`) implements the mathematical conversion from DFA to Right-Linear Grammar:
  1. Map start state $q_0 \to S$, remaining states $q_i \to A, B, C, \dots$
  2. For every transition $\delta(q_i, a) = q_j$, generate production rule:
     $$V_i \to aV_j$$
  3. For every accept state $q_k \in F$, generate epsilon production:
     $$V_k \to \varepsilon$$
  4. Formats human-readable output (`format_grammar()`).

### Phase 3: Translation (AI)
- `DescriberAgent` receives the validated `DFA` and Right-Linear Grammar and generates a concise, accurate single-sentence description of the accepted language (with deterministic heuristic fallbacks when offline).

---

## 3. Product Construction & Composition

Composing DFAs via product construction enables boolean logic:
- **Intersection ($L_1 \cap L_2$)**: Cartesian product with accept states $(q_a, q_b)$ where $q_a \in F_1 \land q_b \in F_2$.
- **Union ($L_1 \cup L_2$)**: Cartesian product with accept states $(q_a, q_b)$ where $q_a \in F_1 \lor q_b \in F_2$.
- **Inversion ($\overline{L}$)**: Swaps accept and non-accept states after completing transition tables.

### Safety Limits
To prevent state-space explosion, the system evaluates product upper bounds against `AUTO_DFA_MAX_PRODUCT_STATES` (default: 2000).

---

## 4. API Endpoints

- `POST /generate`: Forward pipeline endpoint (Prompt -> DFA).
- `POST /reverse-engineer`: Reverse pipeline endpoint (Image -> DFA + Grammar + Description).
- `POST /export/json`: Exports DFA schema as downloadable JSON.
- `POST /export/dot`: Exports Graphviz DOT representation.
- `POST /oracle/verify`: Runs ground-truth oracle tests against a DFA.
- `GET /health`: Health status and subsystem readiness.
