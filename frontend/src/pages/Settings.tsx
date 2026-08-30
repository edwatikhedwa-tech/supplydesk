import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { AlertCircle, CheckCircle2, FileText, Loader2, Mail, Paperclip, RefreshCw, Save, Unplug, X } from 'lucide-react';
import { ApiError, api } from '@/lib/api';
import type { MailAccount, MailTemplateAttachment } from '@/lib/types';

const MAIL_ERROR_LABELS: Record<string, string> = {
  not_configured: 'Подключение к Яндекс.Почте сейчас недоступно на сервере.',
  access_denied: 'Вы отменили подключение почты в Яндексе.',
  missing_code: 'Яндекс не передал код авторизации, попробуйте ещё раз.',
  connection_failed: 'Не удалось подключить почту, попробуйте ещё раз.',
};

interface MailStatus {
  connected: boolean;
  provider?: string;
  email?: string;
  status?: string;
  last_error?: string | null;
  updated_at?: string | null;
  accounts?: MailAccount[];
}

const MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024;
const MAX_TOTAL_ATTACHMENT_BYTES = 20 * 1024 * 1024;
const ALLOWED_MIME_PREFIXES = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument', 'text/plain', 'image/'];
const DEFAULT_TEMPLATE_SUBJECT = 'Запрос коммерческого предложения';
const DEFAULT_TEMPLATE_BODY = 'Добрый день!\n\nПросим предоставить коммерческое предложение.';

