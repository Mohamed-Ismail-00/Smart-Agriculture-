/**
 * idUtils.js
 * ----------
 * Helpers for working with public IDs (UUIDs) on the client.
 * Never expose or guess internal integer IDs.
 */

export function isValidPublicId(id) {
  if (!id) return false;
  // Simple UUID v4 check
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  return uuidRegex.test(id);
}

export function getLandRoute(publicId) {
  if (!isValidPublicId(publicId)) {
    console.warn('Invalid public ID used in navigation');
    return '/lands';
  }
  return `/lands/${publicId}`;
}
