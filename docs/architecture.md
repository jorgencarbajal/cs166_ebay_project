# Architecture and design decisions

The data model, the decisions we made, and what we gave up for each one.

> **Status (2026-08-21):** the foundation is built. Section 1.3 is settled — we use sequences, and they are loaded on the server. The six feature modules are not written yet, so sections 4 and 5 describe the plan rather than the code.

Setup is in the [README](../README.md). A file-by-file map is in [overview.md](overview.md). Tasks are in [issues.md](issues.md). This file is about *why*.

---

## 1. The data model

The instructor gave us `sql/schema.sql` and the whole class uses it as-is. We do not edit it. Six tables: `users`, `item`, `auction`, `bid`, `payment`, `shipment`.

Four things about it are not obvious from reading the file, and all four affect how we write code.

### 1.1 `UNIQUE (login, role)` matters more than it looks

`users` has `login` as its primary key, then adds this:

```sql
UNIQUE (login, role)
```

That constraint can never fail — `login` is already unique on its own. So why is it there? **So other tables can point at it.**

```sql
seller_role VARCHAR(10) NOT NULL DEFAULT 'Seller' CHECK (seller_role = 'Seller'),
FOREIGN KEY (seller_login, seller_role) REFERENCES users(login, role)
```

An `item` stores the seller's login *and* a `seller_role` column locked to `'Seller'` by a CHECK. The foreign key then requires that pair to exist in `users`. Result: **the database refuses to let a Buyer own an item.** Same trick locks `bid.buyer_role` to `'Buyer'`.

It's a clean way to enforce roles in pure SQL, with no triggers.

**The cost.** Those foreign keys are `ON UPDATE CASCADE`. Changing `users.role` cascades into every child row's `*_role` column, which then breaks the CHECK that locks it. Demote a Seller who owns items, and `item.seller_role` changes to `'Buyer'`, which `CHECK (seller_role = 'Seller')` rejects.

So "Admin changes a user's role" only works if the user owns no rows in other tables. We check first and refuse with a clear message. This goes in the report as a limitation of the design (§2.2 asks for exactly this).

### 1.2 `current_highest_bid` is stored twice

`auction.current_highest_bid` duplicates something you could calculate:

```sql
SELECT MAX(bid_amount) FROM bid WHERE auction_id = ?
```

Storing it is still the right call. Browse and search show the current price on every row, and running that aggregate per row would make a cheap query expensive. It also gives the bid rule one column to compare against.

**The cost.** Two copies of the same fact, and they can disagree. Every bid has to insert into `bid` **and** update `auction`, in one transaction — otherwise the auction shows a stale price and the next bid is checked against the wrong number.

There's also a race. Two buyers both read `current_highest_bid = 50` and both bid 55. Both pass validation. We use `SELECT ... FOR UPDATE` on the auction row so the second one waits for the first to finish, then re-reads the real value.

Our demo is single-user, so this will never actually happen. We do it anyway: it costs one clause, and "how do you handle two bids at once" is an obvious demo question.

### 1.3 Nothing auto-increments, so we added sequences

Every primary key is a plain `INT`. No `SERIAL`, no `IDENTITY`. Something has to produce the next id for `item`, `auction`, `bid`, `payment`, and `shipment`.

**Settled 2026-08-20: we add our own sequences.** `sql/extensions.sql` makes one per table and sets it as the column default:

```sql
CREATE SEQUENCE item_id_seq;
ALTER TABLE item ALTER COLUMN item_id SET DEFAULT nextval('item_id_seq');
ALTER SEQUENCE item_id_seq OWNED BY item.item_id;
```

That is what `SERIAL` does internally. We write it by hand because we can't edit the instructor's `CREATE TABLE`.

**What we rejected:** `SELECT COALESCE(MAX(id), 0) + 1` in Python. It has to run in the same transaction as the insert, two transactions can still read the same `MAX` and collide, and every insert would need retry logic. Sequences never hand out a duplicate and need no retries. `src/ids.py` was deleted before it was written.

**Bonus:** this is a schema *extension*, not an edit. §2.3 allows it if documented, §3 gives extra credit for it. This section is the documentation.

**The cost:** every `INSERT` must leave the id column out and use `RETURNING` to get it back. Name the id yourself and you defeat the default. `users` has no sequence — its key is the `login` string.

**One gotcha.** `sql/seed.sql` uses explicit ids, because a seed file has to reference its own rows. That means the sequences never move while it loads, so the first insert from the app would ask for `1` and collide. `seed.sql` ends with a `setval` block that pushes each sequence past the seeded rows. **That block stays last.**

