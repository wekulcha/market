import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { adminApi } from '../../api/admin';
import { Badge, Button, Card, Field, LoadingPanel, Notice, PageHeader, SelectField, StatePanel, TextAreaField } from '../../components/ui';
import type { ModerationOffer } from '../../types/domain';
import { formatMoneyKopecks, kopecksToRublesInput, quantityText, rublesInputToKopecks, UNIT_LABELS } from '../../utils/format';

function ModerationDetails({ offer }: { offer: ModerationOffer }) {
  const client = useQueryClient();
  const [markupType, setMarkupType] = useState<ModerationOffer['markupType']>(offer.markupType || 'PERCENT');
  const [markupValue, setMarkupValue] = useState(() => {
    if (offer.markupType === 'PERCENT') return offer.markupValue == null ? '' : String(offer.markupValue);
    if (offer.markupType === 'FIXED') return kopecksToRublesInput(offer.fixedMarkupKopecks);
    return kopecksToRublesInput(offer.manualBuyerUnitPriceKopecks);
  });
  const [reason, setReason] = useState(offer.internalComment ?? '');
  const numericMarkup = markupType === 'PERCENT' ? Number(markupValue) : rublesInputToKopecks(markupValue);
  const previewKopecks = useMemo(() => {
    if (numericMarkup == null || !Number.isFinite(numericMarkup)) return null;
    if (markupType === 'PERCENT') return Math.round(offer.procurementUnitPriceKopecks * (1 + numericMarkup / 100));
    if (markupType === 'FIXED') return offer.procurementUnitPriceKopecks + numericMarkup;
    return numericMarkup;
  }, [markupType, numericMarkup, offer.procurementUnitPriceKopecks]);
  const invalidate = () => client.invalidateQueries({ queryKey: ['admin', 'moderation'] });
  const pricing = useMutation({
    mutationFn: () => adminApi.priceOffer(offer.id, {
      markupType,
      markupPercent: markupType === 'PERCENT' && Number.isFinite(numericMarkup) ? numericMarkup : null,
      fixedMarkupKopecks: markupType === 'FIXED' ? numericMarkup : null,
      manualBuyerUnitPriceKopecks: markupType === 'MANUAL' ? numericMarkup : null,
    }),
    onSuccess: invalidate,
  });
  const decision = useMutation({
    mutationFn: (value: 'APPROVE' | 'REJECT' | 'REQUEST_CHANGES') => adminApi.moderateOffer(offer.id, { decision: value, reason: reason.trim() || null }),
    onSuccess: invalidate,
  });
  const publish = useMutation({ mutationFn: () => adminApi.publishOffer(offer.id), onSuccess: invalidate });
  return (
    <div className="moderation-grid">
      <div className="stack">
        <Card>
          <div className="list-row">
            <div className="list-row__main"><strong>{offer.name}</strong><span>{offer.sellerDisplayName} · {offer.category}</span></div>
            <Badge tone="warning">{offer.status}</Badge>
          </div>
          <p>{offer.description || 'Описание не заполнено.'}</p>
          <div className="grid grid--3">
            <div><span className="muted tiny">Цена поставщика</span><div className="price">{formatMoneyKopecks(offer.procurementUnitPriceKopecks)} <small>/ {UNIT_LABELS[offer.unit]}</small></div></div>
            <div><span className="muted tiny">Доступно</span><div className="price">{quantityText(offer.availableQuantity, offer.unit)}</div></div>
            <div><span className="muted tiny">Минимум</span><div className="price">{quantityText(offer.minimumQuantity, offer.unit)}</div></div>
          </div>
          {offer.photos.length > 0 && <div className="grid grid--3" style={{ marginTop: 16 }}>{offer.photos.map((photo) => <img src={photo} alt={offer.name} loading="lazy" key={photo} style={{ aspectRatio: '4 / 3', width: '100%', objectFit: 'cover', borderRadius: 12 }} />)}</div>}
          <div className="list" style={{ marginTop: 16 }}>
            <div className="list-row"><span>Упаковка</span><strong>{offer.packageSize || '—'}</strong></div>
            <div className="list-row"><span>Срок годности</span><strong>{offer.shelfLife || '—'}</strong></div>
            <div className="list-row"><span>Хранение</span><strong>{offer.storageConditions || '—'}</strong></div>
          </div>
        </Card>
      </div>
      <Card className="sticky-card form-grid">
        <h2>Цена и решение</h2>
        <SelectField label="Тип наценки" value={markupType} onChange={(event) => { setMarkupType(event.target.value as ModerationOffer['markupType']); setMarkupValue(''); }}>
          <option value="PERCENT">Процент</option><option value="FIXED">Фиксированная сумма</option><option value="MANUAL">Конечная цена вручную</option>
        </SelectField>
        <Field label={markupType === 'PERCENT' ? 'Наценка, %' : markupType === 'FIXED' ? 'Наценка, ₽' : 'Цена покупателя, ₽'} inputMode="decimal" value={markupValue} onChange={(event) => setMarkupValue(event.target.value)} />
        <Notice tone={previewKopecks != null ? 'success' : 'warning'}>Цена покупателя: <strong>{formatMoneyKopecks(previewKopecks)}</strong></Notice>
        {offer.status === 'SUBMITTED' && <Notice tone="info">Сначала одобрите предложение, затем сохраните цену и опубликуйте.</Notice>}
        <Button
          variant="secondary"
          busy={pricing.isPending}
          disabled={previewKopecks == null || !['APPROVED', 'UNDER_REVIEW'].includes(offer.status)}
          onClick={() => pricing.mutate()}
        >
          Сохранить цену
        </Button>
        <TextAreaField label="Комментарий / причина отклонения" value={reason} onChange={(event) => setReason(event.target.value)} />
        <div className="button-row">
          <Button busy={decision.isPending && decision.variables === 'APPROVE'} disabled={offer.status === 'APPROVED'} onClick={() => decision.mutate('APPROVE')}>Одобрить</Button>
          <Button variant="secondary" busy={decision.isPending && decision.variables === 'REQUEST_CHANGES'} disabled={!reason.trim()} onClick={() => decision.mutate('REQUEST_CHANGES')}>На доработку</Button>
          <Button variant="danger" busy={decision.isPending && decision.variables === 'REJECT'} disabled={!reason.trim()} onClick={() => decision.mutate('REJECT')}>Отклонить</Button>
        </div>
        <Button variant="ghost" busy={publish.isPending} disabled={offer.status !== 'APPROVED' || offer.proposedBuyerUnitPriceKopecks == null} onClick={() => publish.mutate()}>Опубликовать</Button>
        {(pricing.error || decision.error || publish.error) && <Notice tone="danger">Действие не выполнено. Обновите очередь и проверьте статус.</Notice>}
      </Card>
    </div>
  );
}

export function ModerationPage() {
  const offers = useQuery({ queryKey: ['admin', 'moderation'], queryFn: adminApi.moderationOffers });
  const [selectedId, setSelectedId] = useState<string | null>(null);
  if (offers.isLoading) return <LoadingPanel />;
  if (offers.error) return <StatePanel icon="!" title="Очередь не загрузилась" action={<Button onClick={() => void offers.refetch()}>Повторить</Button>} />;
  const items = offers.data?.items ?? [];
  const selected = items.find((offer) => offer.id === selectedId) ?? items[0];
  return (
    <div className="stack stack--lg">
      <PageHeader eyebrow="Контроль публикации" title="Модерация предложений" description="Проверьте товар, задайте конечную цену и зафиксируйте решение." />
      {items.length === 0 && <StatePanel title="Очередь пуста" description="Новые предложения поставщиков появятся здесь." />}
      {items.length > 1 && <div className="filter-row">{items.map((offer) => <button type="button" className={`filter-chip${selected?.id === offer.id ? ' is-active' : ''}`} onClick={() => setSelectedId(offer.id)} key={offer.id}>{offer.name}</button>)}</div>}
      {selected && <ModerationDetails key={selected.id} offer={selected} />}
    </div>
  );
}
