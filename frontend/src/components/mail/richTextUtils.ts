export interface RichTextValue {
  bodyHtml: string;
  bodyText: string;
}

export function readRichTextEditor(element: HTMLDivElement | null): RichTextValue {
  if (!element) return { bodyHtml: '', bodyText: '' };
  return {
    bodyHtml: element.innerHTML || '',
    bodyText: (element.innerText || element.textContent || '').replace(/\u00a0/g, ' '),
  };
}

export function plainTextToHtml(value: string): string {
  const escaped = value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
  return `<p>${escaped.replace(/\r?\n/g, '<br>')}</p>`;
}
