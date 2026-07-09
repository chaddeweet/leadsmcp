from __future__ import annotations

import html
import json


def _safe(value: str) -> str:
    return html.escape(value, quote=True)


def _common_head(
    title: str,
    *,
    description: str = "",
    canonical_url: str = "",
    extra_head: str = "",
) -> str:
    safe_title = _safe(title)
    safe_description = _safe(description)
    safe_canonical_url = _safe(canonical_url)
    return f"""<!DOCTYPE html>
<html lang=\"en\" data-theme=\"dark\">
<head>
  <meta charset=\"UTF-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
  <title>{safe_title}</title>
  {f'<meta name="description" content="{safe_description}">' if description else ''}
  {f'<link rel="canonical" href="{safe_canonical_url}">' if canonical_url else ''}
  {f'<meta property="og:title" content="{safe_title}">' if title else ''}
  {f'<meta property="og:description" content="{safe_description}">' if description else ''}
  {f'<meta name="twitter:title" content="{safe_title}">' if title else ''}
  {f'<meta name="twitter:description" content="{safe_description}">' if description else ''}
  <meta name=\"twitter:card\" content=\"summary_large_image\">
  <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">
  <link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>
  <link href=\"https://fonts.googleapis.com/css2?family=Geist+Mono:wght@400;500&family=Inter:wght@300..700&display=swap\" rel=\"stylesheet\">
  <link href=\"https://api.fontshare.com/v2/css?f[]=cabinet-grotesk@400,500,700,800,900&display=swap\" rel=\"stylesheet\">
  {extra_head}
  <style>
    :root, [data-theme=\"dark\"] {{
      --color-bg: #0b0c0e;
      --color-surface: #111214;
      --color-surface-2: #161719;
      --color-surface-offset: #1c1d20;
      --color-border: #2e3035;
      --color-divider: #242528;
      --color-text: #e8e9eb;
      --color-text-muted: #9399a3;
      --color-text-faint: #5a5f68;
      --color-text-inverse: #0b0c0e;
      --color-primary: #4cf5d2;
      --color-primary-hover: #2de8c3;
      --color-primary-dim: rgba(76, 245, 210, 0.12);
      --color-accent2: #6e7cff;
      --radius-sm: 0.375rem;
      --radius-md: 0.5rem;
      --radius-lg: 0.75rem;
      --radius-xl: 1rem;
      --font-display: 'Cabinet Grotesk', 'Inter', sans-serif;
      --font-body: 'Inter', sans-serif;
      --font-mono: 'Geist Mono', 'Fira Code', monospace;
      --text-xs: clamp(0.75rem, 0.7rem + 0.25vw, 0.875rem);
      --text-sm: clamp(0.875rem, 0.8rem + 0.35vw, 1rem);
      --text-base: clamp(1rem, 0.95rem + 0.25vw, 1.125rem);
      --text-lg: clamp(1.125rem, 1rem + 0.75vw, 1.5rem);
      --text-xl: clamp(1.5rem, 1.2rem + 1.25vw, 2.25rem);
      --space-1: 0.25rem;
      --space-2: 0.5rem;
      --space-3: 0.75rem;
      --space-4: 1rem;
      --space-5: 1.25rem;
      --space-6: 1.5rem;
      --space-8: 2rem;
      --space-10: 2.5rem;
      --space-12: 3rem;
      --space-16: 4rem;
      --content-wide: 1160px;
      --transition: 180ms cubic-bezier(0.16, 1, 0.3, 1);
    }}
    [data-theme=\"light\"] {{
      --color-bg: #f4f5f7;
      --color-surface: #ffffff;
      --color-surface-2: #f9fafb;
      --color-surface-offset: #f0f1f3;
      --color-border: #d4d7dd;
      --color-divider: #e2e4e8;
      --color-text: #111214;
      --color-text-muted: #5a606b;
      --color-text-faint: #9ba0aa;
      --color-text-inverse: #f4f5f7;
      --color-primary: #007a65;
      --color-primary-hover: #006354;
      --color-primary-dim: rgba(0, 122, 101, 0.10);
      --color-accent2: #4a56d6;
    }}

    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html {{ -webkit-font-smoothing: antialiased; scroll-behavior: smooth; }}
    body {{
      min-height: 100dvh;
      line-height: 1.6;
      font-family: var(--font-body);
      font-size: var(--text-base);
      color: var(--color-text);
      background: var(--color-bg);
    }}
    a {{ color: inherit; }}
    code, pre {{ font-family: var(--font-mono); }}

    .container {{ max-width: var(--content-wide); margin-inline: auto; padding-inline: clamp(var(--space-4), 4vw, var(--space-12)); }}

    nav {{
      position: sticky;
      top: 0;
      z-index: 100;
      background: color-mix(in srgb, var(--color-bg) 88%, transparent);
      backdrop-filter: blur(16px);
      border-bottom: 1px solid var(--color-border);
      padding: var(--space-4) 0;
    }}
    .nav-inner {{ display: flex; align-items: center; justify-content: space-between; gap: var(--space-6); }}
    .brand {{
      display: inline-flex;
      align-items: center;
      gap: var(--space-3);
      text-decoration: none;
      font-family: var(--font-display);
      font-weight: 800;
      letter-spacing: -0.01em;
    }}
    .dot {{ width: 10px; height: 10px; border-radius: 999px; background: var(--color-primary); box-shadow: 0 0 14px var(--color-primary); }}
    .nav-actions {{ display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; justify-content: flex-end; }}

    .btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: var(--space-2);
      border-radius: var(--radius-md);
      padding: var(--space-2) var(--space-5);
      text-decoration: none;
      border: 1px solid var(--color-border);
      font-size: var(--text-sm);
      transition: background var(--transition), border-color var(--transition), color var(--transition), box-shadow var(--transition);
    }}
    .btn:hover {{ border-color: var(--color-text-muted); }}
    .btn-primary {{
      background: var(--color-primary);
      color: var(--color-text-inverse);
      border-color: transparent;
      font-weight: 600;
    }}
    .btn-primary:hover {{ background: var(--color-primary-hover); box-shadow: 0 0 20px var(--color-primary-dim); }}
    .btn-ghost {{ background: transparent; color: var(--color-text-muted); }}
    .btn-ghost:hover {{ color: var(--color-text); background: var(--color-surface-offset); }}

    .theme-toggle {{
      width: 40px;
      height: 40px;
      border-radius: var(--radius-md);
      border: 1px solid var(--color-border);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      background: var(--color-surface);
      color: var(--color-text-muted);
      cursor: pointer;
    }}

    .hero {{
      padding: clamp(var(--space-10), 8vw, var(--space-16)) 0 var(--space-10);
      position: relative;
      overflow: hidden;
    }}
    .hero::before {{
      content: '';
      position: absolute;
      inset: 0;
      pointer-events: none;
      background:
        radial-gradient(ellipse 58% 55% at 70% 0%, rgba(76,245,210,0.10) 0%, transparent 70%),
        radial-gradient(ellipse 45% 45% at 20% 80%, rgba(110,124,255,0.08) 0%, transparent 70%);
    }}
    .hero-content {{ position: relative; z-index: 1; }}
    .eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: var(--space-2);
      font-size: var(--text-xs);
      font-weight: 600;
      letter-spacing: 0.06em;
      text-transform: uppercase;
      color: var(--color-primary);
      background: var(--color-primary-dim);
      border: 1px solid color-mix(in srgb, var(--color-primary) 35%, transparent);
      border-radius: 999px;
      padding: 2px var(--space-3);
      margin-bottom: var(--space-5);
    }}
    h1 {{
      font-family: var(--font-display);
      font-size: clamp(2rem, 1.3rem + 2.8vw, 3.6rem);
      font-weight: 900;
      line-height: 1.05;
      letter-spacing: -0.03em;
      margin-bottom: var(--space-4);
    }}
    .hero-sub {{
      font-size: var(--text-lg);
      color: var(--color-text-muted);
      max-width: 72ch;
      margin-bottom: var(--space-6);
    }}
    .hero-cta {{ display: flex; flex-wrap: wrap; gap: var(--space-3); }}

    .section {{ padding: var(--space-6) 0 var(--space-12); }}
    .grid {{ display: grid; gap: var(--space-4); grid-template-columns: repeat(12, minmax(0, 1fr)); }}

    .card {{
      background: var(--color-surface);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-xl);
      padding: var(--space-6);
    }}
    .card h2 {{
      font-family: var(--font-display);
      font-size: var(--text-xl);
      font-weight: 800;
      letter-spacing: -0.02em;
      margin-bottom: var(--space-3);
    }}
    .card h3 {{
      font-family: var(--font-display);
      font-size: var(--text-lg);
      font-weight: 700;
      letter-spacing: -0.015em;
      margin-bottom: var(--space-2);
    }}
    .muted {{ color: var(--color-text-muted); }}

    .list {{ display: grid; gap: var(--space-3); margin-top: var(--space-4); }}
    .list-item {{
      display: flex;
      gap: var(--space-3);
      align-items: flex-start;
      background: var(--color-surface-2);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-lg);
      padding: var(--space-4);
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: var(--space-2);
      border-radius: 999px;
      font-size: var(--text-xs);
      padding: 2px var(--space-2);
      background: var(--color-primary-dim);
      color: var(--color-primary);
      flex-shrink: 0;
      white-space: nowrap;
      margin-top: 2px;
    }}
    .route {{ font-family: var(--font-mono); font-size: var(--text-sm); color: var(--color-accent2); }}

    pre {{
      margin-top: var(--space-4);
      background: var(--color-surface-2);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-lg);
      padding: var(--space-4);
      overflow-x: auto;
      font-size: 0.82rem;
      line-height: 1.7;
      color: var(--color-text-muted);
    }}

    .field-grid {{
      display: grid;
      gap: var(--space-4);
      grid-template-columns: repeat(12, minmax(0, 1fr));
    }}
    .field {{
      grid-column: span 6;
      display: grid;
      gap: var(--space-2);
    }}
    .field[data-span=\"12\"] {{ grid-column: 1 / -1; }}
    .field[data-span=\"4\"] {{ grid-column: span 4; }}
    .field[data-span=\"3\"] {{ grid-column: span 3; }}
    .field > span {{
      font-size: var(--text-sm);
      font-weight: 600;
      letter-spacing: -0.01em;
    }}
    .field-hint {{
      color: var(--color-text-muted);
      font-size: var(--text-xs);
      line-height: 1.5;
    }}
    .input,
    .select,
    .textarea {{
      width: 100%;
      border-radius: var(--radius-md);
      border: 1px solid var(--color-border);
      background: var(--color-surface-2);
      color: var(--color-text);
      padding: 0.85rem 0.95rem;
      font: inherit;
      transition: border-color var(--transition), box-shadow var(--transition), background var(--transition);
    }}
    .textarea {{
      min-height: 120px;
      resize: vertical;
    }}
    .input:focus,
    .select:focus,
    .textarea:focus {{
      outline: none;
      border-color: color-mix(in srgb, var(--color-primary) 50%, var(--color-border));
      box-shadow: 0 0 0 3px color-mix(in srgb, var(--color-primary) 18%, transparent);
    }}
    .panel {{
      background: var(--color-surface-2);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-lg);
      padding: var(--space-4);
    }}
    .inline-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: var(--space-2);
      margin-top: var(--space-3);
    }}
    .pill {{
      display: inline-flex;
      align-items: center;
      gap: var(--space-2);
      border-radius: 999px;
      border: 1px solid var(--color-border);
      background: var(--color-surface-offset);
      padding: 0.3rem 0.75rem;
      font-size: var(--text-xs);
      color: var(--color-text-muted);
    }}
    .status-good {{ color: var(--color-primary); }}
    .status-warn {{ color: #ffc857; }}
    .status-bad {{ color: #ff7a7a; }}
    .app-frame {{
      padding: var(--space-8) 0 var(--space-12);
    }}
    .results-shell {{
      display: grid;
      gap: var(--space-4);
    }}
    .results-summary {{
      display: grid;
      gap: var(--space-3);
      grid-template-columns: repeat(4, minmax(0, 1fr));
    }}
    .metric {{
      background: var(--color-surface-2);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-lg);
      padding: var(--space-4);
    }}
    .metric-label {{
      color: var(--color-text-muted);
      font-size: var(--text-xs);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: var(--space-2);
    }}
    .metric-value {{
      font-family: var(--font-display);
      font-size: var(--text-lg);
      font-weight: 700;
      letter-spacing: -0.02em;
    }}
    .empty-state {{
      text-align: center;
      border: 1px dashed var(--color-border);
      border-radius: var(--radius-lg);
      padding: var(--space-8);
      color: var(--color-text-muted);
      background: color-mix(in srgb, var(--color-surface) 60%, transparent);
    }}

    .contact-shell {{
      background: var(--color-surface);
      border: 1px solid var(--color-border);
      border-radius: var(--radius-xl);
      padding: var(--space-4);
      overflow: hidden;
    }}

    .split {{ display: grid; gap: var(--space-4); grid-template-columns: 1.5fr 1fr; }}

    footer {{
      border-top: 1px solid var(--color-divider);
      padding: var(--space-6) 0 var(--space-10);
      color: var(--color-text-faint);
      font-size: var(--text-sm);
    }}

    @media (max-width: 980px) {{
      .split {{ grid-template-columns: 1fr; }}
      .nav-actions .btn {{ display: none; }}
      .field,
      .field[data-span=\"4\"],
      .field[data-span=\"3\"] {{ grid-column: 1 / -1; }}
      .results-summary {{ grid-template-columns: 1fr 1fr; }}
    }}
    @media (max-width: 680px) {{
      .results-summary {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
"""


def _theme_script() -> str:
    return """
<script>
(function(){
  const toggle = document.querySelector('[data-theme-toggle]');
  const root = document.documentElement;
  const saved = localStorage.getItem('leadsmcp-theme');
  let mode = saved || root.getAttribute('data-theme') || 'dark';

  function icon(theme){
    if (theme === 'dark') {
      return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>';
    }
    return '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3A7 7 0 0 0 21 12.79z"/></svg>';
  }

  function apply(theme){
    mode = theme;
    root.setAttribute('data-theme', mode);
    if (toggle) {
      toggle.innerHTML = icon(mode);
      toggle.setAttribute('aria-label', mode === 'dark' ? 'Switch to light mode' : 'Switch to dark mode');
    }
  }

  apply(mode);
  if (toggle) {
    toggle.addEventListener('click', function(){
      apply(mode === 'dark' ? 'light' : 'dark');
      localStorage.setItem('leadsmcp-theme', mode);
    });
  }
})();
</script>
"""


