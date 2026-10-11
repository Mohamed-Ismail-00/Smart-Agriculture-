/**
 * Loads API-protected image URLs using the auth token and renders via blob URL.
 */

import { useEffect, useState } from "react";
import { isImageBlobCached, resolveAuthenticatedImageUrl } from "../services/api";

export default function AuthenticatedImage({
  src,
  alt = "",
  className,
  style,
  fallback = null,
}) {
  const [blobUrl, setBlobUrl] = useState(null);

  useEffect(() => {
    let cancelled = false;
    let objectUrl = null;

    if (!src) {
      setBlobUrl(null);
      return undefined;
    }

    resolveAuthenticatedImageUrl(src).then((url) => {
      if (cancelled) {
        // A cached blob URL is shared with other mounts of the same image.
        if (url?.startsWith("blob:") && !isImageBlobCached(src)) URL.revokeObjectURL(url);
        return;
      }
      objectUrl = url;
      setBlobUrl(url);
    });

    return () => {
      cancelled = true;
      if (objectUrl?.startsWith("blob:") && !isImageBlobCached(src)) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [src]);

  if (!blobUrl) {
    return fallback;
  }

  return <img src={blobUrl} alt={alt} className={className} style={style} loading="lazy" />;
}