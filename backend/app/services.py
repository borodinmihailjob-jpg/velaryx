from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from . import models
from .config import settings
from .astro_engine import calculate_natal_chart
from .security import expiry_after_days, generate_token
from .tarot_engine import build_seed, card_image_url, draw_cards, supported_spreads


def get_or_create_user(db: Session, tg_user_id: int) -> models.User:
    user = db.query(models.User).filter(models.User.tg_user_id == tg_user_id).first()
    if user:
        return user

    user = models.User(tg_user_id=tg_user_id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_birth_profile(
    db: Session,
    user_id: int,
    birth_date,
    birth_time,
    birth_place: str,
    latitude: float,
    longitude: float,
    timezone_name: str,
) -> models.BirthProfile:
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        raise HTTPException(status_code=422, detail="Invalid timezone")

    profile = models.BirthProfile(
        user_id=user_id,
        birth_date=birth_date,
        birth_time=birth_time,
        birth_place=birth_place,
        latitude=latitude,
        longitude=longitude,
        timezone=timezone_name,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def calculate_and_store_natal_chart(db: Session, user_id: int, profile_id) -> models.NatalChart:
    profile = (
        db.query(models.BirthProfile)
        .filter(models.BirthProfile.id == profile_id, models.BirthProfile.user_id == user_id)
        .first()
    )
    if not profile:
        raise HTTPException(status_code=404, detail="Birth profile not found")

    payload = calculate_natal_chart(profile)
    sun_sign = payload["planets"]["sun"]["sign"]
    moon_sign = payload["planets"]["moon"]["sign"]
    rising_sign = payload["rising_sign"]

    chart = models.NatalChart(
        profile_id=profile.id,
        sun_sign=sun_sign,
        moon_sign=moon_sign,
        rising_sign=rising_sign,
        chart_payload=payload,
    )
    db.add(chart)
    db.commit()
    db.refresh(chart)
    return chart


def get_latest_natal_chart(db: Session, user_id: int) -> models.NatalChart:
    chart = (
        db.query(models.NatalChart)
        .join(models.BirthProfile, models.BirthProfile.id == models.NatalChart.profile_id)
        .filter(models.BirthProfile.user_id == user_id)
        .order_by(models.NatalChart.created_at.desc())
        .first()
    )
    if not chart:
        raise HTTPException(status_code=404, detail="Natal chart not found")
    return chart


def _natal_sections_from_payload(chart_payload: dict) -> list[dict]:
    interpretation = chart_payload.get("interpretation") if isinstance(chart_payload, dict) else {}
    if not isinstance(interpretation, dict):
        interpretation = {}

    sections: list[dict] = []
    summary = interpretation.get("summary")
    if summary:
        sections.append({"title": "Общий вектор", "text": summary, "icon": "✨"})

    sun_text = interpretation.get("sun_explanation")
    if sun_text:
        sections.append({"title": "Солнце", "text": sun_text, "icon": "☀️"})

    moon_text = interpretation.get("moon_explanation")
    if moon_text:
        sections.append({"title": "Луна", "text": moon_text, "icon": "🌙"})

    rising_text = interpretation.get("rising_explanation")
    if rising_text:
        sections.append({"title": "Асцендент", "text": rising_text, "icon": "⬆️"})

    key_aspects = interpretation.get("key_aspects")
    if isinstance(key_aspects, list) and key_aspects:
        sections.append(
            {
                "title": "Ключевые аспекты",
                "text": " • ".join(str(item) for item in key_aspects[:5]),
                "icon": "🔭",
            }
        )

    return sections


def get_full_natal_chart(db: Session, user_id: int) -> tuple[models.NatalChart, list[dict], str | None]:
    chart = get_latest_natal_chart(db=db, user_id=user_id)
    sections = _natal_sections_from_payload(chart.chart_payload)
    wheel_chart_url = None
    payload = chart.chart_payload if isinstance(chart.chart_payload, dict) else {}
    candidate = payload.get("wheel_chart_url")
    if isinstance(candidate, str) and candidate.strip():
        wheel_chart_url = candidate.strip()
    return chart, sections, wheel_chart_url


def _build_daily_summary(sun_sign: str, moon_sign: str, rising_sign: str, day_seed: int) -> tuple[int, str, dict]:
    energy_score = 45 + (day_seed % 55)
    mood = ["баланс", "прорыв", "рефлексия", "инициатива", "забота"][day_seed % 5]
    focus = ["отношениях", "карьере", "финансах", "здоровье", "обучении"][day_seed % 5]

    summary = (
        f"Сегодня акцент на {focus}: энергия {energy_score}/100. "
        f"Солнечный знак {sun_sign}, Луна в {moon_sign}, Асцендент {rising_sign}. "
        f"Режим дня: {mood}."
    )
    payload = {
        "sun_sign": sun_sign,
        "moon_sign": moon_sign,
        "rising_sign": rising_sign,
        "mood": mood,
        "focus": focus,
    }
    return energy_score, summary, payload


def get_or_create_daily_forecast(db: Session, user_id: int, forecast_date: date) -> models.DailyForecast:
    existing = (
        db.query(models.DailyForecast)
        .filter(models.DailyForecast.user_id == user_id, models.DailyForecast.forecast_date == forecast_date)
        .first()
    )
    if existing:
        return existing

    chart = get_latest_natal_chart(db, user_id)
    day_seed = (forecast_date.toordinal() + user_id) % 1000
    energy_score, summary, payload = _build_daily_summary(
        sun_sign=chart.sun_sign,
        moon_sign=chart.moon_sign,
        rising_sign=chart.rising_sign,
        day_seed=day_seed,
    )

    forecast = models.DailyForecast(
        user_id=user_id,
        forecast_date=forecast_date,
        energy_score=energy_score,
        summary=summary,
        payload=payload,
    )
    db.add(forecast)
    db.commit()
    db.refresh(forecast)
    return forecast


def build_forecast_story_slides(chart: models.NatalChart, forecast: models.DailyForecast) -> list[dict]:
    interpretation = {}
    if isinstance(chart.chart_payload, dict):
        interpretation = chart.chart_payload.get("interpretation", {}) or {}

    slides = [
        {
            "title": "Энергия дня",
            "body": f"{forecast.summary}",
            "badge": f"{forecast.energy_score}/100",
        },
        {
            "title": "Вектор натала",
            "body": str(interpretation.get("summary") or "Опирайтесь на свои сильные качества и ритм."),
            "badge": f"{chart.sun_sign} • {chart.moon_sign}",
        },
    ]

    key_aspects = interpretation.get("key_aspects")
    if isinstance(key_aspects, list) and key_aspects:
        slides.append(
            {
                "title": "Ключевой аспект",
                "body": str(key_aspects[0]),
                "badge": chart.rising_sign,
            }
        )

    slides.append(
        {
            "title": "Практика дня",
            "body": "Выберите 1 задачу с максимальным эффектом и завершите ее до вечера.",
            "badge": str(forecast.payload.get("focus", "фокус")),
        }
    )
    return slides


def _sign_compatibility(inviter_sign: str, invitee_sign: str) -> tuple[int, list[str], list[str]]:
    if inviter_sign == invitee_sign:
        return (
            88,
            ["Похожий жизненный темп", "Легко понимать мотивацию друг друга"],
            ["Риск зациклиться в одном паттерне", "Нужны свежие впечатления извне"],
        )

    supportive_pairs = {
        ("Aries", "Leo"),
        ("Aries", "Sagittarius"),
        ("Taurus", "Virgo"),
        ("Taurus", "Capricorn"),
        ("Gemini", "Libra"),
        ("Gemini", "Aquarius"),
        ("Cancer", "Scorpio"),
        ("Cancer", "Pisces"),
        ("Leo", "Sagittarius"),
        ("Virgo", "Capricorn"),
        ("Libra", "Aquarius"),
        ("Scorpio", "Pisces"),
    }
    if (inviter_sign, invitee_sign) in supportive_pairs or (invitee_sign, inviter_sign) in supportive_pairs:
        return (
            81,
            ["Естественная взаимная поддержка", "Хорошая эмоциональная синхронизация"],
            ["Важно не замалчивать ожидания", "Сохранять личные границы"],
        )

    return (
        69,
        ["Притяжение через различия", "Потенциал личного роста в паре"],
        ["Потребуется ясная коммуникация", "Нужно договариваться о темпе и приоритетах"],
    )


def draw_tarot_reading(
    db: Session,
    user_id: int,
    spread_type: str,
    question: str | None,
) -> models.TarotSession:
    if spread_type not in supported_spreads():
        raise HTTPException(status_code=422, detail=f"Unsupported spread_type: {spread_type}")

    seed = build_seed(
        user_id=user_id,
        spread_type=spread_type,
        question=question,
        salt=datetime.now(timezone.utc).isoformat(),
    )
    cards_payload = draw_cards(spread_type=spread_type, seed=seed)

    session = models.TarotSession(
        user_id=user_id,
        spread_type=spread_type,
        question=question,
        seed=seed,
    )
    db.add(session)
    db.flush()

    for card in cards_payload:
        db.add(
            models.TarotCard(
                session_id=session.id,
                position=card["position"],
                slot_label=card["slot_label"],
                card_name=card["card_name"],
                is_reversed=card["is_reversed"],
                meaning=card["meaning"],
            )
        )

    db.commit()
    db.refresh(session)
    return session


def get_tarot_session(db: Session, user_id: int, session_id) -> models.TarotSession:
    session = (
        db.query(models.TarotSession)
        .options(joinedload(models.TarotSession.cards))
        .filter(models.TarotSession.id == session_id, models.TarotSession.user_id == user_id)
        .first()
    )
    if not session:
        raise HTTPException(status_code=404, detail="Tarot session not found")
    return session


def build_combo_insight(
    db: Session,
    user_id: int,
    question: str | None,
    spread_type: str,
) -> tuple[models.NatalChart, models.DailyForecast, models.TarotSession, list[dict], str]:
    chart = get_latest_natal_chart(db=db, user_id=user_id)
    forecast = get_or_create_daily_forecast(db=db, user_id=user_id, forecast_date=date.today())

    session = draw_tarot_reading(
        db=db,
        user_id=user_id,
        spread_type=spread_type,
        question=question,
    )
    session_with_cards = get_tarot_session(db=db, user_id=user_id, session_id=session.id)
    sorted_cards = sorted(session_with_cards.cards, key=lambda c: c.position)

    tarot_cards_payload = [
        {
            "position": card.position,
            "slot_label": card.slot_label,
            "card_name": card.card_name,
            "is_reversed": card.is_reversed,
            "meaning": card.meaning,
            "image_url": card_image_url(card.card_name),
            "provider": settings.tarot_provider,
        }
        for card in sorted_cards
    ]

    first_card = tarot_cards_payload[0]["card_name"] if tarot_cards_payload else "карты"
    natal_summary = chart.chart_payload.get("interpretation", {}).get("summary", "")
    combined_advice = (
        f"{natal_summary} Сегодняшний фокус: {forecast.payload.get('focus', 'баланс')}. "
        f"Ключ карты дня: {first_card}. Действуйте через маленькие шаги и фиксируйте результат."
    ).strip()

    return chart, forecast, session_with_cards, tarot_cards_payload, combined_advice


def create_compat_invite(db: Session, inviter_user_id: int, ttl_days: int, max_uses: int) -> models.CompatInvite:
    invite = models.CompatInvite(
        token=generate_token("comp_"),
        inviter_user_id=inviter_user_id,
        expires_at=expiry_after_days(ttl_days),
        used=False,
        max_uses=max_uses,
        use_count=0,
    )
    db.add(invite)
    db.commit()
    db.refresh(invite)
    return invite


def start_compat_session(db: Session, invite_token: str, invitee_user_id: int) -> tuple[models.CompatSession, models.CompatResult]:
    invite = db.query(models.CompatInvite).filter(models.CompatInvite.token == invite_token).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")

    now = datetime.now(timezone.utc)
    invite_expires = invite.expires_at
    if invite_expires.tzinfo is None:
        invite_expires = invite_expires.replace(tzinfo=timezone.utc)

    if invite_expires < now:
        raise HTTPException(status_code=410, detail="Invite expired")

    if invite.use_count >= invite.max_uses:
        raise HTTPException(status_code=409, detail="Invite already exhausted")

    invite.use_count += 1
    invite.used = invite.use_count >= invite.max_uses

    session = models.CompatSession(
        inviter_user_id=invite.inviter_user_id,
        invitee_user_id=invitee_user_id,
        invite_token=invite.token,
    )
    db.add(session)
    db.flush()

    inviter_chart = (
        db.query(models.NatalChart)
        .join(models.BirthProfile, models.BirthProfile.id == models.NatalChart.profile_id)
        .filter(models.BirthProfile.user_id == invite.inviter_user_id)
        .order_by(models.NatalChart.created_at.desc())
        .first()
    )
    invitee_chart = (
        db.query(models.NatalChart)
        .join(models.BirthProfile, models.BirthProfile.id == models.NatalChart.profile_id)
        .filter(models.BirthProfile.user_id == invitee_user_id)
        .order_by(models.NatalChart.created_at.desc())
        .first()
    )

    if inviter_chart and invitee_chart:
        score, strengths, growth_areas = _sign_compatibility(inviter_chart.sun_sign, invitee_chart.sun_sign)
    else:
        seed = (invite.inviter_user_id + invitee_user_id + invite.use_count) % 100
        score = max(45, seed)
        strengths = ["Есть потенциал взаимного интереса", "Пара может быстро находить общую цель"]
        growth_areas = ["Важна регулярная обратная связь", "Нужны договоренности по ожиданиям"]

    detail_payload = {
        "chemistry": max(40, score - 5),
        "communication": min(99, score + 3),
        "stability": max(35, score - 8),
        "strengths": strengths,
        "growth_areas": growth_areas,
    }
    result = models.CompatResult(
        session_id=session.id,
        score=score,
        summary="Высокий потенциал, важен осознанный диалог и поддержка.",
        payload=detail_payload,
    )
    db.add(result)
    db.commit()
    db.refresh(session)
    db.refresh(result)
    return session, result


def create_wishlist(
    db: Session,
    owner_user_id: int,
    title: str,
    slug: str,
    is_public: bool,
    cover_url: str | None,
) -> models.Wishlist:
    wishlist = models.Wishlist(
        owner_user_id=owner_user_id,
        title=title,
        slug=slug,
        is_public=is_public,
        public_token=generate_token("wl_"),
        cover_url=cover_url,
    )
    db.add(wishlist)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Slug already exists")
    db.refresh(wishlist)
    return wishlist


def add_wishlist_item(
    db: Session,
    user_id: int,
    wishlist_id,
    title: str,
    image_url: str | None,
    budget_cents: int | None,
) -> models.WishlistItem:
    wishlist = db.query(models.Wishlist).filter(models.Wishlist.id == wishlist_id).first()
    if not wishlist:
        raise HTTPException(status_code=404, detail="Wishlist not found")
    if wishlist.owner_user_id != user_id:
        raise HTTPException(status_code=403, detail="Not your wishlist")

    item = models.WishlistItem(
        wishlist_id=wishlist.id,
        title=title,
        image_url=image_url,
        budget_cents=budget_cents,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_public_wishlist(db: Session, public_token: str) -> models.Wishlist:
    wishlist = (
        db.query(models.Wishlist)
        .options(
            joinedload(models.Wishlist.items).joinedload(models.WishlistItem.reservations),
        )
        .filter(models.Wishlist.public_token == public_token, models.Wishlist.is_public.is_(True))
        .first()
    )
    if not wishlist:
        raise HTTPException(status_code=404, detail="Wishlist not found")
    return wishlist


def reserve_item(
    db: Session,
    public_token: str,
    item_id,
    reserver_tg_user_id: int | None,
    reserver_name: str | None,
) -> models.ItemReservation:
    wishlist = get_public_wishlist(db, public_token)
    item = (
        db.query(models.WishlistItem)
        .filter(models.WishlistItem.id == item_id, models.WishlistItem.wishlist_id == wishlist.id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    existing = (
        db.query(models.ItemReservation)
        .filter(models.ItemReservation.item_id == item.id, models.ItemReservation.active.is_(True))
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Item already reserved")

    reservation = models.ItemReservation(
        item_id=item.id,
        reserver_tg_user_id=reserver_tg_user_id,
        reserver_name=reserver_name,
        active=True,
    )
    db.add(reservation)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Item already reserved")
    db.refresh(reservation)
    return reservation
