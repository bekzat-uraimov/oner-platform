"""Seed the database with sample courses for local dev and demos.

Idempotent: re-running skips courses whose slug already exists, so it's safe to
run after every `alembic upgrade`. Run with `uv run python -m app.seed`.

The catalog mirrors what ONER sells: filmmaking and content creation, in Russian.
Durations are in seconds.
"""

from decimal import Decimal

from sqlmodel import Session, select

from app.core.db import engine
from app.models import Course, CourseStatus, Currency, Lesson, Module


def lesson(title: str, duration: int, description: str | None = None) -> dict:
    return {"title": title, "duration": duration, "description": description}


SAMPLE_COURSES = [
    {
        "title": "Цветокоррекция в DaVinci Resolve",
        "slug": "color-grading-resolve",
        "cover": "/covers/color-grading-resolve.svg",
        "description": "От плоского исходника до рекламного грейда: скоупы, кожа, свой look и сдача клиенту.",
        "learning_outcomes": (
            "Читать скоупы и выставлять баланс белого\n"
            "Передавать тон кожи без оранжевых лиц\n"
            "Собирать узнаваемый look для бренда\n"
            "Сдавать проект под Instagram, YouTube и ТВ"
        ),
        "requirements": "Компьютер, на котором запускается DaVinci Resolve\nБесплатной версии Resolve достаточно",
        "segment": "Цвет",
        "price": Decimal("12900.00"),
        "modules": [
            {
                "title": "Основы цвета",
                "description": "Как камера и глаз видят цвет, и почему монитору нельзя верить.",
                "lessons": [
                    lesson("Коррекция и грейдинг", 420, "Две разные задачи и порядок, в котором их решают."),
                    lesson("Скоупы: вектор, волна, гистограмма", 780, "Учимся доверять приборам."),
                    lesson("Баланс белого и экспозиция", 660, "Первичная коррекция за пять минут."),
                ],
            },
            {
                "title": "Грейдинг",
                "description": "Ноды, маски и работа с кожей.",
                "lessons": [
                    lesson("Ноды и порядок операций", 900),
                    lesson("Кожа и тона лица", 840, "Как сохранить живой цвет лица при сильном грейде."),
                    lesson("Маски и трекинг", 720),
                    lesson("Собираем look для рекламы", 1020, "От референса до готового пресета."),
                ],
            },
            {
                "title": "Сдача проекта",
                "lessons": [
                    lesson("Экспорт под Instagram и YouTube", 600, "Кодеки, битрейт и цветовые пространства."),
                    lesson("Правки и работа с клиентом", 480),
                ],
            },
        ],
    },
    {
        "title": "Монтаж в Premiere Pro",
        "slug": "editing-premiere",
        "cover": "/covers/editing-premiere.svg",
        "description": "Монтаж, который держит внимание: ритм, звук, титры и быстрая работа на таймлайне.",
        "learning_outcomes": (
            "Собирать черновой монтаж за вечер\n"
            "Резать в ритм музыки и речи\n"
            "Чистить и сводить звук\n"
            "Делать субтитры и вертикальные версии"
        ),
        "requirements": "Adobe Premiere Pro, подойдёт пробная версия\nНаушники",
        "segment": "Монтаж",
        "price": Decimal("9900.00"),
        "modules": [
            {
                "title": "Таймлайн",
                "description": "Скорость работы решает больше, чем эффекты.",
                "lessons": [
                    lesson("Интерфейс и горячие клавиши", 540),
                    lesson("Черновой монтаж", 900, "Отбор дублей и структура ролика."),
                    lesson("Ритм и склейки", 780),
                ],
            },
            {
                "title": "Звук",
                "lessons": [
                    lesson("Чистка голоса", 600),
                    lesson("Музыка и сведение", 660),
                ],
            },
            {
                "title": "Готовый ролик",
                "lessons": [
                    lesson("Титры и субтитры", 540),
                    lesson("Вертикальная версия для Reels", 480),
                    lesson("Экспорт", 360),
                ],
            },
        ],
    },
    {
        "title": "Съёмка: от автомата к ручному режиму",
        "slug": "camera-basics",
        "cover": "/covers/camera-basics.svg",
        "description": "Экспозиция, фокус, объективы и композиция. Снимаем осознанно на камеру или телефон.",
        "learning_outcomes": (
            "Снимать в ручном режиме без пересветов\n"
            "Выбирать объектив под задачу\n"
            "Строить кадр и движение камеры\n"
            "Снимать интервью и перебивки"
        ),
        "requirements": "Камера с ручным режимом или смартфон",
        "segment": "Съёмка",
        "price": Decimal("8900.00"),
        "modules": [
            {
                "title": "Экспозиция",
                "description": "Выдержка, диафрагма и ISO на реальных кадрах.",
                "lessons": [
                    lesson("Треугольник экспозиции", 840),
                    lesson("Профили и лог", 600, "Зачем снимать серую картинку."),
                    lesson("Баланс белого на площадке", 420),
                ],
            },
            {
                "title": "Кадр",
                "lessons": [
                    lesson("Объективы и фокусные расстояния", 720),
                    lesson("Композиция и ракурсы", 660),
                    lesson("Движение камеры", 780),
                ],
            },
            {
                "title": "Практика",
                "lessons": [
                    lesson("Съёмка интервью", 900),
                    lesson("Перебивки и детали", 540),
                ],
            },
        ],
    },
    {
        "title": "Свет для видео",
        "slug": "lighting-video",
        "cover": "/covers/lighting-video.svg",
        "description": "Схемы света для интервью, продукта и атмосферных сцен, с дорогими приборами и без.",
        "learning_outcomes": (
            "Ставить трёхточечную схему\n"
            "Работать с окном и практическим светом\n"
            "Снимать продукт с чистыми бликами\n"
            "Создавать настроение цветом света"
        ),
        "requirements": "Любой источник света, даже настольная лампа",
        "segment": "Свет",
        "price": Decimal("7900.00"),
        "modules": [
            {
                "title": "Основы",
                "lessons": [
                    lesson("Жёсткий и мягкий свет", 600),
                    lesson("Трёхточечная схема", 780),
                ],
            },
            {
                "title": "Сцены",
                "description": "Три задачи, которые встречаются в каждом втором проекте.",
                "lessons": [
                    lesson("Интервью у окна", 720),
                    lesson("Предметная съёмка", 840),
                    lesson("Ночная атмосфера", 660),
                ],
            },
            {
                "title": "Бюджет",
                "lessons": [
                    lesson("Свет за 5 000 сом", 540, "Что купить первым и чем заменить студийные приборы."),
                ],
            },
        ],
    },
    {
        "title": "Режиссура короткого видео",
        "slug": "directing-short",
        "cover": "/covers/directing-short.svg",
        "description": "Идея, сценарий, раскадровка и работа с актёрами. Как снять рекламу, которую досматривают.",
        "learning_outcomes": (
            "Превращать бриф в идею\n"
            "Писать сценарий и раскадровку\n"
            "Вести съёмочную площадку\n"
            "Работать с непрофессиональными актёрами"
        ),
        "requirements": "Базовые навыки съёмки",
        "segment": "Режиссура",
        "price": Decimal("14900.00"),
        "modules": [
            {
                "title": "Идея",
                "lessons": [
                    lesson("От брифа к идее", 780),
                    lesson("Сценарий на одну страницу", 660),
                ],
            },
            {
                "title": "Подготовка",
                "lessons": [
                    lesson("Раскадровка и шот-лист", 720),
                    lesson("Кастинг и локации", 600),
                ],
            },
            {
                "title": "Площадка",
                "lessons": [
                    lesson("Работа с актёром", 900),
                    lesson("Команда и тайминг смены", 660),
                ],
            },
            {
                "title": "Разбор",
                "lessons": [
                    lesson("Разбор рекламного ролика", 1080, "От сценария до финального монтажа."),
                ],
            },
        ],
    },
    {
        "title": "Reels и контент для Instagram",
        "slug": "instagram-reels",
        "cover": "/covers/instagram-reels.svg",
        "description": "Контент-план, съёмка на телефон и монтаж Reels, которые смотрят до конца.",
        "learning_outcomes": (
            "Составлять контент-план на месяц\n"
            "Снимать вертикальное видео на телефон\n"
            "Монтировать Reels в CapCut\n"
            "Читать статистику и повторять удачное"
        ),
        "requirements": "Смартфон\nАккаунт в Instagram",
        "segment": "Контент",
        "price": Decimal("6900.00"),
        "modules": [
            {
                "title": "Стратегия",
                "lessons": [
                    lesson("Рубрики и контент-план", 600),
                    lesson("Хук в первые три секунды", 480),
                ],
            },
            {
                "title": "Производство",
                "lessons": [
                    lesson("Съёмка на телефон", 720),
                    lesson("Свет и звук дома", 540),
                    lesson("Монтаж в CapCut", 780),
                ],
            },
            {
                "title": "Рост",
                "lessons": [
                    lesson("Статистика и что с ней делать", 540),
                ],
            },
        ],
    },
    {
        "title": "Моушн-дизайн в After Effects",
        "slug": "motion-after-effects",
        "cover": "/covers/motion-after-effects.svg",
        "description": "Готовится. Остаётся черновиком и не видна в каталоге.",
        "segment": "Монтаж",
        "price": Decimal("0.00"),
        "status": CourseStatus.draft,
        "modules": [
            {"title": "Основы", "lessons": [lesson("Интерфейс и ключевые кадры", 600)]},
        ],
    },
]


def seed() -> None:
    with Session(engine) as session:
        for data in SAMPLE_COURSES:
            existing = session.exec(
                select(Course).where(Course.slug == data["slug"])
            ).first()
            if existing:
                print(f"skip (exists): {data['slug']}")
                continue

            course = Course(
                title=data["title"],
                slug=data["slug"],
                description=data["description"],
                learning_outcomes=data.get("learning_outcomes"),
                requirements=data.get("requirements"),
                segment=data["segment"],
                price=data["price"],
                currency=data.get("currency", Currency.KGS),
                status=data.get("status", CourseStatus.published),
                # A path the web app serves from web/public, or any image URL.
                cover=data.get("cover"),
            )
            for m_order, module_data in enumerate(data["modules"]):
                module = Module(
                    title=module_data["title"],
                    description=module_data.get("description"),
                    order=m_order,
                )
                for l_order, item in enumerate(module_data["lessons"]):
                    module.lessons.append(
                        Lesson(
                            title=item["title"],
                            description=item.get("description"),
                            duration=item.get("duration"),
                            order=l_order,
                        )
                    )
                course.modules.append(module)

            session.add(course)
            print(f"created: {data['slug']}")

        session.commit()
    print("seed done.")


if __name__ == "__main__":
    seed()
