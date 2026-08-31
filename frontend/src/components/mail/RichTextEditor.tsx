import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react';
import { Bold, Italic, Link as LinkIcon, List, ListOrdered, type LucideIcon } from 'lucide-react';
import { readRichTextEditor, type RichTextValue } from './richTextUtils';

interface RichTextEditorProps {
  initialHtml?: string;
  placeholder?: string;
  ariaLabel: string;
  id?: string;
  disabled?: boolean;
  onChange?: (value: RichTextValue) => void;
}

export const RichTextEditor = forwardRef<HTMLDivElement, RichTextEditorProps>(function RichTextEditor(
  { initialHtml = '', placeholder = 'Напишите письмо…', ariaLabel, id, disabled = false, onChange }: RichTextEditorProps,
  forwardedRef,
) {
  const localRef = useRef<HTMLDivElement>(null);

  useImperativeHandle(forwardedRef, () => localRef.current as HTMLDivElement, []);

  useEffect(() => {
    if (localRef.current) localRef.current.innerHTML = initialHtml;
  }, [initialHtml]);

  const exec = (command: string, value?: string) => {
    document.execCommand(command, false, value);
    localRef.current?.focus();
  };

  return (
    <div className="border border-ink-200 rounded-lg overflow-hidden">
      <div className="flex items-center gap-1 px-2 py-1.5 border-b border-ink-100 bg-ink-50">
        <ToolbarButton disabled={disabled} label="Жирный" onClick={() => exec('bold')} icon={Bold} />
        <ToolbarButton disabled={disabled} label="Курсив" onClick={() => exec('italic')} icon={Italic} />
        <ToolbarButton disabled={disabled} label="Маркированный список" onClick={() => exec('insertUnorderedList')} icon={List} />
        <ToolbarButton disabled={disabled} label="Нумерованный список" onClick={() => exec('insertOrderedList')} icon={ListOrdered} />
        <ToolbarButton
          disabled={disabled}
          label="Вставить ссылку"
          onClick={() => {
            const url = window.prompt('URL:');
            if (url) exec('createLink', url);
          }}
          icon={LinkIcon}
        />
      </div>
      <div
        ref={localRef}
        contentEditable={!disabled}
        suppressContentEditableWarning
        id={id}
        aria-label={ariaLabel}
        aria-disabled={disabled}
        data-placeholder={placeholder}
        onInput={() => { if (!disabled) onChange?.(readRichTextEditor(localRef.current)); }}
        className="min-h-[140px] max-h-[280px] overflow-y-auto px-3 py-2.5 text-sm text-ink-800 outline-none focus:outline-none disabled:bg-ink-50 [&:empty]:before:content-[attr(data-placeholder)] [&:empty]:before:text-ink-300"
      />
    </div>
  );
});

function ToolbarButton({ disabled, label, onClick, icon: Icon }: { disabled?: boolean; label: string; onClick: () => void; icon: LucideIcon }) {
  return (
    <button
      type="button"
      disabled={disabled}
      aria-label={label}
      onMouseDown={(event) => event.preventDefault()}
      onClick={onClick}
      className="p-1.5 text-ink-500 hover:text-ink-900 hover:bg-ink-200 rounded transition-colors"
    >
      <Icon size={15} aria-hidden="true" />
    </button>
  );
}
