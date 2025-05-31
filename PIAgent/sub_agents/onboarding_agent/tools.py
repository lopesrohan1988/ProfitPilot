import uuid
from google.cloud import bigquery
import googlemaps
import os
from typing import Optional, List, Dict, Any, Union
import json
import datetime
import random 
from ...shared_libraries import constants
# Import the OLDER Google Maps client library
import googlemaps
from google.api_core.exceptions import GoogleAPIError
from ..comparision_agent.tools import db_get_business_details

import google.generativeai as genai
import dotenv
dotenv.load_dotenv()

# --- BigQuery Configuration ---
PROJECT_ID = constants.PROJECT_ID
DATASET_ID = constants.BQ_DATASET_ID
TABLE_BUSINESS = f"{PROJECT_ID}.{DATASET_ID}.business"
TABLE_COMPETITOR = f"{PROJECT_ID}.{DATASET_ID}.competitor"
TABLE_INVENTORY_ITEM = f"{PROJECT_ID}.{DATASET_ID}.inventory_item" # New table constant
TABLE_SALES_TRANSACTION = f"{PROJECT_ID}.{DATASET_ID}.sales_transaction" # New table constant

# --- BigQuery Client Initialization ---
try:
    bq_client = bigquery.Client(project=PROJECT_ID, location='US')
    print(f"BigQuery client initialized for project: {PROJECT_ID}")
except Exception as e:
    print(f"Error initializing BigQuery client: {e}")
    bq_client = None

# --- Google Maps API Configuration ---
GMAPS_API_KEY = constants.GOOGLE_MAP_API_KEY

if not GMAPS_API_KEY:
    print("WARNING: Maps_API_KEY environment variable not set. Maps_search_business will not function.")
    gmaps_client = None
else:
    gmaps_client = googlemaps.Client(key=GMAPS_API_KEY)

# --- Gemini API Configuration ---
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY") # Using GOOGLE_API_KEY as per your setup
if not GEMINI_API_KEY:
    print("Warning: GOOGLE_API_KEY environment variable not set. Gemini API calls might fail.")
else:
    genai.configure(api_key=GEMINI_API_KEY)
    print("Gemini API configured.")




# --- Gemini Model Initialization ---
try:
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
    print("Gemini model initialized for text generation.")
except Exception as e:
    print(f"Error initializing Gemini model: {e}")
    gemini_model = None
# --- Tool Functions for Onboarding Agent ---

def db_check_business_exists(business_name: str) -> List[Dict[str, Any]]:
    """
    Checks if a business with the given name already exists in the system (BigQuery).
    Returns a list of business details if found.

    Args:
        business_name (str): The name of the business to check.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries, where each dictionary contains
                              business details (e.g., 'business_id', 'name', 'address', etc.).
                              Returns an empty list if no matches are found.
    """
    print(f"ADK Tool Call: db_check_business_exists(business_name='{business_name}')")
    if not bq_client:
        print("BigQuery client not initialized. Cannot check business existence.")
        return []

    # Query only by business_name as per original signature
    query = f"""
    SELECT
        id, g_m_b_id, address, business_id, business_type, description, name, owner_contact_info
    FROM
        `{TABLE_BUSINESS}`
    WHERE
        LOWER(name) LIKE @business_name
    """
    query_params = [
        bigquery.ScalarQueryParameter("business_name", "STRING", f"%{business_name.lower()}%")
    ]

    try:
        query_job = bq_client.query(query, job_config=bigquery.QueryJobConfig(query_parameters=query_params))
        rows = query_job.result()

        matches = []
        for row in rows:
            matches.append({
                "id": row.id,
                "gmb_id": row.g_m_b_id,
                "address": row.address,
                "business_id": row.business_id,
                "business_type": row.business_type,
                "description": row.description,
                "name": row.name,
                "owner_contact": row.owner_contact_info
            })

        if not matches:
            print(f"BigQuery: Business '{business_name}' not found.")
        else:
            print(f"BigQuery: Found {len(matches)} matches for '{business_name}'.")
        return matches

    except Exception as e:
        print(f"Error checking business existence in BigQuery: {e}")
        return []


