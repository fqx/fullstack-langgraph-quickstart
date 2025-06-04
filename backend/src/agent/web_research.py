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
        """Search the web using Jina Search API."""
        if not self.use_jina_reader or not self.jina_api_key:
            return []

        # Use Jina's search endpoint with proper URL format and gl=US parameter
        search_url = f"https://s.jina.ai/{query}?gl=US"
        headers = {
            "Authorization": f"Bearer {self.jina_api_key}",
            "Accept": "application/json",
            "X-Return-Format": "json"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(search_url, headers=headers, timeout=20) as response:
                    if response.status == 200:
                        # Jina returns plain text by default, we need to parse it
                        content = await response.text()

                        # Try to parse as JSON first
                        try:
                            response_json = json.loads(content)
                            if isinstance(response_json, dict) and 'data' in response_json:
                                results_data = response_json['data']
                            else:
                                results_data = response_json if isinstance(response_json, list) else []
                        except json.JSONDecodeError:
                            # If not JSON, parse the text response manually
                            results_data = self._parse_search_text(content, num_results)

                        return results_data[:num_results]
                    else:
                        error_text = await response.text()
                        print(f"Error searching with Jina API: HTTP {response.status} - {error_text}")
                        return []
        except Exception as e:
            print(f"Error searching with Jina API: {e}")
            return []

    def _parse_search_text(self, content: str, max_results: int) -> List[Dict[str, Any]]:
        """Parse Jina search text response into structured data."""
        results = []
        lines = content.strip().split('\n')

        current_result = {}
        for line in lines:
            line = line.strip()
            if not line:
                if current_result and len(results) < max_results:
                    results.append(current_result)
                    current_result = {}
                continue

            # Look for title (usually starts with ##)
            if line.startswith('##') or line.startswith('#'):
                current_result['title'] = line.lstrip('#').strip()
            # Look for URL (contains http)
            elif 'http' in line and not current_result.get('url'):
                # Extract URL from the line
                import re
                url_match = re.search(r'https?://[^\s]+', line)
                if url_match:
                    current_result['url'] = url_match.group()
            # Everything else is likely snippet/description
            elif not line.startswith('http') and len(line) > 20:
                if 'snippet' not in current_result:
                    current_result['snippet'] = line
                else:
                    current_result['snippet'] += ' ' + line

        # Add the last result if exists
        if current_result and len(results) < max_results:
            results.append(current_result)

        # Ensure all results have required fields with safe defaults
        for result in results:
            result.setdefault('title', 'No title')
            result.setdefault('url', '')
            result.setdefault('snippet', 'No description available')

        return results



    async def scrape_content(self, url: str) -> Dict[str, Any]:
        """Scrape content from a URL using Jina Reader API."""
        if not self.use_jina_reader or not self.jina_api_key:
            return {"url": url, "content": "", "title": "", "success": False, "error": "Jina Reader not configured"}

        # Use Jina's reader endpoint with proper URL format
        reader_url = f"https://r.jina.ai/{url}"
        headers = {
            "Authorization": f"Bearer {self.jina_api_key}",
            "Accept": "application/json",
            "X-Return-Format": "markdown"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(reader_url, headers=headers, timeout=30) as response:
                    if response.status == 200:
                        content = await response.text()

                        # Try to parse as JSON first
                        try:
                            response_json = json.loads(content)
                            if isinstance(response_json, dict):
                                # Extract content from JSON response
                                content_data = response_json.get("data", content)
                                title = response_json.get("title", "")

                                # If data is still JSON, extract further
                                if isinstance(content_data, dict):
                                    content_for_return = content_data.get("content", str(content_data))
                                    if not title:
                                        title = content_data.get("title", "")
                                else:
                                    content_for_return = str(content_data)
                            else:
                                content_for_return = content
                                title = ""
                        except json.JSONDecodeError:
                            # If not JSON, use the raw content
                            content_for_return = content
                            title = ""

                        # Extract title from markdown if not found
                        if not title and content_for_return:
                            lines = content_for_return.split('\n')
                            for line in lines:
                                line = line.strip()
                                if line.startswith('# '):
                                    title = line[2:].strip()
                                    break
                                elif line and not line.startswith('#') and len(line) > 10:
                                    # Use first substantial line as title if no h1 found
                                    title = line[:100] + "..." if len(line) > 100 else line
                                    break

                        return {
                            "url": url,
                            "content": content_for_return,
                            "title": title or "Untitled",
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
                "summary": "Jina Reader not configured. AI-based research fallback might be affected.",
                "jina_reader_enabled": False
            }

        # Search for relevant URLs
        search_results = await self.search_web(query, num_results=max_sources * 2)

        if not search_results:
            return {
                "query": query,
                "sources": [],
                "summary": "No search results found for the query.",
                "jina_reader_enabled": True
            }

        # Scrape content from top results
        scraping_tasks = []
        for result in search_results[:max_sources]:
            if result.get("url"):
                scraping_tasks.append(self.scrape_content(result["url"]))

        scraped_contents = await asyncio.gather(*scraping_tasks, return_exceptions=True)

        # Combine search results with scraped content - with safe key access
        sources = []
        for i, result in enumerate(search_results[:max_sources]):
            scraped = scraped_contents[i] if i < len(scraped_contents) and not isinstance(scraped_contents[i], Exception) else {}
            sources.append({
                "title": result.get("title", "No title"),
                "url": result.get("url", ""),
                "snippet": result.get("snippet", "No description available"),
                "content": scraped.get("content", "")[:2000] if isinstance(scraped, dict) else "",
                "scraped_successfully": scraped.get("success", False) if isinstance(scraped, dict) else False
            })

        return {
            "query": query,
            "sources": sources,
            "total_sources": len(sources),
            "successful_scrapes": sum(1 for s in sources if s["scraped_successfully"]),
            "jina_reader_enabled": True
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
        research_result = await research_tool.research_query(query, max_sources=3)

        if research_result.get("sources"):
            # Combine AI content with real sources - using safe key access
            source_summaries = []
            for source in research_result["sources"]:
                title = source.get("title", "Untitled")
                snippet = source.get("snippet", "No description")
                if source.get("content"):
                    source_summaries.append(f"**{title}**: {snippet}")

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

