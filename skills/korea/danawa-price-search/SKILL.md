---
name: danawa-price-search
description: Use when searching Danawa products, comparing Korean shopping mall offers, or answering 다나와 최저가/가격비교 questions. Performs read-only Danawa product search and offer comparison through public HTML/AJAX surfaces, including shipping, card discounts, and installment notes.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [korea, shopping, danawa, price-comparison, ecommerce]
    related_skills: []
---

# Danawa Price Search

## Overview

Use this skill to perform read-only Danawa product search and lowest-price comparison through public web surfaces. It is designed for Korean shopping queries where the user wants a practical comparison rather than only the catalog headline price.

The helper script fetches Danawa search results, resolves product `pcode`s, calls the public price-comparison AJAX fragment, and emits JSON suitable for a concise Markdown comparison table.

## When to Use

Use this skill when the user asks for:

- 다나와 검색, 다나와 최저가, 가격비교
- Korean product lowest-price lookup
- Mall-by-mall comparison including shipping fee
- Whether a Danawa offer has card-specific discounts or interest-free installments

Do not use this skill for:

- Actually purchasing products or logging into a mall account
- High-volume monitoring without adding throttling/backoff
- Non-Korean stores where Danawa does not have catalog coverage

## Public Surfaces

The current implementation uses these unauthenticated Danawa surfaces:

- Product search page: `https://search.danawa.com/dsearch.php?query=...`
- Product detail page: `https://prod.danawa.com/info/?pcode=...`
- Price comparison AJAX: `https://prod.danawa.com/info/ajax/getAllPriceCompareMallList.ajax.php`

The AJAX endpoint returns HTML fragments. Parse `.diff_item`, mall logo `alt`, `em.prc_c`/`em.prc_t`, shipping text, card line, installment layer, and Danawa bridge links.

## Commands

From this skill directory:

```bash
python scripts/danawa_search.py search "에어팟 프로 2세대" --limit 8
python scripts/danawa_search.py offers 28208783 --limit 10
python scripts/danawa_search.py compare "에어팟 프로 2세대" --limit 5 --offers 5
```

The helper prints JSON only. Convert the JSON to a user-facing Korean summary after inspecting the candidate titles and offers.

## Output Shape

### `search`

`search` emits:

```json
{
  "query": "...",
  "source_url": "...",
  "count": 0,
  "items": []
}
```

Each item includes:

- `pcode`
- `title`
- `price`
- `price_text`
- `mall_text`
- `url`
- `image_url`
- `spec`

### `offers`

`offers` emits:

```json
{
  "pcode": "...",
  "title": "...",
  "source_url": "...",
  "count": 0,
  "offers": []
}
```

Each offer includes:

- `mall`
- `price`, `price_text`
- `shipping`
- `is_free_shipping`
- `shipping_fee`
- `total_price`, `total_price_text`
- `card_price`, `card_price_text`
- `card_name`
- `card_discount`, `card_discount_text`
- `installment`
- `installment_detail`
- `url`

Always summarize whether shipping is free, the shipping-fee-inclusive total, card-specific discounted price if present, and interest-free installment text.

### `compare`

`compare` runs `search` first, then enriches each search result with per-product `offers[]` on a best-effort basis.

## User-Facing Format

For Discord/Telegram/chat responses, prefer a compact Markdown table.

```md
| 순위 | 판매처 | 상품가 | 배송 | 실구매가 | 카드할인가 | 무이자 | 링크 |
|---:|---|---:|---|---:|---:|---|---|
| 1 | G마켓 | 217,950원 | 무료배송 | 217,950원 | - | 최대 24개월 | 보기 |
| 2 | 옥션 | 305,722원 | 무료배송 | 305,722원 | 우리카드 303,720원 | 최대 24개월 | 보기 |
```

Sort primarily by `total_price`. If `card_price` exists and changes the winner, call out the lowest card-discounted option separately below the table.

Suggested summary lines:

```md
최저 실구매가: G마켓 217,950원 / 무료배송
카드 기준 최저가: 옥션 우리카드 303,720원
무이자: G마켓·옥션 최대 24개월 표기
```

If Danawa does not expose a card discount row, write “카드 할인가 표기 없음” rather than assuming no discount exists at checkout.

## Implementation Notes

1. Search Danawa by keyword and collect candidate `pcode`s.
2. For a selected `pcode`, fetch the detail page and extract category/maker/product globals from inline JavaScript.
3. POST those fields plus `oPriceCompareSetting` defaults to `getAllPriceCompareMallList.ajax.php` with:
   - `User-Agent: Mozilla/5.0...`
   - `Accept-Language: ko-KR,ko;q=0.9`
   - `Referer: https://prod.danawa.com/info/?pcode=<pcode>`
   - `X-Requested-With: XMLHttpRequest`
4. Parse HTML fragments and sort/filter as needed. The endpoint already returns min-price ordering when `sSortType=minPrice`.
5. Keep all actions read-only. Use Danawa bridge links as user-facing purchase links; do not bypass tracking unless explicitly needed.

## Common Pitfalls

1. **Search ranking can surface adjacent products first.** Show 3-5 candidates and note exact title/pcode when the query is ambiguous.
2. **Search result price and AJAX lowest offer can differ.** Danawa catalog min price may reflect card/affiliate/updated price while the AJAX fragment shows current offer rows.
3. **Card discount rows are conditional.** Danawa exposes card discounts per offer when it renders `.card_line`, for example `우리카드 303,720원`. Missing markup does not prove the checkout has no card promo.
4. **Installment text is 안내용.** `.btn_foi` / `.foi_layer` can expose installment details, but card/payment amount conditions may vary at checkout.
5. **The surface is scrape-style.** Keep request volume low and add throttling/backoff before monitor or batch use.
6. **Selectors may change.** If parsing returns zero rows, re-check Danawa markup before assuming no offers exist.

## Verification Checklist

- [ ] `python scripts/danawa_search.py search "갤럭시 s25 울트라 자급제" --limit 3` returns product candidates.
- [ ] `python scripts/danawa_search.py offers <pcode> --limit 5` returns mall offers.
- [ ] Offer rows include shipping text and `total_price_text`.
- [ ] Card-discounted offers include `card_name`, `card_price_text`, and `card_discount_text` when Danawa exposes them.
- [ ] Installment text is included when Danawa exposes it.
- [ ] User-facing answer is a table sorted by shipping-fee-inclusive total.
