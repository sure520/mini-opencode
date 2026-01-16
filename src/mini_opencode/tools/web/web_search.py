import json
import warnings

from mini_opencode.config import get_config_section

# Suppress warnings from langchain_tavily regarding Pydantic field shadowing
warnings.filterwarnings("ignore", category=UserWarning, module="langchain_tavily")
from langchain_tavily import TavilySearch  # noqa: E402

web_search = TavilySearch(
    name="web_search",
    max_results=5,
    tavily_api_key=get_config_section(
        ["tools", "configs", "web_search", "tavily_api_key"]
    ),
)

if __name__ == "__main__":
    print(json.dumps(web_search.invoke("NBA Finals"), ensure_ascii=False, indent=4))
