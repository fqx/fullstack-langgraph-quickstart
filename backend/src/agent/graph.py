import os
from agent.tools_and_schemas import SearchQueryList, Reflection
from dotenv import load_dotenv
from langchain_core.messages import AIMessage
from langgraph.types import Send
from langgraph.graph import StateGraph
from langgraph.graph import START, END
from langchain_core.runnables import RunnableConfig
from openai import AsyncOpenAI
from typing import List, Union
import logging

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
        response_format={ "type": "json_object" },
        # temperature=1.0,
        # max_tokens=256,
    )
    # Parse output and extract the query list from JSON response
    import json
    try:
        response_json = json.loads(completion.choices[0].message.content)
        # Extract the query list from the JSON structure
        if isinstance(response_json, dict) and "query" in response_json:
            queries = response_json["query"]
            # Ensure queries is a list
            if isinstance(queries, str):
                queries = [queries]
        else:
            # Fallback if JSON structure is unexpected
            queries = [completion.choices[0].message.content]
    except Exception as e:
        print(f"Error parsing query JSON: {e}")
        # Fallback to treating the entire response as a single query
        queries = [completion.choices[0].message.content]

    return {"query_list": queries}



def continue_to_web_research(state: QueryGenerationState):
    """LangGraph node that sends the search queries to the web research node.

    This is used to spawn n number of web research nodes, one for each search query.
    """
    query_list = state.get("query_list", [])

    # Ensure query_list is actually a list of strings
    if not isinstance(query_list, list):
        query_list = [str(query_list)]

    # Filter out empty queries and ensure all items are strings
    valid_queries = []
    for query in query_list:
        if isinstance(query, str) and query.strip():
            valid_queries.append(query.strip())
        elif query:  # Non-string but truthy value
            valid_queries.append(str(query).strip())

    if not valid_queries:
        # Fallback to a default query if no valid queries found
        valid_queries = ["research topic information"]

    return [
        Send("web_research", {"search_query": search_query, "id": int(idx)})
        for idx, search_query in enumerate(valid_queries)
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
    reflection_model = state.get("reflection_model") or configurable.reflection_model
    current_date = get_current_date()

    # 使用现有的反思提示词
    formatted_prompt = reflection_instructions.format(
        current_date=current_date,
        research_topic=get_research_topic(state["messages"]),
        summaries="\n\n---\n\n".join(state["web_research_result"]),
    )

    # 添加调试日志
    logging.info("=" * 50)
    logging.info("REFLECTION - 开始反思分析")
    logging.info(f"研究主题: {get_research_topic(state['messages'])}")
    logging.info(f"研究结果数量: {len(state.get('web_research_result', []))}")

    completion = await openai_client.chat.completions.create(
        model=reflection_model,
        messages=[{"role": "system", "content": formatted_prompt}],
        response_format={"type": "json_object"},
        max_completion_tokens=32000,
    )

    # 记录LLM原始响应
    raw_response = completion.choices[0].message.content
    logging.info(f"LLM原始响应: {raw_response}")

    import json
    try:
        result = json.loads(raw_response)
        logging.info(f"解析成功: {result}")
    except Exception as e:
        logging.error(f"JSON解析失败: {e}")
        result = {
            "is_sufficient": False,
            "knowledge_gap": f"解析错误: {str(e)}",
            "follow_up_queries": [],
        }

    # 确保follow_up_queries是列表
    follow_up_queries = result.get("follow_up_queries", [])
    if not isinstance(follow_up_queries, list):
        follow_up_queries = []
        logging.warning("follow_up_queries不是列表，已重置为空列表")

    logging.info(f"是否足够: {result.get('is_sufficient', False)}")
    logging.info(f"知识缺口: {result.get('knowledge_gap', '')}")
    logging.info(f"后续查询数量: {len(follow_up_queries)}")
    for idx, query in enumerate(follow_up_queries):
        logging.info(f"  查询 {idx + 1}: {query}")

    logging.info("REFLECTION - 反思完成")
    logging.info("=" * 50)

    return {
        "is_sufficient": result.get("is_sufficient", False),
        "knowledge_gap": result.get("knowledge_gap", ""),
        "follow_up_queries": follow_up_queries,
        "research_loop_count": state["research_loop_count"],
        "number_of_ran_queries": len(state.get("search_query", [])),
    }


def evaluate_research(
    state: ReflectionState,
    config: RunnableConfig,
) -> Union[str, List[Send]]:
    """
    评估研究进度并决定下一步行动：继续研究或生成最终答案
    """
    import logging

    # 获取配置参数
    configuration = Configuration.from_runnable_config(config)
    max_research_loops = getattr(configuration, 'max_research_loops', 3)

    # 获取当前状态信息
    follow_up_queries = state.get("follow_up_queries", [])
    number_of_ran_queries = state.get("number_of_ran_queries", 0)
    research_loop_count = state.get("research_loop_count", 0)  # 循环次数
    reflection_summary = state.get("reflection_summary", "")

    # 详细调试日志
    logging.info("=" * 50)
    logging.info("EVALUATE_RESEARCH - 开始评估")
    logging.info(f"当前研究循环次数: {research_loop_count}")
    logging.info(f"最大研究循环次数: {max_research_loops}")
    logging.info(f"当前已执行查询次数: {number_of_ran_queries}")
    logging.info(f"待处理的后续查询数量: {len(follow_up_queries)}")
    logging.info(f"后续查询列表: {follow_up_queries}")
    logging.info(f"反思总结: {reflection_summary[:200]}...")

    # 检查是否达到最大循环次数
    if research_loop_count >= max_research_loops:
        logging.warning(f"已达到最大研究循环次数 ({max_research_loops})，强制进入最终答案阶段")
        return "finalize_answer"

    # 检查是否有有效的后续查询
    if not follow_up_queries:
        logging.info("没有后续查询，进入最终答案阶段")
        return "finalize_answer"

    # 过滤空查询
    valid_queries = [q.strip() for q in follow_up_queries if q and q.strip()]

    if not valid_queries:
        logging.info("所有后续查询都为空，进入最终答案阶段")
        return "finalize_answer"

    # 限制并发查询数量
    max_concurrent_queries = getattr(configuration, 'max_concurrent_queries', 3)
    limited_queries = valid_queries[:max_concurrent_queries]

    logging.info(f"准备执行 {len(limited_queries)} 个并行查询（第 {research_loop_count + 1} 轮循环）")
    for idx, query in enumerate(limited_queries):
        logging.info(f"  查询 {idx + 1}: {query}")

    # 创建并行研究任务
    research_tasks = []
    for idx, follow_up_query in enumerate(limited_queries):
        task = Send(
            "web_research",
            {
                "search_query": follow_up_query,
                "id": number_of_ran_queries + idx + 1,
                "research_loop_count": research_loop_count + 1,  # 传递循环计数
            },
        )
        research_tasks.append(task)
        logging.info(f"创建研究任务 ID: {number_of_ran_queries + idx + 1}, 查询: {follow_up_query}")

    logging.info(f"返回 {len(research_tasks)} 个并行研究任务")
    logging.info("EVALUATE_RESEARCH - 评估完成")
    logging.info("=" * 50)

    return research_tasks



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
