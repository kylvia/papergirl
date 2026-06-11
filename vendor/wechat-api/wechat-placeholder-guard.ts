const WECHAT_IMAGE_PLACEHOLDER_RE = /\bWECHATIMGPH_\d+\b/g;

export function findUnresolvedImagePlaceholders(html: string): string[] {
  return [...new Set(html.match(WECHAT_IMAGE_PLACEHOLDER_RE) ?? [])];
}

export function assertNoUnresolvedImagePlaceholders(html: string): void {
  const placeholders = findUnresolvedImagePlaceholders(html);
  if (placeholders.length > 0) {
    throw new Error(`Unresolved WeChat image placeholders remain: ${placeholders.join(", ")}`);
  }
}
