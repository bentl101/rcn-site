<?php
declare(strict_types=1);

// Include-only production code; never expose a maintenance endpoint or data.
if (PHP_SAPI !== 'cli' && realpath($_SERVER['SCRIPT_FILENAME'] ?? '') === __FILE__) {
    http_response_code(403);
    exit;
}

function dct_lead_csv_columns(): array
{
    // Preserve the original schema, including the two retired form fields.
    return [
        'submitted_at', 'lead_order_id', 'first_name', 'last_name', 'email', 'phone',
        'destination', 'departure_city', 'travel_date', 'duration', 'guests', 'budget',
        'operator', 'pace', 'notes', 'contact_preference', 'source_page', 'utm_source',
        'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'utm_id', 'matchtype',
        'gad_device', 'network', 'adgroupid', 'targetid', 'loc_physical', 'loc_interest',
        'gclid', 'gbraid', 'wbraid', 'click_id', 'click_id_type', 'landing_page', 'referrer',
        'time_on_page', 'device_type', 'browser_language', 'page_load_time',
        'hashed_email', 'hashed_phone', 'ip_address', 'user_agent', 'environment',
        'qa_test', 'ads_validate_only',
    ];
}

function csv_safe(string $value): string
{
    return preg_match('/^[=+\-@]/', $value) ? "'" . $value : $value;
}

function dct_csv_flush($handle): bool
{
    return fflush($handle) && (!function_exists('fsync') || fsync($handle));
}

function dct_csv_write_all($handle, string $bytes): bool
{
    $offset = 0;
    $length = strlen($bytes);
    while ($offset < $length) {
        $written = fwrite($handle, substr($bytes, $offset));
        if ($written === false || $written === 0) return false;
        $offset += $written;
    }
    return true;
}

function dct_csv_rows($handle): array
{
    $rows = [];
    while (($row = fgetcsv($handle, 0, ',', '"', '\\')) !== false) $rows[] = $row;
    if (!feof($handle)) throw new RuntimeException('CSV read failed');
    return $rows;
}

function dct_csv_replace_locked($handle, string $bytes): bool
{
    if (!rewind($handle) || !dct_csv_write_all($handle, $bytes)
        || !ftruncate($handle, strlen($bytes)) || !dct_csv_flush($handle)
        || !rewind($handle)) return false;
    return stream_get_contents($handle) === $bytes;
}

/** Repair only the known 48-header/46-row transition, preserving all values.
 * The same-inode lock also protects requests still running the old append code.
 * A private, exclusive-create, verified backup is required before any rewrite.
 */
function dct_repair_lead_csv(string $path): bool
{
    if (!file_exists($path)) return true;
    $handle = @fopen($path, 'r+b');
    if ($handle === false) return false;
    try {
        if (!flock($handle, LOCK_EX)) return false;
        $original = stream_get_contents($handle);
        if ($original === false) return false;
        if ($original === '') return true;
        if (!rewind($handle)) return false;
        $rows = dct_csv_rows($handle);
        $columns = dct_lead_csv_columns();
        if (($rows[0] ?? null) !== $columns) return false;
        $shortColumns = array_values(array_diff($columns, ['departure_city', 'pace']));
        $changed = false;
        foreach ($rows as $index => $row) {
            if ($index === 0 || count($row) === count($columns)) continue;
            if (count($row) !== count($shortColumns)) return false;
            $named = array_combine($shortColumns, $row);
            $rows[$index] = array_map(static fn($column) => $named[$column] ?? '', $columns);
            $changed = true;
        }
        if (!$changed) return true;

        $buffer = fopen('php://temp', 'w+b');
        if ($buffer === false) return false;
        try {
            foreach ($rows as $row) {
                // Historical fields are already escaped: do not csv_safe twice.
                if (fputcsv($buffer, $row, ',', '"', '\\') === false) return false;
            }
            rewind($buffer);
            $repaired = stream_get_contents($buffer);
            rewind($buffer);
            if ($repaired === false || dct_csv_rows($buffer) !== $rows) return false;
        } finally {
            fclose($buffer);
        }

        $backupPath = $path . '.schema-backup-' . gmdate('Ymd-His') . '-' . bin2hex(random_bytes(6));
        $mask = umask(0077);
        try {
            $backup = @fopen($backupPath, 'x+b');
        } finally {
            umask($mask);
        }
        if ($backup === false) return false;
        try {
            if (!chmod($backupPath, 0600) || !dct_csv_write_all($backup, $original)
                || !dct_csv_flush($backup) || !rewind($backup)
                || stream_get_contents($backup) !== $original) return false;
        } finally {
            fclose($backup);
        }
        if (!dct_csv_replace_locked($handle, $repaired)) {
            if (!dct_csv_replace_locked($handle, $original)) {
                error_log('DCT: CSV repair and restore failed; recover private schema backup');
            }
            return false;
        }
        return true;
    } catch (Throwable $error) {
        error_log('DCT: private CSV schema check failed');
        return false;
    } finally {
        flock($handle, LOCK_UN);
        fclose($handle);
    }
}

/** Header-aware, lock-first append for leads and delivery audit logs. */
function append_csv(string $path, array $columns, array $row): bool
{
    if (!$columns || count($columns) !== count($row)
        || count(array_unique($columns)) !== count($columns) || in_array('', $columns, true)) return false;
    $handle = @fopen($path, 'c+b');
    if ($handle === false) return false;
    try {
        if (!flock($handle, LOCK_EX)) return false;
        $stat = fstat($handle);
        if ($stat === false) return false;
        $size = $stat['size'];
        $header = $size === 0 ? $columns : fgetcsv($handle, 0, ',', '"', '\\');
        if (!is_array($header) || count(array_unique($header)) !== count($header)
            || in_array('', $header, true) || array_diff($columns, $header)) return false;
        $named = array_combine($columns, $row);
        $ordered = array_map(static fn($column) => csv_safe((string)($named[$column] ?? '')), $header);
        // Refuse an incomplete last line rather than concatenate two records.
        if ($size > 0) {
            if (fseek($handle, -1, SEEK_END) !== 0 || fread($handle, 1) !== "\n") return false;
        }
        if (fseek($handle, 0, SEEK_END) !== 0) return false;
        $ok = ($size !== 0 || fputcsv($handle, $header, ',', '"', '\\') !== false)
            && fputcsv($handle, $ordered, ',', '"', '\\') !== false && dct_csv_flush($handle);
        if (!$ok) {
            // Do not leave a partial new record or header after an I/O failure.
            if (!ftruncate($handle, $size) || !dct_csv_flush($handle)) {
                error_log('DCT: CSV append rollback failed');
            }
        }
        return $ok;
    } finally {
        flock($handle, LOCK_UN);
        fclose($handle);
    }
}
