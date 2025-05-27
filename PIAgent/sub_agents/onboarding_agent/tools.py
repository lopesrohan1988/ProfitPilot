# Assuming google.adk.tools and bigquery are available
from google.cloud import bigquery
from google.adk.tools import ToolContext # Keep this for general ADK compatibility
from typing import Optional, List, Dict, Any, Union

# --- Simulated Database (for demonstration purposes) ---
_businesses_db = {}  # {business_id: {name, address, type, description, gmb_id, owner_contact}}
_competitors_db = {} # {business_id: [{comp_name, website, google_place_id}, ...]}
_next_business_id = 1

# --- BigQuery Client (as per your example, though not strictly used in simulations) ---
try:
    client = bigquery.Client(location='US')
except Exception as e:
    print(f"Error initializing BigQuery client: {e}")
    client = None

# --- Tool Functions for Onboarding Agent ---

# NOTE: For ADK, when you define a function directly in the 'tools' list for an agent,
# the LLM will try to call it by matching *named parameters*.
# The 'tool_context' argument is typically used for things like the raw user query
# or other ADK-specific context, but for structured data input,
# direct named parameters are often more reliable for LLM inference.


def db_check_business_exists(business_name: str) -> List[Dict[str, Any]]:
    """
    Checks if a business with the given name already exists in the system.
    Returns a list of business details if found (can be empty, single, or multiple matches).

    Args:
        business_name (str): The name of the business to check.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries, where each dictionary contains
                              business details (e.g., 'business_id', 'name', 'address', etc.).
                              Returns an empty list if no matches are found.
    """
    print(f"ADK Tool Call: db_check_business_exists(business_name='{business_name}')")
    matches = []
    # Simulate some existing businesses for testing
    if not _businesses_db: # Populate if empty for initial testing
        global _next_business_id
        _businesses_db["biz_00001"] = {
            "business_id": "biz_00001",
            "name": "Acme Corp",
            "address": "101 Main St, Anytown",
            "type": "Manufacturing",
            "description": "Produces widgets",
            "gmb_id": "gmb_acme",
            "owner_contact": "contact@acmecorp.com"
        }
        _next_business_id += 1
        _businesses_db["biz_00002"] = {
            "business_id": "biz_00002",
            "name": "Acme Widgets",
            "address": "202 Elm St, Otherville",
            "type": "Retail",
            "description": "Sells widgets",
            "gmb_id": None,
            "owner_contact": "sales@acmewidgets.com"
        }
        _next_business_id += 1

    for biz_id, biz_details in _businesses_db.items():
        # Using 'in' for a simple 'like' simulation
        if business_name.lower() in biz_details['name'].lower():
            print(f"Simulation: Business '{biz_details['name']}' found with ID '{biz_id}'.")
            matches.append({"business_id": biz_id, **biz_details})

    if not matches:
        print(f"Simulation: Business '{business_name}' not found in internal DB.")
    return matches


def db_create_business(name: str, address: str, business_type: str, description: str,
                       gmb_id: Optional[str] = None, owner_contact: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Registers a new business in the system (SIMULATED).
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
    global _next_business_id
    business_id = f"biz_{_next_business_id:05d}"
    _next_business_id += 1

    business_details = {
        "business_id": business_id,
        "name": name,
        "address": address,
        "type": business_type,
        "description": description,
        "gmb_id": gmb_id,
        "owner_contact": owner_contact
    }
    _businesses_db[business_id] = business_details
    _competitors_db[business_id] = [] # Initialize empty list for competitors

    print(f"ADK Tool Call: db_create_business(name='{name}', address='{address}', business_type='{business_type}', description='{description}', gmb_id='{gmb_id}', owner_contact='{owner_contact}')")
    print(f"Simulation: Business '{name}' created with ID '{business_id}'. Details: {_businesses_db[business_id]}")
    return business_details


def db_check_competitors_exist(business_id: str) -> List[Dict[str, Any]]:
    """
    Checks if any competitors are already set up for a given business ID (SIMULATED).
    Returns a list of competitor details if found.

    Args:
        business_id (str): The ID of the business to check.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries, where each dictionary contains
                              competitor details ('name', 'website_url', 'google_place_id').
                              Returns an empty list if no competitors are found.
    """
    print(f"ADK Tool Call: db_check_competitors_exist(business_id='{business_id}')")
    competitors = _competitors_db.get(business_id, [])
    if competitors:
        print(f"Simulation: Competitors found for business ID '{business_id}': {competitors}")
        return competitors
    print(f"Simulation: No competitors found for business ID '{business_id}'.")
    return []

def db_add_competitor(business_id: str, competitor_name: str, website_url: str,
                      google_place_id: Optional[str] = None) -> bool:
    """
    Adds a competitor to an existing business in the system (SIMULATED).

    Args:
        business_id (str): The ID of the business to associate the competitor with.
        competitor_name (str): The name of the competitor.
        website_url (str): The website URL of the competitor.
        google_place_id (Optional[str]): Google Place ID for the competitor.

    Returns:
        bool: True if the competitor was successfully added, False otherwise.
    """
    print(f"ADK Tool Call: db_add_competitor(business_id='{business_id}', competitor_name='{competitor_name}', website_url='{website_url}', google_place_id='{google_place_id}')")
    if business_id not in _businesses_db:
        print(f"Simulation: Error - Business ID '{business_id}' does not exist.")
        return False

    competitor_details = {
        "name": competitor_name,
        "website_url": website_url,
        "google_place_id": google_place_id
    }
    _competitors_db[business_id].append(competitor_details)
    print(f"Simulation: Competitor '{competitor_name}' added to business ID '{business_id}'. Current competitors: {_competitors_db[business_id]}")
    return True

def Maps_search_business(query: str, location_bias: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
    """
    Searches Google Maps for business information (SIMULATED).

    Args:
        query (str): The business name and/or address (e.g., "Nike 8887 Thornel St Houston").
        location_bias (Optional[Dict[str, float]]): Dictionary with 'lat' and 'lng' for biasing results (not used in simulation).

    Returns:
        List[Dict[str, Any]]: A list of dictionaries, each representing a found business
                              with keys like 'name', 'address', 'place_id', 'website', 'phone_number'.
    """
    print(f"ADK Tool Call: Maps_search_business(query='{query}')")
    results = []
    # Simulate some potential results based on the query for testing
    if "nike" in query.lower():
        results = [
            {"name": "Nike Store Galleria", "address": "5085 Westheimer Rd, Houston, TX 77056", "place_id": "ChIJV4k8v_1Xj4ARjQfT6_jW36k", "website": "nike.com/galleria", "phone_number": "+1 713-555-1212"},
            {"name": "Nike Clearance Store", "address": "123 Outlet Mall Dr, Houston, TX 77000", "place_id": "ChIJabCdefG7j4ARutYjKLM9012", "website": "nike.com/clearance", "phone_number": "+1 713-555-1213"},
        ]
    elif "starbucks" in query.lower():
         results = [
            {"name": "Starbucks Houston Downtown", "address": "100 Main St, Houston, TX 77002", "place_id": "ChIJ1234567890abcdefghijk", "website": "starbucks.com/downtown", "phone_number": "+1 713-555-1214"},
        ]
    else:
        results = []  # No results found
    print(f"Simulation: Found {len(results)} businesses on Google Maps for '{query}'.")
    return results

# NOTE: The ToolContext parameter is typically for tools that consume the raw user query
# or ADK-specific contextual data. For structured data collected by the agent for
# a tool call, defining named parameters as above is usually the more robust pattern
# as the LLM is better at identifying and mapping values to these names.