import aiosqlite
import os
from pathlib import Path

DB_PATH = Path("/tmp/yulia_healer.db")  # sandbox-friendly; later change to local data/

ADMIN_IDS = {1375984482, 5912547447}  # Юлия + тестер

from contextlib import asynccontextmanager

@asynccontextmanager
async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    try:
        yield db
    finally:
        await db.close()

async def init_db():
    async with get_db() as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            first_name TEXT,
            last_name TEXT,
            username TEXT,
            phone TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            short_description TEXT,
            description TEXT,
            price INTEGER NOT NULL DEFAULT 0,
            duration_minutes INTEGER DEFAULT 60,
            image_url TEXT,
            is_online INTEGER DEFAULT 1,
            is_offline INTEGER DEFAULT 1,
            is_active INTEGER DEFAULT 1,
            payment_required INTEGER DEFAULT 0,  -- 0 = only request, 1 = YooKassa
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS availability_slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            service_id INTEGER,  -- NULL = general
            datetime_start TEXT NOT NULL,  -- ISO
            datetime_end TEXT NOT NULL,
            is_available INTEGER DEFAULT 1,
            is_online INTEGER DEFAULT 0,
            note TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            service_id INTEGER,
            event_id INTEGER,
            slot_id INTEGER,
            datetime_start TEXT NOT NULL,
            datetime_end TEXT,
            status TEXT DEFAULT 'pending',  -- pending, confirmed, cancelled, completed
            client_name TEXT,
            client_phone TEXT,
            client_comment TEXT,
            is_online INTEGER DEFAULT 0,
            payment_status TEXT DEFAULT 'none',  -- none, pending, paid, failed
            payment_id TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (service_id) REFERENCES services(id),
            FOREIGN KEY (slot_id) REFERENCES availability_slots(id)
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            datetime_start TEXT NOT NULL,
            datetime_end TEXT,
            place TEXT,
            is_online INTEGER DEFAULT 0,
            price INTEGER DEFAULT 0,
            max_participants INTEGER DEFAULT 0,  -- 0 = unlimited
            image_url TEXT,
            is_active INTEGER DEFAULT 1,
            payment_required INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS event_bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            client_name TEXT,
            client_phone TEXT,
            status TEXT DEFAULT 'pending',
            payment_status TEXT DEFAULT 'none',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """)
        await db.commit()

        # Seed initial services if empty
        cursor = await db.execute("SELECT COUNT(*) as cnt FROM services")
        row = await cursor.fetchone()
        if row["cnt"] == 0:
            await seed_services(db)

async def seed_services(db):
    services = [
        {
            "title": "Энергетическая практика Аксесс «Активация акустических волн»",
            "short_description": "Освобождение тела от ограничений, возврат в состояние лёгкости и радости",
            "description": "Энергетическая практика Аксесс «Активация акустических волн». Акустическая вибрация — это то, чем наше тело создано было быть. Это пространство возможностей и единства с собой и миром. На электрической вибрации крепятся все обиды, чувство вины, сомнения, сожаления, страх, ревность и другие отвлекающие импланты. Также ограничения, блоки и стресс. С помощью этого процесса есть возможность освободить тело от всех этих ограничений и вернуть его в первоначальное состояние расслабления, лёгкости, радости и возможностей.\n\nСеанс проходит в Новороссийске. Время сеанса 60 минут.",
            "price": 4000,
            "duration_minutes": 60,
            "is_online": 0,
            "is_offline": 1,
            "sort_order": 1
        },
        {
            "title": "Энергетическая практика «Когнитивный диссонанс»",
            "short_description": "Устранение внутреннего конфликта и стресса из тела",
            "description": "Энергетическая практика Аксесс «Когнитивный диссонанс». Когнитивный диссонанс — это две противоположные или разные точки зрения на один и тот же предмет. Из-за этого вы генеративную энергию превращаете в разрушительную и прячете это в тело, превращаете в стресс. Всё это приводит к боли, нехватке денег или какому-либо страданию. А из тела это убирает этот телесный процесс Аксесс.\n\nСеанс проходит в Новороссийске. Время сеанса 60-90 минут.",
            "price": 4000,
            "duration_minutes": 75,
            "is_online": 0,
            "is_offline": 1,
            "sort_order": 2
        },
        {
            "title": "Энергетическая практика «Дублирование семейных болезней»",
            "short_description": "Растождествление от родовых паттернов и возврат ДНК к изначальной структуре",
            "description": "Энергетическая практика телесный процесс Аксесс «Дублирование семейных болезней». Наука говорит, что наше тело и его ДНК — это 50% от мамы и папы. Процесс позволяет устранить то, где наше тело дублирует семейные паттерны, и вернуть ДНК тела в его изначальную структуру.\n\nСеанс проходит в Новороссийске. Время сеанса 40-60 минут.",
            "price": 4000,
            "duration_minutes": 50,
            "is_online": 0,
            "is_offline": 1,
            "sort_order": 3
        },
        {
            "title": "Медитация самоисцеления",
            "short_description": "Практика для достижения внутреннего покоя, снижения стресса и наполнения энергией",
            "description": "Медитация для самоисцеления — практика, направленная на достижение состояния внутреннего покоя и гармонии. Помогает снизить уровень стресса, улучшить концентрацию и общее самочувствие. Полезна для исцеления ситуаций из прошлого, при расстройствах, нехватке энергии, ощущении тупика, депрессии.",
            "price": 5000,
            "duration_minutes": 60,
            "is_online": 1,
            "is_offline": 1,
            "sort_order": 4
        },
        {
            "title": "Исцеление нижних тел",
            "short_description": "Исцеление 6 нижних тел: Физического, Эмоционального, Эфирного, Астрального, Ментального, Каузального",
            "description": "Исцеление 6 нижних тел: Физического, Эмоционального, Эфирного, Астрального, Ментального, Каузального.",
            "price": 6000,
            "duration_minutes": 90,
            "is_online": 1,
            "is_offline": 1,
            "sort_order": 5
        },
        {
            "title": "Исцеление Рода, Родовых программ",
            "short_description": "Исцеление Родового Древа, травм и программ, передающихся из поколения в поколение",
            "description": "Сессия для работы с Родом: исцеление Родового Древа, исцеление травм, передающихся из поколения в поколение, Родовых программ.",
            "price": 7000,
            "duration_minutes": 90,
            "is_online": 1,
            "is_offline": 1,
            "sort_order": 6
        },
        {
            "title": "Просмотр потенциалов будущего",
            "short_description": "Погружение для раскрытия потенциалов, способностей, талантов и даров",
            "description": "Сессия погружение для просмотра и наибольшего раскрытия потенциалов способностей, талантов, даров. Выход на эту ветку реальности, соединение с выбранной реальностью по чакрам.",
            "price": 12000,
            "duration_minutes": 120,
            "is_online": 1,
            "is_offline": 1,
            "sort_order": 7
        },
        {
            "title": "Исцеление болезней",
            "short_description": "Исследование и исцеление кармических причин заболеваний",
            "description": "Сессия по исследованию и исцелению кармических причин заболеваний, завершение уроков, связанных с болезнью. Погружение поможет понять, чему учит болезнь, в чём её урок, в чём позитивная роль болезни, при каких условиях возможно исцеление.",
            "price": 8000,
            "duration_minutes": 90,
            "is_online": 1,
            "is_offline": 1,
            "sort_order": 8
        },
        {
            "title": "Работа с имплантами, конфликтующими энергиями, сущностями",
            "short_description": "Освобождение тела от имплантов, конфликтующих энергий и расторжение контрактов",
            "description": "Сессия для освобождения из тела имплантов, конфликтующих энергий, расторжение контрактов с сущностями.",
            "price": 7000,
            "duration_minutes": 90,
            "is_online": 1,
            "is_offline": 1,
            "sort_order": 9
        },
        {
            "title": "Завершение контрактов, клятв, обетов, обещаний",
            "short_description": "Завершение клятв, обетов, контрактов из этой и прошлых жизней",
            "description": "Сессия по завершению данных как в этой, так и в прошлых жизнях клятв, обетов, обещаний, обязательств, контрактов с энерго-структурами, эгрегорами.",
            "price": 7000,
            "duration_minutes": 90,
            "is_online": 1,
            "is_offline": 1,
            "sort_order": 10
        },
        {
            "title": "Исцеление психологических травм",
            "short_description": "Исцеление травматичных опытов души с поддержкой Высшего Я и Ангелов",
            "description": "Сеанс погружения с поддержкой Высшего Я, Высших Сил, Ангелов для исцеления травматичных опытов души.",
            "price": 7000,
            "duration_minutes": 90,
            "is_online": 1,
            "is_offline": 1,
            "sort_order": 11
        },
        {
            "title": "Консультация на Метафорических картах",
            "short_description": "Сессия с МАК по любому запросу: отношения, травмы, программы, предназначение, финансы",
            "description": "Сессия с метафорическими картами по любому запросу: отношения, психологические травмы, негативные программы, установки, предназначение, финансы.",
            "price": 4000,
            "duration_minutes": 60,
            "is_online": 1,
            "is_offline": 1,
            "sort_order": 12
        },
        {
            "title": "Консультация по Матрице судьбы",
            "short_description": "Разбор талантов, кармических задач, родовых программ и предназначений",
            "description": "Консультация по методу «Целостная Матрица Судьбы» Татьяны Жеребцовой. Разбор ваших талантов, кармических задач, родовых программ, кармического хвоста и предназначений.",
            "price": 5000,
            "duration_minutes": 75,
            "is_online": 1,
            "is_offline": 1,
            "sort_order": 13
        },
        {
            "title": "Исцеление страха",
            "short_description": "Исцеление страха через погружение и просмотр прошлых жизней",
            "description": "Исцеление страха в канале с Высшим Я, через погружение в медитативное состояние и если необходима более глубокая проработка — просмотр прошлых жизней, откуда зародился страх.",
            "price": 5000,
            "duration_minutes": 75,
            "is_online": 1,
            "is_offline": 1,
            "sort_order": 14
        },
        {
            "title": "Исцеление кармических отношений",
            "short_description": "Возврат энергии, завершение контрактов или переход на новый уровень отношений",
            "description": "Сессия погружение на исцеление кармических отношений, возврат своей энергии, выход из отношений, завершение всех контрактов с любым человеком или переход на новый уровень отношений.",
            "price": 5000,
            "duration_minutes": 75,
            "is_online": 1,
            "is_offline": 1,
            "sort_order": 15
        },
        {
            "title": "Сеанс Access Bars",
            "short_description": "Энергетическое очищение через лёгкие прикосновения к 32 точкам на голове",
            "description": "ACCESS BARS — метод энергетического очищения, основанный на лёгких прикосновениях к определённым участкам на голове (Бары). Эти точки связаны со всеми мыслями, идеями, эмоциями, убеждениями. При касании открываются каналы, по которым ненужный «балласт» выводится из сознания.",
            "price": 4000,
            "duration_minutes": 60,
            "is_online": 0,
            "is_offline": 1,
            "sort_order": 16
        },
        {
            "title": "Исцеление тела Access Цепи",
            "short_description": "Избавление от болезней, блоков, негативных установок и болей в теле",
            "description": "Сеанс исцеления тела с помощью Аксесс Цепи — избавление от болезней, блоков, негативных установок, подавленных эмоций, болей в теле и всего, что воспринимается как Цепи и не даёт жить в лёгкости и радости.",
            "price": 3000,
            "duration_minutes": 50,
            "is_online": 0,
            "is_offline": 1,
            "sort_order": 17
        },
        {
            "title": "Путешествие в Хроники Акаши",
            "short_description": "Исследование прошлых жизней, осознание кармы, ответы на вопросы",
            "description": "Путешествие в Хроники Акаши для исследования прошлых жизней, осознания кармы, ответов на вопросы.",
            "price": 5000,
            "duration_minutes": 90,
            "is_online": 1,
            "is_offline": 1,
            "sort_order": 18
        },
        {
            "title": "Исцеление Кармических программ",
            "short_description": "Осознание кармы и исцеление кармических причин в настоящей жизни",
            "description": "Сессия погружения для осознания кармы и исцеления кармических причин в настоящей жизни, исцеление временной линии.",
            "price": 7000,
            "duration_minutes": 90,
            "is_online": 1,
            "is_offline": 1,
            "sort_order": 19
        },
        {
            "title": "Индивидуальная трансформационная игра «Сферы жизни»",
            "short_description": "Вернуть гармонию, радость и смысл через работу с ценностями и целями",
            "description": "Индивидуальная игра «Сфера жизни» поможет определить ценности, цели и приоритеты, найти баланс между работой, личной жизнью и саморазвитием. Состоит из анализа ситуации, определения ценностей, постановки целей, разработки плана и отслеживания прогресса.",
            "price": 3000,
            "duration_minutes": 90,
            "is_online": 1,
            "is_offline": 1,
            "sort_order": 20
        },
    ]

    for s in services:
        await db.execute(
            """INSERT INTO services 
               (title, short_description, description, price, duration_minutes, 
                is_online, is_offline, sort_order)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                s["title"], s["short_description"], s["description"],
                s["price"], s["duration_minutes"],
                s["is_online"], s["is_offline"], s["sort_order"]
            )
        )
    await db.commit()
    print(f"Seeded {len(services)} services")
