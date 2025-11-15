import os
from dotenv import load_dotenv
import google.generativeai as genai
from google.adk.agents import LlmAgent
from google.adk.apps.app import App, EventsCompactionConfig
from google.adk.runners import Runner

# Import our custom services and tools
from services.session_service import TinyDBSessionService
from services.knowledge_service import KnowledgeService
from tools.document_tools import create_document_tools
from tools.github_tool import create_github_tools

# --- 1. Configure genai (for tools) ---
# Load .env from project root so developers don't need to set env every time
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)
gemini_key = os.environ.get("GEMINI_API_KEY")
if not gemini_key:
    print("FATAL ERROR: GEMINI_API_KEY not found in environment.")
    print("Please create a .env file in the project root with GEMINI_API_KEY=<your_key>")
    exit(1)

genai.configure(api_key=gemini_key)

# --- 2. Initialize Services ---
chat_session_service = TinyDBSessionService("chat_history_db.json")
knowledge_service = KnowledgeService("knowledge_db.json")

# --- 3. Create Tools ---
document_tools = create_document_tools(knowledge_service)
github_tools = create_github_tools()
all_tools = document_tools + github_tools

# --- 4. Define Agent Instruction ---
SYSTEM_INSTRUCTION = """
You are a professional assistant whose primary job is to write job application emails and cover letters
based on the user's resume(s) and public GitHub profile. When a user asks for an email or cover letter,
consult the stored resume summaries and the user's GitHub profile to craft a tailored, concise, and relevant message.

Priority rules (do not override):
- If the user's prompt contains the job posting text or includes a job posting file in the same message,
    do not ask the user for the job description — use the provided job posting immediately.
- If no job posting or job details are provided, ask a concise follow-up question only if critical facts are missing
    (for example: the target role or company). Otherwise, generate a reasonable sample job description and proceed.
- When producing emails or cover letters: output plain text only. Do not include Markdown, fenced code,
    bullet lists with Markdown markup, or any markdown-specific formatting. Format the document as a
    professional business email or a plain one-page cover letter.

Tone rules:
- For emails and cover letters: use a business-professional tone. Be concise, confident, and polite.
- For conversational interactions with the user (clarifying questions, guidance, or casual chat): adopt
    a friendly and slightly playful tone — keep it enjoyable while remaining professional.

Knowledge sources and required tools:
1. STATIC KNOWLEDGE (Resumes): Use `query_knowledge_base_tool` every time you need facts about the
     user's past roles, skills, or education.
2. PUBLIC GITHUB PROFILE (Dynamic): Use `github_profile_tool` to obtain the user's public projects,
     languages, and recent activity. Incorporate this information to highlight recent projects, popular
     languages, or relevant repositories in cover letters and emails.
3. USER-PROVIDED FILES: If the user uploads a job posting or other file as part of their prompt,
     read and use that file in addition to the resume and GitHub data.

Workflow (summary):
- If asked to ingest resumes, call `process_static_resumes_tool`.
- If asked to write an email/cover letter:
    1. Use any job posting text/file included in the user's message. If none is present, call `query_knowledge_base_tool`
         and `github_profile_tool` and generate a sample job description only if necessary.
    2. Call `query_knowledge_base_tool` for resume details.
    3. Call `github_profile_tool` to gather public project and language signals.
    4. Combine all sources and produce a tailored email and cover letter that emphasizes the user's
         most relevant skills, recent projects, and achievements.

When including GitHub info, summarize the top repos (name, stars, primary language) and use plain language
(do not paste raw JSON unless explicitly asked). Keep emails to a professional length (subject + 3-6 short
paragraphs for emails; one page max for cover letters).
"""

# --- 5. Create the Agent ---
agent = LlmAgent(
    model="gemini-2.0-flash",
    name="document_agent",
    instruction=SYSTEM_INSTRUCTION,
    tools=all_tools
)

# --- 6. Configure Context Compaction (for chat history) ---
compaction_config = EventsCompactionConfig(
    compaction_interval=20,
    overlap_size=1
)

# --- 7. Create the App ---
app = App(
    name="document_app",
    root_agent=agent,
    events_compaction_config=compaction_config
)

# --- 8. Create the Runner ---
runner = Runner(
    agent=agent,
    app_name="document_app",
    session_service=chat_session_service
)