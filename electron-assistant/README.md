Living Assistant desktop shell (Electron)

The floating agent: a round face with eyes that stays on top of the desktop,
independent of any browser, and opens into a chat panel. It is the main daily
interface; the web dashboard is for management, history, settings and logs.

Use it
- Click the orb: open or close the chat (typing, streaming replies, stop,
  regenerate, conversation history, spoken replies).
- Double-click the orb, or press the mic in the chat: ask by voice. The ring
  around the orb shows the live microphone spectrum while it listens.
- Drag the orb anywhere; its position is remembered per display.
- Right-click the orb or use the tray icon: chat, voice, dashboard,
  "Start with Windows", hide/show.
- Ctrl+Shift+Space (Cmd+Shift+Space on macOS) opens or closes the chat.

Chat and voice use the same conversation as the dashboard: the server keeps one
active conversation that every interface continues and follows live.

How it runs
- run.bat installs the Electron runtime (pinned version, one folder per version
  under %TEMP%\LivingAssistant) and starts the backend and this shell.
- The shell keeps the backend available: if http://127.0.0.1:8787 stops
  answering (after a start with the OS, or a crash) it starts the backend itself,
  hidden, with backoff, logging to its user-data folder. It only stops a backend
  it started. Set ASSISTANT_PYTHON to use a different Python.
- Only one copy runs; starting it again opens the chat of the running one.

Manual run
1. cd electron-assistant
2. npm install
3. npm start

Privacy and safety
- The window loads only the local /agent page; other links open in the browser.
- The page gets the local API token from the backend (it is never put in URLs).
- The eyes follow the cursor position only; no keystrokes, window titles or
  screen pixels are read. The microphone is used only when you ask, and each
  listen needs your approval (Allow / Not now in the bubble).
