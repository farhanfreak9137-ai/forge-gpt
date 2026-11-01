import urllib.request, json, sys

payload = json.dumps({
    "message": "Create a file called hello.txt with the content: Hello from ForgeAgent! This works perfectly."
}).encode()

req = urllib.request.Request(
    "http://127.0.0.1:8000/api/v1/studio/chat",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST"
)
with urllib.request.urlopen(req, timeout=120) as resp:
    data = json.loads(resp.read())
    print("SENDER:", data.get("sender"))
    print("FILE_ACTIONS:", data.get("file_actions"))
    print("EXECUTED_FILES:", data.get("executed_file_changes"))
    text = data.get("text", "")
    print("TEXT (first 500):", text[:500].encode("ascii", errors="replace").decode())

