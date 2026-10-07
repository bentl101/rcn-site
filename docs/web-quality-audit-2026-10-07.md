# Website quality audit — 7 October 2026

## Evidence

20 completed Lighthouse 13.5.0 navigation audits: 15 mobile pages, three desktop comparisons, and two additional mobile Avalon repetitions. Chrome 155 on macOS, fresh isolated profiles, simulated mobile slow 4G and 4× CPU; desktop preset. No forms submitted or production changes made. Each HTML/JSON report includes its configuration.

| Real-user field data | LCP | INP | CLS | Status |
| --- | ---: | ---: | ---: | --- |
| RCN origin, mobile, latest 28 days/p75 | 1.7 s | 79 ms | 0 | Passed |
| RCN origin, desktop, latest 28 days/p75 | 1.5 s | 37 ms | 0 | Passed |
| DCT | — | — | — | No public field data available |

Source: [RCN PageSpeed report](https://pagespeed.web.dev/analysis/https-book-rivercruisenetwork-com-avalon-waterways-html/zdzmdmwx6s?form_factor=mobile), [DCT PageSpeed report](https://pagespeed.web.dev/analysis/https-book-discountcoachtours-ca/acajrjkl20?form_factor=mobile). RCN field evidence is origin-level, not Avalon-specific. This historical window cannot verify the deployment made today.

Google’s separate lab run: Avalon mobile performance 77, LCP 3.9 s, TBT 320 ms, CLS 0.015; desktop performance 88 and LCP 0.9 s. DCT homepage mobile performance 85, LCP 3.8 s, TBT 0 ms, CLS 0.025. These are single runs on Google’s Chrome 153 infrastructure.

Local cold-mobile simulations below are materially worse on RCN. Different Chrome versions, network traces, locations and simulation inputs mean the results are not interchangeable. Local observed unthrottled Avalon LCP was 1.334 s in run 1, while its simulated metric was 9.709 s. Neither value establishes real-user p75. Use repeated lab results to diagnose fragile conditions, and real visitor data to determine delivered experience.

## Local lab results

| Site / page | Device / run | Performance | Accessibility | Best practices | SEO | LCP (s) | CLS | TBT (ms) |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| RCN/amawaterways-river-cruise.html | mobile / 1 | 65 | 94 | 100 | 100 | 9.14 | 0.003 | 260 |
| RCN/avalon-waterways.html | mobile / 1 | 66 | 94 | 100 | 100 | 9.71 | 0.014 | 230 |
| RCN/avalon-waterways.html | desktop / 1 | 89 | 94 | 100 | 100 | 2.18 | 0.009 | 0 |
| RCN/avalon-waterways.html | mobile / 2 | 62 | 94 | 100 | 100 | 9.65 | 0.000 | 290 |
| RCN/avalon-waterways.html | mobile / 3 | 62 | 94 | 100 | 100 | 9.98 | 0.000 | 289 |
| RCN/emerald-river-cruise.html | mobile / 1 | 64 | 94 | 100 | 100 | 9.20 | 0.000 | 244 |
| RCN/index.html | mobile / 1 | 54 | 95 | 100 | 100 | 9.76 | 0.000 | 283 |
| RCN/index.html | desktop / 1 | 99 | 95 | 100 | 100 | 0.88 | 0.003 | 0 |
| RCN/scenic-river-cruise.html | mobile / 1 | 61 | 94 | 100 | 100 | 9.46 | 0.000 | 294 |
| RCN/thank-you.html | mobile / 1 | 62 | 91 | 100 | 63 | 10.98 | 0.014 | 286 |
| RCN/viking-river-cruise.html | mobile / 1 | 66 | 94 | 100 | 100 | 9.30 | 0.004 | 240 |
| DCT/404.html | mobile / 1 | 100 | 90 | 100 | 54 | 1.70 | 0.000 | 0 |
| DCT/cosmos-tours.html | mobile / 1 | 79 | 96 | 100 | 100 | 4.03 | 0.000 | 28 |
| DCT/globus-journeys.html | mobile / 1 | 78 | 96 | 100 | 100 | 4.32 | 0.000 | 30 |
| DCT/index.html | mobile / 1 | 81 | 97 | 100 | 92 | 3.96 | 0.000 | 50 |
| DCT/index.html | desktop / 1 | 100 | 97 | 100 | 92 | 0.67 | 0.000 | 0 |
| DCT/insight-vacations.html | mobile / 1 | 74 | 96 | 100 | 100 | 5.76 | 0.008 | 0 |
| DCT/privacy.html | mobile / 1 | 83 | 96 | 100 | 92 | 3.88 | 0.000 | 0 |
| DCT/thank-you.html | mobile / 1 | 99 | 95 | 100 | 58 | 1.67 | 0.009 | 0 |
| DCT/trafalgar-tours.html | mobile / 1 | 81 | 96 | 100 | 100 | 3.98 | 0.000 | 33 |

Avalon mobile (three equivalent local runs): median performance 62; median simulated LCP 9.71 s, range 9.65–9.98 s. Other page figures are single-run diagnostics. All 15 mobile CLS measurements are below 0.1. TBT is not INP.

## Findings and priorities

**Urgency:** No urgent production fault was identified by these navigation audits. They do not establish end-to-end lead delivery or constitute a security assessment. Slow-mobile loading is a high-priority performance investigation, contrast is an accessibility remediation priority, and further image/cache tuning is a lower-priority optimisation. No production fixes were made during this audit.

1. **Loading under slow-mobile conditions:** render-blocking Google Fonts and styles recur on both sites. Avalon’s local insight estimates about 1.96 seconds of potential savings; Google estimates 1.76 seconds. Treat estimates as opportunities, not guaranteed additive gains. Profile a font/critical-CSS change before deployment.
2. **RCN analytics delivery:** one Avalon trace transferred roughly 507 KB for GTM/Ads/GA scripts, 222 KB for PostHog and 28 KB for Clarity. Both recording tools and a PostHog surveys module load. Review optional module delivery and scheduling while retaining attribution, form events and server-side conversion behaviour. These figures establish transfer cost, not that a specific vendor alone caused the LCP delay.
3. **Accessibility:** contrast failures recur: RCN white text on turquoise has an observed 2.28:1 contrast ratio; DCT callback text is about 4.4:1 versus a 4.5:1 requirement. Some RCN pages also lack a main landmark. Plan targeted styling/semantic fixes preserving sales copy and CTA intent. Automated scores do not establish WCAG compliance.
4. **Remaining image opportunities:** Google flags about 27 KB on mobile Avalon and 297 KB on DCT homepage. Some desktop-sized hero/logo resources can be made more responsive. Current hero discovery/preload checks pass. Preserve suitable resolution for pixel density.
5. **SEO interpretation:** enquiry landing pages generally pass automated SEO checks. Thank-you and 404 pages intentionally use noindex; their lower scores are not a reason to index them. The DCT `/index.html` test flags a canonical pointing to `/`; those URLs contain equivalent homepage content, and Google’s `/` test passes. Do not change a correct homepage canonical just to satisfy the alias audit.

## Reuse and next steps

[Reusable grader setup](website-grader.md) documents the installed Codex/Claude skills, runner and VPS options. [Local HTML dashboard](../reports/web-quality-2026-10-07/index.html) links all full reports. No paid API calls were made; no VPS service or recurring schedule was installed.

Recommended next experiment: optimise font/CSS delivery and optional analytics loading on a limited RCN page; rerun three equivalent lab tests, verify attribution/forms and inspect current PostHog visitor metrics. Review any tracking change separately from image/copy/layout changes.
