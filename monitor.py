import os
import time
import json
import requests
from datetime import datetime

BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
CHAT_ID = os.getenv("TG_CHAT_ID")

TARGET_NODES = [
    "ru1.node.check-host.net",
    "ru2.node.check-host.net",
    "de1.node.check-host.net",
    "us1.node.check-host.net",
    "sg1.node.check-host.net"
]

def send_telegram(text: str):
    if not BOT_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"TG Error: {e}")

def check_target(site_url: str):
    headers = {"Accept": "application/json"}
    init_url = f"https://check-host.net/check-http?host={site_url}&max_nodes=6"
    for node in TARGET_NODES:
        init_url += f"&node={node}"
    
    try:
        res = requests.get(init_url, headers=headers, timeout=15).json()
        req_id = res.get("request_id")
        if not req_id:
            return {"status": "ERROR", "details": {}, "link": ""}
        
        time.sleep(20)
        
        result_url = f"https://check-host.net/check-result/{req_id}"
        data = requests.get(result_url, headers=headers, timeout=15).json()
        
        node_results = {}
        success_count = 0
        total_nodes = 0
        
        for node, val in data.items():
            if val and len(val) > 0 and val[0]:
                total_nodes += 1
                is_ok = val[0][0] == 1
                if is_ok:
                    success_count += 1
                node_results[node] = "OK" if is_ok else "DEAD"
        
        site_is_up = success_count > 0 and (success_count / max(total_nodes, 1)) >= 0.5
        return {
            "status": "UP" if site_is_up else "DOWN",
            "nodes": node_results,
            "report_link": f"https://check-host.net/check-report/{req_id}"
        }
    except Exception as exc:
        return {"status": "DOWN", "error": str(exc), "nodes": {}}

def main():
    with open("sites.json", "r", encoding="utf-8") as f:
        sites = json.load(f)

    history = {}
    if os.path.exists("history.json"):
        try:
            with open("history.json", "r", encoding="utf-8") as f:
                history = json.load(f)
        except Exception:
            history = {}

    now_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    for site in sites:
        url = site["url"]
        name = site["name"]
        
        state = history.setdefault(url, {
            "name": name,
            "checks": [],
            "consecutive_fails": 0,
            "last_status": "UNKNOWN"
        })

        res = check_target(url)
        current_status = res["status"]
        
        record = {
            "timestamp": now_str,
            "status": current_status,
            "nodes": res.get("nodes", {}),
            "report_link": res.get("report_link", "")
        }
        state["checks"].insert(0, record)
        state["checks"] = state["checks"][:100]

        if current_status == "UP":
            if state["last_status"] == "DOWN":
                send_telegram(
                    f"🟢 <b>САЙТ ЗАРАБОТАЛ!</b>\n\n"
                    f"<b>Имя:</b> {name}\n"
                    f"<b>URL:</b> {url}\n"
                    f"<b>Отчет:</b> {res.get('report_link')}\n"
                    f"Время: {now_str}"
                )
            state["consecutive_fails"] = 0
        else:
            state["consecutive_fails"] += 1
            if state["consecutive_fails"] % 5 == 0:
                send_telegram(
                    f"🔴 <b>Сайт лежит ({state['consecutive_fails']} проверок подряд)</b>\n\n"
                    f"<b>Имя:</b> {name}\n"
                    f"<b>URL:</b> {url}\n"
                    f"<b>Отчет:</b> {res.get('report_link')}"
                )

        state["last_status"] = current_status

    with open("history.json", "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()