def db_create_business(name: str, address: str, business_type: str, description: str,
                       gmb_id: Optional[str] = None, owner_contact: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Registers a new business in the system (BigQuery).
    Returns the created business's details including its new ID.

    Args:
        name (str): The name of the business.
        address (str): The physical address of the business.
        business_type (str): The type of business (e.g., retail, restaurant).
        description (str): A brief description of the business.
        gmb_id (Optional[str]): Google My Business ID.
        owner_contact (Optional[str]): Owner's contact info (email/phone).

    Returns:
        Optional[Dict[str, Any]]: A dictionary containing the newly created business's details
                                  including its 'business_id', otherwise None if creation fails.
    """
    print(f"ADK Tool Call: db_create_business(name='{name}', address='{address}', business_type='{business_type}', description='{description}', gmb_id='{gmb_id}', owner_contact='{owner_contact}')")
    if not bq_client:
        print("BigQuery client not initialized. Cannot create business.")
        return None

    id_uuid = str(uuid.uuid4())
    business_id_val = f"biz_{id_uuid.split('-')[0]}"

    query = f"""
    INSERT INTO `{TABLE_BUSINESS}` (
        id, g_m_b_id, address, business_id, business_type, description, name, owner_contact_info
    ) VALUES (
        @id, @g_m_b_id, @address, @business_id, @business_type, @description, @name, @owner_contact_info
    )
    """

    owner_contact_json = {}
    if owner_contact:
        owner_contact_json = {"primary": owner_contact}
    owner_contact_info_str = str(owner_contact_json).replace("'", '"')

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("id", "STRING", id_uuid),
            bigquery.ScalarQueryParameter("g_m_b_id", "STRING", gmb_id),
            bigquery.ScalarQueryParameter("address", "STRING", address),
            bigquery.ScalarQueryParameter("business_id", "STRING", business_id_val),
            bigquery.ScalarQueryParameter("business_type", "STRING", business_type),
            bigquery.ScalarQueryParameter("description", "STRING", description),
            bigquery.ScalarQueryParameter("name", "STRING", name),
            bigquery.ScalarQueryParameter("owner_contact_info", "JSON", owner_contact_info_str)
        ]
    )

    try:
        query_job = bq_client.query(query, job_config=job_config)
        query_job.result()

        created_business_details = {
            "id": id_uuid,
            "business_id": business_id_val,
            "name": name,
            "address": address,
            "type": business_type,
            "description": description,
            "gmb_id": gmb_id,
            "owner_contact": owner_contact
        }
        print(f"BigQuery: Business '{name}' created with ID '{business_id_val}'.")
        return created_business_details

    except Exception as e:
        print(f"Error creating business in BigQuery: {e}")
        return None


def db_check_competitors_exist(business_id: str) -> List[Dict[str, Any]]:
    """
    Checks if any competitors are already set up for a given business ID (BigQuery).
    Returns a list of competitor details if found.

    Args:
        business_id (str): The ID of the business to check.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries, where each dictionary contains
                              competitor details ('name', 'website_url', 'google_place_id').
                              Returns an empty list if no competitors are found.
    """
    print(f"ADK Tool Call: db_check_competitors_exist(business_id='{business_id}')")
    if not bq_client:
        print("BigQuery client not initialized. Cannot check competitors.")
        return []

    query = f"""
    SELECT
        name, website_url, google_place_id
    FROM
        `{TABLE_COMPETITOR}`
    WHERE
        business_id = @business_id
    """
    query_params = [
        bigquery.ScalarQueryParameter("business_id", "STRING", business_id)
    ]

    try:
        query_job = bq_client.query(query, job_config=bigquery.QueryJobConfig(query_parameters=query_params))
        rows = query_job.result()

        competitors = []
        for row in rows:
            competitors.append({
                "name": row.name,
                "website_url": row.website_url,
                "google_place_id": row.google_place_id
            })

        if not competitors:
            print(f"BigQuery: No competitors found for business ID '{business_id}'.")
        else:
            print(f"BigQuery: Found {len(competitors)} competitors for business ID '{business_id}'.")
        return competitors

    except Exception as e:
        print(f"Error checking competitors existence in BigQuery: {e}")
        return []

def db_add_competitor(business_id: str, competitor_name: str, website_url: str,
                      google_place_id: Optional[str] = None) -> bool:
    """
    Adds a competitor to an existing business in the system (BigQuery).

    Args:
        business_id (str): The ID of the business to associate the competitor with.
        competitor_name (str): The name of the competitor.
        website_url (str): The website URL of the competitor.
        google_place_id (Optional[str]): Google Place ID for the competitor.

    Returns:
        bool: True if the competitor was successfully added, False otherwise.
    """
    print(f"ADK Tool Call: db_add_competitor(business_id='{business_id}', competitor_name='{competitor_name}', website_url='{website_url}', google_place_id='{google_place_id}')")
    if not bq_client:
        print("BigQuery client not initialized. Cannot add competitor.")
        return False

    id_uuid = str(uuid.uuid4())
    competitor_id_val = f"comp_{id_uuid.split('-')[0]}"

    query = f"""
    INSERT INTO `{TABLE_COMPETITOR}` (
        id, business_id, competitor_id, google_place_id, name, website_url
    ) VALUES (
        @id, @business_id, @competitor_id, @google_place_id, @name, @website_url
    )
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("id", "STRING", id_uuid),
            bigquery.ScalarQueryParameter("business_id", "STRING", business_id),
            bigquery.ScalarQueryParameter("competitor_id", "STRING", competitor_id_val),
            bigquery.ScalarQueryParameter("google_place_id", "STRING", google_place_id),
            bigquery.ScalarQueryParameter("name", "STRING", competitor_name),
            bigquery.ScalarQueryParameter("website_url", "STRING", website_url)
        ]
    )

    try:
        query_job = bq_client.query(query, job_config=job_config)
        query_job.result()
        print(f"BigQuery: Competitor '{competitor_name}' added for business ID '{business_id}'.")
        return True

    except Exception as e:
        print(f"Error adding competitor to BigQuery: {e}")
        return False


