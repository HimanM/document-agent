# Document Agent - Capstone Writeup

## Title
Document Agent — Resume & Cover Letter Assistant

## Subtitle
An agent-powered assistant that crafts professional plain-text application emails and tailored cover letters from uploaded resumes and public GitHub profiles.

## Card and Thumbnail Image
Add a card or thumbnail image (used by the submission platform to help identify your proposal). Replace the placeholder below with an accessible image path or URL.

Thumbnail placeholder: `path/to/thumbnail.png` or `https://example.com/thumbnail.png`

## Submission Track
Agent-based Applications / Productivity Tools

## Media Gallery (optional)
- Demo video (YouTube): `https://www.youtube.com/your-demo-url-here` (optional)

## Project Description (≤1500 words)
This project implements a lightweight agent-based assistant that helps job applicants generate concise, business-professional plain-text emails and customized cover letters from a candidate's resume and public GitHub profile. It demonstrates tool-enabled agents, session-backed memory, and event-driven streaming to a modern web UI.

Key capabilities:
- Upload resumes (stored under `resumes/`) and optionally summarize them into a small knowledge DB.
- Use a GitHub tool to fetch public profile and repository metadata, providing contextual facts the agent can reference when tailoring messages.
- Run a small `LlmAgent` + `Runner` stack using a TinyDB-backed session store so conversation history and events persist between requests.
- Stream agent responses over Server-Sent Events (SSE) into a single chat bubble with paragraph preservation and a small inline completion note.

Architecture highlights:
- Frontend: Flask single-page app (`flask/templates/index.html`, `flask/static/*`) with a composer supporting drag-and-drop attachments, an attach button, and file chips. Streaming SSE client merges streamed chunks into a single AI bubble and preserves paragraph breaks.
- Backend: `flask/app.py` exposes `POST /api/chat`, upload endpoints (`/api/upload`, `/api/upload_resume`), and admin clear endpoints. The chat endpoint ensures a session exists and runs the Runner in a background thread while streaming Events.
- Agent & Services: `adk_config.py` wires up an `LlmAgent`, registers tools (including `tools/github_tool.py`), and uses `services/session_service.py` (TinyDB) and `services/knowledge_service.py` to persist events and resume summaries.

Limitations & Notes:
- The local TinyDB is intended for demos and is not production-grade storage.
- The agent enforces plain-text email output (no Markdown) when requested; the system instruction is tuned to prefer business-professional tone for application materials.
- Model and client compatibility depends on the environment and API access; ensure required keys and package versions are available before running.

## Attachments
Provide links to the project's code and any supporting materials. Leave the GitHub repository placeholder below; replace it with your public repository URL before final submission.

- GitHub Repository (required — please paste your public repo URL here):

  [ADD YOUR PUBLIC GITHUB REPOSITORY URL HERE]

- Files & key locations in this repository (for reviewers who inspect the bundle directly):
  - `adk_config.py` — agent, tools, and runner configuration
  - `main.py` — CLI reference runner and environment loader
  - `flask/` — web UI, SSE client, and server endpoints
    - `flask/app.py` — Flask endpoints and SSE streaming worker
    - `flask/templates/index.html` — frontend chat UI
    - `flask/static/app.js` — streaming client + upload logic
    - `flask/static/styles.css` — UI styles
  - `services/session_service.py` — TinyDB session store (event serialization)
  - `services/knowledge_service.py` — knowledge DB helpers
  - `tools/github_tool.py` — GitHub profile + repos tool
  - `tools/document_tools.py` — resume processing helpers

## How to run (short)
1. Install dependencies and set environment vars (see `README.md`).
2. Start the Flask app and open the UI; upload resumes under the "Upload Resume" button; Process the resume by sending a message to the agent.

## Contact / Author Note
This is a small personal capstone demo created to explore agent tooling and to obtain the Kaggle participation certificate — a light and earnest project showcasing ADK concepts in a focused, runnable repo.

---

If you want, I can also add a small thumbnail image into the repo and update `README.md` to include the final GitHub URL once you provide it.

