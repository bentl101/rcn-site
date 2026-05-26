<?php
// Legacy endpoint — forward all POSTs to submit-v2.php so cached pages,
// bookmarks, and bots that target the old URL still hit the full pipeline
// (CSV log, n8n with lead_order_id, backup mail). $_POST / $_SERVER carry
// through via include, so no data is lost.
require __DIR__ . '/submit-v2.php';
