---
name: cv-pdf-and-image-generator
description: Generate a clean one-page CV/resume as both PDF and PNG when office/browser tools are unavailable. Uses Python with reportlab for PDF and Pillow for image rendering, then verifies the PNG with vision.
version: 1.0.0
author: Mizuki
license: MIT
metadata:
  hermes:
    tags: [cv, resume, pdf, png, productivity, reportlab, pillow]
---

# CV PDF and image generator

Use this when a user wants a CV/resume rendered as a **file**, especially as both **PDF and image/PNG**, and richer document tools (LibreOffice, Chromium, wkhtmltopdf, pandoc, etc.) are missing.

## When to use
- User asks for a CV/resume as a picture, PNG, or PDF
- You only have resume text and need to turn it into shareable files
- Browser/office rendering tools are absent or unreliable
- You need a fast, self-contained fallback that works from the terminal

## Prerequisite checks
First check what rendering tools already exist:

```bash
python3 - <<'PY'
import shutil
for cmd in ['wkhtmltopdf','chromium','google-chrome','chromium-browser','convert','magick','python3','libreoffice','pandoc','pdflatex']:
    print(cmd, shutil.which(cmd))
PY
```

Then check for Python libraries:

```bash
python3 - <<'PY'
mods=['PIL','reportlab','weasyprint','matplotlib']
for m in mods:
    try:
        __import__(m)
        print(m, 'OK')
    except Exception as e:
        print(m, 'NO', e)
PY
```

## Recommended fallback approach
If standard rendering tools are missing, install the minimal Python dependencies:

```bash
uv pip install pillow reportlab
```

Then generate both files in one script:
- **PDF**: use `reportlab.pdfgen.canvas` and `platypus.Paragraph`
- **PNG**: use `Pillow` (`Image`, `ImageDraw`, `ImageFont`)
- Keep the layout simple and robust: one-page, header bar, left sidebar, main content area

## Suggested layout
For general visual CVs, a clean entry-level layout that works well:
- Full-width dark header with name and contact line
- Left sidebar for:
  - Skills
  - Languages
  - Education
  - Looking for
- Right/main panel for:
  - Personal profile
  - Work experience
  - Additional information

For ATS-focused job applications, prefer a simpler one-column structure instead:
- Name, target title, single contact line
- Professional Summary
- Core Skills
- Professional Experience
- Projects
- Education
- Certification Study (only if relevant)
- Languages
- Optional ATS Keywords section when the user explicitly asks for high ATS matching

Colors that worked well:
- Background: `#F6F8FB`
- Header/navy: `#183153`
- Accent/section titles: `#2E7D6B`
- Body text: `#1F2937`
- Divider lines: `#E6ECF2`

## Important implementation details
- Use **A4** for PDF output
- For the image, `1240x1754` gives a clean A4-like PNG
- In the PDF, `simpleSplit()` helps fit sidebar text
- In the PDF main content, `Paragraph.wrap()` avoids overflow
- In the PNG, write a custom `wrap_text()` helper using `ImageDraw.textlength()`
- Prefer a **single contact line** in the header (`Location • Phone • Email`) instead of stacking each line vertically; this avoids clipping near the bottom of the header
- Use a generous header height to prevent overlap
- Expect some empty lower-page space for short CVs; that is acceptable if the content remains balanced and readable
- If using ReportLab `getSampleStyleSheet()`, avoid built-in style names like `Title` and `Bullet`; use custom names such as `CVTitle`, `CVContact`, and `CVBullet` to prevent `KeyError: Style ... already defined`.
- When a user needs ATS/editable uploads and `python-docx` is unavailable, generate a plain valid `.docx` manually as a ZIP package with `[Content_Types].xml`, `_rels/.rels`, `word/document.xml`, and minimal `docProps` files. Keep DOCX content one-column and text-only.

## ATS-focused CV workflow
When the CV is for an ATS-scored job application, generate a clean parsing-first set of outputs instead of only a visually polished PDF/PNG:

