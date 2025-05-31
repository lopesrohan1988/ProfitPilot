import uuid
from google.cloud import bigquery
import os
from typing import Optional, List, Dict, Any, Union
import json 
from datetime import datetime, timedelta

# Import the new Places API client library
import googlemaps
from google.api_core.exceptions import GoogleAPIError

import google.generativeai as genai 
import dotenv
dotenv.load_dotenv()

from ..comparision_agent.tools import db_get_business_details

# --- Gemini API Configuration ---
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GEMINI_API_KEY:
    print("Warning: GEMINI_API_KEY environment variable not set. Gemini API calls might fail.")
else:
    genai.configure(api_key=GEMINI_API_KEY)
    print("Gemini API configured.")

# --- BigQuery Configuration ---
PROJECT_ID = 'profitpilot-2cc51'
DATASET_ID = 'profitpilot_data'
TABLE_BUSINESS = f"{PROJECT_ID}.{DATASET_ID}.business"
TABLE_COMPETITOR = f"{PROJECT_ID}.{DATASET_ID}.competitor"
# Use the new business_review table
TABLE_BUSINESS_REVIEW = f"{PROJECT_ID}.{DATASET_ID}.business_review" 
TABLE_INVENTORY_ITEM = f"{PROJECT_ID}.{DATASET_ID}.inventory_item"
TABLE_SALES_TRANSACTION = f"{PROJECT_ID}.{DATASET_ID}.sales_transaction"
# --- BigQuery Client Initialization ---
try:
    bq_client = bigquery.Client(project=PROJECT_ID, location='US')
    print(f"BigQuery client initialized for project: {PROJECT_ID}")
except Exception as e:
    print(f"Error initializing BigQuery client: {e}")
    bq_client = None

# --- Google Maps API Configuration ---
Maps_API_KEY = os.getenv("GOOGLE_MAP_API_KEY")
try:
    if Maps_API_KEY:
        places_client = googlemaps.Client(key=Maps_API_KEY)
        print("Google Places API (Older) client initialized.")
    # places_client = places.PlacesClient()
    # print("New Google Places API client initialized.")
except Exception as e:
    print(f"Error initializing New Google Places API client: {e}")
    places_client = None

# --- Gemini Model Initialization ---
try:
    gemini_model = genai.GenerativeModel('gemini-1.5-flash') # Or 'gemini-pro'
    print("Gemini model initialized for text generation.")
except Exception as e:
    print(f"Error initializing Gemini model: {e}")
    gemini_model = None

