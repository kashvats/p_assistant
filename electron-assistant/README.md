Cross-platform hovering desktop companion for Living Assistant.

How to run:
1. cd electron-assistant
2. npm install
3. npm start

The app creates a small always-on-top, frameless window that connects to the
local FastAPI service. It polls durable activity events, surfaces questions
when a tool or evaluation fails, sends approved questions to the assistant, and
offers an explicit button for approval-gated screen analysis.

On first launch, open the settings button and paste the local assistant access
token if the backend requires authentication. This token only authenticates
the local dashboard API; it is not a model-provider credential. The token is
stored in the Electron profile so it is not placed in source code.
For managed launches, `ASSISTANT_API_URL` and `ASSISTANT_API_TOKEN` can be
provided as environment variables instead.

The companion observes assistant activity and does not continuously read the
screen. Screen analysis only runs when the user presses the screen button and
the backend's existing desktop approval gate allows it.

The eyes receive only local, coarse signals from Electron: cursor position
relative to the companion window and system idle time. These drive eye tracking
and observing/idle expressions; they do not include keystrokes, clicks, window
titles, screen pixels, messages, passwords, tokens, or payment data. Assistant
activity events may drive learning-state expressions, but only event type names
and coarse idle/active counts are retained locally. The UI labels these as
observed or inferred rather than confirmed preferences.

Pause observation, disable learning, clear learned behavior, and hide the
assistant from the visible privacy controls. Hiding can be reversed with
Ctrl+Shift+Space (Cmd+Shift+Space on macOS).

The compact face itself is draggable: grab the eyes/avatar and move the
floating companion anywhere on the desktop. The expanded assistant can be
moved from its top bar.

Expanded mode also includes **Talk to me**. It uses the backend's existing
approval-gated local microphone capture, local Whisper transcription, normal
orchestrator command execution, and optional local TTS response path. The
voice request validates the selected model before opening the microphone:
local Ollama/AirLLM models do not require provider credentials; an online
provider reports only its own required credential or unsupported-adapter error.

The provider badge identifies whether the active model is local or online.
Ollama and AirLLM models never require a model-provider API key. Explicit online
model prefixes (`openai:`, `anthropic:`, `claude:`, `google:`, or `gemini:`)
report only the selected provider's missing environment credential
(`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, or `GOOGLE_API_KEY`). This installation
does not provide external inference adapters, so online selections are rejected
before they can be routed to Ollama. Selecting a local model removes the online
credential prompt.
