import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional, List
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import aiosqlite

from database import init_db, get_db, ADMIN_IDS, DB_PATH

UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ==================== Models ====================

class UserOut(BaseModel):
    id: int
    telegram_id: int
    first_name: Optional[str]
    last_name: Optional[str]
    username: Optional[str]
    phone: Optional[str]

class ServiceBase(BaseModel):
    title: str
    short_description: Optional[str] = None
    description: Optional[str] = None
    price: int = 0
    duration_minutes: int = 60
    image_url: Optional[str] = None
    is_online: bool = True
    is_offline: bool = True
    is_active: bool = True
    payment_required: bool = False
    sort_order: int = 0

class ServiceCreate(ServiceBase):
    pass

class ServiceUpdate(BaseModel):
    title: Optional[str] = None
    short_description: Optional[str] = None
    description: Optional[str] = None
    price: Optional[int] = None
    duration_minutes: Optional[int] = None
    image_url: Optional[str] = None
    is_online: Optional[bool] = None
    is_offline: Optional[bool] = None
    is_active: Optional[bool] = None
    payment_required: Optional[bool] = None
    sort_order: Optional[int] = None

class ServiceOut(ServiceBase):
    id: int
    created_at: Optional[str]
    updated_at: Optional[str]

class SlotCreate(BaseModel):
    service_id: Optional[int] = None
    datetime_start: str
    datetime_end: str
    is_available: bool = True
    is_online: bool = False
    note: Optional[str] = None

class SlotOut(BaseModel):
    id: int
    service_id: Optional[int]
    datetime_start: str
    datetime_end: str
    is_available: bool
    is_online: bool
    note: Optional[str]

class BookingCreate(BaseModel):
    service_id: Optional[int] = None
    event_id: Optional[int] = None
    slot_id: Optional[int] = None
    datetime_start: str
    datetime_end: Optional[str] = None
    client_name: str
    client_phone: str
    client_comment: Optional[str] = None
    is_online: bool = False

class BookingOut(BaseModel):
    id: int
    service_id: Optional[int]
    event_id: Optional[int]
    datetime_start: str
    status: str
    client_name: Optional[str]
    client_phone: Optional[str]
    client_comment: Optional[str]
    is_online: bool
    payment_status: str
    created_at: str
    service_title: Optional[str] = None

class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    datetime_start: str
    datetime_end: Optional[str] = None
    place: Optional[str] = None
    is_online: bool = False
    price: int = 0
    max_participants: int = 0
    image_url: Optional[str] = None
    is_active: bool = True
    payment_required: bool = False

class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    datetime_start: Optional[str] = None
    datetime_end: Optional[str] = None
    place: Optional[str] = None
    is_online: Optional[bool] = None
    price: Optional[int] = None
    max_participants: Optional[int] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None
    payment_required: Optional[bool] = None

class EventOut(EventCreate):
    id: int
    created_at: Optional[str]
    current_participants: int = 0

class TelegramAuth(BaseModel):
    telegram_id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None

# ==================== App ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    print("✅ Database initialized")
    yield

app = FastAPI(title="Yulia Healer MiniApp API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# ==================== Helpers ====================

async def get_or_create_user(db: aiosqlite.Connection, tg_id: int, first_name: str = None, 
                              last_name: str = None, username: str = None) -> dict:
    cursor = await db.execute("SELECT * FROM users WHERE telegram_id = ?", (tg_id,))
    user = await cursor.fetchone()
    if user:
        return dict(user)
    await db.execute(
        "INSERT INTO users (telegram_id, first_name, last_name, username) VALUES (?, ?, ?, ?)",
        (tg_id, first_name, last_name, username)
    )
    await db.commit()
    cursor = await db.execute("SELECT * FROM users WHERE telegram_id = ?", (tg_id,))
    return dict(await cursor.fetchone())

def is_admin(telegram_id: int) -> bool:
    return telegram_id in ADMIN_IDS

async def require_admin(x_telegram_id: int = Header(..., alias="X-Telegram-Id")):
    if not is_admin(x_telegram_id):
        raise HTTPException(status_code=403, detail="Admin access required")
    return x_telegram_id

# ==================== Auth / Me ====================

@app.post("/api/auth")
async def auth_user(data: TelegramAuth):
    async with get_db() as db:
        user = await get_or_create_user(
            db, data.telegram_id, data.first_name, data.last_name, data.username
        )
        return {
            "user": user,
            "is_admin": is_admin(data.telegram_id)
        }

@app.get("/api/me")
async def get_me(x_telegram_id: int = Header(..., alias="X-Telegram-Id")):
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM users WHERE telegram_id = ?", (x_telegram_id,))
        user = await cursor.fetchone()
        if not user:
            raise HTTPException(404, "User not found")
        return {
            "user": dict(user),
            "is_admin": is_admin(x_telegram_id)
        }

# ==================== Services (Public) ====================

@app.get("/api/services", response_model=List[ServiceOut])
async def list_services(active_only: bool = True):
    async with get_db() as db:
        if active_only:
            cursor = await db.execute(
                "SELECT * FROM services WHERE is_active = 1 ORDER BY sort_order, id"
            )
        else:
            cursor = await db.execute("SELECT * FROM services ORDER BY sort_order, id")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

@app.get("/api/services/{service_id}", response_model=ServiceOut)
async def get_service(service_id: int):
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM services WHERE id = ?", (service_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(404, "Service not found")
        return dict(row)

# ==================== Services (Admin) ====================

@app.post("/api/admin/services", response_model=ServiceOut)
async def create_service(data: ServiceCreate, admin_id: int = Depends(require_admin)):
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO services 
               (title, short_description, description, price, duration_minutes,
                image_url, is_online, is_offline, is_active, payment_required, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data.title, data.short_description, data.description, data.price,
                data.duration_minutes, data.image_url,
                int(data.is_online), int(data.is_offline), int(data.is_active),
                int(data.payment_required), data.sort_order
            )
        )
        await db.commit()
        service_id = cursor.lastrowid
        cursor = await db.execute("SELECT * FROM services WHERE id = ?", (service_id,))
        return dict(await cursor.fetchone())

