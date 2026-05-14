#!/usr/bin/env node

/**
 * CSV Merge Tool - Combine multiple CSVs with deduplication
 *
 * Usage:
 *   ./merge-csv.js \
 *     --input=file1.csv,file2.csv \
 *     --output=combined.csv \
 *     --dedupe-key=search_term  (optional, column name to dedupe on)
 *
 * Features:
 *   - Combines multiple CSV files with same headers
 *   - Deduplicates rows based on a key column (optional)
 *   - Handles quoted CSV values correctly
 *
 * Returns: File path and row count
 */

import { readFileSync, writeFileSync } from 'fs';

// Parse command line arguments
const args = process.argv.slice(2).reduce((acc, arg) => {
    if (arg.includes('=')) {
        const eqIndex = arg.indexOf('=');
        const key = arg.slice(0, eqIndex).replace('--', '');
        const value = arg.slice(eqIndex + 1);
        if (key && value) {
            acc[key] = value;
        }
    }
    return acc;
}, {});

const inputFiles = args['input'] ? args['input'].split(',').map(f => f.trim()) : [];
const outputFile = args['output'];
const dedupeKey = args['dedupe-key'] || null;

// Validate arguments
if (inputFiles.length === 0 || !outputFile) {
    console.error('Error: Missing required arguments');
    console.error('');
    console.error('Usage:');
    console.error('  ./merge-csv.js \\');
    console.error('    --input=file1.csv,file2.csv \\');
    console.error('    --output=combined.csv \\');
    console.error('    --dedupe-key=column_name  (optional)');
    process.exit(1);
}

// Helper: Parse a CSV row handling quoted values
function parseCSVRow(row) {
    const values = [];
    let current = '';
    let inQuotes = false;

    for (let i = 0; i < row.length; i++) {
        const char = row[i];
        if (char === '"') {
            if (inQuotes && row[i + 1] === '"') {
                current += '"';
                i++;
            } else {
                inQuotes = !inQuotes;
            }
        } else if (char === ',' && !inQuotes) {
            values.push(current);
            current = '';
        } else {
            current += char;
        }
    }
    values.push(current);
    return values;
}

try {
    const allRows = [];
    let headers = null;
    let totalInputRows = 0;

    for (const file of inputFiles) {
        let content;
        try {
            content = readFileSync(file, 'utf8');
        } catch (err) {
            console.error(`Warning: Could not read ${file}, skipping`);
            continue;
        }

        const lines = content.split('\n').filter(line => line.trim());

        if (lines.length === 0) {
            console.error(`Warning: ${file} is empty, skipping`);
            continue;
        }

        const fileHeaders = lines[0];
        if (!headers) {
            headers = fileHeaders;
        } else if (headers !== fileHeaders) {
            console.error(`Warning: Header mismatch in ${file}`);
            console.error(`  Expected: ${headers.substring(0, 100)}...`);
            console.error(`  Got: ${fileHeaders.substring(0, 100)}...`);
            console.error('  Skipping file');
            continue;
        }

        // Add data rows (skip header)
        const dataRows = lines.slice(1);
        totalInputRows += dataRows.length;
        allRows.push(...dataRows);
        console.error(`  ${file}: ${dataRows.length} rows`);
    }

    if (!headers) {
        console.error('Error: No valid CSV files found');
        process.exit(1);
    }

    // Deduplicate if key specified
    let finalRows = allRows;
    let duplicatesRemoved = 0;

    if (dedupeKey) {
        const headerArray = parseCSVRow(headers);
        const keyIndex = headerArray.findIndex(h =>
            h.toLowerCase().includes(dedupeKey.toLowerCase()) ||
            h.toLowerCase() === dedupeKey.toLowerCase()
        );

        if (keyIndex === -1) {
            console.error(`Error: Dedupe key '${dedupeKey}' not found in headers`);
            console.error(`Available columns: ${headerArray.join(', ')}`);
            process.exit(1);
        }

        console.error(`Deduplicating on column: ${headerArray[keyIndex]} (index ${keyIndex})`);

        const seen = new Set();
        finalRows = allRows.filter(row => {
            const values = parseCSVRow(row);
            const keyValue = values[keyIndex];
            if (seen.has(keyValue)) {
                return false;
            }
            seen.add(keyValue);
            return true;
        });
        duplicatesRemoved = allRows.length - finalRows.length;
    }

    // Write combined file
    const output = [headers, ...finalRows].join('\n');
    writeFileSync(outputFile, output, 'utf8');

    console.log(`File: ${outputFile}`);
    console.log(`Rows: ${finalRows.length}`);
    if (duplicatesRemoved > 0) {
        console.log(`Duplicates removed: ${duplicatesRemoved}`);
    }

} catch (error) {
    console.error('Error merging CSVs:', error.message);
    process.exit(1);
}
