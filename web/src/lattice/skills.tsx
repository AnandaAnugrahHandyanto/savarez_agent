// skills.tsx — Skills view
import React, { useState, useMemo } from 'react';
import { cn } from './primitives';
import { ViewHeader } from './views';

const SKILL_LIST = [
  { id: "pdf",         name: "PDF Reader",          category: "Documents",    desc: "Extract text, tables and structure from PDF files. Cite page numbers in responses.",      enabled: true,  badge: "core" },
  { id: "websearch",   name: "Web Search",          category: "Web",          desc: "Search the public web and cite sources. Filters to the past day/week/month.",             enabled: true,  badge: "core" },
  { id: "codereview",  name: "Code Review",         category: "Engineering",  desc: "Static analysis, style critique, and refactor suggestions across major languages.",      enabled: true  },
  { id: "datawrangle", name: "Data Wrangling",      category: "Analysis",     desc: "Clean, transform and pivot CSVs/Parquet up to 100MB. Inline charts in responses.",        enabled: true  },
  { id: "diagram",     name: "Diagram Generator",   category: "Visual",       desc: "Draw sequence, flow and architecture diagrams from natural-language descriptions.",       enabled: false },
  { id: "slidegen",    name: "Slide Generator",     category: "Visual",       desc: "Compose decks from outlines using your brand template. Exports to .pptx.",                enabled: false },
  { id: "translate",   name: "Translator",          category: "Language",     desc: "Translate between 50+ languages while preserving tone, formatting and code blocks.",      enabled: true  },
  { id: "summarize",   name: "Smart Summarizer",    category: "Documents",    desc: "Multi-page summaries with section anchors and key-quote callouts.",                        enabled: true  },
  { id: "calendar",    name: "Schedule Assistant",  category: "Productivity", desc: "Find free slots across calendars, draft invites, and propose meeting agendas.",           enabled: false },
  { id: "email",       name: "Email Drafter",       category: "Productivity", desc: "Tone-aware drafts (concise / warm / formal). Threading and reply suggestions.",           enabled: false },
  { id: "research",    name: "Deep Research",       category: "Web",          desc: "Multi-step research with intermediate planning. Returns a structured brief and sources.", enabled: false, badge: "beta" },
  { id: "sql",         name: "SQL Helper",          category: "Engineering",  desc: "Write, explain and optimize SQL across Postgres, MySQL, SQLite, BigQuery.",               enabled: true  },
] as const;

type Skill = { id: string; name: string; category: string; desc: string; enabled: boolean; badge?: string };

const CATEGORIES = ["All", "Core", "Documents", "Web", "Engineering", "Analysis", "Visual", "Language", "Productivity"];

function SkillIcon({ id }: { id: string }) {
  const map: Record<string, React.ReactNode> = {
    pdf:         <><rect x="3" y="2" width="14" height="20" rx="2"/><path d="M3 7h14M7 11h6M7 14h6M7 17h4"/></>,
    websearch:   <><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/></>,
    codereview:  <><path d="M7 8l-4 4 4 4M17 8l4 4-4 4M14 5l-4 14"/></>,
    datawrangle: <><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 3v18"/></>,
    diagram:     <><rect x="2" y="3" width="8" height="6" rx="1"/><rect x="14" y="3" width="8" height="6" rx="1"/><rect x="8" y="15" width="8" height="6" rx="1"/><path d="M6 9v3h6v3M18 9v3h-6"/></>,
    slidegen:    <><rect x="3" y="4" width="18" height="14" rx="2"/><path d="M7 9l3 3 3-2 4 4M9 20h6"/></>,
    translate:   <><path d="M3 5h8M7 3v2M5 5c0 4 4 6 4 6M9 11c0 0-4 2-6 6"/><path d="M13 21l4-10 4 10M14.5 17h5"/></>,
    summarize:   <><path d="M4 6h16M4 10h16M4 14h12M4 18h8"/></>,
    calendar:    <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 9h18M8 3v4M16 3v4"/></>,
    email:       <><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 7 9-7"/></>,
    research:    <><circle cx="10" cy="10" r="6"/><path d="M14.5 14.5L20 20"/><path d="M7 10h6M10 7v6"/></>,
    sql:         <><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/></>,
  };
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
      {map[id] || <circle cx="12" cy="12" r="6"/>}
    </svg>
  );
}

export function SkillsView() {
  const [skills, setSkills] = useState<Skill[]>(SKILL_LIST as unknown as Skill[]);
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("All");

  const toggle = (id: string) => setSkills((cur) => cur.map((s) => s.id === id ? { ...s, enabled: !s.enabled } : s));

  const filtered = useMemo(() => {
    return skills.filter((s) => {
      if (q && !s.name.toLowerCase().includes(q.toLowerCase()) && !s.desc.toLowerCase().includes(q.toLowerCase())) return false;
      if (cat === "All") return true;
      if (cat === "Core") return s.badge === "core";
      return s.category === cat;
    });
  }, [skills, q, cat]);

  const enabledCount = skills.filter((s) => s.enabled).length;

  return (
    <div className="view">
      <ViewHeader
        title="Skills"
        subtitle={`${enabledCount} of ${skills.length} enabled — extend what the agent can do`}
      >
        <div className="view-filters">
          <div className="view-search">
            <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="7" cy="7" r="4.5"/><path d="M13.5 13.5L10.5 10.5" strokeLinecap="round"/></svg>
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search skills…" />
          </div>
          <div className="skills-cats">
            {CATEGORIES.map((c) => (
              <button key={c} className={cn("skills-cat", cat === c && "is-active")} onClick={() => setCat(c)}>
                {c}
              </button>
            ))}
          </div>
        </div>
      </ViewHeader>

      <div className="view-body view-body-scroll">
        {filtered.length === 0 ? (
          <div className="view-empty">
            <h3>No skills match</h3>
            <p>Adjust the filters or clear the search to see more.</p>
          </div>
        ) : (
          <div className="skills-grid">
            {filtered.map((s) => (
              <div key={s.id} className={cn("skill-card", s.enabled && "is-on")}>
                <div className="skill-hd">
                  <span className="skill-icon"><SkillIcon id={s.id} /></span>
                  <div className="skill-meta">
                    <div className="skill-name">
                      {s.name}
                      {s.badge === "core" && <span className="skill-badge core">core</span>}
                      {s.badge === "beta" && <span className="skill-badge beta">beta</span>}
                    </div>
                    <div className="skill-cat mono">{s.category}</div>
                  </div>
                  <button className={cn("switch", s.enabled && "on")}
                          role="switch" aria-checked={s.enabled}
                          onClick={() => toggle(s.id)}>
                    <span className="thumb" />
                  </button>
                </div>
                <div className="skill-desc">{s.desc}</div>
                <div className="skill-foot">
                  <button className="btn btn-sm" disabled={!s.enabled} style={{ opacity: s.enabled ? 1 : .4 }}>
                    Configure
                  </button>
                  <button className="btn btn-sm">Docs</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
