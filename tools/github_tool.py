"""Simple GitHub profile tool for the document agent.

Reads `GITHUB_USERNAME` (required) and `GITHUB_TOKEN` (optional) from
environment variables and returns a short summary of the user's public
profile and repositories suitable for an LLM to reason about the
candidate's public technical footprint.

This tool is intentionally lightweight (uses `requests` via
`asyncio.to_thread`) so it works in environments where `aiohttp` may be
problematic.
"""
import os
import asyncio
from typing import Any, Dict


def make_github_profile_tool(provided_username: str = None, provided_token: str = None):
    """Factory that returns an async tool function using the provided
    username/token or falling back to environment variables.
    """

    async def github_profile_tool() -> str:
        """Fetch GitHub profile and repos and return a human-friendly summary.

        Returns a string that the agent can consume. If username is not set,
        returns an error message instructing the user how to provide it.
        """
        username = provided_username or os.getenv("GITHUB_USERNAME")
        if not username:
            return "Error: GITHUB_USERNAME not set. Set `GITHUB_USERNAME` in .env or export it before starting the app."

        token = provided_token or os.getenv("GITHUB_TOKEN")
        headers = {
            "Accept": "application/vnd.github+json"
        }
        if token:
            headers["Authorization"] = f"token {token}"

        def fetch() -> Dict[str, Any]:
            import requests

            base = "https://api.github.com"
            timeout = 10

            user_resp = requests.get(f"{base}/users/{username}", headers=headers, timeout=timeout)
            if user_resp.status_code != 200:
                return {"error": f"Failed to fetch user: {user_resp.status_code} {user_resp.text}"}
            user = user_resp.json()

            repos_resp = requests.get(f"{base}/users/{username}/repos?per_page=100", headers=headers, timeout=timeout)
            if repos_resp.status_code != 200:
                return {"error": f"Failed to fetch repos: {repos_resp.status_code} {repos_resp.text}"}
            repos = repos_resp.json()

            # Aggregate simple stats
            total_stars = sum(r.get("stargazers_count", 0) for r in repos)
            top_repos = sorted(repos, key=lambda r: r.get("stargazers_count", 0), reverse=True)[:5]
            languages: Dict[str, int] = {}
            for r in repos:
                lang = r.get("language")
                if lang:
                    languages[lang] = languages.get(lang, 0) + 1

            recent = sorted(repos, key=lambda r: r.get("pushed_at") or r.get("updated_at", ""), reverse=True)[:3]

            return {
                "user": user,
                "repos": repos,
                "total_stars": total_stars,
                "top_repos": top_repos,
                "languages": languages,
                "recent": recent,
            }

        result = await asyncio.to_thread(fetch)

        if isinstance(result, dict) and "error" in result:
            return result["error"]

        user = result["user"]
        lines = []
        lines.append(f"GitHub profile for {user.get('login')} ({user.get('name') or ''})")
        if user.get("bio"):
            lines.append(f"Bio: {user.get('bio')}")
        lines.append(f"Public repos: {user.get('public_repos')} | Followers: {user.get('followers')} | Following: {user.get('following')}")
        lines.append(f"Total stars across fetched repos: {result['total_stars']}")

        lines.append("Top repos by stars:")
        for r in result["top_repos"]:
            lines.append(f"- {r['name']}: {r.get('stargazers_count',0)} stars | {r.get('language') or 'unknown'} | {r.get('html_url')}")

        lang_items = sorted(result["languages"].items(), key=lambda kv: kv[1], reverse=True)
        if lang_items:
            lines.append("Languages used (by repo count): " + ", ".join(f"{k}({v})" for k, v in lang_items[:8]))

        lines.append("Recently updated repos:")
        for r in result["recent"]:
            lines.append(f"- {r['name']}: pushed_at {r.get('pushed_at') or r.get('updated_at')}")

        lines.append("\n(End of GitHub summary)")

        return "\n".join(lines)

    return github_profile_tool


# If someone wants a factory to plug into the agent, return a list
# with our single tool.

def create_github_tools(username: str = None, token: str = None):
    """Return a list of tool callables suitable for registration with the agent.

    If `username` or `token` are provided, they will be used instead of
    reading environment variables at runtime. This helps ensure the agent
    uses the values loaded from `.env` at startup.
    """
    return [make_github_profile_tool(provided_username=username, provided_token=token)]
