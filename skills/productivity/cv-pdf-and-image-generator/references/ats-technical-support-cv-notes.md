# ATS technical support CV notes

Use these notes when tailoring a student/freelancer CV for Technical Support / IT Support / Help Desk roles.

## Job-post extraction from screenshots
When the user provides job-post screenshots, extract and mirror role keywords before drafting:
- Technical Support Specialist
- Help Desk / IT Support
- Troubleshooting
- Hardware and software support
- Operating systems
- Windows and Linux/Ubuntu
- Microsoft Office / Outlook
- Basic networking: TCP/IP, DNS, DHCP, routers, Wi-Fi
- User account support
- System maintenance and backups
- Cybersecurity best practices
- Customer support / communication

## ATS-safe structure
Prefer a simple one-column structure:
1. Name + target title
2. Contact line
3. Professional Summary
4. Core Skills
5. Professional Experience
6. Projects
7. Education
8. Certification Study
9. Languages
10. ATS Keywords, if the user explicitly wants ATS optimization

Avoid photos, sidebars, tables, icons, progress bars, and multi-column layouts for ATS-focused applications.

## Student and not-yet-certified wording
If the user is studying for A+, Network+, CCNA, AWS, etc. but has not passed the exams, do not list them as earned certifications. Use an honest section such as:

`CERTIFICATION STUDY`
`Currently studying for CompTIA A+, CompTIA Network+, and Cisco CCNA. Not yet certified.`

This still adds useful ATS keywords without making a false claim.

## Freelance/project wording
For real but early freelance/devops work, include it as experience and/or projects using cautious factual wording:
- `Freelance IT Support, Web Development, and DevOps`
- `Performed DevOps work for a live client website, including deployment support and website delivery.`
- `Worked with AWS, GitHub, static website hosting, DNS/domain configuration, and production website updates.`

If the system memory or conversation confirms specific services, add targeted keywords like S3, CloudFront, DNS, domain configuration, GitHub Actions, but avoid overstating ownership beyond what the user said.

## Deliverables
For this kind of request, deliver at least:
- PDF for submission
- DOCX for editable/ATS upload workflows
- PNG preview for visual checking
- Plain ATS text for quick edits and keyword checks

For DOCX when `python-docx` is unavailable, a minimal valid DOCX can be created as a ZIP package containing `[Content_Types].xml`, `_rels/.rels`, `word/document.xml`, and minimal docProps files. Keep it plain text, no images/tables/columns.

## Verification checklist
- File sizes are non-zero
- Vision-check PNG for clipping/overlap/readability
- Keyword-check the plain text against job requirements
- Explicitly tell the user exact ATS scores cannot be guaranteed because ATS systems differ
