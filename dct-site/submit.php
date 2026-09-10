<?php
declare(strict_types=1);

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    header('Location: /', true, 303);
    exit;
}

function clean_value(string $key, int $max = 500): string
{
    $value = $_POST[$key] ?? '';
    if (!is_string($value)) return '';
    return substr(trim(strip_tags(str_replace(["\r", "\0"], '', $value))), 0, $max);
}

function csv_safe(string $value): string
{
    return preg_match('/^[=+\-@]/', $value) ? "'" . $value : $value;
}

function append_csv(string $path, array $columns, array $row): bool
{
    $isNew = !file_exists($path) || filesize($path) === 0;
    $handle = fopen($path, 'ab');
    if ($handle === false) return false;
    $ok = false;
    if (flock($handle, LOCK_EX)) {
        if ($isNew) fputcsv($handle, $columns);
        $ok = fputcsv($handle, array_map('csv_safe', $row)) !== false;
        fflush($handle);
        flock($handle, LOCK_UN);
    }
    fclose($handle);
    return $ok;
}

function normalise_email_for_ads(string $email): string
{
    $email = strtolower(trim($email));
    $parts = explode('@', $email, 2);
    if (count($parts) !== 2) return '';
    [$local, $domain] = $parts;
    if ($domain === 'gmail.com' || $domain === 'googlemail.com') {
        $local = explode('+', $local, 2)[0];
        $local = str_replace('.', '', $local);
        $domain = 'gmail.com';
    }
    return $local . '@' . $domain;
}

function normalise_phone_for_ads(string $phone): string
{
    $raw = trim($phone);
    $digits = preg_replace('/\D+/', '', $raw) ?? '';
    if (strlen($digits) === 10) return '+1' . $digits;
    if (strlen($digits) === 11 && str_starts_with($digits, '1')) return '+' . $digits;
    if (str_starts_with($raw, '+') && strlen($digits) >= 8 && strlen($digits) <= 15) return '+' . $digits;
    return '';
}

function sha256_value(string $value): string
{
    return $value === '' ? '' : hash('sha256', $value);
}

function mail_safe_value(string $value): string
{
    return str_replace(["\r", "\n"], ' ', $value);
}

function direct_lead_mail_body(array $lead): string
{
    $fields = [
        'Lead Order ID' => 'lead_order_id', 'Name' => null, 'Email' => 'email',
        'Phone' => 'phone', 'Destination' => 'destination',
        'Travel date' => 'travel_date', 'Duration' => 'duration', 'Guests' => 'guests',
        'Budget' => 'budget', 'Operator' => 'operator',
        'Notes' => 'notes', 'Contact preference' => 'contact_preference',
        'Source page' => 'source_page', 'UTM source' => 'utm_source',
        'UTM medium' => 'utm_medium', 'UTM campaign' => 'utm_campaign',
        'UTM term' => 'utm_term', 'UTM content' => 'utm_content',
        'Landing page' => 'landing_page', 'Referrer' => 'referrer',
        'Submitted at' => 'submitted_at',
    ];
    $lines = [
        'New Discount Coach Tours lead (hosting backup)',
        'This is the direct PHP/cPanel copy. The n8n email is sent separately.',
        '',
    ];
    foreach ($fields as $label => $key) {
        $value = $key === null
            ? trim(mail_safe_value((string)($lead['first_name'] ?? '') . ' ' . (string)($lead['last_name'] ?? '')))
            : mail_safe_value((string)($lead[$key] ?? ''));
        $lines[] = $label . ': ' . ($value !== '' ? $value : '—');
    }
    return implode("\n", $lines);
}

if (clean_value('website', 200) !== '') {
    http_response_code(204);
    exit;
}

$required = ['first_name', 'last_name', 'email', 'phone', 'destination', 'travel_date', 'duration', 'guests', 'budget'];
foreach ($required as $key) {
    if (clean_value($key) === '') {
        header('Location: /?form_error=missing#enquire', true, 303);
        exit;
    }
}