def Maps_search_business(query: str, location_bias: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
    """
    Searches Google Maps for business information using the actual Google Maps Places API.

    Args:
        query (str): The business name and/or address (e.g., "Nike 8887 Thornel St Houston").
        location_bias (Optional[Dict[str, float]]): Dictionary with 'lat' and 'lng' for biasing results.
                                                     E.g., {'lat': 29.7604, 'lng': -95.3698}

    Returns:
        List[Dict[str, Any]]: A list of dictionaries, each representing a found business
                              with keys like 'name', 'address', 'place_id', 'website', 'phone_number'.
    """
    print(f"ADK Tool Call: Maps_search_business(query='{query}', location_bias={location_bias})")
    if not gmaps_client:
        print("Google Maps client not initialized. Cannot search businesses.")
        return []

    try:
        gmaps_location = None
        gmaps_radius = None # Default to no radius unless specified
        if location_bias and 'lat' in location_bias and 'lng' in location_bias:
            gmaps_location = (location_bias['lat'], location_bias['lng'])
            # You might want to pass a default radius here if a general bias is expected
            # For `text_search`, location and radius define the search area.
            # If the user provides a "location_bias" but no explicit radius, pick a reasonable default
            gmaps_radius = 5000 # Example: 5km radius for biasing

        response = gmaps_client.places(
            query=query,
            location=gmaps_location, # Pass if available, else None
            radius=gmaps_radius # Pass if available, else None
        )
        # print(f"Google Maps API Response: {response}")
        results = []
        if 'results' in response:
            for place in response['results']:
                results.append({
                    'name': place.get('name'),
                    'address': place.get('formatted_address'),
                    'place_id': place.get('place_id'),
                    'website': place.get('website'),
                    'phone_number': place.get('nationalPhoneNumber')
                })
        print(f"Google Maps: Found {len(results)} businesses for '{query}'.")
        return results

    except Exception as e:
        print(f"Error searching Google Maps: {e}")
        return []
    




def db_insert_inventory_item(item_data: Dict[str, Any]) -> bool:
    """
    Inserts a single inventory item into the `inventory_item` BigQuery table.
    """
    print(f"\n--- Tool Call: db_insert_inventory_item ---")
    if not bq_client:
        print("BigQuery client not initialized. Cannot insert inventory item.")
        return False

    query = f"""
    INSERT INTO `{TABLE_INVENTORY_ITEM}` (
        id, business_id, category, current_stock_level, is_perishable,
        item_id, item_name, last_updated, reorder_threshold, shelf_life_days,
        supplier_id, unit_cost, unit_price
    ) VALUES (
        @id, @business_id, @category, @current_stock_level, @is_perishable,
        @item_id, @item_name, @last_updated, @reorder_threshold, @shelf_life_days,
        @supplier_id, @unit_cost, @unit_price
    )
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("id", "STRING", item_data.get('id')),
            bigquery.ScalarQueryParameter("business_id", "STRING", item_data.get('business_id')),
            bigquery.ScalarQueryParameter("category", "STRING", item_data.get('category')),
            bigquery.ScalarQueryParameter("current_stock_level", "INT64", item_data.get('current_stock_level')),
            bigquery.ScalarQueryParameter("is_perishable", "BOOL", item_data.get('is_perishable')),
            bigquery.ScalarQueryParameter("item_id", "STRING", item_data.get('item_id')),
            bigquery.ScalarQueryParameter("item_name", "STRING", item_data.get('item_name')),
            bigquery.ScalarQueryParameter("last_updated", "TIMESTAMP", item_data.get('last_updated')),
            bigquery.ScalarQueryParameter("reorder_threshold", "INT64", item_data.get('reorder_threshold')),
            bigquery.ScalarQueryParameter("shelf_life_days", "INT64", item_data.get('shelf_life_days')),
            bigquery.ScalarQueryParameter("supplier_id", "STRING", item_data.get('supplier_id')),
            bigquery.ScalarQueryParameter("unit_cost", "FLOAT64", item_data.get('unit_cost')),
            bigquery.ScalarQueryParameter("unit_price", "FLOAT64", item_data.get('unit_price')),
        ]
    )

    try:
        query_job = bq_client.query(query, job_config=job_config)
        query_job.result()
        print(f"BigQuery: Successfully inserted inventory item '{item_data.get('item_name')}' for business '{item_data.get('business_id')}'.")
        return True
    except Exception as e:
        print(f"Error inserting inventory item to BigQuery: {e}")
        return False

def db_insert_sales_transaction(transaction_data: Dict[str, Any]) -> bool:
    """
    Inserts a single sales transaction into the `sales_transaction` BigQuery table.
    """
    print(f"\n--- Tool Call: db_insert_sales_transaction ---")
    if not bq_client:
        print("BigQuery client not initialized. Cannot insert sales transaction.")
        return False

    query = f"""
    INSERT INTO `{TABLE_SALES_TRANSACTION}` (
        id, business_id, cost_per_unit, customer_id, item_id, item_name,
        line_item_id, payment_method, price_per_unit, quantity, timestamp,
        total_line_cost, total_line_profit, total_line_revenue, transaction_date, transaction_id
    ) VALUES (
        @id, @business_id, @cost_per_unit, @customer_id, @item_id, @item_name,
        @line_item_id, @payment_method, @price_per_unit, @quantity, @timestamp,
        @total_line_cost, @total_line_profit, @total_line_revenue, @transaction_date, @transaction_id
    )
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("id", "STRING", transaction_data.get('id')),
            bigquery.ScalarQueryParameter("business_id", "STRING", transaction_data.get('business_id')),
            bigquery.ScalarQueryParameter("cost_per_unit", "FLOAT64", transaction_data.get('cost_per_unit')),
            bigquery.ScalarQueryParameter("customer_id", "STRING", transaction_data.get('customer_id')),
            bigquery.ScalarQueryParameter("item_id", "STRING", transaction_data.get('item_id')),
            bigquery.ScalarQueryParameter("item_name", "STRING", transaction_data.get('item_name')),
            bigquery.ScalarQueryParameter("line_item_id", "STRING", transaction_data.get('line_item_id')),
            bigquery.ScalarQueryParameter("payment_method", "STRING", transaction_data.get('payment_method')),
            bigquery.ScalarQueryParameter("price_per_unit", "FLOAT64", transaction_data.get('price_per_unit')),
            bigquery.ScalarQueryParameter("quantity", "INT64", transaction_data.get('quantity')),
            bigquery.ScalarQueryParameter("timestamp", "TIMESTAMP", transaction_data.get('timestamp')),
            bigquery.ScalarQueryParameter("total_line_cost", "FLOAT64", transaction_data.get('total_line_cost')),
            bigquery.ScalarQueryParameter("total_line_profit", "FLOAT64", transaction_data.get('total_line_profit')),
            bigquery.ScalarQueryParameter("total_line_revenue", "FLOAT64", transaction_data.get('total_line_revenue')),
            bigquery.ScalarQueryParameter("transaction_date", "DATE", transaction_data.get('transaction_date')),
            bigquery.ScalarQueryParameter("transaction_id", "STRING", transaction_data.get('transaction_id')),
        ]
    )

    try:
        query_job = bq_client.query(query, job_config=job_config)
        query_job.result()
        print(f"BigQuery: Successfully inserted sales transaction for item '{transaction_data.get('item_name')}' for business '{transaction_data.get('business_id')}'.")
        return True
    except Exception as e:
        print(f"Error inserting sales transaction to BigQuery: {e}")
        return False

