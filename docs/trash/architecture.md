# Architecture — the why

Last updated **2026-08-25**. Working notes. `overview.md` says what each file is; this says why it is shaped that way.

## 1. The four schema properties that drove everything

The logical schema was handed to us and never edited. Four of its properties are not obvious from reading `CREATE TABLE`, and each one dictated a design decision.

### `UNIQUE (login, role)` on `users` is load-bearing

It exists so child tables can foreign-key to `(login, role)` and pin the role with a CHECK — `item.seller_role = 'Seller'`, `bid.buyer_role = 'Buyer'`. That is how role-based integrity is enforced in pure SQL, with no application code involved.

Two consequences:

- Those foreign keys are `ON UPDATE CASCADE`, so changing a user's role rewrites the dependent rows and then trips the pinning CHECK. A role change is only safe for a user who owns nothing. This is why **#14 was going to refuse outright** rather than clean up.
- **A Seller physically cannot hold a bid row.** `bids.place()` therefore calls `require_role(session, "Buyer", ...)` at the top, and a Seller choosing "Place a bid" gets *"Only Buyers can place a bid"* rather than a self-bid message. That contradicts `buyer.py`'s docstring, which says Sellers and Admins get every Buyer action. **Known and deliberate** — removing the check would only convert a readable sentence into a psycopg IntegrityError. `SelfBid` is consequently unreachable through the interface.

### `auction.current_highest_bid` is denormalized

The same number lives on the auction row and as the largest `bid_amount` in the bid table. Fast to read, easy to get wrong.

Without a lock, two buyers bidding simultaneously both read the same stale high bid, both pass validation, both insert, and the second UPDATE overwrites the first — leaving an auction that claims one price with two bids at it and no way to say who is winning.

So `bids.place()` opens with `SELECT ... FOR UPDATE OF a`, validates **after** the lock, then inserts and updates inside the same transaction. `auctions.end()` does the same for the same reason: it reads the highest bidder and then writes a winner based on it, and a bid landing between those two steps would record the wrong person.

### Nothing auto-increments

Every primary key is a plain `INT`. We fixed that ourselves in `sql/extensions.sql` — one sequence per numeric-PK table, wired in as `DEFAULT nextval(...)`, which is what `SERIAL` does under the hood.

The alternative was `MAX(id) + 1` in the application, which has to run inside the same transaction as the insert it feeds and can still collide, so every insert would need retry logic. Sequences need neither.

**Every INSERT omits its id column and uses `RETURNING`.** The id is invented server-side, so `RETURNING` is the only way to learn it — and unlike a follow-up `SELECT MAX(...)`, it cannot pick up someone else's row. `users` has no sequence; its key is the login string.

This is also a documented schema extension: §2.3 permits it, §3 rewards it.

### Auctions have no start or end time

The only timestamp in the entire schema is `bid.bid_timestamp`. Nothing expires on its own. An auction closes when its seller closes it and never otherwise, which is why `auctions.end()` exists and why there is no scheduler anywhere.

Also: `auction.item_id`, `payment.auction_id` and `shipment.auction_id` are all `UNIQUE`. That is the schema enforcing "one auction per item" and "you cannot pay twice" without any application code — and it is why the won-but-unpaid anti-join was already fast before any index existed.

## 2. The two contracts

Settled 2026-08-21 and never revisited.

**Feature functions open their own connection and take a `Session`, not a `conn`.**

```python
def place(session, auction_id, amount):
    with get_connection() as conn:
        ...
```

Passing `conn` in would drag transaction management up into the menu layer. `with get_connection() as conn:` commits on clean exit and rolls back if an exception escapes, so **there is no `conn.commit()` anywhere in this project**. Every `raise` inside a `with` block therefore rolls back and releases its locks for free.

The acting user's login is never a parameter — it comes from `session.login`, so a caller cannot act as someone else. A *target* login, as on admin screens, still is one.

**Menu role files contain no control flow.** They export `TITLE` and `ACTIONS`, a list of `(key, label, function)` triples. `menus/__init__.py` owns the loop, the dispatch, and the single `except AppError` that protects every action.

The role files must never import `menus/__init__.py`. Imports run one direction only; reversing it hits a half-built module. This was caught during the first draft.

Adding a feature was always: write the function in its feature module, then replace the placeholder body in the role file. `menus/__init__.py` was never touched again after it was written.

## 3. Other decisions

