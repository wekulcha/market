import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { canBrowseCatalog, canCheckout } from '../../auth/access';
import { buyerApi, type CatalogQuery } from '../../api/buyer';
import { QuantityControl } from '../../components/QuantityControl';
import {
  Badge,
  Button,
  Card,
  Field,
  LoadingPanel,
  Notice,
  PageHeader,
  SelectField,
  SkeletonCards,
  StatePanel,
  TextAreaField,
} from '../../components/ui';
import type {
  BuyerOffer,
  BuyerOrderStatus,
  BuyerProfile,
  BuyerSubscription,
  SubscriptionStatus,
} from '../../types/domain';
import { formatDateTime, formatMoneyKopecks, quantityText, UNIT_LABELS } from '../../utils/format';

const SUBSCRIPTION_LABELS: Record<SubscriptionStatus, string> = {
  NONE: 'Нет подписки',
  PENDING: 'Ожидает оплаты',
  TRIAL: 'Пробный период',
  ACTIVE: 'Активна',
  PAST_DUE: 'Нужна оплата',
  EXPIRED: 'Истекла',
  CANCELED: 'Отменена',
  BLOCKED: 'Заблокирована',
};

const ORDER_LABELS: Record<BuyerOrderStatus, string> = {
  DRAFT: 'Черновик',
  RESERVED: 'Товар зарезервирован',
  PENDING_CONFIRMATION: 'Ждём подтверждения',
  CONFIRMED: 'Подтверждён',
  SELLER_PREPARING: 'Поставщик готовит',
  READY_FOR_PICKUP: 'Готов к забору',
  COURIER_ASSIGNED: 'Курьер назначен',
  PICKED_UP: 'Забран у поставщика',
  IN_DELIVERY: 'В пути',
  DELIVERED: 'Доставлен',
  COMPLETED: 'Завершён',
  CANCELED: 'Отменён',
  REFUNDED: 'Возврат',
};

function statusTone(status: string): 'neutral' | 'success' | 'warning' | 'danger' | 'info' {
  if (['ACTIVE', 'PUBLISHED', 'COMPLETED', 'DELIVERED'].includes(status)) return 'success';
  if (['CANCELED', 'EXPIRED', 'REFUNDED'].includes(status)) return 'danger';
  if (['PENDING', 'PAST_DUE', 'PENDING_CONFIRMATION', 'RESERVED'].includes(status)) return 'warning';
  return 'info';
}

function SubscriptionCard({ subscription }: { subscription: BuyerSubscription }) {
  const queryClient = useQueryClient();
  const payment = useMutation({
    mutationFn: () => buyerApi.createSubscriptionPayment(),
    onSuccess: async ({ id, paymentUrl }) => {
      if (paymentUrl?.startsWith('mock://')) {
        await buyerApi.confirmMockSubscriptionPayment(id);
        await queryClient.invalidateQueries({ queryKey: ['buyer', 'subscription'] });
        await queryClient.invalidateQueries({ queryKey: ['buyer', 'me'] });
        return;
      }
      if (paymentUrl) window.location.assign(paymentUrl);
    },
  });
  const active = canCheckout(subscription);
  return (
    <Card className={active ? 'card--accent' : ''}>
      <div className="list-row">
        <div className="list-row__main">
          <Badge tone={active ? 'success' : 'warning'}>{SUBSCRIPTION_LABELS[subscription.status]}</Badge>
          <h2 style={{ marginTop: 10 }}>{subscription.planName ?? 'Доступ к оптовому каталогу'}</h2>
          <span>
            {active
              ? `Действует до ${formatDateTime(subscription.expiresAt)}`
              : 'Оформите подписку, чтобы видеть цены и размещать заказы.'}
          </span>
        </div>
        <div style={{ textAlign: 'right' }}>
          <strong>{formatMoneyKopecks(subscription.amountKopecks)}</strong>
          {!active && (
            <div style={{ marginTop: 9 }}>
              <Button size="sm" variant={active ? 'secondary' : 'primary'} busy={payment.isPending} onClick={() => payment.mutate()}>
                Оплатить
              </Button>
            </div>
          )}
        </div>
      </div>
      {payment.error && <Notice tone="danger">Не удалось создать платёж. Попробуйте ещё раз.</Notice>}
    </Card>
  );
}

