import uuid
from google.cloud import bigquery
import os
from typing import Optional, List, Dict, Any, Union

# Import the new Places API client library
from google.maps import places_v1 as places # This is the most common and correct way to import the new Places API client
from google.api_core.exceptions import GoogleAPIError

# --- BigQuery Configuration ---
PROJECT_ID = 'profitpilot-2cc51'
DATASET_ID = 'profitpilot_data'
TABLE_BUSINESS = f"{PROJECT_ID}.{DATASET_ID}.business"
TABLE_COMPETITOR = f"{PROJECT_ID}.{DATASET_ID}.competitor"

# --- BigQuery Client Initialization ---
try:
    bq_client = bigquery.Client(project=PROJECT_ID, location='US')
    print(f"BigQuery client initialized for project: {PROJECT_ID}")
except Exception as e:
    print(f"Error initializing BigQuery client: {e}")
    bq_client = None

# --- Google Maps API Configuration ---
# The new Places API client doesn't use a simple API key directly in its constructor
# for most methods. It typically relies on Application Default Credentials (ADC).
# However, you *can* pass an API key directly if desired for specific use cases
# by setting it in the environment variable GOOGLE_API_KEY.
# For simplicity in this example, we'll initialize the client directly.
# Ensure your environment is authenticated via `gcloud auth application-default login`
# or set GOOGLE_API_KEY if you're using API key authentication for the new API.
# The `google-maps-places` library will attempt to use ADC by default.

# Initialize the new Places API client
# No direct API key needed in the constructor if using ADC.
try:
    places_client = places.PlacesClient()
    print("New Google Places API client initialized.")