### 1.4 Auctions have no start or end time

No `end_time`, no `created_at`, nothing. The only timestamp in the whole schema is `bid.bid_timestamp`.

Per §6.3 an auction ends when the seller ends it. Nothing expires on a schedule and nothing runs in the background, which makes the system simpler. It also means search has no time filter, and any report about how long an auction ran would have to work it out from bid timestamps.

### 1.5 Other constraints worth knowing

- `auction.item_id` is `UNIQUE` — an item can be auctioned once, ever.
- `payment.auction_id` and `shipment.auction_id` are `UNIQUE` — one payment and one shipment per auction, so the database enforces "already paid."
- `bid` is `ON DELETE CASCADE` from `auction`. Everything else is `ON DELETE RESTRICT`, so deleting an item that has an auction fails on purpose. The admin delete feature has to handle that.
- Passwords are `VARCHAR(100)`, plain text. We keep it that way and record it as a limitation instead of quietly hashing.

---

## 2. Layering

```
main.py → menus/ → feature modules → db.py → PostgreSQL
```

Imports go one direction only. The rule that makes the layers real:

> **Feature modules return data or raise an error. They never print. Menus catch errors and display things.**

`bids.place()` doesn't know if a person, a test, or a script called it. It raises `BidTooLow`. `menus/buyer.py` catches it and decides the user sees a red line.

**Why it's worth it.** Three people write menus at the same time. Keeping all display code in `ui.py` and the menu layer means restyling the interface later touches a few files instead of twelve — and interface quality is worth extra credit under §3. It also means the rules can be tested without a terminal, and each rule exists in one place so it can't be enforced two different ways.

**The cost.** More files. Placing a bid touches three of them, and `errors.py` exists only to hold exception classes. On a project this size you feel that immediately and the benefit only later.

### 2.1 Permission checks go in the feature modules

`require_role` is called inside the feature function, not just when building the menu. Hiding an option from a Buyer's menu is not security — it's decoration. The schema's role foreign keys would catch most of it anyway, but a raw constraint error doesn't explain anything to the user.

### 2.2 Menus are split by role

`menus/buyer.py`, `menus/seller.py`, `menus/admin.py`. This matches how §6.1 splits privileges, and it lets three people own three files instead of fighting over one.

Sellers and Admins get the Buyer actions too, since §6.1 says the base actions are available to everyone. `seller.py` starts from `list(buyer.ACTIONS)` and adds to it; `admin.py` starts from `list(seller.ACTIONS)`.

**Settled 2026-08-21: the role files have no control flow.** They export a `TITLE` string and an `ACTIONS` list of `(key, label, function)` triples. `menus/__init__.py` has the one loop that displays any of them, calls the chosen function, and catches `AppError`.

The alternative was each role file running its own `while` loop and its own `try/except`. Three reasons we didn't:

- **One `except AppError` for the whole app** instead of one per action. Errors look the same everywhere, and nobody can forget to catch one.
- **Two of these three files belong to people who didn't build the rest of the system.** Giving them a list to fill in is safer than giving them a loop to get right.
- **No circular import.** The first draft had the role files importing `run_role_menu` from `menus/__init__.py`, which fails — Python hits a half-built module. Exporting only data keeps imports going one way.

The cost: reading `buyer.py` doesn't show you the loop that runs it. Each role file's docstring says where to look.

---

## 3. Where SQL lives

Two rules that sound contradictory but aren't.

**Schema and data live in `.sql` files, never in Python strings.** `sql/schema.sql`, `extensions.sql`, and `seed.sql` are the source of truth. The Postgres instance is a user process that dies on reboot, so losing it is realistic — those files are what rebuild it. `scripts/load_db.py` just reads and runs them.

**Application queries live inline in the feature modules**, next to the function that uses them. They're code: they change when the logic changes, and splitting them into 25 tiny files would mean opening a second file every time you debug.

The line between the two: **does it need to survive losing the server?**

**Never negotiable:** pass parameters as psycopg's second argument. Never build a query by concatenating user input, not even a search filter.

---

## 4. Transactions

Most operations are one statement and need nothing special. Three are multi-step and have to be all-or-nothing:

- **Placing a bid** — lock the auction, validate, insert the bid, update `current_highest_bid`. See §1.2.
- **Ending an auction** — find the highest bidder, set `winner_login`, set status to `Closed`. Half of that is worse than none.
- **Paying for a won auction** — insert the payment and create the `Pending` shipment together, so nothing ends up paid for but unshippable.