function formatSize(bytes: number): string {
  return bytes < 1024 * 1024 ? `${Math.ceil(bytes / 1024)} КБ` : `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}

function fileMime(file: File): string {
  if (file.type) return file.type;
  const extension = file.name.split('.').pop()?.toLowerCase();
  if (extension === 'pdf') return 'application/pdf';
  if (extension === 'doc') return 'application/msword';
  if (extension === 'docx') return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
  if (extension === 'txt') return 'text/plain';
  return 'application/octet-stream';
}

function isAllowedMime(mime: string): boolean {
  return ALLOWED_MIME_PREFIXES.some((prefix) => mime === prefix || mime.startsWith(prefix));
}

function readFileAsBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(',')[1] ?? '');
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

function formatMailCheckTime(value?: string | null): string {
  if (!value) return 'Ещё не проверялись';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
}

export function Settings() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [status, setStatus] = useState<MailStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [mailruEmail, setMailruEmail] = useState('');
  const [mailruPassword, setMailruPassword] = useState('');
  const [mailruConnecting, setMailruConnecting] = useState(false);
  const [actionMessage, setActionMessage] = useState('');
  const [actionError, setActionError] = useState('');
  const [templateSubject, setTemplateSubject] = useState(DEFAULT_TEMPLATE_SUBJECT);
  const [templateBody, setTemplateBody] = useState(DEFAULT_TEMPLATE_BODY);
  const [templateAttachments, setTemplateAttachments] = useState<MailTemplateAttachment[]>([]);
  const [templateUpdatedAt, setTemplateUpdatedAt] = useState<string | null>(null);
  const [templateLoading, setTemplateLoading] = useState(true);
  const [templateSaving, setTemplateSaving] = useState(false);
  const [templateMessage, setTemplateMessage] = useState('');
  const [templateError, setTemplateError] = useState('');

  const mailErrorCode = searchParams.get('mail_error');
  const justConnected = searchParams.get('connected') === 'true';
  const accounts = status?.accounts ?? [];

  const load = () => {
    setLoading(true);
    return api.mailStatus().then(setStatus).finally(() => setLoading(false));
  };

  const loadTemplate = () => {
    setTemplateLoading(true);
    setTemplateError('');
    return api.mailTemplate()
      .then((template) => {
        setTemplateSubject(template.subject);
        setTemplateBody(template.body);
        setTemplateAttachments(template.attachments);
        setTemplateUpdatedAt(template.updated_at);
      })
      .catch((error) => {
        setTemplateSubject(DEFAULT_TEMPLATE_SUBJECT);
        setTemplateBody(DEFAULT_TEMPLATE_BODY);
        setTemplateAttachments([]);
        setTemplateUpdatedAt(null);
        setTemplateError(error instanceof ApiError ? error.message : 'Не удалось загрузить шаблон письма.');
      })
      .finally(() => setTemplateLoading(false));
  };

  useEffect(() => {
    void load();
    void loadTemplate();
    if (mailErrorCode || justConnected) {
      // Query params are one-shot feedback from the OAuth redirect — clear them
      // so a page refresh doesn't keep re-showing the same banner.
      searchParams.delete('mail_error');
      searchParams.delete('connected');
      setSearchParams(searchParams, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleTest = async (mailAccountId?: number) => {
    setTesting(true);
    setActionMessage('');
    setActionError('');
    try {
      const res = await api.mailTest(mailAccountId);
      setActionMessage(res.message);
      await load();
    } catch {
      setActionError('Не удалось проверить соединение.');
    } finally {
      setTesting(false);
    }
  };

  const handleSync = async (mailAccountId?: number) => {
    setSyncing(true);
    setActionMessage('');
    setActionError('');
    try {
      const res = await api.mailSync(mailAccountId);
      setActionMessage(`Синхронизация выполнена: получено ${res.imported ?? 0}.`);
      await load();
    } catch {
      setActionError('Не удалось синхронизировать почту.');
    } finally {
      setSyncing(false);
    }
  };

  const handleDisconnect = async (mailAccountId?: number) => {
    setDisconnecting(true);
    setActionMessage('');
    setActionError('');
    try {
      if (mailAccountId == null) {
        await api.mailDisconnect();
      } else {
        await api.mailDisconnectAccount(mailAccountId);
      }
      await load();
      setActionMessage('Аккаунт отключён. Сохранённые письма и история не удалены. Для полной безопасности также удалите пароль SupplyDesk в настройках Mail.ru → Безопасность → Пароли для внешних приложений.');
    } catch {
      setActionError('Не удалось отключить почту.');
    } finally {
      setDisconnecting(false);
    }
  };

  const handleConnect = () => {
    window.location.href = '/api/mail/yandex/start';
  };

  const handleMailruConnect = async () => {
    setActionMessage('');
    setActionError('');
    if (!mailruEmail.trim() || !mailruPassword) {
      setActionError('Укажите email Mail.ru и пароль приложения.');
      return;
    }
    setMailruConnecting(true);
    try {
      await api.mailConnectMailru(mailruEmail.trim(), mailruPassword);
      setMailruPassword('');
      setActionMessage('Mail.ru подключён. Пароль приложения больше не хранится в форме.');
      await load();
    } catch (error) {
      setActionError(error instanceof ApiError ? error.message : 'Не удалось подключить Mail.ru. Проверьте email и пароль приложения.');
    } finally {
      setMailruConnecting(false);
    }
  };

  const handleTemplateFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    setTemplateError('');
    let total = templateAttachments.reduce((sum, attachment) => sum + attachment.size, 0);
    const next = [...templateAttachments];
    for (const file of Array.from(files)) {
      const mime = fileMime(file);
      if (!isAllowedMime(mime)) {
        setTemplateError(`«${file.name}»: разрешены PDF, DOC/DOCX, TXT и изображения.`);
        continue;
      }
      if (file.size > MAX_ATTACHMENT_BYTES) {
        setTemplateError(`«${file.name}»: файл больше 10 МБ.`);
        continue;
      }
      if (next.some((attachment) => attachment.filename.toLowerCase() === file.name.toLowerCase())) {
        setTemplateError(`«${file.name}» уже прикреплён к шаблону.`);
        continue;
      }
      if (total + file.size > MAX_TOTAL_ATTACHMENT_BYTES) {
        setTemplateError('Суммарный размер вложений не должен превышать 20 МБ.');
        break;
      }
      try {
        const contentBase64 = await readFileAsBase64(file);
        total += file.size;
        next.push({
          filename: file.name,
          mime_type: mime,
          size: file.size,
          content_base64: contentBase64,
        });
      } catch {
        setTemplateError(`«${file.name}»: не удалось прочитать файл.`);
      }
    }
    setTemplateAttachments(next);
  };

  const handleSaveTemplate = async () => {
    setTemplateMessage('');
    setTemplateError('');
    if (!templateSubject.trim()) {
      setTemplateError('Укажите тему письма.');
      return;
    }
    if (!templateBody.trim()) {
      setTemplateError('Введите текст письма.');
      return;
    }
    setTemplateSaving(true);
    try {
      const saved = await api.saveMailTemplate({
        subject: templateSubject.trim(),
        body: templateBody,
        attachments: templateAttachments,
      });
      setTemplateSubject(saved.subject);
      setTemplateBody(saved.body);
      setTemplateAttachments(saved.attachments);
      setTemplateUpdatedAt(saved.updated_at);
      setTemplateMessage('Шаблон сохранён и будет подставляться при подготовке запросов.');
    } catch (error) {
      setTemplateError(error instanceof ApiError ? error.message : 'Не удалось сохранить шаблон письма.');
    } finally {
      setTemplateSaving(false);
    }
  };

  return (
    <div className="min-h-screen px-6 py-7 lg:px-10 lg:py-10 animate-fade-in">
      <div className="mx-auto max-w-[760px] space-y-6">
        <div>
          <h1 className="text-page-title font-bold">Настройки</h1>
          <p className="mt-1 text-sm text-ink-500">Подключение почты и параметры рабочего пространства.</p>
        </div>

        {justConnected && (
          <div className="flex items-center gap-2.5 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
            <CheckCircle2 className="h-4 w-4 shrink-0" />Почта успешно подключена.
          </div>
        )}
        {mailErrorCode && (
          <div className="flex items-center gap-2.5 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            <AlertCircle className="h-4 w-4 shrink-0" />{MAIL_ERROR_LABELS[mailErrorCode] ?? 'Не удалось подключить почту.'}
          </div>
        )}

        <section className="space-y-4 rounded-2xl border border-ink-200/80 bg-white p-6 shadow-soft">
          <div className="flex items-center gap-2">
            <Mail className="h-4 w-4 text-ink-400" />
            <h2 className="text-base font-bold text-ink-900">Почта</h2>
          </div>

          {loading ? (
            <div className="py-6 text-center text-sm text-ink-400">Загрузка…</div>
          ) : (
            <div className="space-y-4">
              {accounts.length === 0 && <p className="text-sm text-ink-500">Почта не подключена — отправка запросов поставщикам и приём ответов недоступны.</p>}
              {accounts.map((account) => {
                const label = account.provider === 'mailru' ? 'Mail.ru' : 'Яндекс.Почта';
                const incomingHealth = account.incoming_health ?? (account.last_error ? 'error' : account.incoming_enabled ? 'pending' : 'disabled');
                const incomingError = account.incoming_last_error || (incomingHealth === 'error' ? account.last_error : null);
                const incomingLabel = incomingHealth === 'healthy' ? 'Работают' : incomingHealth === 'error' ? 'Ошибка синхронизации' : incomingHealth === 'disabled' ? 'Отключены' : 'Проверка нужна';
                const outgoingLabel = account.outgoing_health === 'error' ? 'Ошибка подключения' : account.outgoing_enabled ? 'Готовы' : 'Отключены';
                return <div key={account.id} className="rounded-xl border border-ink-200 bg-ink-50/50 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0"><div className="truncate text-sm font-semibold text-ink-800">{account.email}</div><div className="mt-0.5 text-xs text-ink-500">{label} · {account.auth_mode === 'app_password' ? 'пароль приложения' : 'OAuth'}</div></div>
                    <span className={`inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${account.connected ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-800'}`}><CheckCircle2 className="h-3.5 w-3.5" />{account.connected ? 'Подключён' : 'Нужна проверка'}</span>
                  </div>
                  <div className="mt-3 grid gap-2 text-xs sm:grid-cols-3">
                    <div className="rounded-lg border border-ink-200 bg-white px-3 py-2"><span className="block text-ink-500">Аккаунт</span><span className={`mt-0.5 block font-semibold ${account.connected ? 'text-emerald-700' : 'text-ink-600'}`}>{account.connected ? 'Подключён' : 'Нужна проверка'}</span></div>
                    <div className="rounded-lg border border-ink-200 bg-white px-3 py-2"><span className="block text-ink-500">Исходящие</span><span className={`mt-0.5 block font-semibold ${account.outgoing_enabled ? 'text-emerald-700' : 'text-ink-600'}`}>{outgoingLabel}</span></div>
                    <div className="rounded-lg border border-ink-200 bg-white px-3 py-2"><span className="block text-ink-500">Входящие ответы</span><span className={`mt-0.5 block font-semibold ${incomingHealth === 'healthy' ? 'text-emerald-700' : incomingHealth === 'error' ? 'text-rose-700' : 'text-ink-600'}`}>{incomingLabel}</span></div>
                  </div>
                  <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-ink-500"><span>Последняя проверка: {formatMailCheckTime(account.incoming_last_success_at)}</span>{incomingError && <span className="font-semibold text-rose-700">Ошибка входящих: {incomingError}</span>}</div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button onClick={() => void handleTest(account.id)} disabled={testing} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-ink-200 bg-white px-3.5 py-2 text-xs font-semibold text-ink-700 transition hover:border-ink-300 disabled:opacity-50">{testing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}Проверить</button>
                    <button onClick={() => void handleSync(account.id)} disabled={syncing} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-ink-200 bg-white px-3.5 py-2 text-xs font-semibold text-ink-700 transition hover:border-ink-300 disabled:opacity-50">{syncing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}{incomingHealth === 'error' ? 'Повторить входящие' : 'Синхронизировать входящие'}</button>
                    <button onClick={() => void handleDisconnect(account.id)} disabled={disconnecting} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-ink-200 bg-white px-3.5 py-2 text-xs font-semibold text-rose-600 transition hover:border-rose-200 hover:bg-rose-50 disabled:opacity-50">{disconnecting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Unplug className="h-3.5 w-3.5" />}Отключить</button>
                  </div>
                </div>;
              })}
              <div className="rounded-xl border border-accent-200 bg-accent-50/50 p-4">
                <div className="flex items-start justify-between gap-3"><div><h3 className="text-sm font-bold text-ink-900">Добавить Mail.ru</h3><p className="mt-1 text-xs leading-5 text-ink-600">Нужен отдельный пароль приложения с правом «Полный доступ к Почте».</p></div><Mail className="h-5 w-5 shrink-0 text-accent-600" /></div>
                <div className="mt-3 grid gap-2 sm:grid-cols-2">
                  <label className="text-xs font-semibold text-ink-700">Email<input value={mailruEmail} onChange={(event) => setMailruEmail(event.target.value)} type="email" autoComplete="off" placeholder="name@mail.ru" className="mt-1 h-10 w-full rounded-lg border border-ink-200 bg-white px-3 text-sm font-normal focus:border-accent-400 focus:outline-none focus:ring-2 focus:ring-accent-100" /></label>
                  <label className="text-xs font-semibold text-ink-700">Пароль приложения<input value={mailruPassword} onChange={(event) => setMailruPassword(event.target.value)} type="password" autoComplete="new-password" placeholder="Не обычный пароль" className="mt-1 h-10 w-full rounded-lg border border-ink-200 bg-white px-3 text-sm font-normal focus:border-accent-400 focus:outline-none focus:ring-2 focus:ring-accent-100" /></label>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-3"><button onClick={() => void handleMailruConnect()} disabled={mailruConnecting} className="inline-flex min-h-10 items-center gap-2 rounded-lg bg-accent-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-accent-700 disabled:opacity-50">{mailruConnecting && <Loader2 className="h-4 w-4 animate-spin" />}Подключить Mail.ru</button><a href="https://help.mail.ru/mail/login/mailer/" target="_blank" rel="noreferrer" className="text-xs font-semibold text-accent-700 hover:text-accent-800">Открыть официальную инструкцию</a></div>
                <details className="mt-3 rounded-lg border border-accent-200/80 bg-white/70 px-3 py-2 text-xs text-ink-700">
                  <summary className="cursor-pointer font-semibold text-accent-800">Как получить пароль приложения?</summary>
                  <ol className="mt-2 list-decimal space-y-1 pl-5 leading-5">
                    <li>Откройте Mail.ru и перейдите в настройки.</li>
                    <li>Откройте «Все настройки» → «Безопасность».</li>
                    <li>Выберите «Пароли для внешних приложений».</li>
                    <li>Создайте пароль для SupplyDesk и выберите «Полный доступ к Почте».</li>
                    <li>Вставьте созданный пароль в форму выше.</li>
                  </ol>
                </details>
              </div>
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs leading-5 text-amber-900">Обычный пароль Mail.ru не подходит. SupplyDesk проверяет SMTP и IMAP по защищённым каналам; письмо не отправляется во время подключения.</div>
              {actionMessage && <p className="text-xs font-medium text-emerald-700">{actionMessage}</p>}
              {actionError && <p role="alert" className="text-xs font-medium text-rose-600">{actionError}</p>}
              {!accounts.some((account) => account.provider === 'yandex' && account.connected) && <button onClick={handleConnect} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-ink-200 bg-white px-4 py-2.5 text-sm font-semibold text-ink-700 transition hover:border-accent-300 hover:text-accent-700"><Mail className="h-4 w-4" />Подключить Яндекс.Почту</button>}
            </div>
          )}
        </section>

        <section className="space-y-5 rounded-2xl border border-ink-200/80 bg-white p-5 shadow-soft sm:p-6" aria-labelledby="mail-template-title">
          <div className="flex items-start gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-accent-50 text-accent-600">
              <FileText className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <h2 id="mail-template-title" className="text-base font-bold text-ink-900">Шаблон запроса поставщику</h2>
              <p className="mt-1 text-xs leading-5 text-ink-500">Тема, текст и вложения автоматически появятся при подготовке нового письма. Перед отправкой их можно изменить.</p>
            </div>
          </div>

          {templateLoading ? (
            <div role="status" className="flex items-center gap-2 py-6 text-sm text-ink-500">
              <Loader2 className="h-4 w-4 animate-spin" />Загружаем шаблон…
            </div>
          ) : (
            <>
              <div>
                <label htmlFor="mail-template-subject" className="mb-1.5 block text-xs font-bold text-ink-700">Тема письма</label>
                <input
                  id="mail-template-subject"
                  value={templateSubject}
                  onChange={(event) => { setTemplateSubject(event.target.value); setTemplateMessage(''); }}
                  maxLength={240}
                  placeholder="Например: Запрос предложения — {{request_name}}"
                  className="h-11 w-full rounded-xl border border-ink-200 bg-ink-50/60 px-3.5 text-sm text-ink-800 placeholder:text-ink-400 transition focus:border-accent-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-accent-100"
                />
              </div>

              <div>
                <div className="mb-1.5 flex items-center justify-between gap-3">
                  <label htmlFor="mail-template-body" className="text-xs font-bold text-ink-700">Текст письма</label>
                  <span className="text-2xs tabular-nums text-ink-600">{templateBody.length} / 20 000</span>
                </div>
                <textarea
                  id="mail-template-body"
                  value={templateBody}
                  onChange={(event) => { setTemplateBody(event.target.value); setTemplateMessage(''); }}
                  maxLength={20_000}
                  rows={12}
                  className="w-full resize-y rounded-xl border border-ink-200 bg-ink-50/60 px-3.5 py-3 text-sm leading-6 text-ink-800 transition focus:border-accent-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-accent-100"
                />
              </div>

              <div className="rounded-xl border border-ink-100 bg-ink-50/60 px-3.5 py-3">
                <p className="text-xs font-bold text-ink-700">Переменные персонализации</p>
                <div className="mt-2 flex flex-wrap gap-1.5" aria-label="Доступные переменные шаблона">
                  {['supplier_name', 'request_name', 'request_description', 'sender_name', 'company_name'].map((variable) => (
                    <code key={variable} className="rounded-md border border-ink-200 bg-white px-2 py-1 text-[11px] text-ink-600">{`{{${variable}}}`}</code>
                  ))}
                </div>
              </div>

              <div>
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-xs font-bold text-ink-700">Вложения шаблона</p>
                    <p className="mt-1 text-xs text-ink-500">PDF, DOC/DOCX, TXT или изображения; до 10 МБ на файл и 20 МБ суммарно.</p>
                  </div>
                  <label className="inline-flex min-h-10 cursor-pointer items-center justify-center gap-2 rounded-lg border border-ink-200 bg-white px-3.5 py-2 text-xs font-semibold text-ink-700 transition hover:border-accent-300 hover:text-accent-700 focus-within:ring-2 focus-within:ring-accent-500 focus-within:ring-offset-2">
                    <Paperclip className="h-3.5 w-3.5" />Прикрепить файл
                    <input
                      type="file"
                      multiple
                      accept=".pdf,.doc,.docx,.txt,image/*"
                      aria-label="Прикрепить файл к шаблону"
                      className="sr-only"
                      onChange={(event) => { void handleTemplateFiles(event.target.files); event.target.value = ''; }}
                    />
                  </label>
                </div>

                {templateAttachments.length > 0 ? (
                  <ul className="mt-3 space-y-2">
                    {templateAttachments.map((attachment) => (
                      <li key={attachment.filename} className="flex min-w-0 items-center gap-2 rounded-lg border border-ink-200 bg-ink-50/50 px-3 py-2 text-xs">
                        <Paperclip className="h-3.5 w-3.5 shrink-0 text-ink-400" />
                        <span className="min-w-0 flex-1 truncate font-medium text-ink-700" title={attachment.filename}>{attachment.filename}</span>
                        <span className="shrink-0 tabular-nums text-ink-500">{formatSize(attachment.size)}</span>
                        <button
                          type="button"
                          onClick={() => { setTemplateAttachments((current) => current.filter((item) => item.filename !== attachment.filename)); setTemplateMessage(''); }}
                          aria-label={`Удалить вложение ${attachment.filename}`}
                          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-ink-400 transition hover:bg-rose-50 hover:text-rose-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-3 text-xs text-ink-500">Постоянных вложений пока нет.</p>
                )}
              </div>

              <div aria-live="polite">
                {templateMessage && <p className="text-xs font-medium text-emerald-700">{templateMessage}</p>}
                {templateError && <p role="alert" className="text-xs font-medium text-rose-600">{templateError}</p>}
              </div>

              <div className="flex flex-col-reverse gap-3 border-t border-ink-100 pt-4 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-xs text-ink-600">
                  {templateUpdatedAt ? `Последнее сохранение: ${new Date(templateUpdatedAt).toLocaleString('ru-RU')}` : 'Используется базовый шаблон SupplyDesk.'}
                </p>
                <button
                  type="button"
                  onClick={() => { void handleSaveTemplate(); }}
                  disabled={templateSaving}
                  className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-accent-600 px-5 py-2.5 text-sm font-bold text-white shadow-soft transition hover:bg-accent-700 disabled:cursor-wait disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-500 focus-visible:ring-offset-2"
                >
                  {templateSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                  {templateSaving ? 'Сохраняем…' : 'Сохранить шаблон'}
                </button>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
