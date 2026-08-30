import { useState, useRef, useEffect } from 'react';
import { Copy, Check } from 'lucide-react';

/** Копирование значения одним кликом — для адресов и ИНН, которые снабженец
 *  переносит в почту, договор или 1С. Появляется при наведении на строку,
 *  чтобы не соперничать за внимание с самими данными, но остаётся видимой
 *  сразу после нажатия — иначе непонятно, сработало ли.
 *
 *  stopPropagation обязателен: кнопка живёт внутри кликабельной строки
 *  таблицы, которая иначе откроет боковую карточку поверх результата. */
export function CopyButton({ value, label = 'Скопировать' }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | null>(null);

  useEffect(() => () => { if (timer.current) window.clearTimeout(timer.current); }, []);

  const copy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    e.preventDefault();
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      // Clipboard API недоступен вне защищённого контекста (http на не-localhost) —
      // запасной путь через скрытое поле, иначе кнопка молча ничего не делает.
      const field = document.createElement('textarea');
      field.value = value;
      field.style.position = 'fixed';
      field.style.opacity = '0';
      document.body.appendChild(field);
      field.select();
      try { document.execCommand('copy'); } finally { document.body.removeChild(field); }
    }
    setCopied(true);
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setCopied(false), 1600);
  };

  return (
    <button
      onClick={copy}
      title={copied ? 'Скопировано' : label}
      aria-label={copied ? 'Скопировано' : label}
      className={[
        'inline-flex h-5 w-5 shrink-0 items-center justify-center rounded transition-all',
        copied
          ? 'text-emerald-600 opacity-100'
          : 'text-ink-400 opacity-0 hover:bg-ink-100 hover:text-ink-700 focus:opacity-100 group-hover/row:opacity-100',
      ].join(' ')}
    >
      {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
    </button>
  );
}
