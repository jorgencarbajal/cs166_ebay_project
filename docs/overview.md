# Codebase overview

A map of `src/` — what each file is responsible for, what it is allowed to import, and how one user action travels through the system.

> **Status (2026-08-21):** the foundation is built and the application runs. `db.py`, `errors.py`, `ui.py`, `auth.py`, all four files under `menus/`, and `main.py` exist and work — you can register, log in, reach your role's menu, and quit. The six **feature modules** are still docstrings, so every menu action currently says which issue will fill it in. See [issues.md](issues.md) for who is building what.

Setup instructions live in the [README](../README.md). Task breakdown lives in [issues.md](issues.md). This file is only about the code.

---

## The one rule

**Feature modules never print. Menu modules never contain business logic.**

A feature module takes a connection plus plain arguments, does the database work, and either returns data or raises an exception. It has no idea whether a human, a test, or a script called it. A menu module prompts the user, calls the feature module, catches whatever it raises, and renders the result.

If you find yourself importing `rich` into `bids.py`, or writing a `SELECT` inside `menus/buyer.py`, something has gone in the wrong file.

Why we care, given a ten-day deadline: three people are writing menus simultaneously. If presentation lives only in the menu layer, restyling the entire interface later touches three files instead of twelve — and interface quality is explicitly worth extra credit.

---

## Layers

```
main.py
   │
   ▼
menus/          ← prompts, printing, catching errors
   │
   ▼
feature modules ← business rules, SQL, transactions
   │
   ▼
db.py           ← connections, nothing else
   │
   ▼
PostgreSQL
```

Imports flow downward only. A feature module must never import a menu, and `db.py` must never import anything of ours at all.

---

## The foundation

Everything else depends on these. They were built first, by one person, before the feature work split three ways — because a half-finished `ui.py` blocks all three of us. **All of them exist and are tested.**

### `src/db.py` — connections

Reads `.env` and hands out psycopg connections with `dict_row` set, so every query returns dictionaries keyed by column name rather than positional tuples.

It does nothing else. It never creates tables, never drops them, never loads data. Importing it is always safe — which is deliberate, because the destructive work lives in `scripts/load_db.py` and a stray import must never be able to wipe a database.

### `src/errors.py` — the exception vocabulary

One class per business rule the application enforces: `BidTooLow`, `SelfBid`, `AuctionClosed`, `NotAuthorized`, `NotWinner`, `AlreadyPaid`, `PaymentIncomplete`, `LoginTaken`, `BadCredentials` — all inheriting from `AppError`.

They live together in one file so a menu can catch a specific one without importing five feature modules, and so the top-level loop can catch `AppError` as a blanket "the user did something the rules forbid" and print it in red.

Some carry data. `BidTooLow` holds the current high bid, so the menu can say *"must exceed $45.00"* rather than *"bid too low."*

> **There is no `src/session.py` and no `src/ids.py`.** Both were designed, then deleted before they were written. `Session` is a five-line dataclass and lives in `auth.py`; id generation moved into the database as sequences in `sql/extensions.sql`. Do not recreate either file.

### `src/ui.py` — everything the user sees

The only module in the project that imports `rich`.

Holds the shared console, `success` / `error` / `warn` / `info`, `heading`, `blank`, a `table()` that renders the `dict_row` dictionaries the feature modules return, `page()` for anything longer than a screen, a numbered `menu()`, and prompt helpers that re-ask on invalid input instead of crashing.

Money is `NUMERIC(10,2)` in the schema, so prompts return `Decimal`, never `float`. That conversion happens here once rather than being reinvented in six modules.

Symbols degrade gracefully: `ui.py` checks `sys.stdout.encoding` at import and falls back from `✓ ✗ ⚠ ·` to `OK / !! / ?? / --` where the terminal cannot render them. That fallback is why the interface can be previewed off-server with `scripts/ui_demo.py`.

### `src/auth.py` — registration and login, and the `Session`

`register()` inserts a new user and returns a `Session`; `login()` verifies credentials and returns a `Session`. Both raise from `errors.py` — `LoginTaken` and `BadCredentials`.

New accounts are always `Buyer` — the schema defaults it and only an Admin can change it, so `register()` deliberately takes no role parameter and omits the column from its `INSERT`.

