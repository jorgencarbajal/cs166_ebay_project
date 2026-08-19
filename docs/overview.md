# Codebase overview

A map of `src/` — what each file is responsible for, what it is allowed to import, and how one user action travels through the system.

> **Status:** most of this is design, not code. Only `src/db.py` and `sql/schema.sql` exist today. Everything else is the shape we agreed on before splitting up the work, so that three people writing in parallel end up with one coherent program instead of three. If a file described here is missing, it has not been written yet — see `docs/issues.md` for who is building what.

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

Five files that everything else depends on. These are built first, by one person, before the feature work splits three ways — because a half-finished `ui.py` blocks all three of us.

### `src/db.py` — connections *(exists)*

Reads `.env` and hands out psycopg connections with `dict_row` set, so every query returns dictionaries keyed by column name rather than positional tuples.

It does nothing else. It never creates tables, never drops them, never loads data. Importing it is always safe — which is deliberate, because the destructive work lives in `scripts/load_db.py` and a stray import must never be able to wipe a database.

### `src/errors.py` — the exception vocabulary

One class per business rule the application enforces: `BidTooLow`, `SelfBid`, `AuctionClosed`, `NotAuthorized`, `NotWinner`, `AlreadyPaid`, `PaymentIncomplete`, `LoginTaken`, `BadCredentials` — all inheriting from `AppError`.

They live together in one file so a menu can catch a specific one without importing five feature modules, and so the top-level loop can catch `AppError` as a blanket "the user did something the rules forbid" and print it in red.

Some carry data. `BidTooLow` holds the current high bid, so the menu can say *"must exceed $45.00"* rather than *"bid too low."*

### `src/session.py` — who is logged in

A small dataclass holding `login` and `role`, passed down into the menus rather than kept in a global.

It also holds `require_role(session, "Admin")`, which raises `NotAuthorized`. Permission checks belong in the feature modules, not only in the menus — hiding a menu option is not access control, and the graders will try calling things they shouldn't be able to.

### `src/ids.py` — primary key generation

Nothing in the instructor's schema auto-increments. Every primary key is a plain `INT`, so we generate ids for `item`, `auction`, `bid`, `payment`, and `shipment` ourselves.

`next_id(conn, table, column)` returns `MAX(col) + 1`. It **must** be called inside the same transaction as the insert it feeds, or two concurrent inserts will compute the same number.

### `src/ui.py` — everything the user sees

The only module in the project that imports `rich`.

Holds the shared console, `success` / `error` / `warn` / `info`, a `table()` that renders the `dict_row` dictionaries the feature modules return, a numbered `menu()`, and prompt helpers that re-ask on invalid input instead of crashing.

Money is `NUMERIC(10,2)` in the schema, so prompts return `Decimal`, never `float`. That conversion happens here once rather than being reinvented in six modules.

### `src/auth.py` — registration and login

`register()` inserts a new user and returns a `Session`; `login()` verifies credentials and returns a `Session`.

New accounts are always `Buyer` — the schema defaults it and only an Admin can change it, so `register()` deliberately takes no role parameter.

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

Each function takes `conn` as its first argument. None of them open their own connections, and none of them print.

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

`__init__.py` shows the opening menu (log in, register, quit), and once a `Session` exists, dispatches to the matching role menu. It also holds the top-level `except AppError`, so a broken business rule prints a red line and returns to the menu rather than killing the program.

Sellers and Admins can do everything a Buyer can — the spec lists the base actions as available to all users, with seller and admin abilities as *additional*. So the seller and admin menus include the buyer options rather than duplicating that code.

---

## How one action flows

Placing a bid, end to end:

1. **`menus/buyer.py`** prompts for an auction id and an amount, converting the amount to `Decimal` via `ui.prompt_decimal`.
2. It calls `bids.place(conn, auction_id, session.login, amount)`.
3. **`bids.py`** opens a transaction, locks the auction row with `SELECT ... FOR UPDATE`, and checks the rules: auction is `Active`, the bidder is not the seller, the amount beats both `current_highest_bid` and the item's `starting_price`.
4. If a rule fails it raises — `BidTooLow(current)`, `SelfBid`, or `AuctionClosed` — and the transaction rolls back.
5. If everything passes it gets a `bid_id` from `ids.next_id`, inserts the bid, updates `auction.current_highest_bid`, commits, and returns the new id.
6. **`menus/buyer.py`** either calls `ui.success` with the new bid id, or catches the exception and calls `ui.error` with its message.

Note what each layer does not do. The menu knows no SQL. The feature module knows nothing about terminals. The rules are enforced in exactly one place, so they hold no matter who calls.

---

## Outside `src/`

```
main.py                 entry point — hands control to menus/
scripts/load_db.py      run by hand; the only destructive code we write
sql/schema.sql          the instructor's schema, verbatim, never edited
sql/indexes.sql         our physical design work
data/                   the dataset
docs/                   this file, issues.md, the spec, the final report
```

`scripts/` versus `src/` is the important line: **things you import** versus **things you run on purpose**. `load_db.py` drops all six tables. It is a script precisely so that no import can ever trigger it.

---

## Things that will trip you up

Four properties of the schema that reading `schema.sql` top to bottom will not make obvious. Each is explained in full in [architecture.md](architecture.md).

- **`UNIQUE (login, role)` on `users` is load-bearing.** It looks redundant beside the `login` primary key. It exists so child tables can foreign-key to `(login, role)` and pin the role with a CHECK — which is how "only Sellers own items" is enforced by the database rather than by us. The consequence is that changing someone's role is genuinely difficult once they own rows.
- **`auction.current_highest_bid` is denormalized.** The same fact lives in `bid` and on `auction`. Placing a bid must update both, in one transaction, or they drift apart.
- **Nothing auto-increments.** Every insert needs an id from `ids.next_id`.
- **Auctions have no start or end time.** No column for it. An auction ends when its seller ends it, and never otherwise.
