import re

def extract_files(response_text: str):
    file_actions = []
    seen_paths = set()
    
    valid_exts = {
        'html', 'htm', 'css', 'js', 'jsx', 'ts', 'tsx', 'json', 
        'py', 'md', 'sh', 'sql', 'yaml', 'yml', 'txt', 'bat'
    }
    
    pattern = re.compile(r"```(?:([a-zA-Z0-9_-]+)(?:\s+file=[\"']([^\"']+)[\"'])?)?\s*\r?\n(.*?)\r?\n```", re.DOTALL)
    
    for match in pattern.finditer(response_text):
        lang = match.group(1) or ""
        explicit_file = match.group(2)
        content = match.group(3) or ""
        
        detected_path = None
        if explicit_file:
            detected_path = explicit_file.strip()
            
        if not detected_path:
            preceding = response_text[:match.start()].strip()
            lines = preceding.splitlines()
            for line in reversed(lines[-4:]):
                clean_line = re.sub(r"^[#*\s\d\.\-:`'\"]+|[*\s:`'\"]+$", "", line).strip()
                m = re.search(r"([a-zA-Z0-9_\-\./\\]+\.[a-zA-Z0-9]+)", clean_line)
                if m:
                    cand = m.group(1).replace("\\", "/").strip().lstrip("/")
                    ext = cand.split(".")[-1].lower()
                    if ext in valid_exts and "<" not in cand and ">" not in cand and ".." not in cand:
                        detected_path = cand
                        break
                        
        if not detected_path:
            first_line = content.strip().splitlines()[0] if content.strip() else ""
            m = re.search(r"(?:<!--|//|/\*|#)\s*([a-zA-Z0-9_\-\./\\]+\.[a-zA-Z0-9]+)", first_line)
            if m:
                cand = m.group(1).replace("\\", "/").strip().lstrip("/")
                ext = cand.split(".")[-1].lower()
                if ext in valid_exts and "<" not in cand and ">" not in cand and ".." not in cand:
                    detected_path = cand

        if detected_path and detected_path not in seen_paths:
            seen_paths.add(detected_path)
            file_actions.append({"path": detected_path, "lines": len(content.splitlines())})
            
    return file_actions

sample = '''
Here is the code for your portfolio website:

### 1. `my-portfolio/index.html`
```html
<!DOCTYPE html>
<html>
<body><h1>Portfolio</h1></body>
</html>
```

### 2. `my-portfolio/style.css`
```css
body { background: #111; color: white; }
```

### 3. `my-portfolio/script.js`
```javascript
console.log("Loaded");
```
'''

print("Extracted files:", extract_files(sample))