def build_landing_page(*, base_url: str, install_url: str, github_url: str, canonical_url: str) -> str:
    base = base_url.rstrip("/")
    support_page = f"{base}/support"
    contact_page = f"{base}/contact"
    search_page = f"{base}/app/lead-search"
    install_href = install_url or f"{base}/oauth/ghl/start"
    pricing_anchor = f"{canonical_url}#pricing-model"

    faq_items = [
        {
            "question": "How is LeadsMCP different from Apollo or ZoomInfo?",
            "answer": "Legacy platforms rely on static databases and expensive monthly subscriptions. LeadsMCP runs live API scraping, gives you free previews, and only charges when you export the leads you want to keep.",
        },
        {
            "question": "What does MCP compatibility mean?",
            "answer": "LeadsMCP is built to plug into Model Context Protocol workflows so AI agents and LLM-based systems can query, enrich, and route live lead data securely.",
        },
        {
            "question": "How accurate is the data?",
            "answer": "LeadsMCP is designed around live API sourcing, layered enrichment, and verification before export. That means you preview fresher lead data than static database tools typically provide.",
        },
        {
            "question": "How do I get leads into my CRM?",
            "answer": "After export approval, LeadsMCP can push structured payloads into GoHighLevel and other CRM workflows without forcing a CSV-and-Zapier handoff.",
        },
        {
            "question": "Do I have to pay if a search returns bad data?",
            "answer": "No. The workflow is preview first, then pay to export. You can inspect the qualified lead set before you trigger a metered export event.",
        },
    ]

    software_schema = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": "LeadsMCP",
        "applicationCategory": "BusinessApplication",
        "operatingSystem": "Web-based API",
        "description": "MCP-native lead generation software with live API scraping, free previews, and pay-per-export pricing.",
        "url": canonical_url,
        "offers": {
            "@type": "Offer",
            "priceCurrency": "USD",
            "price": "0.99",
            "description": "Pay-per-export lead generation pricing starting at $0.99 per lead.",
        },
    }
    faq_schema = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": item["question"],
                "acceptedAnswer": {"@type": "Answer", "text": item["answer"]},
            }
            for item in faq_items
        ],
    }
    product_schema = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "LeadsMCP",
        "description": "Live API lead generation and enrichment platform for MCP and CRM workflows.",
        "brand": {"@type": "Brand", "name": "LeadsMCP"},
        "url": canonical_url,
        "offers": {
            "@type": "Offer",
            "priceCurrency": "USD",
            "price": "0.99",
            "availability": "https://schema.org/InStock",
        },
    }

    extra_head = "\n".join(
        [
            '<meta name="robots" content="index,follow">',
            f'<meta property="og:url" content="{_safe(canonical_url)}">',
            '<meta property="og:type" content="website">',
            f'<script type="application/ld+json">{json.dumps(software_schema, separators=(",", ":"))}</script>',
            f'<script type="application/ld+json">{json.dumps(faq_schema, separators=(",", ":"))}</script>',
            f'<script type="application/ld+json">{json.dumps(product_schema, separators=(",", ":"))}</script>',
        ]
    )

    return (
        _common_head(
            "MCP Lead Generation Software & Live API Scraper | LeadsMCP",
            description="Automate B2B lead generation with LeadsMCP. Use live API scraping, free previews, and pay-per-export pricing for your AI and MCP workflows.",
            canonical_url=canonical_url,
            extra_head=extra_head,
        )
        + f"""
<body>
  <style>
    .landing-shell {{
      background:
        radial-gradient(circle at 80% 0%, rgba(76, 245, 210, 0.12), transparent 34%),
        radial-gradient(circle at 10% 25%, rgba(110, 124, 255, 0.1), transparent 30%),
        var(--color-bg);
    }}
    .landing-hero {{
      min-height: calc(100svh - 76px);
      display: grid;
      align-items: center;
      padding: clamp(var(--space-10), 7vw, var(--space-16)) 0 var(--space-12);
    }}
    .landing-grid {{
      display: grid;
      grid-template-columns: minmax(0, 1.05fr) minmax(340px, 0.95fr);
      gap: clamp(var(--space-6), 5vw, var(--space-12));
      align-items: center;
    }}
    .hero-copy {{
      max-width: 58rem;
    }}
    .hero-copy h1 {{
      max-width: 12ch;
    }}
    .hero-proof {{
      display: flex;
      flex-wrap: wrap;
      gap: var(--space-2);
      margin: var(--space-6) 0;
    }}
    .hero-proof .pill {{
      background: color-mix(in srgb, var(--color-primary-dim) 78%, transparent);
      border-color: color-mix(in srgb, var(--color-primary) 24%, transparent);
    }}
    .poster {{
      position: relative;
      overflow: hidden;
      border-radius: calc(var(--radius-xl) + 10px);
      border: 1px solid color-mix(in srgb, var(--color-primary) 18%, var(--color-border));
      padding: clamp(var(--space-5), 3vw, var(--space-8));
      background:
        linear-gradient(165deg, rgba(12, 17, 22, 0.94), rgba(15, 21, 27, 0.94)),
        linear-gradient(120deg, rgba(76, 245, 210, 0.10), transparent 45%);
      box-shadow: 0 30px 90px rgba(0, 0, 0, 0.32);
    }}
    .poster::after {{
      content: '';
      position: absolute;
      inset: auto -10% -30% auto;
      width: 260px;
      height: 260px;
      border-radius: 999px;
      background: radial-gradient(circle, rgba(76, 245, 210, 0.22) 0%, transparent 68%);
      pointer-events: none;
    }}
    .poster-kicker {{
      display: flex;
      justify-content: space-between;
      gap: var(--space-3);
      font-size: var(--text-xs);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--color-text-faint);
      margin-bottom: var(--space-5);
    }}
    .poster-board {{
      display: grid;
      gap: var(--space-4);
    }}
    .poster-row {{
      display: grid;
      grid-template-columns: 1fr auto 1fr;
      gap: var(--space-3);
      align-items: stretch;
    }}
    .poster-card {{
      padding: var(--space-4);
      border-radius: var(--radius-lg);
      border: 1px solid color-mix(in srgb, var(--color-border) 92%, transparent);
      background: color-mix(in srgb, var(--color-surface) 88%, transparent);
    }}
    .poster-card h3 {{
      margin-bottom: var(--space-2);
    }}
    .poster-list {{
      display: grid;
      gap: var(--space-2);
      color: var(--color-text-muted);
      font-size: var(--text-sm);
    }}
    .poster-arrow {{
      display: flex;
      align-items: center;
      justify-content: center;
      color: var(--color-primary);
      font-size: 1.45rem;
      font-weight: 800;
    }}
    .metric-band {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: var(--space-4);
      margin-top: var(--space-8);
    }}
    .metric-band .card {{
      padding: var(--space-5);
      background: color-mix(in srgb, var(--color-surface) 90%, transparent);
    }}
    .metric-band .metric-value {{
      font-size: clamp(1.7rem, 1.4rem + 1.2vw, 2.4rem);
    }}
    .section-heading {{
      max-width: 54rem;
      margin-bottom: var(--space-8);
    }}
    .section-heading h2 {{
      font-size: clamp(1.8rem, 1.4rem + 1.5vw, 2.7rem);
      line-height: 1.08;
      margin-bottom: var(--space-3);
    }}
    .feature-grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: var(--space-4);
    }}
    .feature-card {{
      padding: var(--space-5);
      border-radius: calc(var(--radius-lg) + 4px);
      border: 1px solid var(--color-border);
      background:
        linear-gradient(180deg, color-mix(in srgb, var(--color-surface) 95%, transparent), color-mix(in srgb, var(--color-surface-2) 96%, transparent));
    }}
    .comparison-grid {{
      display: grid;
      grid-template-columns: minmax(0, 1.05fr) minmax(0, 0.95fr);
      gap: var(--space-4);
      align-items: start;
    }}
    .problem-stack,
    .flow-stack,
    .audience-grid,
    .faq-grid {{
      display: grid;
      gap: var(--space-4);
    }}
    .architecture-grid,
    .audience-grid {{
      grid-template-columns: repeat(3, minmax(0, 1fr));
    }}
    .timeline {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: var(--space-3);
    }}
    .timeline-step {{
      position: relative;
      padding: var(--space-5);
      border-radius: var(--radius-lg);
      border: 1px solid var(--color-border);
      background: color-mix(in srgb, var(--color-surface) 92%, transparent);
    }}
    .timeline-step::before {{
      content: attr(data-step);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 32px;
      height: 32px;
      border-radius: 999px;
      margin-bottom: var(--space-3);
      background: var(--color-primary);
      color: var(--color-text-inverse);
      font-weight: 700;
      font-size: var(--text-sm);
    }}
    .proof-zone {{
      display: grid;
      gap: var(--space-4);
      grid-template-columns: minmax(0, 1.15fr) minmax(280px, 0.85fr);
    }}
    .proof-placeholder {{
      border: 1px dashed color-mix(in srgb, var(--color-primary) 38%, var(--color-border));
      background: color-mix(in srgb, var(--color-surface) 90%, transparent);
      border-radius: calc(var(--radius-xl) + 2px);
      padding: var(--space-6);
    }}
    .proof-placeholder .pill-row {{
      margin-top: var(--space-4);
    }}
    .faq-item {{
      padding: var(--space-5);
      border-radius: var(--radius-lg);
      border: 1px solid var(--color-border);
      background: color-mix(in srgb, var(--color-surface) 92%, transparent);
    }}
    .faq-item summary {{
      cursor: pointer;
      list-style: none;
      font-family: var(--font-display);
      font-size: var(--text-lg);
      font-weight: 700;
    }}
    .faq-item summary::-webkit-details-marker {{
      display: none;
    }}
    .faq-item p {{
      margin-top: var(--space-3);
      color: var(--color-text-muted);
    }}
    .final-cta {{
      position: relative;
      overflow: hidden;
      border-radius: calc(var(--radius-xl) + 8px);
      border: 1px solid color-mix(in srgb, var(--color-primary) 20%, var(--color-border));
      padding: clamp(var(--space-8), 4vw, var(--space-12));
      background:
        radial-gradient(circle at 20% 20%, rgba(76, 245, 210, 0.16), transparent 38%),
        linear-gradient(155deg, rgba(11, 14, 18, 0.98), rgba(18, 25, 31, 0.95));
    }}
    .link-inline {{
      color: var(--color-primary);
      text-decoration: none;
    }}
    .link-inline:hover {{
      text-decoration: underline;
    }}
    @media (max-width: 1100px) {{
      .landing-grid,
      .comparison-grid,
      .proof-zone {{
        grid-template-columns: 1fr;
      }}
      .architecture-grid,
      .audience-grid,
      .metric-band,
      .timeline,
      .feature-grid {{
        grid-template-columns: 1fr 1fr;
      }}
      .poster-row {{
        grid-template-columns: 1fr;
      }}
      .poster-arrow {{
        transform: rotate(90deg);
      }}
    }}
    @media (max-width: 760px) {{
      .architecture-grid,
      .audience-grid,
      .metric-band,
      .timeline,
      .feature-grid {{
        grid-template-columns: 1fr;
      }}
      .landing-hero {{
        min-height: auto;
      }}
    }}
  </style>

  <div class="landing-shell">
    <nav>
      <div class="container">
        <div class="nav-inner">
          <a href="{_safe(base)}" class="brand"><span class="dot"></span>LeadsMCP</a>
          <div class="nav-actions">
            <button class="theme-toggle" data-theme-toggle aria-label="Switch theme"></button>
            <a class="btn btn-ghost" href="{_safe(support_page)}">Docs</a>
            <a class="btn btn-ghost" href="{_safe(contact_page)}">Contact</a>
            <a class="btn btn-primary" href="{_safe(install_href)}">Start Your Free Preview</a>
          </div>
        </div>
      </div>
    </nav>

    <main>
      <section class="landing-hero">
        <div class="container landing-grid">
          <div class="hero-copy">
            <p class="eyebrow">MCP Lead Generation Software</p>
            <h1>The AI-powered lead engine built for the Model Context Protocol.</h1>
            <p class="hero-sub">Stop paying for stale database subscriptions. LeadsMCP uses live API scraping to find, verify, and enrich B2B leads in real time. Preview your data for free, pay only for what you export, and feed your AI agents seamlessly via MCP.</p>
            <div class="hero-cta">
              <a class="btn btn-primary" href="{_safe(install_href)}">Start Your Free Preview</a>
              <a class="btn btn-ghost" href="{_safe(support_page)}">View API &amp; MCP Documentation</a>
            </div>
            <div class="hero-proof">
              <span class="pill">Zero lock-in</span>
              <span class="pill">Live API sourced</span>
              <span class="pill">Pay per export</span>
              <span class="pill">AI-ready via MCP</span>
            </div>
            <p class="muted">Traditional lead subscriptions leak money through stale records, unused credits, and disconnected tooling. LeadsMCP is the live-data alternative for RevOps, AI ops, agencies, and growth teams who want aligned unit economics.</p>
          </div>

          <aside class="poster">
            <div class="poster-kicker">
              <span>Disruption model</span>
              <span>Show first, pay to export</span>
            </div>
            <div class="poster-board">
              <div class="poster-row">
                <div class="poster-card">
                  <div class="metric-label">Legacy stack</div>
                  <h3>The leaky bucket</h3>
                  <div class="poster-list">
                    <span>Flat subscription spend regardless of usage</span>
                    <span>Stale contact records and wasted credits</span>
                    <span>CSV handoffs across scrapers, verifiers, and CRMs</span>
                  </div>
                </div>
                <div class="poster-arrow">→</div>
                <div class="poster-card">
                  <div class="metric-label">LeadsMCP</div>
                  <h3>Live lead acquisition loop</h3>
                  <div class="poster-list">
                    <span>Live API query</span>
                    <span>Qualification and verification</span>
                    <span>Free preview before export</span>
                    <span>Metered billing and instant CRM sync</span>
                  </div>
                </div>
              </div>
              <div class="poster-card">
                <div class="metric-label">Why teams switch</div>
                <h3>Fresh data with cost alignment built in</h3>
                <p class="muted">Instead of prepaying for database seats, you run the search, inspect the results, and only trigger billing when you keep the leads.</p>
              </div>
            </div>
          </aside>
        </div>

        <div class="container">
          <div class="metric-band">
            <article class="card">
              <div class="metric-label">Primary keyword</div>
              <div class="metric-value">MCP lead generation software</div>
            </article>
            <article class="card">
              <div class="metric-label">Positioning</div>
              <div class="metric-value">Live API, not static lists</div>
            </article>
            <article class="card">
              <div class="metric-label">Pricing model</div>
              <div class="metric-value">Free preview, pay per export</div>
            </article>
            <article class="card">
              <div class="metric-label">Workflow</div>
              <div class="metric-value">MCP to CRM in one flow</div>
            </article>
          </div>
        </div>
      </section>

      <section class="section">
        <div class="container comparison-grid">
          <div class="card">
            <div class="section-heading" style="margin-bottom: var(--space-5);">
              <p class="eyebrow">The Old Model</p>
              <h2>The old subscription model is a leaky bucket.</h2>
              <p class="muted">Static lead databases force you to pay for records you do not trust and volumes you may never actually export.</p>
            </div>
            <div class="problem-stack">
              <div class="list-item"><span class="badge">1</span><div><strong>Static data</strong><p class="muted">By the time a list is downloaded from a legacy platform, job changes and inbox churn have already eroded the accuracy.</p></div></div>
              <div class="list-item"><span class="badge">2</span><div><strong>Wasted spend</strong><p class="muted">You still pay the same monthly fee whether you export 10 leads or 10,000.</p></div></div>
              <div class="list-item"><span class="badge">3</span><div><strong>Fragmented tech</strong><p class="muted">Scraper, verifier, CRM sync, and AI orchestration often live in separate tools stitched together with manual workarounds.</p></div></div>
            </div>
          </div>

          <div class="card" id="pricing-model">
            <div class="section-heading" style="margin-bottom: var(--space-5);">
              <p class="eyebrow">The Disruption Model</p>
              <h2>Show first, pay to export.</h2>
              <p class="muted">LeadsMCP flips the category by aligning your spend to the leads you actually keep.</p>
            </div>
            <div class="flow-stack">
              <div class="list-item"><span class="badge">A</span><div><strong>Free preview</strong><p class="muted">Search, filter, and qualify before a billable action happens.</p></div></div>
              <div class="list-item"><span class="badge">B</span><div><strong>Metered checkout</strong><p class="muted">Stripe usage events fire only when you export or push qualified leads.</p></div></div>
              <div class="list-item"><span class="badge">C</span><div><strong>Performance economics</strong><p class="muted">You stop paying for unused seats and switch to a cost model built around actual lead output.</p></div></div>
            </div>
          </div>
        </div>
      </section>

      <section class="section">
        <div class="container">
          <div class="section-heading">
            <p class="eyebrow">3-Layer Architecture</p>
            <h2>Every lead is enriched before you ever pay a dime.</h2>
            <p class="muted">LeadsMCP is designed as a live enrichment stack, not a list resale business. That means the lead is built in real time, qualified, and verified before export.</p>
          </div>
          <div class="architecture-grid">
            <article class="feature-card">
              <div class="metric-label">Layer 1</div>
              <h3>Deep search scraper</h3>
              <p class="muted">Pull foundational business data from live mapping and search sources the moment you run the query.</p>
            </article>
            <article class="feature-card">
              <div class="metric-label">Layer 2</div>
              <h3>Contact enrichment</h3>
              <p class="muted">Scrape domains for emails, phone numbers, social links, and company context in real time.</p>
            </article>
            <article class="feature-card">
              <div class="metric-label">Layer 3</div>
              <h3>Bulk verification</h3>
              <p class="muted">Confirm deliverability before export so your sender reputation is protected instead of burned on stale data.</p>
            </article>
          </div>
        </div>
      </section>

      <section class="section">
        <div class="container">
          <div class="section-heading">
            <p class="eyebrow">Core Features</p>
            <h2>Built for growth teams, RevOps, and AI operators.</h2>
            <p class="muted">The same stack can power a founder’s first outbound sprint, an agency’s client pipeline, or an internal AI workflow connected over <a class="link-inline" href="{_safe(support_page)}">Model Context Protocol</a>.</p>
          </div>
          <div class="feature-grid">
            <article class="feature-card">
              <h3>Live API scraping</h3>
              <p class="muted">Query the web at the moment of search instead of relying on months-old database snapshots.</p>
            </article>
            <article class="feature-card">
              <h3>MCP native</h3>
              <p class="muted">Connect directly into AI agents and LLM workflows so lead research and enrichment become callable tools.</p>
            </article>
            <article class="feature-card">
              <h3>Unlimited free previews</h3>
              <p class="muted">Inspect the qualified set before billing. The paywall only appears when you choose to export.</p>
            </article>
            <article class="feature-card">
              <h3>Automated CRM sync</h3>
              <p class="muted">Push structured lead payloads into GoHighLevel and other downstream workflows without manual CSV cleanup.</p>
            </article>
            <article class="feature-card">
              <h3>Graduated metered pricing</h3>
              <p class="muted">Pay a micro-transaction per lead instead of locking into enterprise contracts before you know the output quality.</p>
            </article>
            <article class="feature-card">
              <h3>Sales prospecting automation</h3>
              <p class="muted">Move from prompt to preview to verified export in one continuous operating flow.</p>
            </article>
          </div>
        </div>
      </section>

      <section class="section">
        <div class="container">
          <div class="section-heading">
            <p class="eyebrow">Workflow</p>
            <h2>How the pay-per-export flow works.</h2>
            <p class="muted">Automated lead generation simplified into a frictionless pipeline your team or AI agent can operate end to end.</p>
          </div>
          <div class="timeline">
            <article class="timeline-step" data-step="1">
              <h3>Filter &amp; query</h3>
              <p class="muted">Define industry, location, title, or prompt-based search criteria.</p>
            </article>
            <article class="timeline-step" data-step="2">
              <h3>Scrape &amp; qualify</h3>
              <p class="muted">Run live search, deduplication, and verification against the current web.</p>
            </article>
            <article class="timeline-step" data-step="3">
              <h3>Preview for free</h3>
              <p class="muted">Inspect the results with no charge while you decide what to keep.</p>
            </article>
            <article class="timeline-step" data-step="4">
              <h3>Export on approval</h3>
              <p class="muted">Stripe metering logs the billable event only when you export.</p>
            </article>
            <article class="timeline-step" data-step="5">
              <h3>Instant sync</h3>
              <p class="muted">Send leads to your CRM or return them directly into your AI workflow.</p>
            </article>
          </div>
        </div>
      </section>

      <section class="section">
        <div class="container proof-zone">
          <div class="card">
            <div class="section-heading" style="margin-bottom: var(--space-5);">
              <p class="eyebrow">Pipeline Impact</p>
              <h2>Accelerate pipeline without enterprise data waste.</h2>
              <p class="muted">LeadsMCP is designed to improve margins, deliverability, and operator time by collapsing multiple lead tools into one live-data workflow.</p>
            </div>
            <div class="list">
              <div class="list-item"><span class="badge">1</span><div><strong>Save hours</strong><p class="muted">Eliminate manual list building, CSV formatting, and cross-tool reconciliation.</p></div></div>
              <div class="list-item"><span class="badge">2</span><div><strong>Protect deliverability</strong><p class="muted">Live verification helps reduce bounce risk before leads ever touch your outbound systems.</p></div></div>
              <div class="list-item"><span class="badge">3</span><div><strong>Automate AI outbound</strong><p class="muted">Give custom GPTs and AI agents secure access to verified lead generation tools via MCP.</p></div></div>
              <div class="list-item"><span class="badge">4</span><div><strong>Radical ROI</strong><p class="muted">Shift from prepaid database seats to a performance-aligned acquisition model.</p></div></div>
            </div>
          </div>

          <aside class="proof-placeholder">
            <p class="eyebrow">Proof Zone</p>
            <h2 style="font-size: var(--text-xl); margin-bottom: var(--space-3);">Ready for real logos and case studies.</h2>
            <p class="muted">I left this section intentionally honest. It is designed to hold your real customer logos, one verified testimonial, and case-study proof without hardcoding fake social proof onto the page.</p>
            <div class="pill-row">
              <span class="pill">99.8% data accuracy target</span>
              <span class="pill">Zero lock-in contracts</span>
              <span class="pill">100% live API sourced</span>
            </div>
          </aside>
        </div>
      </section>

      <section class="section">
        <div class="container">
          <div class="section-heading">
            <p class="eyebrow">Who It Is For</p>
            <h2>Built for operators who want output, not shelfware.</h2>
          </div>
          <div class="audience-grid">
            <article class="feature-card">
              <h3>B2B founders &amp; solo freelancers</h3>
              <p class="muted">Generate the first qualified leads each month without committing to large software contracts up front.</p>
            </article>
            <article class="feature-card">
              <h3>Growth marketers &amp; agencies</h3>
              <p class="muted">Run multiple client pipelines, preview leads before export, and keep tighter control over data resale margins.</p>
            </article>
            <article class="feature-card">
              <h3>AI Ops &amp; RevOps teams</h3>
              <p class="muted">Connect hyper-scale lead workflows into internal MCP servers and automated CRM routing for outbound teams.</p>
            </article>
          </div>
        </div>
      </section>

      <section class="section">
        <div class="container">
          <div class="section-heading">
            <p class="eyebrow">FAQ</p>
            <h2>Questions technical and commercial buyers ask first.</h2>
          </div>
          <div class="faq-grid">
            {"".join(
                f'''
            <details class="faq-item">
              <summary>{html.escape(item["question"])}</summary>
              <p>{html.escape(item["answer"])}</p>
            </details>
            '''
                for item in faq_items
            )}
          </div>
        </div>
      </section>

      <section class="section">
        <div class="container">
          <div class="final-cta">
            <p class="eyebrow">Ready to disrupt your lead generation?</p>
            <h2 style="margin-bottom: var(--space-4);">Stop paying for a leaky bucket.</h2>
            <p class="hero-sub" style="max-width: 48rem;">Run your first search, preview your leads for free, and only pay for the results you keep. If you want the technical path, the docs and MCP connection details are already live.</p>
            <div class="hero-cta">
              <a class="btn btn-primary" href="{_safe(install_href)}">Build Your First List for Free</a>
              <a class="btn btn-ghost" href="{_safe(support_page)}">Read the Documentation</a>
              <a class="btn btn-ghost" href="{_safe(pricing_anchor)}">See the pricing model</a>
            </div>
          </div>
        </div>
      </section>
    </main>

    <footer>
      <div class="container">
        <p>LeadsMCP · MCP lead generation software · <a class="link-inline" href="{_safe(support_page)}">Docs</a> · <a class="link-inline" href="{_safe(contact_page)}">Contact</a> · <a class="link-inline" href="{_safe(github_url)}" target="_blank" rel="noopener noreferrer">GitHub</a></p>
      </div>
    </footer>
  </div>

  {_theme_script()}
</body>
</html>
"""
    )


def build_support_page(*, base_url: str, install_url: str, github_url: str) -> str:
    base = base_url.rstrip("/")
    install_href = f"{base}/oauth/ghl/start"

    callback_hyphen = f"{base}/leadsmcp-install/"
    callback_slash = f"{base}/leadsmcp/install"
    oauth_start = f"{base}/oauth/ghl/start"
    oauth_exchange = f"{base}/oauth/ghl/exchange"
    oauth_refresh = f"{base}/oauth/ghl/refresh"
    mcp_endpoint = f"{base}/mcp"
    health_endpoint = f"{base}/health"
    contact_page = f"{base}/contact"
    support_page = f"{base}/support"

    connector_json = f"""{{
  \"mcpServers\": {{
    \"leadsmcp\": {{
      \"url\": \"{mcp_endpoint}\", 
      \"transport\": \"streamable_http\",
      \"headers\": {{
        \"x-mcp-secret\": \"<your_mcp_secret>\",
        \"Authorization\": \"Bearer <ghl_access_or_pit_token>\",
        \"locationId\": \"<ghl_location_id>\",
        \"x-ghl-version\": \"2021-07-28\"
      }}
    }}
  }}
}}"""

    mcp_remote_cmd = f"""npx -y mcp-remote {mcp_endpoint} \\
  --transport http-only \\
  --header \"x-mcp-secret: <your_mcp_secret>\" \\
  --header \"Authorization: Bearer <ghl_access_token>\" \\
  --header \"locationId: <ghl_location_id>\" \\
  --header \"x-ghl-version: 2021-07-28\""""

    typingmind_cmd = """PORT=8080 npx @typingmind/mcp <connector_id>"""

    exchange_curl = f"""curl -X POST {oauth_exchange} \\
  -H \"Content-Type: application/json\" \\
  -H \"x-mcp-secret: <your_mcp_secret>\" \\
  -d '{{\"code\":\"<oauth_code>\",\"user_type\":\"Location\",\"redirect_uri\":\"{callback_hyphen}\"}}'"""

    refresh_curl = f"""curl -X POST {oauth_refresh} \\
  -H \"Content-Type: application/json\" \\
  -H \"x-mcp-secret: <your_mcp_secret>\" \\
  -d '{{\"refresh_token\":\"<refresh_token>\",\"user_type\":\"Location\",\"redirect_uri\":\"{callback_hyphen}\"}}'"""

    return (
        _common_head("LeadsMCP Support Hub")
        + f"""
<body>
  <nav>
    <div class=\"container\">
      <div class=\"nav-inner\">
        <a href=\"{_safe(support_page)}\" class=\"brand\"><span class=\"dot\"></span>LeadsMCP Support</a>
        <div class=\"nav-actions\">
          <button class=\"theme-toggle\" data-theme-toggle aria-label=\"Switch theme\"></button>
          <a class=\"btn btn-ghost\" href=\"{_safe(github_url)}\" target=\"_blank\" rel=\"noopener noreferrer\">GitHub</a>
          <a class=\"btn btn-primary\" href=\"{_safe(contact_page)}\">Book Setup Call</a>
        </div>
      </div>
    </div>
  </nav>

  <section class=\"hero\">
    <div class=\"container\">
      <div class=\"hero-content\">
        <p class=\"eyebrow\">Marketplace Support Ready</p>
        <h1>LeadsMCP support, install, and automation links in one place.</h1>
        <p class=\"hero-sub\">Use this page as your GHL Marketplace support URL. It includes install actions, OAuth callback paths, MCP connection snippets, and export-billing flow safeguards.</p>
        <div class=\"hero-cta\">
          <a class=\"btn btn-primary\" href=\"{_safe(install_href)}\" target=\"_blank\" rel=\"noopener noreferrer\">Install LeadsMCP</a>
          <a class=\"btn btn-ghost\" href=\"{_safe(mcp_endpoint)}\" target=\"_blank\" rel=\"noopener noreferrer\">Open MCP Endpoint</a>
          <a class=\"btn btn-ghost\" href=\"{_safe(health_endpoint)}\" target=\"_blank\" rel=\"noopener noreferrer\">Health Check</a>
        </div>
      </div>
    </div>
  </section>

  <section class=\"section\">
    <div class=\"container\">
      <div class=\"grid\">
        <article class=\"card\" style=\"grid-column: span 12;\">
          <h2>Install + OAuth Routes</h2>
          <p class=\"muted\">Use these exact URLs for your marketplace install flow and app backend automation.</p>
          <div class=\"list\">
            <div class=\"list-item\"><span class=\"badge\">Install</span><div><div class=\"route\">{_safe(install_href)}</div><p class=\"muted\">Primary install button target.</p></div></div>
            <div class=\"list-item\"><span class=\"badge\">OAuth Start</span><div><div class=\"route\">{_safe(oauth_start)}</div><p class=\"muted\">Signed state redirect entrypoint.</p></div></div>
            <div class=\"list-item\"><span class=\"badge\">Callback</span><div><div class=\"route\">{_safe(callback_hyphen)}</div><p class=\"muted\">Recommended callback alias for marketplace apps.</p></div></div>
            <div class=\"list-item\"><span class=\"badge\">Callback Alias</span><div><div class=\"route\">{_safe(callback_slash)}</div><p class=\"muted\">Legacy-safe alias route.</p></div></div>
            <div class=\"list-item\"><span class=\"badge\">Exchange</span><div><div class=\"route\">{_safe(oauth_exchange)}</div><p class=\"muted\">Backend code exchange endpoint (requires <code>x-mcp-secret</code>).</p></div></div>
            <div class=\"list-item\"><span class=\"badge\">Refresh</span><div><div class=\"route\">{_safe(oauth_refresh)}</div><p class=\"muted\">Backend refresh endpoint (requires <code>x-mcp-secret</code>).</p></div></div>
          </div>
        </article>

        <article class=\"card\" style=\"grid-column: span 12;\">
          <h2>MCP Client Configuration</h2>
          <p class=\"muted\">Compatible with tools expecting official GHL-style headers (`Authorization`, `locationId`) plus your `x-mcp-secret`.</p>
          <pre><code>{html.escape(connector_json)}</code></pre>
        </article>

        <article class=\"card\" style=\"grid-column: span 6;\">
          <h3>TypingMind Runner</h3>
          <p class=\"muted\">Use this runner command after creating your custom connector.</p>
          <pre><code>{html.escape(typingmind_cmd)}</code></pre>
          <p class=\"muted\">Keep the process running while TypingMind is connected.</p>
        </article>

        <article class=\"card\" style=\"grid-column: span 6;\">
          <h3>mcp-remote Bridge</h3>
          <p class=\"muted\">Bridge to desktop clients that need local STDIO transport.</p>
          <pre><code>{html.escape(mcp_remote_cmd)}</code></pre>
        </article>

        <article class=\"card\" style=\"grid-column: span 6;\">
          <h3>OAuth Code Exchange Example</h3>
          <pre><code>{html.escape(exchange_curl)}</code></pre>
        </article>

        <article class=\"card\" style=\"grid-column: span 6;\">
          <h3>OAuth Refresh Example</h3>
          <pre><code>{html.escape(refresh_curl)}</code></pre>
        </article>

        <article class=\"card\" style=\"grid-column: span 12;\">
          <h2>Automation Flow Links</h2>
          <div class=\"hero-cta\">
            <a class=\"btn btn-primary\" href=\"{_safe(mcp_endpoint)}\" target=\"_blank\" rel=\"noopener noreferrer\">MCP Endpoint</a>
            <a class=\"btn btn-ghost\" href=\"{_safe(health_endpoint)}\" target=\"_blank\" rel=\"noopener noreferrer\">Health</a>
            <a class=\"btn btn-ghost\" href=\"{_safe(oauth_start)}\" target=\"_blank\" rel=\"noopener noreferrer\">OAuth Start</a>
            <a class=\"btn btn-ghost\" href=\"{_safe(callback_hyphen)}\" target=\"_blank\" rel=\"noopener noreferrer\">Callback Alias</a>
            <a class=\"btn btn-ghost\" href=\"{_safe(contact_page)}\">Contact + Booking</a>
          </div>
        </article>
      </div>
    </div>
  </section>

  <footer>
    <div class=\"container\">
      <p>LeadsMCP support hub · Marketplace links current · Never publish raw OAuth or MCP secrets.</p>
    </div>
  </footer>

  {_theme_script()}
</body>
</html>
"""
    )


def build_contact_page(*, base_url: str, github_url: str, install_url: str) -> str:
    base = base_url.rstrip("/")
    support_page = f"{base}/support"
    install_href = f"{base}/oauth/ghl/start"

    return (
        _common_head("Contact LeadsMCP")
        + f"""
<body>
  <nav>
    <div class=\"container\">
      <div class=\"nav-inner\">
        <a href=\"{_safe(support_page)}\" class=\"brand\"><span class=\"dot\"></span>LeadsMCP Contact</a>
        <div class=\"nav-actions\">
          <button class=\"theme-toggle\" data-theme-toggle aria-label=\"Switch theme\"></button>
          <a class=\"btn btn-ghost\" href=\"{_safe(support_page)}\">Support Hub</a>
          <a class=\"btn btn-ghost\" href=\"{_safe(github_url)}\" target=\"_blank\" rel=\"noopener noreferrer\">GitHub</a>
          <a class=\"btn btn-primary\" href=\"{_safe(install_href)}\" target=\"_blank\" rel=\"noopener noreferrer\">Install LeadsMCP</a>
        </div>
      </div>
    </div>
  </nav>

  <section class=\"hero\">
    <div class=\"container\">
      <div class=\"hero-content\">
        <p class=\"eyebrow\">Need Help Fast?</p>
        <h1>Book a setup call for your GHL Marketplace install.</h1>
        <p class=\"hero-sub\">Use the calendar below for onboarding help, OAuth troubleshooting, MCP connector setup, and export-billing flow validation.</p>
      </div>
    </div>
  </section>

  <section class=\"section\">
    <div class=\"container\">
      <div class=\"split\">
        <article class=\"card\">
          <h2>Book Time</h2>
          <p class=\"muted\">Pick an available slot and we can walk through your install live.</p>
          <div class=\"contact-shell\" style=\"margin-top: var(--space-4);\">
            <iframe src=\"https://api.leadconnectorhq.com/widget/booking/YJLn2n99ZpsSoQ8NqAz5\" style=\"width: 100%;border:none;overflow: hidden;\" scrolling=\"no\" id=\"YJLn2n99ZpsSoQ8NqAz5_1775407751459\"></iframe><br>
          </div>
        </article>

        <aside class=\"card\">
          <h3>Quick Access Links</h3>
          <p class=\"muted\">These are the links typically needed during support sessions.</p>
          <div class=\"list\">
            <div class=\"list-item\"><span class=\"badge\">Support</span><div class=\"route\">{_safe(support_page)}</div></div>
            <div class=\"list-item\"><span class=\"badge\">Install</span><div class=\"route\">{_safe(install_href)}</div></div>
            <div class=\"list-item\"><span class=\"badge\">MCP</span><div class=\"route\">{_safe(base)}/mcp</div></div>
            <div class=\"list-item\"><span class=\"badge\">Health</span><div class=\"route\">{_safe(base)}/health</div></div>
            <div class=\"list-item\"><span class=\"badge\">Callback</span><div class=\"route\">{_safe(base)}/leadsmcp-install/</div></div>
          </div>

          <div class=\"hero-cta\" style=\"margin-top: var(--space-5);\">
            <a class=\"btn btn-primary\" href=\"{_safe(support_page)}\">Open Support Hub</a>
            <a class=\"btn btn-ghost\" href=\"{_safe(github_url)}\" target=\"_blank\" rel=\"noopener noreferrer\">Repo Docs</a>
          </div>
        </aside>
      </div>
    </div>
  </section>

  <footer>
    <div class=\"container\">
      <p>LeadsMCP contact page · Styled to match MCP Orchestrator theme.</p>
    </div>
  </footer>

  <script src=\"https://link.msgsndr.com/js/form_embed.js\" type=\"text/javascript\"></script>
  {_theme_script()}
</body>
</html>
"""
    )


