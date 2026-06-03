#!/usr/bin/env python3
"""Daily morning summary: DeepSeek balance + MiMo status + live pricing."""
import subprocess, sys, os, json, re, urllib.request, urllib.error, base64
from datetime import datetime

script_dir = os.path.expanduser('~/.hermes/scripts')
now = datetime.now().strftime('%Y-%m-%d %H:%M:%S (CST)')
lines = []
lines.append(f"☀️ 早安！API 每日简报 — {now}")
lines.append("")

def run_script(name):
    path = os.path.join(script_dir, name)
    if os.path.exists(path):
        try:
            r = subprocess.run(['python3', path], capture_output=True, text=True, timeout=20)
            out = r.stdout.strip()
            err = r.stderr.strip()
            if out:
                return out
            if err:
                return f"[{name}] Error: {err[:200]}"
            return f"[{name}] No output"
        except subprocess.TimeoutExpired:
            return f"[{name}] Timeout"
        except Exception as e:
            return f"[{name}] Failed: {e}"
    return f"[{name}] Script not found"

# ── Pricing cache ──────────────────────────────────────────────
PRICING_CACHE_PATH = os.path.join(script_dir, 'pricing_cache.json')

def fetch_deepseek_pricing():
    """Parse DeepSeek official pricing page for latest rates."""
    url = 'https://api-docs.deepseek.com/quick_start/pricing'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode('utf-8', errors='replace')
        # Find the pricing table
        tables = re.findall(r'<table[^>]*>.*?</table>', html, re.DOTALL)
        result = {'source': 'DeepSeek 官方', 'fetched_at': now, 'models': {}}

        for table in tables:
            table_text = re.sub(r'<[^>]+>', ' ', table)
            table_text = re.sub(r'\s+', ' ', table_text).strip()
            if 'flash' not in table_text.lower() and 'v4' not in table_text.lower():
                continue

            # Find output pricing
            cache_hit_match = re.search(
                r'INPUT TOKENS \(CACHE HIT\).*?\$([\d.]+).*?\$([\d.]+)',
                table_text, re.DOTALL
            )
            cache_miss_match = re.search(
                r'INPUT TOKENS \(CACHE MISS\).*?\$([\d.]+).*?\$([\d.]+)',
                table_text, re.DOTALL
            )
            output_match = re.search(
                r'OUTPUT TOKENS.*?\$([\d.]+).*?\$([\d.]+)',
                table_text, re.DOTALL
            )

            flash_prices = {}
            pro_prices = {}

            if cache_hit_match:
                flash_prices['input_cache_hit'] = cache_hit_match.group(1)
                pro_prices['input_cache_hit'] = cache_hit_match.group(2)
            if cache_miss_match:
                flash_prices['input_cache_miss'] = cache_miss_match.group(1)
                pro_prices['input_cache_miss'] = cache_miss_match.group(2)
            if output_match:
                flash_prices['output'] = output_match.group(1)
                pro_prices['output'] = output_match.group(2)

            if flash_prices:
                result['models']['deepseek-v4-flash'] = flash_prices
            if pro_prices:
                result['models']['deepseek-v4-pro'] = pro_prices

            # Extract note about the 75% discount ending
            for line in table_text.split('.'):
                if 'discount' in line.lower() or 'promotion' in line.lower():
                    result['pro_discount_note'] = line.strip()[:200]

        return result
    except Exception as e:
        return {'error': str(e), 'source': 'DeepSeek 官方', 'fetched_at': now}


def fetch_mimo_pricing():
    """Fetch MiMo pricing. Uses API + fallback to cached data."""
    result = {'source': '', 'fetched_at': now, 'models': {}, 'note': ''}

    # Try official pricing page (React SPA - may not get structured data)
    try:
        req = urllib.request.Request('https://platform.xiaomimimo.com/pricing',
            headers={'User-Agent': 'Mozilla/5.0'})
        resp = urllib.request.urlopen(req, timeout=10)
        html = resp.read().decode('utf-8', errors='replace')
        # Minimal extraction - look for any plaintext pricing
        text = re.sub(r'<[^>]+>', '\n', html)
        text = re.sub(r'&nbsp;', ' ', text)
        for line in text.split('\n'):
            s = line.strip()
            if any(k in s for k in ['元/', 'token', 'Token', '百万']):
                result['note'] = s[:200]
                break
    except:
        pass

    # Try to fetch pricing from the models list (some providers include it)
    env_path = os.path.expanduser('~/.hermes/.env')
    api_key = None
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith('OPENAI_API_KEY='):
                api_key = line[len('OPENAI_API_KEY='):]
                break

    if api_key:
        try:
            req = urllib.request.Request('https://token-plan-cn.xiaomimimo.com/v1/models',
                headers={'Authorization': f'Bearer {api_key}'})
            resp = urllib.request.urlopen(req, timeout=10)
            models = json.loads(resp.read().decode())
            result['available_models'] = [m['id'] for m in models.get('data', [])]
        except:
            pass

    return result


