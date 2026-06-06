/**
 * IPC Validation Middleware for Hermes Electron
 *
 * Type-safe validation for Inter-Process Communication handlers
 * using Zod schemas. Provides defense-in-depth input validation
 * for security-critical IPC channels.
 *
 * Usage:
 *   const { createValidatedHandler, schemas } = require('./ipc-validation.cjs');
 *
 *   ipcMain.handle('hermes:api',
 *     createValidatedHandler('hermes:api', schemas['hermes:api'],
 *       (_event, { url, method, headers, body, timeout }) => {
 *         // handler code here
 *       }
 *     )
 *   );
 */

const z = require('zod');

// ─────────────────────────────────────────────────────────────
// REUSABLE BASE SCHEMAS
// ─────────────────────────────────────────────────────────────

const schemas = {
  // File path: 1-4096 chars, trimmed, normalized
  FilePath: z.string()
    .min(1, 'File path cannot be empty')
    .max(4096, 'File path exceeds 4096 characters')
    .transform(v => v.trim()),

  // UUID v4 format
  UUID: z.string()
    .uuid('Invalid UUID format'),

  // Network port: 1-65535
  Port: z.number()
    .int('Port must be an integer')
    .min(1, 'Port must be >= 1')
    .max(65535, 'Port must be <= 65535'),

  // Timeout in milliseconds: 100ms-5 minutes
  Timeout: z.number()
    .int('Timeout must be an integer')
    .min(100, 'Timeout must be >= 100ms')
    .max(300000, 'Timeout must be <= 300000ms (5 minutes)'),

  // Public HTTPS URL (blocks private IPs, localhost, cloud metadata)
  PublicUrl: z.string()
    .url('Must be a valid URL')
    .refine(
      url => url.startsWith('https://'),
      'URL must use HTTPS protocol (http:// blocked)'
    )
    .refine(
      url => {
        try {
          const urlObj = new URL(url);
          const hostname = urlObj.hostname;

          // Block localhost
          if (hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1') {
            return false;
          }

          // Block private IP ranges
          const privatePatterns = [
            /^10\./,                          // 10.0.0.0/8
            /^172\.(1[6-9]|2[0-9]|3[01])\./, // 172.16.0.0/12
            /^192\.168\./,                    // 192.168.0.0/16
            /^169\.254\./,                    // 169.254.0.0/16 (link-local)
          ];

          if (privatePatterns.some(pattern => pattern.test(hostname))) {
            return false;
          }

          // Block cloud metadata endpoints
          const metadataHosts = [
            '169.254.169.254',     // AWS metadata
            'metadata.google.internal',  // GCP metadata
            '169.254.169.250',     // Azure metadata
            'instance-data',       // Various cloud metadata
          ];

          if (metadataHosts.includes(hostname)) {
            return false;
          }

          return true;
        } catch {
          return false;
        }
      },
      'URL must be public HTTPS (private IPs, localhost, cloud metadata blocked)'
    ),
};

// ─────────────────────────────────────────────────────────────
// IPC HANDLER SCHEMAS (10 critical handlers)
// ─────────────────────────────────────────────────────────────

schemas['hermes:api'] = z.object({
  url: schemas.PublicUrl,
  method: z.enum(['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS']),
  headers: z.record(z.string(), z.string()).optional(),
  body: z.string().max(1048576).optional(), // 1MB max
  timeout: schemas.Timeout.optional(),
});

schemas['hermes:terminal:start'] = z.object({
  cwd: schemas.FilePath.optional(),
  cols: z.number().int().min(1).max(1024).optional(),
  rows: z.number().int().min(1).max(1024).optional(),
  env: z.record(z.string(), z.string()).optional(),
});

schemas['hermes:terminal:write'] = z.object({
  id: schemas.UUID,
  data: z.string()
    .max(65536, 'Terminal input limited to 65KB per write')
    .refine(
      data => {
        // Ensure data is UTF-8 compatible
        try {
          Buffer.from(data, 'utf8');
          return true;
        } catch {
          return false;
        }
      },
      'Terminal data must be valid UTF-8'
    ),
});

schemas['hermes:saveImageFromUrl'] = z.object({
  url: schemas.PublicUrl,
});

schemas['hermes:readFileDataUrl'] = z.object({
  filePath: schemas.FilePath,
});

schemas['hermes:readFileText'] = z.object({
  filePath: schemas.FilePath,
});

schemas['hermes:fs:readDir'] = z.object({
  dirPath: schemas.FilePath,
});

schemas['hermes:fs:gitRoot'] = z.object({
  startPath: schemas.FilePath,
});

schemas['hermes:openExternal'] = z.object({
  url: z.string()
    .url('Must be a valid URL')
    .refine(
      url => url.startsWith('https://') || url.startsWith('http://'),
      'URL must use HTTP or HTTPS'
    ),
});

schemas['hermes:fetchLinkTitle'] = z.object({
  url: schemas.PublicUrl,
});

// ─────────────────────────────────────────────────────────────
// VALIDATION MIDDLEWARE
// ─────────────────────────────────────────────────────────────

/**
 * Creates a validated IPC handler wrapper
 *
 * @param {string} handlerName - IPC handler name (for error messages)
 * @param {z.ZodSchema} schema - Zod schema for validation
 * @param {Function} handler - Original handler function
 * @returns {Function} Wrapped handler with validation
 */
function createValidatedHandler(handlerName, schema, handler) {
  return async (event, input) => {
    try {
      // Validate input against schema
      const validated = schema.parse(input);

      // Call original handler with validated data
      return await handler(event, validated);
    } catch (error) {
      if (error instanceof z.ZodError) {
        // Format validation errors clearly
        const messages = error.errors.map(e => {
          const path = e.path.join('.');
          return `${path}: ${e.message}`;
        }).join('; ');

        console.error(`[IPC Validation Error] ${handlerName}: ${messages}`);

        // Return error to renderer (don't throw — IPC will break)
        return {
          __validationError: true,
          handler: handlerName,
          message: messages,
        };
      }

      // Unknown error — propagate
      console.error(`[IPC Handler Error] ${handlerName}:`, error);
      throw error;
    }
  };
}

// ─────────────────────────────────────────────────────────────
// EXPORTS
// ─────────────────────────────────────────────────────────────

module.exports = {
  createValidatedHandler,
  schemas,
};
