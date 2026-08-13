#!/usr/bin/env python3
"""Build the four operator landing pages from a shared, reviewable template."""

from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

OPERATORS = {
    "trafalgar-tours.html": {
        "name": "Trafalgar Tours",
        "short": "Trafalgar",
        "mark": "operator-trafalgar.svg",
        "image": "trafalgar-guests.webp",
        "position": "center",
        "eyebrow": "Iconic sights · local stories · effortless days",
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
        "name": "Globus Journeys",
        "short": "Globus",
        "mark": "operator-globus.svg",
        "image": "globus-alps.webp",
        "position": "center",
        "eyebrow": "Classic touring · thoughtful choices · more included",
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
        "name": "Cosmos Tours",
        "short": "Cosmos",
        "mark": "operator-cosmos.svg",
        "image": "cosmos-highlands.webp",
        "position": "center",
        "eyebrow": "Brilliant value · famous sights · time your way",
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
        "name": "Insight Vacations",
        "short": "Insight",
        "mark": "operator-insight.svg",
        "image": "insight-lake-como.webp",
        "position": "center",
        "eyebrow": "Premium touring · meaningful moments · elevated comfort",
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


def list_items(items: list[str]) -> str:
    return "\n".join(f"<li>{escape(item)}</li>" for item in items)


def page(data: dict) -> str:
    tags = "".join(f'<span class="tag">{escape(tag)}</span>' for tag in data["tags"])
    cards = "\n".join(
        f'<article class="feature-card"><h3>{escape(title)}</h3><p>{escape(copy)}</p></article>'
        for title, copy in data["cards"]
    )
    operator_query = data["name"].replace(" ", "%20")
    return f'''<!doctype html>
<html lang="en-CA">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(data["name"])} | Discount Coach Tours</title>
  <meta name="description" content="Compare {escape(data["name"])} guided coach tours with help from a Canadian travel specialist.">
  <meta name="robots" content="noindex,nofollow"><meta name="theme-color" content="#2b123c">
  <link rel="icon" href="/assets/images/dct-logo-mark.svg?v=20260813b" type="image/svg+xml">
  <link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;650;700;800&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/assets/css/site.css?v=20260813a">
  <script>window.dataLayer=window.dataLayer||[];</script>
</head>
<body>
  <a class="skip-link" href="#main">Skip to main content</a>
  <div class="preview-bar"><p>Private review site — tour details and tracking are awaiting client approval</p></div>
  <header class="site-header"><div class="shell nav">
    <a class="brand" href="/" aria-label="Discount Coach Tours home"><img src="/assets/images/dct-logo-horizontal.svg?v=20260813b" alt="Discount Coach Tours" width="1800" height="520"></a>
    <nav aria-label="Primary navigation"><ul class="nav-links" data-nav-links><li><a href="/#operators">Tour operators</a></li><li><a href="/#why-coach">Why coach touring</a></li><li><a href="/#how-it-works">How it works</a></li><li><a href="/#enquire">Contact</a></li><li><a class="button button-accent" href="/?operator={operator_query}#enquire">Plan my tour</a></li></ul></nav>
    <div class="nav-actions"><button class="icon-button" type="button" data-theme-toggle aria-label="Use dark theme"><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M20 15.3A8.5 8.5 0 0 1 8.7 4a8.5 8.5 0 1 0 11.3 11.3Z"/></svg></button><a class="button" href="tel:+18779778586">1 877 977 8586</a><button class="icon-button menu-button" type="button" data-menu-toggle aria-expanded="false" aria-label="Open menu"><svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M4 7h16M4 12h16M4 17h16"/></svg></button></div>
  </div></header>
  <main id="main">
    <section class="operator-hero" style="--operator-image:url('/assets/images/{data["image"]}')"><div class="shell operator-hero-inner"><div class="operator-hero-copy">
      <p class="breadcrumbs"><a href="/">Home</a> / {escape(data["name"])}</p>
      <div class="operator-mark"><img src="/assets/images/{data["mark"]}" alt="{escape(data["name"])}" width="560" height="160"></div>
      <p class="eyebrow">{escape(data["eyebrow"])}</p><h1>{escape(data["headline"])}</h1><p class="lede">{escape(data["intro"])}</p>
      <div class="tag-row">{tags}</div><div class="cluster"><a class="button button-accent button-lg" href="/?operator={operator_query}#enquire">Ask about {escape(data["short"])} tours</a><a class="button button-light button-lg" href="tel:+18779778586">Call 1 877 977 8586</a></div>
    </div></div></section>

    <section class="section"><div class="shell grid-2"><div><p class="eyebrow">Is {escape(data["short"])} right for you?</p><h2 style="margin-top:.8rem">A guided journey with its own point of view</h2><p class="lede" style="margin-top:1.2rem">{escape(data["summary"])}</p><p class="small" style="margin-top:1rem">{escape(data["fact"])}</p></div><div class="media-frame"><img src="/assets/images/{data["image"]}" alt="Scenic {escape(data["short"])} style coach touring" width="1200" height="900"></div></div></section>

    <section class="section section-soft"><div class="shell"><div class="section-heading center"><p class="eyebrow">Best for</p><h2>Travellers who want the trip to feel easy</h2></div><div class="grid-3">{cards}</div></div></section>

    <section class="section"><div class="shell grid-2"><div><p class="eyebrow">Where could you go?</p><h2 style="margin-top:.8rem">A world of coach touring</h2><p class="lede" style="margin-top:1.2rem">Availability changes by season. We’ll compare current itineraries and departure dates around the destination you have in mind.</p><div class="tag-row" style="margin-top:1.5rem">{"".join(f'<span class="tag">{escape(region)}</span>' for region in data["regions"])}</div></div><div class="info-card"><h3>What is usually included</h3><ul class="check-list" style="margin-top:1.2rem">{list_items(data["included"])}</ul><p class="small" style="margin-top:1.2rem">Exact inclusions vary by itinerary and departure. Your specialist will confirm the current operator terms before booking.</p></div></div></section>

    <section class="section-tight"><div class="shell cta-band"><div><p class="eyebrow" style="color:#f2bd64">Let’s find your departure</p><h2 style="margin-top:.6rem">Want us to compare current {escape(data["short"])} options?</h2><p style="margin-top:.8rem;color:rgb(255 250 241 / 78%)">Share your destination, timing and budget. A specialist can help narrow the tours that fit.</p></div><a class="button button-accent button-lg" href="/?operator={operator_query}#enquire">Start my enquiry</a></div></section>
  </main>
  <footer class="site-footer"><div class="shell"><div class="footer-grid"><div><a class="brand" href="/"><img src="/assets/images/dct-logo-horizontal.svg?v=20260813b" alt="Discount Coach Tours" width="1800" height="520"></a><p class="small" style="margin-top:1rem;max-width:24rem">Independent help comparing guided coach holidays from trusted tour operators.</p></div><div><h3>Tour operators</h3><ul class="footer-links"><li><a href="/trafalgar-tours.html">Trafalgar Tours</a></li><li><a href="/globus-journeys.html">Globus Journeys</a></li><li><a href="/cosmos-tours.html">Cosmos Tours</a></li><li><a href="/insight-vacations.html">Insight Vacations</a></li></ul></div><div><h3>Plan</h3><ul class="footer-links"><li><a href="/#why-coach">Why coach touring</a></li><li><a href="/#enquire">Enquire now</a></li><li><a href="/privacy.html">Privacy</a></li></ul></div><div><h3>Contact</h3><ul class="footer-links"><li><a href="tel:+18779778586">1 (877) 977-8586</a></li><li><a href="mailto:sales@discountcoachtours.ca">sales@discountcoachtours.ca</a></li><li>1425 Osprey Drive, Unit 203<br>Ancaster, ON L9G 4V5</li></ul></div></div><div class="footer-bottom"><p>© <span data-current-year></span> Discount Coach Tours. TICO registration #50020475.</p><p>Tour operator names and marks belong to their respective owners.</p></div></div></footer>
  <script src="/assets/js/site.js?v=20260813a" defer></script>
</body></html>'''


for filename, operator in OPERATORS.items():
    (ROOT / filename).write_text(page(operator), encoding="utf-8")

print(f"Built {len(OPERATORS)} operator pages.")
