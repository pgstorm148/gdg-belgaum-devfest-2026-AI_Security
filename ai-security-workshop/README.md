# AI Security — Breaking, Securing & Building Trustworthy AI Applications

Companion repo for the GDG DevFest Belgaum session: five live demos, an attack **arena**
that runs the same attacks against **GPT, Gemini and Claude**, a browser playground, a
take-home lab, and tests.

**Works offline out of the box** (deterministic simulator, no GPU, no API key).
**Add one API key** and every demo, the arena and the lab run against a real model.
Everything (companies, people, orders, keys) is fictional. Every "key" is a fake **canary** value.

| # | Demo | OWASP LLM Top 10 (2026) | What you see |
|---|------|------------------------|--------------|
| 1 | Prompt injection (direct + indirect) | LLM01 Prompt Injection | A support bot obeys a hidden HTML comment in a product review |
| 2 | Secret leakage | LLM02 Sensitive Info Disclosure, LLM08 Hidden Context Exposure | An API key leaks; an exact-match filter is bypassed by spelling the key out |
| 3 | RAG poisoning | LLM05 Data & Model Poisoning, LLM09 Vector & Embedding Weaknesses | One edited wiki page rewrites the refund policy |
| 4 | Agent tool abuse | LLM03 Excessive Agency | An agent refunds someone else's order because a delivery note told it to |
| 5 | Multi-turn & PAV defences | LLM01 (multi-turn) + original research | Session-level auditing catches what per-turn filters miss |

---

## 1. Prerequisites

