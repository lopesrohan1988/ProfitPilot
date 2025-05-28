
"""Defines constants."""

import os

import dotenv

dotenv.load_dotenv()

AGENT_NAME = "ProfitPilot_AI_Assistant"
DESCRIPTION = "A helpful assistant Intelligent Growth & Strategy for Mom & Pop Shops."

LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "global")
MODEL = os.getenv("MODEL", "gemini-2.0-flash-001")
DATASET_ID = os.getenv("DATASET_ID", "products_data_agent")
TABLE_ID = os.getenv("TABLE_ID", "shoe_items")
# DISABLE_WEB_DRIVER = int(os.getenv("DISABLE_WEB_DRIVER", "0"))
WHL_FILE_NAME = os.getenv("ADK_WHL_FILE", "")
STAGING_BUCKET = os.getenv("STAGING_BUCKET", "")
# PROJECT_ID = 'profitpilot-2cc51'
BQ_DATASET_ID =os.getenv("BQ_DATASET_ID", "EMPTY")
PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "EMPTY")
GOOGLE_MAP_API_KEY = os.getenv("GOOGLE_MAP_API_KEY", "EMPTY")