$email = clean_value('email', 254);
if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
    header('Location: /?form_error=email#enquire', true, 303);
    exit;
}

$orderId = clean_value('lead_order_id', 64);
if (!preg_match('/^DCT-\d{8}-\d{6}-[a-f0-9]{8}$/', $orderId)) {
    $orderId = 'DCT-' . gmdate('Ymd-His') . '-' . bin2hex(random_bytes(4));
}

$clickId = clean_value('click_id', 500);
$clickIdType = strtolower(clean_value('click_id_type', 30));
$gclid = clean_value('gclid', 500);
$gbraid = clean_value('gbraid', 500);
$wbraid = clean_value('wbraid', 500);
if ($gclid === '' && $clickIdType === 'gclid') $gclid = $clickId;
if ($gbraid === '' && $clickIdType === 'gbraid') $gbraid = $clickId;
if ($wbraid === '' && $clickIdType === 'wbraid') $wbraid = $clickId;

$phone = clean_value('phone', 50);
$normalisedEmail = normalise_email_for_ads($email);
$normalisedPhone = normalise_phone_for_ads($phone);
$actionToken = bin2hex(random_bytes(32));

$ipAddress = substr($_SERVER['HTTP_CF_CONNECTING_IP'] ?? $_SERVER['REMOTE_ADDR'] ?? '', 0, 64);
$lead = [
    'submitted_at' => gmdate('c'), 'lead_order_id' => $orderId,
    'first_name' => clean_value('first_name', 100), 'last_name' => clean_value('last_name', 100),
    'email' => $email, 'phone' => $phone,
    'destination' => clean_value('destination', 200),
    'travel_date' => clean_value('travel_date', 20), 'duration' => clean_value('duration', 50),
    'guests' => clean_value('guests', 50), 'budget' => clean_value('budget', 80),
    'operator' => clean_value('operator', 80),
    'notes' => clean_value('notes', 2000), 'contact_preference' => clean_value('contact_preference', 30),
    'source_page' => clean_value('source_page', 120), 'utm_source' => clean_value('utm_source', 200),
    'utm_medium' => clean_value('utm_medium', 200), 'utm_campaign' => clean_value('utm_campaign', 300),
    'utm_term' => clean_value('utm_term', 300), 'utm_content' => clean_value('utm_content', 300),
    'utm_id' => clean_value('utm_id', 200), 'matchtype' => clean_value('matchtype', 50),
    'gad_device' => clean_value('gad_device', 50), 'network' => clean_value('network', 50),
    'adgroupid' => clean_value('adgroupid', 100), 'targetid' => clean_value('targetid', 100),
    'loc_physical' => clean_value('loc_physical', 100), 'loc_interest' => clean_value('loc_interest', 100),
    'gclid' => $gclid, 'gbraid' => $gbraid, 'wbraid' => $wbraid,
    'click_id' => $clickId, 'click_id_type' => $clickIdType,
    'landing_page' => clean_value('landing_page', 1000), 'referrer' => clean_value('referrer', 1000),
    'time_on_page' => clean_value('time_on_page', 20), 'device_type' => clean_value('device_type', 20),
    'browser_language' => clean_value('browser_language', 50), 'page_load_time' => clean_value('page_load_time', 30),
    'hashed_email' => sha256_value($normalisedEmail), 'hashed_phone' => sha256_value($normalisedPhone),
    'ip_address' => $ipAddress, 'user_agent' => substr($_SERVER['HTTP_USER_AGENT'] ?? '', 0, 500),
    'environment' => 'production', 'qa_test' => clean_value('qa_test', 10) === '1' ? '1' : '0',
    'ads_validate_only' => clean_value('qa_test', 10) === '1' && clean_value('ads_validate_only', 10) === '1' ? '1' : '0',
    // This raw, one-time link secret is sent only to n8n for the action URL.
    // It is deliberately excluded from the local CSV log below; the sheet
    // stores only its SHA-256 digest.
    'action_token' => $actionToken,
];