- **Python 3.10 or newer**: check with `python --version` (use `python3` on macOS/Linux if `python` is missing)
- Git (or download the ZIP)
- Optional, for real models: a key from **Gemini** (free tier), **OpenAI** or **Anthropic**, or [Ollama](https://ollama.com) locally

## 2. Setup (2 minutes)

```bash
git clone <REPO_URL>            # or unzip the download
cd ai-security-workshop
python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
pip install -r requirements.txt  # optional: only needed for the browser UI (Streamlit)
```

The terminal demos, the arena and the lab need **no packages at all**.

## 3. Run the demos

```bash
python demos/demo1_prompt_injection.py
python demos/demo2_secret_leakage.py
python demos/demo3_rag_poisoning.py
python demos/demo4_agent_tool_abuse.py
python demos/demo5_pav_defenses.py
python run_all.py --step        # everything, pausing after each scenario
streamlit run app.py             # browser UI: Playground · Arena · Stage demos
```

Flags (demos 1–4):

| Flag | Meaning |
|------|---------|
| `--backend sim` / `gpt` / `gemini` / `claude` / `ollama` | which model (default `sim`) |
| `--mode vulnerable` / `secure` / `both` | which build (demo 2: `--build vulnerable/patched/secure/all`) |
| `--without output_policy,…` | the secure build minus these defences (ablation) |
| `--with sanitize,…` | only these defences on |
| `--show-prompt` | print the exact API request sent to the model |
| `--attack "your text"` | try your own message (demo 3: `--question`) |
| `--step` | pause after each scenario (use this on stage) |
| `--approve` | demo 4 only: the simulated human approver says yes |

## 4. Run against real models: GPT · Gemini · Claude

```bash
cp .env.example .env              # then paste your key(s) into .env
python -m common.llm gemini       # smoke test
python demos/demo1_prompt_injection.py --backend gemini --show-prompt
python arena.py --backends gpt,gemini,claude --trials 3
```

**Full student guide with exercises: [ARENA.md](ARENA.md).**

| Backend | Key | Default model (override in `.env`) | Deterministic? |
|---------|-----|-----------------------------------|----------------|
| `sim` | none | simulator of a vulnerable model | **Yes** |
| `gpt` / `openai` | `OPENAI_API_KEY` | `OPENAI_MODEL=gpt-6.1-terra` | No |
| `gemini` | `GEMINI_API_KEY` | `GEMINI_MODEL=gemini-3.5-flash-lite` | No |
| `claude` / `anthropic` | `ANTHROPIC_API_KEY` | `ANTHROPIC_MODEL=claude-haiku-5-5` | No |
| `ollama` | none | `OLLAMA_MODEL=llama3.2` | No |

Real backends use each provider's **native tool calling**, like production agents do. The code is
standard-library `urllib` in `common/providers.py`: read `neutral_turns()` to see exactly how a
retrieved document ends up in the same request as your system prompt.

**What to expect:** the simulator falls for every attack, on purpose. Real models resist some
attacks some of the time, and that changes between models, versions and runs. That's why the
arena reports a success *rate* (k/n), and why every secure build is designed to hold even when
the model is fully fooled. The arena marks those cases `(+m caught)`.

## 5. Tests

```bash
python -m unittest discover -s tests -v              # 25 offline tests (2 live ones skip)
LAB_TARGET=solution python lab/test_lab.py            # lab reference solution: 3/3
LIVE_TESTS=1 python -m unittest tests.test_live -v    # real models: secure builds must hold
```

| File | Proves |
|------|--------|
| `tests/test_demos.py` | every stage demo still tells its story (vulnerable falls, secure holds) |
| `tests/test_defenses.py` | all 14 attacks beat the vulnerable build and fail against the secure one; removing the specific layer that stops each attack reopens the hole; heuristic detectors have documented gaps |
| `tests/test_providers.py` | GPT / Claude / Gemini requests are shaped correctly and full agent loops round-trip in each provider's native tool format (offline, with scripted API responses); secure builds hold even when the model obeys the attacker; 429 retry works |
| `tests/test_live.py` | opt-in, real APIs: every secure build holds on every configured model, and normal requests still work |

## 6. Project layout

```
ai-security-workshop/
├── common/
│   ├── llm.py          # simulator, Reply type, get_llm()
│   ├── providers.py    # OpenAI · Anthropic · Gemini · Ollama with native tool calling
│   ├── guards.py       # injection tripwire, output policy, canary check, audit log, rate limiter
│   ├── cli.py · env.py · ui.py
├── demos/              # demo1 … demo5 (every defence switchable)
├── attack_lib/         # 14 attacks with objective success checks
├── arena.py            # multi-model, multi-trial attack success matrix → reports/
├── app.py              # Streamlit: Playground · Arena · Stage demos
├── data/               # fictional FAQ, reviews, orders, knowledge base
├── lab/                # take-home lab (starter, solution, tests): see LAB.md
├── tests/
├── slides/             # the talk deck (.pptx, speaker notes included)
├── ARENA.md  LAB.md  SLIDE_GUIDE.md  TROUBLESHOOTING.md  .env.example
```

## 7. The defences, in one place

| Defence | Switch name | Reads attacker text? | Demo |
|---------|-------------|---------------------|------|
| Input tripwire | `tripwire` | yes, so it's bypassable | 1, lab |
| Strip hidden markup | `sanitize` | yes | 1 |
| Quarantine suspicious docs | `quarantine`, `ingest_scan` | yes, so it's bypassable | 1, 3 |
| Spotlight untrusted data | `spotlight` | n/a (a hint to the model) | 1, 3 |
| Output domain allowlist | `output_policy` | **no: checks the outcome** | 1, 3 |
| Secret out of the prompt | `secret_out_of_prompt` | **no: architecture** | 2 |
| Canary monitor | `canary_monitor` | **no: checks the outcome** | 2, lab |
| Provenance / trust filter | `trust_filter` | **no: metadata** | 3 |
| Identity from session | `session_identity` | **no: auth** | 4, lab |
| Ownership check | `ownership` | **no: auth** | 4 |
| Amount limit | `amount_limit` | **no: business rule** | 4 |
| Human approval | `human_approval` | **no: a person** | 4 |
| Redact tool output | `redact_tool_output` | yes, so it's bypassable | 4 |

> The pattern: defences that **read the attacker's words** can be out-written. Defences that
> check **outcomes, identity and provenance** in code can't be talked out of anything.

## 8. Ethics

Use these techniques only on systems you own or are explicitly authorised to test. Never try
them against production systems, college portals, or other people's apps.

## 9. References

- OWASP Top 10 for LLM Applications 2026 — https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/
- OWASP Top 10 for Agentic Applications — https://genai.owasp.org
- Greshake et al., *Not what you've signed up for* (indirect prompt injection), arXiv:2302.12173
- Perez & Ribeiro, *Ignore Previous Prompt*, arXiv:2211.09527
- Russinovich et al., *Crescendo multi-turn jailbreak*, arXiv:2404.01833
- Gandhi, P., *I Cannot Comply, But I Can Teach: The Pedagogical Acceleration Vector in Safety-Aligned LLMs*, SSRN 6860600
