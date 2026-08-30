import { useEffect, useMemo, useRef, useState } from 'react';
import { ImageOff } from 'lucide-react';

const SANDBOX_FLAGS = [
  'allow-same-origin',
  'allow-popups',
  'allow-popups-to-escape-sandbox',
].join(' ');

// This stylesheet belongs to the reader, not to the email. It only constrains
// the outer document and content that cannot safely shrink itself. Email CSS
// remains the later, higher-fidelity source of typography, colors and spacing.
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
    font-size: 14px;
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
    font-size: 13px;
  }
  .mail-quote-body { margin-top: 10px; }
`;

const INVISIBLE_EMAIL_MARKS = /\u034F|\u200B|\u200C|\u200D|\u2060|\u2800|\uFEFF/g;
const EMPTY_LAYOUT_TEXT = /[\s\u00A0\u1680\u2000-\u200A\u202F\u205F\u3000\u2800]/g;

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function plainTextToHtml(text: string): string {
  return `<div class="email-plain-text">${escapeHtml(text)}</div>`;
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

  // Some mail builders express a mobile-incompatible width through nested
  // table cells instead of min-width. Clamp only boxes that are already wider
  // than the reader; fixed-size CTA tables that fit the viewport are untouched.
  for (let pass = 0; pass < 3; pass += 1) {
    body.querySelectorAll<HTMLElement>('table, td, th').forEach((element) => {
      const rect = element.getBoundingClientRect();
      if (rect.width <= availableWidth + 1 && rect.left >= -1 && rect.right <= availableWidth + 1) return;

      // A padded table cell can make a `width:100%` child wider than its
      // viewport even after the child itself is clamped. Size it to the
      // remaining inline space from its current position so its padding and
      // border stay inside the reader as well.
      const safeWidth = Math.max(1, availableWidth - Math.max(0, rect.left));
      element.style.width = `${safeWidth}px`;
      element.style.maxWidth = '100%';
      element.style.boxSizing = 'border-box';
      if (element.tagName === 'TABLE') element.style.tableLayout = 'fixed';
    });
  }

  // A sender may intentionally keep a price or CTA on one line. If that
  // choice becomes wider than the reader, allow just that overflowing text
  // to wrap instead of clipping the final characters off-screen.
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
      // Some templates use one remote image as the surface for the whole
      // message. Keep the white sender text readable when that asset is
      // blocked, while nested white cards retain their own backgrounds.
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

    // Keep remote assets blocked, but make text-bearing cards readable when the
    // sender used an external image as the only surface color.
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

  // Some marketing templates contain zero-width formatting marks. Removing
  // only those characters keeps the sender's visible spacing untouched.
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

  // An image commonly sits in an otherwise empty link/cell with a fixed
  // height. Remove only that empty ancestor chain. Also remove unmistakable
  // large, content-free marketing spacers; normal email spacing is retained.
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
  const [height, setHeight] = useState(120);
  const [error, setError] = useState(false);
  const documentMarkup = useMemo(() => buildEmailDocument(html, text), [html, text]);
  // The API flag describes the original message. The marker is the stronger
  // UI fact: it is present only after the sanitizer replaced a remote <img>
  // source with data-remote-src, so plain text, CID and image-free mail stay
  // free of a reader notice even if a stale flag is returned.
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
    setHeight(120);
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
            80,
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
        if (!image.complete) {
          image.addEventListener('load', updateHeight, { once: true });
          image.addEventListener('error', updateHeight, { once: true });
          imageListeners.push({ image, type: 'load' }, { image, type: 'error' });
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
        <div className="whitespace-pre-wrap break-words text-sm text-ink-600">
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
          className="mt-3 flex items-start gap-2.5 rounded-lg border border-ink-200 bg-ink-50 px-3 py-2.5 text-xs text-ink-600"
          data-testid="email-remote-images-notice"
          role="status"
        >
          <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-white text-ink-500 ring-1 ring-ink-200">
            <ImageOff size={14} aria-hidden="true" />
          </span>
          <div className="min-w-0">
            <p className="font-semibold text-ink-700">Изображения отключены</p>
            <p className="mt-0.5 leading-5 text-ink-500">Мы не загружаем картинки с внешних сайтов, чтобы защитить вашу конфиденциальность. Текст письма доступен</p>
          </div>
        </div>
      )}
    </div>
  );
}
