# Assuming this is in a file like 'sub_agents/comparision_agent/agent.py'
from google.adk.agents.llm_agent import Agent

from ...shared_libraries import constants
# Import the tools specific to the comparison agent
from .tools import db_get_business_details, db_get_competitors, db_get_processed_reviews, agent_call_customer_sentiment_analyst_for_reviews
from ...prompts import comparision_prompt_text # Import the new prompt


comparision_agent = Agent(
    model=constants.MODEL,
    name="comparision_agent",
    description="Analyzes and compares processed customer reviews for a business against its competitors.",
    instruction=comparision_prompt_text.COMPARISON_AGENT_PROMPT, # Use the new, dedicated prompt
    tools=[
        db_get_business_details,
        db_get_competitors,
        db_get_processed_reviews,
        agent_call_customer_sentiment_analyst_for_reviews, # This tool initiates data collection if needed
    ],
)