export function BuyerHomePage() {
  const profile = useQuery({ queryKey: ['buyer', 'me'], queryFn: buyerApi.me });
  const subscription = useQuery({ queryKey: ['buyer', 'subscription'], queryFn: buyerApi.subscription });
  if (profile.isLoading || subscription.isLoading) return <LoadingPanel />;
  if (profile.error || subscription.error || !profile.data || !subscription.data) {
    return <StatePanel icon="!" title="Не удалось загрузить кабинет" description="Проверьте соединение и повторите запрос." action={<Button onClick={() => { void profile.refetch(); void subscription.refetch(); }}>Повторить</Button>} />;
  }
  return (
    <div className="stack stack--lg">
      <section className="hero">
        <p className="eyebrow">Закрытый B2B-маркет</p>
        <h1>Выгодные партии для вашего бизнеса</h1>
        <p>Проверенные предложения, понятные условия и доставка от поставщика до вашей точки.</p>
        <div className="hero__stats">
          <div className="hero__stat"><strong>1 окно</strong><span>для всех поставщиков</span></div>
          <div className="hero__stat"><strong>Без контактов</strong><span>стороны защищены платформой</span></div>
        </div>
      </section>
      <SubscriptionCard subscription={subscription.data} />
      <div>
        <div className="section-title"><h2>Быстрый старт</h2></div>
        <div className="grid grid--2">
          <Link to="/buyer/catalog"><Card><span className="eyebrow">Каталог</span><h2>Найти партию</h2><p className="muted tiny">Поиск по категориям, цене и сроку.</p></Card></Link>
          <Link to="/buyer/orders"><Card><span className="eyebrow">Заказы</span><h2>Проверить доставку</h2><p className="muted tiny">Актуальный статус каждого заказа.</p></Card></Link>
        </div>
      </div>
      {!profile.data.companyName && <Notice tone="warning">Заполните данные компании в профиле до первого заказа.</Notice>}
    </div>
  );
}

function OfferCard({
  offer,
  quantity,
  onQuantity,
  onAdd,
  busy,
}: {
  offer: BuyerOffer;
  quantity: number;
  onQuantity: (quantity: number) => void;
  onAdd: () => void;
  busy: boolean;
}) {
  const priceVisible = offer.buyerUnitPriceKopecks != null;
  return (
    <Card className="offer-card">
      <div className="offer-card__media">
        {offer.photos[0]
          ? <img src={offer.photos[0]} alt={offer.publicName} loading="lazy" decoding="async" />
          : <div className="offer-card__placeholder" aria-hidden="true">◇</div>}
      </div>
      <div className="offer-card__body">
        <Badge>{offer.category}</Badge>
        <h2>{offer.publicName}</h2>
        <p>{offer.publicDescription || 'Оптовое предложение KULCHA B2B'}</p>
        <div className="offer-card__meta">
          <span>{offer.availableQuantityLabel}</span>
          <span>Мин. {quantityText(offer.minimumQuantity, offer.unit)}</span>
          {offer.packageSize && <span>{offer.packageSize}</span>}
        </div>
      </div>
      <div className="offer-card__footer">
        <div className="price">
          {priceVisible ? formatMoneyKopecks(offer.buyerUnitPriceKopecks) : 'Цена по подписке'}
          {priceVisible && <small> / {UNIT_LABELS[offer.unit]}</small>}
        </div>
        {priceVisible && (
          <div className="button-row">
            <QuantityControl value={quantity} minimum={offer.minimumQuantity} step={offer.quantityStep} onChange={onQuantity} disabled={busy} />
            <Button size="sm" busy={busy} onClick={onAdd}>В корзину</Button>
          </div>
        )}
      </div>
    </Card>
  );
}

