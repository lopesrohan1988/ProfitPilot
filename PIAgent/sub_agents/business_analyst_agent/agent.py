# sub_agents/business_analyst_agent/agent.py

from google.adk.agents.llm_agent import Agent

from ...shared_libraries import constants
# Import the new tools from the main tools.py file
from .tools import agent_provide_pricing_advice, agent_analyze_sales_trends, agent_check_inventory_levels

from ...prompts import business_analyst_prompt_text

business_analyst_agent = Agent(
    model=constants.MODEL, # Assuming MODEL is defined in constants
    name="business_analyst_agent",
    description="Provides data-driven insights and recommendations on sales trends, pricing strategies, and inventory management.",
    instruction=business_analyst_prompt_text.BUSINESS_ANALYST_PROMPT,
    tools=[
        agent_provide_pricing_advice,
        agent_analyze_sales_trends,
        agent_check_inventory_levels,
    ],
)