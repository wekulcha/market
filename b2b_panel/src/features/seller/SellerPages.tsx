import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { sellerApi, type SellerOfferInput } from '../../api/seller';
import {
  Badge,
  Button,
  Card,
  Field,
  LoadingPanel,
  Notice,
  PageHeader,
  SelectField,
  StatePanel,
  TextAreaField,
} from '../../components/ui';
import type {
  BuyerOrderStatus,
  QuantityUnit,
  SellerOffer,
  SellerOfferStatus,
  SellerProfile,
  SellerVerificationStatus,
} from '../../types/domain';
import {
  formatDateTime,
  formatMoneyKopecks,
  kopecksToRublesInput,
  quantityText,
  rublesInputToKopecks,
  UNIT_LABELS,
} from '../../utils/format';

const VERIFICATION_LABELS: Record<SellerVerificationStatus, string> = {
  PENDING: 'На проверке',
  VERIFIED: 'Поставщик проверен',
  SUSPENDED: 'Доступ приостановлен',
  BLOCKED: 'Поставщик заблокирован',
};

const OFFER_LABELS: Record<SellerOfferStatus, string> = {
  DRAFT: 'Черновик',
  SUBMITTED: 'Отправлено',
  UNDER_REVIEW: 'На модерации',
  CHANGES_REQUESTED: 'Нужны изменения',
  REJECTED: 'Отклонено',
  APPROVED: 'Одобрено',
  PUBLISHED: 'Опубликовано',
  PAUSED: 'Приостановлено',
  SOLD_OUT: 'Распродано',
  EXPIRED: 'Истекло',
  ARCHIVED: 'В архиве',
};

const ORDER_LABELS: Partial<Record<BuyerOrderStatus, string>> = {
  PENDING_CONFIRMATION: 'Нужно подтвердить',
  CONFIRMED: 'Подтверждено',
  SELLER_PREPARING: 'Готовится',
  READY_FOR_PICKUP: 'Готово к забору',
  PICKED_UP: 'Передано курьеру',
  CANCELED: 'Отменено',
};

function tone(status: string): 'neutral' | 'success' | 'warning' | 'danger' | 'info' {
  if (['VERIFIED', 'PUBLISHED', 'READY_FOR_PICKUP'].includes(status)) return 'success';
  if (['REJECTED', 'SUSPENDED', 'BLOCKED', 'CANCELED', 'EXPIRED'].includes(status)) return 'danger';
  if (['PENDING', 'SUBMITTED', 'UNDER_REVIEW', 'CHANGES_REQUESTED', 'PENDING_CONFIRMATION'].includes(status)) return 'warning';
  return 'info';
}

function SellerProfileForm({ profile }: { profile: SellerProfile }) {
  const client = useQueryClient();
  const [companyName, setCompanyName] = useState(profile.companyName);
  const [inn, setInn] = useState(profile.inn ?? '');
  const [contactName, setContactName] = useState(profile.contactName);
  const [phone, setPhone] = useState(profile.phone);
  const [pickupAddress, setPickupAddress] = useState(profile.pickupAddress);
  const save = useMutation({
    mutationFn: () => sellerApi.updateMe({ companyName, inn: inn || null, contactName, phone, pickupAddress }),
    onSuccess: (value) => client.setQueryData(['seller', 'me'], value),
  });
  return (
    <form className="stack" onSubmit={(event) => { event.preventDefault(); save.mutate(); }}>
      <Card className="form-grid">
        <Field label="Компания / ИП" value={companyName} onChange={(event) => setCompanyName(event.target.value)} required />
        <Field label="ИНН" inputMode="numeric" value={inn} onChange={(event) => setInn(event.target.value.replace(/\D/g, '').slice(0, 12))} />
        <div className="form-grid form-grid--2">
          <Field label="Контактное лицо" value={contactName} onChange={(event) => setContactName(event.target.value)} required />
          <Field label="Телефон" type="tel" value={phone} onChange={(event) => setPhone(event.target.value)} required />
        </div>
        <TextAreaField label="Адрес забора товара" value={pickupAddress} onChange={(event) => setPickupAddress(event.target.value)} required />
      </Card>
      {save.isSuccess && <Notice tone="success">Профиль сохранён.</Notice>}
      {save.error && <Notice tone="danger">Не удалось сохранить профиль.</Notice>}
      <Button type="submit" busy={save.isPending}>Сохранить данные</Button>
    </form>
  );
}

