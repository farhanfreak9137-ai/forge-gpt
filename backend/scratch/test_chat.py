import urllib.request, json

payload = json.dumps({"message": "Hello! Say hi back in one sentence."}).encode()
req = urllib.request.Request(
    "http://127.0.0.1:8000/api/v1/studio/chat",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST"
)
with urllib.request.urlopen(req, timeout=120) as resp:
    data = json.loads(resp.read())
    print("SENDER:", data.get("sender"))
    print("TEXT:", data.get("text", "")[:300])

