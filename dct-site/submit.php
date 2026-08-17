<?php
declare(strict_types=1);

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    header('Location: /', true, 303);
    exit;
}

function clean_value(string $key, int $max = 500): string
{
    $value = $_POST[$key] ?? '';
    if (!is_string($value)) {
        return '';
    }
    $value = trim(strip_tags(str_replace(["\r", "\0"], '', $value)));
    return substr($value, 0, $max);
}

function csv_safe(string $value): string
{
    return preg_match('/^[=+\-@]/', $value) ? "'" . $value : $value;
}

if (clean_value('website', 200) !== '') {
    http_response_code(204);
    exit;
}

$required = ['first_name', 'last_name', 'email', 'phone', 'destination', 'departure_city', 'travel_date', 'duration', 'guests', 'budget', 'pace'];
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

$columns = [
    'submitted_at', 'lead_order_id', 'first_name', 'last_name', 'email', 'phone',
    'destination', 'departure_city', 'travel_date', 'duration', 'guests', 'budget',
    'operator', 'pace', 'notes', 'contact_preference', 'source_page', 'utm_source',
    'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'click_id', 'click_id_type',
    'landing_page', 'referrer', 'time_on_page', 'ip_address', 'user_agent', 'environment'
];

$values = [
    gmdate('c'), $orderId, clean_value('first_name', 100), clean_value('last_name', 100),
    $email, clean_value('phone', 50), clean_value('destination', 200), clean_value('departure_city', 120),
    clean_value('travel_date', 20), clean_value('duration', 50), clean_value('guests', 50),
    clean_value('budget', 50), clean_value('operator', 80), clean_value('pace', 50),
    clean_value('notes', 2000), clean_value('contact_preference', 30), clean_value('source_page', 120),
    clean_value('utm_source', 200), clean_value('utm_medium', 200), clean_value('utm_campaign', 300),
    clean_value('utm_term', 300), clean_value('utm_content', 300), clean_value('click_id', 500),
    clean_value('click_id_type', 30), clean_value('landing_page', 1000), clean_value('referrer', 1000),
    clean_value('time_on_page', 20), substr($_SERVER['REMOTE_ADDR'] ?? '', 0, 64),
    substr($_SERVER['HTTP_USER_AGENT'] ?? '', 0, 500), 'staging'
];

$dataDir = getenv('DCT_DATA_DIR') ?: dirname(__DIR__) . '/dct-private-data';
if (!is_dir($dataDir) && !mkdir($dataDir, 0770, true) && !is_dir($dataDir)) {
    error_log('DCT: unable to create private data directory');
    header('Location: /?form_error=server#enquire', true, 303);
    exit;
}

$path = rtrim($dataDir, '/') . '/leads.csv';
$isNew = !file_exists($path) || filesize($path) === 0;
$handle = fopen($path, 'ab');
if ($handle === false) {
    error_log('DCT: unable to open private lead log');
    header('Location: /?form_error=server#enquire', true, 303);
    exit;
}

if (flock($handle, LOCK_EX)) {
    if ($isNew) {
        fputcsv($handle, $columns);
    }
    fputcsv($handle, array_map('csv_safe', $values));
    fflush($handle);
    flock($handle, LOCK_UN);
}
fclose($handle);

header('Cache-Control: no-store');
header('Location: /thank-you.html', true, 303);
exit;
