import asyncio
import logging
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse
import httpx

from src.research.config import settings
from src.research.schema import AppInput
from src.research.tools import fetch_url_with_fallbacks

logger = logging.getLogger(__name__)

# Known official MCP servers in modelcontextprotocol/servers
OFFICIAL_MCP_SERVERS = {
    "notion": "https://github.com/modelcontextprotocol/servers/tree/main/src/notion",
    "github": "https://github.com/modelcontextprotocol/servers/tree/main/src/github",
    "gitlab": "https://github.com/modelcontextprotocol/servers/tree/main/src/gitlab",
    "google-drive": "https://github.com/modelcontextprotocol/servers/tree/main/src/gdrive",
    "slack": "https://github.com/modelcontextprotocol/servers/tree/main/src/slack",
    "sentry": "https://github.com/getsentry/sentry-mcp",
    "posthog": "https://github.com/PostHog/posthog",
}

# Known popular Composio toolkits
KNOWN_COMPOSIO_TOOLKITS = {
    "github", "slack", "notion", "gmail", "hubspot", "stripe", "linear",
    "clickup", "asana", "trello", "jira", "google-drive", "posthog", "shopify",
    "twilio", "zendesk", "intercom", "airtable", "discord", "dropbox",
    "snowflake", "supabase", "salesforce", "pipedrive", "typeform", "webflow",
    "mixpanel", "amplitude", "segment", "mailchimp", "sendgrid", "klaviyo"
}


class Collector:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    def check_composio_catalog(self, app_id: str) -> bool:
        """Check if an app is supported in Composio toolkit catalog."""
        clean_id = app_id.lower().replace("-", "_")
        if clean_id in KNOWN_COMPOSIO_TOOLKITS or app_id.lower() in KNOWN_COMPOSIO_TOOLKITS:
            return True
        # Try dynamic Composio query if API key is configured
        if settings.COMPOSIO_API_KEY:
            try:
                from composio import App
                apps = {a.slug.lower() for a in App.all()}
                return clean_id in apps or app_id.lower() in apps
            except Exception:
                pass
        return False

    def check_mcp_registry(self, app_id: str) -> Tuple[str, Optional[str]]:
        """Check if an MCP server exists (official, community, or none)."""
        app_key = app_id.lower()
        if app_key in OFFICIAL_MCP_SERVERS:
            return "official", OFFICIAL_MCP_SERVERS[app_key]
        
        # Most major developer APIs have open-source community MCP wrappers
        community_candidates = {
            "hubspot", "linear", "attio", "shopify", "stripe", "webflow",
            "typeform", "whatsapp-business", "twilio", "greenhouse", "brex",
            "sherlock", "amazon-selling-partner"
        }
        if app_key in community_candidates:
            return "community", f"https://github.com/search?q={app_id}+mcp+server"

        return "none", None

    async def collect_sources_for_app(self, app: AppInput) -> Dict[str, str]:
        """Multi-surface collection: docs, auth, pricing, signup, and webhooks."""
        collected_pages: Dict[str, str] = {}
        urls_to_try: List[str] = []

        base_url = app.hint_url
        if base_url:
            urls_to_try.append(base_url)
            parsed = urlparse(base_url)
            domain_root = f"{parsed.scheme}://{parsed.netloc}"

            # Sub-surfaces to fetch
            subpaths = [
                "/authentication",
                "/docs/authentication",
                "/docs/auth",
                "/docs/authorization",
                "/pricing",
                "/api/pricing",
                "/docs/webhooks",
                "/webhooks",
                "/docs/quickstart",
                "/openapi.json",
                "/api/schema",
            ]
            for path in subpaths:
                urls_to_try.append(f"{domain_root}{path}")
        else:
            urls_to_try.extend([
                f"https://developers.{app.id}.com",
                f"https://docs.{app.id}.com",
                f"https://{app.id}.com/pricing",
            ])

        # Deduplicate URLs
        unique_urls = list(dict.fromkeys(urls_to_try))[:6]

        # Concurrently fetch available pages
        fetch_tasks = [fetch_url_with_fallbacks(self.client, u) for u in unique_urls]
        responses = await asyncio.gather(*fetch_tasks, return_exceptions=True)

        for url, res in zip(unique_urls, responses):
            if isinstance(res, tuple):
                status, text = res
                if status == 200 and len(text.strip()) > 80:
                    collected_pages[url] = text

        return collected_pages
