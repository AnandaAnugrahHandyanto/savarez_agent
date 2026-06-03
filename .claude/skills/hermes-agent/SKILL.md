```markdown
# hermes-agent Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill teaches the core development conventions and workflows used in the `hermes-agent` TypeScript codebase. It covers file organization, code style, commit patterns, and testing practices to ensure consistency and maintainability across contributions.

## Coding Conventions

### File Naming
- Use **kebab-case** for all filenames.
  - Example: `my-module.ts`, `user-service.test.ts`

### Import Style
- Use **relative imports** for referencing other modules within the project.
  - Example:
    ```typescript
    import { fetchData } from './utils/fetch-data';
    ```

### Export Style
- Use **named exports** for all modules.
  - Example:
    ```typescript
    // In utils/logger.ts
    export function logInfo(message: string) { ... }
    ```

### Commit Messages
- Follow **conventional commit** style.
- Use the `chore` prefix for maintenance and non-feature commits.
  - Example:
    ```
    chore: update dependencies for security patches
    ```

## Workflows

### Code Contribution
**Trigger:** When adding new features, bug fixes, or improvements  
**Command:** `/contribute`

1. Create a new branch for your work.
2. Follow coding conventions for file naming, imports, and exports.
3. Write or update tests as needed.
4. Commit changes using conventional commit messages (e.g., `chore: ...`).
5. Open a pull request for review.

### Dependency Update
**Trigger:** When dependencies need to be updated  
**Command:** `/update-deps`

1. Update the relevant dependencies in your project files.
2. Test the project to ensure compatibility.
3. Commit changes with a message like `chore: update dependencies`.
4. Push and open a pull request.

## Testing Patterns

- Test files follow the `*.test.*` naming pattern.
  - Example: `api-handler.test.ts`
- The testing framework is not explicitly detected; check existing test files for conventions.
- Place test files alongside the modules they test or in a dedicated `tests` directory if present.

## Commands
| Command        | Purpose                                             |
|----------------|-----------------------------------------------------|
| /contribute    | Start the code contribution workflow                |
| /update-deps   | Begin the dependency update workflow                |
```
