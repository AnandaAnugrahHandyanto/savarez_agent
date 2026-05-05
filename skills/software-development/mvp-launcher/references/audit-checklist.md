# Audit Checklist

Complete checklist for auditing MVP code across all phases.

## Code Quality (25 points)

- [ ] **Linting** - No ESLint/Prettier errors
- [ ] **Type Safety** - Types defined, minimal `any`
- [ ] **Naming** - Clear variable/function names
- [ ] **Comments** - Complex logic explained
- [ ] **Dead Code** - No unused imports/variables
- [ ] **Consistency** - Follows style guide
- [ ] **File Organization** - Logical structure
- [ ] **DRY** - No unnecessary duplication

## Security (25 points)

- [ ] **Input Validation** - All user inputs validated
- [ ] **SQL Injection** - Parameterized queries only
- [ ] **XSS Prevention** - Output encoding
- [ ] **CSRF Protection** - Tokens where needed
- [ ] **Auth** - Proper session/JWT handling
- [ ] **Secrets** - No hardcoded keys/tokens
- [ ] **HTTPS** - All traffic encrypted
- [ ] **CORS** - Correctly configured
- [ ] **Rate Limiting** - API protected
- [ ] **Dependencies** - No known vulnerabilities (`npm audit`)

## Performance (20 points)

- [ ] **Bundle Size** - Under 500KB initial load
- [ ] **Lazy Loading** - Routes/components split
- [ ] **Images** - Optimized, lazy loaded
- [ ] **Caching** - HTTP cache headers set
- [ ] **Database Queries** - Indexed, no N+1
- [ ] **API Response Time** - <200ms for critical paths
- [ ] **Compression** - Gzip/Brotli enabled

## Accessibility (15 points)

- [ ] **Semantic HTML** - Proper tags (nav, main, article)
- [ ] **Alt Text** - All images described
- [ ] **ARIA Labels** - Where semantic HTML insufficient
- [ ] **Keyboard Navigation** - Tab order logical
- [ ] **Color Contrast** - WCAG AA compliant
- [ ] **Focus States** - Visible focus indicators
- [ ] **Screen Reader** - Tested with NVDA/VoiceOver

## UX/UI (15 points)

- [ ] **Responsive** - Mobile-first, breakpoints work
- [ ] **Loading States** - Users know when loading
- [ ] **Error Handling** - User-friendly errors
- [ ] **Empty States** - Helpful when no data
- [ ] **Forms** - Validation, success feedback
- [ ] **Navigation** - Clear, consistent
- [ ] **Feedback** - Actions have consequences shown

## DevOps/Infrastructure (Bonus)

- [ ] **Docker** - Image builds, minimal size
- [ ] **K8s** - Manifests valid, resources defined
- [ ] **Health Checks** - Liveness/readiness probes
- [ ] **Logs** - Structured, meaningful
- [ ] **Monitoring** - Metrics exposed
- [ ] **Secrets** - Externalized (K8s secrets, vault)

## Scoring

- 90-100: Production ready
- 80-89: Minor issues, can launch
- 70-79: Moderate issues, fix before launch
- <70: Significant issues, major work needed

## Critical Issues (Auto-block)

Any of these should prevent deployment:
- Secrets in code
- No input validation on user data
- No HTTPS
- SQL injection possible
- XSS vulnerabilities
- Auth bypass possible

## Audit Report Template

```json
{
  "score": 85,
  "critical_issues": [],
  "warnings": ["Bundle size 600KB", "Missing alt text on 3 images"],
  "suggestions": ["Add service worker", "Implement infinite scroll"],
  "strengths": ["Clean component structure", "Good auth implementation"],
  "next_actions": ["Optimize images", "Add loading skeletons"]
}
```
