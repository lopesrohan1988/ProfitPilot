# ProfitPilot AI Business Optimization Assistant

**ProfitPilot AI** is an intelligent, multi-agent assistant that empowers small and medium-sized businesses with data-driven insights and actionable recommendations. By leveraging cutting-edge AI and cloud data solutions, ProfitPilot helps owners optimize profitability, manage inventory, and understand market dynamics.

---
## Architecture Diagram


```mermaid
---
config:
  layout: dagre
---
flowchart LR
 subgraph Root["Root"]
        root_agent["root_agent"]
  end
 subgraph s1["Sub-Agents"]
        onboarding_agent["onboarding_agent"]
        comparision_agent["comparision_agent"]
        business_analyst_agent["business_analyst_agent"]
  end
 subgraph subGraph2["Tools - Onboarding Agent"]
        ob_db_check_business_exists{{"db_check_business_exists"}}
        ob_db_create_business{{"db_create_business"}}
        ob_db_check_competitors_exist{{"db_check_competitors_exist"}}
        ob_db_add_competitor{{"db_add_competitor"}}
        ob_Maps_search_business{{"Maps_search_business"}}
        ob_agent_generate_simulated_data{{"agent_generate_simulated_data"}}
  end
 subgraph subGraph3["Tools - Comparison Agent"]
        comp_db_get_business_details{{"db_get_business_details"}}
        comp_db_get_competitors{{"db_get_competitors"}}
        comp_db_get_processed_reviews{{"db_get_processed_reviews"}}
        comp_agent_call_customer_sentiment_analyst_for_reviews{{"agent_call_customer_sentiment_analyst_for_reviews"}}
  end
 subgraph subGraph4["Tools - Business Analyst Agent"]
        ba_agent_provide_pricing_advice{{"agent_provide_pricing_advice"}}
        ba_agent_analyze_sales_trends{{"agent_analyze_sales_trends"}}
        ba_agent_check_inventory_levels{{"agent_check_inventory_levels"}}
  end
 subgraph subGraph5["Target Services"]
        bigquery[("BigQuery")]
        google_maps_places_api[("Google Maps Places API")]
        gemini[("Gemini API")]
  end
    root_agent --> onboarding_agent & comparision_agent & business_analyst_agent
    onboarding_agent --> ob_db_check_business_exists & ob_db_create_business & ob_db_check_competitors_exist & ob_db_add_competitor & ob_Maps_search_business & ob_agent_generate_simulated_data
    ob_db_check_business_exists --> bigquery
    ob_db_create_business --> bigquery
    ob_db_check_competitors_exist --> bigquery
    ob_db_add_competitor --> bigquery
    ob_Maps_search_business --> google_maps_places_api
    ob_agent_generate_simulated_data --> bigquery & gemini
    comparision_agent --> comp_db_get_business_details & comp_db_get_competitors & comp_db_get_processed_reviews & comp_agent_call_customer_sentiment_analyst_for_reviews
    comp_db_get_business_details --> bigquery
    comp_db_get_competitors --> bigquery
    comp_db_get_processed_reviews --> bigquery
    comp_agent_call_customer_sentiment_analyst_for_reviews --> google_maps_places_api & bigquery & gemini
    business_analyst_agent --> ba_agent_provide_pricing_advice & ba_agent_analyze_sales_trends & ba_agent_check_inventory_levels
    ba_agent_provide_pricing_advice --> bigquery
    ba_agent_analyze_sales_trends --> bigquery
    ba_agent_check_inventory_levels --> bigquery
    style root_agent fill:#ADD8E6,stroke:#333,stroke-width:2px
    style onboarding_agent fill:#FFD700,stroke:#333,stroke-width:2px
    style comparision_agent fill:#90EE90,stroke:#333,stroke-width:2px
    style business_analyst_agent fill:#FFB6C1,stroke:#333,stroke-width:2px
    style ob_db_check_business_exists fill:#D3D3D3,stroke:#666,stroke-width:1px
    style ob_db_create_business fill:#D3D3D3,stroke:#666,stroke-width:1px
    style ob_db_check_competitors_exist fill:#D3D3D3,stroke:#666,stroke-width:1px
    style ob_db_add_competitor fill:#D3D3D3,stroke:#666,stroke-width:1px
    style ob_Maps_search_business fill:#D3D3D3,stroke:#666,stroke-width:1px
    style ob_agent_generate_simulated_data fill:#D3D3D3,stroke:#666,stroke-width:1px
    style comp_db_get_business_details fill:#D3D3D3,stroke:#666,stroke-width:1px
    style comp_db_get_competitors fill:#D3D3D3,stroke:#666,stroke-width:1px
    style comp_db_get_processed_reviews fill:#D3D3D3,stroke:#666,stroke-width:1px
    style comp_agent_call_customer_sentiment_analyst_for_reviews fill:#D3D3D3,stroke:#666,stroke-width:1px
    style ba_agent_provide_pricing_advice fill:#D3D3D3,stroke:#666,stroke-width:1px
    style ba_agent_analyze_sales_trends fill:#D3D3D3,stroke:#666,stroke-width:1px
    style ba_agent_check_inventory_levels fill:#D3D3D3,stroke:#666,stroke-width:1px
    style bigquery fill:#FFC0CB,stroke:#8B0000,stroke-width:2px
    style google_maps_places_api fill:#ADD8E6,stroke:#00008B,stroke-width:2px
    style gemini fill:#98FB98,stroke:#006400,stroke-width:2px
```