export function BuyerCatalogPage() {
  const client = useQueryClient();
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [sort, setSort] = useState<CatalogQuery['sort']>('NEWEST');
  const [quantities, setQuantities] = useState<Record<string, number>>({});
  const query = useMemo(() => ({ search, category, sort }), [category, search, sort]);
  const catalog = useQuery({ queryKey: ['buyer', 'catalog', query], queryFn: () => buyerApi.catalog(query) });
  const subscription = useQuery({ queryKey: ['buyer', 'subscription'], queryFn: buyerApi.subscription });
  const addItem = useMutation({
    mutationFn: ({ offerId, quantity }: { offerId: string; quantity: number }) => buyerApi.addCartItem(offerId, quantity),
    onSuccess: (cart) => client.setQueryData(['buyer', 'cart'], cart),
  });
  const offers = catalog.data?.items ?? [];
  const categories = useMemo(() => [...new Set(offers.map((offer) => offer.category))].sort((a, b) => a.localeCompare(b, 'ru')), [offers]);

  if (subscription.isLoading) return <LoadingPanel />;
  if (subscription.data && !canBrowseCatalog(subscription.data)) {
    return <StatePanel icon="◉" title="Каталог доступен по подписке" description="Активируйте тариф на главной странице, чтобы увидеть предложения." action={<Link to="/buyer"><Button>К подписке</Button></Link>} />;
  }
  return (
    <div>
      <PageHeader eyebrow="Только активные партии" title="Каталог" description="Публичные цены уже включают наценку платформы. Контакты поставщика не раскрываются." />
      <div className="search-row">
        <Field aria-label="Поиск" label="Поиск" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Название или категория" />
        <SelectField label="Сортировка" value={sort} onChange={(event) => setSort(event.target.value as CatalogQuery['sort'])}>
          <option value="NEWEST">Сначала новые</option>
          <option value="PRICE_ASC">Цена: ниже</option>
          <option value="PRICE_DESC">Цена: выше</option>
          <option value="EXPIRY_ASC">Срок партии</option>
        </SelectField>
      </div>
      {categories.length > 0 && (
        <div className="filter-row">
          <button className={`filter-chip${category === '' ? ' is-active' : ''}`} onClick={() => setCategory('')} type="button">Все</button>
          {categories.map((item) => <button className={`filter-chip${category === item ? ' is-active' : ''}`} onClick={() => setCategory(item)} type="button" key={item}>{item}</button>)}
        </div>
      )}
      {catalog.isLoading && <SkeletonCards count={4} />}
      {catalog.error && <StatePanel icon="!" title="Каталог не загрузился" description="Данные не потеряны — повторите запрос." action={<Button onClick={() => void catalog.refetch()}>Повторить</Button>} />}
      {!catalog.isLoading && !catalog.error && offers.length === 0 && <StatePanel title="Предложений пока нет" description="Измените фильтры или зайдите немного позже." />}
      <div className="offer-grid">
        {offers.map((offer) => {
          const quantity = quantities[offer.id] ?? offer.minimumQuantity;
          return (
            <OfferCard
              key={offer.id}
              offer={offer}
              quantity={quantity}
              onQuantity={(next) => setQuantities((current) => ({ ...current, [offer.id]: next }))}
              onAdd={() => addItem.mutate({ offerId: offer.id, quantity })}
              busy={addItem.isPending && addItem.variables?.offerId === offer.id}
            />
          );
        })}
      </div>
      {addItem.isSuccess && <Notice tone="success">Товар добавлен. Итоговая цена и остаток будут повторно проверены сервером при checkout.</Notice>}
      {addItem.error && <Notice tone="danger">Не удалось добавить товар: возможно, остаток уже изменился.</Notice>}
    </div>
  );
}

