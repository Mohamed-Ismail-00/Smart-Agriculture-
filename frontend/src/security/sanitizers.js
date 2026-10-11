/**
 * sanitizers.js
 * -------------
 * Basic input/output sanitization for the frontend.
 */

export function sanitize(str = '') {
  if (typeof str !== 'string') return '';
  return str
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;');
}

export function sanitizeObject(obj) {
  if (!obj || typeof obj !== 'object') return obj;
  const clean = {};
  for (const [k, v] of Object.entries(obj)) {
    clean[k] = typeof v === 'string' ? sanitize(v) : v;
  }
  return clean;
}
