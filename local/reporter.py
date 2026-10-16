#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地上报器 —— 把本机一切服务状态推给服务器指挥中心
用法: python reporter.py [--server URL] [--interval 60]
默认推到 https://wenzetongxun.com/hub/api/report （经本机 Clash 7897）
"""
import argparse
import json
import os
import socket
import subprocess
import time
import urllib.request

DEFAULTS = {
    "8787 免费LLM网关": "http://127.0.0.1:8787/v1/models",
    "8788 账号池": "http://127.0.0.1:8788/health",
    "8789 key池中转站": "http://127.0.0.1:8789/v1/models",
    "8804 热点雷达": "http://127.0.0.1:8804/api/hot",
    "8791 多号管理台": "http://127.0.0.1:8791/",
    "8792 抖音采集API": "http://127.0.0.1:8792/openapi.json",
    "9222 Chrome CDP": "http://127.0.0.1:9222/json/version",
}


def probe(url, timeout=4):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "pojia-reporter/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def gpu_info():
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                           capture_output=True, text=True, timeout=5)
        return (r.stdout or "").strip() or "无"
    except Exception:
        return "无"


def collect():
    services = {name: probe(url) for name, url in DEFAULTS.items()}
    # 热榜条数
    hot_total, hot_plats = 0, []
    try:
        req = urllib.request.Request(DEFAULTS["8804 热点雷达"], headers={"User-Agent": "x"})
        with urllib.request.urlopen(req, timeout=8) as r:
            d = json.load(r)
            hot_total = d.get("total", 0)
            hot_plats = d.get("platforms", [])
    except Exception:
        pass
    # 账号池
    accounts = {"current": "?", "count": 0, "credits": "?"}
    try:
        tok = open(r"C:/Users/qq/AppData/Roaming/WorkDaddy/.api-token", encoding="utf-8").read().strip()
        req = urllib.request.Request("http://127.0.0.1:47832/api/accounts",
                                     headers={"x-workdaddy-token": tok})
        with urllib.request.urlopen(req, timeout=6) as r:
            d = json.load(r)
            cur = d.get("current", {})
            accounts = {"current": (cur.get("nickname") or "?") + " " + (cur.get("phone") or ""),
                        "count": len(d.get("accounts", [])), "credits": "-"}
    except Exception:
        pass
    # 数字人
    venv_py = r"D:\Code\OpenAvatarChat\.venv\Scripts\python.exe"
    torch_ok = False
    if os.path.exists(venv_py):
        try:
            r = subprocess.run([venv_py, "-c", "import torch;print(torch.__version__)"],
                               capture_output=True, text=True, timeout=20)
            torch_ok = r.returncode == 0 and "2." in (r.stdout or "")
        except Exception:
            pass
    models_dir = r"D:\Code\OpenAvatarChat\models"
    weights = "未下载"
    if os.path.isdir(models_dir):
        n = sum(len(f) for _, _, f in os.walk(models_dir))
        weights = "%d 个文件" % n if n else "未下载"
    # 代理池
    proxy_n = 0
    try:
        import sqlite3
        pdb = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)),
                                           ), "proxykit", "proxykit.db")
        if not os.path.exists(pdb):
            pdb = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..",
                               "proxykit", "proxykit.db")
        if os.path.exists(pdb):
            c = sqlite3.connect(pdb)
            proxy_n = c.execute("SELECT COUNT(*) FROM proxies").fetchone()[0]
            c.close()
    except Exception:
        pass
    return {
        "services": services,
        "hot": {"total": hot_total, "platforms": hot_plats},
        "accounts": accounts,
        "avatar": {"gpu": probe_gpu(), "gpu_name": gpu_info(), "torch": torch_ok, "weights": weights},
        "proxy": {"alive": proxy_n},
        "tg": {"ready": os.path.exists(os.path.join(os.path.dirname(__file__), "tg", "pojia.session")),
               "session": "未登录"},
        "host": socket.gethostname(),
        "at": time.time(),
    }


def probe_gpu():
    try:
        r = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True, timeout=5)
        return r.returncode == 0 and "GPU" in (r.stdout or "")
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="https://wenzetongxun.com/hub/api/report")
    ap.add_argument("--token", default="pojia-hub")
    ap.add_argument("--interval", type=int, default=60)
    ap.add_argument("--proxy", default="http://127.0.0.1:7897")
    args = ap.parse_args()
    print("[reporter] -> %s every %ds" % (args.server, args.interval), flush=True)
    while True:
        try:
            data = collect()
            data["token"] = args.token
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({"http": args.proxy, "https": args.proxy}))
            req = urllib.request.Request(args.server, data=body,
                                         headers={"Content-Type": "application/json",
                                                  "User-Agent": "pojia-reporter/1.0"})
            with opener.open(req, timeout=20) as r:
                print("[reporter] %s %s" % (r.status, time.strftime("%H:%M:%S")), flush=True)
        except Exception as e:
            print("[reporter] ERR %s" % str(e)[:120], flush=True)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
