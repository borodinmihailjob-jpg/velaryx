import { useEffect, useState } from 'react';
import { apiRequest } from '../api';
import { BrandMark, GoldButton, InkButton, ParchmentCard, Shell } from '../components/common/index.jsx';

function browserTimezone() {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
}

function toTimeInputValue(rawValue) {
  if (!rawValue) return '12:00';
  const source = String(rawValue).trim();
  const parts = source.split(':');
  if (parts.length >= 2) {
    const hh = String(parts[0]).padStart(2, '0').slice(0, 2);
    const mm = String(parts[1]).padStart(2, '0').slice(0, 2);
    return `${hh}:${mm}`;
  }
  return '12:00';
}

function defaultBirthForm() {
  return {
    birth_date: '',
    birth_time: '12:00',
    birth_place: '',
    latitude: '',
    longitude: '',
    timezone: browserTimezone(),
  };
}

export default function OnboardingScreen({ mode = 'create', onComplete, onBack }) {
  const isEditMode = mode === 'edit';
  const [form, setForm] = useState(() => defaultBirthForm());
  const [loading, setLoading] = useState(false);
  const [loadingProfile, setLoadingProfile] = useState(isEditMode);
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');

  useEffect(() => {
    if (!isEditMode) return undefined;

    let active = true;
    setLoadingProfile(true);
    setError('');
    setInfo('');

    apiRequest('/v1/natal/profile/latest')
      .then((profile) => {
        if (!active) return;
        setForm({
          birth_date: String(profile?.birth_date || ''),
          birth_time: toTimeInputValue(profile?.birth_time),
          birth_place: String(profile?.birth_place || ''),
          latitude: String(profile?.latitude ?? ''),
          longitude: String(profile?.longitude ?? ''),
          timezone: String(profile?.timezone || browserTimezone()),
        });
        setInfo('Текущие данные загружены. Обновите поля и сохраните.');
      })
      .catch((e) => {
        if (!active) return;
        setInfo(String(e?.message || 'Не удалось загрузить профиль. Заполните форму вручную.'));
      })
      .finally(() => {
        if (active) setLoadingProfile(false);
      });

    return () => {
      active = false;
    };
  }, [isEditMode]);

  const setField = (key, value) => {
    setError('');
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const canSubmit =
    Boolean(form.birth_date) &&
    Boolean(form.birth_time) &&
    Boolean(form.birth_place.trim()) &&
    Number.isFinite(Number(form.latitude)) &&
    Number.isFinite(Number(form.longitude)) &&
    Boolean(form.timezone.trim());

  const submit = async (event) => {
    event.preventDefault();
    if (!canSubmit || loading) return;

    setLoading(true);
    setError('');
    try {
      const profile = await apiRequest('/v1/natal/profile', {
        method: 'POST',
        body: JSON.stringify({
          birth_date: form.birth_date,
          birth_time: form.birth_time || '12:00',
          birth_place: form.birth_place.trim(),
          latitude: Number(form.latitude),
          longitude: Number(form.longitude),
          timezone: form.timezone.trim() || 'UTC',
        }),
      });

      await apiRequest('/v1/natal/calculate', {
        method: 'POST',
        body: JSON.stringify({ profile_id: profile.id }),
      });

      localStorage.setItem('onboarding_complete', '1');
      onComplete();
    } catch (e) {
      setError(String(e?.message || e || 'Не удалось сохранить профиль'));
    } finally {
      setLoading(false);
    }
  };

  const content = (
    <div className="screen">
      {!isEditMode ? (
        <div className="header-row">
          <div className="brand-mark"><BrandMark /></div>
          <div>
            <h1 style={{ fontFamily: 'Cinzel, serif', fontSize: 24, margin: 0 }}>Velaryx</h1>
            <p style={{ margin: 0, fontSize: 12, color: 'var(--smoke-600)' }}>
              Подготовим профиль для персональных расчётов
            </p>
          </div>
        </div>
      ) : null}

      <ParchmentCard>
        <h2 style={{ fontFamily: 'Cinzel, serif', fontSize: 18, marginBottom: 6 }}>
          {isEditMode ? 'Данные рождения' : 'Первичная настройка'}
        </h2>
        <p className="muted-text">
          Укажите дату, время и место рождения. Эти данные нужны для натальной карты и будущих модулей.
        </p>
        {info ? <div className="info-banner">{info}</div> : null}
        {error ? <div className="error-banner">{error}</div> : null}

        <form onSubmit={submit} className="form-grid" style={{ marginTop: 12 }}>
          <label className="field-label">
            Дата рождения
            <input
              type="date"
              className="input-field"
              value={form.birth_date}
              onChange={(e) => setField('birth_date', e.target.value)}
            />
          </label>

          <label className="field-label">
            Время рождения
            <input
              type="time"
              className="input-field"
              value={form.birth_time}
              onChange={(e) => setField('birth_time', e.target.value)}
            />
          </label>

          <label className="field-label">
            Место рождения
            <input
              className="input-field"
              value={form.birth_place}
              onChange={(e) => setField('birth_place', e.target.value)}
              placeholder="Город, страна"
            />
          </label>

          <div className="row-2">
            <label className="field-label">
              Широта
              <input
                className="input-field"
                value={form.latitude}
                onChange={(e) => setField('latitude', e.target.value)}
                placeholder="55.7558"
                inputMode="decimal"
              />
            </label>
            <label className="field-label">
              Долгота
              <input
                className="input-field"
                value={form.longitude}
                onChange={(e) => setField('longitude', e.target.value)}
                placeholder="37.6173"
                inputMode="decimal"
              />
            </label>
          </div>

          <label className="field-label">
            Часовой пояс
            <input
              className="input-field"
              value={form.timezone}
              onChange={(e) => setField('timezone', e.target.value)}
              placeholder="Europe/Moscow"
            />
          </label>

          <div className="row-2" style={{ marginTop: 4 }}>
            {isEditMode ? <InkButton onClick={onBack}>Отмена</InkButton> : <span />}
            <GoldButton type="submit" loading={loading} disabled={!canSubmit || loading}>
              {isEditMode ? 'Сохранить' : 'Продолжить'}
            </GoldButton>
          </div>
        </form>

        {loadingProfile ? <p className="muted-text" style={{ marginTop: 12 }}>Загрузка профиля...</p> : null}
      </ParchmentCard>
    </div>
  );

  if (isEditMode) {
    return <Shell title="Профиль" sub="Редактирование данных рождения" onBack={onBack}>{content}</Shell>;
  }

  return content;
}
