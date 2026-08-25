# CLAUDE.md

Guidance for Claude Code (claude.ai/code) working in this repository.

**Not committed** — listed in `.gitignore`. Jorge keeps it in OneDrive and drags it between his desktop and laptop. Treat it as personal working context, never suggest committing it, and hand it to a teammate by file transfer rather than by git. It goes stale on their machine the moment Jorge edits his copy: **if this file contradicts the code in front of you, the code wins.**

## Status — the project is done

**Called done on 2026-08-25.** The demo is Thursday **2026-08-27**. Ten minutes, one presenter, one attempt.

Everything below is on `main`, committed and pushed. The application runs end to end on the server: register → log in → role menu → browse → search → view detail → place a bid → close an auction → review your bids → admin reports → log out → quit.

**The only graded item still outstanding is #19, the written report** — 10% of Phase 3, currently at zero. Everything it needs exists in note form already (see "Where the notes live" below).

### What is built

| Issue | Feature | Where |
|---|---|---|
| #1 | Load the database | `scripts/load_db.py` |
| #2 | Foundation — errors, ui, auth, menus | `src/errors.py`, `ui.py`, `auth.py`, `menus/` |
| #3 | Browse auctions | `auctions.browse()` |
| #4 | Search auctions | `auctions.search()` |
| #5 | Auction detail + bid history | `auctions.detail()`, `bids.history()` |
| #7 | Place a bid | `bids.place()`, `bids.list_for_buyer()` |
| #10 | End an auction | `auctions.end()` |
| #16 | Four admin reports | `src/reports.py` |
| #17 | Indexes and tuning | `sql/indexes.sql`, `sql/tuning_queries.sql` |
| #21 | Bulk dataset | `sql/bulk_seed.sql` |

### What was cut, on purpose

**#6 profile, #8 create listing, #9 manage listings, #11 pay, #12 shipments, #13 list users, #14 role change, #15 remove item.**

The team went from three people to one on 2026-08-25. The client-application 10% was already earned by `ui.py` and the menu dispatch, so every further feature would have earned fractions of the 30% while #17 sat at a full 10% untouched. Tuning and the report won.

Consequence to state honestly rather than hide: **a Seller cannot list an item through the application.** The demo runs on seeded items.

`src/users.py`, `items.py`, `payments.py` and `shipments.py` are still module docstrings with no functions. Their menu entries name their issue number rather than pretending to work.

**Do not start building these.** If asked to, check first that it is really wanted — the scope decision was deliberate and is documented in the report.

### Branches

| Branch | State |
|---|---|
| `main` | **Canonical.** Fully commented. The version to read and hand in. |
| `comment_free` | Comments stripped from `src/`, `sql/`, `scripts/`; docstrings cut to summary + returns. `src/` is 1,350 lines instead of 1,990. |
| `ui_change` | **Not merged.** Right-aligned numeric columns, colour-coded status values, a "logged in as" subtitle under menu headings, and a `rich.markup.escape()` fix. |

`ui_change` contains a genuine bug fix — without `escape()`, an item name containing square brackets has part of it eaten as rich markup. Worth merging. If both branches are merged, `ui.py` conflicts: take the `ui_change` version and re-run the comment strip on it rather than resolving by hand.

**Uncommitted changes travel across `git checkout`.** This caught Jorge twice. Commit or stash before switching.

## How to work in this repo

Jorge writes the code. Build **one file, class, or function at a time**, at their pace — no skeletons, no speculative structure, no files they did not ask for. Designing and discussing up front is welcome; wholesale implementation is not.

Keep answers **short and direct** unless elaboration is asked for. He asks follow-ups when he wants more.

Write code comments as **single unwrapped lines** — one comment per physical line, however long, never hard-wrapped across multiple `#` lines. He collapses long lines with `alt+Z`, and hard wrapping defeats that. Comment generously; he is still learning Python.

## The project

CS166 Phase 3 — an online auction and bidding system. PostgreSQL back end, Python terminal client. Summer 2026 (the spec PDF is headed "Spring 2026"; its dates are stale).

Phase 3 is 60% of the project grade: **30%** SQL queries and reports plus core functionality, **10%** physical database design and tuning, **10%** client application, **10%** documentation. Extra credit (+10%) for a friendlier interface, extra features, or meaningful schema/dataset extensions — **two claims already earned**: the five sequences in `extensions.sql`, and the interface work in `ui.py`.

The spec PDF is at `docs/trash/CS166-Project.pdf`. It cannot be read directly — `pdftoppm` is not installed. A text-extraction script that decompresses the FlateDecode streams was written once in the scratchpad; rewrite it if the text is needed.

## The schema — four properties that drove everything

Six tables: `users`, `item`, `auction`, `bid`, `payment`, `shipment`. The schema was handed to us and **`sql/schema.sql` is never edited**.

