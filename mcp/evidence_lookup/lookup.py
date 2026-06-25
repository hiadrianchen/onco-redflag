#!/usr/bin/env python3
"""evidence-lookup 统一入口（provider 调度）。

默认走 local（确定性、可离线、测试用）。仅当显式 provider="knows"，
或环境同时设置 KNOWS_API_KEY 且 KNOWS_USE=1 时走 KnowS 在线检索；KnowS 失败自动回退 local，
保证"有据可依"不因网络/额度而断。
"""
import os

from local_provider import lookup as _local


def _want_knows(provider):
    if provider:
        return provider == "knows"
    return bool(os.environ.get("KNOWS_API_KEY")) and os.environ.get("KNOWS_USE", "0") == "1"


def lookup(source_key, max_results=2, provider=None):
    if _want_knows(provider):
        from knows_provider import lookup as _knows
        res = _knows(source_key, max_results)
        if res.get("found"):
            return res
        fb = _local(source_key, max_results)
        fb["fallback_from"] = "knows"
        fb["knows_error"] = res.get("error")
        return fb
    return _local(source_key, max_results)


if __name__ == "__main__":
    import json
    print("local:", json.dumps(lookup("idsa_fn_2010"), ensure_ascii=False))
    print("knows:", json.dumps(lookup("idsa_fn_2010", provider="knows"), ensure_ascii=False))
