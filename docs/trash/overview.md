# Overview — the file-by-file map

Last updated **2026-08-25**, at the point the project was called done. Working notes, not a graded document.

Everything below is on branch `main`. See the branch note at the bottom — `main` is the canonical one.

## Layout

Files are split by what they **are**, not what they are about. Python you import, SQL you run, scripts you invoke.

```
main.py             the application entry point
src/                importable application code
src/menus/          one file per role
sql/                schema, extensions, datasets, indexes, measurements
scripts/            run by hand
docs/               notes
```

There is no `data/` — the datasets are generated in SQL rather than loaded from files.

## `src/` — the application

| File | State | What it is |
|---|---|---|
| `db.py` | done | Connections only. Reads `.env`, hands out psycopg connections with `dict_row`. Imported by everything; never destructive. |
| `errors.py` | done | 15 exception classes, all inheriting `AppError`. The vocabulary every feature raises from. Knows nothing about terminals. |
| `ui.py` | done | The only module that imports `rich`. Messages, `table()`, `page()`, `menu()`, and prompts that re-ask on bad input. 244 lines. |
| `auth.py` | done | `Session` (frozen dataclass), `require_role()`, `register()`, `login()`. |
| `auctions.py` | done | `browse()`, `search()`, `detail()`, `end()`. The busiest module. |
| `bids.py` | done | `place()`, `history()`, `list_for_buyer()`. Contains the project's only row-locking transaction. |
| `reports.py` | done | The four admin reports. The one module not named after a table — see architecture.md. |
| `users.py` | **docstring only** | #6 and #13 were not built. |
| `items.py` | **docstring only** | #8, #9, #15 were not built. |
| `payments.py` | **docstring only** | #11 was not built. |
| `shipments.py` | **docstring only** | #12 was not built. |

### `src/menus/`

| File | Actions | Real / placeholder |
|---|---|---|
| `__init__.py` | — | `run()` login gate, `dispatch()`, `run_role_menu()`, `do_login()`, `do_register()`. Owns the loop and the single `except AppError`. |
| `buyer.py` | 9 | 5 real — browse, search, view, bid, my bids |
| `seller.py` | 15 | 6 real — the above plus close auction |
| `admin.py` | 23 | 10 real — the above plus the four reports |

`seller.ACTIONS` starts from `list(buyer.ACTIONS)`, `admin.ACTIONS` from `list(seller.ACTIONS)`. The `list()` is a copy, not an alias — without it, appending to the seller menu would mutate the buyer menu.

Placeholders call `_not_built_yet(feature, issue)`, which prints a warning naming the issue number.

## `sql/`

| File | Lines | What it is |
|---|---|---|
| `schema.sql` | 90 | **The instructor's, verbatim. Never edited.** Six tables, opens with six `DROP TABLE ... CASCADE`. |
| `extensions.sql` | 20 | Ours. Five sequences, one per numeric-PK table, wired in as column `DEFAULT nextval(...)`. |
| `seed.sql` | 55 | Ours. The **demo** dataset — 7 users, 9 items, 7 auctions, 11 bids, 2 payments, 2 shipments. Ends with a `setval` block that must stay last. |
| `bulk_seed.sql` | 111 | Ours. The **measurement** dataset — 440 users, 5,000 items, ~4,500 auctions, ~36,000 bids, built with `generate_series()`. Never run for the demo. |
| `indexes.sql` | 19 | Ours. Eight indexes. Run last, after the data. |
| `tuning_queries.sql` | 140 | Ours. Nine `EXPLAIN (ANALYZE, BUFFERS)` statements. Not part of the build — run by hand, twice. |

**Logins in both datasets:** `admin1`, `seller1`, `seller2`, `buyer1`, `buyer2`, `buyer3`, `newbie1` — all password `pass123`. `bulk_seed.sql` adds volume *around* those rows without touching them.

## `scripts/`

`load_db.py` — the only destructive file in the project. Runs the `.sql` files in one transaction, skipping empty ones.

```bash
python scripts/load_db.py --yes                      # schema, extensions, seed, indexes
python scripts/load_db.py --yes --bulk               # + bulk_seed, before indexes
python scripts/load_db.py --yes --bulk --skip-indexes   # the "before" measurement
python scripts/load_db.py --dry-run                  # show the plan, touch nothing
```

`ui_demo.py` was deleted on 2026-08-25. `smoke.py`, `src/ids.py`, `src/session.py` and `src/template.py` were deleted earlier. Do not recreate any of them.

## `docs/`

`flow.md` — build order and run order. `presentation.md` — the Thursday plan: run of show, the nine demo cases, tuning numbers, pre-flight checklist. `trash/` — these notes plus the spec PDF.

## Size

**1,453 lines of code** — 1,018 Python plus 435 SQL. Another 218 comment lines and 580 docstring lines on top, on `main`.

## Branches

| Branch | State |
|---|---|
| **`main`** | **Canonical.** Fully commented, the version to read and to hand in. |
| `comment_free` | `src/`, `sql/` and `scripts/` with comments stripped and docstrings cut to summary + returns. `src/` is 1,350 lines instead of 1,990. Useful for showing code on screen. |
| `ui_change` | **Not merged.** Right-aligned numeric columns, colour-coded status values, a "logged in as" subtitle under menu headings, and a `rich.markup.escape()` fix so a value containing square brackets renders literally. |

`ui_change` is worth merging — the escape fix is a real bug fix. If you merge both branches, `ui.py` will conflict: take the `ui_change` version and re-run the comment strip on it rather than resolving by hand.
