"""
Helm backend smoke test.
Runs against localhost:8000 — backend must be up.
"""
import urllib.request
import urllib.error
import json
import sys
import time
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASE = "http://localhost:8000"
OK = " OK"
FAIL = " FAIL"

results = []

def req(method, path, body=None, token=None, label=None):
    url = BASE + path
    data = json.dumps(body).encode() if body else None
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            raw = resp.read()
            status = resp.status
            try:
                payload = json.loads(raw)
            except Exception:
                payload = raw.decode()
            return status, payload
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            payload = json.loads(raw)
        except Exception:
            payload = raw.decode()
        return e.code, payload

def check(label, status, payload, expect_status, extract=None):
    ok = status == expect_status
    icon = OK if ok else FAIL
    print(f"[{status}]{icon} {label}")
    if not ok:
        print(f"       → {payload}")
    results.append((label, ok))
    if extract and ok:
        return extract(payload)
    return None

print("\n===================================")
print("  Helm Smoke Test")
print("===================================\n")

# 1. Health
status, payload = req("GET", "/api/health")
check("GET /api/health", status, payload, 200)

# 2. Register
status, payload = req("POST", "/api/auth/register", {
    "email": "smoketest@helmgate.dev",
    "name": "Smoke Tester",
    "password": "smoke1234"
})
if status == 400 and "already registered" in str(payload):
    # Already exists — login instead
    status2, payload2 = req("POST", "/api/auth/login", {
        "email": "smoketest@helmgate.dev",
        "password": "smoke1234"
    })
    check("POST /api/auth/register (user exists → login)", status2, payload2, 200)
    token = payload2.get("access_token") if isinstance(payload2, dict) else None
else:
    token = check("POST /api/auth/register", status, payload, 201,
                  extract=lambda p: p.get("access_token"))

if not token:
    print("\n✗ No token — cannot continue.\n")
    sys.exit(1)

# 3. Login
status, payload = req("POST", "/api/auth/login", {
    "email": "smoketest@helmgate.dev",
    "password": "smoke1234"
})
check("POST /api/auth/login", status, payload, 200)

# 4. Wrong password → 401
status, payload = req("POST", "/api/auth/login", {
    "email": "smoketest@helmgate.dev",
    "password": "wrongpass"
})
check("POST /api/auth/login (wrong pass → 401)", status, payload, 401)

# 5. Profile
status, payload = req("GET", "/api/profile", token=token)
check("GET /api/profile", status, payload, 200)

# 6. Memory — upsert
status, payload = req("PUT", "/api/memory/role", {"value": "Backend тестер"}, token=token)
check("PUT /api/memory/role", status, payload, 200)

# 7. Memory — list
status, payload = req("GET", "/api/memory", token=token)
check("GET /api/memory", status, payload, 200)

# 8. Memory — delete
status, payload = req("DELETE", "/api/memory/role", token=token)
check("DELETE /api/memory/role", status, payload, 204)

# 9. Create chat
chat_id = check("POST /api/chats", *req("POST", "/api/chats", token=token), 201,
                extract=lambda p: p.get("id"))

if not chat_id:
    print("\n✗ No chat_id — cannot continue.\n")
    sys.exit(1)

# 10. List chats
status, payload = req("GET", "/api/chats", token=token)
check("GET /api/chats", status, payload, 200)

# 11. Send message (streaming — we just check it opens, not full content)
print(f"\n[...] POST /api/chats/{chat_id}/messages (SSE stream)...")
url = f"{BASE}/api/chats/{chat_id}/messages"
body = json.dumps({"content": "Привет! Кто ты?"}).encode()
headers = {
    "Content-Type": "application/json",
    "Accept": "text/event-stream",
    "Authorization": f"Bearer {token}",
}
r = urllib.request.Request(url, data=body, headers=headers, method="POST")
try:
    with urllib.request.urlopen(r, timeout=120) as resp:
        chunks = []
        for line in resp:
            line = line.decode("utf-8").strip()
            if line.startswith("data: "):
                try:
                    d = json.loads(line[6:])
                    chunks.append(d)
                    if d.get("type") == "done":
                        break
                except Exception:
                    pass
        has_meta  = any(c.get("type") == "meta"  for c in chunks)
        has_token = any(c.get("type") == "token" for c in chunks)
        has_done  = any(c.get("type") == "done"  for c in chunks)
        has_error = any(c.get("type") == "error" for c in chunks)
        # OK if: stream opened + meta received + clean close (done OR graceful error)
        ok = has_meta and (has_done or has_error)
        icon = OK if ok else FAIL
        print(f"[SSE]{icon} POST /api/chats/{chat_id}/messages")
        if has_token:
            sample = "".join(c.get("content","") for c in chunks if c.get("type")=="token")
            print(f"       LLM sample: {sample[:80]}...")
        if has_error:
            err = next(c.get("detail","") for c in chunks if c.get("type")=="error")
            print(f"       LLM error (handled gracefully): {err[:120]}")
        if not ok:
            print(f"       meta={has_meta} token={has_token} done={has_done} error={has_error}")
            print(f"       chunks={chunks[:3]}")
        results.append((f"POST /api/chats/{chat_id}/messages", ok))
except Exception as e:
    print(f"[ERR]{FAIL} POST /api/chats/{chat_id}/messages → {e}")
    results.append((f"POST /api/chats/{chat_id}/messages", False))

# 12. Get messages
status, payload = req("GET", f"/api/chats/{chat_id}/messages", token=token)
check(f"GET /api/chats/{chat_id}/messages", status, payload, 200)

# 13. Files list
status, payload = req("GET", "/api/files", token=token)
check("GET /api/files", status, payload, 200)

# 14. Delete chat
status, payload = req("DELETE", f"/api/chats/{chat_id}", token=token)
check(f"DELETE /api/chats/{chat_id}", status, payload, 204)

# 15. Admin — stats (expect 403, user is not admin)
status, payload = req("GET", "/api/admin/stats", token=token)
check("GET /api/admin/stats (non-admin → 403)", status, payload, 403)

# ═══ Summary ═══
print("\n===================================")
passed = sum(1 for _, ok in results if ok)
failed = sum(1 for _, ok in results if not ok)
print(f"  {passed}/{len(results)} passed   {failed} failed")
print("===================================\n")
if failed:
    sys.exit(1)
