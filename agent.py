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

SYSTEM_PROMPT = """
You are an AI lead-generation agent. Your job is to:
1. Use Outscraper tools to find and enrich business data
2. Validate contact information (emails, phones) before importing
3. Upsert contacts into GoHighLevel with complete, clean data
4. Tag contacts and add them to the appropriate pipeline

Always confirm the GHL location ID is 5fMBh61yvJqYSuLpGMvV before writing.
Report a summary of: how many found, how many valid, how many created/updated in GHL.
"""


async def run_agent(task: str):
    """Run the agent against the orchestrator MCP server."""
    print(f"\n🤖 Task: {task}\n{'─'*60}")

    async with MultiServerMCPClient(
        {
            "orchestrator": {
                "url": MCP_SERVER_URL,
                "transport": "streamable_http",
            }
        }
    ) as client:
        tools = await client.get_tools()
        print(f"✅ Connected — {len(tools)} tools available\n")

        llm = ChatOpenAI(
            model="gpt-4o",
            api_key=os.getenv("OPENAI_API_KEY"),
            temperature=0,
        )

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
