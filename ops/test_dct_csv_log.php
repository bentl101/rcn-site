<?php
declare(strict_types=1);

// Isolated synthetic fixtures only. Run: php ops/test_dct_csv_log.php
require dirname(__DIR__) . '/dct-site/csv-log.php';
$testDir = sys_get_temp_dir() . '/dct-csv-test-' . bin2hex(random_bytes(8));
mkdir($testDir, 0700);
$checks = 0;
function check(bool $condition, string $message): void
{
    global $checks;
    if (!$condition) throw new RuntimeException($message);
    $checks++;
}
function fixture(string $path, array $rows): void
{
    $handle = fopen($path, 'wb');
    foreach ($rows as $row) fputcsv($handle, $row, ',', '"', '\\');
    fclose($handle);
}
function rows(string $path): array
{
    $handle = fopen($path, 'rb');
    try { return dct_csv_rows($handle); } finally { fclose($handle); }
}
$columns = dct_lead_csv_columns();
$short = array_values(array_diff($columns, ['departure_city', 'pace']));
$old = array_map(static fn($column) => 'old-' . $column, $columns);
$named = array_fill_keys($short, '');
$named['lead_order_id'] = 'DCT-20261010-120000-00000001';
$named['notes'] = "Quotation \"test\", café\nSecond line; backslash \\ and slash /";
$named['phone'] = "'+15555550100";
$named['gclid'] = 'dummy-click-not-for-google';
$named['qa_test'] = '1';
$named['ads_validate_only'] = '0';
$expected = array_map(static fn($column) => $named[$column] ?? '', $columns);

$path = $testDir . '/leads.csv';
fixture($path, [$columns, $old, array_values($named)]);
$before = file_get_contents($path);
$inode = fileinode($path);
check(dct_repair_lead_csv($path), 'mixed-schema repair');
check(rows($path) === [$columns, $old, $expected], 'all original values and field positions preserved');
check(fileinode($path) === $inode, 'repair keeps inode for concurrent legacy writers');
$backups = glob($path . '.schema-backup-*');
check(count($backups) === 1, 'one repair backup');
check(file_get_contents($backups[0]) === $before, 'backup exactly equals original bytes');
check((fileperms($backups[0]) & 0777) === 0600, 'backup is private');
$after = file_get_contents($path);
check(dct_repair_lead_csv($path), 'second repair succeeds');
check(file_get_contents($path) === $after && glob($path . '.schema-backup-*') === $backups, 'repair is idempotent');

foreach ([[$columns, ['wrong-width']], [['unknown-header'], ['value']]] as $index => $invalidRows) {
    $invalid = $testDir . '/invalid-' . $index . '.csv';
    fixture($invalid, $invalidRows);
    $bytes = file_get_contents($invalid);
    check(!dct_repair_lead_csv($invalid), 'reject unknown schema/row');
    check(file_get_contents($invalid) === $bytes && glob($invalid . '.schema-backup-*') === [], 'invalid input remains untouched');
}
check(dct_repair_lead_csv($testDir . '/absent.csv'), 'absent log is safe');
check(!file_exists($testDir . '/absent.csv'), 'preflight creates no empty log');

$fresh = $testDir . '/fresh.csv';
check(append_csv($fresh, $columns, $expected), 'new canonical file');
check(rows($fresh) === [$columns, $expected], 'canonical 48-field new row');
$ordered = $testDir . '/ordered.csv';
fixture($ordered, [['second', 'retired', 'first']]);
check(append_csv($ordered, ['first', 'second'], ['=formula', 'two']), 'header-aware mapping');
check(rows($ordered)[1] === ['two', '', "'=formula"], 'mapping, blank retired field, formula escaping');
$bytes = file_get_contents($ordered);
check(!append_csv($ordered, ['unexpected'], ['value']), 'reject unknown field without dropping it');
check(!append_csv($ordered, ['first', 'first'], ['a', 'b']), 'reject duplicate field');
check(!append_csv($ordered, ['first'], []), 'reject mismatched values');
check(file_get_contents($ordered) === $bytes, 'rejected appends leave file unchanged');
$partial = $testDir . '/partial.csv';
file_put_contents($partial, "first,second\na,b");
check(!append_csv($partial, ['first', 'second'], ['c', 'd']), 'reject unterminated final row');
check(file_get_contents($partial) === "first,second\na,b", 'partial final row untouched');

// Backup failure must prevent mutation even when the existing file is writable.
$blockedDir = $testDir . '/no-backup';
mkdir($blockedDir, 0700);
$blocked = $blockedDir . '/leads.csv';
fixture($blocked, [$columns, array_values($named)]);
$blockedBefore = file_get_contents($blocked);
chmod($blockedDir, 0500);
check(!dct_repair_lead_csv($blocked), 'backup creation failure aborts repair');
check(file_get_contents($blocked) === $blockedBefore, 'backup failure preserves original');
chmod($blockedDir, 0700);

