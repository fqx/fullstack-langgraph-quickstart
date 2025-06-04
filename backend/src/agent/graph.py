import os
from agent.tools_and_schemas import SearchQueryList, Reflection
from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langgraph.types import Send
from langgraph.graph import StateGraph
from langgraph.graph import START, END
from langchain_core.runnables import RunnableConfig
from openai import AsyncOpenAI

from agent.state import (
    OverallState,
    QueryGenerationState,
    ReflectionState,
    WebSearchState,
)
from agent.configuration import Configuration
from agent.prompts import (
    get_current_date,
    query_writer_instructions,
    web_searcher_instructions,
    reflection_instructions,
    answer_instructions,
)
from agent.utils import (
    get_citations,
    get_research_topic,
    insert_citation_markers,
    resolve_urls,
)
from agent.web_research import enhance_ai_research_with_real_data

load_dotenv()

if os.getenv("OPENAI_API_KEY") is None:
    raise ValueError("OPENAI_API_KEY is not set")

# OpenAI client
openai_client = AsyncOpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
)


# Nodes
async def generate_query(state: OverallState, config: RunnableConfig) -> QueryGenerationState:
    """LangGraph node that generates a search queries based on the User's question using Azure OpenAI."""
    configurable = Configuration.from_runnable_config(config)
    if state.get("initial_search_query_count") is None:
        state["initial_search_query_count"] = configurable.number_of_initial_queries

    current_date = get_current_date()
    formatted_prompt = query_writer_instructions.format(
        current_date=current_date,
        research_topic=get_research_topic(state["messages"]),
        number_queries=state["initial_search_query_count"],
    )
    # Call Azure OpenAI o3 model for query generation
    completion = await openai_client.chat.completions.create(
        model=configurable.query_generator_model,
        messages=[{"role": "system", "content": formatted_prompt}],
        # temperature=1.0,
        # max_tokens=256,
    )
    # Parse output (assuming output is a JSON list of queries)
    import json
    try:
        queries = json.loads(completion.choices[0].message.content)
    except Exception:
        queries = [completion.choices[0].message.content]
    return {"query_list": queries}


def continue_to_web_research(state: QueryGenerationState):
    """LangGraph node that sends the search queries to the web research node.

    This is used to spawn n number of web research nodes, one for each search query.
    """
    return [
        Send("web_research", {"search_query": search_query, "id": int(idx)})
        for idx, search_query in enumerate(state["query_list"])
    ]


async def web_research(state: WebSearchState, config: RunnableConfig) -> OverallState:
    """LangGraph node that performs web research using Azure OpenAI with optional SerpAPI enhancement."""
    configurable = Configuration.from_runnable_config(config)
    formatted_prompt = web_searcher_instructions.format(
        current_date=get_current_date(),
        research_topic=state["search_query"],
    )
    
    # Call Azure OpenAI o3 model for initial web research
    completion = await openai_client.chat.completions.create(
        model=configurable.query_generator_model,
        messages=[{"role": "system", "content": formatted_prompt}],
        # temperature=0,
        # max_tokens=1024,
    )
    ai_generated_text = completion.choices[0].message.content
    
    # Enhance with real web data if SerpAPI is available and enabled
    sources_gathered = []
    if configurable.use_web_research:
        try:
            enhanced_result = await enhance_ai_research_with_real_data(
                state["search_query"], 
                ai_generated_text
            )
            final_text = enhanced_result["enhanced_content"]
            
            # Convert sources to the expected format
            for source in enhanced_result["sources"]:
                sources_gathered.append({
                    "label": source["title"][:50] + "..." if len(source["title"]) > 50 else source["title"],
                    "short_url": source["url"],
                    "value": source["url"],
                    "snippet": source["snippet"],
                    "scraped_successfully": source.get("scraped_successfully", False)
                })
        except Exception as e:
            print(f"Error enhancing web research: {e}")
            final_text = ai_generated_text
    else:
        final_text = ai_generated_text
    
    return {
        "sources_gathered": sources_gathered,
        "search_query": [state["search_query"]],
        "web_research_result": [final_text],
    }


