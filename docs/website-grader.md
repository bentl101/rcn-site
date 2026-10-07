# Reusable website grading

Installed on 7 October 2026: the six [Web Quality Skills](https://github.com/addyosmani/web-quality-skills) in both `~/.codex/skills/` and `~/.claude/skills/`: web-quality-audit, performance, core-web-vitals, accessibility, seo and best-practices. Codex discovers them on the next turn. These are agent instructions, not the test engine. Lighthouse supplies the automated measurements.

## Run the current RCN/DCT audit

Requires Python 3, Node >=22.19 and Chrome/Chromium. Install the pinned test engine into a separate tools directory, not the production website:

```sh
npm install --prefix /tmp/site-grader lighthouse@13.5.0 --no-audit --no-fund
python3 ops/run_site_audits.py --site all --output /tmp/site-audit \
  --lighthouse /tmp/site-grader/node_modules/.bin/lighthouse \
  --desktop --repeat-avalon 3
```

On macOS, if Chrome is not auto-discovered, add:

```sh
--chrome-path '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
```

The runner explicitly selects the 15 public HTML files in `sites.json`. It navigates only; it does not submit forms, invoke handlers, deploy changes or modify tracking. It runs sequentially to reduce CPU contention. RCN's existing analytics test flag excludes its test sessions from saved PostHog charts; other analytics may still record synthetic page views. Output contains individual HTML/JSON reports and `summary.json`. Never stage these tools or reports into either public website.

Mobile tests use Lighthouse's cold-cache simulated mobile defaults (150 ms RTT, 1,638.4 Kbps throughput, CPU slowdown 4). Desktop uses Lighthouse's desktop preset. Exact configuration and tool version are saved per result. Three Avalon mobile runs support reporting a median and range. Other page results are single-run diagnostics; repeat them before making a decision based on a headline metric.

Lighthouse navigation tests measure LCP, CLS and Total Blocking Time (TBT). TBT is not INP. Use CrUX or first-party RUM for real-user INP and p75 Core Web Vitals. Missing field data means unavailable, never passing. Origin field data cannot establish how every route performs. Today's deployment cannot be validated from a rolling 28-day field window.

## Off-the-shelf options for a VPS

| Tool | Best fit | Output / integration |
| --- | --- | --- |
| [Unlighthouse](https://github.com/harlan-zw/unlighthouse) | Site-wide Google Lighthouse grading | Auto-discovers URLs, reports performance/accessibility/SEO/best practices, static HTML dashboard plus JSON/CSV. Closest fit for the performance grader. |
| [SiteOne Crawler](https://github.com/janreges/siteone-crawler) | Technical SEO crawls and asset checks | Linux CLI, HTML/JSON reports, links/status codes/headings/metadata/security/cache diagnostics. Useful complement to Lighthouse. |
| [LibreCrawl](https://github.com/PhialsBasement/LibreCrawl) | A browser-operated, self-hosted Screaming Frog-style interface | Docker/web application, link and SEO analysis, JavaScript rendering, exports and PageSpeed integration. A fuller service to maintain. |

Recommended starting setup: Unlighthouse for performance grading, with SiteOne when a broader technical crawl is needed. If an interactive web crawl interface is the main requirement, evaluate LibreCrawl instead. None is installed on the VPS by this task.

Unlighthouse's documented static report command is:

```sh
npx --package @unlighthouse/cli@0.19.1 unlighthouse-ci \
  --site https://book.rivercruisenetwork.com --build-static
```

Run each business in a separate working/output directory. Reports are generated under `.unlighthouse/`; preserve report assets together. The VPS needs Chrome/Chromium and sufficient free memory; use low concurrency. The [CI/report documentation](https://unlighthouse.dev/integrations/ci) explains JSON/CSV and budgets. Docker support is described as experimental by the project; a normal unprivileged Linux CLI installation is a simpler first setup.

For a private browser interface, bind it to localhost and access it through an SSH tunnel, or put it behind existing authenticated HTTPS access. LibreCrawl's default local mode has no login and should stay private. Review and pin the chosen release before deployment. No recurring schedule has been created.
