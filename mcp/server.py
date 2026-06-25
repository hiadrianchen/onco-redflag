#!/usr/bin/env python3
"""OncoRedFlag MCP server（stdio / JSON-RPC 2.0，零第三方依赖）。

把确定性红旗引擎 + 循证检索包成标准 MCP 工具，供任意 MCP 客户端挂载。
判级永远由确定性引擎决定；本 server 不引入任何会改判级的逻辑。

工具：
  - redflag_check    : 结构化症状字段 → 红旗判定 + 就医沟通卡 + 循证来源（端到端）
  - evidence_lookup  : source_key / topic → 权威循证来源（provider：local 默认 / knows）

运行：python3 mcp/server.py   （读 stdin 的 JSON-RPC 行，写 stdout）
循证用 KnowS 时：在环境设 KNOWS_API_KEY 且 KNOWS_USE=1（见 .env.example）。
"""
import os
import sys
import json

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for p in (
    os.path.join(_ROOT, "engine"),
    os.path.join(_HERE, "redflag_intake"),
    os.path.join(_HERE, "evidence_lookup"),
    os.path.join(_ROOT, "skill", "onco-redflag-companion"),
):
    if p not in sys.path:
        sys.path.insert(0, p)

from pipeline import run as redflag_run        # noqa: E402  (intake→engine→evidence→card)
from lookup import lookup as evidence_lookup    # noqa: E402

SERVER_INFO = {"name": "onco-redflag", "version": "0.1.0"}
DEFAULT_PROTOCOL = "2024-11-05"

_CASE_PROPS = {
    "treatment_type": {"type": ["string", "null"],
                       "enum": ["cytotoxic_chemo", "immunotherapy", "targeted", "radiation", "other", None],
                       "description": "治疗类型；本工具仅覆盖 cytotoxic_chemo"},
    "days_since_last_chemo": {"type": ["integer", "null"], "description": "末次化疗至今天数（覆盖 0–21）"},
    "temp_c": {"type": ["number", "null"], "description": "体温℃（口温为准）"},
    "temp_route": {"type": ["string", "null"], "enum": ["oral", "axillary", "ear", "forehead", None]},
    "rigors": {"type": ["boolean", "null"], "description": "寒战/僵直"},
    "dyspnea": {"type": ["boolean", "null"]},
    "chest_pain": {"type": ["boolean", "null"]},
    "cyanosis": {"type": ["boolean", "null"]},
    "altered_consciousness": {"type": ["boolean", "null"]},
    "active_bleeding": {"type": ["boolean", "null"]},
    "hematemesis_melena": {"type": ["boolean", "null"]},
    "vomiting_unable_intake_hours": {"type": ["integer", "null"]},
    "diarrhea_count_per_day": {"type": ["integer", "null"]},
    "diarrhea_bloody": {"type": ["boolean", "null"]},
    "has_cvc": {"type": ["boolean", "null"]},
    "cvc_site_inflamed": {"type": ["boolean", "null"]},
    "age": {"type": ["integer", "null"]},
    "patient_group": {"type": ["string", "null"],
                      "enum": ["solid_tumor", "hematologic", "transplant", "pregnant", None]},
}

TOOLS = [
    {
        "name": "redflag_check",
        "description": "化疗期红旗信号核对：输入结构化症状字段，返回'是否需立即就医'判定 + 就医沟通卡 + 循证来源。不诊断、不替代急诊、缺信息一律升级就医。",
        "inputSchema": {"type": "object", "properties": _CASE_PROPS},
    },
    {
        "name": "evidence_lookup",
        "description": "按 source_key 或 topic 检索权威循证来源（指南/患教）。provider=local（默认）或 knows（需 KNOWS_API_KEY）。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_key": {"type": "string", "description": "如 idsa_fn_2010 / nci_infection / acs_when_to_call"},
                "provider": {"type": "string", "enum": ["local", "knows"]},
                "max_results": {"type": "integer"},
            },
            "required": ["source_key"],
        },
    },
]


def _call_tool(name, args):
    if name == "redflag_check":
        card, decision = redflag_run(args or {})
        return card + "\n\n[level] %s  [rule] %s" % (decision.get("level"), decision.get("rule_id"))
    if name == "evidence_lookup":
        res = evidence_lookup(args.get("source_key"), max_results=args.get("max_results", 2),
                              provider=args.get("provider"))
        return json.dumps(res, ensure_ascii=False, indent=2)
    raise ValueError("unknown tool: %s" % name)


def _write(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _result(rid, result):
    _write({"jsonrpc": "2.0", "id": rid, "result": result})


def _error(rid, code, message):
    _write({"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": message}})


def handle(req):
    method = req.get("method")
    rid = req.get("id")
    if method == "initialize":
        proto = (req.get("params") or {}).get("protocolVersion", DEFAULT_PROTOCOL)
        _result(rid, {"protocolVersion": proto, "capabilities": {"tools": {}}, "serverInfo": SERVER_INFO})
    elif method == "notifications/initialized":
        pass  # notification, no response
    elif method == "ping":
        _result(rid, {})
    elif method == "tools/list":
        _result(rid, {"tools": TOOLS})
    elif method == "tools/call":
        params = req.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            text = _call_tool(name, args)
            _result(rid, {"content": [{"type": "text", "text": text}], "isError": False})
        except Exception as e:  # tool error → MCP isError result (not protocol error)
            _result(rid, {"content": [{"type": "text", "text": "tool error: %s" % e}], "isError": True})
    else:
        if rid is not None:
            _error(rid, -32601, "method not found: %s" % method)


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except ValueError:
            continue
        handle(req)


if __name__ == "__main__":
    main()
