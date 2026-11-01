# ForgeAgent: Setup & User Guide

ForgeAgent is an AI helper that lives on your own computer. You chat with it, and it writes code, creates files and runs commands for you. **It always asks before doing anything risky.**

This guide takes you from zero to your first chat. Follow the steps in order. You only need to do the setup once.

> **Works on:** Windows 10 or 11 only.

---

## 1. What you need first

| You need | Why | How to get it |
|---|---|---|
| **Windows 10 or 11** | The app's launchers are Windows-only | |
| **An internet connection** | Setup downloads about 1 GB of tools (once) | |
| **About 3 GB free disk space** | Tools and the app itself | |
| **Node.js (LTS version)** | Runs the app's web page | Go to https://nodejs.org and install the "LTS" button. Or open **Windows Terminal** and run `winget install OpenJS.NodeJS.LTS` |
| **Git** | Lets the agent save restore points for your projects | Go to https://git-scm.com/download/win and install with the default options. Or run `winget install Git.Git` |
| **winget** ("App Installer") | Setup uses it to install Python tools | Already on Windows 11 and most Windows 10. If missing, install **App Installer** from the Microsoft Store |
| **One AI "brain"** (pick one) | Something has to do the thinking | See step 5 |

**After installing Node.js or Git, close any open windows** so Windows notices them.

You do **not** need to install Python yourself. Setup does it.

---

## 2. Unpack the app

1. Right-click the zip file and choose **Extract All…**
2. Pick a **short, simple folder**, for example `C:\ForgeAgent`.
   - Avoid OneDrive or Desktop folders that sync, and avoid very long folder names. They cause odd errors.
3. Open the extracted folder. You should see files such as `SETUP.bat`, `START_FORGEAGENT.bat` and `SETUP_GUIDE.md` (this file).

---

## 3. First-time setup (do this once)

1. Double-click **`SETUP.bat`**.
2. If Windows shows **"Windows protected your PC"**, click **More info**, then **Run anyway**. The file is a plain text script, and you can open it in Notepad to read it.
3. A black window opens and prints a lot of text. **Wait.** It takes about 5 to 15 minutes depending on your internet. It is:
   - installing Python 3.12 (through a tool called `uv`),
   - installing the app's backend packages and a test browser,
   - installing and building the web page.
4. When you see **"Setup finished"**, press any key to close the window.

If it ends with an `[Error]` message, go to **Troubleshooting** (step 10).

> Skipped this step? It's fine: `START_FORGEAGENT.bat` (next step) notices a missing setup and runs it for you.

---

## 4. Start the app

1. Double-click **`START_FORGEAGENT.bat`**.
2. A few things happen on their own:
   - A **Microsoft Edge** window opens on ChatGPT. It is used only for the ChatGPT option in step 5, so you can ignore it if you use something else. It stays open on purpose: **don't close it** while you use ChatGPT through ForgeAgent.
   - A small **"ForgeAgent Backend"** window appears (minimised in the taskbar).
   - A black window shows the web page server, and your browser opens **http://localhost:5173**.
3. If the page says it can't connect, wait about 10 seconds and refresh.

You are in when you see **Agent Studio** with a friendly little robot named Forge.

**To stop the app:** close **both** black windows (the main one and "ForgeAgent Backend" in the taskbar). Closing only your browser tab does not stop it.

---

## 5. Choose your AI "brain" (do this once)

ForgeAgent needs an AI to think with. Pick **one** of these. You can switch any time using the engine box just under the message box in Agent Studio.

### Option A: ChatGPT in Edge (uses your normal ChatGPT account)
1. In the Edge window that opened, **log in to ChatGPT** (solve any "I'm not a robot" check there).
2. In Agent Studio, set the engine box to **ChatGPT in Microsoft Edge**.
3. Send a message. Edge will type it into ChatGPT and bring the answer back.

Good to know:
- The Edge window just needs to **stay open**. It can sit behind other windows or be minimised-to-the-side, but don't close it.
- This works by automating the ChatGPT website. It is fragile (ChatGPT changes its page now and then) and may not be allowed by OpenAI's terms of service. Use it for personal experiments only.
- Edge didn't open, or you closed it? In Agent Studio click **Open Edge to log in**.

### Option B: OpenAI API key (most reliable)
1. Get a key from https://platform.openai.com/api-keys (this is paid by usage).
2. Open **Settings**, set **Engine** to **OpenAI-compatible API**, paste the key, and click **Save changes**.
3. Click **Test connection**. You should see "is reachable".

### Option C: Ollama (free, runs on your own computer)
1. Install Ollama from https://ollama.com and run `ollama pull llama3` in a terminal.
2. Open **Settings**, set **Engine** to **Ollama**, check the server URL and model name, and **Save changes**.

### Option D: Just look around (no account)
Choose **Mock AI (offline test)**. It gives instant, canned replies, so you can learn the app without any account.

