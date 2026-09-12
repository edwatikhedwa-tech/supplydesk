import { CheckCircle2, Clipboard, HelpCircle, MessageCircleQuestion } from 'lucide-react';
import { useMemo, useState } from 'react';
import { PageHeader } from '../components/shell/PageHeader';
import { Button } from '../components/ui/Button';

type HelpArticle = {
  title: string;
  keywords: string[];
  answer: string;
};

const articles: HelpArticle[] = [
  {
    title: 'Как создать и отследить задачу',
    keywords: ['задач', 'календар', 'срок', 'напомин'],
    answer: 'Создайте задачу из Дашборда, карточки поставщика или заявки. Датированные задачи видны в Календаре; задача без срока остаётся в рабочем списке. Напоминания in-app и Email сохраняются в задаче, но не отправляют внешние сообщения автоматически.',
  },
  {
    title: 'Как работать с поставщиком',
    keywords: ['поставщик', 'контакт', 'карточк', 'чёрн', 'избран'],
    answer: 'Откройте карточку поставщика из списка или заявки. В ней можно вести личные или командные контакты, заметки, задачи, избранное и чёрный список. Контакты и рабочие метки остаются внутри вашего рабочего пространства.',
  },
  {
    title: 'Как импортировать поставщиков',
    keywords: ['импорт', 'csv', 'excel', 'таблиц', 'загруз'],
    answer: 'В разделе «Поставщики» доступен безопасный preview CSV в UTF-8: он предлагает сопоставление колонок, показывает ошибки ИНН и возможные дубликаты. После отдельного подтверждения создаются только новые карточки с валидным ИНН; существующие не изменяются и не объединяются. Excel пока не поддерживается.',
  },
  {
    title: 'Чем ИИ-помощник отличается от помощи по продукту',
    keywords: ['ии', 'ai', 'переписк', 'письм', 'помощник'],
    answer: 'ИИ-помощник в «Сообщениях» работает с выбранной перепиской поставщиков и помогает по закупочному контексту. Этот экран не использует ИИ и не придумывает ответов: он объясняет только подтверждённые возможности SupplyDesk.',
  },
];

function normalize(value: string) {
  return value.trim().toLocaleLowerCase('ru-RU');
}

export function Help() {
  const [question, setQuestion] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState('');
  const normalizedQuestion = normalize(question);
  const matches = useMemo(
    () => normalizedQuestion
      ? articles.filter((article) => article.keywords.some((keyword) => normalizedQuestion.includes(keyword)))
      : [],
    [normalizedQuestion],
  );

  async function copyForSupport() {
    const message = `Вопрос по SupplyDesk:\n${question.trim()}`;
    try {
      await navigator.clipboard.writeText(message);
      setCopied(true);
      setCopyError('');
    } catch {
      setCopied(false);
      setCopyError('Не удалось скопировать вопрос. Выделите текст и передайте его вручную.');
    }
  }

  function findAnswer() {
    setSubmitted(true);
    setCopied(false);
    setCopyError('');
  }

  return (
    <div className="h-full overflow-auto">
      <PageHeader
        title="Справка"
        description="Короткие проверенные инструкции по функциям SupplyDesk."
      />
      <div className="mx-auto max-w-4xl space-y-5 px-4 pb-8 sm:px-6">
        <section className="rounded-lg border border-border bg-surface p-4 sm:p-5" aria-labelledby="help-question-title">
          <div className="flex items-start gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-accent-subtle text-accent"><MessageCircleQuestion size={17} /></div>
            <div>
              <h2 id="help-question-title" className="text-[14px] font-semibold text-ink">Что хотите сделать?</h2>
              <p className="mt-1 text-[12px] text-ink-muted">Опишите задачу своими словами — покажем только подходящие проверенные инструкции.</p>
            </div>
          </div>
          <div className="mt-4 flex flex-col gap-2 sm:flex-row">
            <input
              value={question}
              onChange={(event) => { setQuestion(event.target.value); setSubmitted(false); setCopied(false); setCopyError(''); }}
              onKeyDown={(event) => { if (event.key === 'Enter' && question.trim()) findAnswer(); }}
              placeholder="Например: как проверить CSV перед импортом?"
              aria-label="Вопрос для справки"
              className="h-9 min-w-0 flex-1 rounded-md border border-border-strong bg-canvas px-3 text-[13px] outline-none focus:border-accent focus:ring-1 focus:ring-accent-border"
            />
            <Button variant="primary" size="sm" disabled={!question.trim()} onClick={findAnswer}>Найти ответ</Button>
          </div>
          {submitted && matches.length > 0 && (
            <div className="mt-4 space-y-3" aria-live="polite">
              {matches.map((article) => (
                <article key={article.title} className="rounded-md border border-success-border bg-success-subtle px-3 py-2.5">
                  <p className="flex items-center gap-1.5 text-[12.5px] font-medium text-success"><CheckCircle2 size={14} />{article.title}</p>
                  <p className="mt-1 text-[12px] text-ink-soft">{article.answer}</p>
                </article>
              ))}
            </div>
          )}
          {submitted && matches.length === 0 && (
            <div className="mt-4 rounded-md border border-warning-border bg-warning-subtle px-3 py-3" aria-live="polite">
              <p className="text-[12.5px] font-medium text-warning">Пока не могу подтвердить ответ на этот вопрос.</p>
              <p className="mt-1 text-[12px] text-ink-soft">Скопируйте вопрос, откройте техническую поддержку внизу слева и вставьте его в обращение.</p>
              <div className="mt-2.5 flex flex-wrap items-center gap-2">
                <Button variant="secondary" size="sm" icon={<Clipboard size={13} />} onClick={() => void copyForSupport()}>Скопировать вопрос</Button>
                {copied && <span className="text-[11.5px] text-success">Скопировано — можно вставить в обращение.</span>}
                {copyError && <span className="text-[11.5px] text-danger">{copyError}</span>}
              </div>
            </div>
          )}
        </section>

        <section aria-labelledby="help-articles-title">
          <div className="mb-2 flex items-center gap-2"><HelpCircle size={16} className="text-ink-muted" /><h2 id="help-articles-title" className="text-[13px] font-semibold text-ink">Частые вопросы</h2></div>
          <div className="grid gap-3 sm:grid-cols-2">
            {articles.map((article) => (
              <article key={article.title} className="rounded-lg border border-border bg-surface p-4">
                <h3 className="text-[13px] font-medium text-ink">{article.title}</h3>
                <p className="mt-1.5 text-[12px] leading-5 text-ink-muted">{article.answer}</p>
              </article>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
