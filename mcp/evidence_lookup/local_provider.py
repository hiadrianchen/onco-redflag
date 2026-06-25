#!/usr/bin/env python3
"""evidence-lookup 的 local provider：从本地 evidence_pack.yaml 取权威来源。

不联网、不依赖 KnowS。KnowS Key 到手后另写 knows_provider 并在 lookup() 切换。
"""
import os
import yaml

PACK_PATH = os.path.join(os.path.dirname(__file__), "evidence_pack.yaml")


def _load_pack(path=PACK_PATH):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def lookup(source_key, max_results=2, pack=None):
    """按 source key 返回权威来源。返回 {sources, found, provider}。"""
    pack = pack if pack is not None else _load_pack()
    items = pack.get(source_key, []) if source_key else []
    return {"sources": items[:max_results], "found": bool(items), "provider": "local"}


if __name__ == "__main__":
    import json
    print(json.dumps(lookup("idsa_fn_2010"), ensure_ascii=False, indent=2))
