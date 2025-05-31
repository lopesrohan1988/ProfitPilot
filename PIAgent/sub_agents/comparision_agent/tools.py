import uuid
from google.cloud import bigquery
import os
from typing import Optional, List, Dict, Any, Union
import json 
import datetime

# Import the new Places API client library
import googlemaps
from google.api_core.exceptions import GoogleAPIError

import google.generativeai as genai 
import dotenv
dotenv.load_dotenv()
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

def db_get_competitors(business_id: str) -> List[Dict[str, Any]]:
    """
    Retrieves a list of competitors for a given business ID from the database.
    This function specifically queries the 'competitor' table.

    Args:
        business_id (str): The ID of the primary business.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries, where each dictionary contains
                              competitor details (e.g., 'name', 'website_url', 'google_place_id', 'competitor_id').
                              Returns an empty list if no competitors are found.
    """
    print(f"\n--- Comparative Agent Tool Call: db_get_competitors(business_id='{business_id}') ---")
    if not bq_client:
        print("BigQuery client not initialized. Cannot retrieve competitors.")
        return []

    query = f"""
    SELECT
        name, website_url, google_place_id, competitor_id
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
                "google_place_id": row.google_place_id,
                "competitor_id": row.competitor_id
            })

        if not competitors:
            print(f"BigQuery: No competitors found for business ID '{business_id}'.")
        else:
            print(f"BigQuery: Found {len(competitors)} competitors for business ID '{business_id}'.")
        return competitors

    except Exception as e:
        print(f"Error getting competitors from BigQuery: {e}")
        return []


def db_get_business_details(business_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves the full details of a business from the database using its internal business_id.

    Args:
        business_id (str): The internal ID of the business.

    Returns:
        Optional[Dict[str, Any]]: A dictionary containing the business's details
                                  (e.g., 'id', 'gmb_id', 'name', 'address', 'business_id'),
                                  or None if not found.
    """
    print(f"\n--- Comparative Agent Tool Call: db_get_business_details(business_id='{business_id}') ---")
    if not bq_client:
        print("BigQuery client not initialized. Cannot retrieve business details.")
        return None

    query = f"""
    SELECT
        id, g_m_b_id, address, business_id, business_type, description, name, owner_contact_info
    FROM
        `{TABLE_BUSINESS}`
    WHERE
        business_id = @business_id
    LIMIT 1
    """
    query_params = [
        bigquery.ScalarQueryParameter("business_id", "STRING", business_id)
    ]

    try:
        query_job = bq_client.query(query, job_config=bigquery.QueryJobConfig(query_parameters=query_params))
        row = next(iter(query_job.result()), None)

        if row:
            owner_contact = row.owner_contact_info
            if isinstance(owner_contact, dict) and "primary" in owner_contact:
                owner_contact = owner_contact["primary"]
            elif isinstance(owner_contact, str):
                try:
                    parsed_contact = json.loads(owner_contact)
                    if isinstance(parsed_contact, dict) and "primary" in parsed_contact:
                        owner_contact = parsed_contact["primary"]
                except json.JSONDecodeError:
                    pass

            business_details = {
                "id": row.id,
                "gmb_id": row.g_m_b_id,
                "address": row.address,
                "business_id": row.business_id,
                "business_type": row.business_type,
                "description": row.description,
                "name": row.name,
                "owner_contact": owner_contact
            }
            print(f"BigQuery: Found business details for '{business_id}'.")
            return business_details
        else:
            print(f"BigQuery: Business with ID '{business_id}' not found.")
            return None

    except Exception as e:
        print(f"Error getting business details from BigQuery: {e}")
        return None
    
