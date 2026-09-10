import { useEffect, useMemo, useRef, useState } from 'react';
import { ImageOff } from 'lucide-react';

// Ported from frontend/src/components/mail/EmailRenderer.tsx (legacy v1) --
// same sandboxed-iframe design, adapted to frontend-v2's design tokens. The
// backend already returns fully sanitized body_html (mail/content.py's
// sanitize_email_html via nh3 -- http/https/mailto/tel allowed, javascript:/
// data: excluded from links, target=_blank rel=noopener noreferrer nofollow
// forced) and a has_remote_images flag; this component is purely the reader
// surface, not a second sanitizer.

const SANDBOX_FLAGS = ['allow-same-origin', 'allow-popups', 'allow-popups-to-escape-sandbox'].join(' ');

const READER_CSS = `
  :root { color-scheme: light; }
  html, body {
    margin: 0 !important;
    padding: 0 !important;
    width: 100% !important;
    max-width: 100% !important;
    min-width: 0 !important;
    background: transparent;
    overflow-x: hidden !important;
  }
  body {
    color: #1a1a1a;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
    font-size: 12.5px;
    line-height: 1.6;
    overflow-wrap: anywhere;
    word-break: break-word;
    -webkit-font-smoothing: antialiased;
  }
  body > * { max-width: 100% !important; }
  img {
    max-width: 100% !important;
    height: auto !important;
  }
  table { max-width: 100% !important; }
  td, th {
    max-width: 100%;
    overflow-wrap: anywhere;
    word-break: break-word;
  }
  a { word-break: break-word; overflow-wrap: anywhere; }
  button {
    appearance: none;
    border: 0;
    font: inherit;
    cursor: pointer;
  }
  pre {
    max-width: 100% !important;
    overflow: auto !important;
    white-space: pre-wrap !important;
    overflow-wrap: anywhere !important;
  }
  .email-plain-text {
    margin: 0;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    word-break: break-word;
  }
  img[data-remote-src] { display: none !important; }
  details.mail-quote {
    margin-top: 16px;
    border-top: 1px solid #e5e7eb;
    padding-top: 12px;
  }
  details.mail-quote > summary {
    color: #4b5563;
    cursor: pointer;
    font-size: 12px;
  }
  .mail-quote-body { margin-top: 10px; }
`;

