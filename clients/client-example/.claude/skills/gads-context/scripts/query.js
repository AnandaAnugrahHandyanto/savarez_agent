#!/usr/bin/env node

/**
 * Google Ads Query Tool - Direct API to CSV
 *
 * Executes Google Ads queries and saves results directly to CSV,
 * bypassing the context window entirely.
 *
 * Usage:
 *   node query.js \
 *     --customer-id=YOUR_CUSTOMER_ID \
 *     --login-customer-id=YOUR_LOGIN_CUSTOMER_ID \
 *     --query-file=references/campaigns.gaql \
 *     --days=30 \
 *     --output=context/google-ads/data/campaigns.csv
 *
 * Flags:
 *   --query="..." or --query-file=path   GAQL query (one required)
 *   --days=N                             Date range (replaces {DATE_RANGE} placeholder)
 *   --no-date-range                      Skip date injection (for current-state queries)
 *   --allow-empty                        Write empty CSV on zero results instead of erroring
 *   --lag-offset=N                       Shift end date back N days (for conversion lag)
 *   --include-experiments                Include experiment campaigns ({EXPERIMENT_FILTER} → empty)
 *
 * Returns: File path and row count only
 */

import { GoogleAdsApi, enums } from 'google-ads-api';
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { config } from 'dotenv';

// Find project root by walking up from script location
const __dirname = dirname(fileURLToPath(import.meta.url));
let _projectRoot = __dirname;
while (_projectRoot !== '/' && !existsSync(resolve(_projectRoot, 'config'))) {
    _projectRoot = resolve(_projectRoot, '..');
}

// Load environment variables from config/.env
config({ path: resolve(_projectRoot, 'config/.env') });

// Parse command line arguments
const args = process.argv.slice(2).reduce((acc, arg) => {
    if (arg.includes('=')) {
        const eqIndex = arg.indexOf('=');
        const key = arg.slice(0, eqIndex).replace('--', '');
        const value = arg.slice(eqIndex + 1);
        if (key && value) {
            acc[key] = value;
        }
    } else if (arg.startsWith('--')) {
        // Boolean flags without values
        acc[arg.replace('--', '')] = true;
    }
    return acc;
}, {});

const customerId = args['customer-id'];
const loginCustomerId = args['login-customer-id'];
let query = args['query'];
const queryFile = args['query-file'];
const outputPath = args['output'];

// If --query-file provided, read GAQL from file instead of --query
if (queryFile && !query) {
    const queryFilePath = resolve(_projectRoot, queryFile);
    if (!existsSync(queryFilePath)) {
        console.error(`Error: Query file not found: ${queryFilePath}`);
        process.exit(1);
    }
    query = readFileSync(queryFilePath, 'utf8').trim();
}
const days = args['days'] ? parseInt(args['days']) : null;
const noDateRange = args['no-date-range'] === true;
const lagOffset = args['lag-offset'] ? parseInt(args['lag-offset']) : 0;
const includeExperiments = args['include-experiments'] === true || args['include-experiments'] === 'true';

// Validate arguments
if (!customerId || !query || !outputPath) {
    console.error('Error: Missing required arguments');
    console.error('');
    console.error('Usage:');
    console.error('  ./google-ads-query.js \\');
    console.error('    --customer-id=YOUR_CUSTOMER_ID \\');
    console.error('    --login-customer-id=YOUR_LOGIN_CUSTOMER_ID \\');
    console.error('    --query="SELECT ... FROM ... WHERE ..." \\');
    console.error('    --query-file=references/campaigns.gaql \\  (alternative to --query)');
    console.error('    --days=30 \\  (optional, replaces {DATE_RANGE} placeholder)');
    console.error('    --no-date-range \\  (optional, skip date injection)');
    console.error('    --allow-empty \\  (optional, write empty CSV on zero results)');
    console.error('    --lag-offset=N \\  (optional, shift end date back N days)');
    console.error('    --include-experiments \\  (optional, keep experiment campaigns)');
    console.error('    --output=/path/to/output.csv');
    process.exit(1);
}