def maps_get_place_reviews(place_id: str) -> List[Dict[str, Any]]:
    """
    Retrieves reviews for a given Google Place ID using the OLDER Google Places API (Place Details).

    Args:
        place_id (str): The Google Place ID of the business/competitor.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries, each representing a review.
                              Each review dict includes 'rating', 'text', 'author_name', 'author_uri', 'publish_time'.
                              Returns an empty list if no reviews or an error occurs.
    """
    print(f"\n--- Comparative Agent Tool Call: maps_get_place_reviews(place_id='{place_id}') ---")
    if not places_client:
        print("Older Google Places API client not initialized. Cannot get place reviews.")
        return []

    try:
        place_details = places_client.place(
            place_id=place_id,
            fields=['reviews']
        )

        reviews = []
        if 'result' in place_details and 'reviews' in place_details['result']:
            for review_obj in place_details['result']['reviews']:
                # Convert Unix timestamp to ISO 8601 string for BigQuery
                publish_time_iso = None
                if 'time' in review_obj and review_obj['time'] is not None:
                    try:
                        # The 'time' field is usually Unix timestamp in seconds
                        publish_time_iso = datetime.datetime.fromtimestamp(
                            review_obj['time'], tz=datetime.timezone.utc
                        ).isoformat()
                    except Exception as dt_err:
                        print(f"Warning: Could not convert timestamp {review_obj['time']} for review: {dt_err}")
                        publish_time_iso = None # Keep as None if conversion fails


                reviews.append({
                    'rating': review_obj.get('rating'),
                    'text': review_obj.get('text'),
                    'author_name': review_obj.get('author_name'),
                    'author_uri': review_obj.get('author_url'), # Older API uses 'author_url'
                    'publish_time': publish_time_iso # Use the converted ISO format
                })
        
        print(f"Google Places API (Older): Found {len(reviews)} reviews for Place ID '{place_id}'.")
        if len(reviews) == 5:
            print("Note: The Older Google Places API (Place Details) typically returns a maximum of 5 reviews.")
        return reviews

    except googlemaps.exceptions.ApiError as e:
        print(f"Google Places API (Older) Error getting reviews for '{place_id}': {e}")
        print("Ensure 'Places API' (NOT 'Places API (New)') is enabled in your Google Cloud project and API Key is correct.")
        return []
    except Exception as e:
        print(f"Error getting place reviews (Older API) for '{place_id}': {e}")
        return []


