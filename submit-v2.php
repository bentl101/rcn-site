<?php
/**
 * River Cruise Network — Lead Form Handler
 * Forwards lead data to n8n webhook, sends email, and redirects.
 * v2.1 — 2026-02-27: Anti-bot time_on_page restored
 */

// ── Config ────────────────────────────────────────────────────────────────────
$RECIPIENT_EMAIL = 'sales@rivercruisenetwork.com';
$SITE_NAME       = 'River Cruise Network';
$THANK_YOU_URL   = '/thank-you.html';
$ERROR_URL       = '/index.html?error=1';
$N8N_WEBHOOK_URL = 'https://n8.copperchunk.com/webhook/rcn-form';
// ─────────────────────────────────────────────────────────────────────────────

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    header('Location: ' . $ERROR_URL);
    exit;
}

// Sanitise inputs
function clean(string $val): string {
    return htmlspecialchars(strip_tags(trim($val)), ENT_QUOTES, 'UTF-8');
}

$first_name         = clean($_POST['first_name']         ?? '');
$last_name          = clean($_POST['last_name']          ?? '');
$email              = filter_var(trim($_POST['email'] ?? ''), FILTER_SANITIZE_EMAIL);
$phone              = clean($_POST['phone']              ?? '');
$destination        = clean($_POST['destination']        ?? '');
$travel_date        = clean($_POST['travel_date']        ?? '');
$duration           = clean($_POST['duration']           ?? '');
$budget             = clean($_POST['budget']             ?? '');
$guests             = clean($_POST['guests']             ?? '');
$operator           = clean($_POST['operator']           ?? '');
$additional_info    = clean($_POST['additional_info']    ?? '');
$page_source        = clean($_POST['page_source']        ?? 'Website');
$utm_source         = clean($_POST['utm_source']         ?? '');
$utm_medium         = clean($_POST['utm_medium']         ?? '');
$utm_campaign       = clean($_POST['utm_campaign']       ?? '');
$utm_term           = clean($_POST['utm_term']           ?? '');
$utm_content        = clean($_POST['utm_content']        ?? '');
$click_id           = clean($_POST['click_id']           ?? '');
$click_id_type      = clean($_POST['click_id_type']      ?? '');
$device_type        = clean($_POST['device_type']        ?? '');
$user_agent         = $_SERVER['HTTP_USER_AGENT']        ?? '';
$landing_page       = filter_var(trim($_POST['landing_page'] ?? ''), FILTER_SANITIZE_URL);
$referrer           = filter_var(trim($_POST['referrer']    ?? ''), FILTER_SANITIZE_URL);
$time_on_page       = (int)($_POST['time_on_page']       ?? 0);
$honeypot           = trim($_POST['website']             ?? '');

// Basic validation
if (empty($first_name) || !filter_var($email, FILTER_VALIDATE_EMAIL)
    || empty($travel_date) || empty($duration) || empty($budget) || empty($guests) || empty($operator)) {
    header('Location: ' . $ERROR_URL);
    exit;
}

// Anti-bot checks: honeypot + minimum time on page
if (!empty($honeypot) || $time_on_page < 2) {
    header('Location: ' . $THANK_YOU_URL);
    exit;
}

$full_name = trim("$first_name $last_name");

// ── Redirect immediately, then process in background ────────────────────────
ignore_user_abort(true);
header('Location: ' . $THANK_YOU_URL);
header('Connection: close');
header('Content-Length: 0');
ob_end_flush();
flush();
if (function_exists('fastcgi_finish_request')) {
    fastcgi_finish_request();
}

// ── Everything below runs after the user has been redirected ─────────────────

// ── Forward to n8n Webhook ──────────────────────────────────────────────────
$lead_payload = json_encode([
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
    'submitted_at'    => date('Y-m-d H:i:s'),
    'ip_address'      => $_SERVER['REMOTE_ADDR'] ?? 'unknown',
]);

$ch = curl_init($N8N_WEBHOOK_URL);
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST           => true,
    CURLOPT_POSTFIELDS     => $lead_payload,
    CURLOPT_HTTPHEADER     => ['Content-Type: application/json'],
    CURLOPT_TIMEOUT        => 10,
]);
$n8n_response = curl_exec($ch);
$n8n_http_code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$n8n_error = curl_error($ch);
curl_close($ch);

// ── CSV Lead Log (independent of n8n) ───────────────────────────────────────
$csv_file = __DIR__ . '/leads.csv';
$csv_exists = file_exists($csv_file);
$fp = fopen($csv_file, 'a');
if ($fp) {
    if (!$csv_exists) {
        fputcsv($fp, [
            'submitted_at','first_name','last_name','email','phone',
            'destination','travel_date','duration','budget','guests','operator',
            'additional_info','page_source','utm_source','utm_medium','utm_campaign',
            'click_id','click_id_type','device_type','landing_page','referrer',
            'time_on_page','ip_address','n8n_status','n8n_error'
        ]);
    }
    fputcsv($fp, [
        date('Y-m-d H:i:s'), $first_name, $last_name, $email, $phone,
        $destination, $travel_date, $duration, $budget, $guests, $operator,
        $additional_info, $page_source, $utm_source, $utm_medium, $utm_campaign,
        $click_id, $click_id_type, $device_type, $landing_page, $referrer,
        $time_on_page, $_SERVER['REMOTE_ADDR'] ?? 'unknown',
        $n8n_http_code, $n8n_error
    ]);
    fclose($fp);
}

// ── Email Notification (backup) ─────────────────────────────────────────────
$subject = "{$budget} · {$operator} · {$full_name} · RCN Lead";

$body  = "New lead from {$SITE_NAME}\n";
$body .= str_repeat('─', 50) . "\n\n";
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
$body .= "Submitted:   " . date('d M Y H:i:s') . " UTC\n";
$body .= "IP:          " . ($_SERVER['REMOTE_ADDR'] ?? 'unknown') . "\n";

$headers  = "From: noreply@rivercruisenetwork.com\r\n";
$headers .= "Reply-To: {$email}\r\n";
$headers .= "X-Mailer: PHP/" . phpversion() . "\r\n";

mail($RECIPIENT_EMAIL, $subject, $body, $headers);
