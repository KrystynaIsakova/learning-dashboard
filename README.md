# Learning Analytics Data Pipeline

Навчальний проєкт для створення відтворюваного pipeline очищення даних за допомогою Python і Claude Code.

## Архітектура

```text
PostgreSQL raw tables
        ↓
Python extraction
        ↓
Cleaning functions
        ↓
Automated tests
        ↓
Clean and rejected CSV
        ↓
Data-quality validation
        ↓
Metrics
        ↓
Streamlit dashboard
```

Сирі дані зберігаються в PostgreSQL і не змінюються.

Очищені таблиці зберігаються локально:

```text
data/clean/
```

Записи, які не можна безпечно виправити, зберігаються окремо:

```text
data/rejected/
```

## Таблиці

У першій версії pipeline використовуються:

- `users`;
- `enrollments`;
- `payments`.

## Налаштування проєкту

### 1. Створіть віртуальне середовище

Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Встановіть залежності

```bash
python -m pip install -r requirements.txt
```

### 3. Створіть `.env`

Створіть копію `.env.example` і назвіть її `.env`.

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

macOS:

```bash
cp .env.example .env
```

Вставте в `.env` справжній connection string до PostgreSQL.

Не додавайте `.env` до Git.

## Перевірка підключення

```bash
python -m src.database
```

Очікуваний результат:

```text
Database connection successful.
```

## Перевірка доступних таблиць

```bash
python -m src.extract
```

Команда повинна показати кількість рядків у:

- `users`;
- `enrollments`;
- `payments`.

## Запуск тестів

```bash
pytest
```

## Запуск pipeline

Ця команда запрацює після реалізації `src/pipeline.py`:

```bash
python -m src.pipeline
```

## Очікувані результати pipeline

```text
data/
├── clean/
│   ├── users.csv
│   ├── enrollments.csv
│   └── payments.csv
└── rejected/
    └── payments_unknown_user.csv
```

Очікувана кількість рядків:

| Файл | Рядки |
|---|---:|
| `users.csv` | 40 000 |
| `enrollments.csv` | 94 705 |
| `payments.csv` | 87 884 |
| `payments_unknown_user.csv` | 40 |

Pipeline також має створити:

```text
reports/cleaning_report.md
```

## Важливі правила

- Не змінюйте raw-таблиці в PostgreSQL.
- Не редагуйте clean CSV вручну.
- Якщо clean-файл пошкоджений, виправте pipeline та запустіть його повторно.
- Реалізовуйте проєкт по одному кроку.
- Після кожного кроку запускайте відповідні тести.
- Не дозволяйте AI автоматично виправляти дані без погодженого правила.