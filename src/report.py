"""Build the cleaning report (docs/cleaning_rules.md, section 5)."""

from src.checks import CheckResult


TABLE_ORDER = ["users", "enrollments", "payments"]

# Report line -> the stats key that carries the actual value.
TRANSFORMATION_LINES = [
    ("Назв країн уніфіковано (USA, DE, UK)", "users", "countries_unified"),
    ("Пропущених країн замінено на Unknown", "users", "countries_filled_unknown"),
    (
        "Дат enrollment приведено до єдиного формату",
        "enrollments",
        "enrolled_at_reformatted",
    ),
    ("Значень progress_pct виправлено", "enrollments", "progress_pct_fixed"),
    ("Неможливих completed_at очищено", "enrollments", "completed_at_cleared"),
    (
        "Сертифікованих enrollment перенесено до rejected",
        "enrollments",
        "certified_without_completion_rejected",
    ),
    ("Повних дублікатів enrollment видалено", "enrollments", "duplicates_removed"),
    (
        "Платежів перенесено до rejected",
        "payments",
        "payments_unknown_user_rejected",
    ),
]


def _thousands(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def _removed_or_rejected(table_stats: dict[str, int]) -> int:
    return table_stats["raw_rows"] - table_stats["clean_rows"]


def build_report(
    stats: dict[str, dict[str, int]],
    checks: list[CheckResult],
) -> str:
    """Render the report from values the pipeline actually produced."""

    lines = ["# Cleaning report", "", "## Рядки", ""]
    lines.append("| Таблиця | Raw rows | Clean rows | Removed або rejected |")
    lines.append("| --- | ---: | ---: | ---: |")

    for table in TABLE_ORDER:
        table_stats = stats[table]
        lines.append(
            f"| {table} "
            f"| {_thousands(table_stats['raw_rows'])} "
            f"| {_thousands(table_stats['clean_rows'])} "
            f"| {_thousands(_removed_or_rejected(table_stats))} |"
        )

    lines += ["", "## Виконані перетворення", ""]
    lines.append("| Перетворення | Рядків |")
    lines.append("| --- | ---: |")

    for label, table, key in TRANSFORMATION_LINES:
        lines.append(f"| {label} | {_thousands(stats[table][key])} |")

    lines += ["", "## Фінальні перевірки", ""]
    lines.append("| Перевірка | Результат |")
    lines.append("| --- | --- |")

    for check in checks:
        status = "пройдено" if check.passed else f"НЕ ПРОЙДЕНО — {check.detail}"
        lines.append(f"| {check.name} | {status} |")

    failed = [check for check in checks if not check.passed]
    lines += [
        "",
        f"Виконано перевірок: {len(checks)}. "
        f"Пройдено: {len(checks) - len(failed)}. Не пройдено: {len(failed)}.",
        "",
    ]

    return "\n".join(lines)