---

## Key Features

ProfitPilot's specialized AI agents collaborate to provide comprehensive business intelligence:

### Intelligent Onboarding & Data Seeding
- Streamlines initial setup, capturing essential business details.
- Can generate realistic sample sales and inventory data using Gemini for quick demonstrations or new businesses, directly populating BigQuery.

### Dynamic Business Analytics (Powered by Gemini)
- **Sales Trend Analysis**: Analyzes BigQuery sales data with Gemini 1.5 Flash to identify growth, peak periods, popular items, and anomalies.
- **Inventory Level Monitoring**: Reports on current stock, highlighting low-stock or perishable items.
- **Pricing Advice**: Uses Gemini 1.5 Flash to analyze costs, sales prices, and profitability, providing strategic pricing recommendations.

### Competitive Intelligence (Google Maps & Gemini)
- Performs external calls to Google Maps Places API to discover nearby competitors and fetch their public reviews.
- Gemini 1.5 Flash then analyzes this external data for competitive comparisons and market insights.

### Centralized Orchestration
- A Root Agent interprets user queries, manages context, and intelligently delegates tasks across the system, synthesizing agent responses into clear, user-friendly insights.

---

## Technologies

ProfitPilot is built on a robust Google Cloud ecosystem:

- **Google Gemini 1.5 Flash API**: Powers all AI-driven understanding, analysis, insight generation, and natural language responses.
- **Google BigQuery**: Scalable, serverless data warehouse for all core business data (sales, inventory, business profiles).
- **Google Maps Platform / Places API**: Used for competitor discovery and fetching public review data.
- **Python**: Core development language.
- **Python Libraries**: `google-cloud-bigquery`, `google-generativeai`, `googlemaps`, `Flask` (for web deployment).
- **Other Data Sources**: Integrates with Google My Business (GMB) for initial business profile data.

---

## Key Learnings

Developing ProfitPilot highlighted several critical insights:

- **Agentic Architectures**: Breaking down complex problems into specialized AI agents significantly enhances maintainability and performance.
- **LLM & Structured Data**: Effectively transforming structured data (e.g., BigQuery results as JSON) for Gemini's analysis is crucial for deriving precise insights.
- **External API Integration**: Seamlessly integrating external services like Google Maps for real-time competitive data proved essential.
- **Context Management**: Maintaining conversational context and `business_id` across agents is key to a fluid user experience.

---

## Deployment Steps

```bash
export GOOGLE_API_KEY=
export GOOGLE_MAP_API_KEY=
export GOOGLE_CLOUD_PROJECT=
export BQ_DATASET_ID=
export GOOGLE_GENAI_USE_VERTEXAI=FALSE
export GOOGLE_CLOUD_LOCATION=
export AGENT_PATH="./PIAgent"
export APP_NAME="profitpilot-agent-app"
export SERVICE_NAME="profitpilot-agent-service"

adk deploy cloud_run \
  --project=$GOOGLE_CLOUD_PROJECT \
  --region=$GOOGLE_CLOUD_LOCATION \
  --service_name=$SERVICE_NAME \
  --app_name=$APP_NAME \
  --with_ui $AGENT_PATH
```