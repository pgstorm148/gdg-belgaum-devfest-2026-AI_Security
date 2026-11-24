# Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `python: command not found` | Python not on PATH, or only `python3` exists | Use `python3`, or reinstall Python and tick "Add to PATH" (Windows) |
| `SyntaxError` on `str \| None` or `list[dict]` | Python older than 3.10 | Install Python 3.10+ (`python --version`) |
| `ModuleNotFoundError: No module named 'common'` | Running from the wrong folder | `cd ai-security-workshop` first, then run `python demos/...` |
| Strange characters like `←[31m` instead of colours | Old Windows console | Use Windows Terminal, or set `NO_COLOR=1` |
| `₹` or box characters show as `?` (Windows) | Console code page | Run `chcp 65001`, or `set PYTHONIOENCODING=utf-8` |
| `Backend error: Could not reach http://localhost:11434` | Ollama not running | Start the Ollama app or `ollama serve`, then `ollama pull llama3.2`. Or use `--backend sim` |
| Ollama: `model "llama3.2" not found` | Model not pulled | `ollama pull llama3.2`, or set `OLLAMA_MODEL` to a model you have (`ollama list`) |
| `… API_KEY is not set` | No key in `.env` or this terminal | Put it in `.env` (see `.env.example`), or `export OPENAI_API_KEY=...` (PowerShell: `$env:OPENAI_API_KEY="..."`) |
| `HTTP 401` / `403` | Wrong or revoked key, or no billing on the account | Re-copy the key; OpenAI and Anthropic need billing set up |
| `HTTP 404` / "model not found" | Model name retired or not available to your key | Set `OPENAI_MODEL` / `GEMINI_MODEL` / `ANTHROPIC_MODEL` in `.env`. Gemini: `python -m common.llm --list-gemini-models` |
| `HTTP 400 … unsupported parameter` (temperature, max_tokens) | Newer models reject some sampling params | Leave `LLM_TEMPERATURE` empty (the default). Report the message if it names another param |
| `HTTP 429` | Rate limit / free-tier quota | Retried automatically 3×. Then lower `--trials`, wait a minute, or use `--backend sim` |
| Empty reply from GPT or Gemini | Reasoning tokens used up the output budget | Raise `LLM_MAX_TOKENS` (default 4096) |
| A real model *refuses* the normal refund in demo 4 | Model caution varies | Expected sometimes. The arena counts outcomes, not politeness; re-run or try another model |
| Arena says COMPROMISED but the reply looks like a refusal | The automatic check found the attacker's domain/canary quoted in the reply | Read the transcript in `reports/`. Automated checks can misfire; that's why transcripts are saved |
| A real model (GPT/Gemini/Claude/Ollama) *didn't* fall for the attack | Expected: real models are probabilistic and vary by version | That's the lesson: you can't predict which attempt succeeds. The secure builds don't depend on it. Run it a few times, or try the `--attack` flag with a rephrased attack |
| `streamlit: command not found` | Streamlit not installed in the active venv | Activate the venv, `pip install -r requirements.txt`, or run `python -m streamlit run app.py` |
| Streamlit opens but the page is blank | Browser blocked localhost | Open the URL printed in the terminal (usually http://localhost:8501) |
| Lab tests still fail after your fix | `LAB_TARGET` still set to something else, or old log file | `unset LAB_TARGET` (PowerShell: `Remove-Item Env:LAB_TARGET`); tests delete the log themselves |
| `PermissionError` writing `logs/` | Repo in a read-only or synced folder | Move the repo to a normal folder (e.g. your home directory) |

## Live-demo fallbacks (for the speaker)

1. **Primary:** `python run_all.py --step` with the `sim` backend. Offline, deterministic, ~60 s per demo.
2. **Projector UI:** `streamlit run app.py` (needs `pip install streamlit` done *before* the venue).
3. **No laptop / no Python:** the deck has a pre-rendered terminal slide for every demo.
4. **Real-model moment:** run `python arena.py --backends gpt,gemini,claude --attacks 1.4,4.4 --trials 2 --yes`
   the night before and keep the `reports/` file as a fallback slide. Live, run one attack in the Playground with
   **What the model actually received** open. If a model resists, say so on stage: it makes the point better than a staged success.

Pre-flight checklist (night before):

```bash
python -m unittest discover -s tests      # 25 tests OK (2 live skipped)
LIVE_TESTS=1 python -m unittest tests.test_live   # with keys: secure builds hold on real models
LAB_TARGET=solution python lab/test_lab.py # 3 tests OK
python run_all.py > /dev/null && echo READY
```