def db_store_processed_review(
    review_data: Dict[str, Any],
    business_id: str,
    review_source: str, # e.g., "Google Maps"
    entity_type: str, # "business" or "competitor"
    review_id: str # The external review ID (e.g., from Google Places)
) -> bool:
    """
    Stores a *single processed review* into the `business_review` BigQuery table.

    Args:
        review_data (Dict[str, Any]): A dictionary containing the processed review data
                                      conforming to the `business_review` schema.
                                      Expected keys: 'rating', 'text', 'publish_time',
                                      'sentiment_score', 'sentiment_magnitude', 'entities', 'themes', 'entity_sentiment'.
        business_id (str): The internal ID of the primary business this review belongs to.
        review_source (str): The source of the review (e.g., "Google Maps").
        entity_type (str): Whether the review is for the "business" or a "competitor".
        review_id (str): The unique identifier for this review from its source (e.g., Google Places)

    Returns:
        bool: True if storage was successful, False otherwise.
    """
    print(f"\n--- Comparative Agent Tool Call: db_store_processed_review ---")
    if not bq_client:
        print("BigQuery client not initialized. Cannot store processed review.")
        return False

    id_uuid = str(uuid.uuid4())
    raw_text_hash_val = str(hash(review_data.get('text', ''))) # Simple hash for raw text uniqueness

    # Ensure JSON fields are properly serialized
    entity_sentiment_json = json.dumps(review_data.get('entity_sentiment', {}))

    query = f"""
    INSERT INTO `{TABLE_BUSINESS_REVIEW}` (
        id, business_id, entities, entity_sentiment, processed_timestamp,
        rating, raw_text_hash, review_id, sentiment_magnitude, sentiment_score,
        source, text, themes, timestamp_posted, entity_type
    ) VALUES (
        @id, @business_id, @entities, @entity_sentiment, @processed_timestamp,
        @rating, @raw_text_hash, @review_id, @sentiment_magnitude, @sentiment_score,
        @source, @text, @themes, @timestamp_posted, @entity_type
    )
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("id", "STRING", id_uuid),
            bigquery.ScalarQueryParameter("business_id", "STRING", business_id),
            bigquery.ArrayQueryParameter("entities", "STRING", review_data.get('entities', [])),
            bigquery.ScalarQueryParameter("entity_sentiment", "JSON", entity_sentiment_json),
            bigquery.ScalarQueryParameter("processed_timestamp", "TIMESTAMP", review_data.get('processed_timestamp', None)),
            bigquery.ScalarQueryParameter("rating", "FLOAT64", review_data.get('rating')),
            bigquery.ScalarQueryParameter("raw_text_hash", "STRING", raw_text_hash_val),
            bigquery.ScalarQueryParameter("review_id", "STRING", review_id),
            bigquery.ScalarQueryParameter("sentiment_magnitude", "FLOAT64", review_data.get('sentiment_magnitude')),
            bigquery.ScalarQueryParameter("sentiment_score", "FLOAT64", review_data.get('sentiment_score')),
            bigquery.ScalarQueryParameter("source", "STRING", review_source),
            bigquery.ScalarQueryParameter("text", "STRING", review_data.get('text')),
            bigquery.ArrayQueryParameter("themes", "STRING", review_data.get('themes', [])),
            bigquery.ScalarQueryParameter("timestamp_posted", "TIMESTAMP", review_data.get('publish_time')),
            bigquery.ScalarQueryParameter("entity_type", "STRING", entity_type)
        ]
    )

    try:
        query_job = bq_client.query(query, job_config=job_config)
        query_job.result()
        print(f"BigQuery: Successfully stored processed review for business ID '{business_id}'.")
        return True
    except Exception as e:
        print(f"Error storing processed review to BigQuery: {e}")
        return False


def db_get_processed_reviews(business_id: str, entity_type: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieves processed review data for a business or its competitors from the `business_review` table.

    Args:
        business_id (str): The ID of the primary business.
        entity_type (Optional[str]): Filter by 'business' or 'competitor'. If None, retrieves all.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries, each representing a processed review.
    """
    print(f"\n--- Comparative Agent Tool Call: db_get_processed_reviews(business_id='{business_id}', entity_type='{entity_type}') ---")
    if not bq_client:
        print("BigQuery client not initialized. Cannot retrieve processed reviews.")
        return []

    query = f"""
    SELECT
        id, business_id, entities, entity_sentiment, processed_timestamp,
        rating, raw_text_hash, review_id, sentiment_magnitude, sentiment_score,
        source, text, themes, timestamp_posted, entity_type
    FROM
        `{TABLE_BUSINESS_REVIEW}`
    WHERE
        business_id = @business_id
    """
    query_params = [
        bigquery.ScalarQueryParameter("business_id", "STRING", business_id)
    ]

    if entity_type:
        query += " AND entity_type = @entity_type"
        query_params.append(bigquery.ScalarQueryParameter("entity_type", "STRING", entity_type))
    
    query += " ORDER BY timestamp_posted DESC" # Order by most recent reviews

    processed_reviews = []
    try:
        query_job = bq_client.query(query, job_config=bigquery.QueryJobConfig(query_parameters=query_params))
        rows = query_job.result()

        for row in rows:
            # Handle JSON parsing for entity_sentiment
            entity_sentiment_parsed = {}
            if row.entity_sentiment:
                try:
                    entity_sentiment_parsed = json.loads(row.entity_sentiment)
                except (json.JSONDecodeError, TypeError):
                    print(f"Warning: Could not parse entity_sentiment JSON for review ID {row.review_id}")
                    entity_sentiment_parsed = {}

            processed_reviews.append({
                "id": row.id,
                "business_id": row.business_id,
                "entities": row.entities,
                "entity_sentiment": entity_sentiment_parsed,
                "processed_timestamp": row.processed_timestamp.isoformat() if row.processed_timestamp else None,
                "rating": row.rating,
                "raw_text_hash": row.raw_text_hash,
                "review_id": row.review_id,
                "sentiment_magnitude": row.sentiment_magnitude,
                "sentiment_score": row.sentiment_score,
                "source": row.source,
                "text": row.text,
                "themes": row.themes,
                "timestamp_posted": row.timestamp_posted.isoformat() if row.timestamp_posted else None,
                "entity_type": row.entity_type
            })
        
        print(f"BigQuery: Retrieved {len(processed_reviews)} processed reviews for business ID '{business_id}' (entity_type: {entity_type or 'all'}).")
        return processed_reviews

    except Exception as e:
        print(f"Error retrieving processed reviews from BigQuery: {e}")
        return []