- Use a single-column structure: Name, target title, contact line, Professional Summary, Core Skills, Experience, Education, Languages, ATS Keywords.
- Avoid photos, tables, sidebars, icons, text boxes, and multi-column layouts in the ATS version.
- Match the target job title and repeated job-description keywords naturally across Summary, Skills, Experience, and an optional ATS Keywords section.
- Before delivery, run an honesty audit on the matched keywords: separate `true/evidenced`, `positioning`, and `too aggressive`. Do not imply shipped experience with tools/features the user only has awareness of; phrase them as `learning/adaptable` or remove them.
- Create a plain text `.txt` export alongside the PDF/PNG so keyword coverage can be verified mechanically.
- If the user does not yet have a professional email, omit email rather than inventing one; suggest adding one later and offer to update the files.
- Consider generating a simple `.docx` ATS version from the plain text. A minimal DOCX can be created as a ZIP package containing `[Content_Types].xml`, `_rels/.rels`, and `word/document.xml`; keep it text-only with no images/tables for parsing.

## ReportLab implementation pitfalls
- `getSampleStyleSheet()` already defines common style names like `Title` and `Bullet`; use unique names such as `CVTitle`, `CVContact`, and `CVBullet` to avoid `KeyError: Style 'Title' already defined in stylesheet`.
- Validate the generated TXT/DOCX content for required job keywords, not only the PDF/PNG visuals.

## Verification
Always verify the generated files:

1. Check files exist and have non-zero size:
```bash
stat -c '%n %s bytes' /path/to/file.pdf /path/to/file.png
```

2. Run vision on the PNG to catch clipping/overlap:
- Ask specifically about readability, clipping, overlap, and professional layout
- If vision reports header clipping or overlap, adjust spacing and regenerate

3. For ATS-focused CVs, keyword-check the plain text against the target job description or extracted screenshot requirements. Include honest role keywords, but do not guarantee a numeric ATS score because scoring varies by ATS product and employer configuration.

4. If the user mentions studying for certifications they have not earned, add them under `Certification Study` or similar, not under `Certifications` as completed credentials.

This caught a real issue once: stacked contact lines in the header caused the email to clip into the white content area. Switching to a single horizontal contact line fixed it.

## Delivery
- Return/send both files to the user
- For ATS-focused applications, also provide a DOCX and plain `.txt` version when practical
- In Discord/Telegram-capable environments, attach them with `MEDIA:/absolute/path`
- Mention which is the PNG, PDF, DOCX, and text/ATS version

## Reference notes
- `references/ats-technical-support-cv-notes.md` contains a reusable pattern for tailoring student/freelancer CVs to Technical Support / IT Support / Help Desk roles, including honest certification-study wording and DevOps/project phrasing.
- `references/fastpay-it-support-cv-positioning.md` contains FastPay-style IT Support / Linux Admin targeting notes: public job-post signals, honest CV positioning, application text, and interview story prep.
- `references/devops-portfolio-cv-pattern.md` contains the evidence-first pattern for turning verified DevOps portfolio projects into honest junior Cloud/DevOps CV bullets and PDF/PNG/DOCX/TXT outputs.
- `references/webdev-role-cv-and-portfolio-targeting.md` contains the pattern for tailoring a Web Developer / Software Engineer CV and portfolio from job screenshots while keeping claims defensible.

## Pitfalls
- Do not assume browser-based HTML-to-PDF tools are installed
- Do not trust first-pass spacing; verify visually with the vision tool
- Do not deliver a generic visual CV when the user provided a job screenshot/posting; retarget the role, evidence, and portfolio links to that vacancy.
- Do not overstuff ATS keywords with technologies the user cannot defend. Use `strongest stack` and `learning/adaptable` language for weaker familiarity.
- Very narrow sidebars cause ugly wrapping; keep items concise
- If content is too short, the page may look sparse; that is usually preferable to tiny unreadable fonts
- Email/phone in headers are easy to clip if vertical spacing is too tight

## Reusable file naming
Use a predictable output directory and slugged filename, for example:
- `/home/h/cv_output/hevar-kochar-supermarket-cv.pdf`
- `/home/h/cv_output/hevar-kochar-supermarket-cv.png`

## Minimal workflow summary
1. Gather final resume text
2. Check installed renderers and Python libs
3. Install `pillow` and `reportlab` if needed
4. Generate PDF + PNG from one Python script
5. `stat` both outputs
6. Verify the PNG with vision
7. Fix spacing if needed and regenerate
8. Deliver both files
