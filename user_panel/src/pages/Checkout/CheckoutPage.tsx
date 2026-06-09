import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchMarketRestaurant } from '../../api/restaurants';
import { createOrder } from '../../api/orders';
import { ApiError } from '../../api/client';
import { updateUserProfile } from '../../api/users';
import { MARKET_BRAND_NAME, MARKET_MIN_ORDER_TOTAL } from '../../config/market';
import { useAppContext } from '../../context/AppContext';
import { useAuth } from '../../context/AuthContext';
import { useCart } from '../../context/CartContext';
import { Header } from '../../layout/Header';
import { MiniAppShell } from '../../layout/MiniAppShell';
import { requestTelegramContact } from '../../telegram/initTelegram';
import type { CreateOrderPayload, PaymentMethod } from '../../types/order';
import {
  MARKET_STREETS,
  formatLocationParts,
  formatLocationShort,
  parseLocationParts,
} from '../../utils/locationFormat';
import { deliveryCutoffHint, deliveryPromiseText } from '../../utils/deliveryPromise';
import {
  isRegisteredPhone,
  isRussianPhone,
  normalizePhoneInput,
  normalizeRussianPhoneInput,
  phoneToInputValue,
} from '../../utils/phoneFormat';

function sanitizeUsername(username: string | null): string {
  if (!username) return '';
  return username.startsWith('@') ? username : `@${username}`;
}

