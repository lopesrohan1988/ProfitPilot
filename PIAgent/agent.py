

from google.adk.agents import Agent
from .shared_libraries import constants
from . import prompt


root_agent = Agent(
    name=constants.AGENT_NAME,
    model=constants.MODEL,
    description=constants.DESCRIPTION,
    instruction=prompt.ROOT_PROMPT,
    tools=[],
)