- **Feature modules return data or raise. They never print.** Menus catch and render. `ui.py` is the only module that imports `rich`.
- **Application SQL is inline** in the feature modules, as parameterized strings. The "SQL lives in `.sql` files" rule applies to schema and datasets only — those have to survive losing the server instance.
- **One feature module per table**, named after it. `reports.py` is the single exception: its four queries each span three or four tables and belong to none of them, so putting them "where they belong" would have scattered them across `auctions.py` and `users.py`.
- **Vertical slices, not horizontal layers.** One issue = one feature, end to end.
- **Money is `Decimal`, never `float`.** `ui.prompt_decimal()` is the only place typed text becomes money.
- **Menus split by role**, so three people could have owned three files. That stopped mattering when the team became one person, but the split cost nothing.

### The dynamic WHERE in `auctions.search()`

The only query whose WHERE clause is assembled at runtime. Two lists grow side by side: `conditions` holds SQL fragments, each containing a `%s` placeholder; `params` holds the values. The fragments are joined with `" AND "` and interpolated; the values go to psycopg separately.

So the f-string interpolates **only strings the function wrote itself**. A search for `'; DROP TABLE users; --` produces byte-identical SQL to a search for `jacket` — only the parameter differs. Any filter added later must follow the same shape.

`TRUE` is used when every filter is skipped, so the query has one shape instead of two.

## 4. Physical design

The logical schema was given. Everything below it is ours.

**Two datasets, deliberately.** `seed.sql` is thirty rows — small enough to verify by eye, which is what makes it usable for building features and for the demo. `bulk_seed.sql` is 36,000 bids, and exists only because **you cannot measure an index on thirty rows**: Postgres sequential-scans everything at that size because reading the whole table genuinely is cheaper, so every number would be noise. `seed.sql` is never edited; the bulk file adds volume around the same predictable logins and the same seven auction states.

**The fact the whole index section rests on:** PostgreSQL creates an index automatically for `PRIMARY KEY` and `UNIQUE`, and **not** for a `FOREIGN KEY`. So `bid.auction_id` — the most heavily joined column in the application — had no index at all.

Eight indexes were built. Three mattered:

| Index | Query | Result |
|---|---|---|
| `bid (auction_id, bid_amount DESC)` | bid history | 3.39 ms → **0.14 ms**, 340 buffers → 13 |
| `auction (winner_login)` | the top-bidders correlated subquery | 39,188 buffers → 2,167 |
| `bid (buyer_login)` | the top-bidders join | killed the grouping sort entirely |

Top bidders overall: **238.0 ms → 33.1 ms**. Cost: 3 MB of indexes on a 4.5 MB dataset.

Two measured negatives, kept because deciding *not* to index is design too:

- **Search by item name did not improve and cannot.** `ILIKE '%term%'` has a leading wildcard, and a B-tree is sorted by the start of a string — there is nothing to seek on. The real fix is a trigram index, which needs `pg_trgm`, which we could not install on a shared course server.
- **The partial index on Active auctions was declined by the planner**, correctly. Browse wants two thirds of the table, and at that fraction a sequential scan wins.

PostgreSQL 10.23 constrained this: no `CREATE INDEX ... INCLUDE` (PG 11+), and no `CONCURRENTLY` because `load_db.py` wraps every file in one transaction.

## 5. What was cut, and why

The team went from three to one on 2026-08-25, two days before the demo. Feature depth was cut to protect the two graded slices that were still at zero — physical design and tuning, and documentation.

**Not built:** #6 profile, #8 create listing, #9 manage listings, #11 pay, #12 shipments, #13 list users, #14 role change, #15 remove item.

The reasoning: the client-application 10% was already earned by `ui.py`, the menu dispatch and the error vocabulary. Every additional feature would have earned fractions of the 30%, while #17 was a full 10% sitting untouched. Given three days and one person, tuning was worth more than four more menu screens.

Consequence worth being honest about: **a Seller cannot list an item through the application.** The demo runs entirely on seeded items.

## 6. Known limitations

- **Passwords are plain text.** The given schema stores them as `VARCHAR`, and every seeded account has to stay loginable — hashing would lock us out of all of them.
- **`SelfBid` is unreachable**, for the role-pinning reason in §1.
- **No automated tests.** Testing was manual throughout, against named rows in `seed.sql`.
- **Ctrl+D at a pagination prompt raises `EOFError`**, which `main.py` does not catch — it handles `KeyboardInterrupt` only. One line to fix; never got done.
