# RCN and DCT image performance — 7 October 2026

Scope: the canonical RCN root and `dct-site/` only. Live baselines of 32 files per site matched local sources before editing. No obsolete RCN duplicate used.

## Diagnosis

Avalon had two eagerly loaded PNG photos totalling 3,657,911 bytes. PostHog recorded one full-load outlier of 105,298 ms, while that visit's DOM-ready time was 1,052 ms and largest contentful paint was 3,364 ms. This was a late-resource outlier, not evidence of a blank page for 105 seconds. Without a resource waterfall, the exact resource responsible cannot be identified. Other observed Avalon full-load samples were approximately 1.6–3.1 seconds.

## Changes

- 42 RCN and 16 DCT WebP derivatives, including lossless resized logos.
- Responsive photo candidates up to 1,200 pixels, capped at source dimensions; hero images capped at 1,920 pixels. Existing small WebP and SVG assets retained. Original assets retained for recovery; RCN PNG favicon retained for compatibility.
- Explicit raster dimensions, asynchronous decoding and lazy loading for below-fold images. Hero images preloaded with high priority.
- RCN Google Fonts requested directly in the document head with preconnect, removing the CSS import discovery chain; font families and weights preserved.
- Avalon river photos at 768 pixels total 212,086 bytes, 94.2% below the original PNGs. Actual browser transfer depends on viewport and pixel density.
- DCT logo reduced from 2,941 pixels / 174,920 bytes to 600 pixels / 28,536 bytes (lossless WebP).

## Validation

All 15 pages retain identical visible copy, inline and external script definitions, links, form controls and form actions compared with saved live baselines. Image dimensions and responsive width descriptors match decoded files. Generated images are WebP and allowlisted separately by site. Original raster and SVG assets unchanged. RCN analytics regression checks pass, including destination asterisks and legacy Ads conversion baseline. Desktop/mobile Avalon and DCT previews inspected with no horizontal overflow. No sales forms submitted.

RCN deployed from its 50-file committed stage; all 50 FTP readbacks match. All 76 public HTML/CSS/JS/image URLs return HTTP 200 and match source bytes. Known private `leads.csv` and `rcn-secrets.php` return 403; mockup returns 404. Live desktop/mobile Avalon inspected; mobile card selects the 480-pixel WebP. All six destination asterisks and form actions verified by analytics regression checks.

DCT deployed after user authorization via SFTP on `uk09.webhostcluster.com:2022`, account `unitcostdominanc`, using this Mac’s existing default SSH identity. Direct SSH authenticated but the account reports shell access disabled; SFTP works. The documented `unitcost` alias and dedicated key are absent on this Mac. All nine existing destination files matched the saved live baseline before upload, and all 16 new assets were absent. The isolated 25-file stage was uploaded and every file read back byte-for-byte. All 49 public HTML/CSS/JS/image URLs return HTTP 200 and match source bytes. Public `leads.csv`, `dct-secrets.php`, `data/` and `tools/` return 404. Desktop/mobile homepage and all four live operator pages checked; form actions remain `/submit.php`, with no sales submissions.

Runtime gains require subsequent real visitor samples; byte savings alone do not establish a measured speed improvement.