@app.patch("/api/admin/services/{service_id}", response_model=ServiceOut)
async def update_service(service_id: int, data: ServiceUpdate, admin_id: int = Depends(require_admin)):
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM services WHERE id = ?", (service_id,))
        existing = await cursor.fetchone()
        if not existing:
            raise HTTPException(404, "Service not found")

        updates = []
        values = []
        for field, value in data.model_dump(exclude_unset=True).items():
            if value is not None:
                if isinstance(value, bool):
                    value = int(value)
                updates.append(f"{field} = ?")
                values.append(value)

        if not updates:
            return dict(existing)

        updates.append("updated_at = datetime('now')")
        values.append(service_id)

        await db.execute(
            f"UPDATE services SET {', '.join(updates)} WHERE id = ?",
            values
        )
        await db.commit()
        cursor = await db.execute("SELECT * FROM services WHERE id = ?", (service_id,))
        return dict(await cursor.fetchone())

@app.delete("/api/admin/services/{service_id}")
async def delete_service(service_id: int, admin_id: int = Depends(require_admin)):
    async with get_db() as db:
        await db.execute("UPDATE services SET is_active = 0 WHERE id = ?", (service_id,))
        await db.commit()
        return {"ok": True}

@app.post("/api/admin/services/{service_id}/image")
async def upload_service_image(
    service_id: int,
    file: UploadFile = File(...),
    admin_id: int = Depends(require_admin)
):
    ext = Path(file.filename).suffix.lower() or ".jpg"
    filename = f"service_{service_id}_{int(datetime.now().timestamp())}{ext}"
    path = UPLOAD_DIR / filename
    content = await file.read()
    path.write_bytes(content)

    image_url = f"/uploads/{filename}"
    async with get_db() as db:
        await db.execute(
            "UPDATE services SET image_url = ?, updated_at = datetime('now') WHERE id = ?",
            (image_url, service_id)
        )
        await db.commit()
    return {"image_url": image_url}

# ==================== Slots ====================

@app.get("/api/slots")
async def list_slots(
    service_id: Optional[int] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    available_only: bool = True
):
    async with get_db() as db:
        query = "SELECT * FROM availability_slots WHERE 1=1"
        params = []
        if service_id is not None:
            query += " AND (service_id = ? OR service_id IS NULL)"
            params.append(service_id)
        if from_date:
            query += " AND datetime_start >= ?"
            params.append(from_date)
        if to_date:
            query += " AND datetime_start <= ?"
            params.append(to_date)
        if available_only:
            query += " AND is_available = 1"
        query += " ORDER BY datetime_start"
        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

@app.post("/api/admin/slots", response_model=SlotOut)
async def create_slot(data: SlotCreate, admin_id: int = Depends(require_admin)):
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO availability_slots 
               (service_id, datetime_start, datetime_end, is_available, is_online, note)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                data.service_id, data.datetime_start, data.datetime_end,
                int(data.is_available), int(data.is_online), data.note
            )
        )
        await db.commit()
        slot_id = cursor.lastrowid
        cursor = await db.execute("SELECT * FROM availability_slots WHERE id = ?", (slot_id,))
        return dict(await cursor.fetchone())

@app.delete("/api/admin/slots/{slot_id}")
async def delete_slot(slot_id: int, admin_id: int = Depends(require_admin)):
    async with get_db() as db:
        await db.execute("DELETE FROM availability_slots WHERE id = ?", (slot_id,))
        await db.commit()
        return {"ok": True}