except Exception as e:
    print(f"Error initializing New Google Places API client: {e}")
    places_client = None


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
    print(f"\n--- ADK Tool Call: db_check_business_exists(business_name='{business_name}') ---")
    if not bq_client:
        print("BigQuery client not initialized. Cannot check business existence.")
        return []

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
            owner_contact = row.owner_contact_info
            if isinstance(owner_contact, dict) and "primary" in owner_contact:
                owner_contact = owner_contact["primary"]
            elif isinstance(owner_contact, str):
                try:
                    import json
                    parsed_contact = json.loads(owner_contact)
                    if isinstance(parsed_contact, dict) and "primary" in parsed_contact:
                        owner_contact = parsed_contact["primary"]
                except json.JSONDecodeError:
                    pass

            matches.append({
                "id": row.id,
                "gmb_id": row.g_m_b_id,
                "address": row.address,
                "business_id": row.business_id,
                "business_type": row.business_type,
                "description": row.description,
                "name": row.name,
                "owner_contact": owner_contact
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
    print(f"\n--- ADK Tool Call: db_create_business(name='{name}', address='{address}', business_type='{business_type}', description='{description}', gmb_id='{gmb_id}', owner_contact='{owner_contact}') ---")
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

    owner_contact_json_val = {"primary": owner_contact} if owner_contact else {}
    import json
    owner_contact_info_str = json.dumps(owner_contact_json_val)

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
    print(f"\n--- ADK Tool Call: db_check_competitors_exist(business_id='{business_id}') ---")
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
    print(f"\n--- ADK Tool Call: db_add_competitor(business_id='{business_id}', competitor_name='{competitor_name}', website_url='{website_url}', google_place_id='{google_place_id}') ---")
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


# --- MIGRATED Maps_search_business function ---
# --- MIGRATED Maps_search_business function ---
def Maps_search_business(query: str, location_bias: Optional[Dict[str, float]] = None) -> List[Dict[str, Any]]:
    """
    Searches Google Maps for business information using the NEW Google Places API.
    It performs a Text Search and explicitly requests fields like website and phone number.

    Args:
        query (str): The business name and/or address (e.g., "Nike 8887 Thornel St Houston").
        location_bias (Optional[Dict[str, float]]): Dictionary with 'lat' and 'lng' for biasing results.
                                                     E.g., {'lat': 29.7604, 'lng': -95.3698}

    Returns:
        List[Dict[str, Any]]: A list of dictionaries, each representing a found business
                              with keys like 'name', 'address', 'place_id', 'website', 'phone_number'.
    """
    print(f"\n--- ADK Tool Call: Maps_search_business(query='{query}', location_bias={location_bias}) (New Places API) ---")
    if not places_client:
        print("New Google Places API client not initialized. Cannot search businesses.")
        return []

    try:
        # Define the location bias if provided
       
        # Define the fields you want to retrieve.
        # Note: New API uses 'websiteUri' and 'internationalPhoneNumber' as attribute names.
        # Also, formattedAddress and displayName are nested under Place.
        # place.id is the Place ID.
        field_mask = [
            "places.displayName",
            "places.formattedAddress",
            "places.id", # This is the Place ID
            "places.websiteUri", # New field name for website
            "places.internationalPhoneNumber", # New field name for phone number
            "places.location" # Includes lat/lng if you need them later
        ]

        request = places.SearchTextRequest(
            text_query=query,
            
            fields=field_mask # Specify the fields you want
        )

        # Perform the search
        response = places_client.search_text(request=request)

        results = []
        for place_obj in response.places:
            # Access data from the Place object returned by the new API
            results.append({
                'name': place_obj.display_name.text if place_obj.display_name else None,
                'address': place_obj.formatted_address,
                'place_id': place_obj.id, # The unique place ID
                'website': place_obj.website_uri, # Access website URI
                'phone_number': place_obj.international_phone_number # Access international phone number
            })

        print(f"New Google Places API: Found {len(results)} businesses for '{query}'.")
        return results

    except GoogleAPIError as e:
        print(f"Google Places API (New) Error: {e.message}")
        print("Ensure 'Places API (New)' is enabled in your Google Cloud project and credentials are correct.")
        return []
    except Exception as e:
        print(f"Error searching Google Maps (New API): {e}")
        return []
    
# --- Main function for independent testing ---
if __name__ == "__main__":
    print("--- Starting independent tool testing (New Places API) ---")

    # # --- Test 1: Check Business Exists (initial search) ---
    # print("\nAttempting to find 'Test Business 123' (should not exist initially)...")
    # existing_businesses = db_check_business_exists("Test Business 123")
    # print(f"Result for 'Test Business 123': {existing_businesses}")
    # if not existing_businesses:
    #     print("Test 1 Passed: 'Test Business 123' correctly reported as not found.")
    # else:
    #     print("Test 1 Failed: 'Test Business 123' found unexpectedly.")

    # # --- Test 2: Create a New Business ---
    # print("\nCreating a new business: 'My Test Shop V2'...")
    # new_business_details = db_create_business(
    #     name="My Test Shop V2",
    #     address="456 New Test Ln, New City, NL 67890",
    #     business_type="Retail",
    #     description="A shop for testing purposes with New API.",
    #     gmb_id="test_gmb_id_v2",
    #     owner_contact="test_v2@example.com"
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


    # --- Test 4: Search Google Maps (New API - expecting website/phone) ---
    print("\nSearching Google Maps (New API) for 'Starbucks The Galleria Houston' (expecting website/phone)...")
    # Location bias for Houston, TX
    # houston_galleria_bias = {'lat': 29.7277, 'lng': -95.4627}
    gmaps_results = Maps_search_business("Starbucks The Galleria Houston")
    if gmaps_results:
        print(f"Test 4 Passed: Found {len(gmaps_results)} results from New Google Places API.")
        for i, res in enumerate(gmaps_results[:3]): # Print first 3 results
            print(f"  Result {i+1}: Name: {res.get('name')}, Address: {res.get('address')}, Place ID: {res.get('place_id')}, Website: {res.get('website')}, Phone: {res.get('phone_number')}")
            if res.get('website') or res.get('phone_number'):
                print("    (Website/Phone found for this entry - GOOD!)")
            else:
                print("    (Website/Phone NOT found for this entry - potentially missing from Google data)")
    else:
        print("Test 4 Failed: No results from New Google Places API.")


    # # --- Test 5: Check Competitors (for the new business, should be empty) ---
    # if created_business_id:
    #     print(f"\nChecking competitors for '{new_business_details['name']}' (should be empty initially)...")
    #     competitors = db_check_competitors_exist(created_business_id)
    #     if not competitors:
    #         print(f"Test 5 Passed: No competitors found for {new_business_details['name']}.")
    #     else:
    #         print(f"Test 5 Failed: Unexpected competitors found: {competitors}")
    # else:
    #     print("\nSkipping Test 5: Business not created.")

    # # --- Test 6: Add a Competitor ---
    # if created_business_id:
    #     print(f"\nAdding competitor 'New Competitor Co.' to '{new_business_details['name']}'...")
    #     # Search for competitor details using Maps_search_business to get place_id, website, phone
    #     competitor_search_query = "Foot Locker The Galleria Houston"
    #     competitor_maps_results = Maps_search_business(competitor_search_query, location_bias=houston_galleria_bias)
    #     competitor_to_add = None
    #     if competitor_maps_results:
    #         competitor_to_add = competitor_maps_results[0] # Take the first result
    #         print(f"  Found competitor details via Maps (New API): {competitor_to_add}")

    #         competitor_added = db_add_competitor(
    #             business_id=created_business_id,
    #             competitor_name=competitor_to_add.get('name', "Unknown Competitor"),
    #             website_url=competitor_to_add.get('website', ""), # Use fetched website
    #             google_place_id=competitor_to_add.get('place_id')
    #         )
    #         if competitor_added:
    #             print("Test 6 Passed: Competitor 'Foot Locker' added successfully using New Maps API data.")
    #         else:
    #             print("Test 6 Failed: Failed to add competitor.")
    #     else:
    #         print(f"  Could not find '{competitor_search_query}' on Maps (New API). Adding with dummy data.")
    #         competitor_added = db_add_competitor(
    #             business_id=created_business_id,
    #             competitor_name="Foot Locker (Manual V2)",
    #             website_url="https://footlocker.com",
    #             google_place_id="manual_comp_place_id_v2"
    #         )
    #         if competitor_added:
    #             print("Test 6 Passed: Competitor 'Foot Locker (Manual V2)' added successfully.")
    #         else:
    #             print("Test 6 Failed: Failed to add competitor.")
    # else:
    #     print("\nSkipping Test 6: Business not created.")

    # # --- Test 7: Check Competitors (after adding one) ---
    # if created_business_id:
    #     print(f"\nRe-checking competitors for '{new_business_details['name']}' (should now have one)...")
    #     competitors_after_add = db_check_competitors_exist(created_business_id)
    #     if competitors_after_add and len(competitors_after_add) == 1 and ('Foot Locker' in competitors_after_add[0]['name'] or 'Foot Locker (Manual V2)' in competitors_after_add[0]['name']):
    #         print(f"Test 7 Passed: Found 1 competitor: {competitors_after_add[0]['name']} with website: {competitors_after_add[0]['website_url']}.")
    #     else:
    #         print(f"Test 7 Failed: Expected 1 competitor, found: {competitors_after_add}")
    # else:
    #     print("\nSkipping Test 7: Business not created.")


    print("\n--- Independent tool testing complete (New Places API) ---")