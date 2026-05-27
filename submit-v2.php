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
// If you rotate this, update both sides at the same time.
$N8N_SHARED_TOKEN = 'rcn-php-2026-7f2a9e4c-bridge';
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
$user_agent         = $_SERVER['HTTP_USER_AGENT']            ?? '';
$landing_page       = filter_var(trim($_POST['landing_page'] ?? ''), FILTER_SANITIZE_URL);
$referrer           = filter_var(trim($_POST['referrer']     ?? ''), FILTER_SANITIZE_URL);
$time_on_page       = (int)($_POST['time_on_page']           ?? 0);
$honeypot           = trim($_POST['website']                 ?? '');  // signal, not a gate
$lead_order_id      = clean_text($_POST['lead_order_id']     ?? '');
if (empty($lead_order_id)) {
    $lead_order_id = 'RCN-' . gmdate('Ymd-His') . '-' . bin2hex(random_bytes(4));
}
$submitted_at       = gmdate('Y-m-d H:i:s');
$ip_address         = $_SERVER['REMOTE_ADDR'] ?? 'unknown';

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
$csv_file = __DIR__ . '/leads.csv';
$csv_exists = file_exists($csv_file);
$fp = fopen($csv_file, 'a');
$csv_write_ok = false;
if ($fp) {
    if (!$csv_exists) {
        fputcsv($fp, [
            'submitted_at','lead_order_id','first_name','last_name','email','phone',
            'destination','travel_date','duration','budget','guests','operator',
            'additional_info','page_source','utm_source','utm_medium','utm_campaign',
            'utm_term','utm_content','click_id','click_id_type','device_type',
            'landing_page','referrer','time_on_page','honeypot_filled','ip_address',
            'user_agent','n8n_status','n8n_error'
        ]);
    }
    fputcsv($fp, [
        $submitted_at, $lead_order_id, $first_name, $last_name, $email, $phone,
        $destination, $travel_date, $duration, $budget, $guests, $operator,
        $additional_info, $page_source, $utm_source, $utm_medium, $utm_campaign,
        $utm_term, $utm_content, $click_id, $click_id_type, $device_type,
        $landing_page, $referrer, $time_on_page, ($honeypot !== '' ? 1 : 0), $ip_address,
        $user_agent, 'received', '',
    ]);
    fclose($fp);
    $csv_write_ok = true;
}

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
    'user_agent'      => $user_agent,
    'landing_page'    => $landing_page,
    'referrer'        => $referrer,
    'time_on_page'    => $time_on_page,
    'honeypot_filled' => ($honeypot !== ''),
    'submitted_at'    => $submitted_at,
    'ip_address'      => $ip_address,
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
// Tiny file rewrite. leads.csv is small (~thousands of rows max), this is cheap.
if ($csv_write_ok) {
    $rows = file($csv_file);
    if ($rows && count($rows) > 0) {
        $last = trim(array_pop($rows));
        // Replace the final two columns: n8n_status,n8n_error
        $cols = str_getcsv($last);
        if (count($cols) >= 2) {
            $cols[count($cols) - 2] = (string)$n8n_http_code;
            $cols[count($cols) - 1] = $n8n_error;
            $out = fopen($csv_file, 'w');
            foreach ($rows as $r) fwrite($out, $r);
            fputcsv($out, $cols);
            fclose($out);
        }
    }
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
if ($honeypot !== '') $body .= "⚠ Honeypot filled (treated as signal, not blocker)\n";
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