export function BuyerCartPage() {
  const client = useQueryClient();
  const cart = useQuery({ queryKey: ['buyer', 'cart'], queryFn: buyerApi.cart });
  const subscription = useQuery({ queryKey: ['buyer', 'subscription'], queryFn: buyerApi.subscription });
  const update = useMutation({
    mutationFn: ({ id, quantity }: { id: string; quantity: number }) => buyerApi.updateCartItem(id, quantity),
    onSuccess: (value) => client.setQueryData(['buyer', 'cart'], value),
  });
  const remove = useMutation({
    mutationFn: buyerApi.removeCartItem,
    onSuccess: (value) => client.setQueryData(['buyer', 'cart'], value),
  });
  if (cart.isLoading || subscription.isLoading) return <LoadingPanel />;
  if (cart.error || !cart.data) return <StatePanel icon="!" title="Корзина не загрузилась" action={<Button onClick={() => void cart.refetch()}>Повторить</Button>} />;
  if (cart.data.lines.length === 0) return <StatePanel icon="◫" title="Корзина пуста" description="Добавьте подходящие партии из каталога." action={<Link to="/buyer/catalog"><Button>Открыть каталог</Button></Link>} />;
  const checkoutAllowed = subscription.data ? canCheckout(subscription.data) : false;
  return (
    <div className="stack">
      <PageHeader title="Корзина" description="Резерв и финальная цена создаются только на сервере при оформлении." />
      {cart.data.lines.map((line) => (
        <Card key={line.id}>
          <div className="list-row">
            <div className="list-row__main">
              <strong>{line.offer.publicName}</strong>
              <span>{formatMoneyKopecks(line.offer.buyerUnitPriceKopecks)} / {UNIT_LABELS[line.offer.unit]}</span>
              <span>Минимум {quantityText(line.offer.minimumQuantity, line.offer.unit)}, шаг {quantityText(line.offer.quantityStep, line.offer.unit)}</span>
            </div>
            <QuantityControl value={line.quantity} minimum={line.offer.minimumQuantity} step={line.offer.quantityStep} disabled={update.isPending} onChange={(quantity) => update.mutate({ id: line.id, quantity })} />
          </div>
          <Button size="sm" variant="ghost" busy={remove.isPending && remove.variables === line.id} onClick={() => remove.mutate(line.id)}>Удалить</Button>
        </Card>
      ))}
      <Card>
        <div className="list-row"><span>Товары</span><strong>{formatMoneyKopecks(cart.data.itemsTotalKopecks)}</strong></div>
        <div className="list-row"><span>Доставка</span><strong>{cart.data.deliveryFeeKopecks == null ? 'Рассчитаем' : formatMoneyKopecks(cart.data.deliveryFeeKopecks)}</strong></div>
        <div className="list-row"><strong>Итого</strong><strong className="price">{formatMoneyKopecks(cart.data.totalKopecks)}</strong></div>
      </Card>
      {!checkoutAllowed && <Notice tone="warning">Checkout заблокирован до активации подписки.</Notice>}
      {checkoutAllowed ? <Link to="/buyer/checkout"><Button style={{ width: '100%' }}>Перейти к оформлению</Button></Link> : <Link to="/buyer"><Button style={{ width: '100%' }}>Активировать подписку</Button></Link>}
    </div>
  );
}

