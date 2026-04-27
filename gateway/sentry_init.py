import os
import sentry_sdk

_dsn = os.environ.get("SENTRY_DSN", os.environ.get("SENTRY_DSN_PYTHON", ""))
if _dsn:
    sentry_sdk.init(
        dsn=_dsn,
        traces_sample_rate=0.1,
        send_default_pii=False,
        environment=os.environ.get("ENVIRONMENT", "production"),
    )
