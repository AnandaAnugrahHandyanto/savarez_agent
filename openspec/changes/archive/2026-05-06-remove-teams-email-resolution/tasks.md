## 1. Code Removal

- [x] 1.1 Delete `plugins/platforms/teams/graph_client.py`
- [x] 1.2 Remove `GraphClient` imports and instantiation from `plugins/platforms/teams/adapter.py`
- [x] 1.3 Remove email extraction logic and `user_id_alt` assignment from `TeamsAdapter._on_message`

## 2. Documentation Updates

- [x] 2.1 Update `website/docs/user-guide/messaging/teams.md` to instruct users to configure raw AAD Object IDs and Channel IDs using YAML comments for human readability
- [x] 2.2 Update `notes/setup_hermes/setup-hermes-team-gateway.md` (or relevant setup instructions) to remove references to the `User.Read.All` Azure AD Graph API permission

## 3. Testing and Validation

- [x] 3.1 Update or remove unit tests in `tests/gateway/test_teams_graph.py` to reflect the removal of the Graph Client
- [x] 3.2 Validate the gateway successfully starts and processes messages using raw ID matching rules

## 4. Operational Enhancements

- [x] 4.1 Remove spammy `TeamsAdapter dropping message` warning from `adapter.py` for unmentioned background messages
- [x] 4.2 Silence `opentelemetry.context` in `hermes_logging.py` to prevent massive stack traces from polluting logs when LLM streaming connections drop
- [x] 4.3 Inject MS Teams Bot Token into `cache_image_from_url` headers to successfully download image attachments and avoid `401 Unauthorized` errors
