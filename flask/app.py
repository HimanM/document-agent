import os
import sys
import uuid
import json
import threading
import asyncio
import time
import webbrowser
from queue import Queue
import logging
from typing import List
from flask import Flask, request, jsonify, Response, send_from_directory, render_template
from werkzeug.utils import secure_filename

# Ensure project root is on sys.path so imports like `adk_config` work
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Import project runner/agent
from adk_config import runner, agent, chat_session_service, knowledge_service

app = Flask(__name__, template_folder='templates', static_folder='static')

log_level = logging.DEBUG if os.getenv('DEBUG', '').lower() in ('1', 'true', 'yes') else logging.INFO
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)

# Ensure upload folder exists
PROJECT_ROOT = REPO_ROOT
UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, 'user_upload')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Allowed extensions (basic)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'txt', 'docx'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# LocalMessage shim (similar to main.py)
class LocalMessage:
    def __init__(self, *, content, role: str = "user"):
        # Normalize to a minimal shape expected by Runner: an object with
        # `.role` and `.parts` where each part has a `.text` attribute.
        self.role = role
        # Ensure content is a plain dict with a 'parts' list
        if isinstance(content, dict):
            self.content = content
        else:
            # try to keep as-is if it's a genai Content-like object
            try:
                # attempt to extract parts into a dict
                parts = getattr(content, 'parts', None)
                if parts is not None:
                    self.content = {'parts': [p for p in parts]}
                else:
                    self.content = {'parts': [{'text': str(content)}]}
            except Exception:
                self.content = {'parts': [{'text': str(content)}]}

        # Keep parts as plain dicts {'text': ...}
        self.parts = []
        for p in self.content.get('parts', []):
            if isinstance(p, dict):
                self.parts.append({'text': p.get('text')})
            elif hasattr(p, 'text'):
                try:
                    self.parts.append({'text': p.text})
                except Exception:
                    self.parts.append({'text': str(p)})
            else:
                self.parts.append({'text': str(p)})


def extract_text_from_event(event):
    content = getattr(event, 'content', None)
    text_parts = []
    if content is None:
        return ''
    if isinstance(content, str):
        return content
    if hasattr(content, 'text') and content.text:
        return content.text
    parts = getattr(content, 'parts', None)
    if parts:
        for p in parts:
            t = getattr(p, 'text', None)
            if t:
                text_parts.append(t)
    return "\n".join(text_parts).strip()


def async_worker(queue: Queue, user_id: str, session_id: str, final_message_to_send: LocalMessage):
    async def run_and_stream():
        try:
            async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=final_message_to_send):
                # Only stream messages authored by the agent
                try:
                    if event.author == agent.name:
                        text = extract_text_from_event(event)
                        queue.put({"type": "agent_message", "text": text})
                except Exception as e:
                    queue.put({"type": "error", "text": str(e)})
        except Exception as e:
            queue.put({"type": "error", "text": f"Worker exception: {e}"})
        finally:
            queue.put(None)

    asyncio.run(run_and_stream())


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1]
        gen_name = f"{uuid.uuid4().hex}{ext}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], gen_name)
        file.save(save_path)
        # Return relative path usable by the agent
        rel_path = os.path.join('user_upload', gen_name).replace('\\', '/')
        return jsonify({"path": rel_path, "filename": gen_name})
    return jsonify({"error": "File type not allowed"}), 400


@app.route('/api/upload_resume', methods=['POST'])
def upload_resume():
    # Uploads a resume to the `resumes/` folder in the project root.
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        ext = os.path.splitext(filename)[1]
        gen_name = f"{uuid.uuid4().hex}{ext}"
        resumes_dir = os.path.join(PROJECT_ROOT, 'resumes')
        os.makedirs(resumes_dir, exist_ok=True)
        save_path = os.path.join(resumes_dir, gen_name)
        file.save(save_path)
        rel_path = os.path.join('resumes', gen_name).replace('\\', '/')
        return jsonify({"path": rel_path, "filename": gen_name})
    return jsonify({"error": "File type not allowed"}), 400


@app.route('/api/clear_chat', methods=['POST'])
def clear_chat():
    # Instead of deleting the file (which can be locked on Windows),
    # truncate the TinyDB table backing the session service to clear history.
    try:
        if hasattr(chat_session_service, 'sessions_table'):
            chat_session_service.sessions_table.truncate()
            return jsonify({"ok": True, "message": "Chat history cleared (table truncated)."})
        else:
            # Fallback: attempt to recreate the file content safely
            chat_db = os.path.join(PROJECT_ROOT, 'chat_history_db.json')
            open(chat_db, 'w').close()
            return jsonify({"ok": True, "message": "Chat history file reset."})
    except Exception as e:
        logger.exception("Failed to clear chat history")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/clear_knowledge', methods=['POST'])
