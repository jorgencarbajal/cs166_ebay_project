# Architecture and design decisions

Why the system is shaped the way it is — the data model's non-obvious properties, the layering we chose, and what each decision cost us.

> **Status:** design, not yet code. Only `src/db.py` and `sql/schema.sql` exist today. This document is the reasoning three people are building against, written before the work split up.

Setup lives in the [README](../README.md). A file-by-file map lives in [overview.md](overview.md). Tasks live in [issues.md](issues.md). This file is about *why*.

---

## 1. The data model

The instructor supplied `sql/schema.sql` and it is used verbatim by the whole class. We do not edit it. Six tables: `users`, `item`, `auction`, `bid`, `payment`, `shipment`.

Four properties of it drive most of our design, and none of them are obvious from reading the file top to bottom.

### 1.1 `UNIQUE (login, role)` is load-bearing

`users` declares `login` as its primary key and then adds what looks like a pointless second constraint:

```sql
UNIQUE (login, role)
```

A unique constraint on a superset of the primary key is always satisfied, so it constrains nothing. It exists for a different reason: **it gives child tables something to reference.**

```sql
seller_role VARCHAR(10) NOT NULL DEFAULT 'Seller' CHECK (seller_role = 'Seller'),
FOREIGN KEY (seller_login, seller_role) REFERENCES users(login, role)
```

An `item` carries both the seller's login *and* a `seller_role` column pinned to `'Seller'` by a CHECK. The composite foreign key then forces that pair to exist in `users`. The net effect: **the database itself refuses to let a Buyer own an item.** The same trick pins `bid.buyer_role` and `payment.buyer_login` to `'Buyer'`.

This is a genuinely elegant way to express role-based integrity in pure SQL, with no triggers.

**What it costs us.** Those foreign keys are `ON UPDATE CASCADE`. Promoting or demoting a user rewrites `users.role`, which cascades into every dependent row's `*_role` column — and immediately violates the CHECK that pins it. Demote a Seller who owns items and `item.seller_role` cascades to `'Buyer'`, which `CHECK (seller_role = 'Seller')` rejects.

So "Admin changes a user's role," a one-line requirement in §6.1, is only safe when the user owns no dependent rows. Our policy is to detect that case up front and refuse with an explanation, rather than let a constraint violation surface as an unreadable error. This is a real, documentable limitation of the relational design — exactly the kind §2.2 asks groups to write down.

### 1.2 `current_highest_bid` is denormalized

`auction.current_highest_bid` duplicates something already derivable:

```sql
SELECT MAX(bid_amount) FROM bid WHERE auction_id = ?
```

Storing it anyway is the right call. Browse and search display the current price on every row, and recomputing an aggregate per row would turn a cheap listing query into an expensive one. It also gives the bid rule — "each new bid must be greater than the current highest" — a single column to compare against.

**What it costs us.** Two sources of truth that can disagree. Every bid must insert into `bid` **and** update `auction`, in one transaction, or the auction shows a stale price and subsequent bids validate against the wrong number.

It also creates a race. Two buyers reading `current_highest_bid = 50` simultaneously can both submit 55, and both pass validation. We take `SELECT ... FOR UPDATE` on the auction row so the second transaction waits for the first to commit and then re-reads the real value.

Realistically our demo is single-user, so this will never fire in practice. We do it anyway because it is correct, it costs one clause, and "how do you handle concurrent bids" is an obvious question to be asked during the demo.

### 1.3 Nothing auto-increments

Every primary key is a plain `INT`. No `SERIAL`, no `GENERATED ... AS IDENTITY`. The application generates ids for `item`, `auction`, `bid`, `payment`, and `shipment`.

The straightforward approach is `SELECT COALESCE(MAX(id), 0) + 1`, called inside the same transaction as the insert. Under concurrency it can hand the same number to two transactions, and the loser gets a unique violation.

**The alternative worth considering:** add our own sequences in `sql/indexes.sql` and call `nextval()`. Sequences are transaction-safe by design and never hand out a duplicate. This is a schema *extension* rather than a schema edit — §2.3 permits dataset and schema modification when documented, and §3 offers extra credit for meaningful extensions.

`MAX+1` is defensible for a single-user terminal demo. Sequences are the answer a database course is looking for. Whichever we pick, the reasoning goes in the report.

### 1.4 Auctions have no start or end time

There is no `end_time`, no `created_at`, nothing temporal on `auction` at all. The only timestamp in the entire schema is `bid.bid_timestamp`.

Per §6.3 an auction ends when its seller ends it — there is no scheduled expiry and nothing needs to run in the background. That simplifies the system considerably. It also means "search auctions" has no time dimension, and any report about auction duration would have to infer it from bid timestamps.

### 1.5 Other constraints worth knowing

- `auction.item_id` is `UNIQUE` — an item can be auctioned exactly once, ever.
- `payment.auction_id` and `shipment.auction_id` are both `UNIQUE` — one payment and one shipment per auction, so "already paid" is enforced by the database.
- `bid` is `ON DELETE CASCADE` from `auction`; everything else is `ON DELETE RESTRICT`. Deleting an item with an auction fails by design, which the admin delete feature has to handle deliberately.
- Passwords are `VARCHAR(100)` and stored in plain text. We keep it that way to stay compatible with the provided dataset, and record it as a documented limitation rather than quietly hashing.

---

## 2. Layering

```
main.py → menus/ → feature modules → db.py → PostgreSQL
```

Imports flow one direction only. The rule that gives the layering teeth:

> **Feature modules return data or raise. They never print. Menus catch and render.**