export function SellerHomePage() {
  const profile = useQuery({ queryKey: ['seller', 'me'], queryFn: sellerApi.me });
  if (profile.isLoading) return <LoadingPanel />;
  if (profile.error || !profile.data) return <StatePanel icon="!" title="Профиль не загрузился" action={<Button onClick={() => void profile.refetch()}>Повторить</Button>} />;
  return (
    <div className="stack">
      <PageHeader eyebrow="Поставщик" title="Профиль и проверка" description="Покупатель не увидит ваши контакты, закупочную цену и адрес забора." />
      <Card className={profile.data.verificationStatus === 'VERIFIED' ? 'card--accent' : ''}>
        <Badge tone={tone(profile.data.verificationStatus)}>{VERIFICATION_LABELS[profile.data.verificationStatus]}</Badge>
        <h2 style={{ marginTop: 12 }}>{profile.data.companyName || 'Заполните анкету поставщика'}</h2>
        <p className="muted tiny">После проверки вы сможете отправлять партии на модерацию.</p>
        {(profile.data.adminComment ?? profile.data.rejectionReason) && (
          <Notice tone="warning">Комментарий администратора: {profile.data.adminComment ?? profile.data.rejectionReason}</Notice>
        )}
      </Card>
      <SellerProfileForm profile={profile.data} />
    </div>
  );
}

export function SellerOffersPage() {
  const client = useQueryClient();
  const offers = useQuery({ queryKey: ['seller', 'offers'], queryFn: sellerApi.offers });
  const submit = useMutation({
    mutationFn: sellerApi.submitOffer,
    onSuccess: () => client.invalidateQueries({ queryKey: ['seller', 'offers'] }),
  });
  if (offers.isLoading) return <LoadingPanel />;
  if (offers.error) return <StatePanel icon="!" title="Партии не загрузились" action={<Button onClick={() => void offers.refetch()}>Повторить</Button>} />;
  const items = offers.data?.items ?? [];
  return (
    <div className="stack">
      <PageHeader title="Мои предложения" description="Черновик можно менять до отправки на модерацию." action={<Link to="/seller/offers/new"><Button>Новая партия</Button></Link>} />
      {items.length === 0 && <StatePanel title="Предложений пока нет" description="Создайте первую партию и отправьте её администратору." action={<Link to="/seller/offers/new"><Button>Создать</Button></Link>} />}
      {items.map((offer) => {
        const editable = ['DRAFT', 'CHANGES_REQUESTED', 'REJECTED'].includes(offer.status);
        return (
          <Card key={offer.id}>
            <div className="list-row">
              <div className="list-row__main"><strong>{offer.name}</strong><span>{offer.category} · обновлено {formatDateTime(offer.updatedAt)}</span></div>
              <Badge tone={tone(offer.status)}>{OFFER_LABELS[offer.status]}</Badge>
            </div>
            <div className="grid grid--2">
              <div><span className="muted tiny">Ваша цена</span><div className="price">{formatMoneyKopecks(offer.procurementUnitPriceKopecks)} <small>/ {UNIT_LABELS[offer.unit]}</small></div></div>
              <div><span className="muted tiny">Доступно</span><div className="price">{quantityText(offer.availableQuantity, offer.unit)}</div></div>
            </div>
            {offer.rejectionReason && <Notice tone="danger">{offer.rejectionReason}</Notice>}
            <div className="button-row" style={{ marginTop: 13 }}>
              {editable && <Link to={`/seller/offers/${offer.id}/edit`}><Button variant="secondary" size="sm">Редактировать</Button></Link>}
              {editable && <Button size="sm" busy={submit.isPending && submit.variables === offer.id} onClick={() => submit.mutate(offer.id)}>Отправить снова</Button>}
            </div>
          </Card>
        );
      })}
      {submit.error && <Notice tone="danger">Не удалось отправить предложение. Проверьте обязательные поля.</Notice>}
    </div>
  );
}

interface OfferEditorInitial {
  id?: string;
  name: string;
  description: string;
  category: string;
  procurementUnitPrice: string;
  unit: QuantityUnit;
  packageSize: string;
  totalQuantity: string;
  minimumQuantity: string;
  quantityStep: string;
  shelfLife: string;
  storageConditions: string;
  expiresAt: string;
  status?: SellerOfferStatus;
}

function toEditor(offer?: SellerOffer): OfferEditorInitial {
  return {
    id: offer?.id,
    name: offer?.name ?? '',
    description: offer?.description ?? '',
    category: offer?.category ?? 'Овощи и зелень',
    procurementUnitPrice: kopecksToRublesInput(offer?.procurementUnitPriceKopecks),
    unit: offer?.unit ?? 'KG',
    packageSize: offer?.packageSize ?? '1',
    totalQuantity: offer ? String(offer.totalQuantity) : '',
    minimumQuantity: offer ? String(offer.minimumQuantity) : '1',
    quantityStep: offer ? String(offer.quantityStep) : '1',
    shelfLife: offer?.shelfLife ?? '',
    storageConditions: offer?.storageConditions ?? '',
    expiresAt: offer?.expiresAt?.slice(0, 16) ?? '',
    status: offer?.status,
  };
}