// Validate credentials from environment
const clientId = process.env.GOOGLE_ADS_CLIENT_ID;
const clientSecret = process.env.GOOGLE_ADS_CLIENT_SECRET;
const developerToken = process.env.GOOGLE_ADS_DEVELOPER_TOKEN;
const refreshToken = process.env.GOOGLE_ADS_REFRESH_TOKEN;

if (!clientId || !clientSecret || !developerToken || !refreshToken) {
    console.error('Error: Missing Google Ads credentials');
    console.error('Please set the following in config/.env:');
    console.error('  GOOGLE_ADS_CLIENT_ID');
    console.error('  GOOGLE_ADS_CLIENT_SECRET');
    console.error('  GOOGLE_ADS_DEVELOPER_TOKEN');
    console.error('  GOOGLE_ADS_REFRESH_TOKEN');
    process.exit(1);
}

// Initialize Google Ads API client
const client = new GoogleAdsApi({
    client_id: clientId,
    client_secret: clientSecret,
    developer_token: developerToken,
});

const customer = client.Customer({
    customer_id: customerId,
    login_customer_id: loginCustomerId || customerId,
    refresh_token: refreshToken,
});

// Get account timezone and calculate date range if --days provided
async function getAccountTimezone() {
    const timezoneQuery = 'SELECT customer.time_zone FROM customer LIMIT 1';
    const results = await customer.query(timezoneQuery);
    return results[0]?.customer?.time_zone || 'America/Los_Angeles';
}

function calculateDateRange(numDays, timezone, offsetDays = 0) {
    // Get current date in account timezone
    const now = new Date();
    const todayInTz = new Date(now.toLocaleString('en-US', { timeZone: timezone }));

    // End date is yesterday to avoid partial current-day data
    // If offsetDays > 0, shift end date further back (e.g., for conversion lag)
    const endDate = new Date(todayInTz);
    endDate.setDate(endDate.getDate() - 1 - offsetDays);

    // Inclusive range with exact N days total
    const startDate = new Date(endDate);
    startDate.setDate(startDate.getDate() - (numDays - 1));

    // Format as YYYY-MM-DD
    const formatDate = (date) => {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    };

    return {
        start: formatDate(startDate),
        end: formatDate(endDate)
    };
}

