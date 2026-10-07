#!/usr/bin/env python3
"""Run read-only Lighthouse audits against the two explicitly allowlisted public sites.
Install Lighthouse separately; no server files or tracking configuration are changed.
"""
import argparse, json, shutil, subprocess
from pathlib import Path
from urllib.parse import urlencode

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--site', choices=['rcn', 'dct', 'all'], default='all')
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--lighthouse', default=shutil.which('lighthouse') or 'lighthouse')
parser.add_argument('--chrome-path')
parser.add_argument('--desktop', action='store_true', help='Also audit the two homepages and Avalon on desktop')
parser.add_argument('--repeat-avalon', type=int, default=1, choices=range(1, 4), help='Total equivalent mobile Avalon runs')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
config = json.loads((root / 'sites.json').read_text())
args.output.mkdir(parents=True, exist_ok=True)
results = []
jobs = []
for site in (['rcn', 'dct'] if args.site == 'all' else [args.site]):
    for page in sorted(n for n in config[site]['files'] if n.endswith('.html')):
        jobs.append((site, page, 'mobile', 1))
        if args.desktop and (page == 'index.html' or (site == 'rcn' and page == 'avalon-waterways.html')):
            jobs.append((site, page, 'desktop', 1))
        if site == 'rcn' and page == 'avalon-waterways.html':
            jobs.extend((site, page, 'mobile', run) for run in range(2, args.repeat_avalon + 1))
for site, page, device, run in jobs:
    url = config[site]['url'] + '/' + page
    # RCN excludes these navigation-only audits from saved PostHog reports.
    if site == 'rcn':
        url += '?' + urlencode({'rcn_analytics_test': 1})
    name = f'{site}-{Path(page).stem}-{device}-{run}'
    output = args.output / name
    command = [args.lighthouse, url, '--chrome-flags=--headless --disable-extensions',
               '--only-categories=performance,accessibility,best-practices,seo',
               '--output=json', '--output=html', '--output-path=' + str(output), '--quiet']
    if args.chrome_path:
        command.append('--chrome-path=' + args.chrome_path)
    if device == 'desktop':
        command.append('--preset=desktop')
    print(f'Auditing {site}/{page} {device} run {run}', flush=True)
    process = subprocess.run(command, capture_output=True, text=True, timeout=240)
    report_path = Path(str(output) + '.report.json')
    if process.returncode or not report_path.exists():
        raise RuntimeError(f'{name} failed: {process.stderr[-1500:]}')
    report = json.loads(report_path.read_text())
    if report.get('runtimeError'):
        raise RuntimeError(f'{name}: {report["runtimeError"]}')
    audits = report['audits']
    row = {'site': site, 'page': page, 'device': device, 'run': run, 'url': url,
           'lighthouse': report['lighthouseVersion'], 'fetched': report['fetchTime'],
           'scores': {key: round(category['score'] * 100) for key, category in report['categories'].items()},
           'metrics': {key: audits.get(key, {}).get('numericValue') for key in
                       ['largest-contentful-paint', 'first-contentful-paint', 'cumulative-layout-shift', 'total-blocking-time', 'speed-index']},
           'settings': report['configSettings'], 'report': report_path.name,
           'warnings': report.get('runWarnings', [])}
    results.append(row)
    (args.output / 'summary.json').write_text(json.dumps(results, indent=2))
    print(json.dumps({key: row[key] for key in ['site', 'page', 'device', 'run', 'scores', 'metrics']}), flush=True)
print(f'Completed {len(results)} navigation-only audits; no forms submitted.', flush=True)