This file also holds the two things that were once going to be `session.py`:

- **`Session`** — a frozen dataclass of `login` and `role`. Not a database session and holds no connection; it is the app's memory of who is logged in, held in a variable in `menus/__init__.py` and thrown away on logout. `frozen=True` means nothing downstream can quietly promote itself to Admin.
- **`require_role(session, required_role, action)`** — raises `NotAuthorized` or returns quietly. Call it at the top of any restricted feature function. Hiding a menu option is not access control; the graders will try calling things they shouldn't be able to.

**Every feature function takes a `Session`, never a bare login string.** That way identity always traces back to an actual login and a caller cannot act as someone else by passing a different username.

---

## Feature modules

One per entity in the schema, so "which file does this belong in" is never a debate.

| File | Owns | Backed by |
|---|---|---|
| `users.py` | view/edit profile, admin user management, role changes | `users` |
| `items.py` | create and update listings, admin item management | `item` |
| `auctions.py` | browse, search, auction detail, ending an auction | `auction` |
| `bids.py` | placing bids, bid history | `bid` |
| `payments.py` | paying for a won auction | `payment` |
| `shipments.py` | creating and updating shipments | `shipment` |

**Each function opens its own connection and takes a `Session`, not a `conn`.** This is settled — `auth.py` is the worked example:

```python
def place(session, auction_id, amount):
    with get_connection() as conn:
        ...
```

The earlier draft of this document had feature functions take `conn` as their first argument. That was reconsidered: passing a connection in means the *menu* has to open it, which drags transaction management up into the layer that is supposed to contain no logic at all. Opening it here keeps the whole transaction inside the one function that owns the rule.

`with get_connection() as conn:` commits on a clean exit and rolls back if an exception escapes, so **there is no `conn.commit()` anywhere in this project** and raising an `AppError` mid-transaction undoes it for free.

The multi-step operations — placing a bid, ending an auction — are each a single function, so "one function, one connection, one transaction" holds everywhere. None of these modules print.

SQL is written inline, as parameterized query strings next to the function that runs it. This is a deliberate exception to the rule that SQL lives in `.sql` files — that rule protects `schema.sql` and the dataset, which must survive losing the server. Application queries are code, and they are easier to read and debug beside the logic that uses them.

**Never build a query by string-concatenating user input.** Always pass parameters as psycopg's second argument.

---

## Menus

```
src/menus/
  __init__.py    login gate, then dispatch on role
  buyer.py
  seller.py
  admin.py
```

Split by role for two reasons: it mirrors how the spec divides privileges, and it means three people can own three files and rarely touch the same lines.

**`__init__.py` owns all the control flow. The three role files own none of it.** That division is the thing to understand before touching either.

`__init__.py` holds three nested loops:

```
run()                  the login gate — log in, register, or quit
  run_role_menu()      one role's actions, repeating until Log out
    one action         does its work, prints, returns to the menu above
```

plus `dispatch()` (role → module), `do_login()`, and `do_register()`. It also holds the `except AppError` that protects **every action in the application** — one try/except, not one per feature — so a broken business rule prints a red line and returns to the menu rather than killing the program.

`buyer.py`, `seller.py`, and `admin.py` export exactly two names and nothing else:

```python
TITLE = "Buyer menu"

ACTIONS = [
    ("browse", "Browse open auctions", browse_auctions),
    ("bid",    "Place a bid",          place_bid),
]
```

No `while` loop, no `try/except`, no rendering. An action function takes the `Session` and returns nothing. `Log out` and `Quit` are appended by `run_role_menu()`, so never list them yourself.

Sellers and Admins can do everything a Buyer can — the spec lists the base actions as available to all users, with seller and admin abilities as *additional*. So `seller.py` starts from `list(buyer.ACTIONS)` and appends, and `admin.py` starts from `list(seller.ACTIONS)`. The `list()` is a copy, not an alias: without it, appending would mutate the Buyer menu too.

**The role files must never import `menus/__init__.py`.** Imports run one direction — `__init__` imports the three role files, they import `ui` and the feature modules. Reverse it and Python hits a half-built module and fails.

**To add a feature:** write the function in its feature module, then replace the placeholder body in your role file. You do not touch `__init__.py`.