function SellerOfferEditor({ initial }: { initial: OfferEditorInitial }) {
  const navigate = useNavigate();
  const client = useQueryClient();
  const [form, setForm] = useState(initial);
  const [files, setFiles] = useState<File[]>([]);
  const set = <K extends keyof OfferEditorInitial>(key: K, value: OfferEditorInitial[K]) => setForm((current) => ({ ...current, [key]: value }));
  const priceKopecks = rublesInputToKopecks(form.procurementUnitPrice);
  const totalQuantity = Number(form.totalQuantity);
  const minimumQuantity = Number(form.minimumQuantity);
  const quantityStep = Number(form.quantityStep);
  const validQuantity = [totalQuantity, minimumQuantity, quantityStep].every((value) => Number.isFinite(value) && value > 0)
    && totalQuantity >= minimumQuantity;
  const editable = !form.status || ['DRAFT', 'CHANGES_REQUESTED', 'REJECTED'].includes(form.status);

  const save = useMutation({
    mutationFn: async ({ submit }: { submit: boolean }) => {
      if (priceKopecks == null || !validQuantity) throw new Error('validation');
      const body: SellerOfferInput = {
        name: form.name.trim(),
        description: form.description.trim() || null,
        category: form.category,
        procurementUnitPriceKopecks: priceKopecks,
        currency: 'RUB',
        unit: form.unit,
        packageSize: form.packageSize.trim() || null,
        totalQuantity,
        minimumQuantity,
        quantityStep,
        shelfLife: form.shelfLife.trim() || null,
        storageConditions: form.storageConditions.trim() || null,
        expiresAt: form.expiresAt ? new Date(form.expiresAt).toISOString() : null,
      };
      let offer = form.id ? await sellerApi.updateOffer(form.id, body) : await sellerApi.createOffer(body);
      for (const file of files) await sellerApi.uploadImage(offer.id, file);
      if (submit) offer = await sellerApi.submitOffer(offer.id);
      return offer;
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['seller', 'offers'] });
      navigate('/seller/offers', { replace: true });
    },
  });

  const handle = (event: FormEvent, submit: boolean) => {
    event.preventDefault();
    if (!form.name.trim() || priceKopecks == null || !validQuantity) return;
    save.mutate({ submit });
  };

  if (!editable) return <StatePanel title="Предложение нельзя редактировать" description="Дождитесь результата модерации или создайте новую партию." action={<Link to="/seller/offers"><Button>Назад</Button></Link>} />;
  return (
    <form className="stack" onSubmit={(event) => handle(event, false)}>
      <PageHeader title={form.id ? 'Редактировать предложение' : 'Новая партия'} description="Покупателю будут показаны только публичные поля и конечная цена после модерации." />
      {form.status && ['CHANGES_REQUESTED', 'REJECTED'].includes(form.status) && <Notice tone="danger">Исправьте замечания администратора и отправьте предложение повторно.</Notice>}
      <Card className="form-grid">
        <Field label="Название товара" value={form.name} onChange={(event) => set('name', event.target.value)} required />
        <TextAreaField label="Описание" value={form.description} onChange={(event) => set('description', event.target.value)} />
        <SelectField label="Категория" value={form.category} onChange={(event) => set('category', event.target.value)}>
          {['Овощи и зелень', 'Фрукты и ягоды', 'Молочные продукты', 'Мясо и птица', 'Рыба и морепродукты', 'Бакалея', 'Напитки', 'Другое'].map((category) => <option key={category}>{category}</option>)}
        </SelectField>
        <div className="form-grid form-grid--2">
          <Field label="Ваша цена, ₽" inputMode="decimal" value={form.procurementUnitPrice} onChange={(event) => set('procurementUnitPrice', event.target.value)} error={form.procurementUnitPrice && priceKopecks == null ? 'Используйте не более двух знаков после запятой' : undefined} required />
          <SelectField label="Единица" value={form.unit} onChange={(event) => set('unit', event.target.value as QuantityUnit)}>
            <option value="KG">Килограмм</option><option value="LITER">Литр</option><option value="PIECE">Штука</option><option value="BOX">Коробка</option><option value="PACKAGE">Упаковка</option>
          </SelectField>
        </div>
        <Field label="Размер упаковки в выбранных единицах" type="number" min="0.001" step="any" value={form.packageSize} onChange={(event) => set('packageSize', event.target.value)} placeholder="Например, 8" />
        <div className="form-grid form-grid--2">
          <Field label="Всего" type="number" min="0" step="any" value={form.totalQuantity} onChange={(event) => set('totalQuantity', event.target.value)} required />
          <Field label="Минимальная партия" type="number" min="0" step="any" value={form.minimumQuantity} onChange={(event) => set('minimumQuantity', event.target.value)} required />
          <Field label="Шаг количества" type="number" min="0" step="any" value={form.quantityStep} onChange={(event) => set('quantityStep', event.target.value)} error={!validQuantity && form.totalQuantity ? 'Количество, минимум и шаг должны быть положительными; всего — не меньше минимума' : undefined} required />
          <Field label="Годен до" type="datetime-local" value={form.expiresAt} onChange={(event) => set('expiresAt', event.target.value)} />
        </div>
        <Field label="Годен до (дата)" type="date" value={form.shelfLife} onChange={(event) => set('shelfLife', event.target.value)} />
        <TextAreaField label="Условия хранения" value={form.storageConditions} onChange={(event) => set('storageConditions', event.target.value)} />
        <Field label="Фотографии" type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={(event) => setFiles(Array.from(event.target.files ?? []))} hint="Можно загрузить несколько JPG, PNG или WebP." />
      </Card>
      {save.error && <Notice tone="danger">Не удалось сохранить. Проверьте цену, количество и обязательные поля.</Notice>}
      <div className="button-row">
        <Button type="submit" variant="secondary" busy={save.isPending && !save.variables?.submit}>Сохранить черновик</Button>
        <Button type="button" busy={save.isPending && Boolean(save.variables?.submit)} onClick={(event) => handle(event, true)}>Сохранить и отправить</Button>
      </div>
    </form>
  );
}