# --- NEW TOOL FOR GENERATING SIMULATED DATA ---

def agent_generate_simulated_data(business_id: str) -> bool:
    """
    Generates simulated inventory and sales data for a given business ID using Gemini.
    It fetches all business details and lets Gemini infer the business_type
    to generate relevant data.

    Args:
        business_id (str): The ID of the business for which to generate data.

    Returns:
        bool: True if data generation and storage was successful, False otherwise.
    """
    print(f"\n--- Tool Call: agent_generate_simulated_data ---")

    # Step 1: Get ALL business details from the database
    business_details = db_get_business_details(business_id)
    if not business_details:
        print(f"Error: Could not retrieve business details for business_id '{business_id}'. Cannot generate simulated data.")
        return False

    business_name = business_details.get('name', 'N/A')
    business_address = business_details.get('address', 'N/A')
    business_description = business_details.get('description', 'N/A')
    # If business_type is already stored, include it as a strong hint for Gemini
    # otherwise, Gemini will have to infer it from name/description.
    stored_business_type = business_details.get('business_type', 'unknown type')
    gmb_id = business_details.get('gmb_id', 'N/A')
    owner_contact = business_details.get('owner_contact', 'N/A')


    print(f"  Generating simulated data for business ID '{business_id}'.")
    print(f"  Business Name: {business_name}, Description: {business_description}, Stored Type: {stored_business_type}")


    if not gemini_model:
        print("Gemini model not initialized. Cannot generate simulated data.")
        return False

    # Define the JSON schema for Gemini's response
    # Added 'inferred_business_type' to the schema
    response_schema = {
        "type": "OBJECT",
        "properties": {
            "inferred_business_type": {
                "type": "STRING",
                "description": "The business type inferred by Gemini from the provided details (e.g., 'Coffee Shop', 'Shoe Store', 'Grocery Store')."
            },
            "inventory_items": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "item_name": {"type": "STRING", "description": "Name of the inventory item"},
                        "category": {"type": "STRING", "description": "Category of the item (e.g., 'Beverage', 'Pastry', 'Footwear')"},
                        "current_stock_level": {"type": "INTEGER", "description": "Current number of units in stock"},
                        "reorder_threshold": {"type": "INTEGER", "description": "Stock level at which to reorder"},
                        "unit_cost": {"type": "NUMBER", "format": "float", "description": "Cost to the business per unit"},
                        "unit_price": {"type": "NUMBER", "format": "float", "description": "Selling price per unit"},
                        "is_perishable": {"type": "BOOLEAN", "description": "True if the item has a limited shelf life"},
                        "shelf_life_days": {"type": "INTEGER", "description": "Number of days item remains fresh, if perishable"}
                    },
                    "required": ["item_name", "category", "current_stock_level", "reorder_threshold", "unit_cost", "unit_price"]
                }
            },
            "sales_transactions": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "item_name": {"type": "STRING", "description": "Name of the item sold (must match an inventory item name)"},
                        "quantity": {"type": "INTEGER", "description": "Number of units sold in this transaction line item"},
                        "price_per_unit": {"type": "NUMBER", "format": "float", "description": "Actual price per unit at sale time"},
                        "timestamp": {"type": "STRING", "format": "date-time", "description": "ISO 8601 timestamp of the transaction"},
                        "payment_method": {"type": "STRING", "description": "Payment method (e.g., 'Credit Card', 'Cash', 'Mobile Pay')"},
                        "customer_id": {"type": "STRING", "description": "Optional customer identifier"}
                    },
                    "required": ["item_name", "quantity", "price_per_unit", "timestamp"]
                }
            }
        },
        "required": ["inferred_business_type", "inventory_items", "sales_transactions"]
    }

    # Construct the prompt for Gemini, including all details for inference
    prompt = f"""
    Based on the following business details, first **infer the most appropriate business type**.
    Then, generate realistic simulated inventory items and sales transactions relevant to that **inferred business type**.

    **Business Details:**
    - Name: {business_name}
    - Address: {business_address}
    - Description: {business_description}
    - Stored Business Type (if any): {stored_business_type}
    - GMB ID: {gmb_id}
    - Owner Contact: {owner_contact}

    For inventory, create 5-10 distinct items relevant to the inferred business type. Include typical stock levels, reorder points, costs, and prices. Consider if items are perishable.
    
    For sales, generate 30-50 sales transactions over the last 60 days. Ensure the 'item_name' in sales transactions exactly matches an 'item_name' from your generated inventory items. Vary quantities, prices (slightly, if realistic), and timestamps to simulate trends. Include payment methods and optional customer IDs.
    
    Provide the output as a JSON object strictly conforming to the following schema:
    """

    try:
        # Call Gemini with the structured response schema
        response = gemini_model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json", "response_schema": response_schema}
        )

        if not response.text:
            print("Gemini API returned no content for simulated data generation.")
            return False

        generated_data = json.loads(response.text)

        inferred_business_type = generated_data.get("inferred_business_type", "unknown")
        inventory_items = generated_data.get("inventory_items", [])
        sales_transactions = generated_data.get("sales_transactions", [])

        if not inventory_items and not sales_transactions:
            print("Gemini generated empty inventory and sales data.")
            return False

        print(f"Gemini inferred business type: {inferred_business_type}")

        # Store Inventory Items
        print(f"Storing {len(inventory_items)} generated inventory items...")
        item_name_to_id_map = {} # To link sales transactions to item_ids
        for item in inventory_items:
            item_id = str(uuid.uuid4())
            item_name_to_id_map[item['item_name']] = item_id
            
            insert_data = {
                "id": str(uuid.uuid4()),
                "business_id": business_id,
                "category": item.get('category'),
                "current_stock_level": item.get('current_stock_level'),
                "is_perishable": item.get('is_perishable', False),
                "item_id": item_id,
                "item_name": item.get('item_name'),
                "last_updated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "reorder_threshold": item.get('reorder_threshold'),
                "shelf_life_days": item.get('shelf_life_days'),
                "supplier_id": str(uuid.uuid4())[:8], # Mock supplier ID
                "unit_cost": item.get('unit_cost'),
                "unit_price": item.get('unit_price'),
            }
            db_insert_inventory_item(insert_data)

        # Store Sales Transactions
        print(f"Storing {len(sales_transactions)} generated sales transactions...")
        for transaction in sales_transactions:
            item_name = transaction.get('item_name')
            item_id = item_name_to_id_map.get(item_name) # Get item_id from map

            if not item_id:
                print(f"Warning: Skipping sales transaction for unknown item_name '{item_name}'.")
                continue

            quantity = transaction.get('quantity', 0)
            price_per_unit = transaction.get('price_per_unit', 0.0)
            cost_per_unit = 0.0 # Will try to derive from inventory if possible
            
            # Attempt to find unit_cost from generated inventory items
            for inv_item in inventory_items:
                if inv_item.get('item_name') == item_name:
                    cost_per_unit = inv_item.get('unit_cost', 0.0)
                    break

            total_line_revenue = quantity * price_per_unit
            total_line_cost = quantity * cost_per_unit
            total_line_profit = total_line_revenue - total_line_cost

            # Ensure timestamp is in correct format
            timestamp_str = transaction.get('timestamp')
            transaction_dt = None
            if timestamp_str:
                try:
                    # Parse assuming ISO 8601, then convert to UTC and isoformat
                    transaction_dt = datetime.datetime.now(datetime.timezone.utc).isoformat()
                except ValueError:
                    print(f"Warning: Could not parse timestamp '{timestamp_str}'. Using current time.")
                    transaction_dt = datetime.datetime.now(datetime.timezone.utc).isoformat()
            else:
                transaction_dt = datetime.datetime.now(datetime.timezone.utc).isoformat()


            insert_data = {
                "id": str(uuid.uuid4()),
                "business_id": business_id,
                "cost_per_unit": cost_per_unit,
                "customer_id": transaction.get('customer_id', str(uuid.uuid4())[:8]), # Mock customer ID
                "item_id": item_id,
                "item_name": item_name,
                "line_item_id": str(uuid.uuid4()),
                "payment_method": transaction.get('payment_method', 'Unknown'),
                "price_per_unit": price_per_unit,
                "quantity": quantity,
                "timestamp": transaction_dt,
                "total_line_cost": total_line_cost,
                "total_line_profit": total_line_profit,
                "total_line_revenue": total_line_revenue,
                "transaction_date": transaction_dt.split('T')[0], # Extract date part
                "transaction_id": str(uuid.uuid4()),
            }
            db_insert_sales_transaction(insert_data)

        print(f"Simulated data generation and storage complete for '{inferred_business_type}' business.")
        return True

    except Exception as e:
        print(f"Error in agent_generate_simulated_data: {e}")
        return False