- **`UNIQUE (login, role)` on `users` is load-bearing.** Child tables foreign-key to `(login, role)` and pin the role with a CHECK (`item.seller_role = 'Seller'`, `bid.buyer_role = 'Buyer'`). Those FKs are `ON UPDATE CASCADE`, so a role change rewrites dependent rows and trips the CHECK. **It also means a Seller physically cannot hold a bid row** — which is why `SelfBid` is unreachable through the interface and a Seller choosing "Place a bid" gets *"Only Buyers can place a bid."* Known and deliberate. Do not "fix" it by removing the `require_role` call; that only converts a readable sentence into a psycopg IntegrityError.
- **`auction.current_highest_bid` is denormalized.** Placing a bid and ending an auction both lock the auction row with `SELECT ... FOR UPDATE` and do their reads and writes inside one transaction.
- **Nothing auto-increments.** `sql/extensions.sql` adds one sequence per numeric-PK table as a column `DEFAULT nextval(...)` — what `SERIAL` does under the hood. **Every INSERT omits its id and uses `RETURNING`.** `users` has no sequence; its key is the login string.
- **Auctions have no start or end time.** The only timestamp anywhere is `bid.bid_timestamp`. An auction closes when its seller closes it and never otherwise.

Also: `auction.item_id`, `payment.auction_id` and `shipment.auction_id` are all `UNIQUE`. Passwords are plain text, deliberately — hashing would lock us out of every seeded account.

## The two contracts

Settled 2026-08-21. Do not relitigate.

**1. Feature functions open their own connection and take a `Session`, not a `conn`.**

```python
def place(session, auction_id, amount):
    with get_connection() as conn:
        ...
```

The context manager commits on clean exit and rolls back if an exception escapes, so **there is no `conn.commit()` anywhere in this project**. Every `raise` inside a `with` rolls back and releases its locks for free. The acting user's login is never a parameter — it comes from `session.login`.

**2. Menu role files contain no control flow.** They export `TITLE` and `ACTIONS`, a list of `(key, label, function)` triples. `menus/__init__.py` owns the loop, the dispatch, and the single `except AppError`. `seller.py` starts from `list(buyer.ACTIONS)`, `admin.py` from `list(seller.ACTIONS)` — the `list()` is a copy, not an alias.

**Role files must never import `menus/__init__.py`.** Imports run one direction only.

## Other settled decisions

- **Feature modules return data or raise; they never print.** Menus catch and render. `ui.py` is the only module that imports `rich`.
- **Application SQL is inline** in the feature modules as parameterized strings. The "SQL lives in `.sql` files" rule applies to schema and datasets only.
- **One feature module per table.** `src/reports.py` is the single exception — its four queries each span three or four tables and belong to none of them.
- **Money is `Decimal`, never `float`.** `ui.prompt_decimal()` is the only place typed text becomes money.
- **Two datasets.** `seed.sql` is thirty readable rows for building and demoing. `bulk_seed.sql` is ~36,000 bids and exists only because you cannot measure an index on thirty rows. **`seed.sql` is never edited**; the bulk file adds volume around the same predictable logins.
- **`auctions.search()` builds its WHERE at runtime**: SQL fragments containing `%s` in one list, values in another. The f-string interpolates only strings the function wrote itself. Any new filter must follow that shape.

## The tuning numbers

The headline fact: **PostgreSQL indexes `PRIMARY KEY` and `UNIQUE` automatically and does not index a `FOREIGN KEY`.** `bid.auction_id` — the most joined column in the application — had none.

| Query | Before | After | |
|---|---|---|---|
| Bid history | 3.39 ms | **0.14 ms** | 24× · 340 buffers → 13 |
| Top bidders | 238.0 ms | **33.1 ms** | 7.2× · subquery 39,188 buffers → 2,167 |
| Search by name | 3.96 ms | 4.02 ms | no change, and cannot improve |

The third is deliberate. `ILIKE '%term%'` has a leading wildcard and a B-tree is sorted by the *start* of a string, so nothing can seek on it. A partial index on Active auctions was also built and the planner **declined** it, correctly — browse wants two thirds of the table. Cost: 3 MB of indexes on 4.5 MB of data.

**Do not re-run the measurement casually** — it means reloading 36,000 bids. The captured output should be kept as files.

## Commands

```bash
uv sync                                              # install/refresh the venv
python scripts/load_db.py --yes                      # demo dataset  <-- the normal one
python scripts/load_db.py --yes --bulk               # + 36,000 bids, for measuring
python scripts/load_db.py --yes --bulk --skip-indexes   # the "before" measurement
python scripts/load_db.py --dry-run                  # show the plan, touch nothing
.venv/bin/python main.py                             # run it (bin, not Scripts -- server is Linux)
```

`load_db.py` is the only destructive file. `schema.sql` opens with six `DROP TABLE ... CASCADE`.

No test runner, linter, or formatter. **There is no automated test suite** — testing is manual, against named rows in `seed.sql`. Do not propose adding a test file unless asked.

## Where the code runs

**Everything runs on the UCR CS server.** No local Postgres, no SSH tunnel. Do not suggest `ssh -L`, port 5433, or installing Postgres locally.