export function CheckoutPage() {
  const { currentUser, authReady, authError, reloadAuth } = useAuth();
  const { selectedRestaurant, setSelectedRestaurant, setServiceType } = useAppContext();
  const { items, clearCart } = useCart();
  const navigate = useNavigate();

  const itemsTotal = items.reduce((sum, item) => sum + item.meal.price * item.quantity, 0);
  const deliveryFee = 0;
  const serviceFee = 0;
  const total = itemsTotal + deliveryFee + serviceFee;
  const missingToMinimum = Math.max(0, MARKET_MIN_ORDER_TOTAL - itemsTotal);
  const deliveryText = deliveryPromiseText(selectedRestaurant?.ordersAcceptTo);
  const deliveryHint = deliveryCutoffHint(selectedRestaurant?.ordersAcceptTo);

  const [street, setStreet] = useState<string>(MARKET_STREETS[0]);
  const [house, setHouse] = useState('');
  const [entrance, setEntrance] = useState('');
  const [floor, setFloor] = useState('');
  const [apartment, setApartment] = useState('');
  const [comment, setComment] = useState('');
  const [username, setUsername] = useState<string>('');
  const [phoneInput, setPhoneInput] = useState('');
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('CASH');
  const [marketLoading, setMarketLoading] = useState(false);
  const [marketError, setMarketError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [registeringContact, setRegisteringContact] = useState(false);
  const [registrationMessage, setRegistrationMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const loadMarketRestaurant = async () => {
    try {
      setMarketLoading(true);
      setMarketError(null);
      const restaurant = await fetchMarketRestaurant();
      setSelectedRestaurant(restaurant);
      setServiceType('DELIVERY');
    } catch (err) {
      setMarketError(err instanceof Error ? err.message : 'Не удалось загрузить магазин.');
    } finally {
      setMarketLoading(false);
    }
  };

  useEffect(() => {
    setServiceType('DELIVERY');
    if (!selectedRestaurant) {
      void loadMarketRestaurant();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedRestaurant?.id]);

  useEffect(() => {
    if (!currentUser) return;
    setPhoneInput((prev) => (prev.trim() ? prev : phoneToInputValue(currentUser.phone)));
    setUsername(sanitizeUsername(currentUser.username));
  }, [currentUser]);

  useEffect(() => {
    if (!currentUser?.address?.trim()) return;
    const p = parseLocationParts(currentUser.address);
    setStreet((prev) => (prev.trim() ? prev : p.street));
    setHouse((prev) => (prev.trim() ? prev : p.house));
    setEntrance((prev) => (prev.trim() ? prev : p.entrance));
    setFloor((prev) => (prev.trim() ? prev : p.floor));
    setApartment((prev) => (prev.trim() ? prev : p.apartment));
  }, [currentUser?.address]);

  const handleSubmit = async () => {
    setErrorMessage(null);
    setSuccessMessage(null);

    if (items.length === 0) {
      setErrorMessage('Корзина пуста, добавьте товары перед оформлением.');
      return;
    }

    if (itemsTotal < MARKET_MIN_ORDER_TOTAL) {
      setErrorMessage(`Минимальная сумма заказа — ${MARKET_MIN_ORDER_TOTAL} ₽. Добавьте товаров ещё на ${missingToMinimum.toFixed(0)} ₽.`);
      return;
    }

    if (!selectedRestaurant) {
      setErrorMessage('Магазин не настроен. Попробуйте обновить страницу.');
      return;
    }

    if (!authReady) {
      setErrorMessage('Подождите немного, мы еще проверяем вход в mini app.');
      return;
    }

    if (!currentUser) {
      setErrorMessage(authError ?? `Откройте мини-приложение из Telegram через кнопку в боте ${MARKET_BRAND_NAME}.`);
      return;
    }

    if (!isRegisteredPhone(currentUser.phone)) {
      setErrorMessage('Чтобы оформить заказ, сначала поделитесь контактом через Telegram.');
      return;
    }

    const phoneForApi = normalizeRussianPhoneInput(phoneInput);
    if (!phoneForApi) {
      setErrorMessage('Для заказа нужен российский номер. Укажите номер формата +7 900 123-45-67.');
      return;
    }

    if (!street.trim() || !house.trim() || !entrance.trim() || !floor.trim() || !apartment.trim()) {
      setErrorMessage('Укажите улицу, дом, подъезд, этаж и квартиру.');
      return;
    }

    const deliveryAddr = formatLocationParts(street, house, entrance, floor, apartment).trim();

    const payload: CreateOrderPayload = {
      restaurant_id: selectedRestaurant.id,
      service_type: 'DELIVERY',
      delivery_address: deliveryAddr,
      table_number: null,
      comment: comment.trim() || null,
      username: username.replace(/^@/, '') || null,
      phone: phoneForApi,
      payment_method: paymentMethod,
      items: items.map((item) => ({
        meal_id: item.meal.id,
        quantity: item.quantity,
        price: item.meal.price,
      })),
      items_total: itemsTotal,
      delivery_fee: deliveryFee,
      service_fee: serviceFee,
      total,
    };

    try {
      setSubmitting(true);
      await updateUserProfile(currentUser.id, { phone: phoneForApi });
      const response = await createOrder(payload);
      void updateUserProfile(currentUser.id, { address: deliveryAddr }).catch(() => {});
      clearCart();
      setSuccessMessage(`Заказ №${response.id} успешно создан. ${deliveryText}.`);
      setTimeout(() => {
        navigate('/catalog');
      }, 1500);
    } catch (error) {
      console.error(error);
      if (error instanceof ApiError && error.body.trim()) {
        setErrorMessage(error.body.trim());
      } else {
        setErrorMessage('Не удалось оформить заказ. Попробуйте позже.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const handleRegisterContact = async () => {
    setErrorMessage(null);
    setSuccessMessage(null);
    setRegistrationMessage(null);

    if (!authReady) {
      setErrorMessage('Подождите немного, мы еще проверяем вход в mini app.');
      return;
    }
    if (!currentUser) {
      setErrorMessage(authError ?? `Откройте мини-приложение из Telegram через кнопку в боте ${MARKET_BRAND_NAME}.`);
      return;
    }

    try {
      setRegisteringContact(true);
      const shared = await requestTelegramContact();
      if (!shared) {
        setErrorMessage('Telegram не получил контакт. Без телефона оформить заказ не получится.');
        return;
      }
      setRegistrationMessage('Контакт отправлен. Проверяем регистрацию...');
      [900, 2200, 4000].forEach((delay) => {
        window.setTimeout(() => {
          void reloadAuth();
        }, delay);
      });
    } finally {
      setRegisteringContact(false);
    }
  };

  const normalizedPhone = normalizePhoneInput(phoneInput);
  const phoneForApi = normalizeRussianPhoneInput(phoneInput);
  const phoneDigitsOk = phoneForApi !== null;
  const needsRegistration = Boolean(authReady && currentUser && !isRegisteredPhone(currentUser.phone));
  const needsRussianPhone = Boolean(!needsRegistration && normalizedPhone && !isRussianPhone(phoneInput));
  const savedDeliveryAddress = formatLocationShort(currentUser?.address ?? null);
  const actionDisabled =
    submitting ||
    registeringContact ||
    marketLoading ||
    total <= 0 ||
    itemsTotal < MARKET_MIN_ORDER_TOTAL ||
    !selectedRestaurant ||
    !authReady ||
    !currentUser;
  const submitDisabled =
    actionDisabled ||
    (!needsRegistration && !phoneDigitsOk);

  return (
    <MiniAppShell>
      <div className="space-y-4 pb-28">
        <Header
          title="Оформление"
          showBack
          onBackClick={() => navigate('/cart', { replace: true })}
          onProfileClick={() => navigate('/profile')}
          showSearch={false}
        />

        {authReady && !currentUser && (
          <div className="bg-amber-50 rounded-2xl p-3 shadow-sm border border-amber-100 space-y-3">
            <div className="text-sm font-semibold text-amber-900">Нужно подтвердить вход</div>
            <div className="text-xs text-amber-700">
              {authError ?? `Откройте mini app из Telegram через кнопку в боте ${MARKET_BRAND_NAME}.`}
            </div>
            <button
              type="button"
              onClick={reloadAuth}
              className="rounded-xl bg-amber-600 px-3 py-2 text-xs font-semibold text-white hover:bg-amber-700 transition-colors"
            >
              Повторить вход
            </button>
          </div>
        )}

        <div className="bg-white rounded-2xl p-3 shadow-sm">
          <div className="text-xs text-slate-500">Заказ из</div>
          <div className="text-sm font-semibold text-slate-900">
            {selectedRestaurant?.name ?? MARKET_BRAND_NAME}
          </div>
          <div className="text-xs text-slate-500 mt-1">
            {deliveryText}. {deliveryHint}
          </div>
        </div>

        {marketError && (
          <div className="bg-amber-50 rounded-2xl p-3 shadow-sm border border-amber-100 text-xs text-amber-800">
            {marketError}
            <button
              type="button"
              onClick={() => void loadMarketRestaurant()}
              className="ml-2 font-semibold underline"
            >
              Повторить
            </button>
          </div>
        )}

        <div className="bg-white rounded-2xl p-3 shadow-sm space-y-3">
          <div className="text-sm font-semibold text-slate-900">Адрес доставки</div>
          <p className="text-[11px] text-slate-500">
            {savedDeliveryAddress ? `Текущий адрес: ${savedDeliveryAddress}.` : 'Выберите улицу и заполните детали.'}
          </p>
          <div className="space-y-1">
            <label className="block text-[10px] font-medium text-slate-500 uppercase tracking-wide">
              Улица
            </label>
            <select
              className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm bg-white"
              value={street}
              onChange={(e) => setStreet(e.target.value)}
            >
              {MARKET_STREETS.map((streetOption) => (
                <option key={streetOption} value={streetOption}>
                  {streetOption}
                </option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <AddressInput label="Дом" value={house} onChange={setHouse} placeholder="12" />
            <AddressInput label="Подъезд" value={entrance} onChange={setEntrance} placeholder="1" />
            <AddressInput label="Этаж" value={floor} onChange={setFloor} placeholder="4" />
            <AddressInput label="Квартира" value={apartment} onChange={setApartment} placeholder="25" />
          </div>
        </div>

        <div className="bg-white rounded-2xl p-3 shadow-sm space-y-2">
          <label className="block text-[11px] text-slate-500">Комментарий к заказу</label>
          <textarea
            className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm min-h-[72px]"
            placeholder="Например: позвонить перед доставкой"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
        </div>

        <div className="bg-white rounded-2xl p-3 shadow-sm space-y-3">
          <div className="text-sm font-semibold text-slate-900">Контакты</div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Username</label>
              <input
                type="text"
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm bg-slate-50 text-slate-700"
                value={username || '—'}
                readOnly
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Телефон</label>
              <input
                type="tel"
                inputMode="tel"
                autoComplete="tel"
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm bg-white"
                placeholder="+7 900 123-45-67"
                value={phoneInput}
                onChange={(e) => setPhoneInput(e.target.value.slice(0, 24))}
              />
            </div>
          </div>
          <p className="text-[11px] text-slate-400">
            Заказ можно оформить только на российский номер. Перед первым заказом Telegram должен подтвердить ваш контакт.
          </p>
          {needsRussianPhone && (
            <div className="rounded-xl border border-amber-100 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              Для заказа нужно указать и сохранить российский номер телефона.
            </div>
          )}
          {needsRegistration && (
            <div className="rounded-xl border border-amber-100 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              Чтобы оформить заказ, нужно один раз зарегистрироваться: Telegram попросит поделиться контактом.
            </div>
          )}
          {registrationMessage && (
            <div className="rounded-xl border border-emerald-100 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
              {registrationMessage}
            </div>
          )}
        </div>

        <div className="bg-white rounded-2xl p-3 shadow-sm space-y-2">
          <div className="text-sm font-semibold text-slate-900">Оплата</div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => setPaymentMethod('CASH')}
              className={
                'flex-1 rounded-xl px-3 py-2 text-sm border transition-colors ' +
                (paymentMethod === 'CASH'
                  ? 'bg-slate-900 text-white border-slate-900'
                  : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100')
              }
            >
              Наличными
            </button>
            <button
              type="button"
              onClick={() => setPaymentMethod('TRANSFER')}
              className={
                'flex-1 rounded-xl px-3 py-2 text-sm border transition-colors ' +
                (paymentMethod === 'TRANSFER'
                  ? 'bg-slate-900 text-white border-slate-900'
                  : 'bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100')
              }
            >
              Переводом
            </button>
          </div>
        </div>

        <div className="bg-white rounded-2xl p-3 shadow-sm space-y-1 text-sm text-slate-800">
          <div className="flex justify-between">
            <span>Товары в заказе</span>
            <span className="font-semibold">{itemsTotal.toFixed(0)} ₽</span>
          </div>
          <div className="flex justify-between text-slate-500">
            <span>Минимальный заказ</span>
            <span>{MARKET_MIN_ORDER_TOTAL} ₽</span>
          </div>
          {missingToMinimum > 0 && (
            <div className="rounded-xl border border-amber-100 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              Добавьте товаров ещё на {missingToMinimum.toFixed(0)} ₽.
            </div>
          )}
          <div className="flex justify-between text-slate-500">
            <span>Доставка</span>
            <span>{deliveryFee.toFixed(0)} ₽</span>
          </div>
          <div className="flex justify-between text-slate-500">
            <span>Сервисный сбор</span>
            <span>{serviceFee.toFixed(0)} ₽</span>
          </div>
          <div className="border-t border-slate-100 mt-2 pt-2 flex justify-between font-semibold">
            <span>Итого</span>
            <span>{total.toFixed(0)} ₽</span>
          </div>
        </div>

        {errorMessage && <div className="text-xs text-red-500 bg-red-50 rounded-xl p-3">{errorMessage}</div>}
        {successMessage && (
          <div className="text-xs text-emerald-600 bg-emerald-50 rounded-xl p-3">{successMessage}</div>
        )}
      </div>

      {items.length > 0 && (
        <div className="fixed bottom-4 left-1/2 -translate-x-1/2 w-full max-w-[430px] px-4 z-20">
          <div className="bg-white rounded-2xl shadow-lg flex items-center px-3 py-2 gap-3">
            <div className="flex-1">
              <div className="text-[11px] text-slate-500 uppercase">Итого</div>
              <div className="text-sm font-semibold text-slate-900">{total.toFixed(0)} ₽</div>
            </div>
            <button
              type="button"
              disabled={submitDisabled}
              onClick={needsRegistration ? handleRegisterContact : handleSubmit}
              className={
                'flex-[2] text-sm font-semibold py-2 rounded-xl text-center transition-colors ' +
                (submitDisabled
                  ? 'bg-slate-300 text-slate-500 cursor-not-allowed'
                  : 'bg-slate-900 text-white hover:bg-slate-800')
              }
            >
              {needsRegistration
                ? registeringContact
                  ? 'РЕГИСТРАЦИЯ...'
                  : 'ЗАРЕГИСТРИРОВАТЬСЯ'
                : submitting
                  ? 'Отправка...'
                  : 'ЗАКАЗАТЬ'}
            </button>
          </div>
          {needsRegistration && (
            <div className="mt-2 rounded-2xl bg-amber-50 px-3 py-2 text-[11px] text-amber-800 shadow-sm border border-amber-100">
              Это необходимо, чтобы мы могли принять заказ и связаться по доставке.
            </div>
          )}
        </div>
      )}
    </MiniAppShell>
  );
}

function AddressInput({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) {
  return (
    <div>
      <label className="block text-[10px] font-medium text-slate-500 mb-1 uppercase tracking-wide">
        {label}
      </label>
      <input
        type="text"
        className="w-full rounded-xl border border-slate-200 px-2 py-2 text-sm text-center placeholder:text-slate-300"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
