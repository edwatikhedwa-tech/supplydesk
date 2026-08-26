import { useEffect, useRef, useState } from 'react';

const SANDBOX_FLAGS = [
  'allow-same-origin',
  'allow-popups',
  'allow-popups-to-escape-sandbox',
].join(' ');

const NORMALIZE_CSS = `
  html, body {
    margin: 0 !important;
    padding: 0 !important;
    background: transparent !important;
    width: 100% !important;
    max-width: 100% !important;
    overflow-x: hidden !important;
  }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif !important;
    font-size: 14px !important;
    line-height: 1.6 !important;
    color: #1a1a1a !important;
    word-wrap: break-word !important;
    overflow-wrap: break-word !important;
    -webkit-font-smoothing: antialiased;
  }
  * {
    max-width: 100% !important;
    box-sizing: border-box !important;
  }
  img {
    max-width: 100% !important;
    height: auto !important;
    display: inline-block !important;
  }
  table {
    max-width: 100% !important;
    border-collapse: collapse !important;
    table-layout: auto !important;
  }
  table table {
    max-width: none !important;
  }
  td, th {
    padding: 6px 8px !important;
    word-wrap: break-word !important;
  }
  a {
    color: #0066cc !important;
    text-decoration: underline !important;
  }
  p {
    margin: 0 0 12px 0 !important;
    padding: 0 !important;
  }
  h1, h2, h3, h4, h5, h6 {
    margin: 16px 0 8px 0 !important;
    padding: 0 !important;
    line-height: 1.3 !important;
  }
  h1 { font-size: 20px !important; }
  h2 { font-size: 17px !important; }
  h3 { font-size: 15px !important; }
  h4, h5, h6 { font-size: 14px !important; }
  ul, ol {
    margin: 0 0 12px 0 !important;
    padding-left: 24px !important;
  }
  li {
    margin: 2px 0 !important;
  }
  blockquote {
    margin: 8px 0 !important;
    padding: 8px 16px !important;
    border-left: 3px solid #d1d5db !important;
    color: #555 !important;
    font-style: italic !important;
    background: #f9fafb !important;
    border-radius: 0 4px 4px 0 !important;
  }
  hr {
    border: none !important;
    border-top: 1px solid #e5e7eb !important;
    margin: 16px 0 !important;
  }
  pre {
    background: #f3f4f6 !important;
    padding: 12px !important;
    border-radius: 6px !important;
    overflow-x: auto !important;
    font-size: 13px !important;
    margin: 8px 0 !important;
  }
  code {
    font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace !important;
    font-size: 13px !important;
  }
  /* Strip email-level background colors that create huge gaps */
  body > table, body > div {
    background: transparent !important;
  }
  /* Remove fixed pixel widths from email containers */
  [style*="width:"], [width] {
    max-width: 100% !important;
  }
  /* Normalize font sizes that are too large */
  [style*="font-size: 28px"], [style*="font-size:28px"] { font-size: 20px !important; }
  [style*="font-size: 24px"], [style*="font-size:24px"] { font-size: 18px !important; }
  [style*="font-size: 20px"], [style*="font-size:20px"] { font-size: 16px !important; }
  /* Prevent margin/padding from creating huge gaps */
  [style*="margin: 40px"], [style*="margin:40px"] { margin: 16px !important; }
  [style*="padding: 40px"], [style*="padding:40px"] { padding: 16px !important; }
  [style*="padding: 30px"], [style*="padding:30px"] { padding: 12px !important; }
`;

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function plainTextToHtml(text: string): string {
  const escaped = escapeHtml(text);
  return escaped
    .split(/\n/)
    .map((line) => line.trim() === '' ? '<br>' : `<p>${line}</p>`)
    .join('');
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
<style>${NORMALIZE_CSS}</style>
</head>
<body>${body}</body>
</html>`;
}

interface EmailRendererProps {
  html: string | null;
  text: string | null;
  className?: string;
}

export function EmailRenderer({ html, text, className }: EmailRendererProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [height, setHeight] = useState<number>(120);
  const [error, setError] = useState(false);

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    try {
      const doc = buildEmailDocument(html, text);
      iframe.srcdoc = doc;
    } catch {
      setError(true);
    }
  }, [html, text]);

  const handleLoad = () => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    try {
      const doc = iframe.contentDocument;
      if (!doc) return;

      const body = doc.body;
      if (!body) return;

      const updateHeight = () => {
        const scrollHeight = Math.max(
          body.scrollHeight,
          doc.documentElement.scrollHeight,
          80,
        );
        setHeight(scrollHeight + 4);
      };

      updateHeight();

      const observer = new MutationObserver(updateHeight);
      observer.observe(body, { childList: true, subtree: true, attributes: true });

      const images = doc.querySelectorAll('img');
      images.forEach((img) => {
        if (!img.complete) {
          img.addEventListener('load', updateHeight, { once: true });
          img.addEventListener('error', updateHeight, { once: true });
        }
      });

      return () => observer.disconnect();
    } catch {
      setError(true);
    }
  };

  if (error) {
    const fallback = text || html || 'Не удалось отобразить письмо';
    return (
      <div className={className}>
        <div className="text-sm text-ink-600 whitespace-pre-wrap break-words">
          {fallback}
        </div>
      </div>
    );
  }

  return (
    <div className={className}>
      <iframe
        ref={iframeRef}
        sandbox={SANDBOX_FLAGS}
        onLoad={handleLoad}
        title="Содержимое письма"
        style={{ width: '100%', height: `${height}px`, border: 'none', display: 'block' }}
        className="bg-transparent"
      />
    </div>
  );
}
