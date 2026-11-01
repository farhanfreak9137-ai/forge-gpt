# What NOT to send to someone else (for you, the sender)

**This file is for you. It is not included in the zip.**

## The short version

1. **Don't zip the project folder yourself.** The folder has about 1 GB of private and machine-specific data in it.
2. **Use the ready-made zip**, or make a fresh one by running `scripts\make_share_zip.ps1` (right-click → *Run with PowerShell*). It leaves out everything on the "never send" list below and checks its own result.
3. Send the zip over a **private** channel (direct message, private cloud link). Not a public link.

The zip it builds is named `ForgeAgent-share.zip` and is saved next to the project folder (one level up).

---

## Never send these (the script already leaves them out)

| File or folder | What is in it | Why it's dangerous or useless to send |
|---|---|---|
| `backend\data\browser_profile\` (about 760 MB) | The Edge profile ForgeAgent uses, **including your logged-in ChatGPT session** | **Whoever has it can use your ChatGPT account.** The most important one on this list. |
| `backend\data\edge_profile\` | Another Edge profile | Same risk: logins and cookies. |
| `backend\data\forgeagent.db` | Your projects, tasks, approvals and activity history | Private. Also full of old test data. |
| `backend\data\studio_sessions.json` | Every Studio chat you have had | Private conversations. |
| `backend\.env` (if you made one) | Settings such as **your API keys** | Keys cost money if someone else uses them. |
| `workspace\` | Files the agent created for you (for example `my-portfolio`, `farhan.txt`) | Your personal work. The zip gets an empty one. |
| `.git\` | Full change history of the project | Can contain things you deleted or never meant to share. |
| `backend\.venv\` (about 160 MB) | A Python environment built for **your** computer | Doesn't work on another PC. `SETUP.bat` rebuilds it. |
| `frontend\node_modules\` | Downloaded web packages | Huge, and rebuilt by `SETUP.bat`. |
| `frontend\dist\` | A build output | Rebuilt by setup. |
| `__pycache__\`, `.pytest_cache\`, `*.pyc`, `*.log` | Temporary files | Junk. |
| `START EDGE.bat`, `STARTFRONTEND.bat` | Duplicates of `START_EDGE.bat` and `START_FRONTEND.bat` | Only confusing. The script leaves them out. |
| `WHAT_NOT_TO_SEND.md` (this file) | Notes for you | Not meant for the other person. |

## Safe to send (the zip contains these)

- `backend\app`, `backend\tests`, `backend\tools`, `backend\requirements.txt`, `backend\pyproject.toml`
- `frontend\src`, `frontend\package.json`, `package-lock.json` and the config files
- `scripts\`, `docs\`, `examples\`
- `SETUP.bat`, `START_FORGEAGENT.bat`, `START_ALL.bat` and the other launcher `.bat` files
- `SETUP_GUIDE.md` (the guide for the other person), `README.md`, `.env.example` (a template with **no** secrets), `Dockerfile`, `docker-compose.yml`

---

## Before you send: a 30-second check

1. Open the zip in Windows Explorer (don't extract it).
2. It should be **small, a few MB** (not hundreds). If it's big, something private got in.
3. Look inside the folder `ForgeAgent`. You should **not** see any of these: `data`, `.venv`, `node_modules`, `.git`, `.env`, `workspace\my-portfolio`.
4. The script also prints "No private files found in the zip" when it is clean.

## If you sent something private by mistake

| What went out | Do this straight away |
|---|---|
| `browser_profile` / `edge_profile` (ChatGPT login) | Open ChatGPT → Settings → Security → **Log out of all devices**, then change your password. |
| A `.env` with an API key | Delete that key at https://platform.openai.com/api-keys and create a new one. |
| `forgeagent.db` / `studio_sessions.json` | Nothing to revoke, but assume the other person has read your chats and tasks. |

## Good habits when you share

- Ask the other person to also keep **their own** `backend\data` and `.env` private.
- If you change the project later, run `scripts\make_share_zip.ps1` again to get an updated zip. Never edit the zip by hand.
- Your own copy keeps everything: this process never deletes anything from your project.
