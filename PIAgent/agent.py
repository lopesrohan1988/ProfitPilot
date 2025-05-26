

from google.adk.agents import Agent
from .shared_libraries import constants
from .prompts import root_prompt_text


root_agent = Agent(
    name=constants.AGENT_NAME,
    model=constants.MODEL,
    description=constants.DESCRIPTION,
    instruction=root_prompt_text.ROOT_PROMPT,
    tools=[],
)