def build_install_success_page(*, base_url: str, github_url: str, install_url: str, webhook_url: str) -> str:
    base = base_url.rstrip("/")
    support_page = f"{base}/support"
    contact_page = f"{base}/contact"
    install_page = f"{base}/app-install-successfully"
    search_page = f"{base}/app/lead-search"
    mcp_url = f"{base}/mcp"
    chatgpt_docs = "https://help.openai.com/en/articles/12584461-developer-mode-apps-and-full-mcp-connectors-in-chatgpt-beta"
    claude_docs = "https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp"
    google_docs = "https://developers.google.com/maps/ai/mcp"
    vertex_docs = "https://adk.dev/tools-custom/mcp-tools/"

    template = _common_head("LeadsMCP Installed") + """
<body data-webhook-url="__WEBHOOK_URL__">
  <style>
    .success-grid {
      display: grid;
      gap: var(--space-4);
      grid-template-columns: 1.15fr 0.85fr;
      align-items: start;
    }
    .success-stack {
      display: grid;
      gap: var(--space-4);
    }
    .success-hero {
      position: relative;
      overflow: hidden;
      background:
        radial-gradient(circle at 15% 10%, color-mix(in srgb, var(--color-primary) 18%, transparent), transparent 40%),
        radial-gradient(circle at 85% 5%, color-mix(in srgb, var(--color-accent2) 14%, transparent), transparent 36%),
        var(--color-bg);
    }
    .success-hero .hero-sub {
      max-width: 68ch;
    }
    .hero-checklist {
      display: flex;
      flex-wrap: wrap;
      gap: var(--space-2);
      margin-top: var(--space-5);
    }
    .hero-checklist .pill {
      background: color-mix(in srgb, var(--color-primary-dim) 76%, transparent);
      border: 1px solid color-mix(in srgb, var(--color-primary) 28%, transparent);
    }
    .status-banner {
      display: grid;
      gap: var(--space-3);
      padding: var(--space-5);
      border-radius: var(--radius-xl);
      border: 1px solid color-mix(in srgb, var(--color-primary) 26%, var(--color-border));
      background:
        linear-gradient(145deg, color-mix(in srgb, var(--color-primary-dim) 70%, transparent), color-mix(in srgb, var(--color-surface) 96%, transparent));
    }
    .status-banner.is-warning {
      border-color: color-mix(in srgb, #ffce73 45%, var(--color-border));
      background:
        linear-gradient(145deg, rgba(255, 206, 115, 0.10), color-mix(in srgb, var(--color-surface) 96%, transparent));
    }
    .status-line {
      display: inline-flex;
      align-items: center;
      gap: var(--space-2);
      font-weight: 700;
      font-size: var(--text-lg);
    }
    .status-dot {
      width: 12px;
      height: 12px;
      border-radius: 999px;
      background: var(--color-primary);
      box-shadow: 0 0 18px color-mix(in srgb, var(--color-primary) 40%, transparent);
      flex: 0 0 auto;
    }
    .status-dot.warning {
      background: #ffce73;
      box-shadow: 0 0 18px rgba(255, 206, 115, 0.42);
    }
    .kv-grid {
      display: grid;
      gap: var(--space-3);
      margin-top: var(--space-5);
    }
    .kv-row {
      display: grid;
      grid-template-columns: 110px 1fr;
      gap: var(--space-3);
      align-items: baseline;
      padding-bottom: var(--space-3);
      border-bottom: 1px solid var(--color-divider);
    }
    .kv-row:last-child {
      border-bottom: 0;
      padding-bottom: 0;
    }
    .kv-label {
      font-size: var(--text-xs);
      color: var(--color-text-faint);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    .kv-value {
      font-family: var(--font-mono);
      color: var(--color-text);
      word-break: break-word;
    }
    .copy-shell {
      display: grid;
      gap: var(--space-3);
      padding: var(--space-5);
      border-radius: var(--radius-xl);
      border: 1px solid var(--color-border);
      background: color-mix(in srgb, var(--color-surface) 94%, transparent);
    }
    .copy-shell h3 {
      margin-bottom: 0;
    }
    .copy-row {
      display: flex;
      flex-wrap: wrap;
      gap: var(--space-3);
      align-items: center;
      justify-content: space-between;
    }
    .copy-value {
      font-family: var(--font-mono);
      font-size: var(--text-sm);
      color: var(--color-text);
      word-break: break-word;
    }
    .code-card {
      display: grid;
      gap: var(--space-3);
      padding: var(--space-5);
      border-radius: var(--radius-xl);
      border: 1px solid var(--color-border);
      background:
        linear-gradient(180deg, color-mix(in srgb, var(--color-surface) 96%, transparent), color-mix(in srgb, var(--color-surface-2) 94%, transparent));
    }
    .code-card pre {
      margin: 0;
      max-height: 360px;
      overflow: auto;
      padding: var(--space-4);
      border-radius: var(--radius-lg);
      border: 1px solid color-mix(in srgb, var(--color-border) 92%, transparent);
      background: #07080a;
      color: #d9fff4;
      font-size: 0.84rem;
      line-height: 1.6;
    }
    .client-grid {
      display: grid;
      gap: var(--space-4);
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .client-card {
      display: grid;
      gap: var(--space-4);
      padding: var(--space-5);
      border-radius: var(--radius-xl);
      border: 1px solid var(--color-border);
      background:
        linear-gradient(180deg, color-mix(in srgb, var(--color-surface-2) 92%, transparent), color-mix(in srgb, var(--color-surface) 96%, transparent));
    }
    .client-head {
      display: flex;
      justify-content: space-between;
      gap: var(--space-3);
      align-items: start;
    }
    .client-status {
      display: inline-flex;
      align-items: center;
      gap: var(--space-2);
      padding: 0.3rem 0.7rem;
      border-radius: 999px;
      font-size: var(--text-xs);
      font-weight: 700;
      letter-spacing: 0.04em;
      text-transform: uppercase;
      border: 1px solid var(--color-border);
      color: var(--color-text-muted);
      background: color-mix(in srgb, var(--color-surface-offset) 88%, transparent);
      flex: 0 0 auto;
    }
    .client-status.good {
      color: var(--color-primary);
      border-color: color-mix(in srgb, var(--color-primary) 24%, transparent);
      background: color-mix(in srgb, var(--color-primary-dim) 72%, transparent);
    }
    .client-status.warn {
      color: #ffce73;
      border-color: color-mix(in srgb, #ffce73 34%, transparent);
      background: rgba(255, 206, 115, 0.10);
    }
    .client-status.info {
      color: var(--color-accent2);
      border-color: color-mix(in srgb, var(--color-accent2) 30%, transparent);
      background: color-mix(in srgb, var(--color-accent2) 12%, transparent);
    }
    .client-card ul {
      display: grid;
      gap: var(--space-2);
      padding-left: 1.2rem;
      color: var(--color-text-muted);
    }
    .client-card p {
      color: var(--color-text-muted);
      margin: 0;
    }
    .snippet-grid {
      display: grid;
      gap: var(--space-4);
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .full-span {
      grid-column: 1 / -1;
    }
    .callout-list {
      display: grid;
      gap: var(--space-3);
    }
    .callout-item {
      display: flex;
      gap: var(--space-3);
      align-items: start;
    }
    .callout-item .badge {
      margin-top: 0.1rem;
    }
    @media (max-width: 1100px) {
      .success-grid,
      .client-grid,
      .snippet-grid {
        grid-template-columns: 1fr;
      }
    }
    @media (max-width: 720px) {
      .kv-row {
        grid-template-columns: 1fr;
        gap: var(--space-1);
      }
      .client-head,
      .copy-row {
        flex-direction: column;
        align-items: stretch;
      }
    }
  </style>

  <nav>
    <div class="container nav-inner">
      <a href="__INSTALL_PAGE__" class="brand"><span class="dot"></span>LeadsMCP Installed</a>
      <div class="nav-actions">
        <a class="btn btn-ghost" href="__SEARCH_PAGE__">Open Search Workspace</a>
        <a class="btn btn-ghost" href="__SUPPORT_PAGE__">Support Hub</a>
        <a class="btn btn-primary" href="__CONTACT_PAGE__">Book Setup Call</a>
        <button class="theme-toggle" type="button" data-theme-toggle aria-label="Toggle theme">◐</button>
      </div>
    </div>
  </nav>

  <main>
    <section class="hero success-hero">
      <div class="container hero-content">
        <div class="eyebrow">Installation Confirmed</div>
        <h1>Your LeadsMCP app is installed in GoHighLevel.</h1>
        <p class="hero-sub">This page confirms the install, shows which GHL location is connected, and gives you the exact MCP endpoint and starter configs you need to connect a supported AI client.</p>
        <div class="hero-checklist">
          <span class="pill">App installed</span>
          <span class="pill">Location linked</span>
          <span class="pill">Managed token refresh enabled</span>
        </div>
        <div class="hero-cta" style="margin-top: var(--space-6);">
          <a class="btn btn-primary" href="__SEARCH_PAGE__">Open Search Workspace</a>
          <a class="btn btn-ghost" href="__SUPPORT_PAGE__">Read Support Guide</a>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="container success-grid">
        <div class="success-stack">
          <article class="card">
            <div class="status-banner" data-status-banner>
              <div class="status-line"><span class="status-dot" data-status-dot></span><span data-install-headline>Reading install status...</span></div>
              <p class="muted" data-install-summary style="margin-bottom: 0;">We are reading the post-install query string and validating the connected company and location.</p>
            </div>

            <div class="kv-grid">
              <div class="kv-row"><div class="kv-label">Status</div><div class="kv-value" data-install-status>Waiting for query params...</div></div>
              <div class="kv-row"><div class="kv-label">Company</div><div class="kv-value" data-company-id>Not provided</div></div>
              <div class="kv-row"><div class="kv-label">Location</div><div class="kv-value" data-location-id>Not provided</div></div>
              <div class="kv-row"><div class="kv-label">User Type</div><div class="kv-value" data-user-type>Not provided</div></div>
              <div class="kv-row"><div class="kv-label">Install Stored</div><div class="kv-value" data-install-stored>Not provided</div></div>
            </div>
          </article>

          <article class="copy-shell">
            <div class="copy-row">
              <div>
                <div class="metric-label">Remote MCP URL</div>
                <div class="copy-value" data-mcp-url>__MCP_URL__</div>
              </div>
              <button class="btn btn-ghost" type="button" data-copy-button data-copy-target="[data-mcp-url]">Copy URL</button>
            </div>
            <div class="copy-row">
              <div>
                <div class="metric-label">Required headers</div>
                <div class="copy-value">`x-mcp-secret`, `locationId`, `version`</div>
              </div>
            </div>
            <p class="muted" style="margin-bottom: 0;">LeadsmCP now refreshes GHL access server-side after install, so most clients only need your private MCP secret plus the connected location id.</p>
          </article>
        </div>

        <aside class="success-stack">
          <article class="card">
            <h2>What is already done</h2>
            <div class="callout-list" style="margin-top: var(--space-4);">
              <div class="callout-item"><span class="badge">1</span><div><strong>OAuth completed</strong><p class="muted">The app install flow already exchanged the GHL code and stored the managed install record.</p></div></div>
              <div class="callout-item"><span class="badge">2</span><div><strong>Location linked</strong><p class="muted">This page shows the exact company and location ids associated with the install you just finished.</p></div></div>
              <div class="callout-item"><span class="badge">3</span><div><strong>MCP endpoint ready</strong><p class="muted">You can now connect a supported MCP client and start searching, scraping, and writing back into your CRM.</p></div></div>
            </div>
          </article>

          <article class="card">
            <h2>Best next actions</h2>
            <div class="list" style="margin-top: var(--space-4);">
              <div class="list-item"><span class="badge">A</span><div>Copy the MCP URL and the starter config from this page.</div></div>
              <div class="list-item"><span class="badge">B</span><div>Choose a supported client below and paste in your connected location id.</div></div>
              <div class="list-item"><span class="badge">C</span><div>If you want ChatGPT web or Claude web direct connectors, use the platform notes below so you know which path is live today and which one still needs an OAuth-style connector version.</div></div>
            </div>
            <div class="hero-cta" style="margin-top: var(--space-6);">
              <a class="btn btn-primary" href="__INSTALL_URL__">Reinstall App</a>
              <a class="btn btn-ghost" href="__GITHUB_URL__" target="_blank" rel="noopener noreferrer">GitHub Repo</a>
            </div>
          </article>
        </aside>
      </div>
    </section>

    <section class="section">
      <div class="container">
        <article class="card">
          <p class="eyebrow">Connect Your Client</p>
          <h2>Starter configs you can copy right now</h2>
          <p class="muted">Use the detected GHL location id from this install. Keep your private `x-mcp-secret` private and paste it into the client you choose.</p>

          <div class="snippet-grid" style="margin-top: var(--space-5);">
            <div class="code-card">
              <div class="copy-row">
                <div>
                  <h3>Universal remote MCP config</h3>
                  <p class="muted" style="margin-bottom: 0;">Best for clients that support a remote MCP `url` and static headers.</p>
                </div>
                <button class="btn btn-ghost" type="button" data-copy-button data-copy-target="[data-config-json]">Copy JSON</button>
              </div>
              <pre><code data-config-json></code></pre>
            </div>

            <div class="code-card">
              <div class="copy-row">
                <div>
                  <h3>`mcp-remote` bridge command</h3>
                  <p class="muted" style="margin-bottom: 0;">Useful when the client cannot send custom headers directly.</p>
                </div>
                <button class="btn btn-ghost" type="button" data-copy-button data-copy-target="[data-bridge-command]">Copy command</button>
              </div>
              <pre><code data-bridge-command></code></pre>
            </div>

            <div class="code-card full-span">
              <div class="copy-row">
                <div>
                  <h3>Vertex AI / Google ADK example</h3>
                  <p class="muted" style="margin-bottom: 0;">This is the cleanest “Google / Vertex AI” path today if you want LeadsmCP inside your own agent runtime.</p>
                </div>
                <button class="btn btn-ghost" type="button" data-copy-button data-copy-target="[data-vertex-snippet]">Copy Python</button>
              </div>
              <pre><code data-vertex-snippet></code></pre>
            </div>
          </div>
        </article>
      </div>
    </section>

    <section class="section">
      <div class="container">
        <article class="card">
          <p class="eyebrow">Client Guide</p>
          <h2>Which LLM apps work today, and which path to use</h2>
          <div class="client-grid" style="margin-top: var(--space-5);">
            <article class="client-card">
              <div class="client-head">
                <div>
                  <h3>Google / Gemini CLI</h3>
                  <p>Best option if you want a lightweight local client that can work with MCP configs and bridge commands.</p>
                </div>
                <span class="client-status good">Ready now</span>
              </div>
              <ul>
                <li>Use the universal remote config if your Gemini client supports remote `url` plus headers.</li>
                <li>If it does not, use the `mcp-remote` bridge command above.</li>
                <li>Google’s MCP docs show Gemini CLI and related tools as standard MCP clients, and Google’s ADK also supports MCP over HTTP for agent runtimes.</li>
              </ul>
              <a class="btn btn-ghost" href="__GOOGLE_DOCS__" target="_blank" rel="noopener noreferrer">Google MCP docs</a>
            </article>

            <article class="client-card">
              <div class="client-head">
                <div>
                  <h3>Vertex AI / ADK</h3>
                  <p>Use this if you are building your own agent on Google Cloud and want LeadsmCP as a remote toolset.</p>
                </div>
                <span class="client-status good">Ready now</span>
              </div>
              <ul>
                <li>Use the Python snippet above with `StreamableHTTPConnectionParams`.</li>
                <li>This gives you a durable, code-first integration instead of relying on a consumer chat UI.</li>
                <li>It is the strongest path today for “Vertex AI + LeadsmCP”.</li>
              </ul>
              <a class="btn btn-ghost" href="__VERTEX_DOCS__" target="_blank" rel="noopener noreferrer">ADK MCP docs</a>
            </article>

            <article class="client-card">
              <div class="client-head">
                <div>
                  <h3>ChatGPT</h3>
                  <p>ChatGPT supports custom MCP apps/connectors, but the current LeadsmCP production server is still optimized for static-header clients.</p>
                </div>
                <span class="client-status warn">Next step</span>
              </div>
              <ul>
                <li>OpenAI’s current docs say full MCP with write actions is on workspace plans, and direct remote servers must be remote rather than local.</li>
                <li>LeadsmCP can already power write actions, but a smooth ChatGPT web connector flow needs an OAuth-style connector version instead of today’s static-header setup.</li>
                <li>If you want this path first, book setup and we can move that connector version to the top of the roadmap.</li>
              </ul>
              <a class="btn btn-ghost" href="__CHATGPT_DOCS__" target="_blank" rel="noopener noreferrer">ChatGPT MCP docs</a>
            </article>

            <article class="client-card">
              <div class="client-head">
                <div>
                  <h3>Claude</h3>
                  <p>Claude web and Claude Desktop both support remote MCP connectors, but they expect authless or OAuth-style remote connections.</p>
                </div>
                <span class="client-status warn">Next step</span>
              </div>
              <ul>
                <li>Anthropic’s docs show remote connectors on Claude, Claude Desktop, and mobile, with connections brokered from Anthropic’s cloud.</li>
                <li>LeadsmCP’s direct Claude web connector path still needs a connector-friendly auth flow instead of custom static headers.</li>
                <li>Today, use a header-capable client or a bridge if you need Claude in your workflow immediately.</li>
              </ul>
              <a class="btn btn-ghost" href="__CLAUDE_DOCS__" target="_blank" rel="noopener noreferrer">Claude remote MCP docs</a>
            </article>

            <article class="client-card full-span">
              <div class="client-head">
                <div>
                  <h3>Perplexity and other research apps</h3>
                  <p>Perplexity publishes an MCP server for its own APIs, but we could not find official docs for attaching an arbitrary third-party remote MCP server directly to the consumer Perplexity app.</p>
                </div>
                <span class="client-status info">Use a bridge</span>
              </div>
              <ul>
                <li>If your research tool supports standard `mcpServers` with a `url` and `headers`, use the universal config above.</li>
                <li>If it does not, use the `mcp-remote` bridge command or connect through your own agent runtime.</li>
                <li>This is the safest way to avoid promising a direct in-app connector flow that the vendor has not officially documented.</li>
              </ul>
            </article>
          </div>
        </article>
      </div>
    </section>
  </main>

  <script>
    (function () {
      const root = document.documentElement;
      const toggle = document.querySelector('[data-theme-toggle]');
      const savedTheme = localStorage.getItem('leadsmcp-theme');
      if (savedTheme === 'light') root.setAttribute('data-theme', 'light');

      if (toggle) {
        toggle.addEventListener('click', function () {
          const next = root.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
          root.setAttribute('data-theme', next);
          localStorage.setItem('leadsmcp-theme', next);
        });
      }

      const params = new URLSearchParams(window.location.search);
      const code = params.get('code') || '';
      const status = params.get('status') || 'unknown';
      const companyId = params.get('company_id') || 'Not provided';
      const locationId = params.get('location_id') || 'Not provided';
      const userType = params.get('user_type') || 'Not provided';
      const installStored = params.get('install_stored') || 'Not provided';
      const webhookUrl = document.body.dataset.webhookUrl || '';
      const origin = window.location.origin;
      const mcpUrl = `${origin}/mcp`;
      const effectiveLocationId = locationId && locationId !== 'Not provided' ? locationId : '<YOUR_GHL_LOCATION_ID>';
      const configJson = {
        mcpServers: {
          leadsmcp: {
            url: mcpUrl,
            headers: {
              'x-mcp-secret': '<YOUR_MCP_SECRET>',
              locationId: effectiveLocationId,
              version: '2021-07-28'
            }
          }
        }
      };
      const bridgeCommand = [
        `npx -y mcp-remote ${mcpUrl}`,
        '--transport http-only',
        '--header "x-mcp-secret: <YOUR_MCP_SECRET>"',
        `--header "locationId: ${effectiveLocationId}"`,
        '--header "version: 2021-07-28"'
      ].join(' \\\n  ');
      const vertexSnippet = [
        'from google.adk.agents.llm_agent import Agent',
        'from google.adk.tools.mcp_tool import McpToolset',
        'from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams',
        '',
        'root_agent = Agent(',
        "    model='gemini-2.0-flash',",
        "    name='leadsmcp_agent',",
        "    description='Use LeadsMCP to research companies and push structured leads into GoHighLevel.',",
        '    tools=[',
        '        McpToolset(',
        '            connection_params=StreamableHTTPConnectionParams(',
        `                url='${mcpUrl}',`,
        "                headers={",
        "                    'x-mcp-secret': '<YOUR_MCP_SECRET>',",
        `                    'locationId': '${effectiveLocationId}',`,
        "                    'version': '2021-07-28',",
        '                },',
        '            )',
        '        )',
        '    ],',
        ')'
      ].join('\\n');

      const setText = (selector, value) => {
        const node = document.querySelector(selector);
        if (node) node.textContent = value;
      };

      setText('[data-install-status]', status === 'connected' ? 'Connected successfully' : status);
      setText('[data-company-id]', companyId);
      setText('[data-location-id]', locationId);
      setText('[data-user-type]', userType);
      setText('[data-install-stored]', installStored);
      setText('[data-mcp-url]', mcpUrl);
      setText('[data-config-json]', JSON.stringify(configJson, null, 2));
      setText('[data-bridge-command]', bridgeCommand);
      setText('[data-vertex-snippet]', vertexSnippet);

      const installHeadline = document.querySelector('[data-install-headline]');
      const installSummary = document.querySelector('[data-install-summary]');
      const statusBanner = document.querySelector('[data-status-banner]');
      const statusDot = document.querySelector('[data-status-dot]');

      const goodInstall = status === 'connected' && installStored === 'true' && locationId && locationId !== 'Not provided';
      const locationScoped = companyId && locationId && companyId !== locationId && companyId !== 'Not provided' && locationId !== 'Not provided';

      if (goodInstall) {
        if (installHeadline) installHeadline.textContent = 'Installed and ready to connect';
        if (installSummary) {
          installSummary.textContent = locationScoped
            ? `LeadsMCP is installed for location ${locationId}. You can now connect a supported MCP client and start using this sub-account.`
            : `LeadsMCP is installed. Before heavy CRM usage, confirm the location id shown below is the specific GHL sub-account you want to control.`;
        }
        if (!locationScoped && statusBanner) statusBanner.classList.add('is-warning');
        if (statusDot && !locationScoped) statusDot.classList.add('warning');
      } else {
        if (installHeadline) installHeadline.textContent = 'Install finished, but needs review';
        if (installSummary) installSummary.textContent = 'The redirect completed, but one or more install values are missing. Review the company and location ids below before connecting an MCP client.';
        if (statusBanner) statusBanner.classList.add('is-warning');
        if (statusDot) statusDot.classList.add('warning');
      }

      document.querySelectorAll('[data-copy-button]').forEach((button) => {
        button.addEventListener('click', async function () {
          const target = button.getAttribute('data-copy-target');
          const source = target ? document.querySelector(target) : null;
          if (!source) return;
          const text = source.textContent || '';
          try {
            await navigator.clipboard.writeText(text);
            const original = button.textContent;
            button.textContent = 'Copied';
            window.setTimeout(() => {
              button.textContent = original;
            }, 1400);
          } catch (error) {
            console.error('Copy failed:', error);
          }
        });
      });

      if (code && webhookUrl) {
        fetch(webhookUrl, {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ code })
        })
          .then((response) => response.json())
          .then((data) => {
            console.log('Install webhook sent:', data);
          })
          .catch((error) => {
            console.error('Install webhook failed:', error);
          });
      }
    })();
  </script>
</body>
</html>
"""

    return (
        template
        .replace("__INSTALL_PAGE__", _safe(install_page))
        .replace("__SEARCH_PAGE__", _safe(search_page))
        .replace("__SUPPORT_PAGE__", _safe(support_page))
        .replace("__CONTACT_PAGE__", _safe(contact_page))
        .replace("__INSTALL_URL__", _safe(install_url))
        .replace("__MCP_URL__", _safe(mcp_url))
        .replace("__GITHUB_URL__", _safe(github_url))
        .replace("__WEBHOOK_URL__", _safe(webhook_url))
        .replace("__CHATGPT_DOCS__", _safe(chatgpt_docs))
        .replace("__CLAUDE_DOCS__", _safe(claude_docs))
        .replace("__GOOGLE_DOCS__", _safe(google_docs))
        .replace("__VERTEX_DOCS__", _safe(vertex_docs))
    )


