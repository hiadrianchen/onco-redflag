#!/usr/bin/env python3
"""MCP server 冒烟：起子进程，做 initialize → tools/list → tools/call 握手，校验响应。
零依赖、离线（evidence 走默认 local）。失败退出码非 0。
"""
import os
import sys
import json
import subprocess

SERVER = os.path.join(os.path.dirname(__file__), os.pardir, "mcp", "server.py")


def _rpc(proc, obj, expect_response=True):
    proc.stdin.write(json.dumps(obj) + "\n")
    proc.stdin.flush()
    if not expect_response:
        return None
    line = proc.stdout.readline()
    return json.loads(line)


def main():
    env = dict(os.environ)
    env.pop("KNOWS_USE", None)  # force local provider, hermetic
    proc = subprocess.Popen([sys.executable, SERVER], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, text=True, env=env)
    fails = 0
    try:
        # initialize
        r = _rpc(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                        "params": {"protocolVersion": "2024-11-05"}})
        ok = r.get("result", {}).get("serverInfo", {}).get("name") == "onco-redflag"
        print("PASS initialize" if ok else "FAIL initialize: %s" % r); fails += 0 if ok else 1
        _rpc(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"}, expect_response=False)

        # tools/list
        r = _rpc(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = {t["name"] for t in r.get("result", {}).get("tools", [])}
        ok = {"redflag_check", "evidence_lookup"} <= names
        print("PASS tools/list (%s)" % sorted(names) if ok else "FAIL tools/list: %s" % r); fails += 0 if ok else 1

        # tools/call redflag_check — fever case must be RED with citation
        r = _rpc(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                        "params": {"name": "redflag_check",
                                   "arguments": {"treatment_type": "cytotoxic_chemo",
                                                 "days_since_last_chemo": 7, "temp_c": 38.5}}})
        text = r.get("result", {}).get("content", [{}])[0].get("text", "")
        ok = ("[level] RED" in text) and ("参考来源" in text)
        print("PASS redflag_check RED+cite" if ok else "FAIL redflag_check: %s" % text[:200]); fails += 0 if ok else 1

        # tools/call evidence_lookup
        r = _rpc(proc, {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                        "params": {"name": "evidence_lookup", "arguments": {"source_key": "idsa_fn_2010"}}})
        text = r.get("result", {}).get("content", [{}])[0].get("text", "")
        ok = "sources" in text
        print("PASS evidence_lookup" if ok else "FAIL evidence_lookup: %s" % text[:200]); fails += 0 if ok else 1
    finally:
        proc.stdin.close()
        proc.terminate()

    print("\n%s" % ("ALL PASS" if fails == 0 else "%d FAILED" % fails))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