$dataDir = getenv('DCT_DATA_DIR') ?: dirname(__DIR__) . '/dct-private-data';
if (!is_dir($dataDir) && !mkdir($dataDir, 0770, true) && !is_dir($dataDir)) {
    error_log('DCT: unable to create private data directory');
    header('Location: /?form_error=server#enquire', true, 303);
    exit;
}
$logLead = $lead;
unset($logLead['action_token']);
if (!append_csv(rtrim($dataDir, '/') . '/leads.csv', array_keys($logLead), array_values($logLead))) {
    error_log('DCT: unable to write private lead log');
    header('Location: /?form_error=server#enquire', true, 303);
    exit;
}

$isQa = $lead['qa_test'] === '1';
$directMailTo = $isQa ? 'btl101@gmail.com' : 'sales@rivercruisenetwork.com';
$directMailSubject = ($isQa ? '[TEST] ' : '') . '[HOSTING] New DCT lead - ' . mail_safe_value(trim($lead['first_name'] . ' ' . $lead['last_name']));
$directMailHeaders = implode("\r\n", [
    'From: Discount Coach Tours <website@discountcoachtours.ca>',
    'Reply-To: ' . mail_safe_value($email),
    'MIME-Version: 1.0',
    'Content-Type: text/plain; charset=UTF-8',
    'X-DCT-Delivery: hosting-backup',
]);
$directMailStarted = microtime(true);
$directMailStatus = 'rejected';
$directMailError = '';
if (!function_exists('mail')) {
    $directMailError = 'mail_unavailable';
} elseif (mail($directMailTo, $directMailSubject, direct_lead_mail_body($lead), $directMailHeaders)) {
    $directMailStatus = 'accepted';
} else {
    $directMailError = 'mail_returned_false';
}
append_csv(
    rtrim($dataDir, '/') . '/direct-email-deliveries.csv',
    ['attempted_at', 'lead_order_id', 'recipient_class', 'status', 'error', 'duration_ms'],
    [gmdate('c'), $orderId, $isQa ? 'qa' : 'production', $directMailStatus, $directMailError, (string)round((microtime(true) - $directMailStarted) * 1000)]
);

$secretFile = rtrim($dataDir, '/') . '/dct-secrets.php';
$secrets = is_file($secretFile) ? require $secretFile : [];
$token = is_array($secrets) ? (string)($secrets['n8n_token'] ?? '') : '';
$status = 0;
$error = '';
$started = microtime(true);
if ($token === '') {
    $error = 'missing_webhook_token';
} elseif (!function_exists('curl_init')) {
    $error = 'curl_unavailable';
} else {
    $ch = curl_init('https://n8.copperchunk.com/webhook/dct-form');
    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => json_encode($lead, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE),
        CURLOPT_HTTPHEADER => ['Content-Type: application/json', 'X-DCT-Token: ' . $token],
        CURLOPT_USERAGENT => 'Mozilla/5.0 DCT-LeadDelivery/1.0', CURLOPT_RETURNTRANSFER => true,
        CURLOPT_CONNECTTIMEOUT => 3, CURLOPT_TIMEOUT => 5,
    ]);
    curl_exec($ch);
    $status = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $error = (string)curl_error($ch);
    curl_close($ch);
    if ($status !== 200 && $error === '') $error = 'http_' . $status;
}

$deliveryColumns = ['attempted_at', 'lead_order_id', 'http_status', 'error', 'duration_ms'];
$delivery = [gmdate('c'), $orderId, (string)$status, $error, (string)round((microtime(true) - $started) * 1000)];
append_csv(rtrim($dataDir, '/') . '/n8n-deliveries.csv', $deliveryColumns, $delivery);

header('Cache-Control: no-store');
header('Location: /thank-you.html', true, 303);
exit;