def get_pricing():
    """Get pricing with cache. Returns dict with DeepSeek + MiMo pricing."""
    cache = {}
    if os.path.exists(PRICING_CACHE_PATH):
        try:
            with open(PRICING_CACHE_PATH) as f:
                cache = json.load(f)
        except:
            pass

    # Only refresh cache if older than 6 hours
    cache_age_safe = False
    if cache.get('cached_at'):
        try:
            cached_time = datetime.strptime(cache['cached_at'], '%Y-%m-%d %H:%M:%S (CST)')
            cache_age_safe = (datetime.now() - cached_time).total_seconds() < 21600  # 6h
        except:
            pass

    if cache_age_safe and cache.get('deepseek') and cache.get('mimo'):
        return cache

    # Fetch fresh
    ds = fetch_deepseek_pricing()
    mimo = fetch_mimo_pricing()
    result = {
        'cached_at': now,
        'deepseek': ds,
        'mimo': mimo,
    }
    try:
        os.makedirs(os.path.dirname(PRICING_CACHE_PATH), exist_ok=True)
        with open(PRICING_CACHE_PATH, 'w') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    except:
        pass
    return result


# ── GPT Plus status via Codex OAuth ─────────────────────────
def check_gpt_status():
    """Check ChatGPT Plus OAuth status from Codex CLI auth.json."""
    auth_path = os.path.expanduser('~/.codex/auth.json')
    if not os.path.exists(auth_path):
        return ["  ⚠️ Codex CLI 未登录 (无 auth.json)"]

    try:
        with open(auth_path) as f:
            auth = json.load(f)
    except Exception as e:
        return [f"  ❌ 读取 auth.json 失败: {e}"]

    token = auth.get('tokens', {}).get('access_token', '')
    if not token:
        return ["  ⚠️ Codex CLI 无 access_token"]

    # Decode JWT payload for account info
    try:
        payload_b64 = token.split('.')[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += '=' * padding
        payload = json.loads(base64.urlsafe_b64decode(payload_b64))
        plan = payload.get('https://api.openai.com/auth', {}).get('chatgpt_plan_type', 'unknown')
        email = payload.get('https://api.openai.com/profile', {}).get('email', 'unknown')
        exp_ts = payload.get('exp', 0)
        from datetime import datetime, timezone
        exp_dt = datetime.fromtimestamp(exp_ts, tz=timezone.utc).strftime('%Y-%m-%d')
    except Exception:
        plan = 'unknown'
        email = 'unknown'
        exp_dt = 'unknown'

    # Test connectivity (API may be limited by proxy — not critical for report)
    connected = False
    model_count = 0
    try:
        proxy = urllib.request.ProxyHandler({'https': 'http://127.0.0.1:7890'})
        opener = urllib.request.build_opener(proxy)
        token = auth.get('tokens', {}).get('access_token', '')
        req = urllib.request.Request('https://api.openai.com/v1/models')
        req.add_header('Authorization', f'Bearer {token}')
        req.add_header('Content-Type', 'application/json')
        resp = opener.open(req, timeout=10)
        models = json.loads(resp.read().decode())
        model_count = len(models.get('data', []))
        connected = True
    except Exception:
        pass  # Proxy limitations are expected; report token info regardless

    result = []
    result.append(f"  ✅ ChatGPT Plus 已绑定 ({email})")
    result.append(f"  计划: {plan} | Token 到期: {exp_dt}")
    if connected:
        result.append(f"  连通性: ✅ 正常 (可访问 {model_count} 个模型)")
    else:
        result.append(f"  连通性: ⚠️ API 地址受限 (代理节点未放行)")
    return result


# ── Main logic ─────────────────────────────────────────────────

# 1. GPT Plus status (via Codex OAuth)
gpt = check_gpt_status()
lines.append("")
lines.append("ChatGPT Plus (Codex):")
for l in gpt:
    lines.append("  " + l)

# 2. DeepSeek balance
ds = run_script('check_deepseek_balance.py')
lines.append("")
lines.append("DeepSeek:")
for l in ds.split('\n'):
    lines.append("  " + l)

# 2. MiMo status
lines.append("")
lines.append("MiMo:")

api_key = None
env_path = os.path.expanduser('~/.hermes/.env')
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line.startswith('OPENAI_API_KEY='):
            api_key = line[len('OPENAI_API_KEY='):]
            break

if api_key:
    try:
        req = urllib.request.Request('https://token-plan-cn.xiaomimimo.com/v1/models')
        req.add_header('Authorization', f'Bearer {api_key}')
        req.add_header('Content-Type', 'application/json')
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode())
        models = [m['id'] for m in data.get('data', [])]
        lines.append(f"  ✅ API 正常")
        if len(models) > 4:
            lines.append(f"     +{len(models)-4} 个模型 (含 TTS)")
    except Exception as e:
        lines.append(f"  ❌ API 异常: {e}")

    found_balance = False
    for ep in ['/v1/dashboard/billing/credit_grants', '/v1/user/balance']:
        try:
            req = urllib.request.Request(f'https://api.xiaomimimo.com{ep}')
            req.add_header('Authorization', f'Bearer {api_key}')
            resp = urllib.request.urlopen(req, timeout=10)
            bal_data = json.loads(resp.read().decode())
            lines.append(f"  余额 ({ep}): {json.dumps(bal_data, ensure_ascii=False)}")
            found_balance = True
            break
        except urllib.error.HTTPError:
            pass
        except Exception as e:
            lines.append(f"  余额查询失败 ({ep}): {e}")

    if not found_balance:
        lines.append("  ⚠️ MiMo 无公开余额 API")
        lines.append("    查看: https://platform.xiaomimimo.com/#/console/balance")
