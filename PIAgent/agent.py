from google.adk.agents import Agent
from .shared_libraries import constants
from .prompts import root_prompt_text
# Import the sub-agents
from .sub_agents.onboarding_agent.agent import onboarding_agent
from .sub_agents.comparision_agent.agent import comparision_agent # Import the comparison agent

root_agent = Agent(
    name=constants.AGENT_NAME,
    model=constants.MODEL,
    description=constants.DESCRIPTION,
    instruction=root_prompt_text.ROOT_PROMPT,
    sub_agents=[
        onboarding_agent,
        comparision_agent # Add the comparison agent as a sub-agent
    ]
)