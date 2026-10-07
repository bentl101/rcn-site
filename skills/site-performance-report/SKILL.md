---
name: site-performance-report
description: Audit a public website's loading performance and generate a readable local HTML report with measured findings, real-user context and links to full Lighthouse results.
---
# Site performance report

Produce a readable HTML report as the normal deliverable for requests to grade site performance. Audit the requested URLs or sites; read repository boundaries when selecting pages. Reuse existing dated results when the user wants them explained or repackaged rather than retesting automatically.

## Measurement

Use available performance tools; prefer the installed Web Quality Skills measurement guidance when available. Lighthouse CLI provides HTML/JSON diagnostics; Unlighthouse can provide a site-wide static dashboard. Pin and record the actual tool version. Keep tools and report output outside production deployment sources. Install tools only when needed and within the user's authorization.

For this RCN/DCT repository, `ops/run_site_audits.py` reads the explicit `sites.json` allowlists. `docs/website-grader.md` explains installation and invocation. This runner is specific to those two businesses; do not treat it as an arbitrary-domain crawler. Existing report: `reports/web-quality-2026-10-07/index.html`.

For another site, select bounded public URLs from its sitemap/navigation and use Lighthouse or Unlighthouse. Respect robots rules and use modest concurrency. Navigation-only audits must not submit sales forms or invoke action endpoints. Existing analytics may record synthetic page views; use an established test exclusion when available without changing tracking merely for the audit.

Save each Lighthouse HTML/JSON report. Start with mobile conditions and include desktop where useful. Record cold/warm cache, CPU/network throttling, browser/tool version and run date. Repeat a representative problem page at least three times before relying on a headline metric; report its median and range. A single-run page score remains a diagnostic sample.

Separate these evidence types explicitly:
- Simulated lab LCP/CLS/TBT and actual observed trace timings. A slow simulation is not the server's measured response time.
- CrUX field p75, labelled URL or origin scope, device and aggregation window. Unavailable means unavailable, never passing. A 28-day window cannot validate a deployment made today.
- First-party real visitor metrics, with sample size, dates and test sessions excluded.
- Static source hypotheses without runtime confirmation.

TBT is not INP. Do not claim a full Core Web Vitals pass from navigation-only Lighthouse tests. Do not silently combine different browser versions, locations or test profiles into one comparison.

## HTML deliverable

Save a dated output directory containing `index.html`, full reports and machine-readable results. Generate a compact summary dashboard when the tool does not provide one. Use self-contained styling, a responsive table and relative links to the full reports; site/device filters are useful for multiple URLs. Escape page titles, URLs and findings when inserting them into HTML. Do not embed credentials, private lead data or authentication-bearing URLs.

Include:
- Scope, test conditions and date; clear lab versus field evidence.
- Page/device scores and LCP, CLS and TBT with units; INP only from appropriate interaction/field evidence.
- A short prioritised list of measured issues, user impact, supporting evidence and proposed fixes.
- Intentional exclusions and remaining uncertainty. Noindex on thank-you/404 pages is normally correct. Review canonical alias warnings against equivalent content before calling them defects.
- Verification status: what was measured, manually checked, changed, or remains untested. Automated SEO/accessibility scores do not establish rankings or compliance.

Check report links resolve and inspect the dashboard in a browser, including filters if added. Open the saved HTML in Codex when supported and provide an absolute clickable link in the final response. Keep private reports local unless publishing is requested. Do not install a VPS service, schedule recurring runs, or change production based solely on an audit request.

Prioritise fixes from evidence while preserving commercial messaging, form behaviour, attribution and conversions. Treat optional analytics loading, fonts and images as separate reviewable changes. Explain recommendations plainly rather than presenting every diagnostic as urgent.
