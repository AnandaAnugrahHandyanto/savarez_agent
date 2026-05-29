# WorkFlow-1-ShopeeAffiliate

Canonical operating workflow for BlackDuckAi Shopee Affiliate Facebook content loops.

## Fixed posting structure

For each selected Shopee Affiliate product, the default publishing structure is fixed:

1. Run Shopee API and Facebook API read-only checks.
2. Select and verify one product.
3. Research Facebook Ads Library patterns without copying competitor assets or copy.
4. Generate the three approved affiliate links:
   - product link
   - shop link
   - Shopee code/deal link
5. Generate five final ad images with `gpt-image-2` / `gpt-image-2-high` only.
6. Publish five image posts as a ladder after latest TOP approval:
   - post 1: image 1
   - post 2: images 1-2
   - post 3: images 1-3
   - post 4: images 1-4
   - post 5: images 1-5
7. Under every image post, add:
   - one link comment containing the three approved affiliate links
   - five image-only comments with no visible message text or caption
8. Generate one video/Reel with Veo / Gemini Veo only from the approved image set and TOP's reference/prompt.
9. Publish the video/Reel after latest TOP approval.
10. Under the video/Reel, add:
    - one link comment containing the same three approved affiliate links
    - five image-only comments with no visible message text or caption
11. Verify all real Facebook posts/comments by API readback.

## Durable rule from TOP

TOP may revise image direction, content angle, copy direction, voiceover, or video visual direction on each run. Those creative revisions do not change the default posting/comment structure above.

Only skip or change the posting/comment structure when TOP explicitly instructs that exception for the current run.

## Public copy and safety rules

Public captions and comments must not mention:

- AI names, agent names, Red, internal workflow names, or internal system names
- Sub IDs
- commission or internal scoring
- tokens, secrets, credentials, cookies, page tokens, or app secrets
- unverified price, stock, discount, warranty, medical/legal claims, or official-store claims

Use Thai female admin voice for public copy (`ค่ะ`, `คะ`, `นะคะ`).

## Approval boundaries

Draft/read-only work can proceed as part of the workflow. Real side effects require latest explicit approval from TOP, including:

- publishing Facebook posts/Reels
- adding Facebook comments
- deleting or hiding posts/comments
- sending inbox messages
- launching ads or spending budget
- using sensitive customer data

## Required verification

The final run report should include:

- selected product and source verification
- three affiliate links present
- five image files present
- five image posts published and URLs verified
- image-post link comments posted and link count verified
- image-post image-only comments: five attachments and zero message text per post
- Veo video file present
- video/Reel published and URL verified
- video/Reel link comment posted and link count verified
- video/Reel image-only comments: five attachments and zero message text
- no public Sub ID, commission, AI/internal names, or unverified claims

## Mirrors

This workflow is mirrored in:

- Obsidian: `C:/Users/black/Documents/Obsidian Vault/Wiki/ShopeeAffiliate/WorkFlow-1-ShopeeAffiliate.md`
- Hermes skill: `workflow-1-shopeeaffiliate`
