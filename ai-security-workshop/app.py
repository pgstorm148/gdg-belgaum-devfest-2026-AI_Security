"""
Workshop UI.   streamlit run app.py

Tabs
  🎯 Playground   pick an attack (or write your own), edit the poisoned data, choose a model,
                 switch defences on/off, and see EXACTLY what the model received
  🏟️ Arena        run attacks against GPT, Gemini and Claude side by side, several trials each
  🎬 Stage demos  the deterministic demos used on stage

API keys typed in the sidebar live only in this Streamlit process (never written to disk).
Run this on your own laptop. Don't deploy it publicly with keys in it.
"""
import copy
import io
import json
import os
import sys
from contextlib import redirect_stdout

import streamlit as st

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "demos"))

from attack_lib.attacks import ATTACKS, SCENARIOS, run_attack  # noqa: E402
from common.env import load_env  # noqa: E402
from common.llm import available_backends, get_llm  # noqa: E402
import demo1_prompt_injection as d1  # noqa: E402
import demo2_secret_leakage as d2  # noqa: E402
import demo3_rag_poisoning as d3  # noqa: E402
import demo4_agent_tool_abuse as d4  # noqa: E402
import demo5_pav_defenses as d5  # noqa: E402

load_env()
st.set_page_config(page_title="AI Security Workshop", page_icon="🛡️", layout="wide")
st.title("🛡️ Breaking & Securing AI Applications")
st.caption("All companies, people, keys and orders are fictional. Every 'secret' is a fake canary value.")