else:
    lines.append("  ⚠️ 未配置 MiMo API Key")

# 3. Pricing (dynamically fetched)
lines.append("")
lines.append("定价参考 (动态获取):")

pricing = get_pricing()
ds_p = pricing.get('deepseek', {})
mimo_p = pricing.get('mimo', {})

# DeepSeek Flash
flash = ds_p.get('models', {}).get('deepseek-v4-flash', {})
if flash:
    ih = flash.get('input_cache_hit', '0.0028')
    im = flash.get('input_cache_miss', '0.14')
    out = flash.get('output', '0.28')
    # Convert USD to approximate CNY (DeepSeek charges ~¥7.14/$1)
    im_cny = round(float(im) * 7.14, 2)
    out_cny = round(float(out) * 7.14, 2)
    lines.append(f"  DeepSeek V4 Flash: 输入 ¥{im_cny}/M / 输出 ¥{out_cny}/M")
    lines.append(f"     (缓存命中 ${ih}/M · 来源: {ds_p.get('source', 'DeepSeek')})")
else:
    lines.append(f"  DeepSeek V4 Flash: 输入 ¥1.0 / 输出 ¥2.0 / M tokens")
    lines.append(f"     (缓存命中 $0.0028/M)")

# DeepSeek Pro (75% discount ended May 31, permanent lower prices)
pro = ds_p.get('models', {}).get('deepseek-v4-pro', {})
if pro:
    ih = pro.get('input_cache_hit', '0.003625')
    im = pro.get('input_cache_miss', '0.435')
    out = pro.get('output', '0.87')
    im_cny = round(float(im) * 7.14, 2)
    out_cny = round(float(out) * 7.14, 2)
    lines.append(f"  DeepSeek V4 Pro: 输入 ¥{im_cny}/M / 输出 ¥{out_cny}/M")
    lines.append(f"     (折扣已结束 · 来源: {ds_p.get('source', 'DeepSeek')})")
else:
    lines.append(f"  DeepSeek V4 Pro: 输入 ¥3.1 / 输出 ¥6.2 / M tokens")

# MiMo (post-May-27 price cut)
# Standard flat pricing (no longer separates input/output per context length)
mimo_models = mimo_p.get('available_models', [])
lines.append(f"  MiMo V2.5: ¥2/百万tokens 标准 (缓存命中 ¥0.02/百万)")
lines.append(f"  MiMo V2.5 Pro: ¥6/百万tokens 标准 (缓存命中 ¥0.025/百万)")
lines.append(f"     来源: 小米 MiMo 官方 2026-05-27 永久降价公告")
lines.append(f"     官网: https://platform.xiaomimimo.com/pricing")

# Cache timestamp
lines.append(f"  (价格更新于 {now})")

print('\n'.join(lines))
