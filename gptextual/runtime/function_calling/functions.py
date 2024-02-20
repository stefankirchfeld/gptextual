from __future__ import annotations

import httpx

from .function_call_support import (
    register_for_function_calling,
    get_function_config,
)


def _process_search_results(result_json):
    # Initialize an empty list to hold the results
    results = []

    # Get the items from the result JSON
    items = result_json.get("items", [])

    # Loop through the top 3 items
    for i, item in enumerate(items[:10]):
        # Prepare the result dictionary
        result = f"Title: {item.get('title')}|URL: {item.get('link')}|Snippet: {item.get('snippet')}"

        # Append the result to the list
        results.append(result)

    return "\n".join(results)


@register_for_function_calling
async def google_web_search(query: str) -> str:
    """
    Executes a Google search with the specified search string and returns the top 10 search results.
    For each result, a title, URL and preview snippet is returned.

    Args:
        query: the query string
    """
    config = get_function_config(google_web_search)
    api_key, cx_id = None, None
    if config:
        api_key = config.get("api_key", None)
        cx_id = config.get("cx_id", None)

    if api_key is None or cx_id is None:
        return "This tool is not configured correctly and cannot be used at this time. Please try to continue without it or let the user know."

    url = "https://www.googleapis.com/customsearch/v1"

    params = {"key": api_key, "cx": cx_id, "q": query}

    resp = None
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=5)

    resp.raise_for_status()  # Raises an exception if the HTTP status is 400 or higher
    result_json = resp.json()  # Get the response body as JSON

    return _process_search_results(result_json)
