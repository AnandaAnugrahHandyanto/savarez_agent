# Kasia Gateway Testnet Smoke Test

1. Create or choose a dedicated Kasia testnet seed phrase for Hermes.
2. Configure:
   - `KASIA_ENABLED=true`
   - `KASIA_SEED_PHRASE=...`
   - `KASIA_INDEXER_URL=...`
   - `KASIA_NODE_WBORSH_URL=...`
   - `KASIA_NETWORK=testnet-10` or your target testnet
   - `KASIA_ALLOWED_USERS=<peer kaspa address>` or `KASIA_ALLOW_ALL_USERS=true`
3. Start the gateway with `source .venv/bin/activate && python -m hermes_cli.main gateway run`.
4. Verify the bridge health endpoint:
   - `curl http://127.0.0.1:3010/health`
   - Confirm `status`, `walletAddress`, and `lastSyncMs` are populated.
5. From a second Kasia client, send the Hermes address an initial handshake.
6. Confirm Hermes auto-responds to the authorized handshake.
7. Send a plain text message from the second client and confirm Hermes receives it.
8. Use Hermes outbound delivery to the active peer:
   - `send_message(target="kasia:<peer_address>", message="hello from hermes")`
9. Restart the gateway and confirm the same Kasia conversation continues without a new handshake.
