import os
import asyncio
import google.generativeai as genai
from services.knowledge_service import KnowledgeService

# This model is for the *tool itself* to use for summarization
summarization_model = genai.GenerativeModel("gemini-2.0-flash")


def create_document_tools(knowledge_service: KnowledgeService, resumes_dir: str = None):
    """
    Factory function to create tool closures with access to the
    knowledge service. Returns a list of async tool callables in the
    following order: [process_single_resume_tool, process_static_resumes_tool, query_knowledge_base_tool]
    """

    # Resolve the resumes directory: prefer explicit argument, otherwise
    # default to a 'resumes' folder at the project root (two levels up).
    if resumes_dir is None:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        resumes_dir = os.path.join(project_root, 'resumes')

    async def process_static_resumes_tool() -> str:
        """
        Processes all PDF and image files in the configured 'resumes'
        folder. It uploads each file to be summarized, then saves the
        summary to the TinyDB knowledge base.
        """
        print(f"Tool called: process_static_resumes_tool on '{resumes_dir}'")
        try:
            # Check if directory exists
            if not os.path.isdir(resumes_dir):
                return f"Error: The directory '{resumes_dir}' does not exist."

            files = os.listdir(resumes_dir)
            if not files:
                return f"No files found in '{resumes_dir}' to process."

            processed_count = 0

            for file_name in files:
                file_path = os.path.join(resumes_dir, file_name)

                # Determine file type and prompt
                prompt = ""
                source_type = "unknown"
                if file_name.lower().endswith(".pdf"):
                    prompt = "Summarize this resume. Extract key skills, all work experience (company, role, dates), and education."
                    source_type = "Resume (PDF)"
                elif file_name.lower().endswith((".jpg", ".jpeg", ".png")):
                    prompt = "Describe this image in detail."
                    source_type = "Image"
                else:
                    continue  # Skip unsupported files

                print(f"Tool: Processing {file_name}...")

                # Skip if already processed
                if knowledge_service.has_summary(file_name):
                    print(f"Skipping {file_name}: already processed")
                    continue

                # 1. Upload file as a "Prompt Artifact"
                uploaded_file = genai.upload_file(path=file_path)

                # 2. Call the model to get the summary
                response = await summarization_model.generate_content_async(
                    [uploaded_file, prompt],
                    stream=False
                )

                # 3. Save summary to our knowledge DB
                knowledge_service.save_summary(
                    file_name=file_name,
                    summary=getattr(response, 'text', str(response)),
                    source_type=source_type
                )

                # 4. Clean up the uploaded file
                try:
                    genai.delete_file(uploaded_file.name)
                except Exception:
                    # Non-fatal: log and continue
                    pass
                # Move processed file to a 'processed' subfolder to avoid
                # accidental re-processing on future runs.
                try:
                    processed_dir = os.path.join(resumes_dir, 'processed')
                    os.makedirs(processed_dir, exist_ok=True)
                    target_path = os.path.join(processed_dir, file_name)
                    os.replace(file_path, target_path)
                except Exception:
                    # Non-fatal: if move fails, keep file in place
                    pass
                processed_count += 1

            if processed_count == 0:
                return "No new supported files (PDF/Image) found in the 'resumes' folder."

            return f"Successfully processed and saved summaries for {processed_count} files."

        except FileNotFoundError:
            return f"Error: The folder '{resumes_dir}' was not found."
        except Exception as e:
            print(f"Error in tool: {e}")
            return f"An error occurred: {str(e)}"


    async def query_knowledge_base_tool() -> str:
        """
        Retrieves all file summaries (resumes, etc.) from the
        TinyDB knowledge base. The agent can then use this
        information to answer questions.
        """
        print("Tool called: query_knowledge_base_tool")
        return knowledge_service.get_all_summaries()


    async def process_single_resume_tool(file_path: str) -> str:
        """
        Process a single resume file (absolute path). This is intended to be
        used by upload handlers so only the newly uploaded file is processed.
        """
        try:
            if not os.path.isfile(file_path):
                return f"Error: file '{file_path}' does not exist."

            file_name = os.path.basename(file_path)
            # Skip processing if we already have a summary for this file
            if knowledge_service.has_summary(file_name):
                return f"Skipped: '{file_name}' already processed."

            # Determine prompt and type
            prompt = ""
            source_type = "unknown"
            if file_name.lower().endswith(".pdf"):
                prompt = "Summarize this resume. Extract Name, key skills, all work experience (company, role, dates), and education."
                source_type = "Resume (PDF)"
            elif file_name.lower().endswith(('.jpg', '.jpeg', '.png')):
                prompt = "Describe this image in detail."
                source_type = "Image"
            else:
                return f"Skipped: unsupported file type for '{file_name}'."

            uploaded_file = genai.upload_file(path=file_path)
            response = await summarization_model.generate_content_async([uploaded_file, prompt], stream=False)
            knowledge_service.save_summary(file_name=file_name, summary=getattr(response, 'text', str(response)), source_type=source_type)
            try:
                genai.delete_file(uploaded_file.name)
            except Exception:
                pass
            # Move processed file into a sibling 'processed' folder to avoid re-processing
            try:
                processed_dir = os.path.join(os.path.dirname(file_path), 'processed')
                os.makedirs(processed_dir, exist_ok=True)
                target_path = os.path.join(processed_dir, file_name)
                os.replace(file_path, target_path)
            except Exception:
                pass
            return f"Processed: {file_name}"
        except Exception as e:
            return f"Error processing '{file_path}': {e}"


    def process_single_resume_sync(file_path: str) -> str:
        """Synchronous wrapper that runs the async processing in a fresh
        event loop and creates a local model bound to that loop to avoid
        cross-loop Future attachment errors."""
        async def _inner():
            try:
                if not os.path.isfile(file_path):
                    return f"Error: file '{file_path}' does not exist."

                file_name = os.path.basename(file_path)
                if knowledge_service.has_summary(file_name):
                    return f"Skipped: '{file_name}' already processed."

                # determine prompt
                prompt = ""
                source_type = "unknown"
                if file_name.lower().endswith('.pdf'):
                    prompt = "Summarize this resume. Extract Name, key skills, all work experience (company, role, dates), and education."
                    source_type = "Resume (PDF)"
                elif file_name.lower().endswith(('.jpg', '.jpeg', '.png')):
                    prompt = "Describe this image in detail."
                    source_type = "Image"
                else:
                    return f"Skipped: unsupported file type for '{file_name}'."

                # Upload file (sync)
                uploaded_file = genai.upload_file(path=file_path)

                # Create a local model bound to this loop and call async API
                local_model = genai.GenerativeModel("gemini-2.0-flash")
                response = await local_model.generate_content_async([uploaded_file, prompt], stream=False)

                knowledge_service.save_summary(file_name=file_name, summary=getattr(response, 'text', str(response)), source_type=source_type)
                try:
                    genai.delete_file(uploaded_file.name)
                except Exception:
                    pass

                try:
                    processed_dir = os.path.join(os.path.dirname(file_path), 'processed')
                    os.makedirs(processed_dir, exist_ok=True)
                    target_path = os.path.join(processed_dir, file_name)
                    os.replace(file_path, target_path)
                except Exception:
                    pass

                return f"Processed: {file_name}"
            except Exception as e:
                return f"Error processing '{file_path}': {e}"

        # Run the coroutine in a fresh event loop for this thread
        try:
            return asyncio.run(_inner())
        except Exception as e:
            return f"Error running processing loop: {e}"


    # Return the list of raw functions. The first entry is a synchronous
    # single-file processor (useful for callers that want to call it from
    # a thread without managing event loops).
    return [process_single_resume_sync, process_single_resume_tool, process_static_resumes_tool, query_knowledge_base_tool]