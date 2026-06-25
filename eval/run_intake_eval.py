#!/usr/bin/env python3
"""LIVE 评测自由文本 intake（真实 LLM，默认 StepFun）。无 STEPFUN_API_KEY 则跳过（退 0）。

跑法：set -a; . ./.env; set +a; python3 eval/run_intake_eval.py
关注：不漏判（RED→RED）。漏判一条即视为不达标。
"""
import os
import sys

import yaml

_root = os.path.join(os.path.dirname(__file__), os.pardir)
sys.path.insert(0, os.path.join(_root, "engine"))
sys.path.insert(0, os.path.join(_root, "mcp", "redflag_intake"))
from llm_intake import extract           # noqa: E402
from triage import evaluate              # noqa: E402

CASES = os.path.join(os.path.dirname(__file__), "intake_cases.yaml")


def main():
    if not os.environ.get("STEPFUN_API_KEY"):
        print("SKIP: 未设置 STEPFUN_API_KEY（live intake 评测跳过）")
        sys.exit(0)
    with open(CASES, encoding="utf-8") as f:
        cases = yaml.safe_load(f)["cases"]
    miss_red = 0
    other = 0
    for c in cases:
        case = extract(c["text"])
        got = evaluate(case)["level"]
        ok = got == c["expect"]
        flag = "" if ok else ("  ⚠️漏判RED" if c["expect"] == "RED" else "  (不一致)")
        if not ok:
            if c["expect"] == "RED":
                miss_red += 1
            else:
                other += 1
        print("%s [%s] expect=%s got=%s%s" % ("PASS" if ok else "FAIL", c["text"][:18], c["expect"], got, flag))
    print("\n漏判RED=%d, 其它不一致=%d" % (miss_red, other))
    sys.exit(1 if miss_red else 0)  # 漏判 RED 视为不达标；其它不一致仅告警


if __name__ == "__main__":
    main()