# ------------------------------------------------------------------ sidebar: keys & models
with st.sidebar:
    st.header("Models")
    st.caption("Keys stay in memory for this session only. You can also put them in a .env file.")
    for label, env, model_env, default in [
        ("OpenAI (GPT)", "OPENAI_API_KEY", "OPENAI_MODEL", "gpt-6.1-terra"),
        ("Google Gemini", "GEMINI_API_KEY", "GEMINI_MODEL", "gemini-3.5-flash-lite"),
        ("Anthropic Claude", "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "claude-haiku-5-5"),
    ]:
        with st.expander(label, expanded=False):
            k = st.text_input("API key", type="password", key=env, placeholder="already set" if os.getenv(env) else "")
            if k:
                os.environ[env] = k.strip()
            m = st.text_input("Model", value=os.getenv(model_env, default), key=model_env + "_ui")
            if m:
                os.environ[model_env] = m.strip()
    ready = available_backends()
    st.success("Ready: " + ", ".join(ready))


def describe(llm):
    return f"{llm.name} · {getattr(llm, 'model', '')}"


tab_play, tab_arena, tab_stage = st.tabs(["🎯 Playground", "🏟️ Arena", "🎬 Stage demos"])

# ------------------------------------------------------------------ PLAYGROUND
with tab_play:
    left, right = st.columns([1, 1.25])
    with left:
        labels = {f"{a['id']} · {a['technique']}": a for a in ATTACKS}
        choice = st.selectbox("Attack", list(labels))
        attack = copy.deepcopy(labels[choice])
        sc = SCENARIOS[attack["scenario"]]
        st.info(f"**{sc['name']}** — why it can work: {attack['why']}")
        attack["user"] = st.text_area("What the user types", attack["user"], height=110)

        data = attack.get("data", {})
        if "reviews" in data:
            txt = st.text_area("Attacker's review (the app retrieves it)", data["reviews"][-1]["text"], height=130)
            data["reviews"] = d1.REVIEWS[:2] + [{**data["reviews"][-1], "text": txt}]
        if "poison_text" in data:
            default = data["poison_text"] or next(d["text"] for d in d3.load_kb() if d["id"] == "KB-04")
            data["poison_text"] = st.text_area("Attacker's wiki page (KB-04, trust: low)", default, height=150)
        if "note" in data:
            default = data["note"] or d4.DB_SEED["orders"]["O-5003"]["note"]
            data["note"] = st.text_area("Attacker's delivery note on O-5003", default, height=110)
        attack["data"] = data

        backend = st.selectbox("Model", ready, index=0, key="play_backend")
        st.markdown("**Defences**")
        preset = st.radio("Preset", ["vulnerable", "secure", "custom"], horizontal=True, key=f"preset{attack['scenario']}")
        chosen = set()
        for name, desc in sc["defenses"].items():
            default_on = preset == "secure"
            on = st.checkbox(f"`{name}` — {desc}", value=default_on, key=f"{attack['id']}-{name}-{preset}",
                             disabled=preset != "custom")
            if on:
                chosen.add(name)
        if preset == "vulnerable":
            chosen = set()
        elif preset == "secure":
            chosen = set(sc["presets"]["secure"])
        go = st.button("▶ Run attack", type="primary")

    with right:
        if go:
            try:
                llm = get_llm(backend)
                with st.spinner(f"Asking {describe(llm)}…"):
                    r = run_attack(llm, attack, chosen)
                if r["compromised"]:
                    st.error("🚨 COMPROMISED: the attacker's goal was achieved")
                elif r.get("model_fooled"):
                    st.warning(f"🟡 The model was fooled, but a defence caught it ({r.get('blocked_by') or 'gateway'})")
                else:
                    st.success("✅ SAFE")
                st.caption(f"{describe(llm)} · defences: {', '.join(sorted(chosen)) or 'none'}")
                st.chat_message("user").write(attack["user"])
                for t in r["trace"]:
                    st.caption("• " + t)
                st.chat_message("assistant").write(r["output"])
                if r.get("violations"):
                    st.error("Executed outside the user's authority: " + "; ".join(r["violations"]))
                if r.get("ledger"):
                    st.code(json.dumps(r["ledger"], indent=2), language="json")
                with st.expander("🔍 What the model actually received (exact API request)", expanded=True):
                    st.caption("Look for the attacker's text: it sits in the same request as your system prompt.")
                    st.code(json.dumps(getattr(llm, "last_request", None), indent=2, ensure_ascii=False, default=str)[:20000],
                            language="json")
                if getattr(llm, "last_response", None):
                    with st.expander("Raw API response"):
                        st.code(json.dumps(llm.last_response, indent=2, ensure_ascii=False)[:20000], language="json")
            except (RuntimeError, ValueError) as e:
                st.error(f"Backend error: {e}")
        else:
            st.markdown("#### How to use this")
            st.markdown(
                "1. Pick an attack and a model. Start with **vulnerable**.\n"
                "2. Run it 2–3 times: real models don't answer the same way every time.\n"
                "3. Open **What the model actually received** and find the attacker's text.\n"
                "4. Switch to **secure**, then **custom**, and turn layers off one at a time. Which one actually holds?\n"
                "5. Edit the attacker's text and try to beat the secure build. (Hint: the output policy and the gateway don't care how clever the wording is.)")

# ------------------------------------------------------------------ ARENA
with tab_arena:
    st.markdown("Same attacks, different models. Each cell = successful attacks / runs.")
    c1, c2, c3 = st.columns(3)
    with c1:
        backends = st.multiselect("Models", ready, default=[b for b in ready if b != "sim"] or ["sim"])
    with c2:
        ids = st.multiselect("Attacks", [a["id"] for a in ATTACKS], default=["1.3", "1.4", "2.2", "3.2", "4.3", "4.4"])
    with c3:
        trials = st.slider("Trials per attack (real models)", 1, 5, 2)
        builds = st.multiselect("Builds", ["vulnerable", "secure"], default=["vulnerable", "secure"])
    n_runs = sum((1 if b == "sim" else trials) for b in backends) * len(ids) * len(builds)
    st.caption(f"{n_runs} runs. Agent attacks make up to 4 API calls each.")
    if st.button("🏁 Run arena", type="primary", disabled=not (backends and ids and builds)):
        rows, bar = [], st.progress(0.0)
        done = 0
        for b in backends:
            try:
                llm = get_llm(b)
            except (RuntimeError, ValueError) as e:
                st.warning(f"{b}: {e}")
                continue
            for aid in ids:
                at = next(a for a in ATTACKS if a["id"] == aid)
                for build in builds:
                    dset = SCENARIOS[at["scenario"]]["presets"][build]
                    for t in range(1 if b == "sim" else trials):
                        try:
                            r = run_attack(llm, at, dset)
                            rows.append({"model": b, "attack": aid, "build": build, "compromised": r["compromised"],
                                         "fooled_but_caught": bool(r.get("model_fooled")) and not r["compromised"],
                                         "reply": r["output"][:300]})
                        except RuntimeError as e:
                            rows.append({"model": b, "attack": aid, "build": build, "compromised": None,
                                         "fooled_but_caught": None, "reply": f"ERROR: {e}"[:300]})
                        done += 1
                        bar.progress(min(done / max(n_runs, 1), 1.0))
        if rows:
            import pandas as pd
            df = pd.DataFrame(rows)
            ok = df[df["compromised"].notna()].copy()
            ok["compromised"] = ok["compromised"].astype(int)
            pivot = ok.pivot_table(index="attack", columns=["model", "build"], values="compromised",
                                   aggfunc=lambda s: f"{int(s.sum())}/{len(s)}")
            st.subheader("Attack success rate")
            st.dataframe(pivot, width="stretch")
            rate = ok.groupby(["model", "build"])["compromised"].mean().unstack(fill_value=0) * 100
            st.bar_chart(rate, y_label="% of runs compromised")
            with st.expander("All replies"):
                st.dataframe(df, width="stretch")
            st.download_button("Download results (JSON)", df.to_json(orient="records", indent=2), "arena.json")

# ------------------------------------------------------------------ STAGE DEMOS
with tab_stage:
    STAGE = {"1 · Prompt injection": "d1", "2 · Secret leakage": "d2", "3 · RAG poisoning": "d3",
             "4 · Agent tool abuse": "d4", "5 · Multi-turn / PAV defences": "d5"}
    demo = st.radio("Demo", list(STAGE), horizontal=True)
    stage_backend = st.selectbox("Model", ready, key="stage_backend")
    approve = st.checkbox("Demo 4: human approver says YES", value=False)

    def capture(fn, *a, **k):
        buf = io.StringIO()
        with redirect_stdout(buf):
            res = fn(*a, **k)
        return res, buf.getvalue()

    if st.button("▶ Run stage demo"):
        try:
            llm = get_llm(stage_backend)
            key = STAGE[demo]
            if key == "d5":
                out, log = capture(d5.run)
                st.dataframe([{"turn": i + 1, **{k: v for k, v in r.items() if k != "hits"},
                               "signals": ", ".join(r["hits"])} for i, r in enumerate(out["rows"])])
                for name, chk in out["checks"].items():
                    (st.error if chk["flag"] else st.success)(f"{name}: {chk['reason']}")
            else:
                fn = {"d1": lambda: d1.run(llm), "d2": lambda: d2.run(llm), "d3": lambda: d3.run(llm),
                      "d4": lambda: d4.run(llm, approve=approve)}[key]
                res, log = capture(fn)
                for mode in dict.fromkeys(r["mode"] for r in res):
                    st.subheader(f"{mode.upper()} build")
                    for r in [x for x in res if x["mode"] == mode]:
                        with st.container(border=True):
                            st.markdown(f"**{r.get('id', '')} · {r.get('title', 'Scenario')}**")
                            st.chat_message("user").write(r["user"])
                            for t in r.get("trace", []):
                                st.caption(f"• {t}")
                            st.chat_message("assistant").write(r["output"])
                            (st.error("COMPROMISED") if r["compromised"] else st.success("SAFE"))
            with st.expander("Raw terminal output"):
                st.code(log)
        except (RuntimeError, ValueError) as e:
            st.error(f"Backend error: {e}. Switch the model to 'sim' to continue.")