Jorge edits locally and runs on the server. Code moves **by git only** — commit and push from the laptop, `git pull` on the server. Never copy-paste files onto the server.

- Host `cs166.cs.ucr.edu`, same machine as `xe-10.cs.ucr.edu`. Login `jcarb044`.
- Postgres on port `40875` (`$PGPORT`), `127.0.0.1` only. Database `jcarb044_DB` — the capital `DB` is literal.
- **The instance is a user process, not a service.** It dies on reboot and gets reaped. `cs166_db_status` / `cs166_db_start`. This is the first troubleshooting step for any connection failure, and the first thing to check before the demo.
- Plain `psql` fails — it looks for a socket in `/var/run/postgresql`. Use the `cs166_psql` wrapper. It supplies the socket path, so `-h` and `-p` are unnecessary. Remember `-c` for a one-off query, or psql reads the string as a username.
- Repo and venv live in home (`/home/csmajs/jcarb044`). `/extra` is ~100% full and `$PGDATA` is there, so disk-full errors are plausible.
- **Outbound port 22 is blocked** — GitHub SSH needs `~/.ssh/config` pointing `github.com` at `ssh.github.com:443`. HTTPS password auth does not work.

**PostgreSQL 10.23** (2017). No `CREATE INDEX ... INCLUDE` (PG 11+), no `CALL`, no stored procedures. Check syntax against PG 10 docs — modern tutorials hand over syntax that errors here. `CREATE INDEX CONCURRENTLY` also cannot be used, because `load_db.py` wraps every file in one transaction.

## Conventions

- **psycopg 3**, not psycopg2 — `import psycopg`. Do not copy psycopg2 snippets.
- **rich** for terminal UI. Python **3.14**. Package management is **uv** — no `pip`, no hand-editing dependencies.
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` come from `.env` (gitignored; `.env.example` is the template). Nothing is hardcoded and nothing branches on environment.
- On the server `.env` is `localhost` / `40875` / `jcarb044_DB` / `jcarb044` and an **empty** `DB_PASSWORD` — trust auth. The variable must still be present; `db.py` raises `KeyError` if absent.

Connection triage, in order: *connection refused* or *server closed the connection unexpectedly* means Postgres is down → `cs166_db_start`. *Connection timeout expired* means `.env` points somewhere unreachable. *Database does not exist* or *password authentication failed* is good news — Postgres answered, only the values are wrong.

## Working notes for Claude

- **Bash heredocs mangle backslashes on this content.** `\\n` inside a heredoc'd Python string has arrived as a real newline and silently broken a patch. Use the Write tool for any script containing escapes or source text; heredocs are fine for short throwaway Python with no backslashes.
- **A local `.env` points at the server**, so anything that opens a connection hangs on Windows rather than failing fast — psycopg has no default connect timeout. Verify imports, action lists and menu rendering locally; leave anything connection-dependent to be run by hand on the server.
- **`PYTHONIOENCODING=utf-8` in front of a command** makes a Windows terminal render what the server renders — symbols and box-drawing instead of the cp1252 fallback. This is how the UI gets previewed locally.
- **rich buffers output**, so a `UnicodeEncodeError` surfaces on a *later* print than the one that queued the bad character. `ui.py` checks `sys.stdout.encoding` up front instead of catching.
- **rich eats square brackets as markup** — literal ones need escaping as `\[n]ext`. This bit twice: once in `page()`, once on every user-entered table value (fixed on `ui_change`).
- **Counting lines of code:** use `ast` and treat a string as a docstring only when it is the first statement of a Module, ClassDef or FunctionDef. A naive tokenizer counts the multi-line SQL strings inside `conn.execute()` as docstrings and undercounts badly. Current totals on `main`: **1,453 code lines** — 1,018 Python + 435 SQL, plus 218 comment lines and 580 docstring lines.

## Where the notes live

None of these are in the repo's documentation path — they are gitignored working notes that ended up under `docs/trash/`.

| File | What it is |
|---|---|
| `README.md` | Setup and workflow. In the repo. |
| `docs/flow.md` | Build order and run order. In the repo. |
| `docs/presentation.md` | **The Thursday plan.** Run of show, the nine demo test cases with expected results, tuning numbers, limitations to volunteer, pre-flight checklist. |
| `docs/trash/architecture.md` | The why — the four schema traps, the contracts, the physical design, what was cut and the reasoning. Half of the report is already drafted here. |
| `docs/trash/overview.md` | The file-by-file map. |
| `docs/trash/issues.md` | Final status of all 21 issues. **Deliberately plain text — no Markdown markup at all.** Do not "improve" it by adding formatting. |
| `docs/trash/CS166-Project.pdf` | The instructor's spec. |

**Note:** those `docs/trash/` files are currently **tracked** — moving them into `trash/` took them out from under their `.gitignore` patterns, so they are back in the repo. If that is not wanted, add `docs/trash/` to `.gitignore` and `git rm -r --cached docs/trash`.
