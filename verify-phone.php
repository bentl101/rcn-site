<?php
/**
 * River Cruise Network — Phone Verification Proxy
 * Calls Veriphone API server-side to keep API key hidden from browsers.
 */

// ── Config ──────────────────────────────────────────────────────────────────
// API key loaded from the untracked rcn-secrets.php (see that file to rotate).
$RCN_SECRETS       = is_file(__DIR__ . '/rcn-secrets.php') ? (include __DIR__ . '/rcn-secrets.php') : [];
$VERIPHONE_API_KEY = $RCN_SECRETS['VERIPHONE_API_KEY'] ?? (getenv('VERIPHONE_API_KEY') ?: '');
// ────────────────────────────────────────────────────────────────────────────

header('Content-Type: application/json');
header('X-Content-Type-Options: nosniff');

// Only allow GET
if ($_SERVER['REQUEST_METHOD'] !== 'GET') {
    http_response_code(405);
    echo json_encode(['error' => 'Method not allowed']);
    exit;
}

// Basic rate-limiting via session (max 10 checks per minute)
session_start();
$now = time();
$window = 60;
$max_requests = 10;

if (!isset($_SESSION['phone_checks'])) {
    $_SESSION['phone_checks'] = [];
}

// Purge old entries
$_SESSION['phone_checks'] = array_filter(
    $_SESSION['phone_checks'],
    function ($ts) use ($now, $window) { return ($now - $ts) < $window; }
);

if (count($_SESSION['phone_checks']) >= $max_requests) {
    http_response_code(429);
    echo json_encode(['error' => 'Too many requests. Try again shortly.']);
    exit;
}

$_SESSION['phone_checks'][] = $now;

// Get and validate phone param
$phone = trim($_GET['phone'] ?? '');

if (empty($phone) || strlen($phone) < 6) {
    http_response_code(400);
    echo json_encode(['error' => 'Phone number too short']);
    exit;
}

// Call Veriphone API
$url = 'https://api.veriphone.io/v2/verify?'
     . http_build_query(['phone' => $phone, 'key' => $VERIPHONE_API_KEY]);

$ch = curl_init($url);
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_TIMEOUT        => 8,
    CURLOPT_FOLLOWLOCATION => true,
    CURLOPT_HTTPHEADER     => ['Accept: application/json'],
]);

$response = curl_exec($ch);
$httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
$curlErr  = curl_error($ch);
curl_close($ch);

if ($curlErr || $httpCode >= 500) {
    // API unreachable — fail open so form still works
    echo json_encode(['phone_valid' => true, 'fallback' => true]);
    exit;
}

// Forward the Veriphone response as-is
http_response_code($httpCode);
echo $response;
