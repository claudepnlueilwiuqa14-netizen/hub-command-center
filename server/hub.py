#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
指挥中心 hub —— 王承泽的一切服务，一个域名全呈现
=================================================
服务器端：http://127.0.0.1:8310  （nginx /hub/ 反代到域名）

数据来源两条：
  1. 服务器自检：nginx / classroom / ai-group / selfnode / 网关 / 磁盘 / 内存
  2. 本地上报：本地机器上的 reporter.py 每 60 秒 POST /api/report
     （8787/8788/8789 网关、8804 热榜、9222 Chrome、账号池、数字人、TG、VPN）

页面：/            指挥中心大屏（自动刷新）
      /api/state   全部状态 JSON
      /api/report  接收本地上报（POST）
      /health      健康检查

零依赖：只用 Python 标准库。
"""
import json
import os
import subprocess
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.getenv("HUB_PORT", "8310"))
TOKEN = os.getenv("HUB_TOKEN", "pojia-hub")
START = time.time()

LOCK = threading.Lock()
STATE = {
    "server": {},
    "local": {},
    "local_at": 0,
    "events": [],
}


def sh(cmd, timeout=8):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return (r.stdout or "").strip()
    except Exception as e:
        return "ERR:" + str(e)[:60]


def http_json(url, timeout=5):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "pojia-hub/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except Exception as e:
        return {"_error": str(e)[:80]}


def probe_server():
    st = {}
    # 系统
    st["uptime"] = sh("uptime -p")
    st["load"] = sh("cat /proc/loadavg | cut -d' ' -f1-3")
    st["disk"] = sh("df -h / | tail -1 | awk '{print $3\"/\"$2\" (\"$5\" used)\"}'")
    st["mem"] = sh("free -m | awk '/Mem:/{print $3\"/\"$2\" MB\"}'")
    # 服务
    for svc in ["nginx", "classroom", "selfnode", "selfnode-sub", "ai-group", "freellm"]:
        st["svc_" + svc] = sh("systemctl is-active %s 2>/dev/null || echo inactive" % svc)
    # 端口
    ports = {}
    for p in [80, 443, 8443, 8444, 8300, 8765, 8766, 8789, 8310]:
        ports[str(p)] = "up" if sh("ss -tln 2>/dev/null | grep -q ':%s '" % p) == "" and sh("ss -tln 2>/dev/null | grep ':%s '" % p) else "down"
    st["ports"] = ports
    # 课堂站
    h = http_json("http://127.0.0.1:8765/api/health")
    st["classroom_health"] = h.get("ok", False) if isinstance(h, dict) else False
    # 群聊
    st["ai_group_members"] = "?"
    try:
        with urllib.request.urlopen("http://127.0.0.1:8300/members", timeout=5) as r:
            m = json.load(r)
            st["ai_group_members"] = len(m) if isinstance(m, list) else "?"
    except Exception:
        pass
    # 网关
    g = http_json("http://127.0.0.1:8789/v1/models", timeout=6)
    if isinstance(g, dict) and "data" in g:
        st["llm_models"] = len(g["data"])
        st["llm_ok"] = True
    else:
        st["llm_models"] = 0
        st["llm_ok"] = False
    st["_at"] = time.time()
    return st


def server_loop():
    while True:
        try:
            st = probe_server()
            with LOCK:
                STATE["server"] = st
        except Exception:
            pass
        time.sleep(30)


PAGE = """<!doctype html>
<html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>王承泽 · 指挥中心</title>
<style>
:root{--bg:#070a14;--card:rgba(10,17,25,.72);--line:rgba(120,160,220,.18);--txt:#e8f0f2;--dim:#8ba3ab;--ok:#5fe0b0;--bad:#ff8f8f;--warn:#ffca6b;--acc:#70ead1}
*{box-sizing:border-box}
body{margin:0;font:15px/1.7 "Microsoft YaHei",system-ui,sans-serif;background:var(--bg);color:var(--txt);min-height:100vh;
background-image:radial-gradient(ellipse at 20% 10%,rgba(112,234,209,.07),transparent 50%),radial-gradient(ellipse at 80% 90%,rgba(74,168,255,.07),transparent 50%)}
.wrap{max-width:1200px;margin:0 auto;padding:26px 18px 60px}
h1{font-size:26px;margin:0 0 4px;font-weight:700;letter-spacing:.5px}
h1 span{color:var(--acc)}
.sub{color:var(--dim);font-size:13px;margin-bottom:22px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px 18px;backdrop-filter:blur(10px)}
.card h2{font-size:15px;margin:0 0 10px;color:var(--acc);font-weight:600;display:flex;justify-content:space-between}
.row{display:flex;justify-content:space-between;padding:5px 0;font-size:13.5px;border-bottom:1px dashed rgba(120,160,220,.08)}
.row:last-child{border:0}
.row b{font-weight:600}
.ok{color:var(--ok)}.bad{color:var(--bad)}.warn{color:var(--warn)}.dim{color:var(--dim)}
.big{font-size:30px;font-weight:700;margin:2px 0}
a{color:var(--acc);text-decoration:none}
a:hover{text-decoration:underline}
.pill{display:inline-block;padding:2px 10px;border-radius:99px;font-size:12px;background:rgba(112,234,209,.14);color:var(--acc);margin-right:6px}
.evt{font-size:12.5px;color:var(--dim);padding:3px 0;border-bottom:1px dashed rgba(120,160,220,.06)}
.foot{margin-top:26px;color:var(--dim);font-size:12px;text-align:center}
</style></head><body><div class="wrap">
<h1>王承泽 · <span>指挥中心</span></h1>
<div class="sub">一切通过域名彻底呈现 · 每 10 秒自刷新 · <span id="clock"></span></div>
<div class="grid" id="grid"></div>
<div class="foot">wenzetongxun.com/hub · 泽泽破甲体系 · 2026-10-16</div>
</div>
<script>
function pill(v){ if(v===true||v==='active'||v==='up') return '<b class="ok">'+v+'</b>'; if(v===false||v==='inactive'||v==='down') return '<b class="bad">'+v+'</b>'; return '<b>'+v+'</b>'; }
function row(k,v){ return '<div class="row"><span class="dim">'+k+'</span><span>'+v+'</span></div>'; }
function ago(t){ if(!t) return '从未'; var s=(Date.now()/1000)-t; if(s<60) return Math.floor(s)+'秒前'; if(s<3600) return Math.floor(s/60)+'分钟前'; return Math.floor(s/3600)+'小时前'; }
function render(d){
  var g=document.getElementById('grid'); var h='';
  // 总览
  var s=d.server||{}, l=d.local||{};
  h+='<div class="card"><h2>总览 <span class="dim">'+ago(s._at)+'</span></h2>';
  h+=row('课堂站', pill(s.classroom_health===true?'active':'bad'));
  h+=row('多AI群聊', pill(s.svc_ai_group)+' · '+(s.ai_group_members||'?')+' 位成员');
  h+=row('LLM网关', pill(s.llm_ok)+' · '+(s.llm_models||0)+' 模型');
  h+=row('代理节点', pill(s.svc_selfnode));
  h+=row('服务器负载', '<b>'+(s.load||'?')+'</b>');
  h+=row('磁盘', (s.disk||'?'));
  h+=row('内存', (s.mem||'?'));
  h+='</div>';
  // 本机服务
  h+='<div class="card"><h2>本机服务 <span class="dim">'+ago(d.local_at)+'</span></h2>';
  var ls=l.services||{};
  for(var k in ls){ h+=row(k, pill(ls[k])); }
  if(!Object.keys(ls).length) h+='<div class="dim">上报器未连接</div>';
  h+='</div>';
  // 账号池
  h+='<div class="card"><h2>账号池（136 等）</h2>';
  var acc=l.accounts||{};
  h+=row('当前账号', '<b>'+(acc.current||'?')+'</b>');
  h+=row('账号数', acc.count||0);
  h+=row('积分余额', acc.credits||'?');
  h+='</div>';
  // 热榜
  h+='<div class="card"><h2>全平台热榜</h2>';
  var hot=l.hot||{};
  h+=row('条数', '<b class="ok">'+(hot.total||0)+'</b>');
  h+=row('平台', (hot.platforms||[]).join(' / ')||'-');
  h+='</div>';
  // 数字人
  h+='<div class="card"><h2>数字人</h2>';
  var av=l.avatar||{};
  h+=row('GPU', pill(av.gpu)+' '+(av.gpu_name||''));
  h+=row('torch', pill(av.torch));
  h+=row('模型权重', av.weights||'未下载');
  h+='</div>';
  // Telegram
  h+='<div class="card"><h2>Telegram</h2>';
  var tg=l.tg||{};
  h+=row('telethon', pill(tg.ready));
  h+=row('会话', tg.session||'未登录');
  h+='</div>';
  // 入口
  h+='<div class="card"><h2>域名入口</h2>';
  h+=row('<a href="/ai/" target="_blank">多AI群聊 /ai/</a>','<span class="pill">在线</span>');
  h+=row('<a href="/" target="_blank">课堂站 /</a>','<span class="pill">在线</span>');
  h+=row('<a href="/hub/" target="_blank">指挥中心 /hub/</a>','<span class="pill">在线</span>');
  h+='</div>';
  // 事件
  h+='<div class="card"><h2>最近事件</h2>';
  (d.events||[]).slice(-8).reverse().forEach(function(e){ h+='<div class="evt">'+new Date(e.t*1000).toLocaleTimeString()+' '+e.msg+'</div>'; });
  h+='</div>';
  g.innerHTML=h;
  document.getElementById('clock').textContent=new Date().toLocaleString('zh-CN');
}
fetch('/hub/api/state').then(r=>r.json()).then(render).catch(e=>{
  document.getElementById('grid').innerHTML='<div class="card">加载失败: '+e+'</div>';
});
setInterval(()=>{fetch('/hub/api/state').then(r=>r.json()).then(render);},10000);
</script></body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")
        if path in ("", "/hub", "/hub/"):
            self._send(200, PAGE, "text/html")
        elif path in ("/api/state", "/hub/api/state"):
            with LOCK:
                out = {"server": STATE["server"], "local": STATE["local"],
                       "local_at": STATE["local_at"], "events": STATE["events"][-20:]}
            self._send(200, json.dumps(out, ensure_ascii=False))
        elif path in ("/health", "/hub/health"):
            self._send(200, json.dumps({"ok": True, "uptime": int(time.time() - START)}))
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        path = self.path.split("?")[0].rstrip("/")
        if path in ("/api/report", "/hub/api/report"):
            try:
                n = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(n) or b"{}")
                if body.get("token") != TOKEN:
                    self._send(401, json.dumps({"ok": False, "error": "bad token"}))
                    return
                body.pop("token", None)
                with LOCK:
                    STATE["local"] = body
                    STATE["local_at"] = time.time()
                    STATE["events"].append({"t": time.time(), "msg": "本地上报: " + ",".join(list((body.get("services") or {}).keys())[:6])})
                    STATE["events"] = STATE["events"][-50:]
                self._send(200, json.dumps({"ok": True}))
            except Exception as e:
                self._send(400, json.dumps({"ok": False, "error": str(e)[:100]}))
        else:
            self._send(404, json.dumps({"error": "not found"}))


def main():
    threading.Thread(target=server_loop, daemon=True).start()
    print("[hub] listening 127.0.0.1:%d" % PORT, flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
