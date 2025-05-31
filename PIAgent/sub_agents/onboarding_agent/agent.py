


from google.adk.agents.llm_agent import Agent

from ...shared_libraries import constants
from .tools import db_check_business_exists, db_create_business, db_check_competitors_exist, db_add_competitor, Maps_search_business, agent_generate_simulated_data
from ...prompts import onboarding_prompt_text


onboarding_agent = Agent(
    model=constants.MODEL,
    name="onboarding_agent",
    description="A helpful agent to onboard new businesses and their competitors into ProfitPilot AI.",
    instruction=onboarding_prompt_text.ONBOARDING_PROMPT,
    tools=[
        db_check_business_exists, db_create_business, db_check_competitors_exist, db_add_competitor, Maps_search_business, agent_generate_simulated_data
    ],
)