**Listing an item and auctioning it are two separate actions, not one transaction.** An earlier draft said to do both at once. We changed it: `auction.item_id` is `UNIQUE`, so auctioning is permanent, and a Seller should be able to fix a typo before the listing goes live. `sql/seed.sql` has two items with no auction so this path has test data.

**Every feature function opens its own connection** and runs its whole transaction inside it:

```python
with get_connection() as conn:
    ...
```

We don't pass `conn` in from the menu, because that would put transaction management in the layer that's supposed to have no logic.

psycopg 3 connections are context managers: leaving the block commits, and an exception escaping rolls back. Our exceptions *are* the failure signal, so rollback is free — raising `BidTooLow` inside the block undoes the transaction. **There is no `conn.commit()` anywhere in this project.**

---

## 5. Physical design

Worth 10% of the grade. The schema ships with **no indexes except primary keys and unique constraints**. Filling that gap is the assignment.

The plan: get features working, note which queries they actually run, record `EXPLAIN ANALYZE` before, add indexes to `sql/indexes.sql` one at a time, measure again.

Likely candidates:

| Index | For |
|---|---|
| `item(category)` | browse and search filters |
| `item(item_name)` | the `ILIKE` name search |
| `bid(auction_id, bid_amount DESC)` | finding an auction's winner |
| `auction(auction_status)` | listing only Active auctions |

An index that turns out not to help is still a finding. Reporting that with numbers is worth more than a list of indexes with no measurements.

**The server runs PostgreSQL 10.23 (2017).** Old enough to matter:

- `CREATE INDEX ... INCLUDE (...)` is PG 11+ and will error.
- No `CALL`, no stored procedures. Functions only.
- None of the PG 11+ planner improvements.

Check syntax against the PostgreSQL 10 docs. Modern tutorials will give you syntax that fails here.

**One catch:** indexes only show a difference on enough rows. `sql/seed.sql` today is 38 rows — sized to unblock feature work, not to move a query plan. Issue #17 needs bulk data first, which is what `generate_series` is for. §2.3 allows changing the dataset if we report it, which is also why the seeding choices go in the report.

---

## 6. Decisions summarized

| Decision | Chosen | Alternative | Why |
|---|---|---|---|
| Connection lifetime | New connection per operation | One shared connection | Single-user app; a dead database fails immediately instead of leaving a stale handle |
| Row format | `dict_row` | Positional tuples | `row["bid_amount"]` can't silently break when a column is added |
| Application SQL | Inline in modules | Separate `.sql` files | Queries are code; keeping them next to their logic is faster to debug |
| Schema and data | `.sql` files only | Python strings | They have to survive losing the server |
| Display code | Only in `ui.py` and menus | Modules print directly | One place to restyle; rules stay testable |
| Menu structure | One file per role | Single dispatch table | Three people, three files, few conflicts |
| Primary keys | Sequences in `extensions.sql` | `MAX+1` in Python | No locking, no retries; also a documented extension worth extra credit (§1.3) |
| Connection ownership | Feature function opens its own | Menu passes `conn` in | Keeps the transaction inside the function that owns the rule (§4) |
| Menu control flow | One loop in `menus/__init__.py` | A loop per role file | One `except AppError` for the whole app; role files stay a list (§2.2) |
| `Session` | A dataclass in `auth.py` | A `session.py` module | Five lines and one function didn't justify a file |
| Passwords | Plain text | Hashed | Matches the schema and the seed data; documented as a limitation |
| Concurrency | `SELECT ... FOR UPDATE` on bids | Nothing | One clause, and it makes the demo answer defensible |

---

## 7. Known limitations

§2.2 asks for these and the final report needs the list.

- **Role changes are restricted.** The composite role foreign keys make it unsafe to change someone's role once they own rows elsewhere. We detect it and refuse rather than corrupt data. (§1.1)
- **Passwords are plain text.** (§1.5)
- **`current_highest_bid` is duplicated data**, correct only because every write path maintains it. Any future code that inserts into `bid` directly would break it. (§1.2)
- **Primary keys come from sequences we added**, not from the instructor's schema. `sql/extensions.sql` must load after `sql/schema.sql` or every insert fails. (§1.3)
- **Auctions can't expire on their own** — there's nowhere in the schema to store an end time. (§1.4)
- **An item can only be auctioned once**, so a failed auction can't be relisted without creating a new item. (§1.5)