`bids.place()` does not know whether a person, a test, or a script called it. It raises `BidTooLow(current=45.00)`. `menus/buyer.py` catches that and decides the user sees a red line saying the bid must exceed $45.00.

**Why it earns its keep here.** Three people are writing menus at the same time on a ten-day deadline. Because presentation is confined to `ui.py` and the menu layer, restyling the whole interface later touches a handful of files — and interface quality is explicitly worth extra credit under §3. It also makes the business rules testable without a terminal, and puts each rule in exactly one place so it cannot be enforced inconsistently.

**What it costs.** More ceremony. Placing a bid touches three files instead of one, and `errors.py` is a file that exists purely to hold exception classes. On a small project you feel that cost immediately and the benefit only later.

### 2.1 Permission checks live in the feature modules

`require_role` is called inside the feature functions, not only when building the menu. Hiding an option from a Buyer's menu is not access control; it is decoration. The schema's role foreign keys would catch most violations anyway, but a raw constraint error is not an explanation.

### 2.2 Menus are split by role

`menus/buyer.py`, `menus/seller.py`, `menus/admin.py`. This mirrors how §6.1 divides privileges, and — the practical reason — it lets three people own three files instead of contending over one dispatch table.

Sellers and Admins get the buyer actions too, since §6.1 lists the base actions as available to all users with the others as *additional*.

---

## 3. Where SQL lives

Two rules that look contradictory and are not.

**Schema and dataset live in `.sql` files, never in Python strings.** `sql/schema.sql` and the data are the source of truth. If a server instance is lost — and it is a user process that dies on reboot, so this is not hypothetical — those files are what rebuild it. `scripts/load_db.py` is a thin runner that reads them off disk.

**Application queries live inline in the feature modules**, as parameterized strings next to the function that runs them. They are code: they change with the logic around them, and splitting them into 25 tiny files would mean a second file open for every debugging session and nothing gained.

The line between the two is *what has to survive losing the server*.

**Non-negotiable:** parameters are always passed as psycopg's second argument. Never build a query by concatenating user input, even for something as innocent as a search filter.

---

## 4. Transactions

Most operations are a single statement and need nothing special. Three are genuinely multi-step and must be atomic:

- **Placing a bid** — lock the auction, validate, insert the bid, update `current_highest_bid`. Discussed in §1.2 above.
- **Creating a listing** — insert the item and its auction together. An item with no auction is unreachable from every part of the UI.
- **Ending an auction** — find the highest bidder, set `winner_login`, set status to `Closed`. Half of that is worse than none of it.

psycopg 3 connections are context managers, so `with conn:` commits on success and rolls back on any exception. Since our exceptions *are* the failure signal, rollback is automatic — raising `BidTooLow` inside the block undoes the transaction for free.

---

## 5. Physical design

Worth 10% of the project grade, and the schema arrives with **no indexes beyond primary keys and unique constraints**. That empty space is the assignment.

The plan: get features working, capture the queries they actually run, record `EXPLAIN ANALYZE` baselines, add indexes in `sql/indexes.sql` one at a time, and re-measure. Likely candidates are `item(category)`, `item(item_name)` for the `ILIKE` search, `bid(auction_id, bid_amount DESC)` for finding a winner, and `auction(auction_status)`.

Indexes that turn out not to help are still findings, and saying so with numbers is worth more than a list of indexes with no measurements.

**The server runs PostgreSQL 10.23 (2017).** This is old enough to matter:

- `CREATE INDEX ... INCLUDE (...)` — covering indexes — is PG 11+ and will error.
- No `CALL`, no stored procedures. Functions only.
- None of the PG 11+ planner improvements.

Check syntax against the PostgreSQL 10 documentation. Anything written for a modern Postgres will hand you syntax that fails here.

One caveat: index effects are only measurable on enough rows. If the provided dataset is small, generating more is worth doing — §2.3 permits dataset modification when it is reported.

---

## 6. Decisions summarized

| Decision | Chosen | Alternative | Why |
|---|---|---|---|
| Connection lifetime | New connection per operation | One shared connection | Single-user app; a dead database fails loudly and immediately instead of leaving a stale handle |
| Row format | `dict_row` | Positional tuples | `row["bid_amount"]` cannot silently break when a column is added |
| Application SQL | Inline in modules | Separate `.sql` files | Queries are code; keeping them beside their logic is faster to write and debug |
| Schema and data | `.sql` files only | Python strings | They must survive losing the server instance |
| Presentation | Only in `ui.py` and menus | Modules print directly | One place to restyle; business rules stay testable |
| Menu structure | One file per role | Single dispatch table | Three people, three files, few conflicts |
| Primary keys | *Open* — `MAX+1` or sequences | — | See §1.3; decide before writing `ids.py` |
| Password storage | Plain text | Hashed | Compatibility with the provided dataset; documented as a limitation |
| Concurrency | `SELECT ... FOR UPDATE` on bids | Nothing | One clause, and it makes the demo answer defensible |

---

## 7. Known limitations

Collected here because §2.2 asks for them and the final report needs this list.

- **Role changes are restricted.** The composite role foreign keys make it unsafe to change a user's role once they own dependent rows. We detect and refuse rather than corrupt data. (§1.1)
- **Passwords are stored in plain text**, matching the schema and dataset. (§1.5)
- **`current_highest_bid` is denormalized** and correct only because every write path maintains it. Any future code path that inserts into `bid` directly would break that invariant. (§1.2)
- **Primary keys are generated by the application**, so id assignment is not concurrency-safe unless we adopt sequences. (§1.3)
- **Auctions cannot expire on their own** — there is nowhere in the schema to record an end time. (§1.4)
- **An item can only ever be auctioned once**, so a failed auction cannot be relisted without a new item row. (§1.5)
