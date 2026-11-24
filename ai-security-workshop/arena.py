"""
ARENA — run the same attacks against GPT, Gemini, Claude (and the simulator) and measure
the attack success rate, with and without defences.

Real models are probabilistic: the same attack can fail twice and succeed on the third
try. So we run each attack several times (--trials) and report k/n, the way
security research reports Attack Success Rate (ASR).

Examples
    python arena.py                                   # every configured backend, every attack
    python arena.py --backends gpt,gemini,claude --trials 3
    python arena.py --attacks 1.3,1.4 --backends claude --show-prompt
    python arena.py --attacks 4 --mode secure --without ownership     # ablation: remove one layer
    python arena.py --list                            # show attacks and defences

Keys come from environment variables or a .env file in this folder:
    OPENAI_API_KEY · GEMINI_API_KEY · ANTHROPIC_API_KEY
Reports are written to reports/arena-<timestamp>.md and .json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from attack_lib.attacks import ATTACKS, SCENARIOS, run_attack  # noqa: E402
from common import ui  # noqa: E402
from common.cli import show_request  # noqa: E402
from common.llm import BACKEND_ALIASES, available_backends, get_llm  # noqa: E402


def select_attacks(spec: str | None) -> list[dict]:
    if not spec or spec == "all":
        return ATTACKS
    out = []
    for part in spec.split(","):
        part = part.strip()
        if part.isdigit():
            out += [a for a in ATTACKS if a["scenario"] == int(part)]
        else:
            out += [a for a in ATTACKS if a["id"] == part]
    if not out:
        raise SystemExit(f"No attacks match '{spec}'. Run with --list.")
    return out


def defence_sets(mode: str, attack: dict, without: set[str], with_: set[str] | None) -> list[tuple[str, set]]:
    sc = SCENARIOS[attack["scenario"]]
    if with_ is not None:
        return [("custom", with_ & set(sc["defenses"]))]
    sets = []
    if mode in ("vulnerable", "both"):
        sets.append(("vulnerable", set(sc["presets"]["vulnerable"])))
    if mode in ("secure", "both"):
        label = "secure" if not without else "secure-" + "-".join(sorted(without))
        sets.append((label, set(sc["presets"]["secure"]) - without))
    return sets


def print_list():
    ui.banner("ARENA · attack library")
    for sid, sc in SCENARIOS.items():
        ui.section(f"Scenario {sid}: {sc['name']}")
        for a in [x for x in ATTACKS if x["scenario"] == sid]:
            print(f"  {ui.c(a['id'], 'bold')}  {a['technique']}")
            print(ui.c(f"       why: {a['why']}", "grey"))
        print(ui.c("  defences: " + ", ".join(sc["defenses"]), "cyan"))


def fmt_rate(k: int, n: int) -> str:
    return f"{k}/{n}" if n else "–"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--backends", default=None, help="comma list: sim,gpt,gemini,claude,ollama (default: all configured)")
    p.add_argument("--attacks", default="all", help="attack ids (1.3,2.2) or scenario numbers (1,4) or all")
    p.add_argument("--trials", type=int, default=None, help="runs per attack per build (default 3; sim always 1)")
    p.add_argument("--mode", choices=["vulnerable", "secure", "both"], default="both")
    p.add_argument("--without", default="", help="ablation: switch these defences off in the secure build")
    p.add_argument("--with", dest="with_", default=None, help="run ONLY with these defences enabled")
    p.add_argument("--show-prompt", action="store_true", help="print the exact request sent (first trial of each attack)")
    p.add_argument("--quiet", action="store_true", help="don't print each model reply")
    p.add_argument("--yes", action="store_true", help="skip the cost confirmation")
    p.add_argument("--list", action="store_true", help="list attacks and defences, then exit")
    p.add_argument("--out", default=os.path.join(ROOT, "reports"))
    a = p.parse_args()

    if a.list:
        print_list()
        return

    names = [BACKEND_ALIASES.get(b.strip().lower(), b.strip().lower()) for b in a.backends.split(",")] if a.backends else available_backends()
    attacks = select_attacks(a.attacks)
    without = {x.strip() for x in a.without.split(",") if x.strip()}
    with_ = {x.strip() for x in a.with_.split(",") if x.strip()} if a.with_ is not None else None

    llms = []
    for n in names:
        try:
            llm = get_llm(n)
            llms.append(llm)
        except (RuntimeError, ValueError) as e:
            print(ui.c(f"  skipping {n}: {e}", "yellow"))
    if not llms:
        raise SystemExit("No usable backends.")

    def trials_for(llm):
        return 1 if llm.name == "sim" else (a.trials or 3)

    calls = sum(trials_for(l) * len(defence_sets(a.mode, at, without, with_)) for l in llms for at in attacks)
    real = sum(trials_for(l) * len(defence_sets(a.mode, at, without, with_)) for l in llms if l.name != "sim" for at in attacks)
    ui.banner("ARENA · same attacks, different models",
              f"backends = {', '.join(f'{l.name}:{l.model}' for l in llms)} · {len(attacks)} attacks · {calls} runs")
    if real and not a.yes and sys.stdin.isatty():
        ans = input(ui.c(f"  {real} runs hit paid/free-tier APIs (agent runs make up to 4 calls each). Continue? [y/N] ", "yellow"))
        if ans.strip().lower() not in ("y", "yes"):
            return

    rows = []
    for at in attacks:
        ui.section(f"{at['id']} · {SCENARIOS[at['scenario']]['name']} · {at['technique']}")
        print(ui.c(f"  why it can work: {at['why']}", "grey"))
        for llm in llms:
            for label, dset in defence_sets(a.mode, at, without, with_):
                for t in range(trials_for(llm)):
                    rec = {"backend": llm.name, "model": llm.model, "attack": at["id"], "scenario": at["scenario"],
                           "technique": at["technique"], "build": label, "defenses": sorted(dset), "trial": t + 1}
                    started = time.time()
                    try:
                        r = run_attack(llm, at, dset)
                        rec.update(compromised=r["compromised"], model_fooled=bool(r.get("model_fooled")),
                                   blocked_by=r.get("blocked_by"), output=r["output"], trace=r["trace"],
                                   violations=r.get("violations", []), error=None)
                    except RuntimeError as e:
                        rec.update(compromised=None, model_fooled=None, blocked_by=None, output="", trace=[],
                                   violations=[], error=str(e))
                    rec["seconds"] = round(time.time() - started, 1)
                    rows.append(rec)
                    if rec["error"]:
                        tag = ui.c(" ERROR ", "yellow")
                    elif rec["compromised"]:
                        tag = ui.c(" COMPROMISED ", "red")
                    elif rec["model_fooled"]:
                        tag = ui.c(" FOOLED→CAUGHT ", "yellow")
                    else:
                        tag = ui.c(" SAFE ", "green")
                    print(f"  {llm.name:<7}{label:<22}#{t + 1}  {tag}"
                          + (ui.c(f"  {rec['error'][:120]}", "yellow") if rec["error"] else ""))
                    if not a.quiet and not rec["error"]:
                        print(ui.c("      ↳ " + rec["output"].replace("\n", " ")[:160], "grey"))
                    if a.show_prompt and t == 0:
                        show_request(llm)

    # ---------------------------------------------------------------- summary
    builds = list(dict.fromkeys(r["build"] for r in rows))
    ui.banner("RESULTS · attack success rate (k successes / n runs)")
    header = f"  {'attack':<8}" + "".join(f"{l.name + ' ' + b:<26}" for l in llms for b in builds)
    print(ui.c(header, "bold"))
    table = []
    for at in attacks:
        line, cells = f"  {at['id']:<8}", []
        for l in llms:
            for b in builds:
                rs = [r for r in rows if r["attack"] == at["id"] and r["backend"] == l.name and r["build"] == b and r["error"] is None]
                k = sum(1 for r in rs if r["compromised"])
                fooled = sum(1 for r in rs if r["model_fooled"] and not r["compromised"])
                cell = fmt_rate(k, len(rs)) + (f" (+{fooled} caught)" if fooled else "")
                cells.append(cell)
                colour = "red" if k else ("yellow" if fooled else "green")
                line += ui.c(f"{cell:<26}", colour)
        table.append((at, cells))
        print(line)
    print(ui.c("\n  k/n = attacks that reached the user or executed · (+m caught) = model was fooled but a defence stopped it", "grey"))

    # ---------------------------------------------------------------- reports
    os.makedirs(a.out, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    jpath, mpath = os.path.join(a.out, f"arena-{stamp}.json"), os.path.join(a.out, f"arena-{stamp}.md")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    with open(mpath, "w", encoding="utf-8") as f:
        f.write(f"# Arena report · {stamp}\n\n")
        f.write("Models: " + ", ".join(f"`{l.name}` ({l.model})" for l in llms) + "\n\n")
        f.write("Cells show attack successes / runs. *(+m caught)* = the model was fooled but a defence stopped it.\n\n")
        cols = [f"{l.name} · {b}" for l in llms for b in builds]
        f.write("| Attack | Technique | " + " | ".join(cols) + " |\n")
        f.write("|---|---|" + "---|" * len(cols) + "\n")
        for at, cells in table:
            f.write(f"| {at['id']} | {at['technique']} | " + " | ".join(cells) + " |\n")
        f.write("\n## Transcripts of successful attacks\n")
        for r in rows:
            if r["compromised"]:
                f.write(f"\n### {r['attack']} · {r['backend']} ({r['model']}) · {r['build']} · trial {r['trial']}\n\n")
                f.write("```text\n" + r["output"][:1500] + "\n```\n")
                if r["violations"]:
                    f.write(f"Executed: {r['violations']}\n")
        errs = [r for r in rows if r["error"]]
        if errs:
            f.write("\n## Errors\n\n" + "\n".join(f"- {r['backend']} {r['attack']}: {r['error'][:200]}" for r in errs) + "\n")
    print(ui.c(f"\n  report: {mpath}\n  raw:    {jpath}", "cyan"))


if __name__ == "__main__":
    main()
