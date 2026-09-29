# Living Assistant

A highly autonomous, local-first, privacy-respecting personal AI operating assistant built on Ollama, FastAPI, and local tools. 

Unlike a simple chat interface, Living Assistant is a paranoid, multi-layered system designed to run as a continuous background daemon on your local hardware. It manages its own resources, learns from failure, and can even evaluate and write its own code improvements in isolated sandboxes.

## Features

### 1. Core Agentic Orchestration
*   **Hierarchical Orchestrator:** Dynamically routes tasks to specialized local models (SLMs) based on the domain.
*   **Nervous System Daemon:** A background loop that monitors file changes, calendar events, routines, and security telemetry without keeping an LLM loaded in memory.
*   **Adaptive Resource Manager:** Dynamically monitors physical RAM, VRAM, and thermal limits. Manages concurrent LLM generation budgets and evicts unused resident models via LRU to prevent out-of-memory crashes on local hardware.
*   **Local-First Execution:** Relies entirely on local providers (Ollama) rather than cloud APIs, ensuring absolute privacy.

### 2. Evaluated Self-Improvement (Auto-Dev)
*   **Code Self-Mutation:** The assistant can propose and write code to modify user projects, or even its own codebase.
*   **Evaluation Engine:** Before applying a code change, it creates an isolated Git worktree or a network-dropped, read-only Docker container to run unit tests, linters, and benchmarks against the proposed code.
*   **Canary Testing & Rollback:** Runs original and mutated code side-by-side to measure performance regressions before merging. Automatically issues a Git revert if evaluations fail.

### 3. Experience & Memory Engine
*   **Continuous Learning:** Records "episodes" of failed and successful tool executions. Repeated successful episodes are promoted into permanent "lessons" to prevent future failures.
*   **Confidence Decay:** Lessons that conflict with new data or aren't reinforced will decay and be forgotten over time.
*   **Vector Storage:** Integrates with Mem0 and Qdrant for semantic retrieval of past context.

### 4. Extensive Environment Control
*   **Browser Automation:** Deep integration with Playwright. Can navigate, click, fill forms, and read pages. Falls back to headless browser scraping if search API keys are missing.
*   **Desktop Vision & Control:** Takes screenshots, reads active window titles, reads/writes your clipboard, and can physically control your mouse/keyboard.
*   **Voice I/O:** Always-listening wake word detection (openwakeword), local speech-to-text (Whisper), and local text-to-speech (Piper).
*   **File & Shell Execution:** Executes Bash/PowerShell commands with strict timeout boundaries and tracks descendant process trees.
*   **Database Adapters:** Connects to and queries local Postgres, MySQL, and MongoDB databases.
*   **Connectors & OAuth:** Interacts with external services (GitHub, Google, etc.) storing all credentials securely in the native OS keyring.
*   **Calendar, Routines & Briefings:** Manages a local schedule, enforces "quiet hours", triggers "focus modes", and generates morning/evening briefings based on recent activity.

### 5. The "Paranoid" Security Guardian
Because this AI has local execution privileges, the codebase is heavily armored against Indirect Prompt Injection.
*   **Strict Interactive Approvals:** High-risk actions (executing arbitrary shell commands, modifying files) pause execution and require a physical Yes/No prompt on your screen or CLI before proceeding.
*   **DNS Pinning & SSRF Protection:** When browsing, the route guard manually resolves DNS, blocks access to local/private IPs (e.g., `127.0.0.1`, `192.168.1.1`), and pins the browser to the exact IP to prevent DNS-rebinding attacks.
*   **Observation Sanitization:** Any text scraped from the web or OCR'd from your screen is strictly wrapped as an "untrusted external observation".
*   **Core Protection:** The self-improvement engine is hard-coded to reject any proposed edits to its own security files. It cannot jailbreak itself.
*   **Security Sensors:** A daemon that ingests raw OS telemetry (macOS Endpoint Security, Windows Event Logs) to monitor for suspicious child processes or unauthorized network connections.

### 6. Deployment & Platform Hardening
*   **Local Web Dashboard & Desktop HUD:** Hosts a FastAPI backend with a React + Vite + Tailwind dashboard and a hovering Electron companion HUD.
*   **Release Manager:** Handles safe, idempotent updates. Creates fresh virtual environments for updates, snapshots user state, and can roll back to a previous version cleanly.
*   **Cross-Platform Daemons:** Automatically installs the background nervous system as an unprivileged background service (Scheduled Task on Windows, `systemd` on Linux, `LaunchAgent` on macOS).

## Quick Start & Access URLs

### Application URLs

Once started, the assistant serves on `127.0.0.1:8787` by default:

| Interface | URL | Description |
| :--- | :--- | :--- |
| **Web Dashboard** | [http://127.0.0.1:8787/dashboard](http://127.0.0.1:8787/dashboard) | Primary control center: Chat, Model Manager, Approvals, Skills, Agents, Security, and Activity telemetry. |
| **Desktop Companion Agent** | [http://127.0.0.1:8787/agent](http://127.0.0.1:8787/agent) | Lightweight, floating HUD interface loaded by the Electron companion. |
| **Local REST API & Docs** | [http://127.0.0.1:8787/docs](http://127.0.0.1:8787/docs) | Interactive OpenAPI/Swagger documentation covering all 149+ local endpoints. |

---

### Running the Project

#### Option A: One-Click Launchers (Recommended)

- **Windows:** Double-click or run `run.bat`. This automatically checks Python and Node.js prerequisites, validates dependencies, starts the FastAPI server, launches the Electron desktop companion HUD, and opens the Web Dashboard in your browser.
  ```cmd
  run.bat
  ```

- **Linux / macOS:** Run `run.sh` to initialize the environment and start the API server:
  ```bash
  chmod +x run.sh
  ./run.sh
  ```

#### Option B: Manual CLI Execution

```bash
# 1. Install editable package and dependencies
pip install -e .

# 2. Run initial environment diagnostics and onboarding (optional)
organism doctor
organism onboard

# 3. Start the Web Dashboard and API server (Accessible at http://127.0.0.1:8787/dashboard)
organism serve

# Or run interactive terminal chat:
organism chat

# Or start the model-free background daemon (Nervous System):
organism daemon
```

## Documentation

Detailed architecture and module documentation can be found in the `docs/` directory:
* [Architecture Overview](docs/ARCHITECTURE.md)
* [Evaluated Self Improvement](docs/EVALUATED_SELF_IMPROVEMENT.md)
* [Experience Engine](docs/EXPERIENCE_ENGINE.md)
* [Security Sensor Platform](docs/SECURITY_SENSOR_PLATFORM.md)
* [Threat Model](docs/THREAT_MODEL.md)
* ...and more.