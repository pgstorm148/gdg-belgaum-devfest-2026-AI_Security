"""Run every demo in order.   python run_all.py [--step] [--backend sim|ollama|gemini]"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "demos"))

from common.llm import get_llm  # noqa: E402
import demo1_prompt_injection as d1  # noqa: E402
import demo2_secret_leakage as d2  # noqa: E402
import demo3_rag_poisoning as d3  # noqa: E402
import demo4_agent_tool_abuse as d4  # noqa: E402
import demo5_pav_defenses as d5  # noqa: E402

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--step", action="store_true")
    p.add_argument("--backend", default=None)
    a = p.parse_args()
    llm = get_llm(a.backend)
    d1.run(llm, step=a.step)
    d2.run(llm, step=a.step)
    d3.run(llm, step=a.step)
    d4.run(llm, step=a.step)
    d5.run(step=a.step)