export function BuyerCheckoutPage() {
  const navigate = useNavigate();
  const cart = useQuery({ queryKey: ['buyer', 'cart'], queryFn: buyerApi.cart });
  const profile = useQuery({ queryKey: ['buyer', 'me'], queryFn: buyerApi.me });
  const subscription = useQuery({ queryKey: ['buyer', 'subscription'], queryFn: buyerApi.subscription });
  const [addressId, setAddressId] = useState('');
  const [recipientName, setRecipientName] = useState('');
  const [recipientPhone, setRecipientPhone] = useState('');
  const [deliveryWindow, setDeliveryWindow] = useState('');
  const [comment, setComment] = useState('');
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [paymentMethod, setPaymentMethod] = useState<'PAY_ON_DELIVERY' | 'BANK_TRANSFER' | 'MANUAL'>('BANK_TRANSFER');
  const create = useMutation({
    mutationFn: buyerApi.createOrder,
    onSuccess: (order) => navigate(`/buyer/orders?created=${encodeURIComponent(order.number)}`, { replace: true }),
  });
  if (cart.isLoading || profile.isLoading || subscription.isLoading) return <LoadingPanel />;
  if (!cart.data || !profile.data || !subscription.data) return <StatePanel icon="!" title="Не удалось подготовить checkout" />;
  if (!canCheckout(subscription.data)) return <StatePanel title="Нужна активная подписка" action={<Link to="/buyer"><Button>К подписке</Button></Link>} />;
  if (cart.data.lines.length === 0) return <StatePanel title="Корзина пуста" action={<Link to="/buyer/catalog"><Button>В каталог</Button></Link>} />;
  const selectedAddressId = addressId || profile.data.addresses.find((address) => address.isDefault)?.id || profile.data.addresses[0]?.id || '';
  const finalRecipient = recipientName.trim() || profile.data.contactName;
  const finalPhone = recipientPhone.trim() || profile.data.phone;
  const ready = Boolean(selectedAddressId && finalRecipient && finalPhone && termsAccepted);
  return (
    <form className="stack" onSubmit={(event) => {
      event.preventDefault();
      if (!ready) return;
      create.mutate({
        addressId: selectedAddressId,
        recipientName: finalRecipient,
        recipientPhone: finalPhone,
        deliveryWindow: deliveryWindow || null,
        comment: comment.trim() || null,
        paymentMethod,
        idempotencyKey: crypto.randomUUID(),
        termsAccepted: true,
      });
    }}>
      <PageHeader title="Оформление" description="Перед созданием заказа сервер заново проверит подписку, цены, шаг количества и остатки." />
      <Card className="form-grid">
        <SelectField label="Адрес доставки" value={selectedAddressId} onChange={(event) => setAddressId(event.target.value)} required>
          <option value="">Выберите адрес</option>
          {profile.data.addresses.map((address) => <option value={address.id} key={address.id}>{address.label}: {address.value}</option>)}
        </SelectField>
        <div className="form-grid form-grid--2">
          <Field label="Получатель" value={recipientName} onChange={(event) => setRecipientName(event.target.value)} placeholder={profile.data.contactName} />
          <Field label="Телефон" type="tel" value={recipientPhone} onChange={(event) => setRecipientPhone(event.target.value)} placeholder={profile.data.phone} />
        </div>
        <Field label="Желаемое окно доставки" value={deliveryWindow} onChange={(event) => setDeliveryWindow(event.target.value)} placeholder="Например, завтра 10:00–13:00" />
        <SelectField label="Оплата заказа" value={paymentMethod} onChange={(event) => setPaymentMethod(event.target.value as typeof paymentMethod)}>
          <option value="BANK_TRANSFER">Банковский перевод</option>
          <option value="PAY_ON_DELIVERY">При получении</option>
          <option value="MANUAL">По согласованию</option>
        </SelectField>
        <TextAreaField label="Комментарий" value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Уточнения по въезду, разгрузке или времени" />
      </Card>
      <Card>
        <div className="list-row"><span>{cart.data.lines.length} позиций</span><strong>{formatMoneyKopecks(cart.data.itemsTotalKopecks)}</strong></div>
        <div className="list-row"><strong>Предварительный итог</strong><strong>{formatMoneyKopecks(cart.data.totalKopecks)}</strong></div>
      </Card>
      <label className="check-row">
        <input
          type="checkbox"
          checked={termsAccepted}
          onChange={(event) => setTermsAccepted(event.target.checked)}
          required
        />
        <span>Подтверждаю адрес, состав заказа, условия оплаты и создание резерва.</span>
      </label>
      {profile.data.addresses.length === 0 && <Notice tone="warning">Добавьте адрес доставки в профиле.</Notice>}
      {create.error && <Notice tone="danger">Заказ не создан. Возможно, изменились цена или остаток — вернитесь в корзину.</Notice>}
      <Button type="submit" busy={create.isPending} disabled={!ready}>Создать резерв и заказ</Button>
    </form>
  );
}

