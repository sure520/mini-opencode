from firecrawl import FirecrawlApp
from langchain.tools import tool

from mini_opencode.config import get_config_section


@tool("web_crawl", parse_docstring=True)
def web_crawl_tool(url: str) -> str:
    """
    Crawl a website and return the markdown content.

    Args:
        url: The URL of the website to crawl.

    Returns:
        The markdown content of the website.
    """
    settings = get_config_section(["tools", "configs", "web_crawl"])
    if not settings:
        raise ValueError(
            "The `tools/configs/web_crawl` section in `config.yaml` is not found."
            "Please check your configuration file."
        )

    api_key = settings.get("api_key")
    if not api_key:
        raise ValueError(
            "The `api_key` is not specified in the `tools/configs/web_crawl` section."
        )

    firecrawl = FirecrawlApp(api_key=api_key)
    response = firecrawl.scrape(url=url, formats=["markdown"], only_main_content=True)
    return response.markdown