---

## How one action flows

Placing a bid, end to end:

1. **`menus/__init__.py`** draws the Buyer menu, the user picks "Place a bid", and `run_role_menu()` calls `buyer.place_bid(session)` inside its `try`.
2. **`menus/buyer.py`** prompts for an auction id and an amount, converting the amount to `Decimal` via `ui.prompt_decimal`.
3. It calls `bids.place(session, auction_id, amount)`.
4. **`bids.py`** opens a connection, locks the auction row with `SELECT ... FOR UPDATE`, and checks the rules: auction is `Active`, the bidder is not the seller, the amount beats both `current_highest_bid` and the item's `starting_price`.
5. If a rule fails it raises — `BidTooLow(amount, minimum)`, `SelfBid`, or `AuctionClosed`. The exception escapes the `with` block, so psycopg rolls the transaction back automatically.
6. If everything passes it inserts the bid **omitting `bid_id`** and takes the generated id back with `RETURNING bid_id`, updates `auction.current_highest_bid`, and returns. Leaving the `with` block commits.
7. **`menus/buyer.py`** calls `ui.success` with the new bid id — or, if the feature module raised, never runs at all, because `run_role_menu()` caught the `AppError` and printed it in red.

Note what each layer does not do. The menu knows no SQL. The feature module knows nothing about terminals. Neither one writes a `try/except` for business rules — that lives in `run_role_menu()`, once. The rules are enforced in exactly one place, so they hold no matter who calls.

---

## Outside `src/`

```
main.py                 entry point — checks the database is reachable, hands control to menus/
scripts/load_db.py      run by hand; the only destructive code we write
scripts/ui_demo.py      run by hand; previews the interface, needs no database
sql/schema.sql          the instructor's schema, verbatim, never edited
sql/extensions.sql      ours: one sequence per numeric-PK table
sql/seed.sql            ours: the dataset
sql/indexes.sql         ours: physical design work (empty until there is data to measure)
docs/                   this file, architecture.md, issues.md, the spec, the final report
```

There is no `data/` directory — the dataset is generated in SQL rather than loaded from files.

`scripts/` versus `src/` is the important line: **things you import** versus **things you run on purpose**. `load_db.py` drops all six tables. It is a script precisely so that no import can ever trigger it.

`main.py` is deliberately tiny. It runs one `SELECT 1` so a dead Postgres is reported before anyone types a password, then calls `menus.run()`. It catches `OperationalError` and `KeyboardInterrupt` and nothing else — `AppError` is handled below it, and anything else is a bug and is allowed to crash with its traceback intact.

**There is no automated test suite.** You check your work by running the application against the seed data and walking the cases yourself. Every issue in [issues.md](issues.md) carries a `TESTING AGAINST SEED DATA` section naming the exact rows that exercise it — which auction has no bids, which was won and never paid, which items have no auction yet. Work that list before opening a PR.

---

## Things that will trip you up

Four properties of the schema that reading `schema.sql` top to bottom will not make obvious. Each is explained in full in [architecture.md](architecture.md).

- **`UNIQUE (login, role)` on `users` is load-bearing.** It looks redundant beside the `login` primary key. It exists so child tables can foreign-key to `(login, role)` and pin the role with a CHECK — which is how "only Sellers own items" is enforced by the database rather than by us. The consequence is that changing someone's role is genuinely difficult once they own rows.
- **`auction.current_highest_bid` is denormalized.** The same fact lives in `bid` and on `auction`. Placing a bid must update both, in one transaction, or they drift apart.
- **Nothing auto-increments in the instructor's schema** — but we fixed it. `sql/extensions.sql` adds one sequence per numeric-PK table and wires it in as the column `DEFAULT`. So in practice ids generate themselves, provided you let them: **omit the id column from every `INSERT` and use `RETURNING`.** `users` is the exception, since its primary key is the `login` string.
- **Auctions have no start or end time.** No column for it. An auction ends when its seller ends it, and never otherwise.

One more, added since: **`sql/seed.sql` uses explicit ids** — a seed file has to reference its own rows — and therefore ends with a `setval` block that pushes each sequence past the seeded data. If you edit the seed, that block stays last.