@app.patch("/api/admin/slots/{slot_id}")
async def update_slot(slot_id: int, is_available: bool = None, note: str = None,
                      admin_id: int = Depends(require_admin)):
    async with get_db() as db:
        if is_available is not None:
            await db.execute(
                "UPDATE availability_slots SET is_available = ? WHERE id = ?",
                (int(is_available), slot_id)
            )
        if note is not None:
            await db.execute(
                "UPDATE availability_slots SET note = ? WHERE id = ?",
                (note, slot_id)
            )
        await db.commit()
        return {"ok": True}

# ==================== Bookings ====================

@app.post("/api/bookings")
async def create_booking(
    data: BookingCreate,
    x_telegram_id: int = Header(..., alias="X-Telegram-Id")
):
    async with get_db() as db:
        user = await get_or_create_user(db, x_telegram_id)

        # Check slot if provided
        if data.slot_id:
            cursor = await db.execute(
                "SELECT * FROM availability_slots WHERE id = ? AND is_available = 1",
                (data.slot_id,)
            )
            slot = await cursor.fetchone()
            if not slot:
                raise HTTPException(400, "Slot not available")

        cursor = await db.execute(
            """INSERT INTO bookings 
               (user_id, service_id, event_id, slot_id, datetime_start, datetime_end,
                client_name, client_phone, client_comment, is_online, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
            (
                user["id"], data.service_id, data.event_id, data.slot_id,
                data.datetime_start, data.datetime_end,
                data.client_name, data.client_phone, data.client_comment,
                int(data.is_online)
            )
        )
        await db.commit()
        booking_id = cursor.lastrowid

        # Mark slot as unavailable
        if data.slot_id:
            await db.execute(
                "UPDATE availability_slots SET is_available = 0 WHERE id = ?",
                (data.slot_id,)
            )
            await db.commit()

        # Get service title for notification
        service_title = None
        if data.service_id:
            cursor = await db.execute("SELECT title FROM services WHERE id = ?", (data.service_id,))
            row = await cursor.fetchone()
            if row:
                service_title = row["title"]

        # Notify admins via Telegram
        try:
            from bot import notify_admins
            msg = (
                f"🆕 <b>Новая заявка #{booking_id}</b>\n\n"
                f"Услуга: {service_title or '—'}\n"
                f"Клиент: {data.client_name}\n"
                f"Телефон: {data.client_phone}\n"
                f"Когда: {data.datetime_start}\n"
                f"Формат: {'онлайн' if data.is_online else 'очно'}\n"
                f"Комментарий: {data.client_comment or '—'}"
            )
            await notify_admins(msg)
        except Exception as e:
            print("Notify error:", e)

        cursor = await db.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,))
        booking = dict(await cursor.fetchone())
        booking["service_title"] = service_title
        return booking

@app.get("/api/bookings/my")
async def my_bookings(x_telegram_id: int = Header(..., alias="X-Telegram-Id")):
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT b.*, s.title as service_title 
               FROM bookings b
               LEFT JOIN services s ON b.service_id = s.id
               JOIN users u ON b.user_id = u.id
               WHERE u.telegram_id = ?
               ORDER BY b.datetime_start DESC""",
            (x_telegram_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

@app.post("/api/bookings/{booking_id}/cancel")
async def cancel_booking(booking_id: int, x_telegram_id: int = Header(..., alias="X-Telegram-Id")):
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT b.*, u.telegram_id 
               FROM bookings b JOIN users u ON b.user_id = u.id
               WHERE b.id = ?""",
            (booking_id,)
        )
        booking = await cursor.fetchone()
        if not booking:
            raise HTTPException(404, "Booking not found")
        if booking["telegram_id"] != x_telegram_id and not is_admin(x_telegram_id):
            raise HTTPException(403, "Not allowed")

        await db.execute(
            "UPDATE bookings SET status = 'cancelled', updated_at = datetime('now') WHERE id = ?",
            (booking_id,)
        )
        if booking["slot_id"]:
            await db.execute(
                "UPDATE availability_slots SET is_available = 1 WHERE id = ?",
                (booking["slot_id"],)
            )
        await db.commit()
        return {"ok": True}

@app.get("/api/admin/bookings")
async def admin_list_bookings(
    status: Optional[str] = None,
    admin_id: int = Depends(require_admin)
):
    async with get_db() as db:
        query = """SELECT b.*, s.title as service_title, u.telegram_id, u.username, u.first_name
                   FROM bookings b
                   LEFT JOIN services s ON b.service_id = s.id
                   JOIN users u ON b.user_id = u.id
                   WHERE 1=1"""
        params = []
        if status:
            query += " AND b.status = ?"
            params.append(status)
        query += " ORDER BY b.created_at DESC"
        cursor = await db.execute(query, params)
        return [dict(r) for r in await cursor.fetchall()]

@app.patch("/api/admin/bookings/{booking_id}/status")
async def update_booking_status(
    booking_id: int,
    status: str = Query(...),
    admin_id: int = Depends(require_admin)
):
    allowed = {"pending", "confirmed", "cancelled", "completed"}
    if status not in allowed:
        raise HTTPException(400, f"Status must be one of {allowed}")
    async with get_db() as db:
        await db.execute(
            "UPDATE bookings SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, booking_id)
        )
        await db.commit()
        return {"ok": True}

# ==================== Events ====================

@app.get("/api/events", response_model=List[EventOut])
async def list_events(active_only: bool = True, upcoming: bool = True):
    async with get_db() as db:
        query = "SELECT e.*, (SELECT COUNT(*) FROM event_bookings eb WHERE eb.event_id = e.id AND eb.status != 'cancelled') as current_participants FROM events e WHERE 1=1"
        if active_only:
            query += " AND e.is_active = 1"
        if upcoming:
            query += " AND e.datetime_start >= datetime('now')"
        query += " ORDER BY e.datetime_start"
        cursor = await db.execute(query)
        return [dict(r) for r in await cursor.fetchall()]

@app.get("/api/events/{event_id}")
async def get_event(event_id: int):
    async with get_db() as db:
        cursor = await db.execute(
            """SELECT e.*, 
                      (SELECT COUNT(*) FROM event_bookings eb WHERE eb.event_id = e.id AND eb.status != 'cancelled') as current_participants
               FROM events e WHERE e.id = ?""",
            (event_id,)
        )
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(404, "Event not found")
        return dict(row)

@app.post("/api/admin/events", response_model=EventOut)
async def create_event(data: EventCreate, admin_id: int = Depends(require_admin)):
    async with get_db() as db:
        cursor = await db.execute(
            """INSERT INTO events 
               (title, description, datetime_start, datetime_end, place, is_online,
                price, max_participants, image_url, is_active, payment_required)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data.title, data.description, data.datetime_start, data.datetime_end,
                data.place, int(data.is_online), data.price, data.max_participants,
                data.image_url, int(data.is_active), int(data.payment_required)
            )
        )
        await db.commit()
        event_id = cursor.lastrowid
        cursor = await db.execute(
            "SELECT *, 0 as current_participants FROM events WHERE id = ?", (event_id,)
        )
        return dict(await cursor.fetchone())

