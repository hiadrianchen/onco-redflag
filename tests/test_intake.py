#!/usr/bin/env python3
"""自由文本 intake 质量门（hermetic，用 mock LLM，不联网）。

重点不是"LLM 多准"（那要 live eval，见 eval/run_intake_eval.py），而是验证 intake 的**安全管道**：
脏输出/缺失→安全升级不崩溃；代码围栏可解析；LLM 漏抽禁忌信号时关键词兜底仍能升级。
失败退出码非 0。
"""
import os
import sys

_root = os.path.join(os.path.dirname(__file__), os.pardir)
sys.path.insert(0, os.path.join(_root, "engine"))
sys.path.insert(0, os.path.join(_root, "mcp", "redflag_intake"))
from llm_intake import extract           # noqa: E402
from triage import evaluate              # noqa: E402


def mock(output):
    return lambda prompt: output


# (name, text, mock_llm_output, expected_engine_level)
CASES = [
    ("发烧寒战→RED", "化疗第7天发烧38.5有点发抖",
     '{"treatment_type":"cytotoxic_chemo","days_since_last_chemo":7,"temp_c":38.5,"rigors":true}', "RED"),
    ("腹泻8次→RED", "化疗一周多腹泻8次",
     '{"treatment_type":"cytotoxic_chemo","days_since_last_chemo":8,"diarrhea_count_per_day":8}', "RED"),
    ("代码围栏JSON→RED", "化疗5天高烧39",
     '```json\n{"treatment_type":"cytotoxic_chemo","days_since_last_chemo":5,"temp_c":39}\n```', "RED"),
    ("脏输出非JSON→ESCALATE", "我不太舒服", "Sorry, I cannot output JSON here.", "ESCALATE"),
    ("部分抽取缺天数→ESCALATE", "发烧38.5", '{"temp_c":"38.5"}', "ESCALATE"),
    ("LLM漏抽儿童·关键词兜底→ESCALATE", "我家孩子化疗后发烧38.5",
     '{"treatment_type":"cytotoxic_chemo","days_since_last_chemo":6,"temp_c":38.5}', "ESCALATE"),
    ("LLM漏抽血液瘤·兜底→ESCALATE", "白血病化疗后发烧38.5",
     '{"treatment_type":"cytotoxic_chemo","days_since_last_chemo":5,"temp_c":38.5}', "ESCALATE"),
    ("免疫治疗·兜底→ESCALATE", "免疫治疗后腹泻很多次",
     '{"days_since_last_chemo":5,"diarrhea_count_per_day":8}', "ESCALATE"),
]


def main():
    fails = 0
    for name, text, out, expect in CASES:
        case = extract(text, llm=mock(out))
        dec = evaluate(case)
        ok = dec["level"] == expect
        print(("PASS " if ok else "FAIL ") + "%s -> %s/%s" % (name, dec["level"], dec.get("rule_id")))
        fails += 0 if ok else 1
    print("\n%d/%d passed" % (len(CASES) - fails, len(CASES)))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
