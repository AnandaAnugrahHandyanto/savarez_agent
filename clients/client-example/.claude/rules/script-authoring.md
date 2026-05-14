---
paths:
  - ".claude/skills/*/scripts/**"
---

# Script Authoring Rules

When creating or modifying Node.js scripts in `.claude/skills/*/scripts/`:

**NEVER use `process.cwd()` to locate `config/.env` or project files.** The working directory depends on where the user (or Claude) invokes the script from, so `process.cwd()` is unreliable.

**ALWAYS discover the project root by walking up from the script's own location:**

```javascript
import { existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { config } from 'dotenv';

// Find project root by walking up from script location
const __dirname = dirname(fileURLToPath(import.meta.url));
let _projectRoot = __dirname;
while (_projectRoot !== '/' && !existsSync(resolve(_projectRoot, 'config'))) {
    _projectRoot = resolve(_projectRoot, '..');
}

// Load environment variables from config/.env
config({ path: resolve(_projectRoot, 'config/.env') });
```

This ensures `config/.env` is found regardless of the caller's working directory.
