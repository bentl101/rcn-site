#!/usr/bin/env python3
"""Build four operator-specific PPC landing pages from one shared template."""

from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

OPERATORS = {
    "trafalgar-tours.html": {
        "name": "Trafalgar Tours", "short": "Trafalgar", "slug": "trafalgar", "mark": "operator-trafalgar.svg", "mark_width": 146, "mark_height": 40,
        "image": "trafalgar-guests.webp", "eyebrow": "Iconic sights · local stories · effortless days",
        "headline": "Tour differently with Trafalgar",
        "intro": "See the places you came for, then go deeper with local experiences, knowledgeable tour directors and the details already taken care of.",
        "summary": "Trafalgar is a strong match for travellers who want a social, well-orchestrated journey that blends world-famous highlights with stories and encounters that add local character.",
        "tags": ["75+ years of touring", "Tour directors", "Local experiences"],
        "cards": [
            ("First-time guided travellers", "A clear day-by-day structure and an experienced team make it easy to settle into touring."),
            ("Big sights, richer context", "Visit the icons while local specialists help bring history, food and culture to life."),
            ("Travellers who enjoy company", "Share the journey with a group while still finding moments to explore independently."),
        ],
        "regions": ["Britain & Ireland", "Italy & the Mediterranean", "Central Europe", "USA & Canada", "Australia & New Zealand", "Worldwide journeys"],
        "included": ["A planned touring itinerary", "Selected accommodations and breakfasts", "Coach transportation between included stops", "A travel director and local specialists", "Included sightseeing and selected experiences"],
        "fact": "Trafalgar describes more than 75 years of guided travel experience, combining must-see places with local experiences.",
    },
    "globus-journeys.html": {
        "name": "Globus Journeys", "short": "Globus", "slug": "globus", "mark": "operator-globus.jpg", "mark_width": 1396, "mark_height": 228,
        "image": "globus-alps.webp", "eyebrow": "Classic touring · thoughtful choices · more included",
        "headline": "Make big trips feel beautifully easy",
        "intro": "Globus brings hotels, transportation, must-see experiences and expert guidance together — with selected choices that let you personalize the day.",
        "summary": "Globus suits travellers who appreciate a polished classic tour, want many of the essentials arranged and like having choices between selected included experiences.",
        "tags": ["Nearly 100 years", "Choice excursions", "Classic & small-group styles"],
        "cards": [
            ("The confident planner", "Know the core trip is arranged while keeping room for selected personal choices."),
            ("Landmark collectors", "Cover the places you have always wanted to see without planning every transfer yourself."),
            ("Comfort-minded explorers", "Enjoy well-paced transportation, selected hotels and experienced guidance throughout."),
        ],
        "regions": ["Europe", "North America", "South & Central America", "Africa", "Asia", "Australia & New Zealand"],
        "included": ["Selected hotels and transportation", "Guided sightseeing with local experts", "Many meals and experiences noted by itinerary", "Tour director support", "Choice options on selected itineraries"],
        "fact": "Globus highlights nearly a century of touring and offers classic, small-group and off-season Escapes styles.",
    },
    "cosmos-tours.html": {
        "name": "Cosmos Tours", "short": "Cosmos", "slug": "cosmos", "mark": "operator-cosmos.jpg", "mark_width": 1600, "mark_height": 228,
        "image": "cosmos-highlands.webp", "eyebrow": "Brilliant value · famous sights · time your way",
        "headline": "Go farther without stretching the budget",
        "intro": "Cosmos keeps guided touring comfortable and attainable, pairing the essential sights with practical hotels, smooth transportation and time to explore.",
        "summary": "Cosmos is designed for value-conscious travellers who want the confidence of an escorted itinerary, but are happy with practical choices and free time for their own discoveries.",
        "tags": ["60+ years", "Value-focused touring", "Guided time + free time"],
        "cards": [
            ("Smart-value travellers", "Put more of the budget toward seeing the destination with practical inclusions and a clear itinerary."),
            ("Independent spirits", "Enjoy organized transport and key sightseeing, plus space to wander or choose optional activities."),
            ("First big international trip", "Experienced tour support makes unfamiliar places feel approachable from the first day."),
        ],
        "regions": ["Britain & Ireland", "Continental Europe", "USA & Canada", "South America", "Africa", "Asia & the Pacific"],
        "included": ["First-class motorcoach transportation on most itineraries", "Selected accommodations", "Guided sightseeing noted by itinerary", "Tour director support", "Free time and optional excursion opportunities"],
        "fact": "Cosmos presents more than 60 years of affordable touring, combining guided sightseeing with free time and optional activities.",
    },
    "insight-vacations.html": {
        "name": "Insight Vacations", "short": "Insight", "slug": "insight", "mark": "operator-insight.svg", "mark_width": 5845, "mark_height": 850,
        "image": "insight-lake-como.webp", "eyebrow": "Premium touring · meaningful moments · elevated comfort",
        "headline": "Travel in style, without missing the story",
        "intro": "Insight Vacations combines carefully chosen stays, immersive experiences and comfortable touring for travellers who value depth as much as ease.",
        "summary": "Insight is a natural fit when premium details matter: distinctive accommodations, a little more room on the road, carefully chosen dining and experiences with a strong sense of place.",
        "tags": ["Premium guided tours", "130+ journeys", "Five continents"],
        "cards": [
            ("Comfort connoisseurs", "Choose a more elevated touring style where hotels, dining and onboard comfort are part of the experience."),
            ("Culture-led travellers", "Go beyond an overview through local experts, regional food and thoughtfully selected experiences."),
            ("Celebration trips", "A strong option for a milestone journey where the details should feel special from beginning to end."),
        ],
        "regions": ["Italy & the Mediterranean", "Britain & Ireland", "Central & Northern Europe", "USA & Canada", "Asia", "Worldwide journeys"],
        "included": ["Premium guided transportation", "Selected hotels in well-chosen locations", "Regional dining experiences noted by itinerary", "Travel director and local expertise", "Curated sightseeing and experiences"],
        "fact": "Insight Vacations currently presents more than 130 premium guided tours across five continents and traces its touring heritage to 1978.",
    },
}