const INVISIBLE_EMAIL_MARKS = /\u034F|\u200B|\u200C|\u200D|\u2060|\u2800|\uFEFF/g;
const EMPTY_LAYOUT_TEXT = /[\s\u00A0\u1680\u2000-\u200A\u202F\u205F\u3000\u2800]/g;
const MIN_EMAIL_CONTENT_HEIGHT = 24;

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// Plain-text messages have no body_html at all. Turn bare URLs, mailto: and
// tel: text into real clickable links without touching the rest of the
// wording -- matched purely against the original text so escaping only ever
// happens once, on the final segments.
const AUTOLINK_PATTERN = /((?:https?:\/\/|www\.)[^\s<>"']+|mailto:[^\s<>"']+|tel:\+?[\d()\-\s]{5,}\d)/gi;

function autolinkPlainText(text: string): string {
  const segments = text.split(AUTOLINK_PATTERN);
  return segments
    .map((segment, index) => {
      if (index % 2 === 0) return escapeHtml(segment);
      let href = segment;
      let trailing = '';
      const isTel = /^tel:/i.test(href);
      if (!isTel) {
        const trailingMatch = href.match(/[),.;:!?]+$/);
        if (trailingMatch) {
          trailing = trailingMatch[0];
          href = href.slice(0, -trailing.length);
        }
      }
      const label = segment.slice(0, segment.length - trailing.length);
      if (/^www\./i.test(href)) href = `https://${href}`;
      return `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer nofollow">${escapeHtml(label)}</a>${escapeHtml(trailing)}`;
    })
    .join('');
}

function plainTextToHtml(text: string): string {
  return `<div class="email-plain-text">${autolinkPlainText(text)}</div>`;
}

function buildEmailDocument(html: string | null, text: string | null): string {
  let body: string;
  if (html && html.trim()) {
    body = html;
  } else if (text && text.trim()) {
    body = plainTextToHtml(text);
  } else {
    body = '<p style="color:#999;">Нет содержимого</p>';
  }

  return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<base target="_blank">
<style>${READER_CSS}</style>
</head>
<body>${body}</body>
</html>`;
}

function hasMeaningfulText(element: Element): boolean {
  return (element.textContent ?? '')
    .replace(INVISIBLE_EMAIL_MARKS, '')
    .replace(EMPTY_LAYOUT_TEXT, '')
    .length > 0;
}

function hasMeaningfulContent(element: Element): boolean {
  if (hasMeaningfulText(element)) return true;
  return Boolean(element.querySelector('img:not([data-remote-src]), video, audio, svg, canvas'));
}

function clampEmailMinimumWidths(doc: Document) {
  const body = doc.body;
  if (!body) return;
  const availableWidth = doc.documentElement.clientWidth || body.clientWidth;
  if (!availableWidth) return;

  body.querySelectorAll<HTMLElement>('[style*="min-width"]').forEach((element) => {
    const style = element.getAttribute('style') ?? '';
    const match = style.match(/(?:^|;)\s*min-width\s*:\s*([\d.]+)px/i);
    if (match && Number(match[1]) > availableWidth) {
      element.style.minWidth = '0';
    }
  });

  for (let pass = 0; pass < 3; pass += 1) {
    body.querySelectorAll<HTMLElement>('table, td, th').forEach((element) => {
      const rect = element.getBoundingClientRect();
      if (rect.width <= availableWidth + 1 && rect.left >= -1 && rect.right <= availableWidth + 1) return;

      const safeWidth = Math.max(1, availableWidth - Math.max(0, rect.left));
      element.style.width = `${safeWidth}px`;
      element.style.maxWidth = '100%';
      element.style.boxSizing = 'border-box';
      if (element.tagName === 'TABLE') element.style.tableLayout = 'fixed';
    });
  }

  body.querySelectorAll<HTMLElement>('*').forEach((element) => {
    const rect = element.getBoundingClientRect();
    if (rect.left < -1 || rect.right > availableWidth + 1) {
      if (getComputedStyle(element).whiteSpace === 'nowrap') element.style.whiteSpace = 'normal';
    }
  });
}

function isLightColor(color: string): boolean {
  const match = color.match(/rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i);
  if (!match) return false;
  const [red, green, blue] = match.slice(1).map(Number);
  return (red * 299 + green * 587 + blue * 114) / 1000 > 185;
}

function hasLightText(element: Element): boolean {
  return [element, ...element.querySelectorAll('*')].some((node) => {
    if (!(node.textContent ?? '').replace(EMPTY_LAYOUT_TEXT, '').trim()) return false;
    const style = getComputedStyle(node);
    return style.display !== 'none' && style.visibility !== 'hidden' && style.opacity !== '0' && isLightColor(style.color);
  });
}

function applyBlockedBackgroundFallbacks(doc: Document) {
  const body = doc.body;
  if (body && (body.hasAttribute('data-remote-body-background') || body.querySelector('[data-remote-body-background]'))) {
    const style = getComputedStyle(body);
    const hasBackground = style.backgroundColor !== 'rgba(0, 0, 0, 0)' && style.backgroundColor !== 'transparent';
    if (!hasBackground) {
      body.style.backgroundImage = 'none';
      body.style.backgroundColor = '#24558b';
      body.style.color = '#ffffff';
      body.setAttribute('data-blocked-background', 'true');
    }
  }

  doc.querySelectorAll<HTMLElement>('[data-remote-background]').forEach((element) => {
    if (element === doc.body || element === doc.documentElement || !hasMeaningfulContent(element)) return;
    const style = getComputedStyle(element);
    const hasBackground = style.backgroundColor !== 'rgba(0, 0, 0, 0)' && style.backgroundColor !== 'transparent';
    if (hasBackground) return;

    element.style.backgroundImage = 'none';
    element.style.backgroundColor = hasLightText(element) ? '#24558b' : '#eef3f8';
    element.setAttribute('data-blocked-background', 'true');
  });
}

function isDisposableEmptyLayout(element: Element): boolean {
  if (!element.matches('div, p, td, th, tr, tbody, thead, tfoot, table')) return false;
  const style = element.getAttribute('style') ?? '';
  return /(?:^|;)\s*(?:min-)?height\s*:\s*(?:1\d{2,}|[2-9]\d{2,})px/i.test(style)
    || /(?:^|;)\s*padding(?:-top|-bottom)?\s*:\s*(?:[4-9]\d|\d{3,})px/i.test(style);
}

function cleanEmailDocument(doc: Document) {
  const body = doc.body;
  if (!body) return;

  const walker = doc.createTreeWalker(body, 4);
  let node = walker.nextNode();
  while (node) {
    node.nodeValue = node.nodeValue?.replace(INVISIBLE_EMAIL_MARKS, '') ?? '';
    node = walker.nextNode();
  }

  const blockedImages = [...body.querySelectorAll<HTMLImageElement>('img[data-remote-src]')];
  const affectedAncestors = new Set<Element>();
  blockedImages.forEach((image) => {
    let parent = image.parentElement;
    while (parent && parent !== body) {
      affectedAncestors.add(parent);
      parent = parent.parentElement;
    }
    image.remove();
  });

  const candidates = new Set<Element>(affectedAncestors);
  body.querySelectorAll('div, p, td, th, tr, tbody, thead, tfoot, table').forEach((element) => candidates.add(element));
  const depth = (element: Element) => {
    let value = 0;
    let current = element.parentElement;
    while (current) {
      value += 1;
      current = current.parentElement;
    }
    return value;
  };
  [...candidates]
    .sort((left, right) => depth(right) - depth(left))
    .forEach((element) => {
      if (!element.isConnected || hasMeaningfulContent(element)) return;
      if (affectedAncestors.has(element) || isDisposableEmptyLayout(element)) {
        element.remove();
      }
    });
}

function htmlFallbackText(value: string | null): string {
  if (!value) return '';
  try {
    const doc = new DOMParser().parseFromString(value, 'text/html');
    doc.querySelectorAll('style, script, head, title').forEach((node) => node.remove());
    return (doc.body?.textContent ?? '').replace(/\u00a0/g, ' ').trim();
  } catch {
    return '';
  }
}

interface EmailRendererProps {
  html: string | null;
  text: string | null;
  className?: string;
  hasRemoteImages?: boolean;
}

export function EmailRenderer({ html, text, className, hasRemoteImages = false }: EmailRendererProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const observersRef = useRef<{ disconnect: () => void } | null>(null);
  const [height, setHeight] = useState(MIN_EMAIL_CONTENT_HEIGHT);
  const [error, setError] = useState(false);
  const documentMarkup = useMemo(() => buildEmailDocument(html, text), [html, text]);
  const hasBlockedRemoteImages = useMemo(() => {
    if (!hasRemoteImages || !html?.trim() || typeof DOMParser === 'undefined') return false;
    const parsed = new DOMParser().parseFromString(html, 'text/html');
    return Boolean(parsed.querySelector('img[data-remote-src]'));
  }, [hasRemoteImages, html]);
  const rootClassName = ['min-w-0', className].filter(Boolean).join(' ');

  useEffect(() => {
    observersRef.current?.disconnect();
    observersRef.current = null;
    setError(false);
    setHeight(MIN_EMAIL_CONTENT_HEIGHT);
    return () => {
      observersRef.current?.disconnect();
      observersRef.current = null;
    };
  }, [documentMarkup]);

  const handleLoad = () => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    try {
      const doc = iframe.contentDocument;
      const body = doc?.body;
      if (!doc || !body) throw new Error('Email document is unavailable');

      observersRef.current?.disconnect();
      clampEmailMinimumWidths(doc);
      applyBlockedBackgroundFallbacks(doc);
      cleanEmailDocument(doc);

      let frame = 0;
      const updateHeight = () => {
        window.cancelAnimationFrame(frame);
        frame = window.requestAnimationFrame(() => {
          const scrollHeight = Math.max(
            body.scrollHeight,
            doc.documentElement.scrollHeight,
            MIN_EMAIL_CONTENT_HEIGHT,
          );
          setHeight(scrollHeight + 4);
        });
      };

      const mutationObserver = new MutationObserver(updateHeight);
      mutationObserver.observe(body, { childList: true, subtree: true });

      const resizeObserver = 'ResizeObserver' in window ? new ResizeObserver(updateHeight) : null;
      resizeObserver?.observe(body);

      const imageListeners: Array<{ image: HTMLImageElement; type: 'load' | 'error' }> = [];
      doc.querySelectorAll<HTMLImageElement>('img').forEach((image) => {
        image.addEventListener('load', updateHeight);
        image.addEventListener('error', updateHeight);
        imageListeners.push({ image, type: 'load' }, { image, type: 'error' });
        if (image.complete) {
          if (typeof image.decode === 'function') {
            void image.decode().then(() => updateHeight(), () => updateHeight());
          } else {
            window.setTimeout(updateHeight, 0);
          }
        }
      });

      observersRef.current = {
        disconnect: () => {
          window.cancelAnimationFrame(frame);
          mutationObserver.disconnect();
          resizeObserver?.disconnect();
          imageListeners.forEach(({ image, type }) => image.removeEventListener(type, updateHeight));
        },
      };
      updateHeight();
    } catch {
      setError(true);
    }
  };

  if (error) {
    const fallback = text?.trim() ? text : htmlFallbackText(html);
    return (
      <div className={rootClassName}>
        <div className="whitespace-pre-wrap break-words text-[12.5px] leading-relaxed text-ink-soft">
          {fallback || 'Не удалось отобразить письмо'}
        </div>
      </div>
    );
  }

  return (
    <div className={rootClassName}>
      <iframe
        ref={iframeRef}
        sandbox={SANDBOX_FLAGS}
        srcDoc={documentMarkup}
        onLoad={handleLoad}
        title="Содержимое письма"
        referrerPolicy="no-referrer"
        style={{ width: '100%', maxWidth: '100%', height: `${height}px`, border: 'none', display: 'block' }}
        className="bg-transparent"
      />
      {hasBlockedRemoteImages && (
        <div
          className="mt-3 flex items-start gap-2.5 rounded-lg border border-border-strong bg-surface-hover px-3 py-2.5 text-[11.5px] text-ink-muted"
          data-testid="email-remote-images-notice"
          role="status"
        >
          <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-surface text-ink-muted ring-1 ring-border-strong">
            <ImageOff size={14} aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <p className="font-semibold text-ink-soft">Изображения отключены</p>
            <p className="mt-0.5 leading-5 text-ink-muted">Мы не загружаем картинки с внешних сайтов, чтобы защитить вашу конфиденциальность. Текст письма доступен</p>
          </div>
        </div>
      )}
    </div>
  );
}
