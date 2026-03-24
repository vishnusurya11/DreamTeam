"""Web search tool using DuckDuckGo — no API key required."""

from langchain_core.tools import tool

# Roles that can use these tools
ROLES = ["planner", "builder", "qa", "reviewer"]


@tool
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web using DuckDuckGo and return results.

    Args:
        query: The search query string
        max_results: Maximum number of results to return (default 5)
    """
    try:
        from ddgs import DDGS
    except ImportError:
        return "Error: ddgs package not installed. Run: pip install ddgs"

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=min(max_results, 10)))

        if not results:
            return f"No results found for: {query}"

        output = []
        for i, r in enumerate(results, 1):
            output.append(f"[{i}] {r.get('title', 'No title')}")
            output.append(f"    URL: {r.get('href', 'N/A')}")
            output.append(f"    {r.get('body', 'No description')}")
            output.append("")

        return "\n".join(output)
    except Exception as e:
        return f"Search error: {e}"


@tool
def web_search_news(query: str, max_results: int = 5) -> str:
    """Search for recent news articles using DuckDuckGo.

    Args:
        query: The news search query
        max_results: Maximum number of results (default 5)
    """
    try:
        from ddgs import DDGS
    except ImportError:
        return "Error: ddgs package not installed."

    try:
        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=min(max_results, 10)))

        if not results:
            return f"No news found for: {query}"

        output = []
        for i, r in enumerate(results, 1):
            output.append(f"[{i}] {r.get('title', 'No title')}")
            output.append(f"    Source: {r.get('source', 'N/A')} | {r.get('date', 'N/A')}")
            output.append(f"    URL: {r.get('url', 'N/A')}")
            output.append(f"    {r.get('body', 'No description')}")
            output.append("")

        return "\n".join(output)
    except Exception as e:
        return f"News search error: {e}"


# Export tools list for auto-discovery
TOOLS = [web_search, web_search_news]
