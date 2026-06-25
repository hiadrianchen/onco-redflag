#!/usr/bin/env python3
"""端到端编排冒烟：form_intake → engine → evidence_lookup(local) → 渲染卡。
失败退出码非 0（可进 CI）。用法：python3 tests/test_pipeline.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, "skill", "onco-redflag-companion"))
from pipeline import run, DEMOS  # noqa: E402

# 与 pipeline.DEMOS 顺序一致的期望判级
EXPECT = ["RED", "ESCALATE", "ESCALATE", "NO_REDFLAG"]


def main():
    fails = 0
    for (title, form), exp in zip(DEMOS, EXPECT):
        card, dec = run(form)
        level_ok = dec["level"] == exp
        # RED 必须挂上权威来源链接（差异化 + 安全可信度）
        cite_ok = True
        if dec["level"] == "RED":
            cite_ok = "参考来源" in card and "http" in card
        ok = level_ok and cite_ok
        if not ok:
            fails += 1
        print("%s  [%s] level=%s cite=%s" % ("PASS" if ok else "FAIL", title, dec["level"], cite_ok))
    print("\n%d/%d passed" % (len(DEMOS) - fails, len(DEMOS)))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
