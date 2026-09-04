import { useEffect, useMemo, useRef, useState, type ButtonHTMLAttributes, type ReactNode } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BarChart3,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleDot,
  ClipboardList,
  Clock3,
  FileText,
  Inbox,
  LayoutGrid,
  Mail,
  Menu,
  MessageSquare,
  MoreHorizontal,
  Paperclip,
  PackageSearch,
  PanelRight,
  Plus,
  Search,
  Send,
  Settings2,
  ShieldAlert,
  SlidersHorizontal,
  Truck,
  Users,
  X,
} from 'lucide-react';
import {
  Badge as ShadcnBadge,
  Button as ShadcnButton,
  Checkbox,
  Dialog,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Input,
  Popover,
  PopoverContent,
  PopoverTrigger,
  Sidebar as ShadcnSidebar,
  SidebarProvider,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui';
import { cn } from '@/lib/utils';
import '@/styles/ui-experiment.css';

type Tone = 'neutral' | 'info' | 'success' | 'warning' | 'danger';
type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'quiet';
type ExperimentScreen = 'dashboard' | 'requests' | 'suppliers' | 'messages';

interface RequestRow {
  id: number;
  name: string;
  positions: number;
  suppliers: number;
  replies: number;
  pending: number;
  deadline: string;
  deadlineTone: Tone;
  status: string;
  statusTone: Tone;
  progress: number;
  updated: string;
}

interface SupplierRow {
  id: number;
  name: string;
  inn: string;
  site: string;
  contact: string;
  contactTone: Tone;
  response: number;
  requests: number;
  lastContact: string;
  relationship: string;
  relationshipTone: Tone;
}

interface MessageItem {
  id: number;
  direction: 'inbound' | 'outbound';
  sender: string;
  time: string;
  text: string;
  attachments?: string[];
}

interface MailThread {
  id: number;
  requestId: number | null;
  requestName: string;
  supplier: string;
  email: string;
  subject: string;
  preview: string;
  time: string;
  state: string;
  stateTone: Tone;
  unread?: boolean;
  messages: MessageItem[];
}

const navItems: { label: string; shortLabel: string; to: string; icon: typeof BarChart3 }[] = [
  { label: 'Обзор', shortLabel: 'Обзор', to: '/experiment/ui-shadcn-v2', icon: LayoutGrid },
  { label: 'Мои заявки', shortLabel: 'Заявки', to: '/experiment/ui-shadcn-v2/requests', icon: ClipboardList },
  { label: 'Переписка', shortLabel: 'Письма', to: '/experiment/ui-shadcn-v2/messages', icon: MessageSquare },
  { label: 'Поставщики', shortLabel: 'Поставщики', to: '/experiment/ui-shadcn-v2/suppliers', icon: PackageSearch },
];

const requests: RequestRow[] = [
  { id: 1043, name: 'Строительные материалы', positions: 4, suppliers: 27, replies: 8, pending: 3, deadline: 'Сегодня, 18:00', deadlineTone: 'warning', status: 'В работе', statusTone: 'info', progress: 72, updated: '12 мин назад' },
  { id: 1042, name: 'Подшипники для линии фасовки', positions: 6, suppliers: 14, replies: 5, pending: 0, deadline: '6 сент.', deadlineTone: 'neutral', status: 'Есть ответы', statusTone: 'success', progress: 100, updated: 'Вчера' },
  { id: 1041, name: 'Промышленная химия · Q4', positions: 9, suppliers: 33, replies: 0, pending: 12, deadline: '10 сент.', deadlineTone: 'neutral', status: 'Ожидает ответа', statusTone: 'warning', progress: 38, updated: 'Вчера' },
  { id: 1039, name: 'Тара и упаковка', positions: 3, suppliers: 8, replies: 3, pending: 0, deadline: 'Завершено', deadlineTone: 'success', status: 'Завершена', statusTone: 'success', progress: 100, updated: '2 сент.' },
  { id: 1038, name: 'Запасные части для компрессоров', positions: 7, suppliers: 19, replies: 1, pending: 0, deadline: 'Просрочено на 1 день', deadlineTone: 'danger', status: 'Требует внимания', statusTone: 'danger', progress: 54, updated: '2 сент.' },
];

const suppliers: SupplierRow[] = [
  { id: 1, name: 'ООО «ОЛЛБРИК»', inn: '7709988922', site: 'all-brick.ru', contact: 'Ответ получен', contactTone: 'success', response: 82, requests: 11, lastContact: 'Сегодня, 09:42', relationship: 'Проверенный', relationshipTone: 'success' },
  { id: 2, name: 'ООО «ЕВРОМИКС СМ»', inn: '5022052442', site: 'blockstock.ru', contact: 'Ожидаем ответ', contactTone: 'warning', response: 41, requests: 7, lastContact: 'Вчера, 16:20', relationship: 'В работе', relationshipTone: 'info' },
  { id: 3, name: 'АО «ТехноПром»', inn: '7724120864', site: 'technoprom.example', contact: 'Ответ получен', contactTone: 'success', response: 67, requests: 5, lastContact: '2 сент., 13:10', relationship: 'Проверенный', relationshipTone: 'success' },
  { id: 4, name: 'ООО «Северный ресурс»', inn: '7805248160', site: 'sever-resource.example', contact: 'Не контактировали', contactTone: 'neutral', response: 0, requests: 0, lastContact: 'Нет контакта', relationship: 'Новый', relationshipTone: 'neutral' },
  { id: 5, name: 'ООО «Промснаб-Волга»', inn: '5257103129', site: 'promsnab.example', contact: 'Не отвечает', contactTone: 'danger', response: 12, requests: 8, lastContact: '19 авг., 11:04', relationship: 'Нужна проверка', relationshipTone: 'danger' },
];

const mailThreads: MailThread[] = [
  {
    id: 1,
    requestId: 1043,
    requestName: 'Строительные материалы',
    supplier: 'ООО «ОЛЛБРИК»',
    email: 'sales@all-brick.ru',
    subject: 'Re: Строительные материалы · запрос цены',
    preview: 'Добрый день! Подтверждаем наличие кирпича и готовы прислать расчёт…',
    time: 'Сегодня, 09:42',
    state: 'Ответ получен',
    stateTone: 'success',
    unread: true,
    messages: [
      { id: 11, direction: 'outbound', sender: 'Елена · SupplyDesk', time: 'Вчера, 15:08', text: 'Добрый день! Просим подтвердить наличие и стоимость материалов из приложенной заявки. Срок поставки — до 20 сентября.' },
      { id: 12, direction: 'inbound', sender: 'Алексей · ООО «ОЛЛБРИК»', time: 'Сегодня, 09:42', text: 'Добрый день, Елена! Подтверждаем наличие кирпича и блока. Во вложении направляю актуальный прайс и сроки отгрузки. По позиции D500 можем предложить альтернативу с поставкой на два дня раньше.', attachments: ['Прайс_ОЛЛБРИК_сентябрь.xlsx', 'Сроки_отгрузки.pdf'] },
    ],
  },
  {
    id: 2,
    requestId: 1041,
    requestName: 'Промышленная химия · Q4',
    supplier: 'АО «ХимРесурс»',
    email: 'tenders@himresource.example',
    subject: 'Запрос предложения · промышленная химия',
    preview: 'Запрос получили, вернёмся с предложением до конца недели.',
    time: 'Вчера, 16:20',
    state: 'Ожидаем ответ',
    stateTone: 'warning',
    messages: [
      { id: 21, direction: 'outbound', sender: 'Елена · SupplyDesk', time: 'Вчера, 16:20', text: 'Коллеги, добрый день! Направляем запрос на поставку промышленной химии на четвёртый квартал.' },
    ],
  },
  {
    id: 3,
    requestId: null,
    requestName: 'Без привязки',
    supplier: 'ООО «РегионКомплект»',
    email: 'info@regionkomplekt.example',
    subject: 'Re: Запрос на муфты',
    preview: 'Готовы обсудить замену позиции и предложить срок поставки.',
    time: '2 сент., 12:06',
    state: 'Без привязки',
    stateTone: 'warning',
    messages: [
      { id: 31, direction: 'inbound', sender: 'ООО «РегионКомплект»', time: '2 сент., 12:06', text: 'Добрый день! Видим ваш запрос на муфты, но не нашли номер заявки. Готовы обсудить замену позиции и предложить срок поставки.' },
    ],
  },
];

const requestFilters: { key: 'all' | 'active' | 'waiting' | 'done' | 'attention'; label: string }[] = [
  { key: 'all', label: 'Все' },
  { key: 'active', label: 'В работе' },
  { key: 'waiting', label: 'Ожидают ответа' },
  { key: 'done', label: 'Завершены' },
  { key: 'attention', label: 'Требуют внимания' },
];

const supplierFilters: { key: 'all' | 'trusted' | 'waiting' | 'silent'; label: string }[] = [
  { key: 'all', label: 'Все' },
  { key: 'trusted', label: 'Проверенные' },
  { key: 'waiting', label: 'Ожидают ответа' },
  { key: 'silent', label: 'Не отвечают' },
];

function toneLabel(tone: Tone) {
  return tone;
}

function V2Button({ variant = 'secondary', className, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: ButtonVariant }) {
  const primitiveVariant = variant === 'primary' ? 'default' : variant === 'secondary' ? 'outline' : 'ghost';
  return <ShadcnButton variant={primitiveVariant} size="md" className={cn('sd-v2-button', `sd-v2-button--${variant}`, className)} {...props}>{children}</ShadcnButton>;
}

function V2Badge({ label, tone = 'neutral', dot = false }: { label: string; tone?: Tone; dot?: boolean }) {
  return <ShadcnBadge variant="outline" className={cn('sd-v2-badge', `sd-v2-badge--${toneLabel(tone)}`)}>{dot && <span className="sd-v2-badge__dot" aria-hidden="true" />}{label}</ShadcnBadge>;
}

function IconButton({ label, children, className, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return <ShadcnButton aria-label={label} title={label} variant="ghost" size="icon" className={cn('sd-v2-icon-button', className)} {...props}>{children}</ShadcnButton>;
}

function PageIntro({ eyebrow, title, description, actions }: { eyebrow: string; title: string; description: string; actions?: ReactNode }) {
  return (
    <div className="sd-v2-page-intro">
      <div className="sd-v2-page-intro__copy">
        <p className="sd-v2-eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        <p className="sd-v2-page-intro__description">{description}</p>
      </div>
      {actions && <div className="sd-v2-page-intro__actions">{actions}</div>}
    </div>
  );
}

function SectionHeader({ eyebrow, title, meta, action }: { eyebrow?: string; title: string; meta?: string; action?: ReactNode }) {
  return (
    <header className="sd-v2-section-header">
      <div>
        {eyebrow && <p className="sd-v2-section-header__eyebrow">{eyebrow}</p>}
        <div className="sd-v2-section-header__title-row"><h2>{title}</h2>{meta && <span className="sd-v2-section-header__meta">{meta}</span>}</div>
      </div>
      {action}
    </header>
  );
}

function Notice({ message, onDismiss }: { message: string; onDismiss: () => void }) {
  return <div className="sd-v2-notice" role="status"><CheckCircle2 size={16} /><span>{message}</span><IconButton label="Закрыть уведомление" onClick={onDismiss}><X size={15} /></IconButton></div>;
}

function Sidebar({ mobile = false, onNavigate }: { mobile?: boolean; onNavigate?: () => void }) {
  return (
    <SidebarProvider className="h-full min-h-0 w-full bg-transparent">
      <ShadcnSidebar collapsible="none" className="h-full min-h-0 w-full bg-transparent p-0 text-inherit">
        <div className={cn('sd-v2-sidebar__inner', mobile && 'sd-v2-sidebar__inner--mobile')}>
      <div className="sd-v2-brand">
        <div className="sd-v2-brand__mark" aria-hidden="true"><span /> <span /></div>
        <div><strong>SupplyDesk</strong><span>Procurement OS</span></div>
        {!mobile && <span className="sd-v2-brand__version">V2</span>}
      </div>
      <div className="sd-v2-sidebar__section-label">Рабочее пространство</div>
      <nav aria-label="Навигация эксперимента" className="sd-v2-nav">
        {navItems.map(({ label, shortLabel, to, icon: Icon }) => (
          <NavLink key={to} to={to} end={to === navItems[0].to} onClick={onNavigate} className={({ isActive }) => cn('sd-v2-nav__item', isActive && 'is-active')}>
            <Icon size={17} strokeWidth={1.8} />
            <span>{mobile ? shortLabel : label}</span>
            {label === 'Переписка' && <span className="sd-v2-nav__count">3</span>}
          </NavLink>
        ))}
      </nav>
      <div className="sd-v2-sidebar__section-label sd-v2-sidebar__section-label--secondary">Система</div>
      <nav aria-label="Системная навигация" className="sd-v2-nav">
        <a className="sd-v2-nav__item sd-v2-nav__item--muted" href="#experiment-notes"><Settings2 size={17} strokeWidth={1.8} /><span>Настройки</span></a>
        <a className="sd-v2-nav__item sd-v2-nav__item--muted" href="#experiment-notes"><ShieldAlert size={17} strokeWidth={1.8} /><span>Правила отправки</span></a>
      </nav>
      <div className="sd-v2-sidebar__footer">
        <div className="sd-v2-profile"><div className="sd-v2-profile__avatar">ЕК</div><div><strong>Елена Кузнецова</strong><span>Отдел снабжения</span></div><MoreHorizontal size={16} /></div>
        <div className="sd-v2-sidebar__footnote"><CircleDot size={12} /> Стенд презентации · данные вымышлены</div>
      </div>
        </div>
      </ShadcnSidebar>
    </SidebarProvider>
  );
}

function ExperimentShell({ children }: { children: ReactNode }) {
  const location = useLocation();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);
  useEffect(() => setMobileNavOpen(false), [location.pathname]);
  return (
    <div className="sd-v2-theme">
      <div className="sd-v2-shell">
        <aside className="sd-v2-sidebar" aria-label="Навигация SupplyDesk v2"><Sidebar /></aside>
        <div className="sd-v2-main">
          <header className="sd-v2-mobile-header">
            <IconButton label="Открыть навигацию" aria-expanded={mobileNavOpen} onClick={() => setMobileNavOpen(true)}><Menu size={20} /></IconButton>
            <div className="sd-v2-mobile-header__brand"><div className="sd-v2-brand__mark" aria-hidden="true"><span /><span /></div><strong>SupplyDesk</strong></div>
            <V2Badge label="V2" tone="info" />
          </header>
          {mobileNavOpen && <div className="sd-v2-mobile-scrim" aria-hidden="true" onClick={() => setMobileNavOpen(false)} />}
          {mobileNavOpen && <aside className="sd-v2-mobile-drawer" aria-label="Мобильная навигация"><div className="sd-v2-mobile-drawer__close"><span className="sd-v2-sidebar__section-label">Меню</span><IconButton label="Закрыть навигацию" onClick={() => setMobileNavOpen(false)}><X size={18} /></IconButton></div><Sidebar mobile onNavigate={() => setMobileNavOpen(false)} /></aside>}
          <div className="sd-v2-topbar" role="banner"><span><span className="sd-v2-topbar__dot" /> Альтернативный рабочий стол</span><span className="sd-v2-topbar__hint"><kbd>⌘</kbd><kbd>K</kbd> Быстрый поиск <span className="sd-v2-topbar__divider" /> Обзор v2</span></div>
          <main id="main-content" className="sd-v2-content">{children}</main>
        </div>
      </div>
    </div>
  );
}

function MetricStrip() {
  const metrics = [
    { label: 'Активные заявки', value: '12', delta: '+2 за неделю', icon: ClipboardList, tone: 'info' as Tone },
    { label: 'Ожидают ответа', value: '15', delta: '3 требуют внимания', icon: Clock3, tone: 'warning' as Tone },
    { label: 'Новые ответы', value: '8', delta: 'за последние 24 часа', icon: Inbox, tone: 'success' as Tone },
    { label: 'Поставщики в базе', value: '148', delta: 'из них 24 проверенных', icon: Users, tone: 'neutral' as Tone },
  ];
  return <div className="sd-v2-metric-strip">{metrics.map(({ label, value, delta, icon: Icon, tone }) => <div className="sd-v2-metric" key={label}><div className={cn('sd-v2-metric__icon', `sd-v2-metric__icon--${tone}`)}><Icon size={16} /></div><div className="sd-v2-metric__copy"><span>{label}</span><strong>{value}</strong><small>{delta}</small></div></div>)}</div>;
}

function DashboardPage() {
  const [notice, setNotice] = useState('');
  return (
    <div className="sd-v2-page">
      <PageIntro eyebrow="Операционный обзор · Среда, 4 сентября" title="День под контролем" description="Сводка по заявкам, ответам поставщиков и ближайшим действиям команды." actions={<V2Button variant="primary" onClick={() => setNotice('В эксперименте открывается только визуальный прототип формы новой заявки.')}><Plus size={16} /> Новая заявка</V2Button>} />
      {notice && <Notice message={notice} onDismiss={() => setNotice('')} />}
      <MetricStrip />
      <div className="sd-v2-dashboard-lead">
        <section className="sd-v2-command-panel" aria-labelledby="today-focus-title">
          <div className="sd-v2-command-panel__top"><div><p className="sd-v2-section-header__eyebrow">Фокус на сегодня</p><h2 id="today-focus-title">Закрыть три запроса до 18:00</h2><p>По двум заявкам уже есть ответы. Осталось сравнить условия и вернуть выбор в рабочий список.</p></div><div className="sd-v2-command-panel__stamp"><span>04</span><small>СЕН</small></div></div>
          <div className="sd-v2-command-panel__bottom"><div className="sd-v2-progress-copy"><span>Прогресс активного пула</span><strong>72%</strong></div><div className="sd-v2-progress"><span style={{ width: '72%' }} /></div><div className="sd-v2-command-panel__meta"><span><Check size={14} /> 9 из 12 заявок в движении</span><span><Clock3 size={14} /> Следующая проверка через 18 мин.</span></div></div>
        </section>
        <section className="sd-v2-attention" aria-labelledby="attention-title"><div className="sd-v2-attention__header"><div><p className="sd-v2-section-header__eyebrow">Сигналы</p><h2 id="attention-title">Требует внимания</h2></div><span className="sd-v2-attention__count">4</span></div><div className="sd-v2-attention__list"><a href="#attention-request" className="sd-v2-attention__item"><span className="sd-v2-attention__marker sd-v2-attention__marker--danger" /><span><strong>Просрочен ответ</strong><small>Запасные части · 1 день</small></span><ArrowUpRight size={15} /></a><a href="#attention-mail" className="sd-v2-attention__item"><span className="sd-v2-attention__marker sd-v2-attention__marker--warning" /><span><strong>Новое письмо</strong><small>ОЛЛБРИК · заявка №1043</small></span><ArrowUpRight size={15} /></a><a href="#attention-search" className="sd-v2-attention__item"><span className="sd-v2-attention__marker sd-v2-attention__marker--info" /><span><strong>Поиск продолжается</strong><small>Промышленная химия · 62%</small></span><ArrowUpRight size={15} /></a></div></section>
      </div>
      <div className="sd-v2-dashboard-grid">
        <section className="sd-v2-section sd-v2-table-section" aria-labelledby="active-requests-title"><SectionHeader eyebrow="Рабочий список" title="Активные заявки" meta="5 из 12" action={<a href="/experiment/ui-shadcn-v2/requests" className="sd-v2-text-link">Все заявки <ArrowRight size={14} /></a>} /><RequestTable rows={requests.slice(0, 4)} compact /></section>
        <section className="sd-v2-section" aria-labelledby="recent-replies-title"><SectionHeader eyebrow="Входящие" title="Последние ответы" meta="8 новых" action={<a href="/experiment/ui-shadcn-v2/messages" className="sd-v2-text-link">Открыть inbox <ArrowRight size={14} /></a>} /><div className="sd-v2-reply-list">{mailThreads.slice(0, 3).map((thread) => <a className="sd-v2-reply-item" key={thread.id} href="/experiment/ui-shadcn-v2/messages"><div className="sd-v2-avatar">{thread.supplier.slice(4, 6)}</div><div className="sd-v2-reply-item__body"><strong>{thread.supplier}</strong><span>{thread.subject}</span><small>{thread.time} · {thread.requestName}</small></div><ArrowUpRight size={15} /></a>)}</div></section>
      </div>
      <p id="experiment-notes" className="sd-v2-experiment-note">Визуальный стенд · статические данные · production-маршруты и действия не затрагиваются.</p>
    </div>
  );
}

function RequestTable({ rows, compact = false }: { rows: RequestRow[]; compact?: boolean }) {
  return (
    <div className={cn('sd-v2-table-wrap', compact && 'sd-v2-table-wrap--compact')}>
      <Table className="sd-v2-table">
        <TableHeader><TableRow><TableHead>Заявка</TableHead><TableHead>Статус</TableHead><TableHead>Поставщики</TableHead><TableHead>Ответы</TableHead><TableHead>Дедлайн</TableHead><TableHead><span className="sr-only">Действия</span></TableHead></TableRow></TableHeader>
        <TableBody>{rows.map((request) => <TableRow key={request.id}>
          <TableCell data-label="Заявка"><div className="sd-v2-primary-cell"><strong>{request.name}</strong><span>№{request.id} · {request.positions} позиц. · обновлено {request.updated}</span></div></TableCell>
          <TableCell data-label="Статус"><V2Badge label={request.status} tone={request.statusTone} dot /></TableCell>
          <TableCell data-label="Поставщики"><span className="sd-v2-number">{request.suppliers}</span><div className="sd-v2-mini-progress"><span style={{ width: `${request.progress}%` }} /></div></TableCell>
          <TableCell data-label="Ответы"><span className="sd-v2-number">{request.replies}</span>{request.pending > 0 && <small className="sd-v2-cell-note">{request.pending} ждут</small>}</TableCell>
          <TableCell data-label="Дедлайн"><span className={cn('sd-v2-deadline', `sd-v2-deadline--${request.deadlineTone}`)}>{request.deadline}</span></TableCell>
          <TableCell className="sd-v2-table__action"><a className="sd-v2-row-action" href={`/experiment/ui-shadcn-v2/requests?request=${request.id}`}>Открыть <ArrowUpRight size={14} /></a></TableCell>
        </TableRow>)}</TableBody>
      </Table>
    </div>
  );
}

function RequestsPage() {
  const [filter, setFilter] = useState<(typeof requestFilters)[number]['key']>('all');
  const [search, setSearch] = useState('');
  const [showProgress, setShowProgress] = useState(true);
  const [preview, setPreview] = useState<RequestRow | null>(null);
  const previewTriggerRef = useRef<HTMLElement | null>(null);
  const openPreview = (request: RequestRow, trigger?: HTMLElement) => {
    previewTriggerRef.current = trigger ?? null;
    setPreview(request);
  };
  const closePreview = () => {
    const trigger = previewTriggerRef.current;
    setPreview(null);
    window.requestAnimationFrame(() => trigger?.focus());
  };
  const visibleRequests = useMemo(() => requests.filter((request) => {
    const matchesSearch = `${request.name} ${request.id}`.toLowerCase().includes(search.trim().toLowerCase());
    const matchesFilter = filter === 'all' || (filter === 'active' && request.status === 'В работе') || (filter === 'waiting' && request.status === 'Ожидает ответа') || (filter === 'done' && request.status === 'Завершена') || (filter === 'attention' && request.status === 'Требует внимания');
    return matchesSearch && matchesFilter;
  }), [filter, search]);
  return (
    <div className="sd-v2-page">
      <PageIntro eyebrow="Рабочее пространство · Реальные статусы" title="Мои заявки" description="Сравнивайте сроки, ответы и движение по поставщикам в одном рабочем списке." actions={<V2Button variant="primary"><Plus size={16} /> Новая заявка</V2Button>} />
      <section className="sd-v2-section" aria-labelledby="requests-list-title">
        <div className="sd-v2-list-toolbar">
          <div className="sd-v2-filter-group" role="group" aria-label="Фильтр заявок">{requestFilters.map((item) => <button key={item.key} type="button" aria-pressed={filter === item.key} className={cn('sd-v2-filter-chip', filter === item.key && 'is-active')} onClick={() => setFilter(item.key)}>{item.label}<span>{item.key === 'all' ? requests.length : item.key === 'attention' ? 1 : item.key === 'done' ? 1 : item.key === 'waiting' ? 1 : 2}</span></button>)}</div>
          <label className="sd-v2-search"><Search size={16} /><span className="sr-only">Поиск по заявкам</span><Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Поиск по названию или №…" /></label>
          <Popover>
            <PopoverTrigger asChild><IconButton label="Настроить отображение" className="sd-v2-toolbar-icon"><SlidersHorizontal size={17} /></IconButton></PopoverTrigger>
            <PopoverContent align="end" className="w-64">
              <p className="text-sm font-semibold text-ink-900">Настроить отображение</p>
              <label className="mt-3 flex items-center gap-2 text-sm text-ink-700"><Checkbox checked={showProgress} onCheckedChange={(checked) => setShowProgress(checked === true)} /><span>Показывать прогресс</span></label>
            </PopoverContent>
          </Popover>
        </div>
        <div className="sd-v2-section-header sd-v2-section-header--inside"><div><p className="sd-v2-section-header__eyebrow">Структурированные данные</p><div className="sd-v2-section-header__title-row"><h2 id="requests-list-title">Все заявки</h2><span className="sd-v2-section-header__meta">{visibleRequests.length} в списке</span></div></div><div className="sd-v2-table-legend"><span><span className="sd-v2-legend-dot sd-v2-legend-dot--info" />в работе</span><span><span className="sd-v2-legend-dot sd-v2-legend-dot--warning" />нужен ответ</span></div></div>
        {visibleRequests.length > 0 ? <div onClick={(event) => { const target = event.target as HTMLElement; if (target.closest('button, a')) return; const row = target.closest('tr'); if (row) { const id = Number(row.getAttribute('data-request-id')); const next = requests.find((item) => item.id === id); if (next) openPreview(next, target); } }}><div className="sd-v2-table-wrap"><Table className="sd-v2-table sd-v2-table--requests"><TableHeader><TableRow><TableHead>Заявка</TableHead><TableHead>Статус</TableHead><TableHead>Поставщики</TableHead><TableHead>Ответы</TableHead><TableHead>Дедлайн</TableHead><TableHead><span className="sr-only">Действия</span></TableHead></TableRow></TableHeader><TableBody>{visibleRequests.map((request) => <TableRow key={request.id} data-request-id={request.id}><TableCell data-label="Заявка"><button type="button" className="sd-v2-primary-cell sd-v2-primary-cell--button" onClick={(event) => openPreview(request, event.currentTarget)}><strong>{request.name}</strong><span>№{request.id} · {request.positions} позиций · {request.updated}</span></button></TableCell><TableCell data-label="Статус"><V2Badge label={request.status} tone={request.statusTone} dot /></TableCell><TableCell data-label="Поставщики"><span className="sd-v2-number">{request.suppliers}</span>{showProgress && <div className="sd-v2-mini-progress"><span style={{ width: `${request.progress}%` }} /></div>}</TableCell><TableCell data-label="Ответы"><span className="sd-v2-number">{request.replies}</span>{request.pending > 0 && <small className="sd-v2-cell-note">{request.pending} ждут</small>}</TableCell><TableCell data-label="Дедлайн"><span className={cn('sd-v2-deadline', `sd-v2-deadline--${request.deadlineTone}`)}>{request.deadline}</span></TableCell><TableCell className="sd-v2-table__action"><button className="sd-v2-row-action" type="button" onClick={(event) => openPreview(request, event.currentTarget)}>Открыть <ArrowUpRight size={14} /></button></TableCell></TableRow>)}</TableBody></Table></div></div> : <div className="sd-v2-empty"><ClipboardList size={22} /><strong>Ничего не найдено</strong><span>Попробуйте изменить поиск или выбрать другой статус.</span></div>}
      </section>
      {preview && <RequestPreview request={preview} onClose={closePreview} />}
    </div>
  );
}

function RequestPreview({ request, onClose }: { request: RequestRow; onClose: () => void }) {
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sd-v2-preview [&>button]:hidden">
        <DialogHeader className="sd-v2-preview__header">
          <div><p className="sd-v2-section-header__eyebrow">Предпросмотр заявки</p><DialogTitle>{request.name}</DialogTitle><span>№{request.id} · обновлено {request.updated}</span></div>
          <DialogClose asChild><IconButton label="Закрыть предпросмотр"><X size={18} /></IconButton></DialogClose>
        </DialogHeader>
        <div className="sd-v2-preview__body"><div className="sd-v2-preview__status"><V2Badge label={request.status} tone={request.statusTone} dot /><span>Дедлайн: <strong>{request.deadline}</strong></span></div><div className="sd-v2-preview__stats"><div><span>Поставщики</span><strong>{request.suppliers}</strong></div><div><span>Ответы</span><strong>{request.replies}</strong></div><div><span>Позиций</span><strong>{request.positions}</strong></div></div><div className="sd-v2-preview__note"><FileText size={16} /><p>Это визуальный предпросмотр. Открытие production-заявки намеренно не включено в эксперимент.</p></div></div>
        <DialogFooter className="sd-v2-preview__footer"><V2Button variant="quiet" onClick={onClose}>Закрыть</V2Button><V2Button variant="primary" onClick={onClose}>Понятно</V2Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function SuppliersPage() {
  const [filter, setFilter] = useState<(typeof supplierFilters)[number]['key']>('all');
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<number[]>([]);
  const [preview, setPreview] = useState<SupplierRow | null>(null);
  const previewTriggerRef = useRef<HTMLElement | null>(null);
  const openPreview = (supplier: SupplierRow, trigger?: HTMLElement) => {
    previewTriggerRef.current = trigger ?? null;
    setPreview(supplier);
  };
  const closePreview = () => {
    const trigger = previewTriggerRef.current;
    setPreview(null);
    window.requestAnimationFrame(() => trigger?.focus());
  };
  const visibleSuppliers = useMemo(() => suppliers.filter((supplier) => {
    const matchesSearch = `${supplier.name} ${supplier.inn} ${supplier.site}`.toLowerCase().includes(search.trim().toLowerCase());
    const matchesFilter = filter === 'all' || (filter === 'trusted' && supplier.relationship === 'Проверенный') || (filter === 'waiting' && supplier.contact === 'Ожидаем ответ') || (filter === 'silent' && supplier.contact === 'Не отвечает');
    return matchesSearch && matchesFilter;
  }), [filter, search]);
  const toggle = (id: number) => setSelected((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id]);
  return (
    <div className="sd-v2-page">
      <PageIntro eyebrow="Справочник · Контакты и история" title="Поставщики" description="Быстрый обзор компаний, их последнего контакта и состояния ответа." actions={<V2Button variant="primary" disabled={selected.length === 0}><Send size={16} /> Создать заявку {selected.length > 0 && `(${selected.length})`}</V2Button>} />
      <section className="sd-v2-section" aria-labelledby="suppliers-list-title">
        <div className="sd-v2-list-toolbar"><div className="sd-v2-filter-group" role="group" aria-label="Фильтр поставщиков">{supplierFilters.map((item) => <button key={item.key} type="button" aria-pressed={filter === item.key} className={cn('sd-v2-filter-chip', filter === item.key && 'is-active')} onClick={() => setFilter(item.key)}>{item.label}<span>{item.key === 'all' ? suppliers.length : item.key === 'trusted' ? 2 : item.key === 'waiting' ? 1 : 1}</span></button>)}</div><label className="sd-v2-search"><Search size={16} /><span className="sr-only">Поиск по поставщикам</span><Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Название, ИНН или сайт…" /></label></div>
        <div className="sd-v2-section-header sd-v2-section-header--inside"><div><p className="sd-v2-section-header__eyebrow">Компании</p><div className="sd-v2-section-header__title-row"><h2 id="suppliers-list-title">Все поставщики</h2><span className="sd-v2-section-header__meta">{visibleSuppliers.length} в списке</span></div></div><label className="sd-v2-select-all"><Checkbox checked={visibleSuppliers.length > 0 && visibleSuppliers.every((supplier) => selected.includes(supplier.id))} onCheckedChange={(checked) => setSelected(checked === true ? visibleSuppliers.map((supplier) => supplier.id) : [])} />Выбрать все</label></div>
        <div className="sd-v2-table-wrap"><Table className="sd-v2-table sd-v2-table--suppliers"><TableHeader><TableRow><TableHead className="sd-v2-table__check-col"><span className="sr-only">Выбрать</span></TableHead><TableHead>Компания</TableHead><TableHead>Контакт</TableHead><TableHead>Ответы</TableHead><TableHead>Последний контакт</TableHead><TableHead>Связь</TableHead><TableHead><span className="sr-only">Действия</span></TableHead></TableRow></TableHeader><TableBody>{visibleSuppliers.map((supplier) => <TableRow key={supplier.id}><TableCell data-label="Выбрать" className="sd-v2-table__check-col"><Checkbox aria-label={`Выбрать ${supplier.name}`} checked={selected.includes(supplier.id)} onCheckedChange={() => toggle(supplier.id)} /></TableCell><TableCell data-label="Компания"><div className="sd-v2-primary-cell"><button type="button" className="sd-v2-primary-cell--button" onClick={(event) => openPreview(supplier, event.currentTarget)}><strong>{supplier.name}</strong><span>ИНН {supplier.inn}</span></button><a href={`https://${supplier.site}`} className="sd-v2-site-link" target="_blank" rel="noreferrer">{supplier.site} <ArrowUpRight size={12} /></a></div></TableCell><TableCell data-label="Контакт"><V2Badge label={supplier.contact} tone={supplier.contactTone} dot /></TableCell><TableCell data-label="Ответы"><div className="sd-v2-response"><strong>{supplier.response}%</strong><div className="sd-v2-mini-progress"><span style={{ width: `${supplier.response}%` }} /></div><small>{supplier.requests} заявок</small></div></TableCell><TableCell data-label="Последний контакт"><span className="sd-v2-table-meta">{supplier.lastContact}</span></TableCell><TableCell data-label="Связь"><V2Badge label={supplier.relationship} tone={supplier.relationshipTone} /></TableCell><TableCell className="sd-v2-table__action"><button className="sd-v2-row-action" type="button" onClick={(event) => openPreview(supplier, event.currentTarget)}>Карточка <ArrowUpRight size={14} /></button></TableCell></TableRow>)}</TableBody></Table></div>
      </section>
      {selected.length > 0 && <div className="sd-v2-selection-bar"><div><strong>{selected.length}</strong><span>поставщика выбрано</span></div><div><V2Button variant="quiet" onClick={() => setSelected([])}>Снять выбор</V2Button><V2Button variant="primary" onClick={() => setSelected([])}><Send size={15} /> Создать заявку</V2Button></div></div>}
      {preview && <SupplierPreview supplier={preview} onClose={closePreview} />}
    </div>
  );
}

function SupplierPreview({ supplier, onClose }: { supplier: SupplierRow; onClose: () => void }) {
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sd-v2-preview [&>button]:hidden">
        <DialogHeader className="sd-v2-preview__header"><div><p className="sd-v2-section-header__eyebrow">Карточка поставщика</p><DialogTitle>{supplier.name}</DialogTitle><span>ИНН {supplier.inn} · {supplier.site}</span></div><DialogClose asChild><IconButton label="Закрыть карточку"><X size={18} /></IconButton></DialogClose></DialogHeader>
        <div className="sd-v2-preview__body"><div className="sd-v2-preview__status"><V2Badge label={supplier.relationship} tone={supplier.relationshipTone} dot /><span>Последний контакт: <strong>{supplier.lastContact}</strong></span></div><div className="sd-v2-preview__stats"><div><span>Ответы</span><strong>{supplier.response}%</strong></div><div><span>Заявки</span><strong>{supplier.requests}</strong></div><div><span>Контакт</span><strong>{supplier.contact}</strong></div></div><div className="sd-v2-preview__note"><Truck size={16} /><p>Открытие production-карточки намеренно не выполняется в изолированном эксперименте.</p></div></div>
        <DialogFooter className="sd-v2-preview__footer"><V2Button variant="quiet" onClick={onClose}>Закрыть</V2Button><V2Button variant="primary" onClick={onClose}>Понятно</V2Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function MessagesPage() {
  const [mode, setMode] = useState<'requests' | 'unmatched' | 'outbox'>('requests');
  const [search, setSearch] = useState('');
  const [selectedId, setSelectedId] = useState(1);
  const [notice, setNotice] = useState('');
  const visibleThreads = useMemo(() => mailThreads.filter((thread) => {
    const modeMatches = mode === 'requests' ? thread.requestId !== null : mode === 'unmatched' ? thread.requestId === null : thread.messages.some((message) => message.direction === 'outbound');
    const searchMatches = `${thread.supplier} ${thread.subject} ${thread.requestName}`.toLowerCase().includes(search.trim().toLowerCase());
    return modeMatches && searchMatches;
  }), [mode, search]);
  const selected = visibleThreads.find((thread) => thread.id === selectedId) ?? visibleThreads[0] ?? null;
  useEffect(() => { if (visibleThreads.length > 0 && !visibleThreads.some((thread) => thread.id === selectedId)) setSelectedId(visibleThreads[0].id); }, [selectedId, visibleThreads]);
  return <div className="sd-v2-page sd-v2-page--messages"><PageIntro eyebrow="Рабочее пространство · Заявка → поставщик → переписка" title="Переписка" description="Ответы поставщиков, привязанные к заявкам, в одном контексте." actions={<V2Button variant="secondary" onClick={() => setNotice('Ответ можно подготовить в production-рабочем пространстве.')}><Send size={16} /> Ответить</V2Button>} />{notice && <Notice message={notice} onDismiss={() => setNotice('')} />}<Tabs value={mode} onValueChange={(value) => setMode(value as typeof mode)}><TabsList className="sd-v2-mail-tabs" aria-label="Раздел переписки">{[{ key: 'requests', label: 'По заявкам', count: 2 }, { key: 'unmatched', label: 'Без привязки', count: 1 }, { key: 'outbox', label: 'Очередь', count: 1 }].map((tab) => <TabsTrigger key={tab.key} value={tab.key} className="sd-v2-mail-tab">{tab.label}<span>{tab.count}</span></TabsTrigger>)}</TabsList><TabsContent value="requests" className="hidden" /><TabsContent value="unmatched" className="hidden" /><TabsContent value="outbox" className="hidden" /></Tabs><div className={cn('sd-v2-mail-layout', selected && 'sd-v2-mail-layout--reading')}><aside className="sd-v2-mail-navigator" aria-label="Список переписок"><div className="sd-v2-mail-navigator__header"><div><p className="sd-v2-section-header__eyebrow">Рабочий список</p><h2>{mode === 'requests' ? 'Мои заявки' : mode === 'unmatched' ? 'Без привязки' : 'Исходящие'}</h2></div><span>{visibleThreads.length}</span></div><label className="sd-v2-search sd-v2-search--wide"><Search size={16} /><span className="sr-only">Поиск по переписке</span><Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Поиск по заявке или поставщику" /></label><div className="sd-v2-mail-navigator__summary"><span><Mail size={14} /> Все сообщения <strong>{visibleThreads.length}</strong></span><span><Clock3 size={14} /> Ждут ответа <strong>1</strong></span></div><div className="sd-v2-thread-list">{visibleThreads.map((thread) => <button key={thread.id} type="button" className={cn('sd-v2-thread', selected?.id === thread.id && 'is-active')} onClick={() => setSelectedId(thread.id)}><span className={cn('sd-v2-thread__indicator', thread.unread && 'is-unread')} /><span className="sd-v2-thread__body"><span className="sd-v2-thread__top"><strong>{thread.supplier}</strong><time>{thread.time}</time></span><span className="sd-v2-thread__request">{thread.requestName}</span><span className="sd-v2-thread__subject">{thread.subject}</span><span className="sd-v2-thread__preview">{thread.preview}</span></span><V2Badge label={thread.state} tone={thread.stateTone} /></button>)}</div>{visibleThreads.length === 0 && <div className="sd-v2-empty sd-v2-empty--small"><Mail size={20} /><strong>Нет переписок</strong><span>В этом представлении пока нет писем.</span></div>}</aside>{selected ? <MailDetail thread={selected} onBack={() => setSelectedId(0)} onReply={() => setNotice('Кнопка ответа оставлена как presentation-only состояние эксперимента.')} /> : <div className="sd-v2-mail-empty"><Mail size={24} /><strong>Выберите переписку</strong><span>Здесь появится история общения и следующий доступный шаг.</span></div>}<MailContext thread={selected} /></div><p className="sd-v2-experiment-note">Почтовые действия в этом стенде не отправляют письма и не меняют состояние заявок.</p></div>;
}

function MailDetail({ thread, onBack, onReply }: { thread: MailThread; onBack: () => void; onReply: () => void }) {
  return <section className="sd-v2-mail-detail" aria-labelledby="mail-detail-title"><header className="sd-v2-mail-detail__header"><IconButton label="Вернуться к списку переписок" className="sd-v2-mail-back" onClick={onBack}><ArrowLeft size={18} /></IconButton><div className="sd-v2-mail-detail__heading"><p className="sd-v2-section-header__eyebrow">{thread.requestId ? `Заявка №${thread.requestId}` : 'Входящее письмо'}</p><h2 id="mail-detail-title">{thread.subject}</h2><span>{thread.supplier} · {thread.email}</span></div><TooltipProvider delayDuration={150}><Tooltip><TooltipTrigger asChild><IconButton label="Открыть дополнительные действия"><MoreHorizontal size={18} /></IconButton></TooltipTrigger><TooltipContent>Дополнительные действия</TooltipContent></Tooltip></TooltipProvider></header><div className="sd-v2-mail-context-line"><div><FileText size={15} /><span><strong>{thread.requestName}</strong>{thread.requestId && ` · ${thread.messages.length + 2} сообщения`}</span></div><V2Badge label={thread.state} tone={thread.stateTone} dot /></div><div className="sd-v2-message-list">{thread.messages.map((message) => <article className={cn('sd-v2-message', `sd-v2-message--${message.direction}`)} key={message.id}><div className="sd-v2-message__meta"><div className="sd-v2-message__avatar">{message.direction === 'inbound' ? thread.supplier.slice(4, 6) : 'ЕК'}</div><div><strong>{message.sender}</strong><time>{message.time}</time></div></div><p>{message.text}</p>{message.attachments && <div className="sd-v2-attachments">{message.attachments.map((attachment) => <span key={attachment}><Paperclip size={14} />{attachment}</span>)}</div>}</article>)}</div><footer className="sd-v2-mail-reply-bar"><div><span className="sd-v2-reply-bar__status"><span /> Готово к следующему действию</span><small>Ответ будет открыт в рабочей версии</small></div><V2Button variant="primary" onClick={onReply}><Send size={15} /> Ответить поставщику <ArrowRight size={14} /></V2Button></footer></section>;
}

function MailContext({ thread }: { thread: MailThread | null }) {
  return <aside className="sd-v2-mail-context" aria-label="Контекст переписки"><div className="sd-v2-mail-context__heading"><div><p className="sd-v2-section-header__eyebrow">Контекст</p><h2>Связанные данные</h2></div><PanelRight size={17} /></div>{thread ? <><div className="sd-v2-context-block"><span className="sd-v2-context-label">Заявка</span><a href="/experiment/ui-shadcn-v2/requests" className="sd-v2-context-request"><span className="sd-v2-context-request__id">№{thread.requestId ?? '—'}</span><span><strong>{thread.requestName}</strong><small>{thread.requestId ? 'В работе · дедлайн сегодня' : 'Нужно проверить вручную'}</small></span><ChevronRight size={15} /></a></div><div className="sd-v2-context-block"><span className="sd-v2-context-label">Поставщик</span><div className="sd-v2-contact"><div className="sd-v2-avatar sd-v2-avatar--large">{thread.supplier.slice(4, 6)}</div><div><strong>{thread.supplier}</strong><span>{thread.email}</span><small>Последний контакт · {thread.time}</small></div></div></div><div className="sd-v2-context-block"><span className="sd-v2-context-label">Следующий шаг</span><div className="sd-v2-next-step"><span className="sd-v2-next-step__icon"><Check size={15} /></span><div><strong>{thread.requestId ? 'Сравнить условия ответа' : 'Привязать письмо к заявке'}</strong><small>{thread.requestId ? 'После проверки вложений' : 'Связь пока не определена'}</small></div></div></div><div className="sd-v2-context-block sd-v2-context-block--note"><span className="sd-v2-context-label">Заметка</span><p>Контекст заявки всегда виден рядом с письмом — не нужно держать номер в памяти или переключаться между экранами.</p></div></> : <div className="sd-v2-empty sd-v2-empty--small"><Mail size={20} /><span>Контекст появится после выбора письма.</span></div>}</aside>;
}

export function UiExperiment() {
  const location = useLocation();
  const path = location.pathname;
  const screen: ExperimentScreen = path.endsWith('/requests') ? 'requests' : path.endsWith('/suppliers') ? 'suppliers' : path.endsWith('/messages') ? 'messages' : 'dashboard';
  return <ExperimentShell>{screen === 'dashboard' && <DashboardPage />}{screen === 'requests' && <RequestsPage />}{screen === 'suppliers' && <SuppliersPage />}{screen === 'messages' && <MessagesPage />}</ExperimentShell>;
}
