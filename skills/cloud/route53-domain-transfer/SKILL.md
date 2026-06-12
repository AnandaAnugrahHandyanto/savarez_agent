---
name: route53-domain-transfer
description: Transfer an existing domain from another registrar to AWS Route 53 using the AWS CLI.
version: 1.0.0
author: Hermes Agent
license: MIT
---

# Route 53 Domain Transfer via CLI

Use this when a user wants to move a domain registration (not just DNS) into Route 53 and they can provide the auth/EPP code plus contact info.

## Prerequisites
- AWS CLI v2 with route53domains service access (Region must be `us-east-1` for registrar operations).
- Domain is older than ICANN-required wait period (typically 60 days since creation or last transfer).
- Domain is unlocked at current registrar, privacy off, and auth/EPP code available.
- Complete registrant contact info (name, organization, email, phone with country code, full address).

## Workflow

### 1. Collect inputs
Ask the user for:
- Domain name (e.g., `example.com`).
- Auth/EPP code (case-sensitive, often emailed).
- Registrant/Admin/Tech/Billing contact details:
  - First name, last name.
  - Organization (or `None`).
  - Email (must contain `@`).
  - Phone in `+<countrycode>.<number>` format (e.g., `+964.7515050551`).
  - Street, city, postal code, country (two-letter code). Many ccTLDs don’t accept state; omit it unless required per country.
- Nameserver preference (existing hosted zone, new hosted zone, or keep current DNS for now). Note: CLI transfer doesn’t auto-create hosted zones; you update NS separately afterward.

### 2. Store contact JSON
Keep a reusable contact file:
```bash
mkdir -p ~/route53-transfer
cat <<'EOF' > ~/route53-transfer/contact.json
{
  "FirstName": "FIRST",
  "LastName": "LAST",
  "ContactType": "PERSON",
  "OrganizationName": "ORG",
  "AddressLine1": "STREET",
  "City": "CITY",
  "CountryCode": "IQ",
  "ZipCode": "44001",
  "PhoneNumber": "+964.7515050551",
  "Email": "user@example.com"
}
EOF
```
Adjust values per user. Leave `State` unset when the TLD doesn’t require it (Iraq example). If multiple address lines exist, add `"AddressLine2": "..."`.

### 3. Build transfer JSON
Use Python (or `jq`) to embed the contact object for all roles:
```bash
python3 - <<'PY'
import json, pathlib
contact = json.loads(pathlib.Path('~/route53-transfer/contact.json').expanduser().read_text())
data = {
    "DomainName": "example.com",
    "DurationInYears": 1,
    "AuthCode": "AUTH-CODE-HERE",
    "AutoRenew": True,
    "AdminContact": contact,
    "RegistrantContact": contact,
    "TechContact": contact,
    "BillingContact": contact,
    "PrivacyProtectAdminContact": True,
    "PrivacyProtectRegistrantContact": True,
    "PrivacyProtectTechContact": True,
    "PrivacyProtectBillingContact": True
}
path = pathlib.Path('~/route53-transfer/transfer-domain.json').expanduser()
path.write_text(json.dumps(data, indent=2))
PY
```
If nameservers must be specified (keeping existing DNS), add a `"Nameservers": [{"Name": "ns1.example.net"}, ...]` array.

### 4. Run transfer command
Execute in `us-east-1`:
```bash
aws route53domains transfer-domain \
  --region us-east-1 \
  --cli-input-json file://~/route53-transfer/transfer-domain.json
```
Output includes an `OperationId`. Save it for status checks.

### 5. Track status
Use:
```bash
aws route53domains get-operation-detail --region us-east-1 --operation-id OPERATION_ID
```
Statuses include `IN_PROGRESS`, `SUCCESSFUL`, `FAILED`. Failures list `Message` details.

### 6. Post-transfer tasks
- Once complete, create/verify a Route 53 hosted zone and update NS records at current DNS if not transferred already.
- Re-enable privacy if needed (already set to true above).
- Configure auto-renew per user preference.

## Pitfalls & Handling
- **60-day rule:** AWS returns `The domain ... has been registered recently`. Inform the user they must wait; set reminder to reattempt later.
- **Phone format errors:** Must be `+CountryCode.Number`. Use a dot separator; spaces/dashes trigger `does not resemble +999.12345678`.
- **State fields:** Some countries (e.g., Iraq) reject `State`; omit entirely.
- **Auth code expiry:** If AWS reports invalid code, request a fresh one from the registrar.
- **Approval emails:** User must approve from both current registrar and AWS; remind them to check inbox/spam.

## Verification
- `get-operation-detail` shows `Status: SUCCESSFUL`.
- Domain appears under Route 53 → Registered domains.
- WHOIS lists Amazon Registrar after propagation.
- Hosted zone nameservers match registrar settings.

Use this skill whenever a manual Route 53 transfer needs to be orchestrated from the CLI.
