"""
Enhanced web research tools with SerpAPI integration.
Falls back to AI-based research if SerpAPI is not configured.
"""
import os
import asyncio
import aiohttp
import json # Added json import
from typing import List, Dict, Any, Optional
# from serpapi import GoogleSearch # Removed SerpAPI
from bs4 import BeautifulSoup # Will be removed if Jina provides title, or kept for fallback
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class WebResearchTool:
    """Enhanced web research tool using Jina Reader API."""
    
    def __init__(self):
        self.jina_api_key = os.getenv("JINA_API_KEY")
        self.use_jina_reader = bool(self.jina_api_key)
        if not self.use_jina_reader:
            print("Jina API key not found. Web research via Jina Reader will be disabled.")

    async def search_web(self, query: str, num_results: int = 10) -> List[Dict[str, Any]]:
        """Search the web using Jina Reader API."""
        if not self.use_jina_reader or not self.jina_api_key:
            return []

        search_url = "https://s.jina.ai/search"
        # Jina's search 'num_results' might be 'limit' or implicitly handled by results length.
        # For now, we request `num_results` and Jina might cap it. Max is typically around 20.
        params = {"q": query, "num": str(min(num_results, 20))}
        headers = {
            "Authorization": f"Bearer {self.jina_api_key}",
            "Accept": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, params=params, headers=headers, timeout=20) as response:
                    if response.status == 200:
                        response_json = await response.json()
                        # Assuming 'data' contains the list of results directly or as a JSON string
                        data_field = response_json.get('data')
                        if isinstance(data_field, str):
                            results_data = json.loads(data_field)
                        elif isinstance(data_field, list):
                            results_data = data_field
                        else:
                            results_data = []

                        formatted_results = []
                        for result in results_data:
                            # Adapt to Jina's result structure
                            # Common keys might be 'title', 'url'/'link', 'description'/'snippet'
                            formatted_results.append({
                                "title": result.get("title", ""),
                                "url": result.get("url", result.get("link", "")),
                                "snippet": result.get("snippet", result.get("description", "")),
                            })
                        return formatted_results
                    else:
                        print(f"Error searching with Jina Reader API: HTTP {response.status} - {await response.text()}")
                        return []
        except Exception as e:
            print(f"Error searching with Jina Reader API: {e}")
            return []

    async def scrape_content(self, url: str) -> Dict[str, Any]:
        """Scrape content from a URL using Jina Reader API."""
        if not self.use_jina_reader or not self.jina_api_key:
            return {"url": url, "content": "", "title": "", "success": False, "error": "Jina Reader not configured"}

        reader_url = f"https://r.jina.ai/{url}" # Jina URL format
        headers = {
            "Authorization": f"Bearer {self.jina_api_key}",
            "Accept": "application/json", # Expecting JSON envelope
            "X-Respond-With": "markdown", # Requesting markdown content
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(reader_url, headers=headers, timeout=30) as response:
                    if response.status == 200:
                        response_json = await response.json()
                        # Retrieve raw data and ensure content_for_return is a string
                        raw_data_from_jina = response_json.get("data", "")
                        content_for_return = raw_data_from_jina if isinstance(raw_data_from_jina, str) else json.dumps(raw_data_from_jina)

                        # Title extraction logic
                        title = response_json.get("meta", {}).get("title", "")
                        if not title and isinstance(raw_data_from_jina, str) and raw_data_from_jina:
                            lines = raw_data_from_jina.split('\n')
                            if lines and lines[0].startswith("# "):
                                title = lines[0][2:]
                        elif not isinstance(raw_data_from_jina, str):
                            # Optional: Log that raw_data_from_jina was not a string
                            print(f"Jina Reader returned non-string data for URL {url}: {type(raw_data_from_jina)}")

                        return {
                            "url": url,
                            "content": content_for_return, # Use the stringified version
                            "title": title,
                            "success": True,
                        }
                    else:
                        error_text = await response.text()
                        print(f"Error scraping with Jina Reader API: HTTP {response.status} - {error_text}")
                        return {"url": url, "content": "", "title": "", "success": False, "error": f"HTTP {response.status} - {error_text}"}
        except Exception as e:
            print(f"Error scraping with Jina Reader API: {e}")
            return {"url": url, "content": "", "title": "", "success": False, "error": str(e)}

    async def research_query(self, query: str, max_sources: int = 5) -> Dict[str, Any]:
        """Perform comprehensive research on a query using Jina Reader API."""
        if not self.use_jina_reader:
            return {
                "query": query,
                "sources": [],
                "summary": "Jina Reader not configured. AI-based research fallback might be affected.", # Updated summary
                "jina_reader_enabled": False # Changed from serpapi_enabled
            }
        
        # Search for relevant URLs
        # search_web now returns Jina results, which should be List[Dict[str, Any]]
        search_results = await self.search_web(query, num_results=max_sources * 2) # Added await
        
        if not search_results:
            return {
                "query": query,
                "sources": [],
                "summary": "No search results found for the query.",
                "jina_reader_enabled": True # Changed from serpapi_enabled
            }
        
        # Scrape content from top results
        # scrape_content now uses Jina and is async
        scraping_tasks = []
        for result in search_results[:max_sources]: # Assuming search_results is the list from Jina
            if result.get("url"): # Ensure URL exists
                scraping_tasks.append(self.scrape_content(result["url"]))
        
        scraped_contents = await asyncio.gather(*scraping_tasks, return_exceptions=True)
        
        # Combine search results with scraped content
        sources = []
        for i, result in enumerate(search_results[:max_sources]):
            scraped = scraped_contents[i] if i < len(scraped_contents) and not isinstance(scraped_contents[i], Exception) else {}
            sources.append({
                "title": result["title"],
                "url": result["url"],
                "snippet": result["snippet"],
                "content": scraped.get("content", "")[:2000] if isinstance(scraped, dict) else "",  # Limit content
                "scraped_successfully": scraped.get("success", False) if isinstance(scraped, dict) else False
            })
        
        return {
            "query": query,
            "sources": sources,
            "total_sources": len(sources),
            "successful_scrapes": sum(1 for s in sources if s["scraped_successfully"]),
            "jina_reader_enabled": True # Changed from serpapi_enabled
        }


# Initialize the research tool
research_tool = WebResearchTool()


async def enhance_ai_research_with_real_data(query: str, ai_generated_content: str) -> Dict[str, Any]:
    """
    Enhance AI-generated research with real web data using Jina Reader API.
    This function can be called to augment existing AI research.
    """
    if not research_tool.use_jina_reader:
        return {
            "enhanced_content": ai_generated_content,
            "sources": [],
            "enhancement_type": "ai_only"
        }
    
    try:
        # research_query is already async
        research_result = await research_tool.research_query(query, max_sources=3)
        
        if research_result.get("sources"): # Added .get for safety
            # Combine AI content with real sources
            source_summaries = []
            for source in research_result["sources"]:
                if source["content"]:
                    source_summaries.append(f"**{source['title']}**: {source['snippet']}")
            
            enhanced_content = ai_generated_content
            if source_summaries:
                enhanced_content += "\n\n**Additional Sources Found:**\n" + "\n".join(source_summaries)
            
            return {
                "enhanced_content": enhanced_content,
                "sources": research_result["sources"],
                "enhancement_type": "ai_plus_web"
            }
    except Exception as e:
        print(f"Error enhancing research: {e}")
    
    return {
        "enhanced_content": ai_generated_content,
        "sources": [],
        "enhancement_type": "ai_only"
    }