### Keeping your choice after a restart
Choices made in **Settings** are forgotten when you stop the app. To make them permanent:
1. Right-click `.env.example` (in the app folder), choose **Open with → Notepad**, then **File → Save As** and save it as `.env` inside the `backend` folder (set "Save as type" to **All files** so Windows doesn't add `.txt`). The full name must be `backend\.env`.
2. Edit the lines you need, for example:
   ```
   FORGEAGENT_DEFAULT_AI_CONNECTOR=openai
   FORGEAGENT_OPENAI_API_KEY=your-key-here
   ```
   (Engine names: `chatgpt_edge`, `openai`, `ollama`, `mock`, `browser_handoff`.)
3. Stop and start the app again.

Keep that `.env` file private. It contains your key.

---

## 6. Your first chat

1. Open **Agent Studio** (the first item in the left menu).
2. Type what you want in the box at the bottom, for example *"Create a hello.py that prints hello, and run it"*, and press **Enter**. (Use **Shift+Enter** for a new line.)
3. Watch Forge work. When the AI wants to run a command, you will see an amber card: **"Run this command?"**
   - **Approve & run**: let it happen.
   - **Reject**: don't.
   - Read the command first. It runs on your computer.
4. Files the agent writes appear in the **Workspace** panel (button at the top right). They are saved in the `workspace` folder inside the app folder.

### The switches and buttons that matter
- **Auto-run safe commands** (next to the engine box): when ON, harmless commands run without asking. Risky ones (installs, `git push`, deleting things) **always** ask. It is OFF by default.
- **Emergency stop** (red button, top right): instantly blocks every command and file change. Click again, and confirm, to resume.
- **New chat**: starts a fresh conversation. The app also opens on a fresh chat every time you start it. Old chats are in the chat list (the panel icon at the top left).

---

## 7. Projects and tasks (for bigger jobs)

Use this when you want the agent to work inside an existing project folder or plan a larger piece of work.

1. Open **Projects** and click **New project** (creates a folder) or **Import existing** (use a folder you already have). Type the full folder path, for example `C:\Projects\my-app`.
2. Select the project and click **Start a task**. Give it a title and describe what you want and how to check it worked.
3. Open **Tasks** to watch it go through **Plan → Edit → Verify → Done**.
4. If it needs your OK you'll see an amber **Approve / Reject** box, and a number badge on **Tasks** in the menu.
5. Git checkpoints are saved as it works, so you can see what changed. (This needs Git, from step 1.)

---

## 8. Handy things

- **Ctrl + K** opens a quick-jump box: go to any page, start a new chat, switch theme, or open a recent task.
- **Theme and colour:** the sun/moon icon at the top, or **Settings → Make it yours**. Light, dark, or match your computer, plus five accent colours.
- **Collapse the left menu** with the **Collapse** button at its bottom.
- **Overview** shows what the agent is doing right now, and what needs you.
- **Activity** is a log of everything the agent did.

---

## 9. Staying safe

- ForgeAgent **runs commands on your computer**. It only allows a short list of tools and asks before risky actions, but if you approve something, it runs. Read what you approve.
- It only listens on **your own computer**. Don't try to open it to a network or the internet. It has no login.
- Don't give the `backend\data` folder or your `.env` file to anyone. They contain your ChatGPT login and keys.

---

## 10. Troubleshooting

| Problem | What to do |
|---|---|
| `SETUP.bat` says **winget is not recognised** | Install **App Installer** from the Microsoft Store, then run `SETUP.bat` again. |
| **"npm is not recognised"** / setup fails at the web page step | Node.js isn't installed or Windows hasn't noticed it. Install Node.js (step 1), **close all windows**, and run `SETUP.bat` again. |
| Setup stops with a download or network error | Check your internet (and VPN/proxy), then run `SETUP.bat` again. It carries on where it left off. |
| Browser says **can't connect to localhost:5173** | Wait 10 to 20 seconds and refresh. Make sure the black window is still open. |
| The page shows **"Can't reach the ForgeAgent backend"** | The "ForgeAgent Backend" window isn't running. Close all ForgeAgent windows and double-click `START_FORGEAGENT.bat` again. |
| **Port 8000 or 5173 is already in use** | An old copy is still running. Close its black windows, or restart the computer, then start again. |
| Messages never get an answer with the ChatGPT engine | Make sure the Edge window is **open and logged in** to ChatGPT, and no "verify you're human" box is waiting in it. Click **Open Edge to log in** in Agent Studio to bring it back. |
| The engine/API key you chose is gone after a restart | Settings are not remembered by default. Use the `backend\.env` method in step 5. |
| A command shows **"blocked"** | That is the safety list working. Things like `python -c "..."`, shells, and commands outside the project folder are never allowed, on purpose. Ask the AI to put the code in a file instead. |
| You want to start completely fresh | Stop the app and delete the folder `backend\data`. (This also logs you out of ChatGPT in the app's Edge window.) |
| Anything else | Read the black windows for the last error line, and send that line to the person who gave you the app. |

---

## 11. Quick reference

| I want to… | Do this |
|---|---|
| Install | Double-click `SETUP.bat` (once) |
| Start | Double-click `START_FORGEAGENT.bat`, then use http://localhost:5173 |
| Stop | Close both black windows |
| Log in to ChatGPT again | Agent Studio → **Open Edge to log in** (or double-click `OPEN_EDGE_CHATGPT.bat`) |
| Jump anywhere | **Ctrl + K** |
| Stop everything right now | The red **Emergency stop** button |

*For developers: run the automated tests with `backend\.venv\Scripts\python.exe -m pytest backend\tests`. More detail is in `README.md` and the `docs` folder.*