@app.patch("/api/admin/events/{event_id}")
async def update_event(event_id: int, data: EventUpdate, admin_id: int = Depends(require_admin)):
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        existing = await cursor.fetchone()
        if not existing:
            raise HTTPException(404, "Event not found")

        updates = []
        values = []
        for field, value in data.model_dump(exclude_unset=True).items():
            if value is not None:
                if isinstance(value, bool):
                    value = int(value)
                updates.append(f"{field} = ?")
                values.append(value)
        if updates:
            updates.append("updated_at = datetime('now')")
            values.append(event_id)
            await db.execute(
                f"UPDATE events SET {', '.join(updates)} WHERE id = ?", values
            )
            await db.commit()
        cursor = await db.execute(
            """SELECT e.*, 
                      (SELECT COUNT(*) FROM event_bookings eb WHERE eb.event_id = e.id AND eb.status != 'cancelled') as current_participants
               FROM events e WHERE e.id = ?""", (event_id,)
        )
        return dict(await cursor.fetchone())

@app.delete("/api/admin/events/{event_id}")
async def delete_event(event_id: int, admin_id: int = Depends(require_admin)):
    async with get_db() as db:
        await db.execute("UPDATE events SET is_active = 0 WHERE id = ?", (event_id,))
        await db.commit()
        return {"ok": True}

@app.post("/api/events/{event_id}/book")
async def book_event(
    event_id: int,
    client_name: str = Form(...),
    client_phone: str = Form(...),
    x_telegram_id: int = Header(..., alias="X-Telegram-Id")
):
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM events WHERE id = ? AND is_active = 1", (event_id,))
        event = await cursor.fetchone()
        if not event:
            raise HTTPException(404, "Event not found")

        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM event_bookings WHERE event_id = ? AND status != 'cancelled'",
            (event_id,)
        )
        cnt = (await cursor.fetchone())["cnt"]
        if event["max_participants"] > 0 and cnt >= event["max_participants"]:
            raise HTTPException(400, "No places left")

        user = await get_or_create_user(db, x_telegram_id)
        await db.execute(
            """INSERT INTO event_bookings (event_id, user_id, client_name, client_phone, status)
               VALUES (?, ?, ?, ?, 'pending')""",
            (event_id, user["id"], client_name, client_phone)
        )
        await db.commit()
        return {"ok": True, "message": "Запись на мероприятие создана"}

# ==================== Health ====================

@app.get("/api/health")
async def health():
    return {"status": "ok", "time": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
