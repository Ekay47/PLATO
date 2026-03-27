import json
import time
import httpx


def main() -> None:
    base = "http://127.0.0.1:8000"
    req = {
        "requirement_text": "When a customer places an order, the system checks inventory. If in stock, reserve and confirm. Else back-order. Then ship.",
        "diagram_type": "activity",
    }

    with httpx.Client(timeout=30.0) as c:
        r = c.post(f"{base}/runs", json=req)
        r.raise_for_status()
        run_id = r.json()["run_id"]
        print("run_id", run_id)

        start = time.time()
        with c.stream("GET", f"{base}/runs/{run_id}/events", headers={"Accept": "text/event-stream"}) as s:
            for line in s.iter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    ev = json.loads(line[len("data: ") :])
                    payload = ev.get("payload") or {}
                    msg = payload.get("message") or payload.get("key")
                    print(ev.get("type"), ev.get("step"), msg)
                if time.time() - start > 8:
                    break


if __name__ == "__main__":
    main()

