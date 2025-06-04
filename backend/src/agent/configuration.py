import os
from pydantic import BaseModel, Field
from typing import Any, Optional

from langchain_core.runnables import RunnableConfig



class Configuration(BaseModel):
    """The configuration for the agent."""    # Use Azure OpenAI o3 model names (deployment names or model names as configured in Azure)
    query_generator_model: str = Field(
        default="gpt-4.1-nano",
        metadata={
            "description": "The name of the Azure OpenAI o3 model to use for query generation."
        },
    )

    reflection_model: str = Field(
        default="o4-mini",
        metadata={
            "description": "The name of the Azure OpenAI o3 model to use for reflection."
        },
    )

    answer_model: str = Field(
        default="gpt-4.1-mini",
        metadata={
            "description": "The name of the Azure OpenAI o3 model to use for answer generation."
        },
    )

    reasoning_model: str = Field(
        default="o3",
        metadata={
            "description": "The name of the Azure OpenAI o3 model to use for reasoning and reflection."
        },
    )

    # Web research settings
    use_web_research: bool = Field(
        default=True,
        metadata={
            "description": "Whether to use real web research with SerpAPI or fallback to AI-only research."
        },
    )

    max_sources_per_query: int = Field(
        default=5,
        metadata={
            "description": "Maximum number of web sources to gather per search query."
        },
    )

    number_of_initial_queries: int = Field(
        default=3,
        metadata={"description": "The number of initial search queries to generate."},
    )

    max_research_loops: int = Field(
        default=5,
        metadata={"description": "The maximum number of research loops to perform."},
    )

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "Configuration":
        """Create a Configuration instance from a RunnableConfig."""
        configurable = (
            config["configurable"] if config and "configurable" in config else {}
        )

        # Get raw values from environment or config
        raw_values: dict[str, Any] = {
            name: os.environ.get(name.upper(), configurable.get(name))
            for name in cls.model_fields.keys()
        }

        # Filter out None values
        values = {k: v for k, v in raw_values.items() if v is not None}

        return cls(**values)