export function SellerOfferFormPage() {
  const { offerId } = useParams<{ offerId: string }>();
  const offer = useQuery({ queryKey: ['seller', 'offer', offerId], queryFn: () => sellerApi.offer(offerId!), enabled: Boolean(offerId) });
  if (offerId && offer.isLoading) return <LoadingPanel />;
  if (offerId && (offer.error || !offer.data)) return <StatePanel icon="!" title="Предложение не загрузилось" action={<Button onClick={() => void offer.refetch()}>Повторить</Button>} />;
  return <SellerOfferEditor key={offer.data?.updatedAt ?? 'new'} initial={toEditor(offer.data)} />;
}

export function SellerOrdersPage() {
  const client = useQueryClient();
  const orders = useQuery({ queryKey: ['seller', 'orders'], queryFn: sellerApi.orders });
  const confirm = useMutation({ mutationFn: sellerApi.confirmOrder, onSuccess: () => client.invalidateQueries({ queryKey: ['seller', 'orders'] }) });
  const ready = useMutation({ mutationFn: sellerApi.readyOrder, onSuccess: () => client.invalidateQueries({ queryKey: ['seller', 'orders'] }) });
  if (orders.isLoading) return <LoadingPanel />;
  if (orders.error) return <StatePanel icon="!" title="Заказы не загрузились" action={<Button onClick={() => void orders.refetch()}>Повторить</Button>} />;
  const items = orders.data?.items ?? [];
  return (
    <div className="stack">
      <PageHeader title="Подготовка заказов" description="Данные покупателя скрыты. Администратор координирует забор и доставку." />
      {items.length === 0 && <StatePanel title="Активных заказов нет" description="Новые резервы появятся здесь после оформления покупателем." />}
      {items.map((order) => (
        <Card key={order.id}>
          <div className="list-row">
            <div className="list-row__main"><strong>Заказ №{order.number}</strong><span>{formatDateTime(order.createdAt)} · {order.itemsCount} позиций</span></div>
            <Badge tone={tone(order.status)}>{ORDER_LABELS[order.status] ?? order.status}</Badge>
          </div>
          <p className="muted tiny">Объём: {order.quantityLabel}</p>
          {order.pickupWindow && <p className="muted tiny">Окно забора: {order.pickupWindow}</p>}
          <div className="button-row">
            {order.status === 'PENDING_CONFIRMATION' && <Button size="sm" busy={confirm.isPending && confirm.variables === order.id} onClick={() => confirm.mutate(order.id)}>Подтвердить наличие</Button>}
            {['CONFIRMED', 'SELLER_PREPARING'].includes(order.status) && <Button size="sm" busy={ready.isPending && ready.variables === order.id} onClick={() => ready.mutate(order.id)}>Готово к забору</Button>}
          </div>
        </Card>
      ))}
      {(confirm.error || ready.error) && <Notice tone="danger">Действие не выполнено: статус заказа мог уже измениться.</Notice>}
    </div>
  );
}
