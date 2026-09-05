import type { RequestDetail, RequestListItem, Supplier } from '@/lib/types';

const isExplicitPreviewRoute = typeof window !== 'undefined' && window.location.pathname.startsWith('/preview/');

export const isUiPreviewMode = import.meta.env.DEV && (import.meta.env.VITE_UI_PREVIEW_MODE === 'true' || isExplicitPreviewRoute);

const requestNames = [
  'Комплектующие для промышленного шкафа управления насосной станцией',
  'Поставка кабельной продукции и монтажных материалов для объекта',
  'Запасные части для компрессорного оборудования',
  'Металлопрокат по спецификации проекта Северный поток',
  'Светильники, прожекторы и аварийное освещение складского комплекса',
  'Комплект автоматики для вентиляционной установки',
  'Трубы и соединительные детали для технологического трубопровода',
  'Средства индивидуальной защиты для производственной площадки',
  'Подшипники и ремни для ремонтной программы на 2026 год',
  'Материалы для капитального ремонта административного корпуса',
];

const statusByIndex: RequestListItem['status'][] = ['completed', 'searching', 'error', 'updating', 'draft'];

function dateFromNow(days: number): string {
  return new Date(Date.now() + days * 86400000).toISOString();
}

function makeRequest(index: number): RequestListItem {
  const status = statusByIndex[index % statusByIndex.length];
  const positions = 3 + ((index * 7) % 27);
  const suppliers = status === 'draft' ? 0 : 12 + ((index * 13) % 164);
  const replies = status === 'completed' ? Math.min(suppliers, 4 + ((index * 3) % 24)) : Math.min(suppliers, index % 7);
  return {
    id: 2400 + index,
    name: `${requestNames[index % requestNames.length]}${index > 9 ? ` — этап ${Math.ceil(index / 10)}` : ''}`,
    description: index % 3 === 0 ? 'Заявка собрана по рабочей спецификации отдела снабжения.' : null,
    deadline: index % 6 === 0 ? '' : dateFromNow(index % 8 === 0 ? -2 : 4 + (index % 31)),
    sender_name: index % 2 === 0 ? 'Анна Петрова' : 'Михаил Соколов',
    company_name: 'ООО «Северная производственная группа»',
    created_at: dateFromNow(-(index + 2)),
    status,
    search_progress: status === 'searching' || status === 'updating' ? Math.min(suppliers, Math.floor(suppliers * 0.64)) : suppliers,
    search_total: suppliers,
    search_depth: 2 + (index % 3),
    last_error: status === 'error' ? 'Часть источников не ответила вовремя. Проверьте найденных поставщиков.' : null,
    updated_at: dateFromNow(-((index % 4) + 1)),
    positions_count: positions,
    suppliers_count: suppliers,
    sent_count: status === 'draft' ? 0 : Math.floor(suppliers * 0.48),
    replies_count: replies,
    mail_metrics: { outbound_total: Math.floor(suppliers * 0.48), queued: index % 4, accepted: Math.floor(suppliers * 0.4), accepted_effective: Math.floor(suppliers * 0.35), failed: index % 5 === 0 ? 2 : 0, delivery_unknown: index % 6 === 0 ? 1 : 0, bounced: index % 7 === 0 ? 1 : 0, cancelled: 0, replies },
  };
}

export const previewRequests: RequestListItem[] = Array.from({ length: 42 }, (_, index) => makeRequest(index));

const longPositionNames = [
  'Шкаф управления насосной станцией, напольный, IP54, с автоматическим вводом резерва и комплектом маркировки кабелей',
  'Контактор вакуумный трехполюсный для коммутации электродвигателей в шкафу автоматизации, исполнение для тяжелого режима',
  'Кабель силовой медный с изоляцией из сшитого полиэтилена, 4х120 мм², класс пожарной опасности и температурный диапазон по ТУ',
  'Преобразователь частоты с встроенным дросселем постоянного тока, панелью оператора и интерфейсом промышленной сети',
  'Комплект крепежа оцинкованный для установки оборудования на металлоконструкции, включая шайбы, гайки и монтажный инструмент',
  'Датчик давления мембранный с местной индикацией, резьбовым присоединением и протоколом заводской поверки',
  'Теплоизоляция трубопроводов из минеральной ваты в защитной оболочке для наружного монтажа на технологической эстакаде',
  'Светильник промышленный светодиодный взрывозащищенный с аварийным блоком питания и кабельным вводом',
];

