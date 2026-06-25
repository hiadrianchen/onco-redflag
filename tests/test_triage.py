#!/usr/bin/env python3
"""危险案例回归 —— 无第三方测试框架依赖，失败时退出码非 0（可直接进 CI）。

用法：  python3 tests/test_triage.py
"""
import os
import sys

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "engine"))
from triage import evaluate, load_rules  # noqa: E402

CASES_PATH = os.path.join(os.path.dirname(__file__), "danger_cases.yaml")


def main():
    rules = load_rules()
    with open(CASES_PATH, "r", encoding="utf-8") as f:
        cases = yaml.safe_load(f)["cases"]

    failures = 0
    for c in cases:
        res = evaluate(c["case"], rules)
        level_ok = res["level"] == c["expect"]
        rule_ok = ("expect_rule" not in c) or (res.get("rule_id") == c["expect_rule"])
        if level_ok and rule_ok:
            print("PASS  [%s] -> %s / %s" % (c["name"], res["level"], res.get("rule_id")))
        else:
            failures += 1
            print("FAIL  [%s] expected %s/%s got %s/%s"
                  % (c["name"], c["expect"], c.get("expect_rule"),
                     res["level"], res.get("rule_id")))

    print("\n%d/%d passed" % (len(cases) - failures, len(cases)))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
