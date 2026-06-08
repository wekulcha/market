import React, { useEffect, useState } from "react";
import {
  fetchRestaurant,
  patchRestaurant,
  uploadRestaurantCover,
  type RestaurantDetail,
} from "../../api/adminRestaurant";
import { BASE_URL } from "../../api/baseUrl";

interface Props {
  restaurantId: number;
}

function coverPreview(path: string | null | undefined): string {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  try {
    return new URL(BASE_URL, window.location.href).origin + (path.startsWith("/") ? path : `/${path}`);
  } catch {
    return path;
  }
}

export const AdminRestaurantSettingsTab: React.FC<Props> = ({ restaurantId }) => {
  const [detail, setDetail] = useState<RestaurantDetail | null>(null);
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [deliveryCutoff, setDeliveryCutoff] = useState("17:00");
  const [groupChatId, setGroupChatId] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  useEffect(() => {
    if (!restaurantId || Number.isNaN(restaurantId)) return;
    let cancelled = false;
    setLoading(true);
    void fetchRestaurant(restaurantId)
      .then((d) => {
        if (cancelled) return;
        setDetail(d);
        setName(d.name);
        setAddress(d.address);
        setDeliveryCutoff(d.ordersAcceptTo ?? "17:00");
        setGroupChatId(
          d.telegramGroupChatId != null ? String(d.telegramGroupChatId) : ""
        );
      })
      .catch(() => setErr("Не удалось загрузить данные магазина."))
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [restaurantId]);

  const save = async () => {
    if (!restaurantId) return;
    setSaving(true);
    setErr(null);
    setOk(null);
    try {
      const rawGroupId = groupChatId.trim();
      let parsedGroupId: number | null | undefined = undefined;
      if (rawGroupId !== "") {
        const n = Number(rawGroupId);
        if (!Number.isInteger(n)) {
          setErr("ID группы должен быть целым числом (обычно начинается с -100...).");
          return;
        }
        parsedGroupId = n;
      } else {
        parsedGroupId = null;
      }
      const next = await patchRestaurant(restaurantId, {
        name: name.trim(),
        address: address.trim(),
        workingHoursFrom: null,
        workingHoursTo: null,
        ordersAcceptFrom: null,
        ordersAcceptTo: deliveryCutoff.trim() || "17:00",
        telegramGroupChatId: parsedGroupId,
      });
      setDetail(next);
      setOk("Сохранено");
    } catch {
      setErr("Не удалось сохранить.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-white rounded-3xl p-3 md:p-4 shadow-sm border border-slate-100 space-y-4">
      <div className="text-sm font-semibold text-slate-900">О магазине</div>
      {loading && <div className="text-xs text-slate-500">Загрузка…</div>}
      {err && <div className="text-[11px] text-red-500">{err}</div>}
      {ok && <div className="text-[11px] text-emerald-600">{ok}</div>}

      {!loading && (
        <>
          <div className="grid gap-3 lg:grid-cols-2">
            <div className="space-y-1">
              <label className="text-[11px] text-slate-600">Название</label>
              <input
                type="text"
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <label className="text-[11px] text-slate-600">Адрес / как найти</label>
              <input
                type="text"
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
              />
            </div>
          </div>

          <div className="grid gap-3 xl:grid-cols-2">
            <div className="space-y-2 rounded-2xl border border-slate-100 p-3 bg-slate-50/80">
              <div className="text-[11px] font-semibold text-slate-800">Дедлайн доставки сегодня</div>
              <div>
                <label className="text-[10px] text-slate-500">Время</label>
                <input
                  className="w-full rounded-xl border border-slate-200 px-2 py-1.5 text-sm"
                  placeholder="17:00"
                  value={deliveryCutoff}
                  onChange={(e) => setDeliveryCutoff(e.target.value)}
                />
              </div>
              <p className="text-[10px] text-slate-500">
                Заказы до этого времени доставляем сегодня, после него — завтра. Формат ЧЧ:ММ по Москве.
              </p>
            </div>
          </div>

          <div className="grid gap-3 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
            <div className="space-y-1">
              <label className="text-[11px] text-slate-600">
                Telegram Group Chat ID для заказов
              </label>
              <input
                type="text"
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
                placeholder="3982157166"
                value={groupChatId}
                onChange={(e) => setGroupChatId(e.target.value)}
              />
              <p className="text-[10px] text-slate-500">
                Введите ID группы для уведомлений о заказах.
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row lg:flex-col xl:flex-row items-start">
              <div className="w-24 h-24 rounded-2xl bg-slate-100 overflow-hidden flex-shrink-0 border border-slate-100">
                {detail?.imageLink ? (
                  <img src={coverPreview(detail.imageLink)} alt="" className="w-full h-full object-cover" />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-[10px] text-slate-400 p-1 text-center">
                    нет обложки
                  </div>
                )}
              </div>
              <div className="flex-1 min-w-0 space-y-1">
                <label className="text-[11px] text-slate-600">Обложка (JPG, PNG)</label>
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/jpg"
                  disabled={uploading}
                  className="text-[11px] w-full"
                  onChange={async (e) => {
                    const file = e.target.files?.[0];
                    if (!file || !restaurantId) return;
                    setErr(null);
                    setUploading(true);
                    try {
                      const path = await uploadRestaurantCover(restaurantId, file);
                      const next = await patchRestaurant(restaurantId, { imageLink: path });
                      setDetail(next);
                    } catch {
                      setErr("Не удалось загрузить фото.");
                    } finally {
                      setUploading(false);
                      e.target.value = "";
                    }
                  }}
                />
                {uploading && <span className="text-[10px] text-slate-500">Загрузка…</span>}
              </div>
            </div>
          </div>

          <button
            type="button"
            disabled={saving || !name.trim() || !address.trim()}
            onClick={() => void save()}
            className="w-full rounded-2xl bg-slate-900 text-white text-xs font-semibold py-2.5 disabled:opacity-50"
          >
            {saving ? "Сохранение…" : "Сохранить настройки"}
          </button>
        </>
      )}
    </div>
  );
};