function makeSupplier(index: number): Supplier {
  const states: Supplier['mail_status'][] = ['answered', 'waiting', 'sent', 'error', 'delivery_unknown', 'not_sent'];
  const status = states[index % states.length];
  const response = status === 'answered' ? 'answered' : status === 'waiting' ? 'waiting' : 'none';
  const delivery = status === 'error' ? 'failed' : status === 'delivery_unknown' ? 'delivery_unknown' : status === 'not_sent' ? 'not_sent' : status === 'sent' ? 'queued' : 'accepted';
  return {
    id: 8800 + index,
    external_key: `preview-supplier-${index}`,
    name: ['ООО «ПромКомплект Северо-Запад»', 'АО «ТехноЭнергоСнаб»', 'ООО «Инженерные системы и решения»', 'ЗАО «Региональная металлоторговая компания»', 'ООО «ЭлектроКомплект Монтаж»', 'ООО «Промышленная автоматика»', 'АО «Снабжение и логистика»', 'ООО «Вектор Производство»', 'ООО «Стандарт-Ресурс»', 'ООО «Городской технический центр»'][index],
    email: index === 5 ? null : `sales${index + 1}@supplier-${index + 1}.ru`,
    host: `supplier-${index + 1}.ru`,
    inn: `7812${String(340000 + index * 917).padStart(6, '0')}`,
    kind: 'organization', region: index % 2 ? 'Санкт-Петербург' : 'Москва', role: 'Поставщик', phone: '+7 (495) 000-00-00',
    reason: index % 3 === 0 ? 'Найден по названию позиции и региону' : 'Совпадение по отраслевому профилю',
    source: 'Поиск поставщиков', found_url: `https://supplier-${index + 1}.ru/catalog`,
    covers: longPositionNames.slice(index % 3, (index % 3) + 2), position_keys: longPositionNames.slice(index % 3, (index % 3) + 2).map((_, itemIndex) => `position-${(index + itemIndex) % 24}`),
    site_unavailable: index === 8 ? 1 : 0, mail_status: status, delivery_status: delivery, response_status: response,
    delivery_counts: { not_sent: status === 'not_sent' ? 1 : 0, queued: status === 'sent' ? 1 : 0, accepted: ['answered', 'waiting'].includes(status) ? 1 : 0, failed: status === 'error' ? 1 : 0, delivery_unknown: status === 'delivery_unknown' ? 1 : 0, bounced: 0, cancelled: 0 },
    delivery_issue_resolved: false, last_error: status === 'error' ? 'Почтовый сервер получателя временно недоступен' : null,
    registry: null, finances: null, global_supplier_id: null, risks: index === 3 ? ['Юридический адрес изменён недавно'] : [], unread_count: status === 'answered' ? index % 4 + 1 : 0,
    contacts: [], contact_emails: index === 5 ? [] : [`sales${index + 1}@supplier-${index + 1}.ru`], contact_sites: [`supplier-${index + 1}.ru`], site_count: 1, email_count: index === 5 ? 0 : 1, unsent_contact_count: status === 'not_sent' ? 1 : 0, related_supplier_ids: [],
  };
}

export const previewDetail: RequestDetail = {
  request: previewRequests[1],
  positions: Array.from({ length: 24 }, (_, index) => ({ id: 9700 + index, request_id: previewRequests[1].id, position_key: `position-${index}`, name: longPositionNames[index % longPositionNames.length], quantity: `${(index + 1) * 5} ${index % 3 === 0 ? 'шт.' : index % 3 === 1 ? 'м' : 'компл.'}`, created_at: dateFromNow(-3) })),
  items: Array.from({ length: 10 }, (_, index) => makeSupplier(index)),
  mail_metrics: { outbound_total: 7, queued: 1, accepted: 5, accepted_effective: 4, failed: 1, delivery_unknown: 1, bounced: 0, cancelled: 0, replies: 3 },
};

export function previewDetailFor(id: number): RequestDetail {
  return id === previewDetail.request.id ? previewDetail : { ...previewDetail, request: previewRequests.find((request) => request.id === id) ?? previewDetail.request };
}

export const previewUser = { email: 'preview@supplydesk.local', display_name: 'Анна Петрова', workspace_name: 'ООО «Северная производственная группа»' };
