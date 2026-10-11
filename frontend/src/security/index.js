/**
 * security/index.js
 * -----------------
 * Frontend security utilities.
 *
 * Usage:
 *   import { sanitize, withAuth } from '../security';
 */

export { default as sanitize } from './sanitizers';
export { default as withAuth, useRequireAuth } from './routeProtection';
export { default as idUtils } from './idUtils';