def agent_call_customer_sentiment_analyst_for_reviews(business_id: str, competitor_ids: List[str]) -> bool:
    """
    Calls Google Maps Places API to get raw reviews for the main business and its competitors.
    It then stores these raw reviews directly into the `business_review` BigQuery table.

    Args:
        business_id (str): The ID of the primary business that *owns* this review collection task.
                           (Used to fetch business details and competitor details).
        competitor_ids (List[str]): A list of internal competitor IDs whose reviews need to be collected.

    Returns:
        bool: True if raw review collection and storage was successfully initiated, False otherwise.
    """
    print(f"\n--- Comparative Agent Tool Call: agent_call_customer_sentiment_analyst_for_reviews ---")
    
    business_details = db_get_business_details(business_id) # This business_id refers to your main business
    if not business_details or not business_details.get('gmb_id'):
        print(f"Error: Could not retrieve main business details or Google Place ID for business_id '{business_id}'.")
        return False

    main_business_place_id = business_details['gmb_id']
    main_business_internal_id = business_details['business_id'] # This is the ID of YOUR main business
    main_business_name = business_details.get('name', 'Your Business')

    # Collect and store raw reviews for the main business
    print(f"Retrieving and storing raw reviews for main business '{main_business_name}' (Place ID: {main_business_place_id})...")
    raw_business_reviews = maps_get_place_reviews(main_business_place_id)
    
    for i, review in enumerate(raw_business_reviews):
        full_review_data = {
            "rating": review.get('rating'),
            "text": review.get('text'),
            "publish_time": review.get('publish_time'),
            "sentiment_score": 0.0,
            "sentiment_magnitude": 0.0,
            "entities": [],
            "themes": [],
            "entity_sentiment": {},
            "processed_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        review_id_from_source = f"gmb_{main_business_place_id}_{i}_{str(hash(review.get('text', '')))}"

        db_store_processed_review(
            review_data=full_review_data,
            business_id=main_business_internal_id, # Store your main business's ID
            review_source="Google Maps",
            entity_type="business",
            review_id=review_id_from_source
        )

    # Collect and store raw reviews for competitors
    competitors_db = db_get_competitors(business_id) # Still get competitors linked to your main business
    filtered_competitors = [
        comp for comp in competitors_db if comp.get('competitor_id') in competitor_ids
    ]

    for comp in filtered_competitors:
        comp_name = comp.get('name', 'Unknown Competitor')
        comp_place_id = comp.get('google_place_id')
        comp_internal_id = comp.get('competitor_id') # This is the ID of the competitor to store

        if comp_place_id and comp_internal_id:
            print(f"Retrieving and storing raw reviews for competitor '{comp_name}' (Place ID: {comp_place_id})...")
            raw_comp_reviews = maps_get_place_reviews(comp_place_id)
            
            for i, review in enumerate(raw_comp_reviews):
                full_review_data = {
                    "rating": review.get('rating'),
                    "text": review.get('text'),
                    "publish_time": review.get('publish_time'),
                    "sentiment_score": 0.0,
                    "sentiment_magnitude": 0.0,
                    "entities": [],
                    "themes": [],
                    "entity_sentiment": {},
                    "processed_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                }
                review_id_from_source = f"gmb_{comp_place_id}_{i}_{str(hash(review.get('text', '')))}"

                db_store_processed_review(
                    review_data=full_review_data,
                    business_id=comp_internal_id, # Store the competitor's ID
                    review_source="Google Maps",
                    entity_type="competitor",
                    review_id=review_id_from_source
                )
        else:
            print(f"Warning: Competitor '{comp_name}' has no Google Place ID or internal ID. Skipping raw review collection.")

    print(f"Customer Sentiment Analyst: Raw review collection and storage complete.")
    return True


def generate_review_comparison_prompt(
    business_name: str,
    business_processed_reviews: List[Dict[str, Any]],
    competitor_processed_reviews_map: Dict[str, List[Dict[str, Any]]] 
) -> str:
    """
    Generates a detailed prompt for the Gemini API to compare *processed* reviews.
    This version can leverage sentiment, entities, and themes.

    Args:
        business_name (str): The name of the primary business.
        business_processed_reviews (List[Dict[str, Any]]): List of processed review dictionaries for the business.
        competitor_processed_reviews_map (Dict[str, List[Dict[str, Any]]]): Map of competitor names to their processed review lists.

    Returns:
        str: The constructed prompt string.
    """
    print(f"\n--- Comparative Agent Tool Call: generate_review_comparison_prompt (using processed data) ---")
    prompt_parts = [
        f"You are a highly analytical business intelligence expert. Your task is to perform a comparative sentiment and thematic analysis of customer reviews for '{business_name}' against its competitors.",
        "The reviews provided have already undergone preliminary sentiment and entity extraction. Leverage this information.",
        "Provide insights on strengths, weaknesses, common complaints, and unique selling propositions for each entity based on their reviews. Highlight key differences and opportunities for '{business_name}'.",
        "Structure your analysis clearly with sections for 'Overall Sentiment Summary', 'Key Themes and Entity Analysis', 'Strengths Identified', 'Weaknesses Identified', 'Opportunities for {business_name}', and 'Overall Competitive Comparison Summary'.", # Updated placeholder
        "Analyze trends and specific examples from the reviews to support your points. Focus on actionable insights.",
        "\n--- Processed Reviews for Your Business: ---"
    ]

    if not business_processed_reviews:
        prompt_parts.append(f"No processed reviews found for {business_name}.")
    else:
        for i, review in enumerate(business_processed_reviews[:15]): 
            text_snippet = review.get('text', 'No text available.')
            if text_snippet and len(text_snippet) > 200:
                text_snippet = text_snippet[:200] + "..."
            
            prompt_parts.append(f"Review for {business_name} (No. {i+1}):") # Explicitly name the business
            prompt_parts.append(f"  - Text: \"{text_snippet}\"")
            prompt_parts.append(f"  - Rating: {review.get('rating')} stars")
            prompt_parts.append(f"  - Sentiment: Score={review.get('sentiment_score', 0.0):.2f}, Magnitude={review.get('sentiment_magnitude', 0.0):.2f}")
            if review.get('themes'):
                prompt_parts.append(f"  - Themes: {', '.join(review['themes'])}")
            if review.get('entities'):
                prompt_parts.append(f"  - Entities: {', '.join(review['entities'])}")
            if review.get('entity_sentiment'):
                prompt_parts.append(f"  - Entity Sentiment: {json.dumps(review['entity_sentiment'])}")
            prompt_parts.append("") 

    for comp_name, reviews in competitor_processed_reviews_map.items():
        prompt_parts.append(f"\n--- Processed Reviews for Competitor: {comp_name} ---")
        if not reviews:
            prompt_parts.append(f"No processed reviews found for {comp_name}.")
        else:
            for i, review in enumerate(reviews[:15]): 
                text_snippet = review.get('text', 'No text available.')
                if text_snippet and len(text_snippet) > 200:
                    text_snippet = text_snippet[:200] + "..."
                
                prompt_parts.append(f"Review for {comp_name} (No. {i+1}):") # Explicitly name the competitor here
                prompt_parts.append(f"  - Text: \"{text_snippet}\"")
                prompt_parts.append(f"  - Rating: {review.get('rating')} stars")
                prompt_parts.append(f"  - Sentiment: Score={review.get('sentiment_score', 0.0):.2f}, Magnitude={review.get('sentiment_magnitude', 0.0):.2f}")
                if review.get('themes'):
                    prompt_parts.append(f"  - Themes: {', '.join(review['themes'])}")
                if review.get('entities'):
                    prompt_parts.append(f"  - Entities: {', '.join(review['entities'])}")
                if review.get('entity_sentiment'):
                    prompt_parts.append(f"  - Entity Sentiment: {json.dumps(review['entity_sentiment'])}")
                prompt_parts.append("") 

    return "\n".join(prompt_parts)

def call_gemini_api(prompt: str) -> Optional[str]:
    """
    Calls the Gemini API with the given prompt and returns the generated text.

    Args:
        prompt (str): The prompt for the Gemini model.

    Returns:
        Optional[str]: The generated text from the Gemini model, or None if an error occurs.
    """
    print(f"\n--- Comparative Agent Tool Call: call_gemini_api ---")
    if not gemini_model:
        print("Gemini model not initialized. Cannot call API.")
        return None
    if not prompt:
        print("Prompt is empty. Cannot call Gemini API.")
        return None

    try:
        response = gemini_model.generate_content(prompt)
        if response.text:
            print("Gemini API call successful.")
            return response.text
        else:
            print(f"Gemini API returned no text. Parts: {response.parts}, Prompt Feedback: {response.prompt_feedback}")
            return None
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        return None


def agent_call_competitive_edge_analyst(main_business_id: str) -> Optional[str]:
    """
    Calls the Competitive Edge Analyst to perform a comparison on *processed reviews*
    using the Gemini API.

    Args:
        main_business_id (str): The ID of the primary business for which to perform the comparison.

    Returns:
        Optional[str]: The comparative analysis results from the Gemini API, or None if analysis fails.
    """
    print(f"\n--- Comparative Agent Tool Call: agent_call_competitive_edge_analyst ---")
    print(f"  Performing competitive review analysis for business: '{main_business_id}' using Gemini API.")

    # Get main business details to retrieve its internal ID and name
    business_details = db_get_business_details(main_business_id)
    if not business_details or not business_details.get('business_id'):
        print(f"Competitive Edge Analyst: Could not retrieve main business details for ID '{main_business_id}'.")
        return None
    
    main_business_internal_id = business_details['business_id']
    business_name = business_details.get('name', 'Your Business')

    # 1. Retrieve the *processed* reviews from `business_review` table
    # Get reviews for the main business itself
    business_processed_reviews = db_get_processed_reviews(main_business_internal_id, entity_type="business")
    
    # Get all competitors linked to this main business from the `competitor` table
    competitors_db = db_get_competitors(main_business_id)
    
    competitor_processed_reviews_map_for_prompt = {}
    
    # Iterate through each competitor and fetch their reviews
    for comp in competitors_db:
        comp_internal_id = comp.get('competitor_id')
        comp_name = comp.get('name', 'Unknown Competitor')
        
        if comp_internal_id:
            # Fetch reviews for this specific competitor, using its internal ID
            competitor_reviews = db_get_processed_reviews(comp_internal_id, entity_type="competitor")
            if competitor_reviews:
                competitor_processed_reviews_map_for_prompt[comp_name] = competitor_reviews
            else:
                print(f"No processed reviews found for competitor '{comp_name}' (ID: {comp_internal_id}).")
        else:
            print(f"Warning: Competitor '{comp_name}' has no internal ID. Skipping review retrieval for this competitor.")

    if not business_processed_reviews and not competitor_processed_reviews_map_for_prompt:
        print("Competitive Edge Analyst: No processed review data found in DB for the business or its competitors. Cannot perform analysis.")
        return None

    # 2. Generate the prompt for Gemini API
    comparison_prompt = generate_review_comparison_prompt(
        business_name=business_name,
        business_processed_reviews=business_processed_reviews,
        competitor_processed_reviews_map=competitor_processed_reviews_map_for_prompt
    )
    
    # 3. Call Gemini API
    print("Calling Gemini API for review comparison analysis with Prompt:")
    # print(comparison_prompt)  # Temporarily commented out to avoid excessively long prints
    gemini_analysis = call_gemini_api(comparison_prompt)

    if gemini_analysis:
        print("Competitive Edge Analyst: Review comparison analysis completed by Gemini API.")
        return gemini_analysis
    else:
        print("Competitive Edge Analyst: Failed to get analysis from Gemini API.")
        return None

def agent_call_pricing_promotion_strategist(business_id: str) -> bool:
    """
    Simulates calling the Pricing and Promotion Strategist to generate advice.
    This agent would likely depend on data from Economic Monitor, Competitor Scout,
    and Internal Sales Analyst, which it would either pull itself or expect to be prepared.

    Args:
        business_id (str): The ID of the primary business for which to generate strategies.

    Returns:
        bool: True if the request was successfully dispatched/simulated, False otherwise.
    """
    print(f"\n--- Comparative Agent Tool Call: agent_call_pricing_promotion_strategist ---")
    print(f"  Requesting Pricing Promotion Strategist for business: '{business_id}'")
    # Placeholder for actual API call or message queue publish
    print("  (Simulated: Pricing Promotion Strategist task initiated successfully.)")
    return True


# --- Test function for agent_call_competitive_edge_analyst (Live Call) ---
def test_agent_call_competitive_edge_analyst_live(business_id: str):
    """
    Tests agent_call_competitive_edge_analyst by calling actual functions.
    Requires BigQuery and Google Places API to be set up and populated.

    Args:
        business_id (str): The actual business_id from your BigQuery 'business' table
                           that you want to test with. This business should have
                           associated competitors in your 'competitor' table.
    """
    print(f"\n--- Running LIVE Test: test_agent_call_competitive_edge_analyst_live for business_id: '{business_id}' ---")

    if not bq_client:
        print("BigQuery client not initialized. Cannot run live test.")
        return
    if not places_client:
        print("Google Places API client not initialized. Cannot run live test.")
        return
    if not gemini_model:
        print("Gemini model not initialized. Cannot run live test.")
        return

    # First, ensure you have raw reviews collected in the business_review table.
    # You might need to run agent_call_customer_sentiment_analyst_for_reviews first.
    # For this test, we'll assume reviews are already there or try to collect them.
    
    # Get competitors to pass to the collection function if needed
    competitors = db_get_competitors(business_id)
    competitor_ids = [c['competitor_id'] for c in competitors]

    print(f"Attempting to collect and store raw reviews for business '{business_id}' and its {len(competitor_ids)} competitors...")
    collection_success = agent_call_customer_sentiment_analyst_for_reviews(business_id, competitor_ids)
    if not collection_success:
        print("WARNING: Failed to collect and store raw reviews. The competitive analysis might be empty.")
    else:
        print("Raw review collection and storage step completed. Proceeding to analysis.")

    # Call the actual function to be tested
    analysis_output = agent_call_competitive_edge_analyst(business_id)

    # Output the result
    if analysis_output:
        print("\n--- LIVE Test Result: Competitive Analysis Output ---")
        print(analysis_output)
        print("\n--- LIVE Test Passed: Analysis received. Please review the output above. ---")
    else:
        print("\n--- LIVE Test Failed: No analysis output received. Check logs above for errors. ---")

    print("\n--- LIVE Test Complete ---")


# --- Main execution block for independent testing ---
if __name__ == "__main__":
    print("--- Starting independent Comparative Agent Tool testing ---")

    # IMPORTANT: Before running this live test:
    # 1. Ensure your BigQuery tables (`business`, `competitor`, `business_review`)
    #    are set up and contain relevant data.
    # 2. You need a 'business' entry with a valid `g_m_b_id` for `YOUR_BUSINESS_ID`.
    # 3. You need 'competitor' entries associated with `YOUR_BUSINESS_ID` and having
    #    valid `google_place_id` values.
    # 4. Your GCP project must have 'Places API (New)' enabled.
    # 5. Your `GEMINI_API_KEY` must be set in your environment.

    # --- SET YOUR TEST BUSINESS ID HERE ---
    YOUR_BUSINESS_ID = "biz_64d349ec" 
    # Example: "biz_coffee_001" if you used the mock setup previously and populated
    # the actual DB, or retrieve an ID from your BigQuery `business` table.

    if YOUR_BUSINESS_ID == "":
        print("\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("! WARNING: Please set YOUR_BUSINESS_ID to an actual existing !")
        print("!          business_id from your BigQuery 'business' table  !")
        print("!          for the live test to function correctly.         !")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    else:
        # Call the live test function
        test_agent_call_competitive_edge_analyst_live(YOUR_BUSINESS_ID)
        # maps_get_place_reviews('ChIJE7Ar-mwjQYYRifD8cBm-tUQ')  # Example call to test the Maps API tool directly

    print("\n--- Comparative Agent Tool testing complete ---")