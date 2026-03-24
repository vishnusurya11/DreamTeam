"""Web scraping tool — fetch and extract text content from URLs."""

import urllib.request
import urllib.error
import re
from langchain_core.tools import tool

# Roles that can use these tools
ROLES = ["planner", "builder", "qa"]


@tool
def fetch_webpage(url: str, max_chars: int = 5000) -> str:
    """Fetch a webpage and extract its text content.

    Args:
        url: The URL to fetch
        max_chars: Maximum characters to return (default 5000)
    """
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (DreamTeam Agent)"
        })
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode("utf-8", errors="replace")

        # Strip HTML tags
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        # Decode HTML entities
        text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&quot;', '"').replace('&#39;', "'")

        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n[...truncated]"

        return text if text else "Page returned no text content."
    except urllib.error.HTTPError as e:
        return f"HTTP Error {e.code}: {e.reason}"
    except urllib.error.URLError as e:
        return f"URL Error: {e.reason}"
    except Exception as e:
        return f"Error fetching page: {e}"


TOOLS = [fetch_webpage]
