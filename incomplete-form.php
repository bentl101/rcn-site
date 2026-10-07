<?php
/** Incomplete RCN quote attempts: Ben-only operational email, never a sales lead. */
declare(strict_types=1);
header('Content-Type: application/json; charset=UTF-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');

function finish(int $status, string $result): void {
    http_response_code($status);
    echo json_encode(['result' => $result]);
    exit;
}

if (($_SERVER['REQUEST_METHOD'] ?? '') !== 'POST') {
    header('Allow: POST');
    finish(405, 'method_not_allowed');
}
// JSON plus an exact Origin check prevents other websites using visitors' browsers
// to trigger email. No CORS permission is granted. Non-browser abuse is rate limited.
if (($_SERVER['HTTP_ORIGIN'] ?? '') !== 'https://book.rivercruisenetwork.com') {
    finish(403, 'origin_not_allowed');
}
if (strtolower(trim(explode(';', $_SERVER['CONTENT_TYPE'] ?? '')[0])) !== 'application/json') {
    finish(415, 'json_required');
}
$raw = file_get_contents('php://input', false, null, 0, 16385);
if ($raw === false || strlen($raw) > 16384) finish(413, 'too_large');
$data = json_decode($raw, true);
if (!is_array($data) || !is_array($data['fields'] ?? null)) finish(400, 'invalid_payload');
$pages = ['/' => 'River Cruise Network', '/index.html' => 'River Cruise Network',
    '/avalon-waterways.html' => 'Avalon Waterways', '/scenic-river-cruise.html' => 'Scenic',
    '/emerald-river-cruise.html' => 'Emerald', '/amawaterways-river-cruise.html' => 'AmaWaterways',
    '/viking-river-cruise.html' => 'Viking'];
$page = $data['page'] ?? '';
if (!is_string($page) || !isset($pages[$page])) finish(400, 'invalid_page');
$labels = ['first_name' => 'First name', 'last_name' => 'Last name', 'email' => 'Email',
    'phone' => 'Phone', 'destination' => 'Preferred itinerary', 'travel_date' => 'Travel date',
    'duration' => 'Duration', 'guests' => 'Guests', 'budget' => 'Budget per person (CAD)',
    'operator' => 'Operator', 'additional_info' => 'Additional information'];
$fields = [];
foreach ($labels as $name => $label) {
    $value = $data['fields'][$name] ?? '';
    if (!is_string($value) || strlen($value) > ($name === 'additional_info' ? 12000 : 1200)) {
        finish(400, 'invalid_field');
    }
    $fields[$name] = trim(preg_replace('/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/', '', $value));
}
$required = ['first_name', 'email', 'phone', 'destination', 'travel_date', 'duration', 'guests', 'budget'];
if ($page === '/' || $page === '/index.html') $required[] = 'operator';
$missing = array_values(array_filter($required, function ($name) use ($fields) { return $fields[$name] === ''; }));
if (!$missing) finish(422, 'no_missing_required_fields');

// Store only hashes/timestamps/counters outside the document root. Never store the
// entered values, email addresses or raw IPs in a publicly accessible file.
$path = sys_get_temp_dir() . '/rcn-incomplete-' . hash('sha256', __DIR__) . '.json';
$oldMask = umask(0077);
$fp = fopen($path, 'c+');
umask($oldMask);
if (!$fp || !flock($fp, LOCK_EX)) finish(503, 'temporarily_unavailable');
$state = json_decode(stream_get_contents($fp), true);
if (!is_array($state)) $state = [];
$now = time();
foreach ($state as $key => $entry) {
    if (!is_array($entry) || ($entry['expires'] ?? 0) <= $now) unset($state[$key]);
}
$ipKey = 'ip:' . hash('sha256', ($_SERVER['REMOTE_ADDR'] ?? 'unknown') . __DIR__);
$signature = 'attempt:' . hash('sha256', $ipKey . $page . json_encode($fields));
if (isset($state[$signature])) finish(200, 'duplicate');
if (($state[$ipKey]['count'] ?? 0) >= 30 || ($state['global']['count'] ?? 0) >= 300) {
    header('Retry-After: 3600');
    finish(429, 'rate_limited');
}
$id = 'RCN-INCOMPLETE-' . gmdate('Ymd-His') . '-' . bin2hex(random_bytes(4));
$isTest = ($data['is_test'] ?? false) === true;
$body = ($isTest ? "TEST NOTIFICATION\n\n" : '') . "INCOMPLETE QUOTE ATTEMPT — NOT A COMPLETED LEAD\n\n";
$body .= "The visitor tried to submit, but required fields were missing. They may subsequently complete the form.\n";
$body .= "For Ben's review only. Not sent to sales, CRM or Ads. Do not assume consent for marketing.\n\n";
$body .= "Reference: $id\nPage: https://book.rivercruisenetwork.com$page\n";
$instant = new DateTimeImmutable('now', new DateTimeZone('UTC'));
foreach (['Europe/Dublin' => 'Ireland', 'America/Toronto' => 'Toronto', 'UTC' => 'UTC'] as $zone => $label) {
    $body .= $label . ': ' . $instant->setTimezone(new DateTimeZone($zone))->format('Y-m-d H:i:s T') . "\n";
}
$body .= "\nMissing required fields: " . implode(', ', array_map(function ($name) use ($labels) { return $labels[$name]; }, $missing)) . "\n\nEntered details:\n";
foreach ($labels as $name => $label) $body .= $label . ': ' . ($fields[$name] === '' ? '[not entered]' : $fields[$name]) . "\n";
if ($fields['email'] !== '' && !filter_var($fields['email'], FILTER_VALIDATE_EMAIL)) {
    $body .= "\nThe entered email address is also invalid.\n";
}
$headers = "From: River Cruise Network <noreply@rivercruisenetwork.com>\r\n";
$headers .= "MIME-Version: 1.0\r\nContent-Type: text/plain; charset=UTF-8\r\nContent-Transfer-Encoding: base64";
// Recipient is deliberately fixed; no recipient, CC, BCC or Reply-To from input.
$accepted = mail('btl101@gmail.com', ($isTest ? '[TEST] ' : '') . '[RCN incomplete form] Missing required fields', chunk_split(base64_encode($body)), $headers);
if ($accepted) $state[$signature] = ['expires' => $now + 600];
// Count failed mail attempts too, so a mail outage cannot bypass the rate limit.
foreach ([$ipKey, 'global'] as $key) {
    if (!isset($state[$key])) $state[$key] = ['expires' => $now + 3600, 'count' => 0];
    $state[$key]['count']++;
}
rewind($fp);
ftruncate($fp, 0);
fwrite($fp, json_encode($state));
fflush($fp);
flock($fp, LOCK_UN);
fclose($fp);
if (!$accepted) {
    error_log('RCN incomplete form: mail was not accepted; reference=' . $id);
    finish(503, 'mail_unavailable');
}
finish(200, 'accepted');
