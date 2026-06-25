#!/usr/bin/env python3
"""v0 表单式 intake：把结构化表单答案校验/规范化为 engine 的 case schema。

为什么先做表单版：不依赖自由文本 LLM（StepFun）即可端到端跑通与回归，且天然规避脏输入。
自由文本版（LLM 抽取）见 SPEC.md，后续替换本模块即可，引擎/Skill 不变。
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "engine"))
from triage import normalize_case, NUM_FIELDS, BOOL_FIELDS, STR_FIELDS  # noqa: E402

ALLOWED = set(NUM_FIELDS) | set(BOOL_FIELDS) | set(STR_FIELDS)


def from_form(form):
    """只保留已知字段并强制类型规范化；未知字段忽略，缺失字段为 None。"""
    case = {k: v for k, v in (form or {}).items() if k in ALLOWED}
    return normalize_case(case)


if __name__ == "__main__":
    import json
    demo = {"treatment_type": "cytotoxic_chemo", "days_since_last_chemo": "7",
            "temp_c": "38.5", "unknown_field": "ignored"}
    print(json.dumps(from_form(demo), ensure_ascii=False, indent=2))
