import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  AlertCircle, Ban, Building2, ChevronRight, Clock,
  Globe, History, Loader2, Mail, Phone, Send, StickyNote, Star, X,
} from 'lucide-react';
import { api, ApiError } from '@/lib/api';
import { displaySupplierName, formatFullDate, formatRelativeDate } from '@/lib/utils';
import { StarRating, issueReasonLabels, outcomeLabels } from './StatusBits';
import { IssueModal, type IssueSubmission } from './IssueModal';
import { RegistryFinanceRow } from './RegistryFinanceRow';
import type { GlobalSupplierDetail, RelationshipStatus } from '@/lib/types';

export function SupplierPanel({ globalSupplierId, onClose }: { globalSupplierId: number; onClose: () => void }) {
  const navigate = useNavigate();
  const [supplier, setSupplier] = useState<GlobalSupplierDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [note, setNote] = useState('');
  const [editingNote, setEditingNote] = useState(false);
  const [showIssue, setShowIssue] = useState(false);
  const [savingRelationship, setSavingRelationship] = useState(false);
  const [blacklistPrompt, setBlacklistPrompt] = useState(false);
  const [blacklistReasonInput, setBlacklistReasonInput] = useState('');
  const [relationshipError, setRelationshipError] = useState('');

  const load = () => {
    setLoading(true);
    return api
      .globalSupplierDetail(globalSupplierId)
      .then((detail) => {
        setSupplier(detail);
        setNote(detail.note);
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [globalSupplierId]);

  const saveNote = async () => {
    await api.updateGlobalSupplierNote(globalSupplierId, note);
    setEditingNote(false);
    load();
  };

  const setRelationship = async (status: RelationshipStatus, reason?: string) => {
    setSavingRelationship(true);
    setRelationshipError('');
    try {
      await api.setGlobalSupplierRelationship(globalSupplierId, status, reason);
      setBlacklistPrompt(false);
      setBlacklistReasonInput('');
      await load();
    } catch (err) {
      setRelationshipError(err instanceof ApiError ? err.message : 'Не удалось изменить статус.');
    } finally {
      setSavingRelationship(false);
    }
  };

  const handleStatusClick = (status: RelationshipStatus) => {
    if (status === 'blacklisted' && supplier?.relationship_status !== 'blacklisted') {
      setRelationshipError('');
      setBlacklistPrompt(true);
      return;
    }
    setRelationship(status);
  };

  const confirmBlacklist = () => setRelationship('blacklisted', blacklistReasonInput);

  const rateDeal = async (requestId: number, supplierId: number, rating: number) => {
    await api.setDealRating(requestId, supplierId, rating);
    load();
  };

  const submitIssue = async (issue: IssueSubmission) => {
    await api.reportGlobalSupplierIssue(globalSupplierId, issue);
    setShowIssue(false);
    load();
  };

  const statusOptions: { key: RelationshipStatus; label: string; icon: typeof Star }[] = [
    { key: 'none', label: 'Обычный', icon: Building2 },
    { key: 'favorite', label: 'Избранный', icon: Star },
    { key: 'blacklisted', label: 'Чёрный список', icon: Ban },
  ];

  return (
    <>
      <div className="fixed inset-0 bg-ink-900/20 z-40" onClick={onClose} />
      <aside className="fixed right-0 top-0 bottom-0 w-[440px] bg-white shadow-panel z-50 flex flex-col">
        {loading || !supplier ? (
          <div className="flex-1 flex items-center justify-center">
            <Loader2 className="w-6 h-6 text-ink-300 animate-spin" />
          </div>
        ) : (
          <>
            <div className="px-6 py-5 border-b border-ink-200 flex items-start justify-between">
              <div className="min-w-0">
                <h2 title={supplier.name || undefined} className="text-lg font-bold text-ink-900 truncate">{supplier.name ? displaySupplierName(supplier.name, supplier.inn) : supplier.site}</h2>
                <div className="text-xs text-ink-400 mt-0.5">ИНН {supplier.inn}</div>
              </div>
              <button onClick={onClose} className="p-1.5 rounded-lg text-ink-400 hover:text-ink-800 hover:bg-ink-100 transition-colors shrink-0">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="px-6 pt-4 flex items-center gap-2">
              <a
                href={supplier.email ? `mailto:${supplier.email}` : undefined}
                aria-disabled={!supplier.email}
                title={supplier.email ? undefined : 'Нет email для этого поставщика'}
                className={`flex-1 inline-flex items-center justify-center gap-2 px-3 py-2 rounded-xl text-sm font-medium transition-colors ${
                  supplier.email ? 'bg-accent-600 text-white hover:bg-accent-700' : 'bg-ink-100 text-ink-400 cursor-not-allowed pointer-events-none'
                }`}
              >
                <Send className="w-3.5 h-3.5" />Написать
              </a>
              <button
                onClick={() => navigate(`/requests/new?suppliers=${globalSupplierId}`)}
                className="inline-flex items-center justify-center px-3 py-2 rounded-xl text-sm font-medium border border-ink-200 text-ink-700 hover:bg-ink-50 transition-colors"
              >
                В заявку
              </button>
            </div>

            <RegistryFinanceRow registry={supplier.registry} finances={supplier.finances} />

            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">
              <div>
                <div className="text-xs font-medium text-ink-500 uppercase tracking-wider mb-2">Статус отношений</div>
                <div className="flex items-center gap-1 bg-ink-100 rounded-xl p-1">
                  {statusOptions.map((opt) => {
                    const Icon = opt.icon;
                    const isActive = supplier.relationship_status === opt.key;
                    return (
                      <button
                        key={opt.key}
                        disabled={savingRelationship}
                        onClick={() => handleStatusClick(opt.key)}
                        className={`flex-1 flex items-center justify-center gap-1 px-1.5 py-2 rounded-lg text-xs font-medium whitespace-nowrap transition-all disabled:opacity-50 ${
                          isActive
                            ? opt.key === 'favorite' ? 'bg-white text-amber-600 shadow-soft'
                              : opt.key === 'blacklisted' ? 'bg-white text-red-600 shadow-soft'
                              : 'bg-white text-ink-800 shadow-soft'
                            : 'text-ink-500 hover:text-ink-800'
                        }`}
                      >
                        <Icon className="w-3.5 h-3.5" fill={opt.key === 'favorite' && isActive ? 'currentColor' : 'none'} />
                        {opt.label}
                      </button>
                    );
                  })}
                </div>
                {blacklistPrompt && (
                  <div className="mt-2 p-2.5 rounded-xl border border-red-200 bg-red-50 space-y-2">
                    <label className="block text-xs font-medium text-red-700">Причина (обязательно)</label>
                    <input
                      autoFocus
                      value={blacklistReasonInput}
                      onChange={(e) => setBlacklistReasonInput(e.target.value)}
                      placeholder="Например: не отвечает на письма"
                      className="w-full px-2.5 py-1.5 text-sm bg-white border border-red-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-red-200"
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={confirmBlacklist}
                        disabled={savingRelationship || !blacklistReasonInput.trim()}
                        className="px-3 py-1.5 text-xs font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 disabled:opacity-50"
                      >
                        В чёрный список
                      </button>
                      <button
                        onClick={() => { setBlacklistPrompt(false); setBlacklistReasonInput(''); }}
                        className="px-3 py-1.5 text-xs font-medium text-ink-500 hover:text-ink-800"
                      >
                        Отмена
                      </button>
                    </div>
                  </div>
                )}
                {!blacklistPrompt && relationshipError && (
                  <p className="mt-2 text-xs font-medium text-red-600">{relationshipError}</p>
                )}
                {!blacklistPrompt && supplier.relationship_status === 'blacklisted' && supplier.blacklist_reason && (
                  <p className="mt-2 text-xs text-ink-500">
                    Причина: <span className="text-ink-700">{issueReasonLabels[supplier.blacklist_reason] || supplier.blacklist_reason}</span>
                    {supplier.blacklisted_at && <> · {formatFullDate(supplier.blacklisted_at)}</>}
                  </p>
                )}
              </div>

              <div>
                <div className="text-xs font-medium text-ink-500 uppercase tracking-wider mb-2">Контакты</div>
                <div className="space-y-2">
                  {supplier.email && (
                    <div className="flex items-center gap-2.5 text-sm text-ink-700">
                      <Mail className="w-4 h-4 text-ink-400 shrink-0" />{supplier.email}
                    </div>
                  )}
                  {supplier.phone && (
                    <div className="flex items-center gap-2.5 text-sm text-ink-700">
                      <Phone className="w-4 h-4 text-ink-400 shrink-0" />{supplier.phone}
                    </div>
                  )}
                  <div className="flex items-center gap-2.5 text-sm text-ink-700">
                    <Globe className="w-4 h-4 text-ink-400 shrink-0" />
                    {supplier.site ? (
                      <a
                        href={supplier.site.startsWith('http') ? supplier.site : `https://${supplier.site}`}
                        target="_blank"
                        rel="noreferrer"
                        className="hover:text-accent-600 hover:underline"
                      >
                        {supplier.site}
                      </a>
                    ) : '—'}
                  </div>
                </div>
              </div>

              <div>
                <div className="text-xs font-medium text-ink-500 uppercase tracking-wider mb-2">Специализация</div>
                <div className="flex flex-wrap gap-1.5">
                  {supplier.categories.map((cat) => (
                    <span key={cat} className="px-2.5 py-1 rounded-lg text-xs font-medium bg-accent-50 text-accent-700 border border-accent-100">{cat}</span>
                  ))}
                  {supplier.categories.length === 0 && <span className="text-xs text-ink-400">Не указана</span>}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="bg-ink-50 rounded-xl px-4 py-3">
                  <div className="text-lg font-bold text-ink-900">{supplier.total_requests}</div>
                  <div className="text-xs text-ink-500">Всего заявок</div>
                </div>
                <div className="bg-ink-50 rounded-xl px-4 py-3">
                  <div className="text-lg font-bold text-ink-900">{supplier.total_requests > 0 ? `${supplier.response_rate}%` : '—'}</div>
                  <div className="text-xs text-ink-500">Отвечает %</div>
                </div>
                {supplier.avg_deal_rating != null && (
                  <div className="bg-ink-50 rounded-xl px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      <StarRating rating={Math.round(supplier.avg_deal_rating)} />
                      <span className="text-sm font-medium text-ink-800 ml-1">{supplier.avg_deal_rating.toFixed(1)}</span>
                    </div>
                    <div className="text-xs text-ink-500">Средняя оценка сделки</div>
                  </div>
                )}
                {supplier.avg_response_hours != null && (
                  <div className="bg-ink-50 rounded-xl px-4 py-3">
                    <div className="text-sm font-medium text-ink-800">
                      {supplier.avg_response_hours < 1 ? 'меньше часа' : `около ${Math.round(supplier.avg_response_hours)} ч`}
                    </div>
                    <div className="text-xs text-ink-500">Среднее время ответа</div>
                  </div>
                )}
              </div>

              <div>
                <div className="flex items-center gap-2 mb-2">
                  <StickyNote className="w-4 h-4 text-ink-400" />
                  <span className="text-xs font-medium text-ink-500 uppercase tracking-wider">Заметка</span>
                </div>
                {editingNote ? (
                  <div className="space-y-2">
                    <textarea
                      value={note}
                      onChange={(e) => setNote(e.target.value)}
                      rows={3}
                      autoFocus
                      className="w-full px-3 py-2 text-sm bg-white border border-ink-200 rounded-xl text-ink-800 focus:outline-none focus:ring-2 focus:ring-accent-200 focus:border-accent-400 resize-none"
                      placeholder="Добавьте заметку о поставщике…"
                    />
                    <div className="flex gap-2">
                      <button onClick={saveNote} className="px-3 py-1.5 text-xs font-medium text-white bg-accent-600 rounded-lg hover:bg-accent-700">Сохранить</button>
                      <button onClick={() => { setNote(supplier.note); setEditingNote(false); }} className="px-3 py-1.5 text-xs font-medium text-ink-500 hover:text-ink-800">Отмена</button>
                    </div>
                  </div>
                ) : (
                  <div
                    onClick={() => setEditingNote(true)}
                    className="px-3 py-2.5 text-sm bg-ink-50 rounded-xl text-ink-700 cursor-pointer hover:bg-ink-100 transition-colors min-h-[44px]"
                  >
                    {supplier.note || <span className="text-ink-400">Нажмите, чтобы добавить заметку…</span>}
                  </div>
                )}
              </div>

              <div>
                <div className="flex items-center gap-2 mb-3">
                  <History className="w-4 h-4 text-ink-400" />
                  <span className="text-xs font-medium text-ink-500 uppercase tracking-wider">История по заявкам</span>
                </div>
                {supplier.history.length === 0 ? (
                  <div className="text-sm text-ink-400 px-3 py-4 bg-ink-50 rounded-xl text-center">Коммуникации пока нет</div>
                ) : (
                  <div className="space-y-2">
                    {supplier.history.map((h) => (
                      <Link
                        key={h.request_id}
                        to={`/requests/${h.request_id}`}
                        className="flex items-center justify-between gap-3 px-3 py-2.5 bg-ink-50 rounded-xl hover:bg-accent-50 transition-colors group"
                      >
                        <div className="min-w-0">
                          <div className="text-sm font-medium text-ink-800 truncate group-hover:text-accent-700 transition-colors">{h.request_title}</div>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span className="text-xs text-ink-400 flex items-center gap-1"><Clock className="w-3 h-3" />{formatRelativeDate(h.date)}</span>
                            <span className="text-xs text-ink-400">·</span>
                            <span className="text-xs text-ink-500">{outcomeLabels[h.outcome] || h.outcome}</span>
                          </div>
                          {h.outcome === 'answered' && (
                            <div className="mt-1.5" onClick={(e) => e.preventDefault()}>
                              <StarRating rating={h.rating || 0} onChange={(n) => rateDeal(h.request_id, h.supplier_id, n)} />
                            </div>
                          )}
                        </div>
                        <ChevronRight className="w-4 h-4 text-ink-300 group-hover:text-accent-500 transition-colors shrink-0" />
                      </Link>
                    ))}
                  </div>
                )}
              </div>

              {supplier.issues.length > 0 && (
                <div>
                  <div className="flex items-center gap-2 mb-3">
                    <AlertCircle className="w-4 h-4 text-red-400" />
                    <span className="text-xs font-medium text-ink-500 uppercase tracking-wider">Сообщения о проблемах</span>
                  </div>
                  <div className="space-y-2">
                    {supplier.issues.map((issue, i) => (
                      <div key={i} className={`px-3 py-2.5 rounded-xl border ${issue.source === 'auto' ? 'bg-blue-50 border-blue-200' : 'bg-red-50 border-red-200'}`}>
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium text-ink-800">{issueReasonLabels[issue.reason] || issue.reason}</span>
                          {issue.source === 'auto' ? (
                            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-blue-100 text-blue-700">авто</span>
                          ) : (
                            <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-red-100 text-red-700">вручную</span>
                          )}
                          <span className="text-xs text-ink-400 ml-auto">{formatFullDate(issue.reported_at)}</span>
                        </div>
                        {issue.comment && <div className="text-xs text-ink-600 mt-1">{issue.comment}</div>}
                        {issue.correct_inn && <div className="text-xs text-ink-500 mt-1">Правильный ИНН: {issue.correct_inn}</div>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <button
                onClick={() => setShowIssue(true)}
                className="inline-flex items-center gap-1.5 text-xs font-medium text-ink-400 hover:text-ink-700 transition-colors"
              >
                <AlertCircle className="w-3.5 h-3.5" />Сообщить о проблеме
              </button>
            </div>
          </>
        )}
      </aside>
      {showIssue && <IssueModal onClose={() => setShowIssue(false)} onSubmit={submitIssue} />}
    </>
  );
}