async def reflection(state: OverallState, config: RunnableConfig) -> ReflectionState:
    """LangGraph node that identifies knowledge gaps and generates potential follow-up queries using Azure OpenAI."""
    configurable = Configuration.from_runnable_config(config)
    state["research_loop_count"] = state.get("research_loop_count", 0) + 1
    reasoning_model = state.get("reasoning_model") or configurable.reasoning_model
    current_date = get_current_date()
    formatted_prompt = reflection_instructions.format(
        current_date=current_date,
        research_topic=get_research_topic(state["messages"]),
        summaries="\n\n---\n\n".join(state["web_research_result"]),
    )
    completion = await openai_client.chat.completions.create(
        model=reasoning_model,
        messages=[{"role": "system", "content": formatted_prompt}],
        # temperature=1.0,
        max_completion_tokens=32000,
    )
    import json
    try:
        result = json.loads(completion.choices[0].message.content)
    except Exception:
        result = {
            "is_sufficient": False,
            "knowledge_gap": "",
            "follow_up_queries": [],
        }
    return {
        "is_sufficient": result.get("is_sufficient", False),
        "knowledge_gap": result.get("knowledge_gap", ""),
        "follow_up_queries": result.get("follow_up_queries", []),
        "research_loop_count": state["research_loop_count"],
        "number_of_ran_queries": len(state["search_query"]),
    }


def evaluate_research(
    state: ReflectionState,
    config: RunnableConfig,
) -> OverallState:
    """LangGraph routing function that determines the next step in the research flow.

    Controls the research loop by deciding whether to continue gathering information
    or to finalize the summary based on the configured maximum number of research loops.

    Args:
        state: Current graph state containing the research loop count
        config: Configuration for the runnable, including max_research_loops setting

    Returns:
        String literal indicating the next node to visit ("web_research" or "finalize_summary")
    """
    configurable = Configuration.from_runnable_config(config)
    max_research_loops = (
        state.get("max_research_loops")
        if state.get("max_research_loops") is not None
        else configurable.max_research_loops
    )
    
    if (state["is_sufficient"] or 
        state["research_loop_count"] >= max_research_loops or
        (not state["is_sufficient"] and not state["follow_up_queries"])):
        return "finalize_answer"
    else:
        return [
            Send(
                "web_research",
                {
                    "search_query": follow_up_query,
                    "id": state["number_of_ran_queries"] + int(idx),
                },
            )
            for idx, follow_up_query in enumerate(state["follow_up_queries"])
        ]


async def finalize_answer(state: OverallState, config: RunnableConfig):
    """LangGraph node that finalizes the research summary using Azure OpenAI."""
    configurable = Configuration.from_runnable_config(config)
    reasoning_model = state.get("reasoning_model") or configurable.reasoning_model
    current_date = get_current_date()
    formatted_prompt = answer_instructions.format(
        current_date=current_date,
        research_topic=get_research_topic(state["messages"]),
        summaries="\n---\n\n".join(state["web_research_result"]),
    )
    completion = await openai_client.chat.completions.create(
        model=reasoning_model,
        messages=[{"role": "system", "content": formatted_prompt}],
        # temperature=0,
        # max_tokens=1024,
    )
    content = completion.choices[0].message.content
    unique_sources = []
    for source in state["sources_gathered"]:
        if source.get("short_url") and source["short_url"] in content:
            content = content.replace(source["short_url"], source["value"])
            unique_sources.append(source)      # Create research steps for frontend display
    research_steps = []
    search_queries = state.get("search_query", [])
    
    for i, query in enumerate(search_queries, 1):
        research_steps.append({
            "step": i,
            "type": "search",
            "description": f"Searched for: {query}",
            "status": "completed"
        })
    
    # Add analysis step
    if search_queries:
        research_steps.append({
            "step": len(search_queries) + 1,
            "type": "analysis",
            "description": "Analyzed and synthesized information from sources",
            "status": "completed"
        })
    
      # Create structured message with content as string and metadata in additional_kwargs
    structured_data = {
        "sources": unique_sources,
        "research_summary": {
            "total_queries": len(state.get("search_query", [])),
            "research_loops": state.get("research_loop_count", 0),
            "sources_found": len(unique_sources),
            "research_steps": research_steps
        }
    }
    
    return {
        "messages": [AIMessage(content=content, additional_kwargs=structured_data)],
        "sources_gathered": unique_sources,
    }


# Create our Agent Graph
builder = StateGraph(OverallState, config_schema=Configuration)

# Define the nodes we will cycle between
builder.add_node("generate_query", generate_query)
builder.add_node("web_research", web_research)
builder.add_node("reflection", reflection)
builder.add_node("finalize_answer", finalize_answer)

# Set the entrypoint as `generate_query`
# This means that this node is the first one called
builder.add_edge(START, "generate_query")
# Add conditional edge to continue with search queries in a parallel branch
builder.add_conditional_edges(
    "generate_query", continue_to_web_research, ["web_research"]
)
# Reflect on the web research
builder.add_edge("web_research", "reflection")
# Evaluate the research
builder.add_conditional_edges(
    "reflection", evaluate_research, ["web_research", "finalize_answer"]
)
# Finalize the answer
builder.add_edge("finalize_answer", END)

graph = builder.compile(name="pro-search-agent")