## Background and motivation
As a recent graduate applying to internships, I found myself writing similar emails every day. This project was created to automate that repetitive task and to demonstrate agent tooling, memory, and event-driven streaming in a compact capstone-style repository. It was also built after attending Google and Kaggle "5 Days of AI" and is intended as a small personal capstone submission to obtain the participation certificate.

## Goals and scope
- Demonstrate an agent that uses tools and memory to ground responses in user-provided context
- Provide a minimalist web UI with streaming agent responses
- Support file uploads and a simple resume knowledge base

## Implementation summary

### Frontend
- `flask/templates/index.html` and `flask/static/*` provide a single-page chat UI with:
  - Composer area that accepts typed text and file attachments via drag and drop or an attach button
  - Streaming agent replies rendered in a single bubble with paragraph preservation
  - Small italic inline completion note appended inside the AI bubble when streaming finishes

### Backend
- `flask/app.py` exposes these endpoints:
  - `POST /api/chat` - constructs a normalized message object, ensures a session exists, and runs the ADK Runner in a background thread while streaming events as Server Sent Events
  - `POST /api/upload` - upload arbitrary files for use in messages (stored in `user_upload/`)
  - `POST /api/upload_resume` - upload resumes stored under `resumes/`
  - `POST /api/clear_chat` and `POST /api/clear_knowledge` with confirmation and safe truncate behavior for TinyDB

### Agent and services
- `adk_config.py` constructs an `LlmAgent`, registers tools, and creates a `Runner` with a TinyDB-backed `TinyDBSessionService` for sessions.
- `services/session_service.py` implements session creation, event append, and event serialization/deserialization to preserve structured content.
- `services/knowledge_service.py` stores resume summaries in `knowledge_db.json`.

### Tools
- `tools/github_tool.py` fetches public user and repository metadata and summarizes top repositories.
- `tools/document_tools.py` contains utilities to process resumes into simple summaries saved to the knowledge DB.

## How the design maps to ADK concepts
- Agents and Runners: the repo creates an `LlmAgent` and a `Runner`, then runs the Runner asynchronously and streams Events back to the client.
- Tools: the GitHub and document processing tools are registered with the agent and are intended to be called by the agent when the prompt or workflow requires them.
- Sessions and memory: `TinyDBSessionService` persists events and state so conversation history is retained between requests.
- Event content: message content is normalized to simple dicts with `text` and `parts` to avoid ADK validation errors and to make event serialization safe.

## Relation to Kaggle 5 Days of AI materials
- The project follows the core hands-on patterns taught in the 5 Days of AI notebooks: tool-enabled agents, file ingestion as context, session/memory usage, and streaming responses to a UI.
- Specific parallels:
  - Tool usage pattern - the agent calls tools to fetch GitHub data and resume summaries, similar to notebooks demonstrating tool calls
  - File upload and grounding - the repo uploads files and references them in message parts for the agent to use as context
  - Memory and session handling - like the exercises, this repo keeps track of history and uses a persistent store for session events

## Features implemented
- Streaming SSE chat with paragraph separation
- Composer drag and drop and attach-button file uploads
- Resume upload and storage in `resumes/`
- GitHub tool for dynamic context
- TinyDB session and knowledge DB storage
- Confirmation prompts for destructive admin actions

## Limitations and caveats
- Local TinyDB storage is not suitable for production scale
- Model and client compatibility depends on installed libraries and access to the model API
- The GitHub tool may be rate-limited without authentication

## How to reproduce locally
See `README.md` in the repository root for full setup and run instructions including example PowerShell commands.

## Placeholders for demo media
- Screenshot placeholder: `![Demo screenshot](path/to/demo-screenshot.png)`
- Demo video placeholder: `[Watch demo video](https://your.video.url.here)`

## Closing note (personal)
- This is a small and somewhat cheeky personal project I created to earn the participation certificate and to automate writing repetitive internship emails. It focuses on demonstrating ADK patterns in a lightweight, runnable repo.
