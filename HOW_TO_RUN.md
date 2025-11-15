How to run the Document Agent (detailed)

Follow these steps to configure your environment, run the web UI, upload and process resumes, and ask the agent to generate emails and cover letters.

1) Create a virtual environment & install dependencies

PowerShell (from the project root):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

2) Configure environment variables

You can create a `.env` file in the project root or set these variables in your PowerShell session.

Required variables:
- `GITHUB_USERNAME` — your GitHub username (used by the GitHub tool)
- `GITHUB_TOKEN` — optional but recommended: a GitHub Personal Access Token (PAT) for higher rate limits or private repo access
- `GEMINI_API_KEY` — your Google Generative AI (Gemini) API key

Example `.env` (project root):

```text
GITHUB_USERNAME=your-github-username
GITHUB_TOKEN=ghp_...YOUR_TOKEN...
GEMINI_API_KEY=AIzaSy...YOUR_KEY...
```

Or set temporarily in PowerShell for the session:

```powershell
#$env:GITHUB_USERNAME = 'your-github-username'
#$env:GITHUB_TOKEN = 'ghp_...YOUR_TOKEN...'
#$env:GEMINI_API_KEY = 'AIzaSy...YOUR_KEY...'
```

Where to get tokens / keys
- GitHub Personal Access Token (PAT):
  - Docs & create page: https://github.com/settings/personal-access-tokens/new
  - Summary: Sign in → Settings → Developer settings → Personal access tokens → Generate new token. For read-only access to public repos choose minimal scopes (e.g., `contents:read`) and set an expiration.
- Google Generative AI / Gemini API key:
  - Create/choose a Google Cloud project at https://console.cloud.google.com/
  - Enable the Generative AI / Generative Language API for that project (search in the API Library)
  - Create an API key under APIs & Services → Credentials → Create Credentials → API key, then set `GEMINI_API_KEY` to that key. Restrict the key appropriately for security.

3) Launch the web UI

PowerShell (virtualenv active):

```powershell
# From repository root
python flask\app.py
```

Open `http://127.0.0.1:5000/` in your browser if it doesn't open automatically.

4) Recommended UI flow (upload → process → generate)

- Upload a resume first: click the "Upload Resume" button in the sidebar and choose your resume (PDF, image, or supported text formats). The file is saved to `resumes/`.
- Process the uploaded resumes: in the chat composer send the message:

  `Process my resumes`

  This triggers the `process_static_resumes_tool` which summarizes files in `resumes/` and saves summaries to the knowledge DB. Wait for a confirmation message from the agent that processing completed.
- Provide the job description: either paste the job posting text into the composer or upload the job posting file (use the attach button). If uploading, reference it in your message using the file token the UI shows, for example:

  `Write a cover letter for this job [file:user_upload/job_posting.pdf]`

- Ask the agent to generate materials: example prompt after processing and providing the job posting:

  `Please write a professional plain-text application email (subject + 3 short paragraphs) and a one-page cover letter tailored to the attached job posting. Highlight my most relevant projects and skills from the processed resume.`

5) Example quick flow (user inputs in the UI)

- Upload resume via "Upload Resume" → then type: `Process my resumes`
- Upload or paste job posting → then type: `Please draft a plain-text application email and a cover letter for the attached job posting.`

6) Troubleshooting & tips

- If GitHub returns authentication errors, ensure `GITHUB_TOKEN` is correct and has appropriate scopes.
- If the agent reports model or API errors, confirm `GEMINI_API_KEY` is valid, the Generative AI API is enabled for your Google Cloud project, and your account has access to the requested model.
- Check the terminal where you started `python flask\app.py` for server logs and tracebacks.

7) Security and cleanup

- Keep tokens secret and do not commit the `.env` file. Revoke long-lived tokens after testing.
- Use the web UI admin actions to clear the knowledge DB and remove resume files (the app truncates the TinyDB table and attempts to delete resume files where possible).

If you'd like, I can also add a screenshot showing the UI steps or automatically trigger resume processing on upload. Let me know which you'd prefer.

## Alternative: Run the CLI (`main.py`) instead of the web UI

If you prefer a command-line workflow or want to run the agent without the Flask web UI, you can use the provided `main.py` CLI. The CLI follows a similar flow (upload files, process resumes, ask for emails/cover letters) but runs interactively in your terminal.

Quick steps (PowerShell):

```powershell
# Activate your virtualenv (see section 1 above)
.\.venv\Scripts\Activate.ps1
# Ensure your environment variables are set (GEMINI_API_KEY required to upload/process files)
$env:GITHUB_USERNAME = 'your-github-username'
$env:GITHUB_TOKEN = 'ghp_...YOUR_TOKEN...'
$env:GEMINI_API_KEY = 'AIzaSy...YOUR_KEY...'

# Run the CLI
python main.py
```

CLI notes and usage
- `main.py` runs an interactive prompt. Example commands you can type at the prompt:
  - `Process my resumes` — finds files in `resumes/` and triggers the resume processing tool (same as the web UI tool).
  - `Write a cover letter for this job [file:path/to/job_posting.pdf]` — reference a job posting file using the `[file: ...]` token. If the path is a basename, `main.py` will search the workspace for a matching file.
  - `quit` — exit the CLI and persist the session.
- File uploads in the CLI: `main.py` can upload local files to the genai service when you reference them; ensure `GEMINI_API_KEY` is set and the file path exists. If you prefer, copy files into `user_upload/` or `resumes/` before running the CLI and reference them by basename.
- The CLI prints progress and final agent outputs to the terminal. It also persists sessions via the same TinyDB session store used by the Flask UI.

When to use the CLI vs Web UI
- Use the CLI for fast iterative testing, scripting, or when running in headless environments.
- Use the Web UI for an interactive, streaming chat experience with attachments and nicer streaming rendering.

If you'd like, I can also add a short example transcript from `main.py` to `HOW_TO_RUN.md` showing a sample interactive session.
