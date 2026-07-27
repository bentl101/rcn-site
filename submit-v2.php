<?php
/**
 * River Cruise Network — Lead Form Handler
 * v3.0 — 2026-05-27:
 *  - CSV-first: log every valid submission before any external call.
 *  - No HTML escape at intake. Store raw text. Email rendering escapes on output.
 *  - Shared-secret header (X-RCN-Token) on the n8n call so the public webhook
 *    can reject anything that didn't pass through this PHP entry point.
 *  - Anti-bot signals (honeypot/time_on_page) are NOT gates here — they ride
 *    along to n8n as features for the LLM scorer to weigh.
 *  - Ads conversion is fired server-side by n8n after scoring, never here.
 */

// ── Config ────────────────────────────────────────────────────────────────────
$RECIPIENT_EMAIL = 'sales@rivercruisenetwork.com, btl101@gmail.com';
$SITE_NAME       = 'River Cruise Network';
$THANK_YOU_URL   = '/thank-you.html';
$ERROR_URL       = '/index.html?error=1';
$N8N_WEBHOOK_URL = 'https://n8.copperchunk.com/webhook/rcn-form';
// Shared secret. Must match the value n8n's "Verify Token" Code node checks.
// Loaded from the untracked rcn-secrets.php (see that file to rotate).
$RCN_SECRETS = is_file(__DIR__ . '/rcn-secrets.php') ? (include __DIR__ . '/rcn-secrets.php') : [];
$N8N_SHARED_TOKEN = $RCN_SECRETS['RCN_N8N_TOKEN'] ?? (getenv('RCN_N8N_TOKEN') ?: '');
// ─────────────────────────────────────────────────────────────────────────────

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    header('Location: ' . $ERROR_URL);
    exit;
}

// Sanitise: strip tags + trim only. Do NOT HTML-escape at intake — that would
// corrupt downstream consumers (CRM, CSV, sheet, LLM). Escape only at render.
function clean_text(string $val): string {
    return trim(strip_tags($val));
}
function esc_html(string $val): string {
    return htmlspecialchars($val, ENT_QUOTES, 'UTF-8');
}

// ── Enhanced Conversions hashing ─────────────────────────────────────────────
// Google Ads requires SHA-256 (hex, lowercase) of normalised values:
//   - email:  lowercase + trim
//   - phone:  E.164 (digits with leading + and country code), no spaces
//   - names:  lowercase + trim
function hash_for_ads(string $val): string {
    return $val === '' ? '' : hash('sha256', $val);
}
function normalise_email(string $email): string {
    return strtolower(trim($email));
}
// Best-effort E.164 normaliser. Assumes NANP (Canada/US) if 10 digits, +1 otherwise unknown.
function normalise_phone(string $phone): string {
    $digits = preg_replace('/\D+/', '', $phone);
    if ($digits === '') return '';
    if (strlen($digits) === 10)       return '+1' . $digits;          // assume NANP
    if (strlen($digits) === 11 && $digits[0] === '1') return '+' . $digits;
    return '+' . $digits;  // for other lengths just prefix '+', Google handles loosely
}
function normalise_name(string $name): string {
    return strtolower(trim($name));
}

