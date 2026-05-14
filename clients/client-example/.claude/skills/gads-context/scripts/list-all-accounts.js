#!/usr/bin/env node

/**
 * Recursively list ALL accounts under an MCC, including sub-MCC children.
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

const ROOT_MCC = process.env.GOOGLE_ADS_LOGIN_CUSTOMER_ID;

async function getChildren(loginId, depth = 0) {
    const customer = client.Customer({
        customer_id: loginId,
        login_customer_id: loginId,
        refresh_token: process.env.GOOGLE_ADS_REFRESH_TOKEN,
    });

    const query = `
        SELECT
            customer_client.id,
            customer_client.descriptive_name,
            customer_client.currency_code,
            customer_client.time_zone,
            customer_client.manager,
            customer_client.status
        FROM customer_client
        ORDER BY customer_client.id
    `;

    const prefix = '  '.repeat(depth);
    
    let results;
    try {
        results = await customer.query(query);
    } catch (err) {
        console.log(`${prefix}[MCC] ${loginId}  (access denied)`);
        return [];
    }
    
    const children = [];
    for (const r of results) {
        const c = r.customer_client;
        if (Number(c.id) === Number(loginId)) continue; // skip self
        
        const entry = {
            id: c.id,
            name: c.descriptive_name || 'Unnamed',
            manager: c.manager,
            currency: c.currency_code,
            tz: c.time_zone,
        };
        
        if (c.manager) {
            console.log(`${prefix}[MCC] ${c.id}  ${c.descriptive_name || 'Unnamed'}`);
            entry.children = await getChildren(c.id, depth + 1);
        } else {
            console.log(`${prefix}  ${c.id}  ${c.descriptive_name || 'Unnamed'}  (${c.currency_code || '?'}, ${c.time_zone || '?'})`);
        }
        children.push(entry);
    }
    return children;
}

console.log(`\nFull hierarchy under MCC ${ROOT_MCC}:\n`);
const tree = await getChildren(ROOT_MCC);

// Count totals
function countAccounts(nodes) {
    let ad = 0, mcc = 0;
    for (const n of nodes) {
        if (n.manager) {
            mcc++;
            const sub = countAccounts(n.children || []);
            ad += sub.ad;
            mcc += sub.mcc;
        } else {
            ad++;
        }
    }
    return { ad, mcc };
}

const totals = countAccounts(tree);
console.log(`\nTotals: ${totals.ad} ad accounts, ${totals.mcc} sub-MCCs`);
