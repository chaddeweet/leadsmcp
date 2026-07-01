"""
Outscraper MCP Sub-Server (Streamlined)
Wraps the Outscraper API (api.outscraper.cloud) as MCP tools.
This file is mounted into the main orchestrator — do NOT call mcp.run() here.

Includes only essential endpoints:
- google-maps-search
- google-maps-reviews
- emails-and-contacts
- email-validator
- phones-enricher
- similarweb
- geocoding
- reverse-geocoding
- linkedin-profiles
- linkedin-companies
- linkedin-posts
- tiktok-profiles
- twitter-profiles
- google-search
- google-search-news
- google-trends
- youtube-search
- youtube-videos
- youtube-transcripts
- profile/balance
"""
import os
import asyncio
import httpx
from typing import Optional
from fastmcp import FastMCP

mcp = FastMCP(name="Outscraper")

BASE_URL = "https://api.outscraper.cloud"

def _headers() -> dict:
    return {"X-API-KEY": os.getenv("OUTSCRAPER_API_KEY", "")}


def _with_outscraper_defaults(params: dict) -> dict:
    """Ensure every Outscraper request defaults async=false and ui=false.

    Applied to both query params and JSON payloads. User-supplied values are
    preserved; only missing keys are filled in.
    """
    normalized = dict(params or {})
    normalized.setdefault("async", "false")
    normalized.setdefault("ui", "false")
    return normalized

async def _get(endpoint: str, params: dict) -> dict:
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(f"{BASE_URL}{endpoint}", headers=_headers(), params=_with_outscraper_defaults(params))
        r.raise_for_status()
        return r.json()

async def _post(endpoint: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            f"{BASE_URL}{endpoint}",
            headers={**_headers(), "Content-Type": "application/json"},
            json=_with_outscraper_defaults(payload),
        )
        r.raise_for_status()
        return r.json()