// Execute query and stream to CSV
async function executeQuery() {
    try {
        if (!noDateRange) {
            // Handle date range calculation if --days provided
            if (days) {
                const timezone = await getAccountTimezone();
                const dateRange = calculateDateRange(days, timezone, lagOffset);

                // Replace {DATE_RANGE} placeholder with BETWEEN dates
                query = query.replace(
                    /\{DATE_RANGE\}/g,
                    `BETWEEN '${dateRange.start}' AND '${dateRange.end}'`
                );
            }
        }

        // Replace {EXPERIMENT_FILTER}: default excludes experiments, opt-in keeps them
        query = query.replace(
            /\{EXPERIMENT_FILTER\}/g,
            includeExperiments ? '' : "AND campaign.experiment_type = 'BASE'"
        );

        // Execute the query
        const results = await customer.query(query);

        if (!results || results.length === 0) {
            if (args['allow-empty']) {
                writeFileSync(outputPath, '', 'utf8');
                console.log(`File: ${outputPath}`);
                console.log(`Rows: 0`);
                return;
            }
            console.error('Error: Query returned no results');
            process.exit(1);
        }

        // Flatten nested objects to get all field names
        function flattenRow(obj, prefix = '') {
            const flattened = {};
            for (const [key, value] of Object.entries(obj)) {
                const newKey = prefix ? `${prefix}.${key}` : key;
                if (Array.isArray(value)) {
                    // Handle arrays - extract text from RSA headlines/descriptions
                    if (value.length > 0 && typeof value[0] === 'object' && value[0].text !== undefined) {
                        // Array of objects with 'text' property (e.g., headlines, descriptions)
                        flattened[newKey] = value.map(item => item.text).join(' | ');
                    } else if (value.every(item => typeof item === 'string')) {
                        // Array of strings (e.g., final_urls)
                        flattened[newKey] = value.join(' | ');
                    } else {
                        // Other arrays - JSON stringify
                        flattened[newKey] = JSON.stringify(value);
                    }
                } else if (value && typeof value === 'object') {
                    Object.assign(flattened, flattenRow(value, newKey));
                } else {
                    flattened[newKey] = value;
                }
            }
            return flattened;
        }

        // Flatten all rows and collect all unique headers
        const flattenedResults = results.map(row => flattenRow(row));

        // Resolve enum integer values to human-readable strings
        // Maps flattened field paths to their enum type
        const enumFieldMap = {
            // Keywords & criteria
            'ad_group_criterion.keyword.match_type': enums.KeywordMatchType,
            'ad_group_criterion.status': enums.AdGroupCriterionStatus,
            'ad_group_criterion.approval_status': enums.AdGroupCriterionApprovalStatus,
            'ad_group_criterion.system_serving_status': enums.CriterionSystemServingStatus,
            'ad_group_criterion.type': enums.CriterionType,
            'ad_group_criterion.quality_info.creative_quality_score': enums.QualityScoreBucket,
            'ad_group_criterion.quality_info.post_click_quality_score': enums.QualityScoreBucket,
            'ad_group_criterion.quality_info.search_predicted_ctr': enums.QualityScoreBucket,
            'ad_group_criterion.listing_group.type': enums.ListingGroupType,
            'ad_group_criterion.listing_group.case_value.product_category.level': enums.ProductCategoryLevel,
            'ad_group_criterion.listing_group.case_value.product_type.level': enums.ProductTypeLevel,
            'ad_group_criterion.listing_group.case_value.product_custom_attribute.index': enums.ProductCustomAttributeIndex,
            'campaign_criterion.keyword.match_type': enums.KeywordMatchType,
            'campaign_criterion.type': enums.CriterionType,
            'campaign_criterion.status': enums.CampaignCriterionStatus,
            'campaign_criterion.ad_schedule.day_of_week': enums.DayOfWeek,
            'campaign_criterion.ad_schedule.start_minute': enums.MinuteOfHour,
            'campaign_criterion.ad_schedule.end_minute': enums.MinuteOfHour,
            'campaign_criterion.device.type': enums.Device,
            'campaign_criterion.age_range.type': enums.AgeRangeType,
            'campaign_criterion.gender.type': enums.GenderType,
            'campaign_criterion.income_range.type': enums.IncomeRangeType,
            'ad_group_criterion.age_range.type': enums.AgeRangeType,
            'ad_group_criterion.gender.type': enums.GenderType,
            'ad_group_criterion.income_range.type': enums.IncomeRangeType,
            'ad_group_criterion.parental_status.type': enums.ParentalStatusType,
            'shared_criterion.keyword.match_type': enums.KeywordMatchType,
            // Campaign & ad group
            'campaign.status': enums.CampaignStatus,
            'campaign.advertising_channel_type': enums.AdvertisingChannelType,
            'campaign.bidding_strategy_type': enums.BiddingStrategyType,
            'bidding_strategy.type': enums.BiddingStrategyType,
            'bidding_strategy.status': enums.BiddingStrategyStatus,
            'campaign.target_impression_share.location': enums.TargetImpressionShareLocation,
            'bidding_strategy.target_impression_share.location': enums.TargetImpressionShareLocation,
            'bidding_data_exclusion.scope': enums.SeasonalityEventScope,
            'bidding_data_exclusion.devices': enums.Device,
            'bidding_data_exclusion.advertising_channel_types': enums.AdvertisingChannelType,
            'conversion_value_rule.status': enums.ConversionValueRuleStatus,
            'conversion_value_rule.geo_location_condition.geo_match_type': enums.ValueRuleGeoLocationMatchType,
            'conversion_value_rule.geo_location_condition.excluded_geo_match_type': enums.ValueRuleGeoLocationMatchType,
            'conversion_value_rule.device_condition.device_types': enums.ValueRuleDeviceType,
            'conversion_value_rule.action.operation': enums.ValueRuleOperation,
            'campaign.experiment_type': enums.CampaignExperimentType,
            'campaign.serving_status': enums.CampaignServingStatus,
            'campaign.geo_target_type_setting.positive_geo_target_type': enums.PositiveGeoTargetType,
            'campaign.geo_target_type_setting.negative_geo_target_type': enums.NegativeGeoTargetType,
            'campaign.ad_serving_optimization_status': enums.AdServingOptimizationStatus,
            'ad_group.status': enums.AdGroupStatus,
            'ad_group.type': enums.AdGroupType,
            'ad_group_ad.status': enums.AdGroupAdStatus,
            // Segments
            'segments.ad_network_type': enums.AdNetworkType,
            'segments.device': enums.Device,
            'segments.day_of_week': enums.DayOfWeek,
            'segments.product_channel': enums.ProductChannel,
            'segments.conversion_action_category': enums.ConversionActionCategory,
            // Assets
            'asset.type': enums.AssetType,
            'asset.policy_summary.approval_status': enums.PolicyApprovalStatus,
            'asset.policy_summary.review_status': enums.PolicyReviewStatus,
            'asset.image_asset.mime_type': enums.MimeType,
            'campaign_asset.field_type': enums.AssetFieldType,
            'campaign_asset.status': enums.AssetLinkStatus,
            'campaign_asset.primary_status': enums.AssetLinkPrimaryStatus,
            'ad_group_asset.field_type': enums.AssetFieldType,
            'ad_group_asset.status': enums.AssetLinkStatus,
            'ad_group_asset.primary_status': enums.AssetLinkPrimaryStatus,
            // Conversions
            'conversion_action.status': enums.ConversionActionStatus,
            'conversion_action.type': enums.ConversionActionType,
            'conversion_action.category': enums.ConversionActionCategory,
            'conversion_action.counting_type': enums.ConversionActionCountingType,
            'conversion_action.origin': enums.ConversionOrigin,
            'conversion_action.attribution_model_settings.attribution_model': enums.AttributionModel,
            // Geo
            'geographic_view.location_type': enums.GeoTargetingType,
            // Shopping
            'shopping_product.status': enums.ProductStatus,
            'shopping_product.availability': enums.ProductAvailability,
            'shopping_product.channel': enums.ProductChannel,
            'shopping_product.condition': enums.ProductCondition,
            // Placements
            'group_placement_view.placement_type': enums.PlacementType,
            'detail_placement_view.placement_type': enums.PlacementType,
            'performance_max_placement_view.placement_type': enums.PlacementType,
            'detail_content_suitability_placement_view.placement_type': enums.PlacementType,
            // Shared sets
            'shared_set.type': enums.SharedSetType,
            'shared_set.status': enums.SharedSetStatus,
            'shared_criterion.type': enums.CriterionType,
            // Customer negative criteria
            'customer_negative_criterion.type': enums.CriterionType,
            'customer_negative_criterion.content_label.type': enums.ContentLabelType,
            // Brand safety
            'campaign.video_brand_safety_suitability': enums.BrandSafetySuitability,
            // Campaign shared sets
            'campaign_shared_set.status': enums.CampaignSharedSetStatus,
            // Customizers
            'customizer_attribute.type': enums.CustomizerAttributeType,
            'customizer_attribute.status': enums.CustomizerAttributeStatus,
            'ad_group_customizer.status': enums.CustomizerValueStatus,
            'ad_group_customizer.value.type': enums.CustomizerAttributeType,
            'ad_group_criterion_customizer.status': enums.CustomizerValueStatus,
            'ad_group_criterion_customizer.value.type': enums.CustomizerAttributeType,
            'campaign_customizer.status': enums.CustomizerValueStatus,
            'campaign_customizer.value.type': enums.CustomizerAttributeType,
            'customer_customizer.status': enums.CustomizerValueStatus,
            'customer_customizer.value.type': enums.CustomizerAttributeType,
        };

        for (const row of flattenedResults) {
            for (const [key, value] of Object.entries(row)) {
                if (value !== null && value !== undefined && enumFieldMap[key]) {
                    const label = enumFieldMap[key][value];
                    if (typeof label === 'string') {
                        row[key] = label;
                    }
                }
            }
        }

        // Extract issue codes from JSON arrays (e.g., shopping_product.issues)
        for (const row of flattenedResults) {
            if (row['shopping_product.issues']) {
                try {
                    const issues = JSON.parse(row['shopping_product.issues']);
                    if (Array.isArray(issues)) {
                        row['shopping_product.issue_codes'] = issues
                            .map(i => i.error_code)
                            .filter(Boolean)
                            .join(' | ');
                    }
                } catch {
                    row['shopping_product.issue_codes'] = '';
                }
            }
        }

        // Resolve enum values inside asset_automation_settings JSON arrays
        for (const row of flattenedResults) {
            if (row['campaign.asset_automation_settings']) {
                try {
                    const settings = JSON.parse(row['campaign.asset_automation_settings']);
                    if (Array.isArray(settings)) {
                        const resolved = settings.map(s => ({
                            asset_automation_type: enums.AssetAutomationType[s.asset_automation_type] || s.asset_automation_type,
                            asset_automation_status: enums.AssetAutomationStatus[s.asset_automation_status] || s.asset_automation_status,
                        }));
                        row['campaign.asset_automation_settings'] = JSON.stringify(resolved);
                    }
                } catch {
                    // Leave as-is if parsing fails
                }
            }
        }

        // Convert micros to actual currency values
        // Fields ending in _micros get divided by 1,000,000 and renamed
        // Fields like average_cpc, cost_per_conversion are also in micros
        const microsFields = new Set([
            'metrics.average_cpc',
            'metrics.cost_per_conversion',
            'metrics.average_cost',
            'metrics.cost_per_all_conversions'
        ]);

        const convertedResults = flattenedResults.map(row => {
            const converted = {};
            for (const [key, value] of Object.entries(row)) {
                if (key.endsWith('_micros')) {
                    // Remove _micros suffix and convert value
                    const newKey = key.replace('_micros', '');
                    converted[newKey] = value !== null && value !== undefined && value !== ''
                        ? (Number(value) / 1_000_000).toFixed(2)
                        : value;
                } else if (microsFields.has(key)) {
                    // Known micros fields without _micros suffix
                    converted[key] = value !== null && value !== undefined && value !== ''
                        ? (Number(value) / 1_000_000).toFixed(2)
                        : value;
                } else {
                    converted[key] = value;
                }
            }
            return converted;
        });

        const headersSet = new Set();
        convertedResults.forEach(row => {
            Object.keys(row).forEach(key => headersSet.add(key));
        });
        const headers = Array.from(headersSet).sort();

        // Convert to CSV format
        const csvRows = [];

        // Add header row
        csvRows.push(headers.join(','));

        // Add data rows
        for (const row of convertedResults) {
            const values = headers.map(header => {
                let value = row[header];

                // Escape CSV values
                if (value !== null && value !== undefined) {
                    value = String(value);
                    // Quote if contains comma, quote, or newline
                    if (value.includes(',') || value.includes('"') || value.includes('\n')) {
                        value = `"${value.replace(/"/g, '""')}"`;
                    }
                } else {
                    value = '';
                }

                return value;
            });

            csvRows.push(values.join(','));
        }

        // Write to file
        const csvContent = csvRows.join('\n');
        writeFileSync(outputPath, csvContent, 'utf8');

        // Return minimal output (file path + row count)
        console.log(`File: ${outputPath}`);
        console.log(`Rows: ${results.length}`);

    } catch (error) {
        console.error('Error executing query:', error.message);
        if (error.errors) {
            error.errors.forEach(err => {
                console.error(`  - ${err.error_code?.request_error || 'Unknown error'}: ${err.message}`);
            });
        }
        process.exit(1);
    }
}

// Run the query
executeQuery();