// Many simultaneous first writes must produce exactly one header, no lost rows.
if (!function_exists('pcntl_fork')) throw new RuntimeException('pcntl required for concurrency tests');
$parallel = $testDir . '/parallel.csv';
$children = [];
for ($i = 0; $i < 20; $i++) {
    $pid = pcntl_fork();
    if ($pid === 0) exit(append_csv($parallel, ['id', 'value'], [(string)$i, 'test']) ? 0 : 1);
    $children[] = $pid;
}
foreach ($children as $pid) {
    pcntl_waitpid($pid, $status);
    check(pcntl_wexitstatus($status) === 0, 'parallel append succeeded');
}
$parallelRows = rows($parallel);
check(count($parallelRows) === 21 && $parallelRows[0] === ['id', 'value'], 'one header and all 20 concurrent records');
check(count(array_unique(array_column(array_slice($parallelRows, 1), 0))) === 20, 'concurrent IDs unique and retained');

// An old handler may already hold an append descriptor before the repair.
$legacy = fopen($path, 'ab');
check(dct_repair_lead_csv($path), 'repair while old descriptor is open');
flock($legacy, LOCK_EX);
fputcsv($legacy, array_values($named), ',', '"', '\\');
fflush($legacy);
flock($legacy, LOCK_UN);
fclose($legacy);
check(dct_repair_lead_csv($path), 'late legacy append also repaired');
check(rows($path) === [$columns, $old, $expected, $expected], 'late legacy append not stranded or lost');

// Run real handler with an empty POST: repairs only; cannot email/create a lead.
$handlerDir = $testDir . '/handler';
mkdir($handlerDir, 0700);
fixture($handlerDir . '/leads.csv', [$columns, array_values($named)]);
$handlerBefore = file_get_contents($handlerDir . '/leads.csv');
$handler = dirname(__DIR__) . '/dct-site/submit.php';
foreach (['GET', 'POST', 'POST'] as $method) {
    $code = 'putenv(' . var_export('DCT_DATA_DIR=' . $handlerDir, true) . ');'
        . '$_SERVER["REQUEST_METHOD"]=' . var_export($method, true) . ';$_POST=[];require ' . var_export($handler, true) . ';';
    $proc = proc_open([PHP_BINARY, '-d', 'disable_functions=mail,curl_init', '-r', $code],
        [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes);
    fclose($pipes[0]);
    $output = stream_get_contents($pipes[1]); fclose($pipes[1]);
    $errors = stream_get_contents($pipes[2]); fclose($pipes[2]);
    check(proc_close($proc) === 0 && $output === '' && $errors === '', 'handler ' . $method . ' clean exit');
    if ($method === 'GET') check(file_get_contents($handlerDir . '/leads.csv') === $handlerBefore, 'GET is non-mutating');
    else check(rows($handlerDir . '/leads.csv') === [$columns, $expected], 'empty POST repairs only');
}
check(count(glob($handlerDir . '/*')) === 2, 'empty POST creates only one backup, no lead or delivery audit');

// Complete the handler in an isolated process with mail/cURL disabled and no
// secrets present: exercise new-row persistence, QA flags and audit schemas.
$validDir = $testDir . '/valid-handler';
mkdir($validDir, 0700);
$post = [
    'first_name' => 'Synthetic', 'last_name' => 'QA', 'email' => 'nobody@example.invalid',
    'phone' => '+15555550100', 'destination' => 'Italy', 'travel_date' => '2027-06',
    'duration' => 'Flexible', 'guests' => '2', 'budget' => 'Flexible',
    'lead_order_id' => 'DCT-20261010-120000-00000002', 'operator' => 'Trafalgar Tours',
    'qa_test' => '1', 'gclid' => 'synthetic-never-upload',
];
$code = 'putenv(' . var_export('DCT_DATA_DIR=' . $validDir, true) . ');'
    . '$_SERVER["REQUEST_METHOD"]="POST";$_POST=' . var_export($post, true)
    . ';require ' . var_export($handler, true) . ';';
$proc = proc_open([PHP_BINARY, '-d', 'disable_functions=mail,curl_init', '-r', $code],
    [0 => ['pipe', 'r'], 1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes);
fclose($pipes[0]);
$output = stream_get_contents($pipes[1]); fclose($pipes[1]);
$errors = stream_get_contents($pipes[2]); fclose($pipes[2]);
check(proc_close($proc) === 0 && $output === '' && $errors === '', 'valid isolated handler clean exit');
$validRows = rows($validDir . '/leads.csv');
check($validRows[0] === $columns && count($validRows[1]) === 48 && count($validRows) === 2, 'handler writes canonical row');
$validLead = array_combine($columns, $validRows[1]);
check($validLead['qa_test'] === '1' && $validLead['ads_validate_only'] === '0'
    && $validLead['gclid'] === $post['gclid'] && $validLead['operator'] === $post['operator']
    && $validLead['travel_date'] === $post['travel_date'], 'handler field alignment');
check($validLead['departure_city'] === '' && $validLead['pace'] === '' && !in_array('action_token', $columns, true), 'retired fields blank and action token excluded');
check(rows($validDir . '/direct-email-deliveries.csv')[1][4] === 'mail_unavailable', 'no real email sent');
check(rows($validDir . '/n8n-deliveries.csv')[1][3] === 'missing_webhook_token', 'no real webhook or Ads upload');
echo 'PASS: ' . $checks . " checks; synthetic fixtures only; " . $testDir . "\n";