# --- Main function for independent testing ---
if __name__ == "__main__":
    # from ...shared_libraries import constants
    print("--- Starting independent tool testing ---")

    # # --- Test 1: Check Business Exists (initial search) ---
    # print("\nAttempting to find 'Test Business 123' (should not exist initially)...")
    # existing_businesses = db_check_business_exists("Bean & Brew Cafe")
    # print(f"Result for 'Test Business 123': {existing_businesses}")
    # if not existing_businesses:
    #     print("Test 1 Passed: 'Test Business 123' correctly reported as not found.")
    # else:
    #     print("Test 1 Failed: 'Test Business 123' found unexpectedly.")

    # --- Test 2: Create a New Business ---
    # print("\nCreating a new business: 'My Test Shop'...")
    # new_business_details = db_create_business(
    #     name="My Test Shop",
    #     address="123 Test St, Test City, TS 12345",
    #     business_type="Retail",
    #     description="A shop for testing purposes.",
    #     gmb_id="test_gmb_id",
    #     owner_contact="test@example.com"
    # )
    # if new_business_details:
    #     print(f"Test 2 Passed: New business created: {new_business_details}")
    #     created_business_id = new_business_details['business_id']
    # else:
    #     print("Test 2 Failed: Business creation failed.")
    #     created_business_id = None # Ensure it's None if creation failed

    # # --- Test 3: Check if the Newly Created Business Exists ---
    # if created_business_id:
    #     print(f"\nChecking for newly created business: '{new_business_details['name']}'...")
    #     found_created_business = db_check_business_exists(new_business_details['name'])
    #     if found_created_business and any(b['business_id'] == created_business_id for b in found_created_business):
    #         print(f"Test 3 Passed: Newly created business '{new_business_details['name']}' found.")
    #     else:
    #         print("Test 3 Failed: Newly created business not found or ID mismatch.")
    # else:
    #     print("\nSkipping Test 3: Business not created in previous step.")


    # --- Test 4: Search Google Maps ---
    # print("\nSearching Google Maps for 'Starbucks Houston Galleria'...")
    # gmaps_results = Maps_search_business("Starbucks Houston Galleria")
    # if gmaps_results:
    #     print(f"Test 4 Passed: Found {len(gmaps_results)} results from Google Maps.")
    #     for i, res in enumerate(gmaps_results[:3]): # Print first 3 results
    #         print(f"  Result {i+1}: Name: {res.get('name')}, Address: {res.get('address')}, Place ID: {res.get('place_id')}")
    # else:
    #     print("Test 4 Failed: No results from Google Maps.")


    # --- Test 5: Check Competitors (for the new business, should be empty) ---
    # created_business_id='biz_629fd84f'
    # if created_business_id:
    #     print(f"\nChecking competitors for created_business_id (should be empty initially)...")
    #     competitors = db_check_competitors_exist(created_business_id)
    #     if not competitors:
    #         print(f"Test 5 Passed: No competitors found for created_business_id")
    #     else:
    #         print(f"Test 5 Failed: Unexpected competitors found: {competitors}")
    # else:
    #     print("\nSkipping Test 5: Business not created.")

    # --- Test 6: Add a Competitor ---
    # if created_business_id:
    #     print(f"\nAdding competitor 'Competitor Co.' to created_business_id...")
    #     competitor_added = db_add_competitor(
    #         business_id=created_business_id,
    #         competitor_name="Competitor Co.",
    #         website_url="https://competitor.com",
    #         google_place_id="comp_place_id_123"
    #     )
    #     if competitor_added:
    #         print("Test 6 Passed: Competitor 'Competitor Co.' added successfully.")
    #     else:
    #         print("Test 6 Failed: Failed to add competitor.")
    # else:
    #     print("\nSkipping Test 6: Business not created.")

    # --- Test 7: Check Competitors (after adding one) ---
    # if created_business_id:
    #     print(f"\nRe-checking competitors for created_business_id (should now have one)...")
    #     competitors_after_add = db_check_competitors_exist(created_business_id)
    #     if competitors_after_add and len(competitors_after_add) == 1 and competitors_after_add[0]['name'] == 'Competitor Co.':
    #         print(f"Test 7 Passed: Found 1 competitor: {competitors_after_add[0]['name']}.")
    #     else:
    #         print(f"Test 7 Failed: Expected 1 competitor, found: {competitors_after_add}")
    # else:
    #     print("\nSkipping Test 7: Business not created.")

    # --- Test 8: Generate Simulated Data ---
    created_business_id= 'biz_629fd84f'
    if created_business_id:
        print(f"\nGenerating simulated data for business ID '{created_business_id}' (Type: 'Coffee Shop')...")
        simulated_data_generated = agent_generate_simulated_data(created_business_id, "Coffee Shop")
        if simulated_data_generated:
            print("Test 8 Passed: Simulated data generated and stored successfully.")
        else:
            print("Test 8 Failed: Simulated data generation failed.")
    else:
        print("\nSkipping Test 8: Business not created.")

    print("\n--- Independent tool testing complete ---")