def header_brand() -> str:
    return '''<a class="brand header-brand" href="/" aria-label="Discount Coach Tours home">
      <img src="/assets/images/dct-logo-original.png?v=20260816a" alt="Discount Coach Tours" width="2941" height="1558">
    </a>'''


def footer_brand() -> str:
    return '''<a class="brand" href="/" aria-label="Discount Coach Tours home">
      <img src="/assets/images/dct-logo-original.png?v=20260816a" alt="Discount Coach Tours" width="2941" height="1558">
    </a>'''


def operator_navigation(active_slug: str) -> str:
    links = [
        ("Trafalgar", "/trafalgar-tours.html", "trafalgar"),
        ("Globus", "/globus-journeys.html", "globus"),
        ("Insight", "/insight-vacations.html", "insight"),
        ("Cosmos", "/cosmos-tours.html", "cosmos"),
    ]
    items = []
    for label, href, slug in links:
        current = ' aria-current="page"' if slug == active_slug else ""
        items.append(f'<li><a href="{href}"{current}>{label}</a></li>')
    return "".join(items)


def list_items(items: list[str]) -> str:
    return "\n".join(f"<li>{escape(item)}</li>" for item in items)


def enquiry_form(data: dict) -> str:
    name = escape(data["name"])
    short = escape(data["short"])
    source = f'{short} PPC Landing Page'
    return f'''<section class="section section-soft operator-form-section" id="enquire">
      <div class="shell form-wrap">
        <aside class="operator-form-intro">
          <span class="operator-form-kicker">{short} enquiry</span>
          <h2>Get matched with the right {short} tour</h2>
          <p class="lede">Tell us where and when you’d like to travel. We’ll use your details to narrow the current {short} itineraries that fit.</p>
          <div class="locked-operator"><span>Your selected operator</span><strong>{name}</strong></div>
          <ul class="check-list">
            <li>Ask about current dates and availability</li>
            <li>Compare itinerary pace and inclusions</li>
            <li>Discuss flights from your departure city</li>
            <li>No obligation to book</li>
          </ul>
        </aside>

        <div class="form-card operator-form-card">
          <form action="/submit.php" method="post" data-lead-form>
            <div class="form-status" role="status" aria-live="polite"></div>
            <div class="form-section">
              <h3>Your contact details</h3>
              <div class="field-grid two">
                <div class="field"><label for="first_name">First name</label><input id="first_name" name="first_name" autocomplete="given-name" required></div>
                <div class="field"><label for="last_name">Last name</label><input id="last_name" name="last_name" autocomplete="family-name" required></div>
                <div class="field"><label for="email">Email</label><input id="email" name="email" type="email" autocomplete="email" required></div>
                <div class="field"><label for="phone">Phone</label><input id="phone" name="phone" type="tel" autocomplete="tel" inputmode="tel" required></div>
              </div>
            </div>

            <div class="form-section">
              <h3>Your {short} trip</h3>
              <div class="field-grid two">
                <div class="field"><label for="destination">Where would you like to go?</label><input id="destination" name="destination" placeholder="e.g. Italy, Canadian Rockies" required></div>
                <div class="field"><label for="departure_city">Departing from</label><input id="departure_city" name="departure_city" placeholder="e.g. Toronto" required></div>
                <div class="field"><label for="travel_date">Preferred travel month</label><input id="travel_date" name="travel_date" type="month" required></div>
                <div class="field"><label for="duration">Ideal trip length</label><select id="duration" name="duration" required><option value="">Choose one</option><option>Up to 7 days</option><option>8–10 days</option><option>11–14 days</option><option>15–21 days</option><option>22+ days</option><option>Flexible</option></select></div>
                <div class="field"><label for="guests">Travellers</label><select id="guests" name="guests" required><option value="">Choose one</option><option value="1">1 traveller</option><option value="2">2 travellers</option><option value="3">3 travellers</option><option value="4">4 travellers</option><option value="5+">5+ travellers</option></select></div>
                <div class="field"><label for="budget">Budget per person <span class="optional">(CAD)</span></label><select id="budget" name="budget" required><option value="">Choose one</option><option>$2,000–$3,000</option><option>$3,000–$5,000</option><option>$5,000–$8,000</option><option>$8,000–$12,000</option><option>$12,000+</option><option>Not sure yet</option></select></div>
                <div class="field"><label for="pace">Preferred pace</label><select id="pace" name="pace" required><option value="">Choose one</option><option>Relaxed</option><option>Balanced</option><option>Active</option><option>Not sure</option></select></div>
              </div>
              <div class="field"><label for="notes">What matters most? <span class="optional">(optional)</span></label><textarea id="notes" name="notes" placeholder="Must-see places, mobility needs, room preferences or anything else that would help."></textarea></div>
              <fieldset class="radio-set"><legend>How should we contact you?</legend><div class="radio-chip"><input id="contact_either" name="contact_preference" value="Either" type="radio" checked><label for="contact_either">Either</label></div><div class="radio-chip"><input id="contact_phone" name="contact_preference" value="Phone" type="radio"><label for="contact_phone">Phone</label></div><div class="radio-chip"><input id="contact_email" name="contact_preference" value="Email" type="radio"><label for="contact_email">Email</label></div></fieldset>
            </div>

            <div class="form-note"><strong>Review-site note:</strong> this staging form stores test submissions securely. It does not yet email the client or write to their CRM.</div>
            <div class="hp" aria-hidden="true"><label for="website">Leave this field empty</label><input id="website" name="website" tabindex="-1" autocomplete="off"></div>
            <input type="hidden" name="operator" value="{name}">
            <input type="hidden" name="lead_order_id"><input type="hidden" name="time_on_page"><input type="hidden" name="utm_source"><input type="hidden" name="utm_medium"><input type="hidden" name="utm_campaign"><input type="hidden" name="utm_term"><input type="hidden" name="utm_content"><input type="hidden" name="click_id"><input type="hidden" name="click_id_type"><input type="hidden" name="landing_page"><input type="hidden" name="referrer"><input type="hidden" name="source_page" value="{source}">
            <button class="button button-accent button-lg" type="submit">Show me {short} tour options</button>
            <div class="operator-reassurance"><span>Travel Industry Council of Ontario (TICO) registered</span><span>No-obligation enquiry</span><span>Coach tour specialists</span></div>
            <p class="privacy-note">By submitting this form, you agree that Discount Coach Tours may contact you about your enquiry. Your information will be handled according to our <a href="/privacy.html">privacy notice</a>.</p>
          </form>
        </div>
      </div>
    </section>'''


