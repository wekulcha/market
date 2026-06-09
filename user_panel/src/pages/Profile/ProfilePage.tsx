import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchMyOrders } from '../../api/orders';
import { fetchCurrentUser, updateUserProfile } from '../../api/users';
import { logUserActivity } from '../../api/activity';
import { MARKET_BRAND_NAME } from '../../config/market';
import { OrderCard } from '../../components/orders/OrderCard';
import { useAuth } from '../../context/AuthContext';
import { Header } from '../../layout/Header';
import { MiniAppShell } from '../../layout/MiniAppShell';
import type { OrderStatus, UserOrder } from '../../types/order';
import type { User } from '../../types/user';
import {
  MARKET_STREETS,
  formatLocationParts,
  parseLocationParts,
} from '../../utils/locationFormat';
import {
  displayPhone,
  isRegisteredPhone,
  isRussianPhone,
  phoneToRussianLocal10,
  russianLocal10ToStorage,
} from '../../utils/phoneFormat';

const ACTIVE_STATUSES = new Set<OrderStatus>(['CREATED', 'ACCEPTED', 'COOKING', 'DELIVERY']);

export function ProfilePage() {
  const navigate = useNavigate();
  const { currentUser, authError, authReady, reloadAuth } = useAuth();
  const [street, setStreet] = useState<string>(MARKET_STREETS[0]);
  const [house, setHouse] = useState('');
  const [entrance, setEntrance] = useState('');
  const [floor, setFloor] = useState('');
  const [apartment, setApartment] = useState('');
  const [phoneLocal10, setPhoneLocal10] = useState('');
  const [editingPhone, setEditingPhone] = useState(false);
  const [editingAddress, setEditingAddress] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [saveProfileMsg, setSaveProfileMsg] = useState<string | null>(null);
  const [user, setUser] = useState<User | null>(currentUser);
  const [orders, setOrders] = useState<UserOrder[]>([]);
  const [loadingProfile, setLoadingProfile] = useState(false);
  const [loadingOrders, setLoadingOrders] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [ordersError, setOrdersError] = useState<string | null>(null);

  useEffect(() => {
    if (!authReady) return;

    if (!currentUser) {
      setUser(null);
      setOrders([]);
      setProfileError(null);
      setOrdersError(null);
      setLoadingProfile(false);
      setLoadingOrders(false);
      return;
    }

    let cancelled = false;
    setUser(currentUser);
    setLoadingProfile(true);
    setLoadingOrders(true);
    setProfileError(null);
    setOrdersError(null);

    void Promise.allSettled([fetchCurrentUser(), fetchMyOrders()])
      .then(([userResult, ordersResult]) => {
        if (cancelled) return;

        if (userResult.status === 'fulfilled') {
          setUser(userResult.value);
        } else {
          setProfileError('Не удалось обновить данные профиля.');
        }

        if (ordersResult.status === 'fulfilled') {
          setOrders(ordersResult.value);
        } else {
          setOrders([]);
          setOrdersError('Не удалось загрузить заказы.');
        }
      })
      .finally(() => {
        if (cancelled) return;
        setLoadingProfile(false);
        setLoadingOrders(false);
      });

    return () => {
      cancelled = true;
    };
  }, [authReady, currentUser]);

  useEffect(() => {
    const p = parseLocationParts(user?.address ?? null);
    setStreet(p.street);
    setHouse(p.house);
    setEntrance(p.entrance);
    setFloor(p.floor);
    setApartment(p.apartment);
  }, [user?.address]);

  useEffect(() => {
    setPhoneLocal10(phoneToRussianLocal10(user?.phone ?? null));
  }, [user?.phone]);

  useEffect(() => {
    if (!authReady || !currentUser) return;
    logUserActivity('profile_open');
  }, [authReady, currentUser]);

  const activeOrders = useMemo(
    () => orders.filter((order) => ACTIVE_STATUSES.has(order.status)),
    [orders]
  );
  const needsRussianPhoneForOrder = Boolean(
    user && isRegisteredPhone(user.phone) && !isRussianPhone(user.phone) && phoneLocal10.length !== 10
  );

  const saveAddress = async () => {
    if (!user?.id) return;
    setSavingProfile(true);
    setSaveProfileMsg(null);
    try {
      const hasDetails = house.trim() || entrance.trim() || floor.trim() || apartment.trim();
      const addr = hasDetails ? formatLocationParts(street, house, entrance, floor, apartment).trim() : null;
      const next = await updateUserProfile(user.id, { address: addr });
      setUser(next);
      setSaveProfileMsg('Сохранено.');
      setEditingAddress(false);
      void reloadAuth();
    } catch {
      setSaveProfileMsg('Не удалось сохранить.');
    } finally {
      setSavingProfile(false);
    }
  };

  const savePhone = async () => {
    if (!user?.id) return;
    const normalized = russianLocal10ToStorage(phoneLocal10);
    if (!normalized) {
      setSaveProfileMsg('Введите 10 цифр российского номера после +7.');
      return;
    }

    setSavingProfile(true);
    setSaveProfileMsg(null);
    try {
      const next = await updateUserProfile(user.id, { phone: normalized });
      setUser(next);
      setSaveProfileMsg('Телефон сохранён.');
      setEditingPhone(false);
      void reloadAuth();
    } catch {
      setSaveProfileMsg('Не удалось сохранить телефон.');
    } finally {
      setSavingProfile(false);
    }
  };

  return (
    <MiniAppShell>
      <Header
        title="Профиль"
        showSearch={false}
        showBack
        onBackClick={() => navigate(-1)}
        onHomeClick={() => navigate('/catalog')}
      />
      <main className="mt-4 space-y-4 pb-20">
        {!authReady && (
          <section className="bg-slate-50 rounded-2xl p-3 shadow-sm border border-slate-100">
            <div className="text-sm text-slate-600">Проверяем вход в Telegram…</div>
          </section>
        )}

        {authReady && !currentUser && (
          <section className="bg-amber-50 rounded-2xl p-3 shadow-sm border border-amber-100 space-y-3">
            <div className="text-sm font-semibold text-amber-900">Вход в аккаунт</div>
            <div className="text-xs text-amber-700">
              {authError ?? `Откройте мини-приложение из Telegram через кнопку в боте ${MARKET_BRAND_NAME}.`}
            </div>
            <button
              type="button"
              onClick={reloadAuth}
              className="rounded-xl bg-amber-600 px-3 py-2 text-xs font-semibold text-white hover:bg-amber-700 transition-colors"
            >
              Повторить вход
            </button>
          </section>
        )}

        {currentUser && (
          <section className="bg-white rounded-2xl p-3 shadow-sm space-y-2">
            <div className="text-sm font-semibold text-slate-900">Ваши данные</div>
            {loadingProfile && <div className="text-xs text-slate-500">Обновляем профиль...</div>}
            {profileError && <div className="text-xs text-amber-600">{profileError}</div>}
            {saveProfileMsg && <div className="text-xs text-emerald-600">{saveProfileMsg}</div>}
            {user && (
              <div className="mt-2 space-y-3 text-sm">
                <div className="flex justify-between gap-2">
                  <span className="text-slate-500 shrink-0">Telegram ID</span>
                  <span className="font-mono text-slate-800 text-right">{user.telegram_id ?? '—'}</span>
                </div>
                <div className="flex justify-between gap-2">
                  <span className="text-slate-500">Username</span>
                  <span className="text-slate-800 text-right">{user.username || '—'}</span>
                </div>
                <div className="space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <label className="text-xs text-slate-500 pt-0.5">
                      Телефон
                    </label>
                    <div className="flex shrink-0">
                      {!editingPhone ? (
                        <button
                          type="button"
                          onClick={() => {
                            setSaveProfileMsg(null);
                            setEditingPhone(true);
                          }}
                          className="p-2 rounded-xl text-slate-500 hover:bg-slate-100 transition-colors"
                          aria-label="Редактировать телефон"
                        >
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
                            />
                          </svg>
                        </button>
                      ) : (
                        <button
                          type="button"
                          disabled={savingProfile}
                          onClick={() => void savePhone()}
                          className="p-2 rounded-xl text-emerald-600 hover:bg-emerald-50 transition-colors disabled:opacity-50"
                          aria-label="Сохранить телефон"
                        >
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                        </button>
                      )}
                    </div>
                  </div>
                  {editingPhone ? (
                    <div className="flex rounded-xl border border-slate-200 overflow-hidden bg-white">
                      <span className="px-3 py-2 text-sm bg-slate-100 text-slate-600 border-r border-slate-200 select-none">
                        +7
                      </span>
                      <input
                        type="tel"
                        inputMode="numeric"
                        autoComplete="tel-national"
                        className="flex-1 min-w-0 px-3 py-2 text-sm outline-none"
                        placeholder="9001234567"
                        value={phoneLocal10}
                        onChange={(e) => {
                          setPhoneLocal10(e.target.value.replace(/\D/g, '').slice(0, 10));
                          setSaveProfileMsg(null);
                        }}
                      />
                    </div>
                  ) : (
                    <input
                      className="w-full rounded-xl border border-slate-200 px-2 py-2 text-sm bg-slate-50 text-slate-600"
                      value={displayPhone(user.phone)}
                      readOnly
                    />
                  )}
                  {needsRussianPhoneForOrder && (
                    <div className="rounded-xl border border-amber-100 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                      Для заказа нужно указать и сохранить российский номер телефона.
                    </div>
                  )}
                </div>
                <div className="space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <label className="text-xs text-slate-500 pt-0.5">
                      Адрес доставки
                    </label>
                    <div className="flex shrink-0">
                      {!editingAddress ? (
                        <button
                          type="button"
                          onClick={() => {
                            setSaveProfileMsg(null);
                            setEditingAddress(true);
                          }}
                          className="p-2 rounded-xl text-slate-500 hover:bg-slate-100 transition-colors"
                          aria-label="Редактировать адрес"
                        >
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"
                            />
                          </svg>
                        </button>
                      ) : (
                        <button
                          type="button"
                          disabled={savingProfile}
                          onClick={() => void saveAddress()}
                          className="p-2 rounded-xl text-emerald-600 hover:bg-emerald-50 transition-colors disabled:opacity-50"
                          aria-label="Сохранить адрес"
                        >
                          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                          </svg>
                        </button>
                      )}
                    </div>
                  </div>
                  <select
                    className="w-full rounded-xl border border-slate-200 px-2 py-2 text-sm bg-white disabled:bg-slate-50 disabled:text-slate-600"
                    value={street}
                    disabled={!editingAddress}
                    onChange={(e) => {
                      setStreet(e.target.value);
                      setSaveProfileMsg(null);
                    }}
                  >
                    {MARKET_STREETS.map((streetOption) => (
                      <option key={streetOption} value={streetOption}>
                        {streetOption}
                      </option>
                    ))}
                  </select>
                  <div className="grid grid-cols-2 gap-2">
                    <ProfileAddressInput label="Дом" value={house} readOnly={!editingAddress} onChange={setHouse} />
                    <ProfileAddressInput label="Подъезд" value={entrance} readOnly={!editingAddress} onChange={setEntrance} />
                    <ProfileAddressInput label="Этаж" value={floor} readOnly={!editingAddress} onChange={setFloor} />
                    <ProfileAddressInput label="Квартира" value={apartment} readOnly={!editingAddress} onChange={setApartment} />
                  </div>
                </div>
              </div>
            )}
          </section>
        )}

        <section className="bg-white rounded-2xl p-3 shadow-sm space-y-2">
          <div className="text-sm font-semibold text-slate-900">Текущий заказ</div>
          {!currentUser && (
            <div className="text-xs text-slate-500">После авторизации здесь появится активный заказ.</div>
          )}
          {ordersError && <div className="text-xs text-amber-600">{ordersError}</div>}
          {currentUser && loadingOrders && (
            <div className="text-xs text-slate-500">Загружаем текущий заказ...</div>
          )}
          {currentUser && !loadingOrders && activeOrders.length === 0 && (
            <div className="text-xs text-slate-500">Сейчас активных заказов нет.</div>
          )}
          {currentUser && !loadingOrders && activeOrders.length > 0 && (
            <OrderCard
              order={activeOrders[0]}
              onChanged={() => {
                void fetchMyOrders()
                  .then((list) => setOrders(list))
                  .catch(() => {});
              }}
            />
          )}
        </section>

        {currentUser && (
          <section className="bg-white rounded-2xl p-3 shadow-sm">
            <button
              type="button"
              className="w-full flex items-center justify-between py-1 text-sm text-slate-800 hover:bg-slate-50 rounded-lg px-1 transition-colors"
              onClick={() => navigate('/orders/history')}
            >
              <span>История заказов</span>
              <span className="text-slate-400 text-xs">›</span>
            </button>
          </section>
        )}

        <section className="bg-white rounded-2xl p-3 shadow-sm space-y-1">
          <button
            type="button"
            className="w-full flex items-center justify-between py-2 text-sm text-slate-800 hover:bg-slate-50 rounded-lg px-2 transition-colors"
            onClick={() => alert('Политика конфиденциальности: заглушка')}
          >
            <span>Политика конфиденциальности</span>
            <span className="text-slate-400 text-xs">›</span>
          </button>
          <button
            type="button"
            className="w-full flex items-center justify-between py-2 text-sm text-slate-800 hover:bg-slate-50 rounded-lg px-2 transition-colors"
            onClick={() => alert('Пользовательское соглашение: заглушка')}
          >
            <span>Пользовательское соглашение</span>
            <span className="text-slate-400 text-xs">›</span>
          </button>
        </section>
      </main>
    </MiniAppShell>
  );
}

function ProfileAddressInput({
  label,
  value,
  readOnly,
  onChange,
}: {
  label: string;
  value: string;
  readOnly: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <div>
      <span className="text-[10px] text-slate-400 block mb-0.5">{label}</span>
      <input
        className="w-full rounded-xl border border-slate-200 px-2 py-1.5 text-sm text-center read-only:bg-slate-50 read-only:text-slate-600"
        value={value}
        readOnly={readOnly}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}