# --- New Tools for Comparative Agent ---
def db_get_item_pricing_data(business_id: str, item_name: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetches pricing-related data for items from inventory and sales.
    Combines inventory costs with sales prices and profits.
    """
    print(f"\n--- Tool Call: db_get_item_pricing_data ---")
    if not bq_client:
        print("BigQuery client not initialized.")
        return []

    # Get data from inventory_item table
    inventory_query = f"""
    SELECT
        item_id,
        item_name,
        unit_cost,
        unit_price AS current_unit_price,
        reorder_threshold,
        current_stock_level
    FROM `{TABLE_INVENTORY_ITEM}`
    WHERE business_id = @business_id
    """
    inventory_job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("business_id", "STRING", business_id),
        ]
    )
    if item_name:
        inventory_query += " AND item_name = @item_name"
        inventory_job_config.query_parameters.append(
            bigquery.ScalarQueryParameter("item_name", "STRING", item_name)
        )

    # Get sales data for average pricing and profit
    sales_query = f"""
    SELECT
        item_id,
        item_name,
        AVG(price_per_unit) AS avg_sales_price,
        SUM(total_line_profit) AS total_profit,
        SUM(quantity) AS total_quantity_sold
    FROM `{TABLE_SALES_TRANSACTION}`
    WHERE business_id = @business_id
    """
    sales_job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("business_id", "STRING", business_id),
        ]
    )
    if item_name:
        sales_query += " AND item_name = @item_name"
        sales_job_config.query_parameters.append(
            bigquery.ScalarQueryParameter("item_name", "STRING", item_name)
        )
    sales_query += " GROUP BY item_id, item_name"


    all_item_data = {}

    try:
        inventory_results = bq_client.query(inventory_query, job_config=inventory_job_config).result()
        for row in inventory_results:
            item_id = row.item_id
            all_item_data[item_id] = dict(row)
            all_item_data[item_id]['sales_data_available'] = False # Flag

        sales_results = bq_client.query(sales_query, job_config=sales_job_config).result()
        for row in sales_results:
            item_id = row.item_id
            if item_id in all_item_data:
                all_item_data[item_id].update(dict(row))
                all_item_data[item_id]['sales_data_available'] = True
            else:
                # If an item has sales but no inventory entry (shouldn't happen with good data, but for robustness)
                all_item_data[item_id] = dict(row)
                all_item_data[item_id]['sales_data_available'] = True
                # Add placeholders for inventory fields
                all_item_data[item_id]['unit_cost'] = None
                all_item_data[item_id]['current_unit_price'] = None
                all_item_data[item_id]['reorder_threshold'] = None
                all_item_data[item_id]['current_stock_level'] = None

        return list(all_item_data.values())

    except Exception as e:
        print(f"Error fetching pricing data from BigQuery: {e}")
        return []

def db_get_sales_trends_data(business_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetches sales transaction data for trend analysis within a given date range.
    Dates should be in 'YYYY-MM-DD' format.
    """
    print(f"\n--- Tool Call: db_get_sales_trends_data ---")
    if not bq_client:
        print("BigQuery client not initialized.")
        return []

    query = f"""
    SELECT
        timestamp,
        item_name,
        quantity,
        price_per_unit,
        total_line_revenue,
        total_line_profit
    FROM `{TABLE_SALES_TRANSACTION}`
    WHERE business_id = @business_id
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("business_id", "STRING", business_id),
        ]
    )

    if start_date:
        query += " AND transaction_date >= @start_date"
        job_config.query_parameters.append(
            bigquery.ScalarQueryParameter("start_date", "DATE", datetime.strptime(start_date, '%Y-%m-%d').date())
        )
    if end_date:
        query += " AND transaction_date <= @end_date"
        job_config.query_parameters.append(
            bigquery.ScalarQueryParameter("end_date", "DATE", datetime.strptime(end_date, '%Y-%m-%d').date())
        )

    query += " ORDER BY timestamp ASC"

    try:
        query_job = bq_client.query(query, job_config=job_config)
        results = query_job.result()
        return [dict(row) for row in results]
    except Exception as e:
        print(f"Error fetching sales trends data from BigQuery: {e}")
        return []

def db_get_inventory_status(business_id: str, low_stock_only: bool = False) -> List[Dict[str, Any]]:
    """
    Fetches current inventory levels, optionally filtered for low stock items.
    """
    print(f"\n--- Tool Call: db_get_inventory_status ---")
    if not bq_client:
        print("BigQuery client not initialized.")
        return []

    query = f"""
    SELECT
        item_name,
        category,
        current_stock_level,
        reorder_threshold,
        is_perishable,
        shelf_life_days
    FROM `{TABLE_INVENTORY_ITEM}`
    WHERE business_id = @business_id
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("business_id", "STRING", business_id),
        ]
    )

    if low_stock_only:
        query += " AND current_stock_level <= reorder_threshold"
    
    query += " ORDER BY item_name ASC"

    try:
        query_job = bq_client.query(query, job_config=job_config)
        results = query_job.result()
        return [dict(row) for row in results]
    except Exception as e:
        print(f"Error fetching inventory status from BigQuery: {e}")
        return []

# --- NEW AGENT HELPER FUNCTIONS FOR BUSINESS ANALYST ---

