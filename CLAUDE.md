# Project instructions

This is a learning analytics data-cleaning project.

## Architecture

- PostgreSQL contains immutable raw data.
- Python loads raw tables into pandas DataFrames.
- Cleaning functions transform copies of raw DataFrames.
- Clean data is saved to `data/clean/`.
- Rejected records are saved to `data/rejected/`.
- Reports are saved to `reports/`.
- Metrics and dashboards may use only clean data.

## Source of truth

Before implementing data cleaning, read:

`docs/cleaning_rules.md`

Do not invent cleaning decisions that are not documented there.

If the specification is incomplete or ambiguous, stop and ask for a decision.

## Development workflow

For non-trivial tasks:

1. analyze the task;
2. propose a plan;
3. wait for approval;
4. implement only the approved step;
5. run the relevant tests;
6. report the result;
7. wait before continuing.

Do not implement the complete project in one step unless explicitly requested.

## Data safety

- Never modify raw PostgreSQL tables.
- Do not run `UPDATE`, `DELETE`, `DROP`, `TRUNCATE`, `ALTER` or `INSERT`.
- Database access in this project must be read-only.
- Do not modify `.env`.
- Do not print credentials or the database connection string.
- Do not commit `.env`.
- Do not silently remove records.
- Save unresolved rejected records separately.
- Do not edit generated clean CSV files manually.

## Cleaning functions

Cleaning functions must:

- receive DataFrames as arguments;
- work on copies;
- implement only documented rules;
- avoid database access;
- avoid file writing;
- return cleaned or rejected DataFrames explicitly;
- raise clear errors when critical expectations fail.

## Testing

- Do not change production code merely to make a test pass without explaining the issue.
- Do not weaken tests without approval.
- Test primary keys, required columns, ranges and relationships.
- Show the exact failing rule and representative records.
- Run the smallest relevant test set after each implementation step.

## Reporting

Report exact counts whenever possible:

- raw rows;
- clean rows;
- changed rows;
- removed duplicates;
- rejected rows;
- failed checks.

Do not describe a check as passing unless it was actually executed.