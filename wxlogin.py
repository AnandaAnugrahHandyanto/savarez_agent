import asyncio, yaml, ruamel.yaml
from gateway.platforms.weixin import qr_login

async def main():
    r = await qr_login(r"C:\Users\admin\AppData\Local\hermes", timeout_seconds=300)
    if not r:
        print("FAILED")
        return
    c = yaml.safe_load(open(r"C:\Users\admin\AppData\Local\hermes\config.yaml", "r", encoding="utf-8"))
    c["weixin"] = {**c.get("weixin", {}), **r, "enabled": True}
    ry = ruamel.yaml.YAML()
    ry.preserve_quotes = True
    ry.dump(c, open(r"C:\Users\admin\AppData\Local\hermes\config.yaml", "w", encoding="utf-8"))
    print("TOKEN SAVED")

asyncio.run(main())
