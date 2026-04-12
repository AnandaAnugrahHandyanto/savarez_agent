     1|"""Matrix gateway adapter.
     2|
     3|Connects to any Matrix homeserver (self-hosted or matrix.org) via the
     4|mautrix Python SDK.  Supports optional end-to-end encryption (E2EE)
     5|when installed with ``pip install "mautrix[encryption]"``.
     6|
     7|Environment variables:
     8|    MATRIX_HOMESERVER           Homeserver URL (e.g. https://matrix.example.org)
     9|    MATRIX_ACCESS_TOKEN         Access token (preferred auth method)
    10|    MATRIX_USER_ID              Full user ID (@bot:server) — required for password login
    11|    MATRIX_PASSWORD             Password (alternative to access token)
    12|    MATRIX_ENCRYPTION           Set "true" to enable E2EE
    13|    MATRIX_DEVICE_ID            Stable device ID for E2EE persistence across restarts
    14|    MATRIX_ALLOWED_USERS    Comma-separated Matrix user IDs (@user:server)
    15|    MATRIX_HOME_ROOM        Room ID for cron/notification delivery
    16|    MATRIX_REACTIONS        Set "false" to disable processing lifecycle reactions
    17|                            (eyes/checkmark/cross). Default: true
    18|    MATRIX_REQUIRE_MENTION      Require @mention in rooms (default: true)
    19|    MATRIX_FREE_RESPONSE_ROOMS  Comma-separated room IDs exempt from mention requirement
    20|    MATRIX_AUTO_THREAD          Auto-create threads for room messages (default: true)
    21|    MATRIX_RECOVERY_KEY         Recovery key for cross-signing verification after device key rotation
    22|    MATRIX_DM_MENTION_THREADS   Create a thread when bot is @mentioned in a DM (default: false)
    23|"""
    24|
    25|from __future__ import annotations
    26|
    27|import asyncio
    28|import logging
    29|import mimetypes
    30|import os
    31|import re
    32|import time
    33|from html import escape as _html_escape
    34|from pathlib import Path
    35|from typing import Any, Dict, Optional, Set
    36|from dataclasses import dataclass
    37|
    38|try:
    39|    from mautrix.types import (
    40|        ContentURI,
    41|        EventID,
    42|        EventType,
    43|        PaginationDirection,
    44|        PresenceState,
    45|        RoomCreatePreset,
    46|        RoomID,
    47|        SyncToken,
    48|        TrustState,
    49|        UserID,
    50|    )
    51|except ImportError:
    52|    # Stubs so the module is importable without mautrix installed.
    53|    # check_matrix_requirements() will return False and the adapter
    54|    # won't be instantiated in production, but tests may exercise
    55|    # adapter methods so stubs must have the right attributes.
    56|    ContentURI = EventID = RoomID = SyncToken = UserID = str  # type: ignore[misc,assignment]
    57|
    58|    class _EventTypeStub:  # type: ignore[no-redef]
    59|        ROOM_MESSAGE = "m.room.message"
    60|        REACTION = "m.reaction"
    61|        ROOM_ENCRYPTED = "m.room.encrypted"
    62|        ROOM_NAME = "m.room.name"
    63|    EventType = _EventTypeStub  # type: ignore[misc,assignment]
    64|
    65|    class _PaginationDirectionStub:  # type: ignore[no-redef]
    66|        BACKWARD = "b"
    67|        FORWARD = "f"
    68|
    69|    PaginationDirection = _PaginationDirectionStub  # type: ignore[misc,assignment]
    70|
    71|    class _PresenceStateStub:  # type: ignore[no-redef]
    72|        ONLINE = "online"
    73|        OFFLINE = "offline"
    74|        UNAVAILABLE = "unavailable"
    75|
    76|    PresenceState = _PresenceStateStub  # type: ignore[misc,assignment]
    77|
    78|    class _RoomCreatePresetStub:  # type: ignore[no-redef]
    79|        PRIVATE = "private_chat"
    80|        PUBLIC = "public_chat"
    81|        TRUSTED_PRIVATE = "trusted_private_chat"
    82|
    83|    RoomCreatePreset = _RoomCreatePresetStub  # type: ignore[misc,assignment]
    84|
    85|    class _TrustStateStub:  # type: ignore[no-redef]
    86|        UNVERIFIED = 0
    87|        VERIFIED = 1
    88|
    89|    TrustState = _TrustStateStub  # type: ignore[misc,assignment]
    90|
    91|from gateway.config import Platform, PlatformConfig
    92|from gateway.platforms.base import (
    93|    BasePlatformAdapter,
    94|    MessageEvent,
    95|    MessageType,
    96|    ProcessingOutcome,
    97|    SendResult,
    98|)
    99|from gateway.platforms.helpers import ThreadParticipationTracker
   100|
   101|logger = logging.getLogger(__name__)
   102|
   103|
   104|@dataclass
   105|class _MatrixApprovalPrompt:
   106|    """Tracks a pending Matrix reaction-based exec approval prompt."""
   107|
   108|    session_key: str
   109|    chat_id: str
   110|    message_id: str
   111|    resolved: bool = False
   112|
   113|# Matrix message size limit (4000 chars practical, spec has no hard limit
   114|# but clients render poorly above this).
   115|MAX_MESSAGE_LENGTH = 4000
   116|
   117|# Store directory for E2EE keys and sync state.
   118|# Uses get_hermes_home() so each profile gets its own Matrix store.
   119|from hermes_constants import get_hermes_dir as _get_hermes_dir
   120|
   121|_STORE_DIR = _get_hermes_dir("platforms/matrix/store", "matrix/store")
   122|_CRYPTO_DB_PATH = _STORE_DIR / "crypto.db"
   123|
   124|# Grace period: ignore messages older than this many seconds before startup.
   125|_STARTUP_GRACE_SECONDS = 5
   126|
   127|
   128|_E2EE_INSTALL_HINT = (
   129|    "Install with: pip install 'mautrix[encryption]'  (requires libolm C library)"
   130|)
   131|
   132|
   133|def _check_e2ee_deps() -> bool:
   134|    """Return True if mautrix E2EE dependencies (python-olm) are available."""
   135|    try:
   136|        from mautrix.crypto import OlmMachine  # noqa: F401
   137|
   138|        return True
   139|    except (ImportError, AttributeError):
   140|        return False
   141|
   142|
   143|def check_matrix_requirements() -> bool:
   144|    """Return True if the Matrix adapter can be used."""
   145|    token = os.getenv("MATRIX_ACCESS_TOKEN", "")
   146|    password = os.getenv("MATRIX_PASSWORD", "")
   147|    homeserver = os.getenv("MATRIX_HOMESERVER", "")
   148|
   149|    if not token and not password:
   150|        logger.debug("Matrix: neither MATRIX_ACCESS_TOKEN nor MATRIX_PASSWORD set")
   151|        return False
   152|    if not homeserver:
   153|        logger.warning("Matrix: MATRIX_HOMESERVER not set")
   154|        return False
   155|    try:
   156|        import mautrix  # noqa: F401
   157|    except ImportError:
   158|        logger.warning(
   159|            "Matrix: mautrix not installed. Run: pip install 'mautrix[encryption]'"
   160|        )
   161|        return False
   162|
   163|    # If encryption is requested, verify E2EE deps are available at startup
   164|    # rather than silently degrading to plaintext-only at connect time.
   165|    encryption_requested = os.getenv("MATRIX_ENCRYPTION", "").lower() in (
   166|        "true",
   167|        "1",
   168|        "yes",
   169|    )
   170|    if encryption_requested and not _check_e2ee_deps():
   171|        logger.error(
   172|            "Matrix: MATRIX_ENCRYPTION=true but E2EE dependencies are missing. %s. "
   173|            "Without this, encrypted rooms will not work. "
   174|            "Set MATRIX_ENCRYPTION=false to disable E2EE.",
   175|            _E2EE_INSTALL_HINT,
   176|        )
   177|        return False
   178|
   179|    return True
   180|
   181|
   182|class _CryptoStateStore:
   183|    """Adapter that satisfies the mautrix crypto StateStore interface.
   184|
   185|    OlmMachine requires a StateStore with ``is_encrypted``,
   186|    ``get_encryption_info``, and ``find_shared_rooms``.  The basic
   187|    ``MemoryStateStore`` from ``mautrix.client`` doesn't implement these,
   188|    so we provide simple implementations that consult the client's room
   189|    state.
   190|    """
   191|
   192|    def __init__(self, client_state_store: Any, joined_rooms: set):
   193|        self._ss = client_state_store
   194|        self._joined_rooms = joined_rooms
   195|
   196|    async def is_encrypted(self, room_id: str) -> bool:
   197|        return (await self.get_encryption_info(room_id)) is not None
   198|
   199|    async def get_encryption_info(self, room_id: str):
   200|        if hasattr(self._ss, "get_encryption_info"):
   201|            return await self._ss.get_encryption_info(room_id)
   202|        return None
   203|
   204|    async def find_shared_rooms(self, user_id: str) -> list:
   205|        # Return all joined rooms — simple but correct for a single-user bot.
   206|        return list(self._joined_rooms)
   207|
   208|
   209|class MatrixAdapter(BasePlatformAdapter):
   210|    """Gateway adapter for Matrix (any homeserver)."""
   211|
   212|    # Threshold for detecting Matrix client-side message splits.
   213|    # When a chunk is near the ~4000-char practical limit, a continuation
   214|    # is almost certain.
   215|    _SPLIT_THRESHOLD = 3900
   216|
   217|    def __init__(self, config: PlatformConfig):
   218|        super().__init__(config, Platform.MATRIX)
   219|
   220|        self._homeserver: str = (
   221|            config.extra.get("homeserver", "") or os.getenv("MATRIX_HOMESERVER", "")
   222|        ).rstrip("/")
   223|        self._access_token: str = config.token or os.getenv("MATRIX_ACCESS_TOKEN", "")
   224|        self._user_id: str = config.extra.get("user_id", "") or os.getenv(
   225|            "MATRIX_USER_ID", ""
   226|        )
   227|        self._password: str = config.extra.get("password", "") or os.getenv(
   228|            "MATRIX_PASSWORD", ""
   229|        )
   230|        self._encryption: bool = config.extra.get(
   231|            "encryption",
   232|            os.getenv("MATRIX_ENCRYPTION", "").lower() in ("true", "1", "yes"),
   233|        )
   234|        self._device_id: str = config.extra.get("device_id", "") or os.getenv(
   235|            "MATRIX_DEVICE_ID", ""
   236|        )
   237|
   238|        self._client: Any = None  # mautrix.client.Client
   239|        self._crypto_db: Any = None  # mautrix.util.async_db.Database
   240|        self._sync_task: Optional[asyncio.Task] = None
   241|        self._closing = False
   242|        self._startup_ts: float = 0.0
   243|
   244|        # Cache: room_id → bool (is DM)
   245|        self._dm_rooms: Dict[str, bool] = {}
   246|        # Set of room IDs we've joined
   247|        self._joined_rooms: Set[str] = set()
   248|        # Event deduplication (bounded deque keeps newest entries)
   249|        from collections import deque
   250|
   251|        self._processed_events: deque = deque(maxlen=1000)
   252|        self._processed_events_set: set = set()
   253|
   254|        # Buffer for undecrypted events pending key receipt.
   255|        # Each entry: (room_id, event, timestamp)
   256|
   257|        # Thread participation tracking (for require_mention bypass)
   258|        self._threads = ThreadParticipationTracker("matrix")
   259|
   260|        # Mention/thread gating — parsed once from env vars.
   261|        self._require_mention: bool = os.getenv(
   262|            "MATRIX_REQUIRE_MENTION", "true"
   263|        ).lower() not in ("false", "0", "no")
   264|        free_rooms_raw = os.getenv("MATRIX_FREE_RESPONSE_ROOMS", "")
   265|        self._free_rooms: Set[str] = {
   266|            r.strip() for r in free_rooms_raw.split(",") if r.strip()
   267|        }
   268|        self._auto_thread: bool = os.getenv("MATRIX_AUTO_THREAD", "true").lower() in (
   269|            "true",
   270|            "1",
   271|            "yes",
   272|        )
   273|        self._dm_mention_threads: bool = os.getenv(
   274|            "MATRIX_DM_MENTION_THREADS", "false"
   275|        ).lower() in ("true", "1", "yes")
   276|
   277|        # Reactions: configurable via MATRIX_REACTIONS (default: true).
   278|        self._reactions_enabled: bool = os.getenv(
   279|            "MATRIX_REACTIONS", "true"
   280|        ).lower() not in ("false", "0", "no")
   281|        self._pending_reactions: dict[tuple[str, str], str] = {}
   282|
   283|        # Text batching: merge rapid successive messages (Telegram-style).
   284|        # Matrix clients split long messages around 4000 chars.
   285|        self._text_batch_delay_seconds = float(
   286|            os.getenv("HERMES_MATRIX_TEXT_BATCH_DELAY_SECONDS", "0.6")
   287|        )
   288|        self._text_batch_split_delay_seconds = float(
   289|            os.getenv("HERMES_MATRIX_TEXT_BATCH_SPLIT_DELAY_SECONDS", "2.0")
   290|        )
   291|        self._pending_text_batches: Dict[str, MessageEvent] = {}
   292|        self._pending_text_batch_tasks: Dict[str, asyncio.Task] = {}
   293|
   294|        # Matrix reaction-based dangerous command approvals.
   295|        self._approval_reaction_map = {
   296|            "✅": "once",
   297|            "⭕": "session",
   298|            "♾️": "always",
   299|            "♾": "always",
   300|            "❌": "deny",
   301|        }
   302|        self._approval_prompts_by_event: Dict[str, _MatrixApprovalPrompt] = {}
   303|        self._approval_prompt_by_session: Dict[str, str] = {}
   304|        allowed_users_raw = os.getenv("MATRIX_ALLOWED_USERS", "")
   305|        self._allowed_user_ids: Set[str] = {
   306|            u.strip() for u in allowed_users_raw.split(",") if u.strip()
   307|        }
   308|
   309|    def _is_duplicate_event(self, event_id) -> bool:
   310|        """Return True if this event was already processed. Tracks the ID otherwise."""
   311|        if not event_id:
   312|            return False
   313|        if event_id in self._processed_events_set:
   314|            return True
   315|        if len(self._processed_events) == self._processed_events.maxlen:
   316|            evicted = self._processed_events[0]
   317|            self._processed_events_set.discard(evicted)
   318|        self._processed_events.append(event_id)
   319|        self._processed_events_set.add(event_id)
   320|        return False
   321|
   322|    # ------------------------------------------------------------------
   323|    # E2EE helpers
   324|    # ------------------------------------------------------------------
   325|
   326|    @staticmethod
   327|    def _extract_server_ed25519(device_keys_obj: Any) -> Optional[str]:
   328|        """Extract the ed25519 identity key from a DeviceKeys object."""
   329|        for kid, kval in (getattr(device_keys_obj, "keys", {}) or {}).items():
   330|            if str(kid).startswith("ed25519:"):
   331|                return str(kval)
   332|        return None
   333|
   334|    async def _reverify_keys_after_upload(
   335|        self, client: Any, local_ed25519: str
   336|    ) -> bool:
   337|        """Re-query the server after share_keys() and verify our ed25519 key matches."""
   338|        try:
   339|            resp = await client.query_keys({client.mxid: [client.device_id]})
   340|            dk = getattr(resp, "device_keys", {}) or {}
   341|            ud = dk.get(str(client.mxid)) or {}
   342|            dev = ud.get(str(client.device_id))
   343|            if dev:
   344|                server_ed = self._extract_server_ed25519(dev)
   345|                if server_ed != local_ed25519:
   346|                    logger.error(
   347|                        "Matrix: device %s has immutable identity keys that "
   348|                        "don't match this installation. Generate a new access "
   349|                        "token with a fresh device.",
   350|                        client.device_id,
   351|                    )
   352|                    return False
   353|        except Exception as exc:
   354|            logger.error("Matrix: post-upload key verification failed: %s", exc)
   355|            return False
   356|        return True
   357|
   358|    async def _verify_device_keys_on_server(self, client: Any, olm: Any) -> bool:
   359|        """Verify our device keys are on the homeserver after loading crypto state.
   360|
   361|        Returns True if keys are valid or were successfully re-uploaded.
   362|        Returns False if verification fails (caller should refuse E2EE).
   363|        """
   364|        try:
   365|            resp = await client.query_keys({client.mxid: [client.device_id]})
   366|        except Exception as exc:
   367|            logger.error(
   368|                "Matrix: cannot verify device keys on server: %s — refusing E2EE",
   369|                exc,
   370|            )
   371|            return False
   372|
   373|        device_keys_map = getattr(resp, "device_keys", {}) or {}
   374|        our_user_devices = device_keys_map.get(str(client.mxid)) or {}
   375|        our_keys = our_user_devices.get(str(client.device_id))
   376|        local_ed25519 = olm.account.identity_keys.get("ed25519")
   377|
   378|        if not our_keys:
   379|            logger.warning("Matrix: device keys missing from server — re-uploading")
   380|            olm.account.shared = False
   381|            try:
   382|                await olm.share_keys()
   383|            except Exception as exc:
   384|                logger.error("Matrix: failed to re-upload device keys: %s", exc)
   385|                return False
   386|            return await self._reverify_keys_after_upload(client, local_ed25519)
   387|
   388|        server_ed25519 = self._extract_server_ed25519(our_keys)
   389|
   390|        if server_ed25519 != local_ed25519:
   391|            if olm.account.shared:
   392|                logger.error(
   393|                    "Matrix: server has different identity keys for device %s — "
   394|                    "local crypto state is stale. Delete %s and restart.",
   395|                    client.device_id,
   396|                    _CRYPTO_DB_PATH,
   397|                )
   398|                return False
   399|
   400|            logger.warning(
   401|                "Matrix: server has stale keys for device %s — attempting re-upload",
   402|                client.device_id,
   403|            )
   404|            try:
   405|                await client.api.request(
   406|                    client.api.Method.DELETE
   407|                    if hasattr(client.api, "Method")
   408|                    else "DELETE",
   409|                    f"/_matrix/client/v3/devices/{client.device_id}",
   410|                )
   411|                logger.info(
   412|                    "Matrix: deleted stale device %s from server", client.device_id
   413|                )
   414|            except Exception:
   415|                pass
   416|            try:
   417|                await olm.share_keys()
   418|            except Exception as exc:
   419|                logger.error(
   420|                    "Matrix: cannot upload device keys for %s: %s. "
   421|                    "Try generating a new access token to get a fresh device.",
   422|                    client.device_id,
   423|                    exc,
   424|                )
   425|                return False
   426|            return await self._reverify_keys_after_upload(client, local_ed25519)
   427|
   428|        return True
   429|
   430|    # ------------------------------------------------------------------
   431|    # Required overrides
   432|    # ------------------------------------------------------------------
   433|
   434|    async def connect(self) -> bool:
   435|        """Connect to the Matrix homeserver and start syncing."""
   436|        from mautrix.api import HTTPAPI
   437|        from mautrix.client import Client
   438|        from mautrix.client.state_store import MemoryStateStore, MemorySyncStore
   439|
   440|        if not self._homeserver:
   441|            logger.error("Matrix: homeserver URL not configured")
   442|            return False
   443|
   444|        # Ensure store dir exists for E2EE key persistence.
   445|        _STORE_DIR.mkdir(parents=True, exist_ok=True)
   446|
   447|        # Create the HTTP API layer.
   448|        api = HTTPAPI(
   449|            base_url=self._homeserver,
   450|            token=self._access_token or "",
   451|        )
   452|
   453|        # Create the client.
   454|        state_store = MemoryStateStore()
   455|        sync_store = MemorySyncStore()
   456|        client = Client(
   457|            mxid=UserID(self._user_id) if self._user_id else UserID(""),
   458|            device_id=self._device_id or None,
   459|            api=api,
   460|            state_store=state_store,
   461|            sync_store=sync_store,
   462|        )
   463|
   464|        self._client = client
   465|
   466|        # Authenticate.
   467|        if self._access_token:
   468|            api.token = self._access_token
   469|
   470|            # Validate the token and learn user_id / device_id.
   471|            try:
   472|                resp = await client.whoami()
   473|                resolved_user_id = getattr(resp, "user_id", "") or self._user_id
   474|                resolved_device_id = getattr(resp, "device_id", "")
   475|                if resolved_user_id:
   476|                    self._user_id = str(resolved_user_id)
   477|                    client.mxid = UserID(self._user_id)
   478|
   479|                # Prefer user-configured device_id for stable E2EE identity.
   480|                effective_device_id = self._device_id or resolved_device_id
   481|                if effective_device_id:
   482|                    client.device_id = effective_device_id
   483|
   484|                logger.info(
   485|                    "Matrix: using access token for %s%s",
   486|                    self._user_id or "(unknown user)",
   487|                    f" (device {effective_device_id})" if effective_device_id else "",
   488|                )
   489|            except Exception as exc:
   490|                logger.error(
   491|                    "Matrix: whoami failed — check MATRIX_ACCESS_TOKEN and MATRIX_HOMESERVER: %s",
   492|                    exc,
   493|                )
   494|                await api.session.close()
   495|                return False
   496|        elif self._password and self._user_id:
   497|            try:
   498|                resp = await client.login(
   499|                    identifier=self._user_id,
   500|                    password=self._password,
   501|                    device_name="Hermes Agent",
   502|                    device_id=self._device_id or None,
   503|                )
   504|                if resp and hasattr(resp, "device_id"):
   505|                    client.device_id = resp.device_id
   506|                logger.info("Matrix: logged in as %s", self._user_id)
   507|            except Exception as exc:
   508|                logger.error("Matrix: login failed — %s", exc)
   509|                await api.session.close()
   510|                return False
   511|        else:
   512|            logger.error(
   513|                "Matrix: need MATRIX_ACCESS_TOKEN or MATRIX_USER_ID + MATRIX_PASSWORD"
   514|            )
   515|            await api.session.close()
   516|            return False
   517|
   518|        # Set up E2EE if requested.
   519|        if self._encryption:
   520|            if not _check_e2ee_deps():
   521|                logger.error(
   522|                    "Matrix: MATRIX_ENCRYPTION=true but E2EE dependencies are missing. %s. "
   523|                    "Refusing to connect — encrypted rooms would silently fail.",
   524|                    _E2EE_INSTALL_HINT,
   525|                )
   526|                await api.session.close()
   527|                return False
   528|            try:
   529|                from mautrix.crypto import OlmMachine
   530|                from mautrix.crypto.store.asyncpg import PgCryptoStore
   531|                from mautrix.util.async_db import Database
   532|
   533|                _STORE_DIR.mkdir(parents=True, exist_ok=True)
   534|
   535|                # Remove legacy pickle file from pre-SQLite era.
   536|                legacy_pickle = _STORE_DIR / "crypto_store.pickle"
   537|                if legacy_pickle.exists():
   538|                    logger.info(
   539|                        "Matrix: removing legacy crypto_store.pickle (migrated to SQLite)"
   540|                    )
   541|                    legacy_pickle.unlink()
   542|
   543|                # Open SQLite-backed crypto store.
   544|                crypto_db = Database.create(
   545|                    f"sqlite:///{_CRYPTO_DB_PATH}",
   546|                    upgrade_table=PgCryptoStore.upgrade_table,
   547|                )
   548|                await crypto_db.start()
   549|                self._crypto_db = crypto_db
   550|
   551|                _acct_id = self._user_id or "hermes"
   552|                _pickle_key = f"{_acct_id}:{self._device_id or 'default'}"
   553|                crypto_store = PgCryptoStore(
   554|                    account_id=_acct_id,
   555|                    pickle_key=_pickle_key,
   556|                    db=crypto_db,
   557|                )
   558|                await crypto_store.open()
   559|
   560|                crypto_state = _CryptoStateStore(state_store, self._joined_rooms)
   561|                olm = OlmMachine(client, crypto_store, crypto_state)
   562|
   563|                # Accept unverified devices so senders share Megolm
   564|                # session keys with us automatically.
   565|                olm.share_keys_min_trust = TrustState.UNVERIFIED
   566|                olm.send_keys_min_trust = TrustState.UNVERIFIED
   567|
   568|                await olm.load()
   569|
   570|                # Verify our device keys are still on the homeserver.
   571|                if not await self._verify_device_keys_on_server(client, olm):
   572|                    await crypto_db.stop()
   573|                    await api.session.close()
   574|                    return False
   575|
   576|                # Proactively flush one-time keys to detect stale OTK
   577|                # conflicts early.  When crypto state is wiped but the
   578|                # same device ID is reused, the server may still hold OTKs
   579|                # signed with the old ed25519 key.  Identity key re-upload
   580|                # succeeds but OTK uploads fail ("already exists" with
   581|                # mismatched signature).  Peers then cannot establish Olm
   582|                # sessions and all new messages are undecryptable.
   583|                try:
   584|                    await olm.share_keys()
   585|                except Exception as exc:
   586|                    exc_str = str(exc)
   587|                    if "already exists" in exc_str:
   588|                        logger.error(
   589|                            "Matrix: device %s has stale one-time keys on the "
   590|                            "server signed with a previous identity key. "
   591|                            "Peers cannot establish new Olm sessions with "
   592|                            "this device. Delete the device from the "
   593|                            "homeserver and restart, or generate a new "
   594|                            "access token to get a fresh device ID.",
   595|                            client.device_id,
   596|                        )
   597|                        await crypto_db.stop()
   598|                        await api.session.close()
   599|                        return False
   600|                    # Non-OTK errors are transient (network, etc.) — log
   601|                    # but allow startup to continue.
   602|                    logger.warning(
   603|                        "Matrix: share_keys() warning during startup: %s",
   604|                        exc,
   605|                    )
   606|
   607|                # Import cross-signing private keys from SSSS and self-sign
   608|                # the current device. Required after any device-key rotation
   609|                # (fresh crypto.db, share_keys re-upload) — otherwise the
   610|                # device's self-signing signature is stale and peers refuse
   611|                # to share Megolm sessions with the rotated device.
   612|                recovery_key = os.getenv("MATRIX_RECOVERY_KEY", "").strip()
   613|                if recovery_key:
   614|                    try:
   615|                        await olm.verify_with_recovery_key(recovery_key)
   616|                        logger.info("Matrix: cross-signing verified via recovery key")
   617|                    except Exception as exc:
   618|                        logger.warning(
   619|                            "Matrix: recovery key verification failed: %s", exc
   620|                        )
   621|
   622|                client.crypto = olm
   623|                logger.info(
   624|                    "Matrix: E2EE enabled (store: %s%s)",
   625|                    str(_CRYPTO_DB_PATH),
   626|                    f", device_id={client.device_id}" if client.device_id else "",
   627|                )
   628|            except Exception as exc:
   629|                logger.error(
   630|                    "Matrix: failed to create E2EE client: %s. %s",
   631|                    exc,
   632|                    _E2EE_INSTALL_HINT,
   633|                )
   634|                await api.session.close()
   635|                return False
   636|
   637|        # Register event handlers.
   638|        from mautrix.client import InternalEventType as IntEvt
   639|        from mautrix.client.dispatcher import MembershipEventDispatcher
   640|
   641|        # Without this the INVITE handler below never fires.
   642|        client.add_dispatcher(MembershipEventDispatcher)
   643|
   644|        client.add_event_handler(EventType.ROOM_MESSAGE, self._on_room_message)
   645|        client.add_event_handler(EventType.REACTION, self._on_reaction)
   646|        client.add_event_handler(IntEvt.INVITE, self._on_invite)
   647|
   648|        # Initial sync to catch up, then start background sync.
   649|        self._startup_ts = time.time()
   650|        self._closing = False
   651|
   652|        try:
   653|            sync_data = await client.sync(timeout=10000, full_state=True)
   654|            if isinstance(sync_data, dict):
   655|                rooms_join = sync_data.get("rooms", {}).get("join", {})
   656|                self._joined_rooms.clear()
   657|                self._joined_rooms.update(rooms_join.keys())
   658|                # Store the next_batch token so incremental syncs start
   659|                # from where the initial sync left off.
   660|                nb = sync_data.get("next_batch")
   661|                if nb:
   662|                    await client.sync_store.put_next_batch(nb)
   663|                logger.info(
   664|                    "Matrix: initial sync complete, joined %d rooms",
   665|                    len(self._joined_rooms),
   666|                )
   667|                # Build DM room cache from m.direct account data.
   668|                await self._refresh_dm_cache()
   669|
   670|                # Dispatch events from the initial sync so the OlmMachine
   671|                # receives to-device key shares queued while we were offline.
   672|                try:
   673|                    tasks = client.handle_sync(sync_data)
   674|                    if tasks:
   675|                        await asyncio.gather(*tasks)
   676|                except Exception as exc:
   677|                    logger.warning("Matrix: initial sync event dispatch error: %s", exc)
   678|            else:
   679|                logger.warning(
   680|                    "Matrix: initial sync returned unexpected type %s",
   681|                    type(sync_data).__name__,
   682|                )
   683|        except Exception as exc:
   684|            logger.warning("Matrix: initial sync error: %s", exc)
   685|
   686|        # Share keys after initial sync if E2EE is enabled.
   687|        if self._encryption and getattr(client, "crypto", None):
   688|            try:
   689|                await client.crypto.share_keys()
   690|            except Exception as exc:
   691|                logger.warning("Matrix: initial key share failed: %s", exc)
   692|
   693|        # Start the sync loop.
   694|        # NOTE: mautrix event handlers are dispatched by client.start(), not by calling client.sync() manually.
   695|        # We keep our own sync loop for periodic maintenance in _sync_loop, but the actual event stream
   696|        # must be driven by the mautrix client.
   697|        self._client.start(None)
   698|        self._sync_task = asyncio.create_task(self._sync_loop())
   699|        self._mark_connected()
   700|        return True
   701|
   702|    async def disconnect(self) -> None:
   703|        """Disconnect from Matrix."""
   704|        self._closing = True
   705|
   706|        if self._sync_task and not self._sync_task.done():
   707|            self._sync_task.cancel()
   708|            try:
   709|                await self._sync_task
   710|            except (asyncio.CancelledError, Exception):
   711|                pass
   712|
   713|        # Close the SQLite crypto store database.
   714|        if hasattr(self, "_crypto_db") and self._crypto_db:
   715|            try:
   716|                await self._crypto_db.stop()
   717|            except Exception as exc:
   718|                logger.debug("Matrix: could not close crypto DB on disconnect: %s", exc)
   719|
   720|        if self._client:
   721|            try:
   722|                # Stop mautrix syncing task if it was started.
   723|                try:
   724|                    self._client.stop()
   725|                except Exception:
   726|                    pass
   727|                await self._client.api.session.close()
   728|            except Exception:
   729|                pass
   730|            self._client = None
   731|
   732|        logger.info("Matrix: disconnected")
   733|
   734|    async def send(
   735|        self,
   736|        chat_id: str,
   737|        content: str,
   738|        reply_to: Optional[str] = None,
   739|        metadata: Optional[Dict[str, Any]] = None,
   740|    ) -> SendResult:
   741|        """Send a message to a Matrix room."""
   742|
   743|        if not content:
   744|            return SendResult(success=True)
   745|
   746|        is_silent = (metadata or {}).get("silent")
   747|        mention_user_id = (metadata or {}).get("mention_user_id")
   748|
   749|        formatted = self.format_message(content)
   750|        chunks = self.truncate_message(formatted, MAX_MESSAGE_LENGTH)
   751|
   752|        last_event_id = None
   753|        for i, chunk in enumerate(chunks):
   754|            msg_content: Dict[str, Any] = {
   755|                "msgtype": "m.text",
   756|                "body": chunk,
   757|            }
   758|
   759|            # Suppress push notifications when silent=True in metadata.
   760|            if is_silent:
   761|                msg_content["m.silent"] = {}
   762|
   763|            # Append @mention pill to the last chunk of non-silent responses.
   764|            # This triggers push notifications in muted rooms (mention-only mode).
   765|            if (mention_user_id
   766|                    and not is_silent
   767|                    and i == len(chunks) - 1):
   768|                mention_html = (
   769|                    f'<a href="https://matrix.to/#/{mention_user_id}">'
   770|                    f"{mention_user_id}</a>"
   771|                )
   772|                # Plain-text mention
   773|                msg_content["body"] = chunk + f" @{mention_user_id}"
   774|                # HTML mention pill
   775|                html = self._markdown_to_html(chunk)
   776|                if html and html != chunk:
   777|                    base_html = html
   778|                else:
   779|                    base_html = chunk
   780|                msg_content["format"] = "org.matrix.custom.html"
   781|                msg_content["formatted_body"] = base_html + " " + mention_html
   782|            else:
   783|                # Convert markdown to HTML for rich rendering.
   784|                html = self._markdown_to_html(chunk)
   785|                if html and html != chunk:
   786|                    msg_content["format"] = "org.matrix.custom.html"
   787|                    msg_content["formatted_body"] = html
   788|
   789|            # Reply-to support.
   790|            if reply_to:
   791|                msg_content["m.relates_to"] = {"m.in_reply_to": {"event_id": reply_to}}
   792|
   793|            # Thread support: if metadata has thread_id, send as threaded reply.
   794|            thread_id = (metadata or {}).get("thread_id")
   795|            if thread_id:
   796|                relates_to = msg_content.get("m.relates_to", {})
   797|                relates_to["rel_type"] = "m.thread"
   798|                relates_to["event_id"] = thread_id
   799|                relates_to["is_falling_back"] = True
   800|                if reply_to and "m.in_reply_to" not in relates_to:
   801|                    relates_to["m.in_reply_to"] = {"event_id": reply_to}
   802|                msg_content["m.relates_to"] = relates_to
   803|
   804|            try:
   805|                event_id = await asyncio.wait_for(
   806|                    self._client.send_message_event(
   807|                        RoomID(chat_id),
   808|                        EventType.ROOM_MESSAGE,
   809|                        msg_content,
   810|                    ),
   811|                    timeout=45,
   812|                )
   813|                last_event_id = str(event_id)
   814|                logger.info("Matrix: sent event %s to %s", last_event_id, chat_id)
   815|            except Exception as exc:
   816|                # On E2EE errors, retry after sharing keys.
   817|                if self._encryption and getattr(self._client, "crypto", None):
   818|                    try:
   819|                        await self._client.crypto.share_keys()
   820|                        event_id = await asyncio.wait_for(
   821|                            self._client.send_message_event(
   822|                                RoomID(chat_id),
   823|                                EventType.ROOM_MESSAGE,
   824|                                msg_content,
   825|                            ),
   826|                            timeout=45,
   827|                        )
   828|                        last_event_id = str(event_id)
   829|                        logger.info(
   830|                            "Matrix: sent event %s to %s (after key share)",
   831|                            last_event_id,
   832|                            chat_id,
   833|                        )
   834|                        continue
   835|                    except Exception as retry_exc:
   836|                        logger.error(
   837|                            "Matrix: failed to send to %s after retry: %s",
   838|                            chat_id,
   839|                            retry_exc,
   840|                        )
   841|                        return SendResult(success=False, error=str(retry_exc))
   842|                logger.error("Matrix: failed to send to %s: %s", chat_id, exc)
   843|                return SendResult(success=False, error=str(exc))
   844|
   845|        return SendResult(success=True, message_id=last_event_id)
   846|
   847|    async def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
   848|        """Return room name and type (dm/group)."""
   849|        name = chat_id
   850|        chat_type = "dm" if await self._is_dm_room(chat_id) else "group"
   851|
   852|        if self._client:
   853|            try:
   854|                name_evt = await self._client.get_state_event(
   855|                    RoomID(chat_id),
   856|                    EventType.ROOM_NAME,
   857|                )
   858|                if name_evt and hasattr(name_evt, "name") and name_evt.name:
   859|                    name = name_evt.name
   860|            except Exception:
   861|                pass
   862|
   863|        return {"name": name, "type": chat_type}
   864|
   865|    # ------------------------------------------------------------------
   866|    # Optional overrides
   867|    # ------------------------------------------------------------------
   868|
   869|    async def send_typing(
   870|        self, chat_id: str, metadata: Optional[Dict[str, Any]] = None
   871|    ) -> None:
   872|        """Send a typing indicator."""
   873|        if self._client:
   874|            try:
   875|                await self._client.set_typing(RoomID(chat_id), timeout=30000)
   876|            except Exception:
   877|                pass
   878|
   879|    async def stop_typing(self, chat_id: str) -> None:
   880|        """Clear the typing indicator."""
   881|        if self._client:
   882|            try:
   883|                await self._client.set_typing(RoomID(chat_id), timeout=0)
   884|            except Exception:
   885|                pass
   886|
   887|
   888|    async def edit_message(
   889|        self, chat_id: str, message_id: str, content: str
   890|    ) -> SendResult:
   891|        """Edit an existing message (via m.replace)."""
   892|
   893|        formatted = self.format_message(content)
   894|        msg_content: Dict[str, Any] = {
   895|            "msgtype": "m.text",
   896|            "body": f"* {formatted}",
   897|            "m.new_content": {
   898|                "msgtype": "m.text",
   899|                "body": formatted,
   900|            },
   901|            "m.relates_to": {
   902|                "rel_type": "m.replace",
   903|                "event_id": message_id,
   904|            },
   905|        }
   906|
   907|        html = self._markdown_to_html(formatted)
   908|        if html and html != formatted:
   909|            msg_content["m.new_content"]["format"] = "org.matrix.custom.html"
   910|            msg_content["m.new_content"]["formatted_body"] = html
   911|            msg_content["format"] = "org.matrix.custom.html"
   912|            msg_content["formatted_body"] = f"* {html}"
   913|
   914|        try:
   915|            event_id = await self._client.send_message_event(
   916|                RoomID(chat_id),
   917|                EventType.ROOM_MESSAGE,
   918|                msg_content,
   919|            )
   920|            return SendResult(success=True, message_id=str(event_id))
   921|        except Exception as exc:
   922|            return SendResult(success=False, error=str(exc))
   923|
   924|    async def send_image(
   925|        self,
   926|        chat_id: str,
   927|        image_url: str,
   928|        caption: Optional[str] = None,
   929|        reply_to: Optional[str] = None,
   930|        metadata: Optional[Dict[str, Any]] = None,
   931|    ) -> SendResult:
   932|        """Download an image URL and upload it to Matrix."""
   933|        from tools.url_safety import is_safe_url
   934|
   935|        if not is_safe_url(image_url):
   936|            logger.warning("Matrix: blocked unsafe image URL (SSRF protection)")
   937|            return await super().send_image(
   938|                chat_id, image_url, caption, reply_to, metadata=metadata
   939|            )
   940|
   941|        try:
   942|            # Try aiohttp first (always available), fall back to httpx
   943|            try:
   944|                import aiohttp as _aiohttp
   945|
   946|                async with _aiohttp.ClientSession(trust_env=True) as http:
   947|                    async with http.get(
   948|                        image_url, timeout=_aiohttp.ClientTimeout(total=30)
   949|                    ) as resp:
   950|                        resp.raise_for_status()
   951|                        data = await resp.read()
   952|                        ct = resp.content_type or "image/png"
   953|                        fname = (
   954|                            image_url.rsplit("/", 1)[-1].split("?")[0] or "image.png"
   955|                        )
   956|            except ImportError:
   957|                import httpx
   958|
   959|                async with httpx.AsyncClient() as http:
   960|                    resp = await http.get(image_url, follow_redirects=True, timeout=30)
   961|                    resp.raise_for_status()
   962|                    data = resp.content
   963|                    ct = resp.headers.get("content-type", "image/png")
   964|                    fname = image_url.rsplit("/", 1)[-1].split("?")[0] or "image.png"
   965|        except Exception as exc:
   966|            logger.warning("Matrix: failed to download image %s: %s", image_url, exc)
   967|            return await self.send(
   968|                chat_id, f"{caption or ''}\n{image_url}".strip(), reply_to
   969|            )
   970|
   971|        return await self._upload_and_send(
   972|            chat_id, data, fname, ct, "m.image", caption, reply_to, metadata
   973|        )
   974|
   975|    async def send_image_file(
   976|        self,
   977|        chat_id: str,
   978|        image_path: str,
   979|        caption: Optional[str] = None,
   980|        reply_to: Optional[str] = None,
   981|        metadata: Optional[Dict[str, Any]] = None,
   982|    ) -> SendResult:
   983|        """Upload a local image file to Matrix."""
   984|        return await self._send_local_file(
   985|            chat_id, image_path, "m.image", caption, reply_to, metadata=metadata
   986|        )
   987|
   988|    async def send_document(
   989|        self,
   990|        chat_id: str,
   991|        file_path: str,
   992|        caption: Optional[str] = None,
   993|        file_name: Optional[str] = None,
   994|        reply_to: Optional[str] = None,
   995|        metadata: Optional[Dict[str, Any]] = None,
   996|    ) -> SendResult:
   997|        """Upload a local file as a document."""
   998|        return await self._send_local_file(
   999|            chat_id, file_path, "m.file", caption, reply_to, file_name, metadata
  1000|        )
  1001|
  1002|    async def send_voice(
  1003|        self,
  1004|        chat_id: str,
  1005|        audio_path: str,
  1006|        caption: Optional[str] = None,
  1007|        reply_to: Optional[str] = None,
  1008|        metadata: Optional[Dict[str, Any]] = None,
  1009|    ) -> SendResult:
  1010|        """Upload an audio file as a voice message (MSC3245 native voice)."""
  1011|        return await self._send_local_file(
  1012|            chat_id,
  1013|            audio_path,
  1014|            "m.audio",
  1015|            caption,
  1016|            reply_to,
  1017|            metadata=metadata,
  1018|            is_voice=True,
  1019|        )
  1020|
  1021|    async def send_video(
  1022|        self,
  1023|        chat_id: str,
  1024|        video_path: str,
  1025|        caption: Optional[str] = None,
  1026|        reply_to: Optional[str] = None,
  1027|        metadata: Optional[Dict[str, Any]] = None,
  1028|    ) -> SendResult:
  1029|        """Upload a video file."""
  1030|        return await self._send_local_file(
  1031|            chat_id, video_path, "m.video", caption, reply_to, metadata=metadata
  1032|        )
  1033|
  1034|    def format_message(self, content: str) -> str:
  1035|        """Pass-through — Matrix supports standard Markdown natively."""
  1036|        # Strip image markdown; media is uploaded separately.
  1037|        content = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r"\2", content)
  1038|        return content
  1039|
  1040|    # ------------------------------------------------------------------
  1041|    # File helpers
  1042|    # ------------------------------------------------------------------
  1043|
  1044|    async def _upload_and_send(
  1045|        self,
  1046|        room_id: str,
  1047|        data: bytes,
  1048|        filename: str,
  1049|        content_type: str,
  1050|        msgtype: str,
  1051|        caption: Optional[str] = None,
  1052|        reply_to: Optional[str] = None,
  1053|        metadata: Optional[Dict[str, Any]] = None,
  1054|        is_voice: bool = False,
  1055|    ) -> SendResult:
  1056|        """Upload bytes to Matrix and send as a media message."""
  1057|
  1058|        upload_data = data
  1059|        encrypted_file = None
  1060|        if self._encryption and getattr(self._client, "crypto", None):
  1061|            state_store = getattr(self._client, "state_store", None)
  1062|            if state_store:
  1063|                try:
  1064|                    room_encrypted = bool(await state_store.is_encrypted(RoomID(room_id)))
  1065|                except Exception:
  1066|                    room_encrypted = False
  1067|                if room_encrypted:
  1068|                    try:
  1069|                        from mautrix.crypto.attachments import encrypt_attachment
  1070|                        upload_data, encrypted_file = encrypt_attachment(data)
  1071|                    except Exception as exc:
  1072|                        logger.error("Matrix: attachment encryption failed: %s", exc)
  1073|                        return SendResult(success=False, error=str(exc))
  1074|
  1075|        # Upload to homeserver.
  1076|        try:
  1077|            mxc_url = await self._client.upload_media(
  1078|                upload_data,
  1079|                mime_type=content_type,
  1080|                filename=filename,
  1081|                size=len(upload_data),
  1082|            )
  1083|        except Exception as exc:
  1084|            logger.error("Matrix: upload failed: %s", exc)
  1085|            return SendResult(success=False, error=str(exc))
  1086|
  1087|        # Build media message content.
  1088|        msg_content: Dict[str, Any] = {
  1089|            "msgtype": msgtype,
  1090|            "body": caption or filename,
  1091|            "info": {
  1092|                "mimetype": content_type,
  1093|                "size": len(data),
  1094|            },
  1095|        }
  1096|        if encrypted_file is not None:
  1097|            file_payload = encrypted_file.serialize()
  1098|            file_payload["url"] = str(mxc_url)
  1099|            msg_content["file"] = file_payload
  1100|        else:
  1101|            msg_content["url"] = str(mxc_url)
  1102|
  1103|        # Add MSC3245 voice flag for native voice messages.
  1104|        if is_voice:
  1105|            msg_content["org.matrix.msc3245.voice"] = {}
  1106|
  1107|        if reply_to:
  1108|            msg_content["m.relates_to"] = {"m.in_reply_to": {"event_id": reply_to}}
  1109|
  1110|        thread_id = (metadata or {}).get("thread_id")
  1111|        if thread_id:
  1112|            relates_to = msg_content.get("m.relates_to", {})
  1113|            relates_to["rel_type"] = "m.thread"
  1114|            relates_to["event_id"] = thread_id
  1115|            relates_to["is_falling_back"] = True
  1116|            msg_content["m.relates_to"] = relates_to
  1117|
  1118|        try:
  1119|            event_id = await self._client.send_message_event(
  1120|                RoomID(room_id),
  1121|                EventType.ROOM_MESSAGE,
  1122|                msg_content,
  1123|            )
  1124|            return SendResult(success=True, message_id=str(event_id))
  1125|        except Exception as exc:
  1126|            return SendResult(success=False, error=str(exc))
  1127|
  1128|    async def _send_local_file(
  1129|        self,
  1130|        room_id: str,
  1131|        file_path: str,
  1132|        msgtype: str,
  1133|        caption: Optional[str] = None,
  1134|        reply_to: Optional[str] = None,
  1135|        file_name: Optional[str] = None,
  1136|        metadata: Optional[Dict[str, Any]] = None,
  1137|        is_voice: bool = False,
  1138|    ) -> SendResult:
  1139|        """Read a local file and upload it."""
  1140|        p = Path(file_path).expanduser()
  1141|        if not p.exists():
  1142|            return await self.send(
  1143|                room_id, f"{caption or ''}\n(file not found: {file_path})", reply_to
  1144|            )
  1145|
  1146|        fname = file_name or p.name
  1147|        ct = mimetypes.guess_type(fname)[0] or "application/octet-stream"
  1148|        data = p.read_bytes()
  1149|
  1150|        return await self._upload_and_send(
  1151|            room_id, data, fname, ct, msgtype, caption, reply_to, metadata, is_voice
  1152|        )
  1153|
  1154|    # ------------------------------------------------------------------
  1155|    # Sync loop
  1156|    # ------------------------------------------------------------------
  1157|
  1158|    async def _sync_loop(self) -> None:
  1159|        """Continuously sync with the homeserver."""
  1160|        client = self._client
  1161|        # Resume from the token stored during the initial sync.
  1162|        next_batch = await client.sync_store.get_next_batch()
  1163|        while not self._closing:
  1164|            try:
  1165|                sync_data = await client.sync(
  1166|                    since=next_batch,
  1167|                    timeout=30000,
  1168|                )
  1169|
  1170|                # nio returns SyncError objects (not exceptions) for auth
  1171|                # failures like M_UNKNOWN_TOKEN.  Detect and stop immediately.
  1172|                _sync_msg = getattr(sync_data, "message", None)
  1173|                if _sync_msg and isinstance(_sync_msg, str):
  1174|                    _lower = _sync_msg.lower()
  1175|                    if "m_unknown_token" in _lower or "unknown_token" in _lower:
  1176|                        logger.error(
  1177|                            "Matrix: permanent auth error from sync: %s — stopping",
  1178|                            _sync_msg,
  1179|                        )
  1180|                        return
  1181|
  1182|                if isinstance(sync_data, dict):
  1183|                    rooms_join = sync_data.get("rooms", {}).get("join", {})
  1184|                    if rooms_join:
  1185|                        self._joined_rooms.update(rooms_join.keys())
  1186|
  1187|                    # Advance the sync token so the next request is
  1188|                    # incremental instead of a full initial sync.
  1189|                    nb = sync_data.get("next_batch")
  1190|                    if nb:
  1190|                    if nb:
  1191|                        next_batch = nb
  1192|                        await client.sync_store.put_next_batch(nb)
  1193|
  1194|                    # Dispatch events to registered handlers so that
  1195|                    # _on_room_message / _on_reaction / _on_invite fire.
  1196|                    try:
  1197|                        tasks = client.handle_sync(sync_data)
  1198|                        if tasks:
  1199|                            await asyncio.gather(*tasks)
  1200|                    except Exception as exc:
  1201|                        logger.warning("Matrix: sync event dispatch error: %s", exc)
  1202|
  1203|<<<<<<< HEAD
  1204|=======
  1205|                # Retry any buffered undecrypted events.
  1206|                if self._pending_megolm:
  1207|                    await self._retry_pending_decryptions()
  1208|                return
  1209|            except Exception as exc:
  1210|                if self._closing:
  1211|                    return
  1212|                # Detect permanent auth/permission failures.
  1213|                err_str = str(exc).lower()
  1214|                if (
  1215|                    "401" in err_str
  1216|                    or "403" in err_str
  1217|                    or "unauthorized" in err_str
  1218|                    or "forbidden" in err_str
  1219|                ):
  1220|                    logger.error(
  1221|                        "Matrix: permanent auth error: %s — stopping sync", exc
  1222|                    )
  1223|                    return
  1224|                logger.warning("Matrix: sync error: %s — retrying in 5s", exc)
  1225|                await asyncio.sleep(5)
  1226|
  1227|    # ------------------------------------------------------------------
  1228|    # Event callbacks
  1229|    # ------------------------------------------------------------------
  1230|
  1231|    async def _on_room_message(self, event: Any) -> None:
  1232|        """Handle incoming room message events (text, media)."""
  1233|        room_id = str(getattr(event, "room_id", ""))
  1234|        sender = str(getattr(event, "sender", ""))
  1235|
  1236|        # Ignore own messages.
  1237|        if sender == self._user_id:
  1238|            return
  1239|
  1240|
  1241|        event_id = str(getattr(event, "event_id", ""))
  1242|        if self._is_duplicate_event(event_id):
  1243|            return
  1244|
  1245|        # Startup grace: ignore old messages from initial sync.
  1246|        raw_ts = (
  1247|            getattr(event, "timestamp", None)
  1248|            or getattr(event, "server_timestamp", None)
  1249|            or 0
  1250|        )
  1251|        event_ts = raw_ts / 1000.0 if raw_ts else 0.0
  1252|        if event_ts and event_ts < self._startup_ts - _STARTUP_GRACE_SECONDS:
  1253|            return
  1254|
  1255|        # Extract content from the event.
  1256|        content = getattr(event, "content", None)
  1257|        if content is None:
  1258|            return
  1259|
  1260|        # Get msgtype — either from content object or raw dict.
  1261|        if hasattr(content, "msgtype"):
  1262|            msgtype = str(content.msgtype)
  1263|        elif isinstance(content, dict):
  1264|            msgtype = content.get("msgtype", "")
  1265|        else:
  1266|            msgtype = ""
  1267|
  1268|        # Determine source content dict for relation/thread extraction.
  1269|        if isinstance(content, dict):
  1270|            source_content = content
  1271|        elif hasattr(content, "serialize"):
  1272|            source_content = content.serialize()
  1273|        else:
  1274|            source_content = {}
  1275|
  1276|        relates_to = source_content.get("m.relates_to", {})
  1277|
  1278|        # Skip edits (m.replace relation).
  1279|        if relates_to.get("rel_type") == "m.replace":
  1280|            return
  1281|
  1282|        # Ignore m.notice to prevent bot-to-bot loops (m.notice is the
  1283|        # conventional msgtype for bot responses in the Matrix ecosystem).
  1284|        if msgtype == "m.notice":
  1285|            return
  1286|
  1287|        # Dispatch by msgtype.
  1288|        media_msgtypes = ("m.image", "m.audio", "m.video", "m.file")
  1289|        if msgtype in media_msgtypes:
  1290|            await self._handle_media_message(
  1291|                room_id, sender, event_id, event_ts, source_content, relates_to, msgtype
  1292|            )
  1293|        elif msgtype == "m.text":
  1294|            await self._handle_text_message(
  1295|                room_id, sender, event_id, event_ts, source_content, relates_to
  1296|            )
  1297|
  1298|    async def _resolve_message_context(
  1299|        self,
  1300|        room_id: str,
  1301|