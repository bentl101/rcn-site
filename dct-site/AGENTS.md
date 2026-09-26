# Discount Coach Tours only

This directory is exclusively https://book.discountcoachtours.ca/.
Read ../AGENTS.md, ../SITE-BOUNDARIES.md and README.md.

- Edit DCT pages only here. Root-level pages belong to River Cruise Network.
- Deploy to `/home/unitcostdominanc/book.discountcoachtours.ca/` only.
- Never use RCN FTP credentials or its FTP root `/` for DCT.
- Handler: `submit.php`; thank-you: `thank-you.html`; lead IDs: `DCT-`.
- Ads customer: `3639225242`; webhook `/webhook/dct-form`; `X-DCT-Token`.
- Never copy RCN GTM/Ads tags, river-cruise branding or RCN handlers here.
- DCT's shared phone and agreed sales mailbox are intentional; they do not imply shared tracking.
- Public upload allowlist: ../sites.json. Stage with ../ops/stage_site.py --site dct.
- Keep tools, docs, CSVs and private data outside the public root.
- Commit, push, deploy the selected site only, then verify every public asset.