$first_name         = clean_text($_POST['first_name']        ?? '');
$last_name          = clean_text($_POST['last_name']         ?? '');
$email              = filter_var(trim($_POST['email'] ?? ''), FILTER_SANITIZE_EMAIL);
$phone              = clean_text($_POST['phone']             ?? '');
$destination        = clean_text($_POST['destination']       ?? '');
$travel_date        = clean_text($_POST['travel_date']       ?? '');
$duration           = clean_text($_POST['duration']          ?? '');
$budget             = clean_text($_POST['budget']            ?? '');
$guests             = clean_text($_POST['guests']            ?? '');
$operator           = clean_text($_POST['operator']          ?? '');
$additional_info    = clean_text($_POST['additional_info']   ?? '');
$page_source        = clean_text($_POST['page_source']       ?? 'Website');
$utm_source         = clean_text($_POST['utm_source']        ?? '');
$utm_medium         = clean_text($_POST['utm_medium']        ?? '');
$utm_campaign       = clean_text($_POST['utm_campaign']      ?? '');
$utm_term           = clean_text($_POST['utm_term']          ?? '');
$utm_content        = clean_text($_POST['utm_content']       ?? '');
$click_id           = clean_text($_POST['click_id']          ?? '');
$click_id_type      = clean_text($_POST['click_id_type']     ?? '');
$device_type        = clean_text($_POST['device_type']       ?? '');
$browser_language   = clean_text($_POST['browser_language']  ?? '');
$user_agent         = $_SERVER['HTTP_USER_AGENT']            ?? '';
$landing_page       = filter_var(trim($_POST['landing_page'] ?? ''), FILTER_SANITIZE_URL);
$referrer           = filter_var(trim($_POST['referrer']     ?? ''), FILTER_SANITIZE_URL);
// New ValueTrack params
$utm_id             = clean_text($_POST['utm_id']            ?? '');
$matchtype          = clean_text($_POST['matchtype']         ?? '');
$gad_device         = clean_text($_POST['device']            ?? '');  // Google's m/t/c (not to be confused with device_type)
$network            = clean_text($_POST['network']           ?? '');
$adgroupid          = clean_text($_POST['adgroupid']         ?? '');
$targetid           = clean_text($_POST['targetid']          ?? '');
$loc_physical       = clean_text($_POST['loc_physical']      ?? '');
$loc_interest       = clean_text($_POST['loc_interest']      ?? '');
$time_on_page       = (int)($_POST['time_on_page']           ?? 0);
$honeypot_website   = trim($_POST['website']                 ?? '');
$honeypot_reference = trim($_POST['contact_reference']       ?? '');
$honeypot_sources   = [];
if ($honeypot_website !== '')   $honeypot_sources[] = 'website';
if ($honeypot_reference !== '') $honeypot_sources[] = 'contact_reference';
$honeypot_filled    = count($honeypot_sources) > 0;  // signal, not a PHP rejection gate
$honeypot_source    = implode(',', $honeypot_sources);
$lead_order_id      = clean_text($_POST['lead_order_id']     ?? '');
if (empty($lead_order_id)) {
    $lead_order_id = 'RCN-' . gmdate('Ymd-His') . '-' . bin2hex(random_bytes(4));
}
$submitted_at       = gmdate('Y-m-d H:i:s');

// Server-side referrer fallback: if the JS attribution cookie/sessionStorage was
// wiped mid-journey (e.g. Facebook in-app browser), try to recover click_id,
// UTMs, and ValueTrack params from the referrer URL's query string.
if ($click_id === '' && $referrer !== '' && strpos($referrer, '?') !== false) {
    $ref_query = parse_url($referrer, PHP_URL_QUERY) ?? '';
    if ($ref_query) {
        $ref_params = [];
        parse_str($ref_query, $ref_params);
        foreach (['gclid','gbraid','wbraid','fbclid','msclkid','ttclid'] as $ck) {
            if (!empty($ref_params[$ck])) {
                $click_id      = clean_text($ref_params[$ck]);
                $click_id_type = $ck;
                break;
            }
        }
        if ($click_id !== '') {
            // Backfill empty attribution fields from the referrer
            foreach (['utm_source','utm_medium','utm_campaign','utm_term','utm_content',
                      'utm_id','matchtype','network','adgroupid','targetid',
                      'loc_physical','loc_interest'] as $k) {
                if (isset($ref_params[$k]) && $$k === '') {
                    $$k = clean_text($ref_params[$k]);
                }
            }
            if (!empty($ref_params['device']) && $gad_device === '') {
                $gad_device = clean_text($ref_params['device']);
            }
            // The referrer IS the real landing page when storage was wiped
            if ($landing_page === '' || strpos($landing_page, '?') === false) {
                $landing_page = filter_var($referrer, FILTER_SANITIZE_URL);
            }
        }
    }
}
$ip_address         = $_SERVER['REMOTE_ADDR'] ?? 'unknown';

// Enhanced-conversion hashes (computed once, used by n8n upload + sheet writes)
$hashed_email       = hash_for_ads(normalise_email($email));
$hashed_phone       = hash_for_ads(normalise_phone($phone));
$hashed_first_name  = hash_for_ads(normalise_name($first_name));
$hashed_last_name   = hash_for_ads(normalise_name($last_name));

// Basic validation — keep gates tight. Anything bot-shaped survives and gets scored.
if (empty($first_name) || !filter_var($email, FILTER_VALIDATE_EMAIL)
    || empty($travel_date) || empty($duration) || empty($budget)
    || empty($guests) || empty($operator)) {
    header('Location: ' . $ERROR_URL);
    exit;
}

$full_name = trim("$first_name $last_name");