async def _poll(request_id: str, max_wait: int = 300) -> dict:
    async with httpx.AsyncClient(timeout=30.0) as client:
        for _ in range(max_wait // 10):
            await asyncio.sleep(10)
            r = await client.get(f"{BASE_URL}/requests/{request_id}", headers=_headers())
            data = r.json()
            if data.get("status") in ("Success", "Failure"):
                return data
        return {"status": "Timeout", "data": []}

# ══════════════════════════════════════════════════════════════════════════════
# GOOGLE MAPS & SEARCH
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def google_maps_search(
    query: str,
    limit: int = 20,
    language: str = "en",
    region: str = "US",
    enrichments: Optional[str] = None,
) -> dict:
    """
    Search Google Maps for businesses/POIs.
    Returns: name, address, phone, website, rating, reviews count, coordinates, hours.
    
    Args:
        query: e.g. 'plumbers, Johannesburg, ZA' or 'dentists, Cape Town, ZA'
        limit: Max results 1–500 (default 20)
        language: Language code — default 'en'
        region: ISO country code e.g. 'ZA', 'US', 'GB'
        enrichments: Comma-separated — e.g. 'contacts_n_leads,company_insights_service'
    """
    params: dict = {
        "query": query,
        "limit": limit,
        "language": language,
        "region": region,
        "async": "false",
    }
    if enrichments:
        params["enrichment"] = enrichments
    return await _get("/google-maps-search", params)

@mcp.tool()
async def google_maps_reviews(
    query: str,
    reviews_limit: int = 10,
    sort: str = "newest",
) -> dict:
    """
    Get Google Maps reviews for a business.
    
    Args:
        query: Business name/Place ID e.g. 'Starbucks, Manhattan, NY, USA'
        reviews_limit: Number of reviews (default 10)
        sort: 'newest' | 'most_relevant' | 'highest_rating' | 'lowest_rating'
    """
    return await _get(
        "/google-maps-reviews",
        {"query": query, "reviewsLimit": reviews_limit, "sort": sort, "async": "false"},
    )

@mcp.tool()
async def google_search(
    query: str,
    pages_per_query: int = 1,
    language: str = "en",
    region: str = "US",
) -> dict:
    """
    Perform a Google Search — returns organic results, ads, related queries.
    Useful for researching prospects before outreach.
    
    Args:
        query: Any search string
        pages_per_query: Result pages (default 1)
        language: Language code
        region: Country code for localised results
    """
    return await _get(
        "/google-search",
        {"query": query, "pagesPerQuery": pages_per_query, "language": language, "region": region, "async": "false"},
    )

@mcp.tool()
async def google_search_news(
    query: str,
    pages_per_query: int = 1,
    language: str = "en",
    region: str = "US",
) -> dict:
    """
    Search Google News for news articles.
    
    Args:
        query: Search term for news
        pages_per_query: Number of pages to retrieve
        language: Language code
        region: Country code
    """
    return await _get(
        "/google-search-news",
        {"query": query, "pagesPerQuery": pages_per_query, "language": language, "region": region, "async": "false"},
    )

@mcp.tool()
async def google_trends(
    query: str,
    language: str = "en",
    region: str = "US",
) -> dict:
    """
    Get Google Trends data for search terms.
    
    Args:
        query: Search term(s) to analyze trends
        language: Language code
        region: Country code
    """
    return await _get(
        "/google-trends",
        {"query": query, "language": language, "region": region, "async": "false"},
    )

# ══════════════════════════════════════════════════════════════════════════════
# CONTACTS, EMAILS & LEADS
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def emails_and_contacts(
    domains: str,
    contacts_per_company: int = 3,
    emails_per_contact: int = 1,
) -> dict:
    """
    Find email addresses, social links, and phones from domains.
    
    Args:
        domains: Comma-separated domains e.g. 'apple.com,tesla.com'
        contacts_per_company: Number of contacts per domain
        emails_per_contact: Number of emails per contact
    """
    return await _get(
        "/emails-and-contacts",
        {
            "query": domains,
            "contactsPerCompany": contacts_per_company,
            "emailsPerContact": emails_per_contact,
            "async": "false",
        },
    )

@mcp.tool()
async def email_validator(emails: str) -> dict:
    """
    Validate email addresses — checks deliverability, spam traps, blacklists.
    Returns RECEIVING / UNKNOWN / INVALID per email.
    
    Args:
        emails: Comma-separated e.g. 'john@acme.com,jane@corp.com'
    """
    return await _get("/email-validator", {"query": emails, "async": "false"})

# ══════════════════════════════════════════════════════════════════════════════
# PHONE SERVICES
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def phones_enricher(phones: str) -> dict:
    """
    Enrich phone numbers — carrier name, type (mobile/landline), ownership info.
    
    Args:
        phones: Comma-separated E.164 numbers e.g. '+27113456789,+14155550123'
    """
    return await _get("/phones-enricher", {"query": phones, "async": "false"})

# ══════════════════════════════════════════════════════════════════════════════
# DOMAIN & COMPANY SERVICES
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def similarweb(domains: str) -> dict:
    """
    Get website analytics from SimilarWeb — traffic, rankings, audience insights.
    
    Args:
        domains: Comma-separated domains e.g. 'apple.com,tesla.com'
    """
    return await _get("/similarweb", {"domain": domains, "async": "false"})

# ══════════════════════════════════════════════════════════════════════════════
# GEOCODING
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def geocoding(address: str) -> dict:
    """
    Convert address to coordinates (latitude, longitude).
    
    Args:
        address: Full address string e.g. '1600 Amphitheatre Parkway, Mountain View, CA'
    """
    return await _get("/geocoding", {"query": address, "async": "false"})

@mcp.tool()
async def reverse_geocoding(coordinates: str) -> dict:
    """
    Convert coordinates to address.
    
    Args:
        coordinates: Latitude,longitude e.g. '37.4224764,-122.0842499'
    """
    return await _get("/reverse-geocoding", {"query": coordinates, "async": "false"})

# ══════════════════════════════════════════════════════════════════════════════
# LINKEDIN
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def linkedin_profiles(
    query: str,
    limit: int = 10,
) -> dict:
    """
    Get LinkedIn person profiles.
    
    Args:
        query: Profile URL or username e.g. 'https://www.linkedin.com/in/realvlad' or 'realvlad'
        limit: Max results (default 10)
    """
    return await _get("/linkedin-profiles", {"query": query, "limit": limit, "async": "false"})

@mcp.tool()
async def linkedin_companies(
    query: str,
    limit: int = 10,
) -> dict:
    """
    Search LinkedIn companies.
    
    Args:
        query: Company name, URL or ID e.g. 'https://www.linkedin.com/company/outscraper' or 'outscraper'
        limit: Max results (default 10)
    """
    return await _get("/linkedin-companies", {"query": query, "limit": limit, "async": "false"})

@mcp.tool()
async def linkedin_posts(
    query: str,
    limit: int = 10,
) -> dict:
    """
    Get posts from LinkedIn companies.
    
    Args:
        query: Company URL or ID e.g. 'https://www.linkedin.com/company/outscraper' or 'outscraper'
        limit: Number of posts to retrieve
    """
    return await _get("/linkedin-posts", {"query": query, "limit": limit, "async": "false"})

# ══════════════════════════════════════════════════════════════════════════════
# SOCIAL MEDIA
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def tiktok_profiles(
    query: str,
    limit: int = 10,
) -> dict:
    """
    Search TikTok user profiles.
    
    Args:
        query: Username or search term
        limit: Max results (default 10)
    """
    return await _get("/tiktok-profiles", {"query": query, "limit": limit, "async": "false"})

@mcp.tool()
async def twitter_profiles(
    query: str,
    limit: int = 10,
) -> dict:
    """
    Search Twitter/X user profiles.
    
    Args:
        query: Username or search term
        limit: Max results (default 10)
    """
    return await _get("/twitter-profiles", {"query": query, "limit": limit, "async": "false"})

# ══════════════════════════════════════════════════════════════════════════════
# YOUTUBE
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def youtube_search(
    query: str,
    limit: int = 10,
) -> dict:
    """
    Search YouTube videos.
    
    Args:
        query: Search term
        limit: Max results (default 10)
    """
    return await _get("/youtube-search", {"query": query, "limit": limit, "async": "false"})

@mcp.tool()
async def youtube_videos(
    channel_url: str,
    limit: int = 10,
) -> dict:
    """
    Get videos from a YouTube channel.
    
    Args:
        channel_url: Channel URL or username
        limit: Max videos (default 10)
    """
    return await _get("/youtube-videos", {"query": channel_url, "limit": limit, "async": "false"})

@mcp.tool()
async def youtube_transcripts(
    video_url: str,
) -> dict:
    """
    Get transcript/captions from YouTube video.
    
    Args:
        video_url: YouTube video URL or ID
    """
    return await _get("/youtube-transcripts", {"query": video_url, "async": "false"})

# ══════════════════════════════════════════════════════════════════════════════
# ACCOUNT & PROFILE
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def profile_balance() -> dict:
    """
    Get current account balance and usage information.
    Returns credits remaining and account status.
    """
    return await _get("/profile/balance", {})

# ══════════════════════════════════════════════════════════════════════════════
# REQUEST MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool()
async def get_request_results(request_id: str) -> dict:
    """
    Retrieve results of a previously submitted async Outscraper request.
    Polls until complete (max 5 min). Use when a prior tool returned a request_id.
    
    Args:
        request_id: The ID returned by a previous async Outscraper call
    """
    return await _poll(request_id)