def clear_knowledge():
    # Clear knowledge entries using the KnowledgeService to avoid removing files
    # that may be locked by the running process.
    resumes_folder = os.path.join(PROJECT_ROOT, 'resumes')
    try:
        if hasattr(knowledge_service, 'table'):
            knowledge_service.table.truncate()
        else:
            kb = os.path.join(PROJECT_ROOT, 'knowledge_db.json')
            open(kb, 'w').close()

        # Optionally delete resume files: only remove if they are writable and
        # not in use. We'll attempt to remove but ignore failures.
        for fname in os.listdir(resumes_folder) if os.path.isdir(resumes_folder) else []:
            fpath = os.path.join(resumes_folder, fname)
            try:
                os.remove(fpath)
            except Exception:
                logger.debug("Could not remove resume file %s (may be locked)", fpath)

        return jsonify({"ok": True, "message": "Knowledge DB cleared and resumes removed where possible."})
    except Exception as e:
        logger.exception("Failed to clear knowledge DB")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json() or {}
    user_id = data.get('user_id', 'doc_user_1')
    session_id = data.get('session_id', 'doc_chat_session')
    message = data.get('message', '')
    file_paths: List[str] = data.get('file_paths', [])

    # Build content parts
    # Build simple content parts as plain dicts to avoid pydantic validation
    # issues when Runner validates Event content. We include file references
    # as text tokens like [file:user_upload/...] so the agent can handle them.
    parts = []
    for p in file_paths:
        local_path = os.path.join(PROJECT_ROOT, p) if not os.path.isabs(p) else p
        if os.path.exists(local_path):
            parts.append({'text': f"[file:{p}]"})
        else:
            parts.append({'text': f"[missing_file:{p}]"})

    if message:
        parts.append({'text': message})

    # create a top-level text join to make the content a simple dict with a
    # readable `text` field and a `parts` list of dicts. This avoids passing
    # complex SDK objects into the Runner which can trigger pydantic errors.
    joined_text = "\n".join(p.get('text', '') for p in parts if p.get('text'))
    content_obj = {'text': joined_text, 'parts': parts}
    # Log the content shape for debugging
    logger.debug("Prepared content_obj for runner: %s", repr(content_obj))
    final_message = LocalMessage(content=content_obj, role="user")

    # Debug: log the message shape right before starting the worker
    try:
        logger.debug("Final message type: %s", type(final_message))
        logger.debug("Final message.content type: %s", type(final_message.content))
        logger.debug("Final message.parts type: %s", type(final_message.parts))
        logger.debug("Sample parts: %s", final_message.parts[:3])
    except Exception as _:
        logger.exception("Error logging final_message details")

    # Ensure the session exists before launching the worker (Runner expects an existing session)
    try:
        # session_service methods are async; run them synchronously here
        existing_session = asyncio.run(chat_session_service.get_session(app_name=runner.app_name, user_id=user_id, session_id=session_id))
    except Exception:
        existing_session = None

    if not existing_session:
        try:
            asyncio.run(chat_session_service.create_session(app_name=runner.app_name, user_id=user_id, session_id=session_id))
        except Exception as e:
            logger.exception("Failed to create chat session %s: %s", session_id, e)

    q: Queue = Queue()
    thread = threading.Thread(target=async_worker, args=(q, user_id, session_id, final_message), daemon=True)
    thread.start()

    def event_stream():
        while True:
            item = q.get()
            if item is None:
                break
            # SSE data event
            try:
                yield f"data: {json.dumps(item)}\n\n"
            except Exception:
                yield f"data: {json.dumps({'type':'error','text':'serialization error'})}\n\n"
        # final event
        yield 'event: done\\n\\n'

    return Response(event_stream(), mimetype='text/event-stream')


# Static files for frontend
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory(os.path.join(os.path.dirname(__file__), 'static'), filename)


def open_browser():
    url = 'http://127.0.0.1:5000/'
    try:
        webbrowser.open_new_tab(url)
    except Exception:
        print(f"Open your browser at: {url}")


if __name__ == '__main__':
    # Open browser after slight delay to allow server to start
    threading.Timer(1.0, open_browser).start()
    app.run(host='127.0.0.1', port=5000, debug=False)
