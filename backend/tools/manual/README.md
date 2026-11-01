# Manual smoke scripts

Ad-hoc helpers for poking a **running** ForgeAgent backend (and, for some, a logged-in Edge session).
They are not part of the automated suite: `pytest` only collects `backend/tests`, and the
live ChatGPT test there is skipped unless `FORGEAGENT_LIVE_TESTS=1`.

Run them from `backend/` with the project virtualenv, e.g. `.venv\Scripts\python tools\manual\manual_chat.py`.