// ── 1) CSV LEAD LOG — write FIRST, before any external call ──────────────────
// This is the immutable source of truth. If n8n / email / Ads all fail, we
// still have every valid submission with its received status.
$csv_file   = __DIR__ . '/leads.csv';
$csv_header = [
    'submitted_at','lead_order_id','first_name','last_name','email','phone',
    'destination','travel_date','duration','budget','guests','operator',
    'additional_info','page_source','utm_source','utm_medium','utm_campaign',
    'utm_term','utm_content','click_id','click_id_type','device_type',
    'landing_page','referrer','time_on_page','honeypot_filled','ip_address',
    'user_agent','utm_id','matchtype','network','adgroupid','targetid',
    'loc_physical','loc_interest','gad_device','n8n_status','n8n_error',
];
$csv_row = [
    $submitted_at, $lead_order_id, $first_name, $last_name, $email, $phone,
    $destination, $travel_date, $duration, $budget, $guests, $operator,
    $additional_info, $page_source, $utm_source, $utm_medium, $utm_campaign,
    $utm_term, $utm_content, $click_id, $click_id_type, $device_type,
    $landing_page, $referrer, $time_on_page, ($honeypot_filled ? 1 : 0), $ip_address,
    $user_agent, $utm_id, $matchtype, $network, $adgroupid, $targetid,
    $loc_physical, $loc_interest, $gad_device, 'received', '',
];
// Append under an exclusive lock. 'c' creates the file if missing without
// truncating, with the pointer at the start so we can detect an empty file
// and write the header exactly once.
$csv_write_ok = false;
$fp = fopen($csv_file, 'c');
if ($fp && flock($fp, LOCK_EX)) {
    $needs_header = (fstat($fp)['size'] === 0);
    fseek($fp, 0, SEEK_END);
    if ($needs_header) fputcsv($fp, $csv_header);
    fputcsv($fp, $csv_row);
    fflush($fp);
    flock($fp, LOCK_UN);
    $csv_write_ok = true;
}
if ($fp) fclose($fp);

// ── 2) POST to n8n with shared-secret header ─────────────────────────────────
$lead_payload = json_encode([
    'lead_order_id'   => $lead_order_id,
    'first_name'      => $first_name,
    'last_name'       => $last_name,
    'name'            => $full_name,
    'email'           => $email,
    'phone'           => $phone,
    'destination'     => $destination,
    'travel_date'     => $travel_date,
    'duration'        => $duration,
    'budget'          => $budget,
    'guests'          => $guests,
    'operator'        => $operator,
    'additional_info' => $additional_info,
    'page_source'     => $page_source,
    'utm_source'      => $utm_source,
    'utm_medium'      => $utm_medium,
    'utm_campaign'    => $utm_campaign,
    'utm_term'        => $utm_term,
    'utm_content'     => $utm_content,
    'click_id'        => $click_id,
    'click_id_type'   => $click_id_type,
    'device_type'     => $device_type,
    'browser_language'=> $browser_language,
    'user_agent'      => $user_agent,
    'landing_page'    => $landing_page,
    'referrer'        => $referrer,
    'time_on_page'    => $time_on_page,
    'honeypot_filled' => $honeypot_filled,
    'honeypot_source' => $honeypot_source,
    'submitted_at'    => $submitted_at,
    'ip_address'      => $ip_address,
    // ValueTrack / expanded attribution
    'utm_id'          => $utm_id,
    'matchtype'       => $matchtype,
    'network'         => $network,
    'adgroupid'       => $adgroupid,
    'targetid'        => $targetid,
    'loc_physical'    => $loc_physical,
    'loc_interest'    => $loc_interest,
    'gad_device'      => $gad_device,
    // Enhanced conversions (SHA-256 hex, lowercase, normalised)
    'hashed_email'    => $hashed_email,
    'hashed_phone'    => $hashed_phone,
    'hashed_first_name' => $hashed_first_name,
    'hashed_last_name'  => $hashed_last_name,
]);

$ch = curl_init($N8N_WEBHOOK_URL);
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST           => true,
    CURLOPT_POSTFIELDS     => $lead_payload,
    CURLOPT_HTTPHEADER     => [
        'Content-Type: application/json',
        'X-RCN-Token: ' . $N8N_SHARED_TOKEN,
        'User-Agent: RCN-PHP/3.0',
    ],
    // n8n now uses responseMode=onReceived and responds in ~200ms. Tight
    // timeout keeps the user redirect snappy even if n8n hiccups.
    CURLOPT_TIMEOUT        => 5,
    CURLOPT_CONNECTTIMEOUT => 3,
]);
$n8n_response  = curl_exec($ch);
$n8n_http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$n8n_error     = curl_error($ch);
curl_close($ch);

