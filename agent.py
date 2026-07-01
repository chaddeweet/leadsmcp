"""
AI Agent — connects to the running MCP orchestrator and executes tasks.

Usage:
    # With local orchestrator running (python main.py):
    python agent.py

    # With deployed cloud server:
    MCP_SERVER_URL=https://your-app.railway.app/mcp python agent.py
"""
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://localhost:8000/mcp")


def _agent_llm_provider() -> str:
    configured = os.getenv("LEADSMCP_MARKETPLACE_LLM_PROVIDER", "").strip().lower()
    if configured in {"groq", "openai", "google", "gemini"}:
        return "google" if configured == "gemini" else configured
    if os.getenv("GEMINI_API_KEY", "").strip():
        return "google"
    if os.getenv("GROQ_API_KEY", "").strip():
        return "groq"
    if os.getenv("OPENAI_API_KEY", "").strip():
        return "openai"
    return "groq"


def _agent_llm_model() -> str:
    configured = os.getenv("LEADSMCP_MARKETPLACE_LLM_MODEL", "").strip()
    if configured:
        return configured
    if _agent_llm_provider() == "google":
        return "gemini-2.5-flash"
    if _agent_llm_provider() == "groq":
        return "openai/gpt-oss-20b"
    return "gpt-4o-mini"


def _agent_llm_kwargs() -> dict[str, object]:
    provider = _agent_llm_provider()
    kwargs: dict[str, object] = {
        "model": _agent_llm_model(),
        "temperature": 1e-8,
    }
    if provider == "google":
        kwargs["api_key"] = os.getenv("GEMINI_API_KEY", "").strip()
        kwargs["base_url"] = "https://generativelanguage.googleapis.com/v1beta/openai/"
    elif provider == "groq":
        kwargs["api_key"] = os.getenv("GROQ_API_KEY", "").strip()
        kwargs["base_url"] = "https://api.groq.com/openai/v1"
    else:
        kwargs["api_key"] = os.getenv("OPENAI_API_KEY", "").strip()
    return kwargs


def _build_mcp_headers() -> dict[str, str]:
    headers: dict[str, str] = {}

    mcp_secret = os.getenv("MCP_SECRET", "").strip()
    if mcp_secret:
        headers["x-mcp-secret"] = mcp_secret

    # Multi-tenant GHL context: pass tenant credentials per request
    ghl_token = os.getenv("GHL_PIT_TOKEN", "").strip()
    if ghl_token:
        headers["x-ghl-token"] = ghl_token

    ghl_location = os.getenv("GHL_LOCATION_ID", "").strip()
    if ghl_location:
        headers["x-ghl-location-id"] = ghl_location

    ghl_version = os.getenv("GHL_API_VERSION", "").strip()
    if ghl_version:
        headers["x-ghl-version"] = ghl_version

    return headers

SYSTEM_PROMPT = """
You are an AI lead-generation agent. Your job is to:
1. Use Outscraper tools to find and enrich business data
2. Validate contact information (emails, phones) before importing
3. Register the user in Stripe before showing full lead details:
   collect full name, first name, last name, email, and phone
   then call stripe_ensure_customer_profile and retain stripe_customer_id
4. Show search and preview results for free (no billing on browse)
5. Before exporting any lead to GoHighLevel:
   - call stripe_analyze_qualified_lead_export and show per-company lead breakdown
   - generate/retain an export_batch_id and tenant_id for this export
   - call stripe_plan_qualified_lead_export_billing to determine next action
   - if checkout_required, provide checkout URL and wait for completion
   - if permission_required, ask explicit per-batch billing permission
6. After export is approved, log usage with stripe_record_qualified_lead_export
   including export_batch_id, tenant_id, consent_granted=true, and qualified lead counts
7. Only after meter logging, upsert contacts into GoHighLevel with complete, clean data
8. Tag contacts and add them to the appropriate pipeline

Always confirm the GHL location ID is 5fMBh61yvJqYSuLpGMvV before writing.
Never export to GHL without logging a Stripe meter event for that export batch.
Report a summary of: how many found, how many valid, how many exported, how many created/updated in GHL.
"""


async def run_agent(task: str):
    """Run the agent against the orchestrator MCP server."""
    print(f"\n🤖 Task: {task}\n{'─'*60}")
    request_headers = _build_mcp_headers()

    client = MultiServerMCPClient(
        {
            "orchestrator": {
                "url": MCP_SERVER_URL,
                "transport": "streamable_http",
                "headers": request_headers,
            }
        }
    )
    tools = await client.get_tools()
    print(f"✅ Connected — {len(tools)} tools available\n")

    llm = ChatOpenAI(**_agent_llm_kwargs())

    agent = create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": task}]}
    )

    for msg in result["messages"]:
        if hasattr(msg, "type") and msg.type == "ai" and msg.content:
            print("\n=== AGENT RESPONSE ===")
            print(msg.content)

    return result


# ── Example tasks — edit and run ──────────────────────────────────────────────
EXAMPLE_TASKS = {
    "1": """
        Find 10 operational plumbing businesses in Johannesburg, South Africa
        that have both a website and phone number. Validate any emails found.
        For each business, upsert as a GHL contact and tag them with:
        'outscraper', 'plumber', 'johannesburg', 'za'.
        Report: total found, total valid, total created in GHL.
    """,

    "2": """
        Search for 'digital marketing agencies, Cape Town, ZA' — limit 15 results.
        Get company insights for any that have a website.
        Upsert each as a GHL contact with full address. Tag with:
        'agency', 'cape-town', 'outscraper-maps'.
        Then fetch the GHL pipelines list and add each as a new opportunity
        in the first pipeline, stage name 'New Lead'.
    """,

    "3": """
        Search for 'restaurants, Sandton, Johannesburg, ZA' limit 5.
        Just return the business names, ratings, phone numbers, and websites.
        Do NOT write anything to GHL yet.
    """,
}

if __name__ == "__main__":
    import sys
    task_key = sys.argv[1] if len(sys.argv) > 1 else "3"
    task = EXAMPLE_TASKS.get(task_key, EXAMPLE_TASKS["3"])
    asyncio.run(run_agent(task.strip()))
