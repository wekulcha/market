import { useState, type ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '../../api/admin';
import { Badge, Button, Card, Field, LoadingPanel, Notice, PageHeader, SelectField, StatePanel, TextAreaField } from '../../components/ui';
import type { AdminListItem, ApiList } from '../../types/domain';
import { formatDateTime, formatMoneyKopecks } from '../../utils/format';

type ResourceLoader = (page: number, search: string) => Promise<ApiList<AdminListItem>>;

function resourceTone(status: string): 'neutral' | 'success' | 'warning' | 'danger' | 'info' {
  const upper = status.toUpperCase();
  if (['ACTIVE', 'VERIFIED', 'PUBLISHED', 'COMPLETED', 'DELIVERED', 'SENT'].includes(upper)) return 'success';
  if (['BLOCKED', 'REJECTED', 'CANCELED', 'EXPIRED', 'FAILED'].includes(upper)) return 'danger';
  if (['PENDING', 'SUBMITTED', 'UNDER_REVIEW', 'RESERVED'].includes(upper)) return 'warning';
  return 'info';
}

function ResourceTable({
  resource,
  title,
  description,
  loader,
  action,
  renderRowAction,
}: {
  resource: string;
  title: string;
  description: string;
  loader: ResourceLoader;
  action?: ReactNode;
  renderRowAction?: (item: AdminListItem) => ReactNode;
}) {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const query = useQuery({ queryKey: ['admin', resource, page, search], queryFn: () => loader(page, search) });
  if (query.isLoading) return <LoadingPanel />;
  if (query.error) return <StatePanel icon="!" title={`${title}: ошибка загрузки`} action={<Button onClick={() => void query.refetch()}>Повторить</Button>} />;
  const items = query.data?.items ?? [];
  const pageSize = query.data?.pageSize || 20;
  const total = query.data?.total || 0;
  return (
    <div className="stack">
      <PageHeader title={title} description={description} action={action} />
      <Field label="Поиск" type="search" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="ID, название, телефон или статус" />
      {items.length === 0 ? <StatePanel title="Ничего не найдено" description="Измените запрос или дождитесь новых данных." /> : (
        <div className="table-wrap">
          <table className="data-table">
            <thead><tr><th>Объект</th><th>Статус</th><th>Сумма</th><th>Создано</th>{renderRowAction && <th>Действие</th>}</tr></thead>
            <tbody>{items.map((item) => (
              <tr key={item.id}>
                <td><strong>{item.title}</strong><br /><span className="muted tiny">{item.subtitle || `ID ${item.id}`}</span></td>
                <td><Badge tone={resourceTone(item.status)}>{item.status}</Badge></td>
                <td>{formatMoneyKopecks(item.amountKopecks)}</td>
                <td>{formatDateTime(item.createdAt)}</td>
                {renderRowAction && <td>{renderRowAction(item)}</td>}
              </tr>
            ))}</tbody>
          </table>
        </div>
      )}
      {total > pageSize && <div className="pagination"><Button size="sm" variant="ghost" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Назад</Button><Badge>Страница {page}</Badge><Button size="sm" variant="ghost" disabled={page * pageSize >= total} onClick={() => setPage((value) => value + 1)}>Далее</Button></div>}
    </div>
  );
}

export function AdminCatalogPage() {
  const client = useQueryClient();
  const publish = useMutation({ mutationFn: adminApi.publishOffer, onSuccess: () => client.invalidateQueries({ queryKey: ['admin', 'offers'] }) });
  return <ResourceTable resource="offers" title="Опубликованные товары" description="Управление предложениями после модерации." loader={adminApi.offers} renderRowAction={(item) => item.status === 'APPROVED' ? <Button size="sm" busy={publish.isPending && publish.variables === item.id} onClick={() => { if (window.confirm('Опубликовать предложение в каталоге покупателей?')) publish.mutate(item.id); }}>Опубликовать</Button> : null} />;
}

export function SellersPage() {
  const client = useQueryClient();
  const statusMutation = useMutation({
    mutationFn: ({ id, status, reason }: { id: string; status: 'VERIFIED' | 'SUSPENDED'; reason: string }) => adminApi.setSellerStatus(id, status, reason),
    onSuccess: () => client.invalidateQueries({ queryKey: ['admin', 'sellers'] }),
  });
  return <ResourceTable resource="sellers" title="Поставщики" description="Проверка профилей и контроль статуса поставщиков." loader={adminApi.sellers} renderRowAction={(item) => {
    const next = item.status === 'VERIFIED' ? 'SUSPENDED' : 'VERIFIED';
    const label = next === 'VERIFIED' ? 'Подтвердить' : 'Приостановить';
    const reason = next === 'VERIFIED' ? 'Профиль проверен администратором' : 'Доступ приостановлен администратором';
    return <Button size="sm" variant={next === 'VERIFIED' ? 'primary' : 'secondary'} busy={statusMutation.isPending && statusMutation.variables?.id === item.id} onClick={() => { if (window.confirm(`${label} поставщика «${item.title}»?`)) statusMutation.mutate({ id: item.id, status: next, reason }); }}>{label}</Button>;
  }} />;
}

export function BuyersPage() {
  return <ResourceTable resource="buyers" title="Покупатели" description="B2B-клиенты, компании и состояние доступа." loader={adminApi.buyers} />;
}

export function SubscriptionsPage() {
  const client = useQueryClient();
  const [buyerId, setBuyerId] = useState('');
  const [status, setStatus] = useState('ACTIVE');
  const [expiresAt, setExpiresAt] = useState('');
  const [reason, setReason] = useState('');
  const override = useMutation({
    mutationFn: () => adminApi.overrideSubscription({ buyerId: buyerId.trim(), status, expiresAt: new Date(expiresAt).toISOString(), reason: reason.trim() }),
    onSuccess: () => { void client.invalidateQueries({ queryKey: ['admin', 'subscriptions'] }); setBuyerId(''); setReason(''); },
  });
  const form = (
    <Card className="form-grid" style={{ minWidth: 300 }}>
      <h2>Ручное изменение</h2>
      <Field label="Buyer ID" value={buyerId} onChange={(event) => setBuyerId(event.target.value)} />
      <SelectField label="Статус" value={status} onChange={(event) => setStatus(event.target.value)}><option>ACTIVE</option><option>EXPIRED</option><option>PAST_DUE</option></SelectField>
      <Field label="Действует до" type="datetime-local" value={expiresAt} onChange={(event) => setExpiresAt(event.target.value)} />
      <TextAreaField label="Причина" value={reason} onChange={(event) => setReason(event.target.value)} />
      <Button size="sm" busy={override.isPending} disabled={!buyerId.trim() || !expiresAt || !reason.trim()} onClick={() => { if (window.confirm('Применить ручное изменение подписки?')) override.mutate(); }}>Применить</Button>
      {override.error && <Notice tone="danger">Не удалось изменить подписку.</Notice>}
    </Card>
  );
  return <ResourceTable resource="subscriptions" title="Подписки и платежи" description="Активность тарифов и контролируемые ручные overrides." loader={adminApi.subscriptions} action={form} />;
}

export function AdminOrdersPage() {
  const client = useQueryClient();
  const [orderId, setOrderId] = useState('');
  const [status, setStatus] = useState('CONFIRMED');
  const [comment, setComment] = useState('');
  const transition = useMutation({
    mutationFn: () => adminApi.transitionOrder(orderId.trim(), status, comment.trim() || null),
    onSuccess: () => { void client.invalidateQueries({ queryKey: ['admin', 'orders'] }); setComment(''); },
  });
  const form = <Card className="form-grid" style={{ minWidth: 300 }}><h2>Сменить статус</h2><Field label="Order ID" value={orderId} onChange={(event) => setOrderId(event.target.value)} /><SelectField label="Новый статус" value={status} onChange={(event) => setStatus(event.target.value)}>{['CONFIRMED', 'SELLER_PREPARING', 'READY_FOR_PICKUP', 'COURIER_ASSIGNED', 'PICKED_UP', 'IN_DELIVERY', 'DELIVERED', 'COMPLETED', 'CANCELED', 'REFUNDED'].map((value) => <option key={value}>{value}</option>)}</SelectField><TextAreaField label="Комментарий" value={comment} onChange={(event) => setComment(event.target.value)} /><Button size="sm" busy={transition.isPending} disabled={!orderId.trim()} onClick={() => { if (window.confirm(`Перевести заказ в статус ${status}?`)) transition.mutate(); }}>Выполнить переход</Button>{transition.error && <Notice tone="danger">Переход запрещён текущим состоянием заказа.</Notice>}</Card>;
  return <ResourceTable resource="orders" title="Заказы" description="Контроль state machine и коммерческих итогов." loader={adminApi.orders} action={form} />;
}

export function DeliveryPage() {
  const client = useQueryClient();
  const [orderId, setOrderId] = useState('');
  const [courierName, setCourierName] = useState('');
  const [pickupWindow, setPickupWindow] = useState('');
  const [deliveryWindow, setDeliveryWindow] = useState('');
  const create = useMutation({ mutationFn: () => adminApi.createDelivery({ orderId: orderId.trim(), courierName: courierName.trim(), pickupWindow, deliveryWindow }), onSuccess: () => client.invalidateQueries({ queryKey: ['admin', 'deliveries'] }) });
  const advance = useMutation({
    mutationFn: ({ id, status }: { id: string; status: 'PICKED_UP' | 'IN_DELIVERY' | 'DELIVERED' }) => adminApi.updateDeliveryStatus(id, status),
    onSuccess: () => client.invalidateQueries({ queryKey: ['admin', 'deliveries'] }),
  });
  const nextStatus = (status: string): 'PICKED_UP' | 'IN_DELIVERY' | 'DELIVERED' | null => {
    const value = ({
      ASSIGNED: 'PICKED_UP',
      PICKED_UP: 'IN_DELIVERY',
      IN_DELIVERY: 'DELIVERED',
    } as Record<string, 'PICKED_UP' | 'IN_DELIVERY' | 'DELIVERED'>)[status];
    return value ?? null;
  };
  const form = <Card className="form-grid" style={{ minWidth: 320 }}><h2>Назначить доставку</h2><Field label="Order ID" value={orderId} onChange={(event) => setOrderId(event.target.value)} /><Field label="Курьер / служба" value={courierName} onChange={(event) => setCourierName(event.target.value)} /><Field label="Окно забора" value={pickupWindow} onChange={(event) => setPickupWindow(event.target.value)} placeholder="10:00–11:00" /><Field label="Окно доставки" value={deliveryWindow} onChange={(event) => setDeliveryWindow(event.target.value)} placeholder="12:00–14:00" /><Button size="sm" busy={create.isPending} disabled={!orderId || !courierName || !pickupWindow || !deliveryWindow} onClick={() => create.mutate()}>Создать маршрут</Button>{create.error && <Notice tone="danger">Маршрут не создан.</Notice>}</Card>;
  return <ResourceTable resource="deliveries" title="Доставка и диспетчеризация" description="Забор у поставщика и доставка покупателю." loader={adminApi.deliveries} action={form} renderRowAction={(item) => {
    const status = nextStatus(item.status);
    return status ? <Button size="sm" busy={advance.isPending && advance.variables?.id === item.id} onClick={() => { if (window.confirm(`Перевести доставку в статус ${status}?`)) advance.mutate({ id: item.id, status }); }}>{status}</Button> : null;
  }} />;
}

export function InvitesPage() {
  const client = useQueryClient();
  const [label, setLabel] = useState('');
  const [expiresInDays, setExpiresInDays] = useState('7');
  const invite = useMutation({
    mutationFn: () => adminApi.createInvite({ label: label.trim(), expiresInDays: Number(expiresInDays) }),
    onSuccess: () => { void client.invalidateQueries({ queryKey: ['admin', 'invites'] }); setLabel(''); },
  });
  const form = <Card className="form-grid" style={{ minWidth: 320 }}><h2>Новое приглашение</h2><Field label="Метка" value={label} onChange={(event) => setLabel(event.target.value)} placeholder="Кафе на Лесной" /><Field label="Срок, дней" type="number" min="1" max="90" value={expiresInDays} onChange={(event) => setExpiresInDays(event.target.value)} /><Button size="sm" busy={invite.isPending} disabled={!label.trim()} onClick={() => invite.mutate()}>Создать ссылку</Button>{invite.data && <Notice tone="success"><strong>Ссылка готова</strong><br /><a className="text-link" href={invite.data.deepLink} target="_blank" rel="noreferrer">{invite.data.deepLink}</a><br /><span className="tiny">До {formatDateTime(invite.data.expiresAt)}</span></Notice>}{invite.error && <Notice tone="danger">Приглашение не создано.</Notice>}</Card>;
  return <ResourceTable resource="invites" title="Приглашения покупателей" description="Персональные одноразовые ссылки с ограниченным сроком." loader={adminApi.invites} action={form} />;
}

export function NotificationsPage() {
  return <ResourceTable resource="notifications" title="Уведомления" description="История событий buyer-, seller- и admin-ботов." loader={adminApi.notifications} />;
}

export function AuditPage() {
  return <ResourceTable resource="audit" title="Audit log" description="Критические действия, актор, время и контекст изменения." loader={adminApi.audit} />;
}

export function SettingsPage() {
  const client = useQueryClient();
  const settings = useQuery({ queryKey: ['admin', 'settings'], queryFn: adminApi.settings });
  if (settings.isLoading) return <LoadingPanel />;
  if (settings.error || !settings.data) return <StatePanel icon="!" title="Настройки не загрузились" action={<Button onClick={() => void settings.refetch()}>Повторить</Button>} />;
  return <SettingsForm key={JSON.stringify(settings.data)} initial={settings.data} onSaved={(value) => client.setQueryData(['admin', 'settings'], value)} />;
}

function SettingsForm({ initial, onSaved }: { initial: Record<string, string | number | boolean>; onSaved: (value: Record<string, string | number | boolean>) => void }) {
  const [appName, setAppName] = useState(String(initial.appName ?? 'KULCHA B2B'));
  const [catalogAccessPolicy, setCatalogAccessPolicy] = useState(String(initial.catalogAccessPolicy ?? 'TEASER'));
  const [reservationTtlMinutes, setReservationTtlMinutes] = useState(String(initial.reservationTtlMinutes ?? 30));
  const [timezone, setTimezone] = useState(String(initial.timezone ?? 'Europe/Moscow'));
  const save = useMutation({
    mutationFn: () => adminApi.updateSettings({ appName, catalogAccessPolicy, reservationTtlMinutes: Number(reservationTtlMinutes), timezone }),
    onSuccess: onSaved,
  });
  return <div className="stack"><PageHeader title="Настройки" description="Публичное имя, политика каталога и операционные параметры." /><Card className="form-grid"><Field label="Название продукта" value={appName} onChange={(event) => setAppName(event.target.value)} /><SelectField label="Доступ без подписки" value={catalogAccessPolicy} onChange={(event) => setCatalogAccessPolicy(event.target.value)}><option>BLOCKED</option><option>TEASER</option><option>READ_ONLY</option></SelectField><Field label="TTL резерва, минут" type="number" min="5" value={reservationTtlMinutes} onChange={(event) => setReservationTtlMinutes(event.target.value)} /><Field label="Timezone" value={timezone} onChange={(event) => setTimezone(event.target.value)} /><Notice tone="info">Секреты и bot tokens не редактируются через браузер.</Notice></Card>{save.isSuccess && <Notice tone="success">Настройки сохранены.</Notice>}{save.error && <Notice tone="danger">Не удалось сохранить настройки.</Notice>}<Button busy={save.isPending} onClick={() => save.mutate()}>Сохранить</Button></div>;
}
