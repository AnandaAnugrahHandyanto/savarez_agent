# Research Folder

Your knowledge base - curated external content and insights.

## What Goes Here
- Newsletter archives (automatically collected)
- YouTube transcript summaries (automatically collected)
- Manually saved articles and research
- Source material for strategic decisions

## Working with This Folder
- **DO NOT manually edit** - Content auto-collected by automation
- Organized by source (newsletter name or YouTube channel)
- Each source has its own subfolder
- Files include AI-generated summaries

## Current Structure
- `newsletters/` - Newsletter archives organized by source
  - Each source has subfolder (e.g., `newsletters/ethan/`)
  - Files: `YYYYMMDD-title.md` with summary
- `youtube/` - YouTube transcript summaries organized by channel
  - Each channel has subfolder (e.g., `youtube/lenny/`)
  - Files: `YYYYMMDD-title.md` with summary

## How Content Gets Here
1. **Newsletters**: Gmail API → saves to `newsletters/[source]/`
2. **YouTube**: yt-dlp → saves to `youtube/[channel]/`
3. **Automation**: Runs daily, generates AI summaries, updates indexes

## How Content Is Used
- **brain-advisor** agent searches this folder for strategic insights
- Summary indexes in `context/ideas/` provide quick reference
- **briefing-generator** surfaces recent additions (last 7 days)

## Setup
Configure sources in:
- `code/newsletter/config.js` - Newsletter sources and Gmail labels
- `code/youtube/config.js` - YouTube channels to follow

See `code/CLAUDE.md` for detailed setup instructions.

## File Naming
- Auto-generated: `YYYYMMDD-title.md`
- Always includes date prefix for chronological sorting
- Titles cleaned and sanitized for filenames

## Maintenance
- Automation keeps content current
- No manual cleanup needed
- Old content remains searchable
- Consider archiving after 2-3 years if folder gets large