export function BuyerOrdersPage() {
  const orders = useQuery({ queryKey: ['buyer', 'orders'], queryFn: buyerApi.orders });
  if (orders.isLoading) return <LoadingPanel />;
  if (orders.error) return <StatePanel icon="!" title="Заказы не загрузились" action={<Button onClick={() => void orders.refetch()}>Повторить</Button>} />;
  const items = orders.data?.items ?? [];
  return (
    <div className="stack">
      <PageHeader title="Мои заказы" description="Статус отражает путь от резерва до доставки." />
      {items.length === 0 && <StatePanel title="Заказов пока нет" action={<Link to="/buyer/catalog"><Button>Выбрать товары</Button></Link>} />}
      {items.map((order) => (
        <Card key={order.id}>
          <div className="list-row">
            <div className="list-row__main"><strong>Заказ №{order.number}</strong><span>{formatDateTime(order.createdAt)} · {order.itemsCount} позиций</span></div>
            <Badge tone={statusTone(order.status)}>{ORDER_LABELS[order.status]}</Badge>
          </div>
          <div className="list-row"><span>{order.deliveryAddress}</span><strong>{formatMoneyKopecks(order.totalKopecks)}</strong></div>
          {order.deliveryWindow && <p className="muted tiny">Окно: {order.deliveryWindow}</p>}
        </Card>
      ))}
    </div>
  );
}

function BuyerProfileForm({ profile }: { profile: BuyerProfile }) {
  const client = useQueryClient();
  const [companyName, setCompanyName] = useState(profile.companyName);
  const [inn, setInn] = useState(profile.inn ?? '');
  const [contactName, setContactName] = useState(profile.contactName);
  const [phone, setPhone] = useState(profile.phone);
  const [email, setEmail] = useState(profile.email ?? '');
  const save = useMutation({
    mutationFn: () => buyerApi.updateMe({ companyName, inn: inn || null, contactName, phone, email: email || null }),
    onSuccess: (value) => client.setQueryData(['buyer', 'me'], value),
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
        <Field label="Email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
      </Card>
      <Card>
        <h2>Адреса доставки</h2>
        {profile.addresses.length === 0 ? <p className="muted tiny">Адресов пока нет. Их добавление доступно через API профиля.</p> : profile.addresses.map((address) => <div className="list-row" key={address.id}><div className="list-row__main"><strong>{address.label}</strong><span>{address.value}</span></div>{address.isDefault && <Badge tone="success">Основной</Badge>}</div>)}
      </Card>
      {save.isSuccess && <Notice tone="success">Профиль сохранён.</Notice>}
      {save.error && <Notice tone="danger">Не удалось сохранить профиль.</Notice>}
      <Button type="submit" busy={save.isPending}>Сохранить</Button>
    </form>
  );
}

export function BuyerProfilePage() {
  const profile = useQuery({ queryKey: ['buyer', 'me'], queryFn: buyerApi.me });
  if (profile.isLoading) return <LoadingPanel />;
  if (profile.error || !profile.data) return <StatePanel icon="!" title="Профиль не загрузился" action={<Button onClick={() => void profile.refetch()}>Повторить</Button>} />;
  return (
    <div>
      <PageHeader title="Профиль компании" description="Эти данные использует администратор для оформления и доставки." />
      <BuyerProfileForm profile={profile.data} />
    </div>
  );
}