def agent_provide_pricing_advice(business_id: str, item_name: Optional[str] = None) -> str:
    """
    Provides pricing advice based on inventory costs and sales data.
    Can be called for a specific item or for all items.
    """
    print(f"\n--- Tool Call: agent_provide_pricing_advice ---")
    if not gemini_model:
        return "Error: Gemini model not initialized for pricing advice."

    pricing_data = db_get_item_pricing_data(business_id, item_name)

    if not pricing_data:
        return "No pricing data found for your business." + (f" for item '{item_name}'." if item_name else ".")

    data_summary = json.dumps(pricing_data, indent=2)

    prompt = f"""
    Analyze the following pricing and sales data for a business.
    Provide actionable pricing advice, focusing on profitability, potential price adjustments,
    and strategies for high-profit and low-profit items.
    
    Data:
    ```json
    {data_summary}
    ```

    Consider the following fields:
    - `item_name`: Name of the product.
    - `unit_cost`: Cost to the business.
    - `current_unit_price`: Current listed selling price from inventory.
    - `avg_sales_price`: Average actual sales price (might differ from current_unit_price).
    - `total_profit`: Total profit generated by this item.
    - `total_quantity_sold`: Total units sold.
    - `reorder_threshold`: Stock level to reorder.
    - `current_stock_level`: Current stock.

    Present your advice in a clear, concise, and structured markdown format, with headings and bullet points.
    """

    try:
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generating pricing advice with Gemini: {e}"

def agent_analyze_sales_trends(business_id: str, start_date: Optional[str] = None, end_date: Optional[str] = None, time_period: str = "last 30 days") -> str:
    """
    Analyzes sales trends for a business over a specified period.
    The time_period parameter is for user understanding, actual date filtering uses start_date and end_date.
    If no dates are provided, defaults to the last 30 days.
    """
    print(f"\n--- Tool Call: agent_analyze_sales_trends ---")
    if not gemini_model:
        return "Error: Gemini model not initialized for sales trend analysis."

    # Default to last 30 days if no dates are provided
    if not start_date and not end_date:
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=30)
        start_date = start_dt.strftime('%Y-%m-%d')
        end_date = end_dt.strftime('%Y-%m-%d')
        time_period = "the last 30 days" # Update period description

    sales_data = db_get_sales_trends_data(business_id, start_date, end_date)

    if not sales_data:
        return f"No sales data found for your business {time_period}."

    data_summary = json.dumps(sales_data, indent=2)
    business_details = db_get_business_details(business_id)
    business_name = business_details.get('name', 'your business') if business_details else 'your business'


    prompt = f"""
    Analyze the following sales transaction data for {business_name} covering {time_period}.
    Identify key trends such as:
    - Overall sales performance (growth, decline, stability).
    - Peak sales periods (e.g., specific days of the week, times of day, months).
    - Most popular items by quantity sold and revenue.
    - Any notable fluctuations or anomalies.

    Data:
    ```json
    {data_summary}
    ```

    Provide a concise summary of your findings in markdown format, with clear headings and bullet points.
    """

    try:
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generating sales trend analysis with Gemini: {e}"

def agent_check_inventory_levels(business_id: str, low_stock_only: bool = False) -> str:
    """
    Checks and reports current inventory levels, highlighting items below reorder threshold.
    """
    print(f"\n--- Tool Call: agent_check_inventory_levels ---")
    if not gemini_model:
        return "Error: Gemini model not initialized for inventory check."

    inventory_data = db_get_inventory_status(business_id, low_stock_only)

    if not inventory_data:
        return "No inventory data found for your business." + (" Or no items are currently low in stock." if low_stock_only else "")

    data_summary = json.dumps(inventory_data, indent=2)
    business_details = db_get_business_details(business_id)
    business_name = business_details.get('name', 'your business') if business_details else 'your business'


    prompt = f"""
    Analyze the following inventory data for {business_name}.
    Provide a clear report on the current stock levels.
    
    Specifically, identify and list:
    - All items that are currently below their reorder threshold.
    - For perishable items, highlight any that are low in stock or nearing their shelf life limit (if shelf_life_days is provided).
    - General overview of healthy stock levels.

    Data:
    ```json
    {data_summary}
    ```

    Present your report in a clear, concise, and structured markdown format, with headings and bullet points.
    """

    try:
        response = gemini_model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generating inventory report with Gemini: {e}"