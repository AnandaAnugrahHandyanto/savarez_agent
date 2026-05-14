#!/usr/bin/env node

/**
 * List all child accounts under an MCC using customer_client query.
 * Usage: node list-accounts.js
 */

import { GoogleAdsApi } from 'google-ads-api';
import { config } from 'dotenv';
import { resolve, dirname } from 'path';
import { existsSync } from 'fs';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
let projectRoot = __dirname;
while (projectRoot !== '/' && !existsSync(resolve(projectRoot, 'config'))) {
    projectRoot = resolve(projectRoot, '..');
}

config({ path: resolve(projectRoot, 'config/.env') });

const client = new GoogleAdsApi({
    client_id: process.env.GOOGLE_ADS_CLIENT_ID,
    client_secret: process.env.GOOGLE_ADS_CLIENT_SECRET,
    developer_token: process.env.GOOGLE_ADS_DEVELOPER_TOKEN,
});

const loginCustomerId = process.env.GOOGLE_ADS_LOGIN_CUSTOMER_ID;

const customer = client.Customer({
    customer_id: loginCustomerId,
    login_customer_id: loginCustomerId,
    refresh_token: process.env.GOOGLE_ADS_REFRESH_TOKEN,
});

async function main() {
    try {
        const query = `
            SELECT
                customer_client.id,
                customer_client.descriptive_name,
                customer_client.currency_code,
                customer_client.time_zone,
                customer_client.manager,
                customer_client.status
            FROM customer_client
            WHERE customer_client.status = 'ENABLED'
            ORDER BY customer_client.id
        `;

        const results = await customer.query(query);

        // Filter out manager accounts (MCCs), show only ad accounts
        const adAccounts = results.filter(r => !r.customer_client?.manager);
        const managerAccounts = results.filter(r => r.customer_client?.manager);

        console.log(`\nMCC: ${loginCustomerId}\n`);
        
        if (managerAccounts.length > 0) {
            console.log(`Sub-MCCs (${managerAccounts.length}):`);
            for (const r of managerAccounts) {
                const c = r.customer_client;
                console.log(`  ${c.id}  ${c.descriptive_name || 'Unnamed'}`);
            }
            console.log('');
        }

        console.log(`Ad Accounts (${adAccounts.length}):`);
        for (const r of adAccounts) {
            const c = r.customer_client;
            console.log(`  ${c.id}  ${c.descriptive_name || 'Unnamed'}  (${c.currency_code || '?'}, ${c.time_zone || '?'})`);
        }
        console.log('');
    } catch (error) {
        console.error('Error:', error.message);
        if (error.errors) {
            error.errors.forEach(err => console.error(`  - ${err.message}`));
        }
        process.exit(1);
    }
}

main();