// ── 3) Update the CSV row with the actual n8n status ─────────────────────────
// Find THIS submission's row by its unique lead_order_id (column index 1) and
// backfill the n8n status/error columns. Matching by ID — not assuming "last
// row" — is what keeps concurrent submissions from clobbering each other's
// status. The whole read-modify-write runs under an exclusive lock so two
// requests can't interleave their rewrites. leads.csv stays small, so the
// full rewrite is cheap.
if ($csv_write_ok) {
    $fp = fopen($csv_file, 'r+');
    if ($fp && flock($fp, LOCK_EX)) {
        $lines = [];
        while (($line = fgets($fp)) !== false) $lines[] = $line;
        for ($i = count($lines) - 1; $i >= 1; $i--) {   // skip header at index 0
            $cols = str_getcsv(rtrim($lines[$i], "\r\n"));
            if (isset($cols[1]) && $cols[1] === $lead_order_id && count($cols) >= 2) {
                $cols[count($cols) - 2] = (string)$n8n_http_code;
                $cols[count($cols) - 1] = $n8n_error;
                $tmp = fopen('php://temp', 'r+');
                fputcsv($tmp, $cols);
                rewind($tmp);
                $lines[$i] = stream_get_contents($tmp);
                fclose($tmp);
                break;
            }
        }
        ftruncate($fp, 0);
        rewind($fp);
        foreach ($lines as $l) fwrite($fp, $l);
        fflush($fp);
        flock($fp, LOCK_UN);
    }
    if ($fp) fclose($fp);
}

// ── 4) Backup email via PHP mail() — safety net independent of n8n ───────────
$subject = "New RCN lead — {$full_name}";

// Render-time escaping for the HTML-safe block (mail() with plaintext, but
// some clients still render — and this protects against header-injection-shaped
// junk in fields).
$body  = "New lead from {$SITE_NAME}\n";
$body .= str_repeat('─', 50) . "\n\n";
$body .= "Lead Order ID:      {$lead_order_id}\n";
$body .= "Name:               {$full_name}\n";
$body .= "Email:              {$email}\n";
$body .= "Phone:              {$phone}\n\n";
$body .= "Destination:        {$destination}\n";
$body .= "Travel Date:        {$travel_date}\n";
$body .= "Duration:           {$duration}\n";
$body .= "Budget:             {$budget}\n";
$body .= "Number of Guests:   {$guests}\n";
$body .= "Preferred Operator: {$operator}\n\n";
$body .= "Additional Info:\n{$additional_info}\n\n";
$body .= str_repeat('─', 50) . "\n";
$body .= "Source page:    {$page_source}\n";
$body .= "Referrer:       {$referrer}\n";
$body .= "Time on page:   {$time_on_page}s\n";
$body .= "Landing page:   {$landing_page}\n";
if ($utm_source)   $body .= "UTM Source:     {$utm_source}\n";
if ($utm_medium)   $body .= "UTM Medium:     {$utm_medium}\n";
if ($utm_campaign) $body .= "UTM Campaign:   {$utm_campaign}\n";
if ($utm_term)     $body .= "UTM Term:       {$utm_term}\n";
if ($utm_content)  $body .= "UTM Content:    {$utm_content}\n";
if ($click_id)     $body .= "Click ID:       {$click_id} ({$click_id_type})\n";
if ($device_type)  $body .= "Device:         {$device_type}\n";
if ($browser_language) $body .= "Language:       {$browser_language}\n";
if ($honeypot_filled) $body .= "⚠ Honeypot filled ({$honeypot_source}; deterministic spam signal)\n";
$body .= "Submitted:   " . gmdate('d M Y H:i:s') . " UTC\n";
$body .= "IP:          {$ip_address}\n";

// Strip CR/LF from anything reaching headers to block header injection
$safe_reply = preg_replace('/[\r\n]+/', '', $email);
$headers  = "From: noreply@rivercruisenetwork.com\r\n";
$headers .= "Reply-To: {$safe_reply}\r\n";
$headers .= "X-Mailer: PHP/" . phpversion() . "\r\n";

mail($RECIPIENT_EMAIL, $subject, $body, $headers);

// ── 5) Redirect ───────────────────────────────────────────────────────────────
header('Location: ' . $THANK_YOU_URL);
exit;
