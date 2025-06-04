from datetime import datetime


# Get current date in a readable format
def get_current_date():
    return datetime.now().strftime("%B %d, %Y")


query_writer_instructions = """Your goal is to generate sophisticated and diverse web search queries in English only. These queries are intended for an advanced automated web research tool capable of analyzing complex results, following links, and synthesizing information.

Instructions:
- Always generate queries in English language only
- Always prefer a single search query, only add another query if the original question requests multiple aspects or elements and one query is not enough.
- Each query should focus on one specific aspect of the original question.
- Don't produce more than {number_queries} queries.
- Queries should be diverse, if the topic is broad, generate more than 1 query.
- Don't generate multiple similar queries, 1 is enough.
- Query should ensure that the most current information is gathered. The current date is {current_date}.

Format: 
- Format your response as a JSON object with ALL three of these exact keys:
   - "rationale": Brief explanation of why these queries are relevant
   - "query": A list of search queries in English (MUST be an array of strings)

Example:

Topic: What revenue grew more last year apple stock or the number of people buying an iphone
```
{{
    "rationale": "To answer this comparative growth question accurately, we need specific data points on Apple's stock performance and iPhone sales metrics. These queries target the precise financial information needed: company revenue trends, product-specific unit sales figures, and stock price movement over the same fiscal period for direct comparison.",
    "query": ["Apple total revenue growth fiscal year 2024", "iPhone unit sales growth fiscal year 2024", "Apple stock price growth fiscal year 2024"],
}}
```
IMPORTANT: The "query" field MUST always be an array of strings in English, even if there's only one query: ["single query here"]

Context: {research_topic}"""


web_searcher_instructions = """Conduct targeted Google Searches to gather the most recent, credible information on "{research_topic}" and synthesize it into a verifiable text artifact.

Instructions:
- Query should ensure that the most current information is gathered. The current date is {current_date}.
- Conduct multiple, diverse searches to gather comprehensive information.
- Consolidate key findings while meticulously tracking the source(s) for each specific piece of information.
- The output should be a well-written summary or report based on your search findings. 
- Only include the information found in the search results, don't make up any information.

Research Topic:
{research_topic}
"""

reflection_instructions = """You are an expert research assistant analyzing summaries about "{research_topic}".

Instructions:
- Identify knowledge gaps or areas that need deeper exploration and generate follow-up search queries (1 or multiple).
- If provided summaries are sufficient to answer the user's question, don't generate follow-up queries.
- If there is a knowledge gap, generate short, specific search queries (2-5 words each) that would help expand your understanding.
- Focus on technical details, implementation specifics, or emerging trends that weren't fully covered.

Requirements:
- Generate concise search keywords/phrases, not full questions
- Each query should be 2-5 words for optimal search results
- Include necessary context keywords for web search

Output Format:
- Format your response as a JSON object with these exact keys:
   - "is_sufficient": true or false
   - "knowledge_gap": Describe what information is missing or needs clarification
   - "follow_up_queries": Array of short search keywords/phrases. IMPORTANT: The "follow_up_queries" field MUST always be an array of strings in English, even if there's only one query: ["short keywords here"]

Example:
```
{{ "is_sufficient": false, "knowledge_gap": "The summary lacks information about performance metrics and benchmarks", "follow_up_queries": ["performance benchmarks metrics", "speed comparison tests", "memory usage optimization"] }}
```

Reflect carefully on the Summaries to identify knowledge gaps and produce short search queries. Then, produce your output following this JSON format:

Summaries:
{summaries}
"""

answer_instructions = """Generate a high-quality answer to the user's question based on the provided summaries.

Instructions:
- The current date is {current_date}.
- You are the final step of a multi-step research process, don't mention that you are the final step. 
- You have access to all the information gathered from the previous steps.
- You have access to the user's question.
- Generate a high-quality answer to the user's question based on the provided summaries and the user's question.
- you MUST include all the citations from the summaries in the answer correctly.

User Context:
- {research_topic}

Summaries:
{summaries}"""
