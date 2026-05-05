# Tech Stack Guide

Choosing the right technology stack for your MVP based on project requirements.

## Quick Decision Matrix

| If you need... | Consider... |
|----------------|-------------|
| Fastest time to market | Next.js + Vercel |
| SEO-critical content | Next.js (SSG) or Astro |
| Real-time features | Node.js + Socket.io + React |
| Complex data/dashboards | React + FastAPI |
| Mobile app later | React Native shared code |
| AI/ML integration | Python backend + React frontend |
| Simple static site | Astro or vanilla HTML |

## Recommended Stacks

### 1. Modern React Stack (Most Common)

**Best for:** SaaS, dashboards, interactive apps

```
Frontend: Next.js 14 (App Router) + Tailwind CSS + shadcn/ui
Backend: Next.js API routes or FastAPI
Database: PostgreSQL (via Supabase or local)
Auth: NextAuth.js or Clerk
Hosting: Kubernetes or Vercel
```

**Pros:** Large ecosystem, great DX, SEO-friendly
**Cons:** Can be overkill for simple sites

### 2. Lightweight Stack

**Best for:** Landing pages, simple MVPs

```
Frontend: Astro + Tailwind CSS
Backend: FastAPI or Express (if needed)
Database: SQLite for simple, PostgreSQL for complex
Hosting: Static hosting + K8s for API
```

**Pros:** Fast, lightweight, minimal JS
**Cons:** Less interactive than React

### 3. Full-Stack TypeScript

**Best for:** Type safety across stack

```
Frontend: Next.js + tRPC
Backend: tRPC + Prisma + PostgreSQL
Shared: Zod schemas, shared types
Hosting: Kubernetes
```

**Pros:** End-to-end type safety
**Cons:** Learning curve, tight coupling

### 4. Python-First

**Best for:** AI/ML, data-heavy, Python teams

```
Frontend: HTMX + Jinja2 or React
Backend: FastAPI + SQLAlchemy
Database: PostgreSQL
ML/AI: HuggingFace, OpenAI, LangChain
Hosting: Kubernetes
```

**Pros:** Excellent for data/AI, fast to write
**Cons:** Two languages if using React frontend

## Auto-Detection from PRD

Look for keywords:

**React/Next.js indicators:**
- "interactive", "dashboard", "real-time"
- "React", "Next.js", "frontend framework"
- "single page app", "SPA"

**Python/FastAPI indicators:**
- "AI", "machine learning", "data processing"
- "Python", "FastAPI", "Django"
- "API", "microservices"

**Static site indicators:**
- "landing page", "blog", "documentation"
- "content-focused", "marketing site"
- "SEO", "fast loading"

## Database Selection

| Project Type | Database |
|--------------|----------|
| Simple MVP, low traffic | SQLite |
| Standard web app | PostgreSQL |
| Heavy read, caching needed | PostgreSQL + Redis |
| Document-oriented | MongoDB |
| Real-time sync | Firebase or Supabase |

## Default Stack (When Unclear)

If PRD doesn't specify:

```
Frontend: Next.js 14 + Tailwind CSS
Backend: FastAPI (separate service)
Database: PostgreSQL
Auth: JWT-based
Hosting: Kubernetes
```

This provides:
- Good DX for both frontend and backend
- Type safety options
- Scalable architecture
- Easy to find developers
