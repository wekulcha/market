import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { adminApi } from '../../api/admin';
import { Button, Card, LoadingPanel, Metric, PageHeader, StatePanel } from '../../components/ui';
import { formatMoneyKopecks } from '../../utils/format';

export function DashboardPage() {
  const dashboard = useQuery({ queryKey: ['admin', 'dashboard'], queryFn: adminApi.dashboard });
  const moderation = useQuery({ queryKey: ['admin', 'moderation'], queryFn: adminApi.moderationOffers });
  const orders = useQuery({ queryKey: ['admin', 'orders', 1, ''], queryFn: () => adminApi.orders(1) });
  if (dashboard.isLoading) return <LoadingPanel label="Собираем показатели…" />;
  if (dashboard.error || !dashboard.data) return <StatePanel icon="!" title="Dashboard не загрузился" action={<Button onClick={() => void dashboard.refetch()}>Повторить</Button>} />;
  const kpi = dashboard.data;
  return (
    <div className="stack stack--lg">
      <PageHeader eyebrow="Операционный центр" title="Dashboard" description="Продажи, подписки, остатки и задачи, требующие внимания." />
      <div className="admin-metrics">
        <Metric label="Новые предложения" value={kpi.pendingOffers} hint="ожидают модерации" />
        <Metric label="Активные товары" value={kpi.activeOffers} />
        <Metric label="Стоимость остатка" value={formatMoneyKopecks(kpi.inventoryValueKopecks)} />
        <Metric label="Новые заказы" value={kpi.newOrders} />
        <Metric label="GMV" value={formatMoneyKopecks(kpi.gmvKopecks)} />
        <Metric label="Доход от наценки" value={formatMoneyKopecks(kpi.markupRevenueKopecks)} />
        <Metric label="MRR подписок" value={formatMoneyKopecks(kpi.mrrKopecks)} />
        <Metric label="Подписчики" value={kpi.activeSubscribers} />
        <Metric label="Низкий остаток" value={kpi.lowStockOffers} />
        <Metric label="Требуют внимания" value={kpi.ordersRequiringAttention} />
      </div>
      <div className="admin-grid">
        <Card>
          <div className="section-title"><h2>Очередь модерации</h2><Link to="/admin/moderation">Открыть все</Link></div>
          {(moderation.data?.items ?? []).slice(0, 5).map((offer) => (
            <div className="list-row" key={offer.id}>
              <div className="list-row__main"><strong>{offer.name}</strong><span>{offer.sellerDisplayName} · {offer.category}</span></div>
              <strong>{formatMoneyKopecks(offer.procurementUnitPriceKopecks)}</strong>
            </div>
          ))}
          {!moderation.isLoading && (moderation.data?.items.length ?? 0) === 0 && <p className="muted tiny">Очередь пуста.</p>}
        </Card>
        <Card>
          <div className="section-title"><h2>Последние заказы</h2><Link to="/admin/orders">Все заказы</Link></div>
          {(orders.data?.items ?? []).slice(0, 5).map((order) => (
            <div className="list-row" key={order.id}>
              <div className="list-row__main"><strong>{order.title}</strong><span>{order.subtitle}</span></div>
              <span>{order.status}</span>
            </div>
          ))}
          {!orders.isLoading && (orders.data?.items.length ?? 0) === 0 && <p className="muted tiny">Заказов пока нет.</p>}
        </Card>
      </div>
    </div>
  );
}
