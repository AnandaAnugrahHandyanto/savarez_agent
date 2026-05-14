#!/usr/bin/env node

/**
 * Use google-auth-library for desktop OAuth flow.
 * Opens a browser, handles the redirect via a local server, saves the refresh token.
 */

import { readFileSync, writeFileSync, existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { config as dotenvConfig } from 'dotenv';
import { OAuth2Client } from 'google-auth-library';
import http from 'http';
import { exec } from 'child_process';

const __dirname = dirname(fileURLToPath(import.meta.url));
let projectRoot = __dirname;
while (projectRoot !== '/' && !existsSync(resolve(projectRoot, 'config'))) {
    projectRoot = resolve(projectRoot, '..');
}

const envPath = resolve(projectRoot, 'config/.env');
dotenvConfig({ path: envPath });

const CLIENT_ID = process.env.GOOGLE_ADS_CLIENT_ID;
const CLIENT_SECRET = process.env.GOOGLE_ADS_CLIENT_SECRET;

const oauth2Client = new OAuth2Client(
    CLIENT_ID,
    CLIENT_SECRET,
    'http://localhost:3000'
);

const authUrl = oauth2Client.generateAuthUrl({
    access_type: 'offline',
    scope: 'https://www.googleapis.com/auth/adwords',
    prompt: 'consent',
});

console.log('\nOpening browser for Google OAuth...\n');
console.log(`If browser doesn't open, go to: ${authUrl}\n`);

// Try to open browser
exec('xdg-open ' + JSON.stringify(authUrl), () => {});

// Start local server to catch redirect
const server = http.createServer(async (req, res) => {
    const url = new URL(req.url, 'http://localhost:3000');
    const code = url.searchParams.get('code');

    if (!code) {
        res.writeHead(200);
        res.end('Waiting for authorization...');
        return;
    }

    try {
        const { tokens } = await oauth2Client.getToken(code);

        let envContent = readFileSync(envPath, 'utf8');
        envContent = envContent.replace(
            /GOOGLE_ADS_REFRESH_TOKEN=.*/,
            `GOOGLE_ADS_REFRESH_TOKEN=${tokens.refresh_token}`
        );
        writeFileSync(envPath, envContent);

        res.writeHead(200, { 'Content-Type': 'text/html' });
        res.end('<h1>✅ Done</h1><p>Refresh token saved. Close this window.</p>');

        console.log('\n✅ Refresh token saved to config/.env\n');
        server.close();
        process.exit(0);
    } catch (err) {
        res.writeHead(500);
        res.end('Error: ' + err.message);
        console.error('Error:', err.message);
        server.close();
        process.exit(1);
    }
});

server.listen(3000, () => {
    console.log('Listening on http://localhost:3000 for callback...\n');
});

// Timeout after 5 minutes
setTimeout(() => {
    console.error('\nTimed out waiting for authorization.');
    server.close();
    process.exit(1);
}, 300000);