def build_marketplace_search_page(
    *,
    base_url: str,
    github_url: str,
    context_endpoint: str,
    search_endpoint: str,
    ai_endpoint: str,
    search_config_json: str,
    mapbox_public_token: str = "",
    mapbox_style_url: str = "",
    mapbox_js_url: str = "",
    mapbox_css_url: str = "",
) -> str:
    base = base_url.rstrip("/")
    support_page = f"{base}/support"
    contact_page = f"{base}/contact"
    install_success_page = f"{base}/app-install-successfully"
    search_page = f"{base}/app/lead-search"

    template = _common_head("LeadsMCP Search Workspace") + """
<body data-context-endpoint="__CONTEXT_ENDPOINT__" data-search-endpoint="__SEARCH_ENDPOINT__" data-ai-endpoint="__AI_ENDPOINT__" data-mapbox-public-token="__MAPBOX_PUBLIC_TOKEN__" data-mapbox-style-url="__MAPBOX_STYLE_URL__" data-mapbox-js-url="__MAPBOX_JS_URL__" data-mapbox-css-url="__MAPBOX_CSS_URL__">
  <style>
    .workspace-stack {
      display: grid;
      gap: var(--space-4);
      grid-template-columns: 1.05fr 1.45fr;
      align-items: start;
    }
    .context-stack,
    .results-stack {
      display: grid;
      gap: var(--space-4);
    }
    .spotlight-panel {
      position: relative;
      overflow: hidden;
      background:
        linear-gradient(145deg, color-mix(in srgb, var(--color-surface) 82%, transparent), color-mix(in srgb, var(--color-surface-2) 92%, var(--color-accent2) 8%)),
        var(--color-surface);
    }
    .spotlight-panel::after {
      content: '';
      position: absolute;
      inset: auto -10% -35% auto;
      width: 260px;
      height: 260px;
      border-radius: 999px;
      background: radial-gradient(circle, color-mix(in srgb, var(--color-primary) 22%, transparent) 0%, transparent 68%);
      pointer-events: none;
    }
    .context-grid {
      display: grid;
      gap: var(--space-3);
      margin-top: var(--space-5);
    }
    .context-item {
      display: grid;
      grid-template-columns: 110px 1fr;
      gap: var(--space-3);
      align-items: baseline;
      padding-bottom: var(--space-3);
      border-bottom: 1px solid var(--color-divider);
    }
    .context-item:last-child {
      padding-bottom: 0;
      border-bottom: 0;
    }
    .context-label {
      color: var(--color-text-faint);
      font-size: var(--text-xs);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    .context-value {
      min-width: 0;
      font-family: var(--font-mono);
      font-size: var(--text-sm);
      color: var(--color-text);
      word-break: break-word;
    }
    .search-form-shell {
      display: grid;
      gap: var(--space-5);
    }
    .search-hero {
      display: flex;
      justify-content: space-between;
      gap: var(--space-5);
      align-items: flex-start;
    }
    .search-hero-copy {
      max-width: 62ch;
    }
    .search-hero-copy h2 {
      margin-bottom: var(--space-2);
    }
    .search-chips {
      display: flex;
      flex-wrap: wrap;
      gap: var(--space-2);
      margin-top: var(--space-3);
    }
    .search-chip {
      display: inline-flex;
      align-items: center;
      gap: var(--space-2);
      padding: 0.32rem 0.72rem;
      border-radius: 999px;
      background: var(--color-surface-offset);
      border: 1px solid color-mix(in srgb, var(--color-border) 86%, transparent);
      color: var(--color-text-muted);
      font-size: var(--text-xs);
    }
    .search-status {
      min-width: 185px;
      padding: var(--space-4);
      border-radius: var(--radius-lg);
      background: color-mix(in srgb, var(--color-primary-dim) 70%, transparent);
      border: 1px solid color-mix(in srgb, var(--color-primary) 25%, transparent);
    }
    .search-status .metric-label {
      margin-bottom: var(--space-1);
    }
    .search-status .metric-value {
      font-size: var(--text-lg);
    }
    .results-header {
      display: flex;
      justify-content: space-between;
      gap: var(--space-4);
      align-items: end;
    }
    .results-header-copy {
      max-width: 72ch;
    }
    .results-toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: var(--space-2);
      align-items: center;
    }
    .results-family {
      display: inline-flex;
      align-items: center;
      gap: var(--space-2);
      padding: 0.42rem 0.82rem;
      border-radius: 999px;
      background: color-mix(in srgb, var(--color-primary-dim) 68%, transparent);
      border: 1px solid color-mix(in srgb, var(--color-primary) 18%, var(--color-border));
      color: var(--color-text);
      font-size: var(--text-xs);
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    .results-filter-strip {
      display: flex;
      flex-wrap: wrap;
      gap: var(--space-2);
      margin-top: var(--space-4);
    }
    .results-filter-strip[hidden] {
      display: none;
    }
    .filter-chip {
      appearance: none;
      border: 1px solid var(--color-border);
      background: color-mix(in srgb, var(--color-surface-offset) 88%, transparent);
      color: var(--color-text-muted);
      border-radius: 999px;
      padding: 0.46rem 0.82rem;
      font-size: var(--text-xs);
      font-weight: 700;
      letter-spacing: 0.04em;
      cursor: pointer;
      transition: background var(--transition), color var(--transition), border-color var(--transition);
    }
    .filter-chip.is-active {
      background: var(--color-primary);
      border-color: color-mix(in srgb, var(--color-primary) 70%, transparent);
      color: var(--color-text-inverse);
    }
    .search-memory {
      display: grid;
      gap: var(--space-3);
      padding: var(--space-4);
      border-radius: var(--radius-lg);
      border: 1px solid var(--color-border);
      background: color-mix(in srgb, var(--color-surface-offset) 90%, transparent);
    }
    .search-memory-head {
      display: flex;
      justify-content: space-between;
      gap: var(--space-3);
      align-items: center;
    }
    .saved-search-list {
      display: grid;
      gap: var(--space-2);
    }
    .saved-search-item {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: var(--space-2);
      align-items: center;
      padding: var(--space-3);
      border-radius: var(--radius-md);
      border: 1px solid color-mix(in srgb, var(--color-border) 92%, transparent);
      background: color-mix(in srgb, var(--color-surface) 94%, transparent);
    }
    .saved-search-main {
      appearance: none;
      border: 0;
      background: transparent;
      color: inherit;
      text-align: left;
      cursor: pointer;
      padding: 0;
      display: grid;
      gap: var(--space-1);
    }
    .saved-search-title {
      color: var(--color-text);
      font-size: var(--text-sm);
      font-weight: 700;
    }
    .saved-search-meta {
      color: var(--color-text-muted);
      font-size: var(--text-xs);
      overflow-wrap: anywhere;
    }
    .saved-search-remove {
      appearance: none;
      border: 1px solid var(--color-border);
      background: transparent;
      color: var(--color-text-muted);
      border-radius: 999px;
      padding: 0.42rem 0.72rem;
      font-size: var(--text-xs);
      font-weight: 700;
      cursor: pointer;
    }
    .ai-launchpad {
      display: grid;
      gap: var(--space-4);
      padding: var(--space-5);
      border-radius: calc(var(--radius-xl) + 2px);
      border: 1px solid color-mix(in srgb, var(--color-primary) 18%, var(--color-border));
      background:
        radial-gradient(circle at top right, color-mix(in srgb, var(--color-primary) 14%, transparent), transparent 36%),
        linear-gradient(160deg, color-mix(in srgb, var(--color-surface) 94%, transparent), color-mix(in srgb, var(--color-surface-2) 96%, transparent));
    }
    .ai-shell {
      display: grid;
      gap: var(--space-4);
    }
    .ai-status {
      display: flex;
      flex-wrap: wrap;
      gap: var(--space-2);
      align-items: center;
    }
    .ai-thread {
      display: grid;
      gap: var(--space-3);
      min-height: 260px;
      max-height: 520px;
      overflow: auto;
      padding: var(--space-4);
      border-radius: var(--radius-lg);
      border: 1px solid var(--color-border);
      background: linear-gradient(180deg, color-mix(in srgb, var(--color-surface-2) 94%, transparent), color-mix(in srgb, var(--color-surface) 98%, transparent));
    }
    .ai-message {
      display: grid;
      gap: var(--space-2);
      max-width: min(92%, 860px);
      padding: var(--space-4);
      border-radius: var(--radius-lg);
      border: 1px solid color-mix(in srgb, var(--color-border) 88%, transparent);
      background: color-mix(in srgb, var(--color-surface) 96%, transparent);
      box-shadow: 0 14px 32px rgba(0, 0, 0, 0.12);
    }
    .ai-message.user {
      margin-left: auto;
      background: color-mix(in srgb, var(--color-primary-dim) 74%, transparent);
      border-color: color-mix(in srgb, var(--color-primary) 22%, transparent);
    }
    .ai-message.assistant {
      margin-right: auto;
    }
    .ai-message-meta {
      display: flex;
      flex-wrap: wrap;
      gap: var(--space-2);
      align-items: center;
      color: var(--color-text-faint);
      font-size: var(--text-xs);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    .ai-message-body {
      color: var(--color-text);
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      line-height: 1.65;
    }
    .ai-composer {
      display: grid;
      gap: var(--space-3);
    }
    .ai-toolbar {
      display: flex;
      flex-wrap: wrap;
      gap: var(--space-2);
      align-items: center;
      justify-content: space-between;
    }
    .ai-empty {
      color: var(--color-text-muted);
      padding: var(--space-5);
      border-radius: var(--radius-md);
      border: 1px dashed color-mix(in srgb, var(--color-border) 88%, transparent);
      background: color-mix(in srgb, var(--color-surface-offset) 68%, transparent);
    }
    .ai-backdrop {
      position: fixed;
      inset: 0;
      display: none;
      align-items: center;
      justify-content: center;
      padding: clamp(16px, 2vw, 28px);
      background: rgba(4, 7, 12, 0.7);
      backdrop-filter: blur(16px);
      z-index: 165;
    }
    .ai-backdrop.is-open {
      display: flex;
    }
    .ai-modal-shell {
      width: min(1480px, calc(100vw - 32px));
      height: min(92vh, 1100px);
      max-height: calc(100vh - 32px);
    }
    .ai-modal-card {
      display: flex;
      flex-direction: column;
      height: 100%;
      overflow: hidden;
      border-radius: calc(var(--radius-xl) + 6px);
      border: 1px solid color-mix(in srgb, var(--color-primary) 18%, var(--color-border));
      box-shadow: 0 32px 90px rgba(0, 0, 0, 0.4);
    }
    .ai-modal-topbar {
      display: flex;
      justify-content: space-between;
      gap: var(--space-4);
      align-items: start;
      padding: var(--space-5) var(--space-5) 0;
    }
    .ai-modal-body {
      flex: 1 1 auto;
      min-height: 0;
      overflow: auto;
      padding: 0 var(--space-5) var(--space-5);
    }
    .results-launchpad {
      display: grid;
      gap: var(--space-4);
      padding: var(--space-5);
      border-radius: calc(var(--radius-xl) + 2px);
      border: 1px solid color-mix(in srgb, var(--color-primary) 18%, var(--color-border));
      background:
        radial-gradient(circle at top right, color-mix(in srgb, var(--color-primary) 16%, transparent), transparent 36%),
        linear-gradient(160deg, color-mix(in srgb, var(--color-surface) 94%, transparent), color-mix(in srgb, var(--color-surface-2) 96%, transparent));
    }
    .results-launchpad .hero-cta {
      margin-top: 0;
    }
    .results-launch-meta {
      margin-bottom: 0;
    }
    .results-backdrop {
      position: fixed;
      inset: 0;
      display: none;
      align-items: center;
      justify-content: center;
      padding: clamp(16px, 2vw, 28px);
      background: rgba(4, 7, 12, 0.7);
      backdrop-filter: blur(16px);
      z-index: 160;
    }
    .results-backdrop.is-open {
      display: flex;
    }
    .results-modal-shell {
      width: min(1500px, calc(100vw - 32px));
      height: min(92vh, 1100px);
      max-height: calc(100vh - 32px);
    }
    .results-modal-card {
      display: flex;
      flex-direction: column;
      height: 100%;
      overflow: hidden;
      border-radius: calc(var(--radius-xl) + 6px);
      border: 1px solid color-mix(in srgb, var(--color-primary) 18%, var(--color-border));
      box-shadow: 0 32px 90px rgba(0, 0, 0, 0.4);
    }
    .results-modal-topbar {
      display: flex;
      justify-content: space-between;
      gap: var(--space-4);
      align-items: start;
      padding: var(--space-5) var(--space-5) 0;
    }
    .results-modal-body {
      flex: 1 1 auto;
      min-height: 0;
      overflow: auto;
      padding: 0 var(--space-5) var(--space-5);
    }
    .tab-strip {
      display: flex;
      gap: var(--space-2);
      flex-wrap: wrap;
      padding: var(--space-2);
      border-radius: calc(var(--radius-lg) + 6px);
      background: color-mix(in srgb, var(--color-surface-offset) 90%, transparent);
      border: 1px solid var(--color-border);
    }
    .tab-button {
      appearance: none;
      border: 0;
      border-radius: var(--radius-md);
      padding: 0.72rem 1rem;
      background: transparent;
      color: var(--color-text-muted);
      font-weight: 600;
      font-size: var(--text-sm);
      cursor: pointer;
      transition: background var(--transition), color var(--transition), transform var(--transition);
    }
    .tab-button:hover {
      color: var(--color-text);
      background: color-mix(in srgb, var(--color-surface) 80%, transparent);
    }
    .tab-button.is-active {
      background: var(--color-primary);
      color: var(--color-text-inverse);
      box-shadow: 0 18px 30px color-mix(in srgb, var(--color-primary) 24%, transparent);
    }
    .tab-panel {
      display: none;
      margin-top: var(--space-5);
    }
    .tab-panel.is-active {
      display: block;
    }
    .lead-grid {
      display: grid;
      gap: var(--space-3);
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .lead-grid.is-single-column {
      grid-template-columns: 1fr;
    }
    .lead-card {
      width: 100%;
      padding: var(--space-5);
      border-radius: var(--radius-lg);
      border: 1px solid var(--color-border);
      background:
        linear-gradient(180deg, color-mix(in srgb, var(--color-surface-2) 92%, transparent), color-mix(in srgb, var(--color-surface) 96%, transparent));
      color: var(--color-text);
      cursor: pointer;
      transition: transform var(--transition), border-color var(--transition), box-shadow var(--transition);
    }
    .lead-card:hover {
      transform: translateY(-2px);
      border-color: color-mix(in srgb, var(--color-primary) 30%, var(--color-border));
      box-shadow: 0 18px 36px rgba(0, 0, 0, 0.22);
    }
    .lead-card-open {
      width: 100%;
      text-align: left;
      appearance: none;
      background: transparent;
      border: 0;
      color: inherit;
      padding: 0;
      cursor: pointer;
    }
    .lead-card-header {
      display: flex;
      justify-content: space-between;
      gap: var(--space-3);
      align-items: start;
      margin-bottom: var(--space-3);
    }
    .lead-card-header-main {
      display: flex;
      gap: var(--space-3);
      align-items: center;
      min-width: 0;
    }
    .lead-logo {
      width: 52px;
      height: 52px;
      border-radius: 16px;
      overflow: hidden;
      flex: 0 0 52px;
      display: grid;
      place-items: center;
      background:
        radial-gradient(circle at top right, color-mix(in srgb, var(--color-primary) 16%, transparent), transparent 52%),
        color-mix(in srgb, var(--color-surface-offset) 92%, transparent);
      border: 1px solid color-mix(in srgb, var(--color-primary) 14%, var(--color-border));
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
    }
    .lead-logo.has-image .lead-logo-fallback {
      display: none;
    }
    .lead-logo.is-fallback .lead-logo-fallback,
    .lead-logo:not(.has-image) .lead-logo-fallback {
      display: grid;
    }
    .lead-logo.is-fallback .lead-logo-image {
      display: none;
    }
    .lead-logo-image {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
      background: color-mix(in srgb, var(--color-surface) 96%, transparent);
    }
    .lead-logo-fallback {
      width: 100%;
      height: 100%;
      display: none;
      place-items: center;
      color: var(--color-text);
      font-weight: 800;
      letter-spacing: 0.04em;
      font-size: 0.9rem;
      text-transform: uppercase;
    }
    .lead-card-title-wrap {
      min-width: 0;
    }
    .lead-card h3 {
      margin-bottom: 0;
      font-size: clamp(1.02rem, 0.98rem + 0.18vw, 1.12rem);
    }
    .lead-card-kicker {
      font-size: var(--text-xs);
      color: var(--color-text-faint);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    .lead-card-body {
      display: grid;
      gap: var(--space-3);
    }
    .lead-card-line {
      display: flex;
      flex-wrap: wrap;
      gap: var(--space-2);
      align-items: center;
      color: var(--color-text-muted);
      font-size: var(--text-sm);
    }
    .lead-card-snippet {
      color: var(--color-text-muted);
      font-size: var(--text-sm);
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    .response-stack {
      display: grid;
      gap: var(--space-3);
    }
    .response-kv {
      display: grid;
      gap: var(--space-2);
    }
    .response-kv-row {
      display: grid;
      grid-template-columns: minmax(88px, 120px) 1fr;
      gap: var(--space-3);
      align-items: start;
      padding-bottom: var(--space-2);
      border-bottom: 1px solid color-mix(in srgb, var(--color-divider) 72%, transparent);
    }
    .response-kv-row:last-child {
      padding-bottom: 0;
      border-bottom: 0;
    }
    .response-kv-key {
      color: var(--color-text-faint);
      font-size: var(--text-xs);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }
    .response-kv-value {
      color: var(--color-text);
      font-size: var(--text-sm);
      overflow-wrap: anywhere;
    }
    .response-card-meta {
      display: flex;
      flex-wrap: wrap;
      gap: var(--space-2);
      margin-top: var(--space-2);
    }
    .response-card-snippet {
      color: var(--color-text-muted);
      font-size: var(--text-sm);
      line-height: 1.55;
      margin: 0;
      white-space: pre-wrap;
    }
    .response-card-actions {
      display: flex;
      flex-wrap: wrap;
      gap: var(--space-2);
      margin-top: var(--space-3);
      padding-top: var(--space-3);
      border-top: 1px solid color-mix(in srgb, var(--color-divider) 72%, transparent);
    }
    .response-card-action {
      appearance: none;
      border: 1px solid var(--color-border);
      background: color-mix(in srgb, var(--color-surface-offset) 88%, transparent);
      color: var(--color-text);
      border-radius: 999px;
      padding: 0.48rem 0.82rem;
      font-size: var(--text-xs);
      font-weight: 700;
      cursor: pointer;
      transition: border-color var(--transition), background var(--transition), color var(--transition);
    }
    .response-card-action:hover {
      border-color: color-mix(in srgb, var(--color-primary) 28%, var(--color-border));
      background: color-mix(in srgb, var(--color-primary-dim) 72%, transparent);
    }
    a.response-card-action {
      text-decoration: none;
      display: inline-flex;
      align-items: center;
    }
    .response-card-action.is-primary {
      border-color: transparent;
      background: var(--color-primary);
      color: var(--color-on-primary, #07110f);
    }
    .response-card-action.is-primary:hover {
      background: color-mix(in srgb, var(--color-primary) 86%, #000);
    }
    .response-card-action:disabled {
      opacity: 0.55;
      cursor: default;
    }
    .lead-card-links {
      border-top: none;
      padding-top: 0;
      margin-top: var(--space-3);
    }
    .response-card-list {
      display: grid;
      gap: var(--space-2);
      margin: 0;
      padding-left: 1rem;
      color: var(--color-text-muted);
      font-size: var(--text-sm);
    }
    .response-empty-note {
      color: var(--color-text-muted);
      font-size: var(--text-sm);
    }
    .pill-row {
      display: flex;
      flex-wrap: wrap;
      gap: var(--space-2);
    }
    .pill.soft {
      background: color-mix(in srgb, var(--color-surface-offset) 86%, transparent);
      border: 1px solid var(--color-border);
      color: var(--color-text-muted);
    }
    .lead-empty,
    .map-empty,
    .scrape-empty {
      border: 1px dashed var(--color-border);
      border-radius: var(--radius-lg);
      padding: var(--space-8);
      text-align: center;
      color: var(--color-text-muted);
      background: color-mix(in srgb, var(--color-surface-2) 75%, transparent);
    }
    .map-shell {
      display: grid;
      gap: var(--space-4);
    }
    .map-note {
      display: flex;
      justify-content: space-between;
      gap: var(--space-4);
      align-items: center;
      padding: var(--space-4);
      border-radius: var(--radius-lg);
      background: color-mix(in srgb, var(--color-surface-offset) 92%, transparent);
      border: 1px solid var(--color-border);
      color: var(--color-text-muted);
    }
    .map-frame {
      min-height: clamp(520px, 66vh, 860px);
      border-radius: calc(var(--radius-xl) + 2px);
      border: 1px solid var(--color-border);
      overflow: hidden;
      background:
        radial-gradient(circle at 20% 20%, color-mix(in srgb, var(--color-primary) 10%, transparent), transparent 35%),
        color-mix(in srgb, var(--color-surface-2) 92%, transparent);
    }
    .map-frame [aria-label="Map"],
    .map-frame [role="region"] {
      border-radius: inherit;
    }
    .gm-style,
    .gm-style iframe {
      border-radius: inherit;
    }
    .json-shell {
      border-radius: var(--radius-lg);
      border: 1px solid var(--color-border);
      overflow: hidden;
      background: #07080a;
    }
    .json-shell pre {
      max-height: 520px;
      overflow: auto;
      padding: var(--space-5);
      background: #07080a;
      color: #d9fff4;
      font-size: 0.86rem;
      line-height: 1.55;
    }
    .json-shell code,
    .scrape-raw code {
      color: #d9fff4;
      background: transparent;
    }
    .detail-backdrop {
      position: fixed;
      inset: 0;
      background: rgba(4, 6, 10, 0.72);
      backdrop-filter: blur(10px);
      display: none;
      align-items: center;
      justify-content: center;
      padding: var(--space-6);
      z-index: 220;
    }
    .detail-backdrop.is-open {
      display: flex;
    }
    .detail-modal {
      width: min(980px, 100%);
      max-height: min(88vh, 980px);
      overflow: auto;
      border-radius: calc(var(--radius-xl) + 4px);
      border: 1px solid color-mix(in srgb, var(--color-primary) 18%, var(--color-border));
      background:
        linear-gradient(180deg, color-mix(in srgb, var(--color-surface) 96%, transparent), color-mix(in srgb, var(--color-surface-2) 94%, transparent));
      box-shadow: 0 30px 90px rgba(0, 0, 0, 0.42);
    }
    .detail-header {
      display: flex;
      justify-content: space-between;
      gap: var(--space-4);
      align-items: start;
      padding: var(--space-6);
      border-bottom: 1px solid var(--color-divider);
    }
    .detail-title {
      max-width: 70ch;
    }
    .detail-title h3 {
      margin-bottom: var(--space-2);
      font-size: clamp(1.3rem, 1.2rem + 0.35vw, 1.7rem);
    }
    .detail-close {
      appearance: none;
      border: 1px solid var(--color-border);
      background: var(--color-surface-offset);
      color: var(--color-text);
      border-radius: 999px;
      width: 42px;
      height: 42px;
      cursor: pointer;
      font-size: 1.25rem;
      line-height: 1;
    }
    .detail-body {
      padding: var(--space-6);
      display: grid;
      gap: var(--space-6);
    }
    .detail-actions {
      display: flex;
      flex-wrap: wrap;
      gap: var(--space-3);
    }
    .detail-grid {
      display: grid;
      gap: var(--space-3);
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .detail-item {
      padding: var(--space-4);
      border-radius: var(--radius-lg);
      border: 1px solid var(--color-border);
      background: color-mix(in srgb, var(--color-surface-offset) 88%, transparent);
    }
    .detail-key {
      font-size: var(--text-xs);
      color: var(--color-text-faint);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: var(--space-2);
    }
    .detail-value {
      color: var(--color-text);
      word-break: break-word;
      font-size: var(--text-sm);
    }
    .scrape-shell {
      display: grid;
      gap: var(--space-4);
      padding: var(--space-5);
      border-radius: var(--radius-xl);
      border: 1px solid var(--color-border);
      background:
        linear-gradient(145deg, color-mix(in srgb, var(--color-primary-dim) 68%, transparent), color-mix(in srgb, var(--color-surface-offset) 96%, transparent));
    }
    .scrape-header {
      display: flex;
      justify-content: space-between;
      gap: var(--space-3);
      align-items: center;
    }
    .scrape-grid {
      display: grid;
      gap: var(--space-3);
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }
    .scrape-card {
      padding: var(--space-4);
      border-radius: var(--radius-lg);
      border: 1px solid color-mix(in srgb, var(--color-primary) 18%, var(--color-border));
      background: color-mix(in srgb, var(--color-surface) 94%, transparent);
    }
    .scrape-card h4 {
      margin-bottom: var(--space-2);
      font-family: var(--font-display);
      font-size: var(--text-base);
      line-height: 1.2;
    }
    .scrape-raw details {
      border-radius: var(--radius-lg);
      border: 1px solid var(--color-border);
      background: color-mix(in srgb, var(--color-surface) 96%, transparent);
      overflow: hidden;
    }
    .scrape-raw summary {
      cursor: pointer;
      padding: var(--space-4);
      font-weight: 600;
      color: var(--color-text-muted);
    }
    .scrape-raw pre {
      max-height: 280px;
      overflow: auto;
      padding: 0 var(--space-4) var(--space-4);
      color: #d9fff4;
      font-size: 0.82rem;
    }
    .section-caption {
      display: flex;
      justify-content: space-between;
      gap: var(--space-4);
      align-items: center;
      margin-bottom: var(--space-4);
    }
    .section-caption .muted {
      margin: 0;
    }
    .status-good,
    .status-warn,
    .status-bad {
      display: inline-flex;
      align-items: center;
      gap: var(--space-2);
      font-weight: 700;
    }
    .status-good { color: var(--color-primary); }
    .status-warn { color: #ffce73; }
    .status-bad { color: #ff8f95; }
    .visually-hidden {
      position: absolute;
      width: 1px;
      height: 1px;
      padding: 0;
      margin: -1px;
      overflow: hidden;
      clip: rect(0, 0, 0, 0);
      white-space: nowrap;
      border: 0;
    }
    @media (max-width: 1080px) {
      .workspace-stack {
        grid-template-columns: 1fr;
      }
      .lead-grid,
      .detail-grid,
      .scrape-grid {
        grid-template-columns: 1fr;
      }
      .search-hero,
      .results-header,
      .results-modal-topbar,
      .map-note,
      .scrape-header,
      .detail-header {
        flex-direction: column;
        align-items: stretch;
      }
    }
    @media (max-width: 720px) {
      nav {
        position: static;
      }
      .nav-inner,
      .nav-actions,
      .hero-cta,
      .detail-actions {
        width: 100%;
      }
      .nav-inner,
      .nav-actions {
        align-items: stretch;
      }
      .nav-actions {
        display: grid;
        grid-template-columns: auto 1fr 1fr;
      }
      .nav-actions .btn {
        min-width: 0;
        padding-inline: 0.72rem;
      }
      .brand {
        max-width: 100%;
        line-height: 1.2;
      }
      .app-frame .section {
        padding-block: var(--space-4);
      }
      .workspace-stack,
      .context-stack,
      .results-stack,
      .search-form-shell {
        gap: var(--space-3);
      }
      .card,
      .results-launchpad,
      .lead-card,
      .feature-card {
        padding: var(--space-4);
        border-radius: var(--radius-lg);
      }
      .spotlight-panel::after {
        display: none;
      }
      .search-hero {
        gap: var(--space-4);
      }
      .search-hero-copy h2,
      .results-header-copy h2 {
        font-size: 1.45rem;
        line-height: 1.12;
      }
      .search-status {
        min-width: 0;
      }
      .field-grid {
        grid-template-columns: 1fr;
      }
      .field[data-span] {
        grid-column: auto;
      }
      .hero-cta {
        display: grid;
        grid-template-columns: 1fr;
      }
      .hero-cta .btn,
      .detail-actions .btn {
        width: 100%;
        justify-content: center;
      }
      .results-backdrop,
      .ai-backdrop,
      .detail-backdrop {
        align-items: stretch;
        padding: 0;
      }
      .results-modal-shell,
      .ai-modal-shell {
        width: 100vw;
        height: 100dvh;
        max-height: 100dvh;
      }
      .results-modal-card,
      .ai-modal-card,
      .detail-modal {
        width: 100%;
        max-height: 100dvh;
        border-radius: 0;
        border-inline: 0;
      }
      .results-modal-topbar,
      .ai-modal-topbar {
        padding: var(--space-4) var(--space-4) 0;
      }
      .results-modal-body,
      .ai-modal-body {
        padding: 0 var(--space-4) var(--space-4);
      }
      .results-toolbar {
        width: 100%;
        display: grid;
        grid-template-columns: 1fr;
      }
      .context-item {
        grid-template-columns: 1fr;
        gap: var(--space-1);
      }
      .results-summary {
        grid-template-columns: 1fr;
      }
      .lead-grid {
        grid-template-columns: 1fr;
      }
      .lead-card-header {
        flex-direction: column;
        align-items: stretch;
      }
      .lead-card-header .pill {
        align-self: flex-start;
      }
      .map-frame {
        min-height: min(58dvh, 460px);
      }
      .detail-backdrop {
        padding: 0;
      }
      .detail-body,
      .detail-header {
        padding: var(--space-4);
      }
      .detail-header {
        position: sticky;
        top: 0;
        z-index: 2;
        background: var(--color-surface);
      }
      .detail-close {
        position: absolute;
        top: var(--space-3);
        right: var(--space-3);
      }
      .detail-title {
        padding-right: 54px;
      }
      .json-shell pre,
      .scrape-raw pre {
        max-height: 48dvh;
        font-size: 0.78rem;
      }
      .tab-strip {
        padding: var(--space-1);
      }
      .tab-button {
        width: 100%;
        justify-content: center;
      }
    }
    @media (max-width: 420px) {
      .container {
        padding-inline: var(--space-3);
      }
      .nav-actions {
        grid-template-columns: 1fr;
      }
      .search-chip,
      .pill,
      .pill.soft {
        max-width: 100%;
        overflow-wrap: anywhere;
      }
      .context-value,
      .detail-value,
      .lead-card-line {
        overflow-wrap: anywhere;
      }
    }
  </style>

  <nav>
    <div class="container">
      <div class="nav-inner">
        <a href="__SEARCH_PAGE__" class="brand"><span class="dot"></span>LeadsMCP Search Workspace</a>
        <div class="nav-actions">
          <button class="theme-toggle" data-theme-toggle aria-label="Switch theme"></button>
          <a class="btn btn-ghost" href="__SUPPORT_PAGE__" target="_blank" rel="noopener noreferrer">Support</a>
          <a class="btn btn-ghost" href="__CONTACT_PAGE__" target="_blank" rel="noopener noreferrer">Contact</a>
          <a class="btn btn-primary" href="__GITHUB_URL__" target="_blank" rel="noopener noreferrer">GitHub</a>
        </div>
      </div>
    </div>
  </nav>

  <main class="app-frame">
    <section class="section" style="padding-top: 0;">
      <div class="container">
        <div class="workspace-stack">
          <div class="context-stack">
            <article class="card spotlight-panel">
              <p class="eyebrow">Marketplace Context</p>
              <h2>Connected GHL Session</h2>
              <p class="muted">This custom page stays inside your HighLevel app frame, requests encrypted user context from the parent window, and decrypts it server-side before every search.</p>
              <div class="context-grid">
                <div class="context-item"><div class="context-label">Status</div><div class="context-value" data-context-status>Waiting for HighLevel context...</div></div>
                <div class="context-item"><div class="context-label">User</div><div class="context-value" data-context-user>Not loaded</div></div>
                <div class="context-item"><div class="context-label">Email</div><div class="context-value" data-context-email>Not loaded</div></div>
                <div class="context-item"><div class="context-label">Company</div><div class="context-value" data-context-company>Not loaded</div></div>
                <div class="context-item"><div class="context-label">Location</div><div class="context-value" data-context-location>Not loaded</div></div>
                <div class="context-item"><div class="context-label">Role</div><div class="context-value" data-context-role>Not loaded</div></div>
              </div>
              <div class="hero-cta" style="margin-top: var(--space-6);">
                <button class="btn btn-primary" type="button" data-refresh-context>Reload Context</button>
                <a class="btn btn-ghost" href="__INSTALL_SUCCESS_PAGE__" target="_blank" rel="noopener noreferrer">Install Status</a>
              </div>
            </article>

            <article class="card">
              <div class="section-caption">
                <div>
                  <p class="eyebrow">Search Operator</p>
                  <h3 style="margin-bottom: var(--space-2);">What this page can do</h3>
                </div>
              </div>
              <div class="list">
                <div class="list-item"><span class="badge">1</span><div><strong>Search</strong><p class="muted">Run Google Maps, domain scraping, or research searches with the exact required params.</p></div></div>
                <div class="list-item"><span class="badge">2</span><div><strong>Inspect</strong><p class="muted">Review results as lead cards or on a live marker map before touching the CRM.</p></div></div>
                <div class="list-item"><span class="badge">3</span><div><strong>Scrape</strong><p class="muted">Open any business and trigger a focused website scrape from the modal if a website is available.</p></div></div>
              </div>
            </article>
          </div>

          <div class="results-stack">
            <article class="card">
              <div class="search-form-shell">
                <div class="search-hero">
                  <div class="search-hero-copy">
                    <p class="eyebrow">Lead Search</p>
                    <h2>Run a targeted search from inside HighLevel</h2>
                    <p class="muted">Choose the search mode, fill the required parameters, and LeadsMCP will format the response into a reviewable lead workspace instead of a raw tool dump.</p>
                    <div class="search-chips" data-required-fields></div>
                  </div>
                  <div class="search-status">
                    <div class="metric-label">Selected Search</div>
                    <div class="metric-value" data-search-label>Loading…</div>
                    <p class="muted" data-search-description style="margin-top: var(--space-2); margin-bottom: 0;"></p>
                  </div>
                </div>

                <form data-search-form>
                  <div class="field-grid">
                    <label class="field" data-span="12">
                      <span>Search Type</span>
                      <select class="select" name="searchType" data-search-type></select>
                      <small class="field-hint">The form below updates automatically based on the selected search mode.</small>
                    </label>
                  </div>

                  <div class="field-grid" data-dynamic-fields style="margin-top: var(--space-5);"></div>

                  <div class="hero-cta" style="margin-top: var(--space-6);">
                    <button class="btn btn-primary" type="submit" data-run-search disabled>Load GHL context first</button>
                    <button class="btn btn-ghost" type="button" data-save-search>Save Search</button>
                    <button class="btn btn-ghost" type="button" data-reset-form>Reset Form</button>
                    <button class="btn btn-ghost" type="button" data-open-results disabled>Open Review Workspace</button>
                  </div>
                </form>

                <div class="search-memory">
                  <div class="search-memory-head">
                    <div>
                      <div class="metric-label">Saved and recent searches</div>
                      <p class="muted" style="margin: 0;">Reuse recent search configurations without retyping every field.</p>
                    </div>
                  </div>
                  <div class="saved-search-list" data-saved-searches></div>
                  <p class="muted" data-saved-searches-empty style="margin: 0;">No saved searches yet. Run or save a search to keep it here.</p>
                </div>
              </div>
            </article>

            <article class="results-launchpad">
              <div class="section-caption" style="margin-bottom: 0;">
                <div>
                  <p class="eyebrow">Review Workspace</p>
                  <h3 style="margin-bottom: var(--space-2);">Open results in a full-screen workspace</h3>
                  <p class="muted results-launch-meta" data-results-launch-meta>Run a search and we will open the lead cards, map view, and raw payload in a full-screen modal.</p>
                </div>
              </div>
              <div class="hero-cta">
                <button class="btn btn-primary" type="button" data-open-results-launch disabled>Open Review Workspace</button>
                <button class="btn btn-ghost" type="button" data-open-results-map disabled>Open Map Tab</button>
              </div>
            </article>

            <article class="ai-launchpad">
              <div class="section-caption" style="margin-bottom: 0;">
                <div>
                  <p class="eyebrow">AI Workspace</p>
                  <h3 style="margin-bottom: var(--space-2);">Open the copilot in a full-screen workspace</h3>
                  <p class="muted" style="margin-bottom: 0;">Use the MCP-connected copilot in a dedicated full-screen modal so you can research, compare leads, and work with GHL records without a cramped side panel.</p>
                </div>
              </div>
              <div class="hero-cta">
                <button class="btn btn-primary" type="button" data-open-ai-workspace>Open AI Workspace</button>
                <button class="btn btn-ghost" type="button" data-open-ai-workspace-focus>Open and focus chat</button>
              </div>
              <div class="pill-row">
                <span class="pill soft">GHL-enabled</span>
                <span class="pill soft">MCP-backed</span>
                <span class="pill soft">Workspace-aware</span>
              </div>
            </article>
          </div>
        </div>
      </div>
    </section>
  </main>

  <div class="ai-backdrop" data-ai-backdrop>
    <div class="ai-modal-shell">
      <article class="card ai-modal-card">
        <div class="ai-modal-topbar">
          <div class="results-header-copy">
            <p class="eyebrow">AI Workspace</p>
            <h2>MCP-connected copilot with GHL access</h2>
            <p class="muted" style="margin-bottom: 0;">This copilot can use the LeadsMCP research stack and your connected GHL subaccount. It can search, reason over the current workspace, and read or write CRM records from inside the custom page.</p>
          </div>
          <div class="results-toolbar">
            <div class="ai-status">
              <span class="pill soft" data-ai-status>Waiting for HighLevel context...</span>
              <span class="pill soft" data-ai-model>Model loading…</span>
            </div>
            <button class="btn btn-ghost" type="button" data-ai-close>Close</button>
          </div>
        </div>
        <div class="ai-modal-body">
          <div class="ai-shell">
            <div class="ai-thread" data-ai-thread>
              <div class="ai-empty" data-ai-empty>Load the GHL context, then ask the copilot to find leads, summarize the current results, compare prospects, or suggest follow-up research.</div>
            </div>
            <form class="ai-composer" data-ai-form>
              <label class="field" data-span="12" style="margin: 0;">
                <span>Ask the AI copilot</span>
                <textarea class="textarea" rows="5" data-ai-input placeholder="Example: Find 10 premium marriage retreat venues in Florida and tell me which ones look best for partnership outreach." disabled></textarea>
                <small class="field-hint">The copilot can use LeadsMCP tools, the active workspace context, and your connected GHL auth. It avoids Stripe billing/export tools, but it can read or write CRM data when you ask it to.</small>
              </label>
              <div class="ai-toolbar">
                <div class="hero-cta" style="margin-top: 0;">
                  <button class="btn btn-primary" type="submit" data-ai-send disabled>Load GHL context first</button>
                  <button class="btn btn-ghost" type="button" data-ai-clear>Clear Chat</button>
                </div>
                <div class="pill-row">
                  <span class="pill soft">GHL-enabled</span>
                  <span class="pill soft">MCP-backed</span>
                  <span class="pill soft">Workspace-aware</span>
                </div>
              </div>
            </form>
          </div>
        </div>
      </article>
    </div>
  </div>

  <div class="results-backdrop" data-results-backdrop>
    <div class="results-modal-shell">
      <article class="card results-modal-card">
        <div class="results-modal-topbar">
          <div class="results-header-copy">
            <p class="eyebrow">Review Workspace</p>
            <h2>Lead review, map view, and raw payload</h2>
            <div class="results-family" data-results-family>Lead response</div>
            <p class="muted" data-results-meta>Run a search to populate lead cards, map markers, and the raw response payload.</p>
            <div class="results-filter-strip" data-results-filters hidden></div>
          </div>
          <div class="results-toolbar">
            <div class="tab-strip" role="tablist" aria-label="Search results tabs">
              <button class="tab-button is-active" type="button" role="tab" aria-selected="true" data-tab-button="leads">Leads</button>
              <button class="tab-button" type="button" role="tab" aria-selected="false" data-tab-button="map">Map</button>
              <button class="tab-button" type="button" role="tab" aria-selected="false" data-tab-button="raw">Raw JSON</button>
            </div>
            <button class="btn btn-ghost" type="button" data-copy-visible disabled>Copy Visible</button>
            <button class="btn btn-ghost" type="button" data-export-json-visible disabled>Export JSON</button>
            <button class="btn btn-ghost" type="button" data-export-csv-visible disabled>Export CSV</button>
            <button class="btn btn-ghost" type="button" data-results-close>Close</button>
          </div>
        </div>

        <div class="results-modal-body">
          <div class="results-summary" data-results-summary hidden></div>

          <section class="tab-panel is-active" role="tabpanel" data-tab-panel="leads">
            <div class="lead-empty" data-results-empty>No search has been run yet.</div>
            <div class="lead-grid" data-lead-grid hidden></div>
          </section>

          <section class="tab-panel" role="tabpanel" data-tab-panel="map">
            <div class="map-shell">
              <div class="map-note">
                <div>
                  <strong>Marker map</strong>
                  <p class="muted" style="margin-bottom: 0;">Markers appear when a result includes latitude and longitude. Click a marker to open the business detail modal.</p>
                </div>
                <div class="pill-row" data-map-stats></div>
              </div>
              <div class="map-empty" data-map-empty>Run a Google Maps search to place leads on the map.</div>
              <div class="map-frame" data-map-frame hidden></div>
            </div>
          </section>

          <section class="tab-panel" role="tabpanel" data-tab-panel="raw">
            <div class="json-shell" data-results-json hidden><pre><code></code></pre></div>
            <div class="lead-empty" data-results-json-empty>Run a search to inspect the raw Outscraper payload here.</div>
          </section>
        </div>
      </article>
    </div>
  </div>

  <div class="detail-backdrop" data-detail-backdrop>
    <div class="detail-modal" role="dialog" aria-modal="true" aria-labelledby="lead-detail-title">
      <div class="detail-header">
        <div class="detail-title">
          <p class="eyebrow" style="margin-bottom: var(--space-3);">Lead Detail</p>
          <h3 id="lead-detail-title" data-detail-title>Select a lead</h3>
          <p class="muted" data-detail-subtitle style="margin-bottom: 0;">Choose a result card or map marker to inspect the business.</p>
        </div>
        <button class="detail-close" type="button" aria-label="Close lead detail modal" data-detail-close>×</button>
      </div>
      <div class="detail-body">
        <div class="pill-row" data-detail-pills></div>
        <div class="detail-actions">
          <a class="btn btn-ghost" href="#" target="_blank" rel="noopener noreferrer" data-open-website hidden>Open Website</a>
          <button class="btn btn-primary" type="button" data-scrape-website hidden>Scrape Website</button>
        </div>
        <div class="detail-grid" data-detail-grid></div>
        <section class="scrape-shell">
          <div class="scrape-header">
            <div>
              <div class="metric-label">Website scrape</div>
              <div class="metric-value" data-scrape-status>Choose a business with a website to run a focused scrape.</div>
            </div>
            <div class="pill-row" data-scrape-summary></div>
          </div>
          <div class="scrape-empty" data-scrape-empty>No website scrape has been run for this lead yet.</div>
          <div class="scrape-grid" data-scrape-grid hidden></div>
          <div class="scrape-raw" data-scrape-raw hidden>
            <details>
              <summary>Raw website scrape payload</summary>
              <pre><code data-scrape-raw-code></code></pre>
            </details>
          </div>
        </section>
      </div>
    </div>
  </div>

  <script id="marketplace-search-config" type="application/json">__SEARCH_CONFIG__</script>
  <script>
    const SEARCH_TYPES = JSON.parse(document.getElementById('marketplace-search-config').textContent || '{}');
    const CONTEXT_ENDPOINT = document.body.dataset.contextEndpoint;
    const SEARCH_ENDPOINT = document.body.dataset.searchEndpoint;
    const AI_ENDPOINT = document.body.dataset.aiEndpoint;
    const MAPBOX_PUBLIC_TOKEN = document.body.dataset.mapboxPublicToken || '';
    const MAPBOX_STYLE_URL = document.body.dataset.mapboxStyleUrl || 'mapbox://styles/mapbox/standard-satellite';
    const MAPBOX_JS_URL = document.body.dataset.mapboxJsUrl || '';
    const MAPBOX_CSS_URL = document.body.dataset.mapboxCssUrl || '';

    (function () {
      const SAVED_SEARCHES_KEY = 'leadsmcp-saved-searches-v1';
      const MAX_SAVED_SEARCHES = 8;

      const state = {
        encryptedData: '',
        context: null,
        currentSearchType: Object.keys(SEARCH_TYPES)[0] || '',
        activeTab: 'leads',
        activeResultFilter: 'all',
        searchPayload: null,
        visibleResults: [],
        selectedLeadId: '',
        mapProviderLoadingPromise: null,
        mapProviderAuthMessage: '',
        map: null,
        mapMarkers: [],
        mapInfoWindow: null,
        resultsOpen: false,
        aiMessages: [],
        aiBusy: false,
      };

      const form = document.querySelector('[data-search-form]');
      const searchTypeSelect = document.querySelector('[data-search-type]');
      const dynamicFields = document.querySelector('[data-dynamic-fields]');
      const runButton = document.querySelector('[data-run-search]');
      const saveSearchButton = document.querySelector('[data-save-search]');
      const resetButton = document.querySelector('[data-reset-form]');
      const openResultsButton = document.querySelector('[data-open-results]');
      const openResultsLaunchButton = document.querySelector('[data-open-results-launch]');
      const openResultsMapButton = document.querySelector('[data-open-results-map]');
      const refreshContextButton = document.querySelector('[data-refresh-context]');
      const searchLabel = document.querySelector('[data-search-label]');
      const searchDescription = document.querySelector('[data-search-description]');
      const requiredFields = document.querySelector('[data-required-fields]');
      const resultsBackdrop = document.querySelector('[data-results-backdrop]');
      const resultsCloseButton = document.querySelector('[data-results-close]');
      const resultsLaunchMeta = document.querySelector('[data-results-launch-meta]');
      const resultsMeta = document.querySelector('[data-results-meta]');
      const resultsFamily = document.querySelector('[data-results-family]');
      const resultsFilters = document.querySelector('[data-results-filters]');
      const resultsSummary = document.querySelector('[data-results-summary]');
      const resultsEmpty = document.querySelector('[data-results-empty]');
      const leadGrid = document.querySelector('[data-lead-grid]');
      const mapStats = document.querySelector('[data-map-stats]');
      const mapEmpty = document.querySelector('[data-map-empty]');
      const mapFrame = document.querySelector('[data-map-frame]');
      const resultsJson = document.querySelector('[data-results-json]');
      const resultsJsonEmpty = document.querySelector('[data-results-json-empty]');
      const resultsCode = resultsJson ? resultsJson.querySelector('code') : null;
      const copyVisibleButton = document.querySelector('[data-copy-visible]');
      const exportJsonVisibleButton = document.querySelector('[data-export-json-visible]');
      const exportCsvVisibleButton = document.querySelector('[data-export-csv-visible]');
      const savedSearchesList = document.querySelector('[data-saved-searches]');
      const savedSearchesEmpty = document.querySelector('[data-saved-searches-empty]');
      const aiBackdrop = document.querySelector('[data-ai-backdrop]');
      const openAiWorkspaceButton = document.querySelector('[data-open-ai-workspace]');
      const openAiWorkspaceFocusButton = document.querySelector('[data-open-ai-workspace-focus]');
      const aiThread = document.querySelector('[data-ai-thread]');
      const aiEmpty = document.querySelector('[data-ai-empty]');
      const aiForm = document.querySelector('[data-ai-form]');
      const aiInput = document.querySelector('[data-ai-input]');
      const aiSendButton = document.querySelector('[data-ai-send]');
      const aiClearButton = document.querySelector('[data-ai-clear]');
      const aiCloseButton = document.querySelector('[data-ai-close]');
      const aiStatus = document.querySelector('[data-ai-status]');
      const aiModel = document.querySelector('[data-ai-model]');
      const tabButtons = Array.from(document.querySelectorAll('[data-tab-button]'));
      const tabPanels = Array.from(document.querySelectorAll('[data-tab-panel]'));

      const detailBackdrop = document.querySelector('[data-detail-backdrop]');
      const detailClose = document.querySelector('[data-detail-close]');
      const detailTitle = document.querySelector('[data-detail-title]');
      const detailSubtitle = document.querySelector('[data-detail-subtitle]');
      const detailPills = document.querySelector('[data-detail-pills]');
      const detailGrid = document.querySelector('[data-detail-grid]');
      const openWebsiteLink = document.querySelector('[data-open-website]');
      const scrapeButton = document.querySelector('[data-scrape-website]');
      const scrapeStatus = document.querySelector('[data-scrape-status]');
      const scrapeSummary = document.querySelector('[data-scrape-summary]');
      const scrapeEmpty = document.querySelector('[data-scrape-empty]');
      const scrapeGrid = document.querySelector('[data-scrape-grid]');
      const scrapeRaw = document.querySelector('[data-scrape-raw]');
      const scrapeRawCode = document.querySelector('[data-scrape-raw-code]');

      const contextNodes = {
        status: document.querySelector('[data-context-status]'),
        user: document.querySelector('[data-context-user]'),
        email: document.querySelector('[data-context-email]'),
        company: document.querySelector('[data-context-company]'),
        location: document.querySelector('[data-context-location]'),
        role: document.querySelector('[data-context-role]'),
      };

      function setContextNode(key, value, className) {
        const node = contextNodes[key];
        if (!node) return;
        node.textContent = value;
        node.className = className || 'context-value';
      }

      function escapeHtml(value) {
        return String(value)
          .replace(/&/g, '&amp;')
          .replace(/</g, '&lt;')
          .replace(/>/g, '&gt;')
          .replace(/"/g, '&quot;')
          .replace(/'/g, '&#39;');
      }

      function humanizeKey(key) {
        return String(key || '')
          .replace(/_/g, ' ')
          .replace(/([a-z])([A-Z])/g, '$1 $2')
          .replace(/\\s+/g, ' ')
          .trim()
          .replace(/^./, (char) => char.toUpperCase());
      }

      function compactValue(value) {
        if (value === null || value === undefined || value === '') return '';
        if (Array.isArray(value)) {
          return value
            .map((item) => compactValue(item))
            .filter(Boolean)
            .join(', ');
        }
        if (typeof value === 'object') {
          return JSON.stringify(value);
        }
        return String(value);
      }

      function formatMetricValue(value) {
        if (value === null || value === undefined || value === '') return '—';
        if (typeof value === 'number') {
          return Number.isInteger(value) ? value.toString() : value.toFixed(2);
        }
        return String(value);
      }

      function formatRating(lead) {
        if (lead.rating === null || lead.rating === undefined) return '';
        const reviews = lead.reviewCount ? ` · ${lead.reviewCount} reviews` : '';
        return `${lead.rating}${reviews}`;
      }

      function leadInitials(lead) {
        const base = String((lead && (lead.name || lead.websiteDomain || lead.domain || 'Lead')) || 'Lead').trim();
        if (!base) return 'LD';
        const words = base.split(/\\s+/).filter(Boolean);
        if (words.length === 1) {
          return words[0].slice(0, 2).toUpperCase();
        }
        return `${words[0][0] || ''}${words[1][0] || ''}`.toUpperCase();
      }

      function renderLeadLogo(lead) {
        const initials = leadInitials(lead);
        if (lead.logoUrl) {
          return `
            <div class="lead-logo has-image" data-lead-logo>
              <img class="lead-logo-image" src="${escapeHtml(lead.logoUrl)}" alt="${escapeHtml((lead.name || 'Lead') + ' logo')}" loading="lazy" referrerpolicy="no-referrer">
              <span class="lead-logo-fallback" aria-hidden="true">${escapeHtml(initials)}</span>
            </div>
          `;
        }
        return `
          <div class="lead-logo is-fallback" data-lead-logo>
            <span class="lead-logo-fallback" aria-hidden="true">${escapeHtml(initials)}</span>
          </div>
        `;
      }

      function extractLocationLine(lead) {
        const locationBits = [lead.address, lead.city, lead.state, lead.country].filter(Boolean);
        return locationBits.join(', ');
      }

      function domainFromLead(lead) {
        if (!lead) return '';
        if (lead.websiteDomain) return lead.websiteDomain;
        const rawWebsite = lead.website || (lead.raw && (lead.raw.website || lead.raw.url || lead.raw.link || lead.raw.domain));
        if (!rawWebsite) return '';
        try {
          const parsed = new URL(rawWebsite.startsWith('http') ? rawWebsite : `https://${rawWebsite}`);
          return parsed.hostname.replace(/^www\\./, '');
        } catch (error) {
          return String(rawWebsite).replace(/^https?:\\/\\//, '').replace(/^www\\./, '').split('/')[0];
        }
      }

      function getLeadById(leadId) {
        if (!state.searchPayload || !Array.isArray(state.searchPayload.leads)) return null;
        return state.searchPayload.leads.find((lead) => lead.id === leadId) || null;
      }

      function renderSearchTypeOptions() {
        const options = Object.entries(SEARCH_TYPES).map(([key, config]) => {
          return `<option value="${escapeHtml(key)}">${escapeHtml(config.label)}</option>`;
        });
        searchTypeSelect.innerHTML = options.join('');
        if (state.currentSearchType) {
          searchTypeSelect.value = state.currentSearchType;
        }
      }

      function renderFields() {
        const config = SEARCH_TYPES[state.currentSearchType];
        if (!config) return;

        searchLabel.textContent = config.label;
        searchDescription.textContent = config.description;

        const required = config.fields.filter((field) => field.required).map((field) => field.label);
        requiredFields.innerHTML = required
          .map((label) => `<span class="search-chip">${escapeHtml(label)} required</span>`)
          .join('');

        dynamicFields.innerHTML = config.fields.map((field) => {
          const span = field.span || 6;
          const requiredAttr = field.required ? 'required' : '';
          const placeholderAttr = field.placeholder ? `placeholder="${escapeHtml(field.placeholder)}"` : '';
          const minAttr = field.min !== undefined ? `min="${field.min}"` : '';
          const maxAttr = field.max !== undefined ? `max="${field.max}"` : '';
          const value = field.default !== undefined ? String(field.default) : '';
          const valueAttr = value ? `value="${escapeHtml(value)}"` : '';

          let control = '';
          if (field.type === 'textarea') {
            const rows = field.rows || 4;
            control = `<textarea class="textarea" name="${escapeHtml(field.name)}" rows="${rows}" ${placeholderAttr} ${requiredAttr}>${escapeHtml(value)}</textarea>`;
          } else {
            control = `<input class="input" type="${field.type === 'number' ? 'number' : 'text'}" name="${escapeHtml(field.name)}" ${placeholderAttr} ${requiredAttr} ${minAttr} ${maxAttr} ${valueAttr}>`;
          }

          return `
            <label class="field" data-span="${span}">
              <span>${escapeHtml(field.label)}${field.required ? ' *' : ''}</span>
              ${control}
              <small class="field-hint">${escapeHtml(field.help || '')}</small>
            </label>
          `;
        }).join('');
      }

      function collectParams() {
        const config = SEARCH_TYPES[state.currentSearchType];
        const payload = {};

        for (const field of config.fields) {
          const input = form.elements.namedItem(field.name);
          if (!input) continue;
          let value = input.value;
          if (typeof value === 'string') {
            value = value.trim();
          }
          if (!value && field.default !== undefined) {
            value = field.default;
          }
          if (field.required && (value === undefined || value === null || value === '')) {
            throw new Error(`Missing required field: ${field.label}`);
          }
          if (value === undefined || value === null || value === '') {
            continue;
          }
          if (field.type === 'number') {
            const parsed = Number(value);
            if (!Number.isFinite(parsed)) {
              throw new Error(`Field ${field.label} must be numeric.`);
            }
            payload[field.name] = Math.trunc(parsed);
          } else {
            payload[field.name] = value;
          }
        }

        return payload;
      }

      function setFieldValues(params) {
        Object.entries(params || {}).forEach(([key, value]) => {
          const input = form.elements.namedItem(key);
          if (!input) return;
          input.value = value === null || value === undefined ? '' : String(value);
        });
      }

      function readSavedSearches() {
        try {
          const raw = window.localStorage.getItem(SAVED_SEARCHES_KEY);
          if (!raw) return [];
          const parsed = JSON.parse(raw);
          return Array.isArray(parsed) ? parsed : [];
        } catch (error) {
          return [];
        }
      }

      function writeSavedSearches(entries) {
        try {
          window.localStorage.setItem(SAVED_SEARCHES_KEY, JSON.stringify(entries));
        } catch (error) {
        }
      }

      function currentSearchSnapshot() {
        const config = SEARCH_TYPES[state.currentSearchType];
        if (!config) return null;
        const params = collectParams();
        const nonEmptyValues = Object.values(params).filter((value) => value !== null && value !== undefined && String(value).trim() !== '');
        if (!nonEmptyValues.length) return null;
        const primaryValue = config.fields
          .map((field) => params[field.name])
          .find((value) => value !== null && value !== undefined && String(value).trim() !== '');
        const label = primaryValue ? `${config.label} · ${String(primaryValue).slice(0, 48)}` : config.label;
        return {
          id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
          searchType: state.currentSearchType,
          label,
          params,
          createdAt: new Date().toISOString(),
        };
      }

      function renderSavedSearches() {
        if (!savedSearchesList || !savedSearchesEmpty) return;
        const entries = readSavedSearches();
        savedSearchesEmpty.hidden = entries.length > 0;
        savedSearchesList.innerHTML = entries.map((entry, index) => {
          const searchTypeLabel = SEARCH_TYPES[entry.searchType] ? SEARCH_TYPES[entry.searchType].label : humanizeKey(entry.searchType);
          const meta = `${searchTypeLabel} · ${new Date(entry.createdAt).toLocaleDateString()}`;
          return `
            <article class="saved-search-item">
              <button class="saved-search-main" type="button" data-saved-search-load="${index}">
                <span class="saved-search-title">${escapeHtml(entry.label || searchTypeLabel)}</span>
                <span class="saved-search-meta">${escapeHtml(meta)}</span>
              </button>
              <button class="saved-search-remove" type="button" data-saved-search-remove="${index}" aria-label="Remove saved search">Remove</button>
            </article>
          `;
        }).join('');
      }

      function saveCurrentSearch(manual) {
        let snapshot;
        try {
          snapshot = currentSearchSnapshot();
        } catch (error) {
          if (manual) {
            resultsMeta.textContent = error.message || 'Complete the required search fields before saving.';
          }
          return;
        }

        if (!snapshot) {
          if (manual) {
            resultsMeta.textContent = 'Add a search query before saving this search.';
          }
          return;
        }

        const existing = readSavedSearches().filter((entry) => {
          return !(entry.searchType === snapshot.searchType && JSON.stringify(entry.params) === JSON.stringify(snapshot.params));
        });
        const nextEntries = [snapshot, ...existing].slice(0, MAX_SAVED_SEARCHES);
        writeSavedSearches(nextEntries);
        renderSavedSearches();
        if (manual) {
          resultsMeta.textContent = `Saved ${SEARCH_TYPES[snapshot.searchType].label} to recent searches.`;
        }
      }

      function loadSavedSearch(index) {
        const entry = readSavedSearches()[index];
        if (!entry) return;
        state.currentSearchType = entry.searchType;
        renderSearchTypeOptions();
        renderFields();
        setFieldValues(entry.params);
        closeResultsWorkspace();
        resultsMeta.textContent = `Loaded saved search: ${entry.label || SEARCH_TYPES[entry.searchType].label}.`;
      }

      function removeSavedSearch(index) {
        const entries = readSavedSearches();
        if (!entries[index]) return;
        const removed = entries[index];
        entries.splice(index, 1);
        writeSavedSearches(entries);
        renderSavedSearches();
        resultsMeta.textContent = `Removed saved search: ${removed.label || SEARCH_TYPES[removed.searchType].label}.`;
      }

      function setSearchIdleState() {
        resultsSummary.hidden = true;
        resultsEmpty.hidden = false;
        leadGrid.hidden = true;
        leadGrid.classList.remove('is-single-column');
        mapFrame.hidden = true;
        mapEmpty.hidden = false;
        mapStats.innerHTML = '';
        clearMapMarkers();
        resultsJson.hidden = true;
        resultsJsonEmpty.hidden = false;
        state.visibleResults = [];
        state.activeResultFilter = 'all';
        resultsEmpty.textContent = 'No search has been run yet.';
        resultsJsonEmpty.textContent = 'Run a search to inspect the raw Outscraper payload here.';
        resultsMeta.textContent = 'Run a search to populate lead cards, map markers, and the raw response payload.';
        if (resultsFamily) {
          resultsFamily.textContent = 'Lead response';
        }
        if (resultsFilters) {
          resultsFilters.hidden = true;
          resultsFilters.innerHTML = '';
        }
        if (resultsLaunchMeta) {
          resultsLaunchMeta.textContent = 'Run a search and we will open the lead cards, map view, and raw payload in a full-screen modal.';
        }
        [openResultsButton, openResultsLaunchButton, openResultsMapButton].forEach((button) => {
          if (button) button.disabled = true;
        });
        if (copyVisibleButton) copyVisibleButton.disabled = true;
        if (exportJsonVisibleButton) exportJsonVisibleButton.disabled = true;
        if (exportCsvVisibleButton) exportCsvVisibleButton.disabled = true;
      }

      function setAiStatus(message, modelLabel) {
        if (aiStatus) aiStatus.textContent = message;
        if (aiModel && modelLabel) aiModel.textContent = modelLabel;
      }

      function setAiComposerEnabled(enabled) {
        if (aiInput) aiInput.disabled = !enabled;
        if (aiSendButton) {
          aiSendButton.disabled = !enabled || state.aiBusy;
          aiSendButton.textContent = enabled ? (state.aiBusy ? 'Thinking…' : 'Send to Copilot') : 'Load GHL context first';
        }
      }

      function renderAiThread() {
        if (!aiThread) return;
        if (!state.aiMessages.length) {
          if (aiEmpty) aiEmpty.hidden = false;
          aiThread.innerHTML = aiEmpty ? aiEmpty.outerHTML : '';
          return;
        }

        if (aiEmpty) aiEmpty.hidden = true;
        aiThread.innerHTML = state.aiMessages.map((message) => {
          const roleLabel = message.role === 'user' ? 'You' : 'AI Copilot';
          const toolBadges = Array.isArray(message.toolCalls) && message.toolCalls.length
            ? `<div class="pill-row">${message.toolCalls.map((toolName) => `<span class="pill soft">${escapeHtml(toolName)}</span>`).join('')}</div>`
            : '';
          return `
            <article class="ai-message ${escapeHtml(message.role)}">
              <div class="ai-message-meta">
                <span>${escapeHtml(roleLabel)}</span>
                ${message.model ? `<span>${escapeHtml(message.model)}</span>` : ''}
              </div>
              <div class="ai-message-body">${escapeHtml(message.content)}</div>
              ${toolBadges}
            </article>
          `;
        }).join('');
        aiThread.scrollTop = aiThread.scrollHeight;
      }

      function clearAiConversation() {
        state.aiMessages = [];
        renderAiThread();
        setAiStatus(state.encryptedData ? 'Ready for a new research thread.' : 'Waiting for HighLevel context...', aiModel ? aiModel.textContent : '');
      }

      function openAiWorkspace(focusComposer) {
        if (!aiBackdrop) return;
        aiBackdrop.classList.add('is-open');
        syncBodyScrollLock();
        if (focusComposer && aiInput && !aiInput.disabled) {
          window.setTimeout(() => {
            aiInput.focus();
          }, 40);
        }
      }

      function closeAiWorkspace() {
        if (!aiBackdrop) return;
        aiBackdrop.classList.remove('is-open');
        syncBodyScrollLock();
      }

      function currentSearchContextPayload() {
        if (!state.searchPayload) return null;
        return {
          searchType: state.searchPayload.searchType,
          searchLabel: state.searchPayload.searchLabel,
          leadCount: state.searchPayload.leadCount,
          leadPreview: Array.isArray(state.searchPayload.leads) ? state.searchPayload.leads.slice(0, 5) : [],
        };
      }

      async function submitAiPrompt(event) {
        event.preventDefault();
        if (!aiInput) return;
        const prompt = aiInput.value.trim();
        if (!prompt) return;
        aiInput.value = '';
        await runAiPrompt(prompt);
      }

      async function runAiPrompt(rawPrompt) {
        if (!state.encryptedData) return;
        const prompt = String(rawPrompt || '').trim();
        if (!prompt || state.aiBusy) return;

        state.aiMessages.push({ role: 'user', content: prompt });
        state.aiBusy = true;
        setAiComposerEnabled(true);
        setAiStatus('Running the copilot against the LeadsMCP research tools…', aiModel ? aiModel.textContent : '');
        renderAiThread();

        try {
          const response = await fetch(AI_ENDPOINT, {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({
              encryptedData: state.encryptedData,
              messages: state.aiMessages.map((message) => ({ role: message.role, content: message.content })),
              currentSearch: currentSearchContextPayload(),
            })
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) {
            throw new Error(payload.message || 'The AI workspace request failed.');
          }
          state.aiMessages.push({
            role: 'assistant',
            content: payload.reply || 'No reply returned.',
            toolCalls: payload.toolCalls || [],
            model: payload.model || '',
          });
          setAiStatus('Copilot connected and ready.', payload.model || 'LLM ready');
        } catch (error) {
          state.aiMessages.push({
            role: 'assistant',
            content: error.message || 'The AI workspace request failed.',
            toolCalls: [],
            model: '',
          });
          setAiStatus('The copilot hit an error. Check the response below and try again.', aiModel ? aiModel.textContent : '');
        } finally {
          state.aiBusy = false;
          setAiComposerEnabled(Boolean(state.encryptedData));
          renderAiThread();
        }
      }

      function leadWebsiteHref(lead) {
        const raw = lead && (lead.website || (lead.websiteDomain ? `https://${lead.websiteDomain}` : ''));
        if (!raw) return '';
        return String(raw).startsWith('http') ? String(raw) : `https://${raw}`;
      }

      function renderLeadLinkButtons(lead) {
        const buttons = [];
        const site = leadWebsiteHref(lead);
        if (site) {
          buttons.push(`<a class="response-card-action" href="${escapeHtml(site)}" target="_blank" rel="noopener noreferrer">Website</a>`);
        }
        if (lead.email) {
          buttons.push(`<a class="response-card-action" href="mailto:${escapeHtml(lead.email)}">Email</a>`);
        }
        if (lead.phone) {
          const dial = String(lead.phone).replace(/[^0-9+]/g, '');
          if (dial) buttons.push(`<a class="response-card-action" href="tel:${escapeHtml(dial)}">Call</a>`);
        }
        if (lead.sourceUrl) {
          buttons.push(`<a class="response-card-action" href="${escapeHtml(lead.sourceUrl)}" target="_blank" rel="noopener noreferrer">Profile</a>`);
        }
        if (!buttons.length) return '';
        return `<div class="response-card-actions lead-card-links">${buttons.join('')}</div>`;
      }

      function buildLeadPushPrompt(lead) {
        const fields = {
          name: lead.name || '',
          companyName: lead.name || '',
          email: lead.email || '',
          phone: lead.phone || '',
          website: leadWebsiteHref(lead) || lead.websiteDomain || '',
          jobTitle: lead.category || '',
          address: lead.address || '',
          city: lead.city || '',
          state: lead.state || '',
          postalCode: lead.postalCode || '',
          country: lead.country || '',
          sourceUrl: lead.sourceUrl || '',
          source: 'LeadsMCP lead search',
        };
        const clean = {};
        Object.entries(fields).forEach(([key, value]) => {
          if (value) clean[key] = value;
        });
        return [
          'Create or update a contact in the currently connected GoHighLevel location using the LeadsMCP GHL tools.',
          'Match on email or phone first to avoid duplicates: update the existing contact if one already exists, otherwise create a new one.',
          'After writing, confirm exactly what you created or updated.',
          '',
          'Lead details:',
          JSON.stringify(clean, null, 2),
        ].join('\\n');
      }

      function pushLeadToLocation(leadId) {
        const lead = getLeadById(leadId);
        if (!lead) return;
        openAiWorkspace(false);
        if (!state.encryptedData) {
          setAiStatus('Load the HighLevel context first, then push leads to your location.', '');
          return;
        }
        void runAiPrompt(buildLeadPushPrompt(lead));
      }

      function renderContext(context) {
        setContextNode('status', 'Context loaded from HighLevel', 'status-good');
        setContextNode('user', context.userName || 'Unknown user');
        setContextNode('email', context.email || 'Not provided');
        setContextNode('company', context.companyId || 'Not provided');
        setContextNode('location', context.activeLocation || 'Not provided');
        setContextNode('role', context.role || context.type || 'Not provided');
        runButton.disabled = false;
        runButton.textContent = 'Run Search';
        setAiStatus('Copilot ready for read-only research.', aiModel ? aiModel.textContent : 'LLM ready');
        setAiComposerEnabled(true);
      }

      function syncBodyScrollLock() {
        const shouldLock = (resultsBackdrop && resultsBackdrop.classList.contains('is-open'))
          || (aiBackdrop && aiBackdrop.classList.contains('is-open'))
          || (detailBackdrop && detailBackdrop.classList.contains('is-open'));
        document.body.style.overflow = shouldLock ? 'hidden' : '';
      }

      function openResultsWorkspace(tabName = state.activeTab || 'leads') {
        if (!resultsBackdrop || !state.searchPayload) return;
        state.resultsOpen = true;
        resultsBackdrop.classList.add('is-open');
        syncBodyScrollLock();
        activateTab(tabName);
      }

      function closeResultsWorkspace() {
        if (!resultsBackdrop) return;
        state.resultsOpen = false;
        resultsBackdrop.classList.remove('is-open');
        syncBodyScrollLock();
      }

      function renderContextError(message) {
        setContextNode('status', message, 'status-bad');
        setContextNode('user', 'Unavailable');
        setContextNode('email', 'Unavailable');
        setContextNode('company', 'Unavailable');
        setContextNode('location', 'Unavailable');
        setContextNode('role', 'Unavailable');
        runButton.disabled = true;
        runButton.textContent = 'Load GHL context first';
        setAiStatus(message, aiModel ? aiModel.textContent : 'LLM unavailable');
        setAiComposerEnabled(false);
      }

      const RESULT_FAMILY_META = {
        google_maps_search: { label: 'Lead response', hint: 'Business cards with map markers and scrape actions.' },
        emails_and_contacts: { label: 'Website contact response', hint: 'Contact-enrichment cards built for outreach review.' },
        google_maps_reviews: { label: 'Review response', hint: 'Review cards tuned for sentiment and reputation research.' },
        email_validator: { label: 'Validation response', hint: 'Deliverability-first validation cards for email quality checks.' },
        phones_enricher: { label: 'Validation response', hint: 'Carrier and ownership cards for phone-quality checks.' },
        geocoding: { label: 'Geo response', hint: 'Location cards centered on coordinates and address resolution.' },
        reverse_geocoding: { label: 'Geo response', hint: 'Location cards centered on coordinates and address resolution.' },
        google_search: { label: 'Research response', hint: 'Search-result cards for discovery, sourcing, and outreach prep.' },
        google_search_news: { label: 'Research response', hint: 'Article cards for recent news, market shifts, and context.' },
        google_trends: { label: 'Trend response', hint: 'Trend-point cards for demand and interest signals.' },
        linkedin_profiles: { label: 'Profile response', hint: 'Person and account cards built for targeted prospect research.' },
        linkedin_companies: { label: 'Profile response', hint: 'Company profile cards with website and team context.' },
        linkedin_posts: { label: 'Content response', hint: 'Post cards for messaging, tone, and content intelligence.' },
        tiktok_profiles: { label: 'Profile response', hint: 'Creator cards for audience and partnership research.' },
        twitter_profiles: { label: 'Profile response', hint: 'Profile cards for founder, brand, and media discovery.' },
        youtube_search: { label: 'Video response', hint: 'Video cards for podcast, channel, and content sourcing.' },
        youtube_videos: { label: 'Video response', hint: 'Channel video cards built for outreach and research review.' },
        youtube_transcripts: { label: 'Transcript response', hint: 'Transcript segments rendered for quick scanning and copying.' },
        similarweb: { label: 'Domain intel response', hint: 'Traffic and rank cards for account qualification.' },
      };

      const LEAD_STYLE_SEARCH_TYPES = new Set([
        'google_maps_search',
        'emails_and_contacts'
      ]);
      const REVIEW_SEARCH_TYPES = new Set(['google_maps_reviews']);
      const VALIDATION_SEARCH_TYPES = new Set(['email_validator', 'phones_enricher']);
      const GEO_SEARCH_TYPES = new Set(['geocoding', 'reverse_geocoding']);
      const PROFILE_SEARCH_TYPES = new Set(['linkedin_profiles', 'linkedin_companies', 'tiktok_profiles', 'twitter_profiles']);
      const POST_SEARCH_TYPES = new Set(['linkedin_posts']);
      const ARTICLE_SEARCH_TYPES = new Set(['google_search', 'google_search_news']);
      const VIDEO_SEARCH_TYPES = new Set(['youtube_search', 'youtube_videos']);
      const TRANSCRIPT_SEARCH_TYPES = new Set(['youtube_transcripts']);
      const TRENDS_SEARCH_TYPES = new Set(['google_trends']);
      const DOMAIN_INTEL_SEARCH_TYPES = new Set(['similarweb']);

      async function copyTextToClipboard(text, fallbackLabel) {
        const value = String(text || '');
        if (!value) return false;
        try {
          if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(value);
            return true;
          }
        } catch (error) {
        }

        try {
          const area = document.createElement('textarea');
          area.value = value;
          area.setAttribute('readonly', '');
          area.style.position = 'absolute';
          area.style.left = '-9999px';
          document.body.appendChild(area);
          area.select();
          document.execCommand('copy');
          document.body.removeChild(area);
          return true;
        } catch (error) {
          resultsMeta.textContent = `${fallbackLabel || 'Copy'} failed.`;
          return false;
        }
      }

      function downloadJsonFile(filename, payload) {
        const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
      }

      function deepFlatten(value) {
        if (!Array.isArray(value)) return [value];
        const output = [];
        value.forEach((item) => {
          if (Array.isArray(item)) {
            output.push(...deepFlatten(item));
          } else {
            output.push(item);
          }
        });
        return output;
      }

      function firstNonEmpty() {
        for (const value of arguments) {
          if (value === null || value === undefined) continue;
          if (typeof value === 'string') {
            const trimmed = value.trim();
            if (trimmed) return trimmed;
            continue;
          }
          if (Array.isArray(value) && value.length) return value;
          if (typeof value === 'object' && Object.keys(value).length) return value;
          if (value !== '') return value;
        }
        return '';
      }

      function firstArray() {
        for (const value of arguments) {
          if (!Array.isArray(value)) continue;
          const flattened = deepFlatten(value).filter((item) => item !== null && item !== undefined);
          if (flattened.length) return flattened;
        }
        return [];
      }

      function normalizeResultRows(payload) {
        const result = payload && payload.result ? payload.result : {};
        return firstArray(
          result.data,
          result.results,
          result.items,
          result.organic_results,
          result.organicResults,
          result.news_results,
          result.newsResults,
          result.posts,
          result.videos,
          result.video_results,
          result.videoResults,
          result.profiles,
          result.companies,
          result.trends,
          result.timeline_data,
          result.timelineData,
          result.locations
        ).filter((item) => item && typeof item === 'object');
      }

      function searchTypePrimaryLabel(searchType) {
        if (LEAD_STYLE_SEARCH_TYPES.has(searchType)) return 'Lead cards';
        if (REVIEW_SEARCH_TYPES.has(searchType)) return 'Reviews';
        if (VALIDATION_SEARCH_TYPES.has(searchType)) return 'Checks';
        if (GEO_SEARCH_TYPES.has(searchType)) return 'Locations';
        if (PROFILE_SEARCH_TYPES.has(searchType)) return 'Profiles';
        if (POST_SEARCH_TYPES.has(searchType)) return 'Posts';
        if (ARTICLE_SEARCH_TYPES.has(searchType)) return 'Articles';
        if (VIDEO_SEARCH_TYPES.has(searchType)) return 'Videos';
        if (TRANSCRIPT_SEARCH_TYPES.has(searchType)) return 'Transcript rows';
        if (TRENDS_SEARCH_TYPES.has(searchType)) return 'Trend points';
        if (DOMAIN_INTEL_SEARCH_TYPES.has(searchType)) return 'Domains';
        return 'Records';
      }

      function metricsForPayload(payload) {
        const rows = normalizeResultRows(payload);
        const summary = [
          { label: searchTypePrimaryLabel(payload.searchType), value: payload.leadCount || rows.length || 0 },
          { label: 'Map markers', value: payload.geoLeadCount || 0 },
          { label: 'Search type', value: payload.searchLabel || payload.searchType || 'Unknown' },
          { label: 'Runtime', value: `${payload.elapsedMs || 0} ms` },
        ];

        const result = payload.result || {};
        if (Array.isArray(result.requested_domains)) {
          summary.push({ label: 'Requested domains', value: result.requested_domains.length });
        }
        if (typeof result.failed_domains === 'number') {
          summary.push({ label: 'Failed domains', value: result.failed_domains });
        }
        return summary.slice(0, 6);
      }

      function familyMetaForPayload(payload) {
        return RESULT_FAMILY_META[payload.searchType] || {
          label: 'Structured response',
          hint: 'Structured cards generated from the current Outscraper response.'
        };
      }

      function renderResultsFamily(payload) {
        if (!resultsFamily) return;
        const family = familyMetaForPayload(payload);
        resultsFamily.textContent = family.label;
        if (resultsMeta && payload && family.hint) {
          resultsMeta.textContent = `${payload.searchLabel} completed in ${payload.elapsedMs} ms for location ${payload.context.activeLocation || 'unknown'}. ${family.hint}`;
        }
      }

      function filterOptionsForPayload(payload) {
        if (!payload) return [{ id: 'all', label: 'All', predicate: () => true }];
        if (LEAD_STYLE_SEARCH_TYPES.has(payload.searchType)) {
          return [
            { id: 'all', label: 'All', predicate: () => true },
            { id: 'contactable', label: 'Contactable', predicate: (item) => Boolean(item.email || item.phone) },
            { id: 'mapped', label: 'Mapped', predicate: (item) => Boolean(item.hasCoordinates) },
            { id: 'website', label: 'Website', predicate: (item) => Boolean(item.website || item.websiteDomain) },
          ];
        }
        if (REVIEW_SEARCH_TYPES.has(payload.searchType)) {
          return [
            { id: 'all', label: 'All', predicate: () => true },
            { id: 'high_rating', label: 'High Rating', predicate: (item) => Number(item.rating || 0) >= 4 },
            { id: 'owner_reply', label: 'Owner Reply', predicate: (item) => Boolean(item.owner_answer || item.owner_response) },
          ];
        }
        if (VALIDATION_SEARCH_TYPES.has(payload.searchType)) {
          return [
            { id: 'all', label: 'All', predicate: () => true },
            { id: 'positive', label: 'Positive', predicate: (item) => /receiving|valid|ok/i.test(String(firstNonEmpty(item.status, item.result, item.validation_status))) },
            { id: 'risky', label: 'Risky', predicate: (item) => /invalid|unknown|risky|disposable/i.test(String(firstNonEmpty(item.status, item.result, item.validation_status))) || item.is_disposable === true || item.is_valid === false },
          ];
        }
        if (ARTICLE_SEARCH_TYPES.has(payload.searchType) || POST_SEARCH_TYPES.has(payload.searchType) || VIDEO_SEARCH_TYPES.has(payload.searchType)) {
          return [
            { id: 'all', label: 'All', predicate: () => true },
            { id: 'with_link', label: 'Has Link', predicate: (item) => Boolean(item.link || item.url || item.video_url) },
            { id: 'with_snippet', label: 'With Snippet', predicate: (item) => Boolean(item.snippet || item.description || item.text || item.content) },
          ];
        }
        if (PROFILE_SEARCH_TYPES.has(payload.searchType) || DOMAIN_INTEL_SEARCH_TYPES.has(payload.searchType)) {
          return [
            { id: 'all', label: 'All', predicate: () => true },
            { id: 'with_website', label: 'With Website', predicate: (item) => Boolean(item.website || item.company_website || item.url || item.link || item.domain) },
            { id: 'with_location', label: 'With Location', predicate: (item) => Boolean(item.location || item.city || item.country) },
          ];
        }
        return [{ id: 'all', label: 'All', predicate: () => true }];
      }

      function applyActiveResultFilter(items, payload) {
        const filters = filterOptionsForPayload(payload);
        if (!filters.some((filter) => filter.id === state.activeResultFilter)) {
          state.activeResultFilter = 'all';
        }
        const active = filters.find((filter) => filter.id === state.activeResultFilter) || filters[0];
        return {
          filters,
          filteredItems: items.filter((item) => {
            try {
              return active.predicate(item);
            } catch (error) {
              return true;
            }
          }),
        };
      }

      function renderFilterStrip(payload, items) {
        if (!resultsFilters) return;
        const { filters } = applyActiveResultFilter(items, payload);
        if (filters.length <= 1) {
          resultsFilters.hidden = true;
          resultsFilters.innerHTML = '';
          return;
        }
        resultsFilters.hidden = false;
        resultsFilters.innerHTML = filters.map((filter) => {
          const count = items.filter((item) => {
            try {
              return filter.predicate(item);
            } catch (error) {
              return false;
            }
          }).length;
          const active = filter.id === state.activeResultFilter;
          return `<button class="filter-chip${active ? ' is-active' : ''}" type="button" data-result-filter="${escapeHtml(filter.id)}">${escapeHtml(filter.label)} (${count})</button>`;
        }).join('');
      }

      function setVisibleResults(items, payload) {
        state.visibleResults = items.map((item, index) => ({
          id: item.id || `result-${index + 1}`,
          type: payload.searchType,
          label: payload.searchLabel || payload.searchType || 'result',
          data: item,
        }));
        const hasVisible = state.visibleResults.length > 0;
        if (copyVisibleButton) copyVisibleButton.disabled = !hasVisible;
        if (exportJsonVisibleButton) exportJsonVisibleButton.disabled = !hasVisible;
        if (exportCsvVisibleButton) exportCsvVisibleButton.disabled = !hasVisible;
      }

      function renderCardActions(index, options = {}) {
        const buttons = [
          `<button class="response-card-action" type="button" data-card-copy="${index}">Copy JSON</button>`,
          `<button class="response-card-action" type="button" data-card-export="${index}">Export JSON</button>`,
        ];
        if (options.openLeadId) {
          buttons.unshift(`<button class="response-card-action" type="button" data-lead-open="${escapeHtml(options.openLeadId)}">Open Detail</button>`);
        }
        if (options.pushLeadId) {
          buttons.unshift(`<button class="response-card-action is-primary" type="button" data-lead-push="${escapeHtml(options.pushLeadId)}">Push to Location</button>`);
        }
        return `<div class="response-card-actions">${buttons.join('')}</div>`;
      }

      function renderPills(values) {
        const items = values.filter(Boolean);
        if (!items.length) return '';
        return `<div class="pill-row">${items.map((value) => `<span class="pill soft">${escapeHtml(value)}</span>`).join('')}</div>`;
      }

      function renderResponseKv(entries) {
        const rows = entries.filter(([, value]) => value !== null && value !== undefined && compactValue(value));
        if (!rows.length) {
          return '<p class="response-empty-note">No structured fields were returned for this result.</p>';
        }
        return `
          <div class="response-kv">
            ${rows.map(([key, value]) => `
              <div class="response-kv-row">
                <div class="response-kv-key">${escapeHtml(key)}</div>
                <div class="response-kv-value">${escapeHtml(compactValue(value))}</div>
              </div>
            `).join('')}
          </div>
        `;
      }

      function renderStructuredCards(items, options) {
        renderFilterStrip(state.searchPayload, items);
        const filtered = state.searchPayload ? applyActiveResultFilter(items, state.searchPayload).filteredItems : items;
        setVisibleResults(filtered, state.searchPayload || { searchType: state.currentSearchType, searchLabel: state.currentSearchType });

        if (!filtered.length) {
          resultsEmpty.hidden = false;
          leadGrid.hidden = true;
          resultsEmpty.textContent = items.length
            ? 'No results match the active filter.'
            : (options.emptyMessage || 'This search completed, but there were no structured results to display.');
          leadGrid.classList.remove('is-single-column');
          return;
        }

        resultsEmpty.hidden = true;
        leadGrid.hidden = false;
        leadGrid.classList.toggle('is-single-column', Boolean(options.singleColumn));
        leadGrid.innerHTML = filtered.map((item, index) => {
          const title = firstNonEmpty(options.title(item, index), `${options.fallbackTitle || 'Result'} ${index + 1}`);
          const kicker = firstNonEmpty(options.kicker && options.kicker(item, index), options.defaultKicker, state.currentSearchType || 'result');
          const subtitle = options.subtitle ? options.subtitle(item, index) : '';
          const snippet = options.snippet ? options.snippet(item, index) : '';
          const pills = options.pills ? options.pills(item, index) : [];
          const details = options.details ? options.details(item, index) : [];
          const footer = options.footer ? options.footer(item, index) : '';
          return `
            <article class="lead-card">
              <div class="lead-card-header">
                <div>
                  <div class="lead-card-kicker">${escapeHtml(kicker)}</div>
                  <h3>${escapeHtml(title)}</h3>
                </div>
              </div>
              <div class="response-stack">
                ${subtitle ? `<div class="lead-card-line">${escapeHtml(subtitle)}</div>` : ''}
                ${renderPills(Array.isArray(pills) ? pills : [])}
                ${snippet ? `<p class="response-card-snippet">${escapeHtml(snippet)}</p>` : ''}
                ${renderResponseKv(Array.isArray(details) ? details : [])}
                ${footer || ''}
                ${renderCardActions(index)}
              </div>
            </article>
          `;
        }).join('');
      }

      function renderReviewCards(payload) {
        const rows = normalizeResultRows(payload);
        renderStructuredCards(rows, {
          defaultKicker: 'Review',
          fallbackTitle: 'Review',
          title: (row) => firstNonEmpty(row.author_title, row.author_name, row.user, row.name, row.reviewer_name),
          subtitle: (row) => firstNonEmpty(row.review_datetime_utc, row.relative_date, row.date, row.review_date),
          snippet: (row) => firstNonEmpty(row.review_text, row.text, row.snippet, row.description),
          pills: (row) => [
            row.rating !== undefined && row.rating !== null ? `Rating ${row.rating}` : '',
            firstNonEmpty(row.likes, row.likes_count) ? `${firstNonEmpty(row.likes, row.likes_count)} likes` : '',
            row.is_local_guide ? 'Local guide' : ''
          ],
          details: (row) => [
            ['Author', firstNonEmpty(row.author_title, row.author_name, row.user, row.name)],
            ['Rating', row.rating],
            ['Date', firstNonEmpty(row.review_datetime_utc, row.relative_date, row.date, row.review_date)],
            ['Text', firstNonEmpty(row.review_text, row.text, row.snippet)],
            ['Owner response', firstNonEmpty(row.owner_answer, row.owner_response)],
          ],
          emptyMessage: 'No review records were returned for this business query.'
        });
      }

      function renderValidationCards(payload) {
        const rows = normalizeResultRows(payload);
        const isEmail = payload.searchType === 'email_validator';
        renderStructuredCards(rows, {
          defaultKicker: isEmail ? 'Email validation' : 'Phone enrichment',
          fallbackTitle: isEmail ? 'Email check' : 'Phone check',
          title: (row) => firstNonEmpty(row.email, row.query, row.phone, row.number, row.input),
          subtitle: (row) => firstNonEmpty(row.status, row.result, row.validation_status, row.carrier_name, row.carrier),
          pills: (row) => [
            firstNonEmpty(row.smtp_provider, row.provider),
            firstNonEmpty(row.carrier_name, row.carrier),
            firstNonEmpty(row.line_type, row.phone_type, row.type),
            row.is_disposable ? 'Disposable' : '',
            row.is_valid === False ? 'Invalid' : '',
          ],
          details: (row) => [
            ['Input', firstNonEmpty(row.email, row.query, row.phone, row.number, row.input)],
            ['Status', firstNonEmpty(row.status, row.result, row.validation_status)],
            ['Provider', firstNonEmpty(row.smtp_provider, row.provider)],
            ['Carrier', firstNonEmpty(row.carrier_name, row.carrier)],
            ['Type', firstNonEmpty(row.line_type, row.phone_type, row.type)],
            ['Country', firstNonEmpty(row.country, row.country_code)],
            ['Owner', firstNonEmpty(row.owner_name, row.owner, row.name)],
          ],
          emptyMessage: 'No validation results were returned.'
        });
      }

      function renderGeocodeCards(payload) {
        const rows = normalizeResultRows(payload);
        renderStructuredCards(rows.length ? rows : [payload.result || {}], {
          defaultKicker: payload.searchType === 'geocoding' ? 'Geocoding' : 'Reverse geocoding',
          fallbackTitle: 'Location result',
          title: (row) => firstNonEmpty(row.formatted_address, row.address, row.query, row.display_name, row.location),
          subtitle: (row) => firstNonEmpty(row.place_id, row.type, row.location_type),
          pills: (row) => [
            firstNonEmpty(row.country, row.country_code),
            firstNonEmpty(row.city, row.locality),
          ],
          details: (row) => [
            ['Address', firstNonEmpty(row.formatted_address, row.address, row.display_name)],
            ['Latitude', firstNonEmpty(row.latitude, row.lat)],
            ['Longitude', firstNonEmpty(row.longitude, row.lng, row.lon)],
            ['City', firstNonEmpty(row.city, row.locality)],
            ['State / Region', firstNonEmpty(row.state, row.region)],
            ['Country', firstNonEmpty(row.country, row.country_code)],
            ['Postal code', firstNonEmpty(row.postal_code, row.zip, row.postcode)],
          ],
          emptyMessage: 'No location results were returned for this query.'
        });
      }

      function renderArticleCards(payload) {
        const rows = normalizeResultRows(payload);
        renderStructuredCards(rows, {
          defaultKicker: payload.searchType === 'google_search_news' ? 'News result' : 'Search result',
          fallbackTitle: 'Search result',
          title: (row) => firstNonEmpty(row.title, row.name, row.source),
          subtitle: (row) => firstNonEmpty(row.displayed_link, row.link, row.url, row.source),
          snippet: (row) => firstNonEmpty(row.snippet, row.description, row.text),
          pills: (row) => [
            firstNonEmpty(row.date, row.published, row.published_at, row.time),
            firstNonEmpty(row.source),
            row.rank !== undefined ? `Rank ${row.rank}` : '',
          ],
          details: (row) => [
            ['Title', firstNonEmpty(row.title, row.name)],
            ['Link', firstNonEmpty(row.link, row.url, row.displayed_link)],
            ['Source', firstNonEmpty(row.source)],
            ['Published', firstNonEmpty(row.date, row.published, row.published_at, row.time)],
            ['Snippet', firstNonEmpty(row.snippet, row.description, row.text)],
          ],
          emptyMessage: 'No search articles were returned.'
        });
      }

      function renderProfileCards(payload) {
        const rows = normalizeResultRows(payload);
        renderStructuredCards(rows, {
          defaultKicker: 'Profile',
          fallbackTitle: 'Profile',
          title: (row) => firstNonEmpty(row.name, row.full_name, row.company_name, row.title),
          subtitle: (row) => firstNonEmpty(row.headline, row.position, row.category, row.bio, row.description),
          snippet: (row) => firstNonEmpty(row.summary, row.about, row.description, row.bio),
          pills: (row) => [
            firstNonEmpty(row.location, row.city, row.country),
            firstNonEmpty(row.followers, row.followers_count) ? `${firstNonEmpty(row.followers, row.followers_count)} followers` : '',
            firstNonEmpty(row.employees_count, row.company_size) ? `${firstNonEmpty(row.employees_count, row.company_size)} team` : '',
          ],
          details: (row) => [
            ['Name', firstNonEmpty(row.name, row.full_name, row.company_name)],
            ['Headline', firstNonEmpty(row.headline, row.position, row.title)],
            ['Location', firstNonEmpty(row.location, row.city, row.country)],
            ['Website', firstNonEmpty(row.website, row.company_website, row.url, row.link)],
            ['Followers', firstNonEmpty(row.followers, row.followers_count)],
            ['Employees', firstNonEmpty(row.employees_count, row.company_size)],
            ['About', firstNonEmpty(row.summary, row.about, row.description, row.bio)],
          ],
          emptyMessage: 'No profile results were returned.'
        });
      }

      function renderPostCards(payload) {
        const rows = normalizeResultRows(payload);
        renderStructuredCards(rows, {
          defaultKicker: 'Post',
          fallbackTitle: 'LinkedIn post',
          title: (row) => firstNonEmpty(row.author, row.company_name, row.name, row.title),
          subtitle: (row) => firstNonEmpty(row.date, row.published_at, row.posted_at),
          snippet: (row) => firstNonEmpty(row.text, row.content, row.description, row.snippet),
          pills: (row) => [
            firstNonEmpty(row.likes, row.likes_count) ? `${firstNonEmpty(row.likes, row.likes_count)} likes` : '',
            firstNonEmpty(row.comments, row.comments_count) ? `${firstNonEmpty(row.comments, row.comments_count)} comments` : '',
            firstNonEmpty(row.reposts, row.shares) ? `${firstNonEmpty(row.reposts, row.shares)} shares` : '',
          ],
          details: (row) => [
            ['Author', firstNonEmpty(row.author, row.company_name, row.name)],
            ['Date', firstNonEmpty(row.date, row.published_at, row.posted_at)],
            ['Text', firstNonEmpty(row.text, row.content, row.description, row.snippet)],
            ['Link', firstNonEmpty(row.link, row.url)],
          ],
          emptyMessage: 'No post results were returned.'
        });
      }

      function renderVideoCards(payload) {
        const rows = normalizeResultRows(payload);
        renderStructuredCards(rows, {
          defaultKicker: 'Video',
          fallbackTitle: 'Video result',
          title: (row) => firstNonEmpty(row.title, row.name, row.channel_name),
          subtitle: (row) => firstNonEmpty(row.channel_name, row.channel, row.author),
          snippet: (row) => firstNonEmpty(row.description, row.snippet),
          pills: (row) => [
            firstNonEmpty(row.published, row.date, row.upload_date),
            firstNonEmpty(row.views, row.view_count) ? `${firstNonEmpty(row.views, row.view_count)} views` : '',
            firstNonEmpty(row.duration),
          ],
          details: (row) => [
            ['Title', firstNonEmpty(row.title, row.name)],
            ['Channel', firstNonEmpty(row.channel_name, row.channel, row.author)],
            ['Published', firstNonEmpty(row.published, row.date, row.upload_date)],
            ['Duration', firstNonEmpty(row.duration)],
            ['Views', firstNonEmpty(row.views, row.view_count)],
            ['Link', firstNonEmpty(row.link, row.url, row.video_url)],
            ['Description', firstNonEmpty(row.description, row.snippet)],
          ],
          emptyMessage: 'No video results were returned.'
        });
      }

      function renderTranscriptCards(payload) {
        const rows = normalizeResultRows(payload);
        renderStructuredCards(rows.length ? rows : [payload.result || {}], {
          defaultKicker: 'Transcript',
          fallbackTitle: 'Transcript segment',
          title: (row, index) => firstNonEmpty(row.title, row.video_title, row.video, index !== undefined ? `Transcript line ${index + 1}` : ''),
          subtitle: (row) => firstNonEmpty(row.start, row.offset, row.timestamp),
          snippet: (row) => firstNonEmpty(row.text, row.transcript, row.caption, row.content),
          details: (row) => [
            ['Timestamp', firstNonEmpty(row.start, row.offset, row.timestamp)],
            ['Text', firstNonEmpty(row.text, row.transcript, row.caption, row.content)],
            ['Language', firstNonEmpty(row.language)],
            ['Video', firstNonEmpty(row.video_url, row.video, row.url)],
          ],
          singleColumn: true,
          emptyMessage: 'No transcript rows were returned for this video.'
        });
      }

      function renderTrendCards(payload) {
        const rows = normalizeResultRows(payload);
        renderStructuredCards(rows.length ? rows : [payload.result || {}], {
          defaultKicker: 'Trend',
          fallbackTitle: 'Trend point',
          title: (row) => firstNonEmpty(row.query, row.keyword, row.term, row.title),
          subtitle: (row) => firstNonEmpty(row.date, row.period, row.time),
          pills: (row) => [
            firstNonEmpty(row.value, row.score, row.interest) ? `Interest ${firstNonEmpty(row.value, row.score, row.interest)}` : '',
            firstNonEmpty(row.region, row.country),
          ],
          details: (row) => [
            ['Query', firstNonEmpty(row.query, row.keyword, row.term, row.title)],
            ['Date / Period', firstNonEmpty(row.date, row.period, row.time)],
            ['Interest', firstNonEmpty(row.value, row.score, row.interest)],
            ['Region', firstNonEmpty(row.region, row.country)],
          ],
          emptyMessage: 'No trend data points were returned for this query.'
        });
      }

      function renderDomainIntelCards(payload) {
        const rows = normalizeResultRows(payload);
        renderStructuredCards(rows, {
          defaultKicker: 'Domain intelligence',
          fallbackTitle: 'Domain result',
          title: (row) => firstNonEmpty(row.domain, row.website, row.name),
          subtitle: (row) => firstNonEmpty(row.category, row.industry),
          pills: (row) => [
            firstNonEmpty(row.country),
            firstNonEmpty(row.rank) ? `Rank ${firstNonEmpty(row.rank)}` : '',
            firstNonEmpty(row.monthly_visits, row.visits) ? `${firstNonEmpty(row.monthly_visits, row.visits)} visits` : '',
          ],
          details: (row) => [
            ['Domain', firstNonEmpty(row.domain, row.website, row.name)],
            ['Category', firstNonEmpty(row.category, row.industry)],
            ['Country', firstNonEmpty(row.country)],
            ['Rank', firstNonEmpty(row.rank)],
            ['Visits', firstNonEmpty(row.monthly_visits, row.visits)],
          ],
          emptyMessage: 'No Similarweb domain intelligence rows were returned.'
        });
      }

      function summarizePayload(payload) {
        return metricsForPayload(payload);
      }

      function renderSummary(payload) {
        const metrics = summarizePayload(payload);
        resultsSummary.innerHTML = metrics.map((item) => `
          <div class="metric">
            <div class="metric-label">${escapeHtml(item.label)}</div>
            <div class="metric-value">${escapeHtml(formatMetricValue(item.value))}</div>
          </div>
        `).join('');
        resultsSummary.hidden = metrics.length === 0;
      }

      function renderLeadCards(payload) {
        if (!LEAD_STYLE_SEARCH_TYPES.has(payload.searchType)) {
          if (REVIEW_SEARCH_TYPES.has(payload.searchType)) return renderReviewCards(payload);
          if (VALIDATION_SEARCH_TYPES.has(payload.searchType)) return renderValidationCards(payload);
          if (GEO_SEARCH_TYPES.has(payload.searchType)) return renderGeocodeCards(payload);
          if (PROFILE_SEARCH_TYPES.has(payload.searchType)) return renderProfileCards(payload);
          if (POST_SEARCH_TYPES.has(payload.searchType)) return renderPostCards(payload);
          if (ARTICLE_SEARCH_TYPES.has(payload.searchType)) return renderArticleCards(payload);
          if (VIDEO_SEARCH_TYPES.has(payload.searchType)) return renderVideoCards(payload);
          if (TRANSCRIPT_SEARCH_TYPES.has(payload.searchType)) return renderTranscriptCards(payload);
          if (TRENDS_SEARCH_TYPES.has(payload.searchType)) return renderTrendCards(payload);
          if (DOMAIN_INTEL_SEARCH_TYPES.has(payload.searchType)) return renderDomainIntelCards(payload);
        }

        const leads = Array.isArray(payload.leads) ? payload.leads : [];
        renderFilterStrip(payload, leads);
        const filtered = applyActiveResultFilter(leads, payload).filteredItems;
        setVisibleResults(filtered, payload);

        if (!filtered.length) {
          resultsEmpty.hidden = false;
          leadGrid.hidden = true;
          resultsEmpty.textContent = leads.length ? 'No leads match the active filter.' : 'This search completed, but there were no lead records to render as cards.';
          leadGrid.classList.remove('is-single-column');
          return;
        }

        resultsEmpty.hidden = true;
        leadGrid.hidden = false;
        leadGrid.classList.remove('is-single-column');
        leadGrid.innerHTML = filtered.map((lead, index) => {
          const locationLine = extractLocationLine(lead);
          const rating = formatRating(lead);
          const subline = [lead.phone, lead.email, lead.websiteDomain].filter(Boolean).join(' · ');
          const contactStyleSearch = lead.searchType === 'emails_and_contacts';
          return `
            <article class="lead-card">
              <button class="lead-card-open" type="button" data-lead-open="${escapeHtml(lead.id)}">
                <div class="lead-card-header">
                  <div class="lead-card-header-main">
                    ${renderLeadLogo(lead)}
                    <div class="lead-card-title-wrap">
                      <div class="lead-card-kicker">${escapeHtml(contactStyleSearch ? 'contact row' : (lead.searchType || 'lead'))}</div>
                      <h3>${escapeHtml(lead.name || 'Unnamed Lead')}</h3>
                    </div>
                  </div>
                  ${rating ? `<span class="pill soft">${escapeHtml(rating)}</span>` : ''}
                </div>
                <div class="lead-card-body">
                  ${locationLine ? `<div class="lead-card-line">${escapeHtml(locationLine)}</div>` : ''}
                  ${subline ? `<div class="lead-card-line">${escapeHtml(subline)}</div>` : ''}
                  ${lead.category ? `<div class="pill-row"><span class="pill soft">${escapeHtml(lead.category)}</span></div>` : ''}
                  ${lead.description ? `<p class="lead-card-snippet">${escapeHtml(lead.description)}</p>` : ''}
                </div>
              </button>
              ${renderLeadLinkButtons(lead)}
              ${renderCardActions(index, { openLeadId: lead.id, pushLeadId: lead.id })}
            </article>
          `;
        }).join('');
      }

      function loadMapProvider() {
        if (window.mapboxgl) {
          window.mapboxgl.accessToken = MAPBOX_PUBLIC_TOKEN;
          return Promise.resolve(window.mapboxgl);
        }
        if (!MAPBOX_PUBLIC_TOKEN || !MAPBOX_JS_URL) {
          return Promise.reject(new Error('Mapbox is not configured for this deployment.'));
        }
        if (state.mapProviderLoadingPromise) {
          return state.mapProviderLoadingPromise;
        }

        state.mapProviderLoadingPromise = new Promise((resolve, reject) => {
          const finishError = (message) => {
            state.mapProviderLoadingPromise = null;
            state.mapProviderAuthMessage = message;
            reject(new Error(message));
          };

          if (MAPBOX_CSS_URL && !document.querySelector('link[data-mapbox-gl-css]')) {
            const css = document.createElement('link');
            css.rel = 'stylesheet';
            css.href = MAPBOX_CSS_URL;
            css.setAttribute('data-mapbox-gl-css', 'true');
            document.head.appendChild(css);
          }

          const existingScript = document.querySelector('script[data-mapbox-gl-js]');
          if (existingScript) {
            existingScript.addEventListener('load', function onLoad() {
              existingScript.removeEventListener('load', onLoad);
              if (!window.mapboxgl) {
                finishError('Mapbox loaded incompletely. Check the public token and script access.');
                return;
              }
              window.mapboxgl.accessToken = MAPBOX_PUBLIC_TOKEN;
              state.mapProviderAuthMessage = '';
              resolve(window.mapboxgl);
            });
            existingScript.addEventListener('error', function onError() {
              existingScript.removeEventListener('error', onError);
              finishError('Mapbox failed to load. Check the public token, network access, and Mapbox CDN availability.');
            });
            return;
          }

          const script = document.createElement('script');
          script.src = MAPBOX_JS_URL;
          script.async = true;
          script.defer = true;
          script.setAttribute('data-mapbox-gl-js', 'true');
          script.onload = function () {
            if (!window.mapboxgl) {
              finishError('Mapbox loaded incompletely. Check the public token and script access.');
              return;
            }
            window.mapboxgl.accessToken = MAPBOX_PUBLIC_TOKEN;
            state.mapProviderAuthMessage = '';
            resolve(window.mapboxgl);
          };
          script.onerror = function () {
            finishError('Mapbox failed to load. Check the public token, network access, and Mapbox CDN availability.');
          };
          document.head.appendChild(script);
        });

        return state.mapProviderLoadingPromise;
      }

      async function ensureMap() {
        if (state.map || !mapFrame) return state.map;
        await loadMapProvider();
        state.map = new window.mapboxgl.Map({
          container: mapFrame,
          style: MAPBOX_STYLE_URL || 'mapbox://styles/mapbox/standard-satellite',
          center: [0, 0],
          zoom: 2,
          attributionControl: true,
          cooperativeGestures: true,
        });
        state.map.addControl(new window.mapboxgl.NavigationControl({ showCompass: false }), 'top-right');
        state.mapInfoWindow = null;
        state.map.on('error', function (event) {
          const message = (event && event.error && event.error.message)
            ? `Mapbox error: ${event.error.message}`
            : 'Mapbox failed to render. Check the public token and style permissions.';
          state.mapProviderAuthMessage = message;
        });
        await new Promise((resolve) => state.map.once('load', resolve));
        return state.map;
      }

      function clearMapMarkers() {
        state.mapMarkers.forEach((marker) => marker.remove());
        state.mapMarkers = [];
      }

      async function renderMap(payload) {
        const geoLeads = (Array.isArray(payload.leads) ? payload.leads : []).filter((lead) => lead.hasCoordinates);
        if (!geoLeads.length) {
          mapFrame.hidden = true;
          mapEmpty.hidden = false;
          mapStats.innerHTML = '<span class="pill soft">No coordinates available</span>';
          clearMapMarkers();
          return;
        }

        if (!MAPBOX_PUBLIC_TOKEN || !MAPBOX_JS_URL) {
          mapFrame.hidden = true;
          mapEmpty.hidden = false;
          mapEmpty.textContent = 'Mapbox is not configured for this deployment yet.';
          mapStats.innerHTML = '<span class="pill soft">Missing Mapbox public token</span>';
          return;
        }

        try {
          await ensureMap();
        } catch (error) {
          mapFrame.hidden = true;
          mapEmpty.hidden = false;
          mapEmpty.textContent = state.mapProviderAuthMessage || error.message || 'Mapbox failed to load. Refresh the page and try again.';
          mapStats.innerHTML = '<span class="pill soft">Map failed to load</span>';
          return;
        }

        mapFrame.hidden = false;
        mapEmpty.hidden = true;
        mapStats.innerHTML = `
          <span class="pill soft">${escapeHtml(String(geoLeads.length))} markers</span>
          <span class="pill soft">Click a marker to inspect the lead</span>
        `;

        clearMapMarkers();
        const bounds = new window.mapboxgl.LngLatBounds();
        geoLeads.forEach((lead) => {
          const position = [Number(lead.longitude), Number(lead.latitude)];
          const popup = new window.mapboxgl.Popup({ offset: 18, closeButton: false, closeOnClick: false }).setHTML(`
            <div style="min-width: 180px; color: #111214;">
              <strong>${escapeHtml(lead.name || 'Lead')}</strong><br>
              <span>${escapeHtml(extractLocationLine(lead) || lead.websiteDomain || '')}</span>
            </div>
          `);
          const marker = new window.mapboxgl.Marker({ color: '#2f8f7b' })
            .setLngLat(position)
            .setPopup(popup)
            .addTo(state.map);
          marker.getElement().addEventListener('click', () => {
            popup.addTo(state.map);
            openLeadModal(lead.id);
          });
          state.mapMarkers.push(marker);
          bounds.extend(position);
        });

        window.setTimeout(() => {
          if (window.mapboxgl && state.map) {
            state.map.resize();
          }
          if (geoLeads.length === 1) {
            state.map.easeTo({ center: bounds.getCenter(), zoom: 13, duration: 700 });
          } else {
            state.map.fitBounds(bounds, { padding: 48, duration: 700, maxZoom: 14 });
          }
        }, 60);
      }

      function renderRaw(payload) {
        if (!resultsCode) return;
        resultsCode.textContent = JSON.stringify(payload.result, null, 2);
        resultsJson.hidden = false;
        resultsJsonEmpty.hidden = true;
      }

      async function copyVisibleResults() {
        if (!state.visibleResults.length) return;
        const ok = await copyTextToClipboard(JSON.stringify(state.visibleResults.map((item) => item.data), null, 2), 'Copy visible results');
        if (ok) {
          resultsMeta.textContent = `Copied ${state.visibleResults.length} visible results to the clipboard.`;
        }
      }

      function exportVisibleJsonResults() {
        if (!state.visibleResults.length || !state.searchPayload) return;
        const safeType = String(state.searchPayload.searchType || 'results').replace(/[^a-z0-9_-]/gi, '-').toLowerCase();
        downloadJsonFile(`leadsmcp-${safeType}-visible-results.json`, state.visibleResults.map((item) => item.data));
        resultsMeta.textContent = `Exported ${state.visibleResults.length} visible results as JSON.`;
      }

      function csvSafe(value) {
        const text = compactValue(value);
        if (!text) return '';
        return `"${String(text).replace(/"/g, '""')}"`;
      }

      function flattenCsvRow(row) {
        const output = {};
        Object.entries(row || {}).forEach(([key, value]) => {
          if (key === 'raw') return;
          if (Array.isArray(value)) {
            output[key] = value.map((item) => compactValue(item)).filter(Boolean).join(' | ');
            return;
          }
          if (value && typeof value === 'object') {
            output[key] = JSON.stringify(value);
            return;
          }
          output[key] = value;
        });
        return output;
      }

      function exportVisibleCsvResults() {
        if (!state.visibleResults.length || !state.searchPayload) return;
        const rows = state.visibleResults.map((item) => flattenCsvRow(item.data || {}));
        const keys = Array.from(new Set(rows.flatMap((row) => Object.keys(row).filter((key) => key !== 'raw'))));
        const header = keys.join(',');
        const lines = rows.map((row) => keys.map((key) => csvSafe(row[key])).join(','));
        const csv = [header, ...lines].join('\\n');
        const safeType = String(state.searchPayload.searchType || 'results').replace(/[^a-z0-9_-]/gi, '-').toLowerCase();
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `leadsmcp-${safeType}-visible-results.csv`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
        resultsMeta.textContent = `Exported ${state.visibleResults.length} visible results as CSV.`;
      }

      async function copyResultCard(index) {
        const item = state.visibleResults[index];
        if (!item) return;
        const ok = await copyTextToClipboard(JSON.stringify(item.data, null, 2), 'Copy result card');
        if (ok) {
          resultsMeta.textContent = `Copied ${item.label} card JSON to the clipboard.`;
        }
      }

      function exportResultCard(index) {
        const item = state.visibleResults[index];
        if (!item) return;
        const safeType = String(item.type || 'result').replace(/[^a-z0-9_-]/gi, '-').toLowerCase();
        downloadJsonFile(`leadsmcp-${safeType}-card-${index + 1}.json`, item.data);
        resultsMeta.textContent = `Exported ${item.label} card ${index + 1} as JSON.`;
      }

      function renderResults(payload) {
        state.searchPayload = payload;
        state.activeResultFilter = 'all';
        renderResultsFamily(payload);
        if (resultsLaunchMeta) {
          resultsLaunchMeta.textContent = `${payload.searchLabel} returned ${formatMetricValue(metricsForPayload(payload)[0] ? metricsForPayload(payload)[0].value : 0)} ${searchTypePrimaryLabel(payload.searchType).toLowerCase()} and ${payload.geoLeadCount || 0} mappable results. Open the fullscreen review workspace to inspect them.`;
        }
        renderSummary(payload);
        renderLeadCards(payload);
        renderRaw(payload);
        [openResultsButton, openResultsLaunchButton, openResultsMapButton].forEach((button) => {
          if (button) button.disabled = false;
        });
      }

      function activateTab(tabName) {
        state.activeTab = tabName;
        tabButtons.forEach((button) => {
          const isActive = button.dataset.tabButton === tabName;
          button.classList.toggle('is-active', isActive);
          button.setAttribute('aria-selected', isActive ? 'true' : 'false');
        });
        tabPanels.forEach((panel) => {
          panel.classList.toggle('is-active', panel.dataset.tabPanel === tabName);
        });
        if (tabName === 'map' && state.searchPayload) {
          window.requestAnimationFrame(() => {
            void renderMap(state.searchPayload);
          });
        }
      }

      function detailEntriesForLead(lead) {
        const fields = [
          ['Search Type', lead.searchType],
          ['Address', lead.address],
          ['City', lead.city],
          ['State / Region', lead.state],
          ['Country', lead.country],
          ['Postal Code', lead.postalCode],
          ['Phone', lead.phone],
          ['Email', lead.email],
          ['Website', lead.website],
          ['Website Domain', lead.websiteDomain],
          ['Logo URL', lead.logoUrl],
          ['Category', lead.category],
          ['Rating', lead.rating],
          ['Review Count', lead.reviewCount],
          ['Latitude', lead.latitude],
          ['Longitude', lead.longitude],
          ['Source URL', lead.sourceUrl],
        ].filter(([, value]) => value !== null && value !== undefined && value !== '');

        const raw = lead.raw || {};
        Object.entries(raw).forEach(([key, value]) => {
          const normalizedKey = humanizeKey(key);
          if (fields.some(([label]) => label.toLowerCase() === normalizedKey.toLowerCase())) {
            return;
          }
          const formatted = compactValue(value);
          if (!formatted) return;
          fields.push([normalizedKey, formatted]);
        });

        return fields;
      }

      function resetScrapeSection(message) {
        scrapeStatus.textContent = message;
        scrapeSummary.innerHTML = '';
        scrapeGrid.hidden = true;
        scrapeGrid.innerHTML = '';
        scrapeEmpty.hidden = false;
        scrapeRaw.hidden = true;
        scrapeRawCode.textContent = '';
      }

      function renderScrapePayload(payload) {
        const leads = Array.isArray(payload.leads) ? payload.leads : [];
        const summaryItems = [
          { label: 'Lead cards', value: payload.leadCount || 0 },
          { label: 'Runtime', value: `${payload.elapsedMs || 0} ms` },
        ];
        if (payload.result && Array.isArray(payload.result.requested_domains)) {
          summaryItems.push({ label: 'Domains', value: payload.result.requested_domains.length });
        }
        if (payload.result && typeof payload.result.failed_domains === 'number') {
          summaryItems.push({ label: 'Failures', value: payload.result.failed_domains });
        }
        scrapeSummary.innerHTML = summaryItems.map((item) => `<span class="pill soft">${escapeHtml(item.label)}: ${escapeHtml(formatMetricValue(item.value))}</span>`).join('');

        if (!leads.length) {
          scrapeGrid.hidden = true;
          scrapeEmpty.hidden = false;
          scrapeEmpty.textContent = 'The website scrape completed, but there were no structured contacts or leads to display.';
        } else {
          scrapeEmpty.hidden = true;
          scrapeGrid.hidden = false;
          scrapeGrid.innerHTML = leads.map((lead) => `
            <article class="scrape-card">
              <h4>${escapeHtml(lead.name || lead.websiteDomain || 'Website lead')}</h4>
              <div class="pill-row" style="margin-bottom: var(--space-3);">
                ${lead.email ? `<span class="pill soft">${escapeHtml(lead.email)}</span>` : ''}
                ${lead.phone ? `<span class="pill soft">${escapeHtml(lead.phone)}</span>` : ''}
                ${lead.websiteDomain ? `<span class="pill soft">${escapeHtml(lead.websiteDomain)}</span>` : ''}
              </div>
              ${lead.description ? `<p class="muted">${escapeHtml(lead.description)}</p>` : '<p class="muted">Structured contact details returned from the website scrape.</p>'}
            </article>
          `).join('');
        }

        scrapeRaw.hidden = false;
        scrapeRawCode.textContent = JSON.stringify(payload.result, null, 2);
      }

      function openLeadModal(leadId) {
        const lead = getLeadById(leadId);
        if (!lead) return;
        state.selectedLeadId = leadId;
        detailTitle.textContent = lead.name || 'Lead detail';
        detailSubtitle.textContent = extractLocationLine(lead) || lead.websiteDomain || 'Business details from the selected lead.';
        detailPills.innerHTML = [
          lead.category ? `<span class="pill">${escapeHtml(lead.category)}</span>` : '',
          lead.websiteDomain ? `<span class="pill soft">${escapeHtml(lead.websiteDomain)}</span>` : '',
          lead.rating ? `<span class="pill soft">Rating ${escapeHtml(formatMetricValue(lead.rating))}</span>` : '',
          lead.hasCoordinates ? '<span class="pill soft">Mapped</span>' : '',
        ].filter(Boolean).join('');
        detailGrid.innerHTML = detailEntriesForLead(lead).map(([label, value]) => `
          <div class="detail-item">
            <div class="detail-key">${escapeHtml(label)}</div>
            <div class="detail-value">${escapeHtml(compactValue(value))}</div>
          </div>
        `).join('');

        const website = lead.website || '';
        if (website) {
          openWebsiteLink.hidden = false;
          openWebsiteLink.href = website;
        } else {
          openWebsiteLink.hidden = true;
          openWebsiteLink.removeAttribute('href');
        }

        const domain = domainFromLead(lead);
        scrapeButton.hidden = !domain;
        scrapeButton.disabled = false;
        scrapeButton.textContent = domain ? `Scrape ${domain}` : 'Scrape Website';
        resetScrapeSection(domain ? 'Click the scrape button to inspect the selected website for emails, phones, and contact leads.' : 'This lead does not include a website to scrape.');
        detailBackdrop.classList.add('is-open');
        syncBodyScrollLock();
      }

      function closeLeadModal() {
        detailBackdrop.classList.remove('is-open');
        syncBodyScrollLock();
      }

      async function scrapeSelectedWebsite() {
        const lead = getLeadById(state.selectedLeadId);
        const domain = domainFromLead(lead);
        if (!lead || !domain) {
          resetScrapeSection('This lead does not include a scrapeable website.');
          return;
        }

        scrapeButton.disabled = true;
        scrapeButton.textContent = `Scraping ${domain}...`;
        scrapeStatus.textContent = `Running website scrape for ${domain}...`;
        scrapeSummary.innerHTML = '<span class="pill soft">Website scrape in progress</span>';
        scrapeGrid.hidden = true;
        scrapeEmpty.hidden = false;
        scrapeEmpty.textContent = 'Pulling structured contacts from the selected website...';

        try {
          const response = await fetch(SEARCH_ENDPOINT, {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({
              encryptedData: state.encryptedData,
              searchType: 'emails_and_contacts',
              params: {
                domains: domain,
                contacts_per_company: 3,
                emails_per_contact: 2
              }
            })
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) {
            throw new Error(payload.message || 'Website scrape failed.');
          }
          scrapeStatus.textContent = `Website scrape completed for ${domain}.`;
          renderScrapePayload(payload);
        } catch (error) {
          scrapeStatus.textContent = 'Website scrape failed.';
          scrapeSummary.innerHTML = '<span class="pill soft">No website data returned</span>';
          scrapeGrid.hidden = true;
          scrapeEmpty.hidden = false;
          scrapeEmpty.textContent = error.message || 'Website scrape failed.';
          scrapeRaw.hidden = true;
        } finally {
          scrapeButton.disabled = false;
          scrapeButton.textContent = `Scrape ${domain}`;
        }
      }

      async function requestEncryptedUserData() {
        if (window === window.parent) {
          throw new Error('Open this page inside your GoHighLevel custom page iframe.');
        }

        return await new Promise((resolve, reject) => {
          const timeout = window.setTimeout(() => {
            window.removeEventListener('message', onMessage);
            reject(new Error('Timed out waiting for user context from HighLevel.'));
          }, 8000);

          function onMessage(event) {
            const data = event.data || {};
            if (data.message !== 'REQUEST_USER_DATA_RESPONSE' || !data.payload) {
              return;
            }
            window.clearTimeout(timeout);
            window.removeEventListener('message', onMessage);
            resolve(data.payload);
          }

          window.addEventListener('message', onMessage);
          window.parent.postMessage({ message: 'REQUEST_USER_DATA' }, '*');
        });
      }

      async function loadContext() {
        try {
          setContextNode('status', 'Requesting user context from HighLevel...', 'status-warn');
          const encryptedData = await requestEncryptedUserData();
          state.encryptedData = encryptedData;

          const response = await fetch(CONTEXT_ENDPOINT, {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ encryptedData })
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) {
            throw new Error(payload.message || 'Unable to load user context.');
          }
          state.context = payload.context;
          renderContext(payload.context);
        } catch (error) {
          renderContextError(error.message || 'Unable to load user context.');
        }
      }

      async function runSearch(event) {
        event.preventDefault();
        try {
          if (!state.encryptedData) {
            throw new Error('HighLevel user context is not loaded yet.');
          }

          runButton.disabled = true;
          runButton.textContent = 'Running search...';
          resultsMeta.textContent = 'Running search...';

          const params = collectParams();
          const response = await fetch(SEARCH_ENDPOINT, {
            method: 'POST',
            headers: { 'content-type': 'application/json' },
            body: JSON.stringify({
              encryptedData: state.encryptedData,
              searchType: state.currentSearchType,
              params
            })
          });
          const payload = await response.json();
          if (!response.ok || !payload.ok) {
            throw new Error(payload.message || 'Search failed.');
          }
          renderResults(payload);
          saveCurrentSearch(false);
          openResultsWorkspace('leads');
        } catch (error) {
          setSearchIdleState();
          resultsEmpty.textContent = error.message || 'Search failed.';
          resultsMeta.textContent = 'Search failed.';
        } finally {
          runButton.disabled = !state.encryptedData;
          runButton.textContent = state.encryptedData ? 'Run Search' : 'Load GHL context first';
        }
      }

      renderSearchTypeOptions();
      renderFields();
      setSearchIdleState();
      renderSavedSearches();
      renderAiThread();
      setAiStatus('Waiting for HighLevel context...', 'LLM loading…');
      setAiComposerEnabled(false);

      searchTypeSelect.addEventListener('change', function (event) {
        state.currentSearchType = event.target.value;
        renderFields();
      });

      tabButtons.forEach((button) => {
        button.addEventListener('click', function () {
          activateTab(button.dataset.tabButton);
        });
      });

      form.addEventListener('submit', runSearch);
      if (aiForm) {
        aiForm.addEventListener('submit', submitAiPrompt);
      }
      if (aiClearButton) {
        aiClearButton.addEventListener('click', clearAiConversation);
      }
      if (openAiWorkspaceButton) {
        openAiWorkspaceButton.addEventListener('click', function () {
          openAiWorkspace(false);
        });
      }
      if (openAiWorkspaceFocusButton) {
        openAiWorkspaceFocusButton.addEventListener('click', function () {
          openAiWorkspace(true);
        });
      }
      if (aiCloseButton) {
        aiCloseButton.addEventListener('click', closeAiWorkspace);
      }
      if (saveSearchButton) {
        saveSearchButton.addEventListener('click', function () {
          saveCurrentSearch(true);
        });
      }
      resetButton.addEventListener('click', function () {
        renderFields();
        setSearchIdleState();
        closeResultsWorkspace();
      });

      [openResultsButton, openResultsLaunchButton].forEach((button) => {
        if (!button) return;
        button.addEventListener('click', function () {
          openResultsWorkspace('leads');
        });
      });

      if (openResultsMapButton) {
        openResultsMapButton.addEventListener('click', function () {
          openResultsWorkspace('map');
        });
      }

      if (copyVisibleButton) {
        copyVisibleButton.addEventListener('click', function () {
          void copyVisibleResults();
        });
      }

      if (exportJsonVisibleButton) {
        exportJsonVisibleButton.addEventListener('click', exportVisibleJsonResults);
      }

      if (exportCsvVisibleButton) {
        exportCsvVisibleButton.addEventListener('click', exportVisibleCsvResults);
      }

      if (savedSearchesList) {
        savedSearchesList.addEventListener('click', function (event) {
          const loadButton = event.target.closest('[data-saved-search-load]');
          if (loadButton) {
            loadSavedSearch(Number(loadButton.dataset.savedSearchLoad));
            return;
          }
          const removeButton = event.target.closest('[data-saved-search-remove]');
          if (removeButton) {
            removeSavedSearch(Number(removeButton.dataset.savedSearchRemove));
          }
        });
      }

      if (resultsFilters) {
        resultsFilters.addEventListener('click', function (event) {
          const button = event.target.closest('[data-result-filter]');
          if (!button || !state.searchPayload) return;
          state.activeResultFilter = button.dataset.resultFilter || 'all';
          renderLeadCards(state.searchPayload);
        });
      }

      leadGrid.addEventListener('click', function (event) {
        const copyButton = event.target.closest('[data-card-copy]');
        if (copyButton) {
          event.preventDefault();
          event.stopPropagation();
          void copyResultCard(Number(copyButton.dataset.cardCopy));
          return;
        }
        const exportButton = event.target.closest('[data-card-export]');
        if (exportButton) {
          event.preventDefault();
          event.stopPropagation();
          exportResultCard(Number(exportButton.dataset.cardExport));
          return;
        }
        const pushButton = event.target.closest('[data-lead-push]');
        if (pushButton) {
          event.preventDefault();
          event.stopPropagation();
          pushLeadToLocation(pushButton.dataset.leadPush);
          return;
        }
        const button = event.target.closest('[data-lead-open]');
        if (!button) return;
        event.preventDefault();
        openLeadModal(button.dataset.leadOpen);
      });
      leadGrid.addEventListener('error', function (event) {
        const image = event.target;
        if (!(image instanceof HTMLImageElement) || !image.classList.contains('lead-logo-image')) {
          return;
        }
        const container = image.closest('[data-lead-logo]');
        if (container) {
          container.classList.remove('has-image');
          container.classList.add('is-fallback');
        }
        image.remove();
      }, true);

      refreshContextButton.addEventListener('click', loadContext);
      if (resultsCloseButton) {
        resultsCloseButton.addEventListener('click', closeResultsWorkspace);
      }
      if (resultsBackdrop) {
        resultsBackdrop.addEventListener('click', function (event) {
          if (event.target === resultsBackdrop) {
            closeResultsWorkspace();
          }
        });
      }
      if (aiBackdrop) {
        aiBackdrop.addEventListener('click', function (event) {
          if (event.target === aiBackdrop) {
            closeAiWorkspace();
          }
        });
      }
      detailClose.addEventListener('click', closeLeadModal);
      detailBackdrop.addEventListener('click', function (event) {
        if (event.target === detailBackdrop) {
          closeLeadModal();
        }
      });
      document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape') {
          if (detailBackdrop.classList.contains('is-open')) {
            closeLeadModal();
            return;
          }
          if (aiBackdrop && aiBackdrop.classList.contains('is-open')) {
            closeAiWorkspace();
            return;
          }
          if (resultsBackdrop && resultsBackdrop.classList.contains('is-open')) {
            closeResultsWorkspace();
          }
        }
      });
      scrapeButton.addEventListener('click', scrapeSelectedWebsite);

      loadContext();
    })();
  </script>

  __THEME_SCRIPT__
</body>
</html>
"""

    return (
        template
        .replace("__CONTEXT_ENDPOINT__", _safe(context_endpoint))
        .replace("__SEARCH_ENDPOINT__", _safe(search_endpoint))
        .replace("__AI_ENDPOINT__", _safe(ai_endpoint))
        .replace("__SEARCH_PAGE__", _safe(search_page))
        .replace("__SUPPORT_PAGE__", _safe(support_page))
        .replace("__CONTACT_PAGE__", _safe(contact_page))
        .replace("__INSTALL_SUCCESS_PAGE__", _safe(install_success_page))
        .replace("__GITHUB_URL__", _safe(github_url))
        .replace("__SEARCH_CONFIG__", search_config_json)
        .replace("__MAPBOX_PUBLIC_TOKEN__", _safe(mapbox_public_token))
        .replace("__MAPBOX_STYLE_URL__", _safe(mapbox_style_url))
        .replace("__MAPBOX_JS_URL__", _safe(mapbox_js_url))
        .replace("__MAPBOX_CSS_URL__", _safe(mapbox_css_url))
        .replace("__THEME_SCRIPT__", _theme_script())
    )