def page(data: dict) -> str:
    name, short = escape(data["name"]), escape(data["short"])
    tags = "".join(f'<span class="tag">{escape(tag)}</span>' for tag in data["tags"])
    cards = "\n".join(f'<article class="feature-card"><h3>{escape(title)}</h3><p>{escape(copy)}</p></article>' for title, copy in data["cards"])
    regions = "".join(f'<span class="tag">{escape(region)}</span>' for region in data["regions"])
    header_logo = header_brand()
    footer_logo = footer_brand()
    operator_nav = operator_navigation(data["slug"])
    return f'''<!doctype html>
<html lang="en-CA">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <title>{name} | Discount Coach Tours</title>
  <meta name="description" content="Compare {name} guided coach tours with help from a coach tour specialist.">
  <meta name="robots" content="noindex,nofollow"><meta name="theme-color" content="#2b123c">
  <meta property="og:title" content="{name} | Discount Coach Tours"><meta property="og:description" content="Find a {short} guided tour that fits your destination, timing and budget."><meta property="og:image" content="https://book.discountcoachtours.ca/assets/images/{data['image']}"><meta name="twitter:card" content="summary_large_image">
  <link rel="icon" href="/assets/images/dct-logo-mark.svg?v=20260814b" type="image/svg+xml">
  <link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;650;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/assets/css/site.css?v=20260816a">
  <script>window.dataLayer=window.dataLayer||[];</script>
</head>
<body class="operator-page operator-page-{data['slug']}">
  <a class="skip-link" href="#main">Skip to main content</a>
  <div class="preview-bar"><p>Private review site — tour details and tracking are awaiting client approval</p></div>
  <header class="site-header"><div class="shell nav">
    {header_logo}
    <nav aria-label="Tour operators"><ul class="nav-links" data-nav-links>{operator_nav}</ul></nav>
    <div class="nav-actions"><a class="button button-accent header-callback" href="#enquire"><svg class="callback-icon" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M6.6 10.8a15.5 15.5 0 0 0 6.6 6.6l2.2-2.2a1 1 0 0 1 1-.2 11 11 0 0 0 3.6.6 1 1 0 0 1 1 1V20a1 1 0 0 1-1 1C10.6 21 3 13.4 3 4a1 1 0 0 1 1-1h3.5a1 1 0 0 1 1 1c0 1.3.2 2.5.6 3.6a1 1 0 0 1-.2 1Z"/></svg><span class="callback-label-long">Request Callback</span><span class="callback-label-short">Callback</span></a><button class="icon-button" type="button" data-theme-toggle aria-label="Use dark theme"><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M20 15.3A8.5 8.5 0 0 1 8.7 4a8.5 8.5 0 1 0 11.3 11.3Z"/></svg></button><button class="icon-button menu-button" type="button" data-menu-toggle aria-expanded="false" aria-label="Open menu"><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 7h16M4 12h16M4 17h16"/></svg></button></div>
  </div></header>
  <main id="main">
    <section class="operator-hero"><div class="shell operator-hero-inner"><div class="operator-hero-copy">
      <p class="breadcrumbs"><a href="/">Home</a> / {name}</p>
      <div class="operator-mark"><img src="/assets/images/{data['mark']}?v=20260814a" alt="{name}" width="{data['mark_width']}" height="{data['mark_height']}"></div>
      <p class="eyebrow">{escape(data['eyebrow'])}</p><h1>{escape(data['headline'])}</h1><p class="lede">{escape(data['intro'])}</p>
      <div class="tag-row">{tags}</div><div class="cluster"><a class="button button-accent button-lg" href="#enquire">Get {short} tour options</a></div>
    </div></div></section>

    <section class="section" id="why-choose"><div class="shell grid-2"><div><p class="eyebrow">Is {short} right for you?</p><h2 class="spaced-heading">A guided journey with its own point of view</h2><p class="lede spaced-copy">{escape(data['summary'])}</p><p class="small spaced-note">{escape(data['fact'])}</p></div><div class="media-frame"><img src="/assets/images/{data['image']}" alt="Scenic {short} style coach touring" width="1200" height="900"></div></div></section>

    <section class="section section-soft"><div class="shell"><div class="section-heading center"><p class="eyebrow">Best for</p><h2>Travellers who want the trip to feel easy</h2></div><div class="grid-3">{cards}</div></div></section>

    <section class="section" id="destinations"><div class="shell grid-2"><div><p class="eyebrow">Where could you go?</p><h2 class="spaced-heading">A world of {short} touring</h2><p class="lede spaced-copy">Availability changes by season. We’ll compare current itineraries and departure dates around the destination you have in mind.</p><div class="tag-row spaced-tags">{regions}</div></div><div class="info-card"><h3>What is usually included</h3><ul class="check-list spaced-list">{list_items(data['included'])}</ul><p class="small spaced-note">Exact inclusions vary by itinerary and departure. Your specialist will confirm the current operator terms before booking.</p></div></div></section>

    {enquiry_form(data)}
  </main>
  <footer class="site-footer"><div class="shell"><div class="footer-grid"><div>{footer_logo}<p class="small footer-intro">Independent help comparing guided coach holidays from trusted tour operators.</p></div><div><h3>Tour operators</h3><ul class="footer-links"><li><a href="/trafalgar-tours.html">Trafalgar Tours</a></li><li><a href="/globus-journeys.html">Globus Journeys</a></li><li><a href="/insight-vacations.html">Insight Vacations</a></li><li><a href="/cosmos-tours.html">Cosmos Tours</a></li></ul></div><div><h3>Plan</h3><ul class="footer-links"><li><a href="#why-choose">Why {short}</a></li><li><a href="#enquire">Enquire now</a></li><li><a href="/privacy.html">Privacy</a></li></ul></div><div><h3>Contact</h3><ul class="footer-links"><li><a href="tel:+18779778586">1 (877) 977-8586</a></li><li><a href="mailto:sales@discountcoachtours.ca">sales@discountcoachtours.ca</a></li><li>1425 Osprey Drive, Unit 203<br>Ancaster, ON L9G 4V5</li></ul></div></div><div class="footer-bottom"><p>© <span data-current-year></span> Discount Coach Tours. TICO registration #50020475.</p><p>Tour operator names and marks belong to their respective owners.</p></div></div></footer>
  <script src="/assets/js/site.js?v=20260814c" defer></script>
</body></html>'''


for filename, operator in OPERATORS.items():
    (ROOT / filename).write_text(page(operator), encoding="utf-8")

print(f"Built {len(OPERATORS)} operator PPC pages with embedded forms.")
