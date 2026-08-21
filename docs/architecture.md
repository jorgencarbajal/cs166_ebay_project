# Architecture and design decisions

Why the system is shaped the way it is — the data model's non-obvious properties, the layering we chose, and what each decision cost us.

> **Status (2026-08-21):** the foundation is built and the reasoning below has been tested against real code. Section 1.3 in particular is no longer an open question — we adopted sequences and they are loaded on the server. The six feature modules are still unwritten, so sections 4 and 5 remain forward-looking.

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

### 1.3 Nothing auto-increments — so we added sequences

Every primary key in the instructor's schema is a plain `INT`. No `SERIAL`, no `GENERATED ... AS IDENTITY`. Something has to invent the next id for `item`, `auction`, `bid`, `payment`, and `shipment` on every insert.

**Settled 2026-08-20: we add our own sequences.** `sql/extensions.sql` creates one per numeric-PK table and wires it in as the column `DEFAULT`, which is exactly what `SERIAL` does under the hood — written out by hand because we are not allowed to edit the instructor's `CREATE TABLE`.

```sql
CREATE SEQUENCE item_id_seq;
ALTER TABLE item ALTER COLUMN item_id SET DEFAULT nextval('item_id_seq');
ALTER SEQUENCE item_id_seq OWNED BY item.item_id;
```

**The alternative we rejected** was `SELECT COALESCE(MAX(id), 0) + 1` in the application. It has to run inside the same transaction as the insert it feeds, two transactions can still read the same `MAX` and collide on a unique violation, and so every insert in the project would need retry logic wrapped around it. A sequence hands out a guaranteed-unique number with no locking and no retries. `src/ids.py` was deleted before it was written.

**What this buys us beyond correctness:** it is a schema *extension* rather than a schema edit, which §2.3 permits when documented and §3 offers extra credit for. This section is that documentation.

**What it costs:** every `INSERT` must omit the id column and use `RETURNING` to get it back. Name the id explicitly and you defeat the default. `users` has no sequence — its primary key is the `login` string the user types at registration.

**One consequence to remember.** `sql/seed.sql` supplies explicit ids, because a seed file has to reference its own rows. The sequences therefore never advance while it loads and would hand out `1` again, colliding with seeded data on the first insert through the app. `seed.sql` ends with a `setval` block that pushes each sequence past the seeded rows, and that block must stay last.

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

Sellers and Admins get the buyer actions too, since §6.1 lists the base actions as available to all users with the others as *additional*. `seller.py` starts from `list(buyer.ACTIONS)` and appends; `admin.py` starts from `list(seller.ACTIONS)`.

**Settled 2026-08-21: the role files contain no control flow.** They export a `TITLE` string and an `ACTIONS` list of `(key, label, function)` triples, and `menus/__init__.py` holds the single generic loop that renders any of them, dispatches, and catches `AppError`.

The alternative was for each role file to run its own `while` loop with its own `try/except`. Three reasons we did not:

- **One `except AppError` for the whole application** instead of one per action. A `BidTooLow` is rendered identically no matter where it came from, and nobody can forget to catch it.
- **Two of these three files are owned by people who have not written the rest of the system.** Handing them a list to fill in rather than a loop to get right is the cheapest risk reduction available.
- **No circular import.** The first draft had the role files importing `run_role_menu` back out of `menus/__init__.py`, which fails — Python reaches a half-built module. Data-only exports keep imports flowing one direction, consistent with §2 above.

The cost is one indirection: reading `buyer.py` does not show you the loop that runs it. The docstring at the top of each role file says where to look.

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
- **Ending an auction** — find the highest bidder, set `winner_login`, set status to `Closed`. Half of that is worse than none of it.
- **Paying for a won auction** — insert the payment and create the `Pending` shipment together, so nothing ends up paid for and unshippable.

**Listing an item and auctioning it are deliberately separate operations**, not one transaction. An earlier draft of this section said to insert the item and its auction together. Reconsidered: `auction.item_id` is `UNIQUE`, so an item can be auctioned exactly once ever, and forcing the two together means a Seller can never hold a listing back or fix a typo before it goes live. `sql/seed.sql` carries two items with no auction precisely so this path has test data.

**Every feature function opens its own connection and runs its whole transaction inside it** — `with get_connection() as conn:`. Connections are not passed in from the menu layer, because that would drag transaction management up into the layer that is supposed to hold no logic. psycopg 3 connections are context managers, so leaving the block commits and an escaping exception rolls back. Since our exceptions *are* the failure signal, rollback is automatic — raising `BidTooLow` inside the block undoes the transaction for free, and **there is no `conn.commit()` anywhere in this project**.

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

One caveat: index effects are only measurable on enough rows. **`sql/seed.sql` today is a development dataset, not a measurement one** — 38 rows, sized to unblock feature work rather than to move a query plan. Before #17 can produce a real number, it needs bulk data, which is what `generate_series` is for. §2.3 permits dataset modification when it is reported, and §2.3 is also why the seeding choices go in the report.

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
| Primary keys | Sequences in `sql/extensions.sql` | `MAX+1` in Python | No locking, no retries, no same-transaction constraint; also a documented schema extension worth extra credit (§1.3) |
| Connection ownership | Each feature function opens its own | Menu passes `conn` in | Keeps the whole transaction inside the function that owns the rule (§4) |
| Menu control flow | One generic loop in `menus/__init__.py` | A loop per role file | One `except AppError` for the whole app; role files stay a list two teammates can safely fill in (§2.2) |
| `Session` | A dataclass inside `auth.py` | A `session.py` module | Five lines and one function did not justify a module |
| Password storage | Plain text | Hashed | Compatibility with the provided dataset; documented as a limitation |
| Concurrency | `SELECT ... FOR UPDATE` on bids | Nothing | One clause, and it makes the demo answer defensible |

---

## 7. Known limitations

Collected here because §2.2 asks for them and the final report needs this list.

- **Role changes are restricted.** The composite role foreign keys make it unsafe to change a user's role once they own dependent rows. We detect and refuse rather than corrupt data. (§1.1)
- **Passwords are stored in plain text**, matching the schema and dataset. (§1.5)
- **`current_highest_bid` is denormalized** and correct only because every write path maintains it. Any future code path that inserts into `bid` directly would break that invariant. (§1.2)
- **Primary keys are generated by sequences we added ourselves**, not by the instructor's schema. This is a documented extension rather than a limitation, but it means our `sql/extensions.sql` must be loaded after `sql/schema.sql` or every insert fails. (§1.3)
- **Auctions cannot expire on their own** — there is nowhere in the schema to record an end time. (§1.4)
- **An item can only ever be auctioned once**, so a failed auction cannot be relisted without a new item row. (§1.5)
