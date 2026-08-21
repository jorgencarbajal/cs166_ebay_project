# Issue drafts

Copy each block into a GitHub issue. Delete this file once the board is populated — GitHub is the source of truth after that.

**Labels to create first:** `foundation`, `sql`, `client`, `tuning`, `docs`, `buyer`, `seller`, `admin`, `blocker`

**Ordering:** #1 and #2 block everything else. Do not split up the feature work until both are merged.

---

## 1. Load the schema into each developer's database

**Labels:** `foundation`, `sql`, `blocker`

The instructor's schema is committed at `sql/schema.sql`, but nothing runs it yet. Each of us has our own Postgres instance on the school server, so each of us needs to be able to create the tables — and recreate them from scratch after we inevitably corrupt our data while testing.

Write `scripts/load_db.py`. It is run by hand, never imported, and it is the only place in the codebase allowed to do anything destructive. It gets its connection from `src/db.py` like everything else.

**Tasks**

- [ ] `scripts/load_db.py` reads `sql/schema.sql` and executes it against the database in `.env`
- [ ] Print a clear confirmation of which database was targeted before doing anything — `sql/schema.sql` opens with six `DROP TABLE ... CASCADE` statements and there must be no ambiguity about what is being destroyed
- [ ] Require an explicit confirmation prompt, or a `--yes` flag, before dropping
- [ ] Load the dataset from `data/` if one is present (see the open question below)
- [ ] Document the command in the README

**Notes**

- The schema file is read from disk and never embedded in a Python string. If the server instance is lost, `sql/schema.sql` is what rebuilds it.
- Run the whole file in one transaction so a syntax error partway through leaves nothing half-created.

**Open question:** whether the instructor is providing a dataset. Jorge is confirming. If we generate our own, that becomes its own issue — the tuning work needs enough rows for index effects to be measurable, so think tens of thousands of bids, not twenty.

**Done when:** any of us can run one command on the server and get a complete, empty (or seeded) database.

---

## 2. Shared foundation: session, errors, UI helpers, auth, and menu dispatch

**Labels:** `foundation`, `client`, `blocker`

Every feature imports this, so it lands before the three of us split up. It is one issue rather than six because the pieces only make sense together and the whole thing is a few hundred lines.

The architecture it establishes: **feature modules take a connection and arguments, return data or raise, and never print. Menu modules catch and render.** Keeping business logic free of `print` is what lets us restyle the entire interface in one place later, which is where the +10% usability extra credit lives.

### `src/errors.py`

One exception class per business rule the app enforces, all in one file so a menu can `except BidTooLow` without importing five modules. Each carries the data the menu needs to write a useful message.

- [ ] `AppError` — base class, everything else inherits from it
- [ ] `NotAuthorized` — role does not permit this action
- [ ] `BidTooLow(current_bid)` — carries the current high bid so the menu can say what to beat
- [ ] `SelfBid` — a seller bidding on their own auction
- [ ] `AuctionClosed`
- [ ] `AlreadyPaid`, `NotWinner`, `PaymentIncomplete` — payment and shipment guards
- [ ] `LoginTaken`, `BadCredentials`

Menus should be able to `except AppError` as a catch-all and show `str(e)`, so give each one a sensible message.

### `src/session.py`

Holds who is logged in for the life of the program. A small dataclass with `login` and `role` is enough — no global mutable state, pass the session object down into the menus.

- [ ] `Session` dataclass: `login: str`, `role: str`
- [ ] Helpers such as `require_role(session, "Admin")` that raise `NotAuthorized`, so permission checks are one line and consistent everywhere

Role checks belong here and in the feature modules — **not only in the menus**. Hiding a menu option is not access control.

### Primary keys — settled, no module needed

**Decided 2026-08-20: we use sequences.** `sql/extensions.sql` is written and committed. There is **no `src/ids.py`** — delete it if it is still lying around.

Nothing in the instructor's schema auto-increments, so the choice was `MAX(id) + 1` in the application versus adding our own sequences. `MAX(id) + 1` has to run inside the same transaction as the insert it feeds, two transactions can still read the same `MAX` and collide, and every insert would need retry logic wrapped around it. A sequence hands out a unique number with no locking and no retries.

`sql/extensions.sql` creates one sequence per numeric-PK table (`item`, `auction`, `bid`, `payment`, `shipment`) and wires each into its column as a `DEFAULT nextval(...)`, which is what `SERIAL` does under the hood. `users` needs none — its PK is the `login` string.

**What this means for every feature module:** omit the id column from the `INSERT` and use `RETURNING`.

```sql
INSERT INTO bid (auction_id, buyer_login, bid_amount) VALUES (%s, %s, %s) RETURNING bid_id
```

- [ ] Run `sql/extensions.sql` right after `sql/schema.sql` in `scripts/load_db.py` (issue #1)
- [ ] Every insert in `items.py`, `auctions.py`, `bids.py`, `payments.py`, `shipments.py` uses the `RETURNING` shape above
- [ ] `sql/seed.sql` (issue #1) must either omit the id columns too, or call `setval()` on each sequence at the end — otherwise the first row created through the app collides with seeded ids

§2.3 permits documented schema extensions and §3 offers extra credit for meaningful ones. The header comment in `sql/extensions.sql` is written to be lifted straight into the report.

### `src/ui.py`

All `rich` usage lives here. No other module imports `rich`.

- [ ] A single shared `Console`
- [ ] `success(msg)`, `error(msg)`, `warn(msg)`, `info(msg)`
- [ ] `table(rows, columns, title)` — takes the `dict_row` dicts that `db.py` already returns and renders a `rich.table.Table`
- [ ] `prompt(label)`, `prompt_int(label)`, `prompt_decimal(label)`, `prompt_password(label)`, `confirm(label)` — all re-prompting on invalid input rather than crashing
- [ ] `menu(title, options)` — prints a numbered list, returns the chosen key, rejects invalid choices

Money is `NUMERIC(10,2)` in the schema, so use `decimal.Decimal` and never `float`. Do the conversion here, once.

### `src/auth.py`

- [ ] `register(conn, login, password, phone_num, address, favorite_category=None)` — inserts into `users`, raises `LoginTaken` on conflict, returns a `Session`
- [ ] `login(conn, login, password)` — returns a `Session`, raises `BadCredentials`

Per §6.1 new accounts are always `Buyer`; the schema already defaults it. Do not accept a role parameter here — only an Admin can change a role, and that is a separate feature.

Passwords are stored as plain text to match the schema's `VARCHAR(100)`. Note that as a documented limitation in the report rather than quietly hashing, since the provided dataset (if any) will contain plain text.

### `src/menus/__init__.py`

- [ ] Opening menu: log in, register, quit
- [ ] After authentication, dispatch on `session.role` to `buyer.menu()`, `seller.menu()`, or `admin.menu()`
- [ ] A top-level `except AppError` so a business-rule violation prints a red line and returns to the menu instead of killing the program
- [ ] Wire `main.py` to call into here — it is still a stub `print`

Sellers and Admins can do everything a Buyer can (§6.1 lists the base actions for all users, with seller and admin privileges as *additional*). Structure the seller and admin menus to include the buyer options rather than duplicating that code.

**Done when:** a person can register, log in, land on a role-appropriate menu, and quit cleanly — with no features implemented behind any of the options yet.

---

## 3. Browse items

**Labels:** `client`, `sql`, `buyer`

List items available for auction. Available to every logged-in user (§6.1).

**Tasks**

- [ ] `auctions.browse(conn, limit, offset)` joining `item` and `auction`
- [ ] Show item name, category, starting price, current highest bid, status
- [ ] Paginate — the dataset may be large and a terminal cannot show 10,000 rows
- [ ] Render with `ui.table`

**Done when:** a buyer can page through listings and see current prices.

---

## 4. Search auctions

**Labels:** `client`, `sql`, `buyer`

Filtered search over auctions (§6.1).

**Tasks**

- [ ] `auctions.search(conn, name=None, category=None, max_price=None, status=None)`
- [ ] Case-insensitive partial match on `item_name` (`ILIKE`)
- [ ] Exact match on `category`, ceiling on `current_highest_bid`, filter on `auction_status`
- [ ] Build the WHERE clause from whichever filters were supplied — **parameterized**, never string-concatenated with user input
- [ ] Menu prompts for each filter, blank means "don't filter"

**Note:** this query is the headline candidate for the tuning issue (#17). Keep it clean and note which columns it filters on.

**Done when:** a buyer can find auctions by any combination of name, category, price, and status.

---

## 5. View auction status

**Labels:** `client`, `sql`, `buyer`

Full detail on a single auction (§6.1).

**Tasks**

- [ ] `auctions.detail(conn, auction_id)` returning item attributes, seller, current high bid, status, and winner if closed
- [ ] `bids.history(conn, auction_id)` returning that auction's bids newest first
- [ ] Menu shows the detail panel plus the bid history table
- [ ] Raise a clear error for an auction id that does not exist

**Done when:** a buyer can inspect one auction and see who has bid what.

---

## 6. View and edit profile

**Labels:** `client`, `sql`, `buyer`

§6.1: users may update profile fields **except `login` and `role`**.

**Tasks**

- [ ] `users.get_profile(conn, login)`
- [ ] `users.update_profile(conn, login, **fields)` accepting only `password`, `phone_num`, `address`, `favorite_category`
- [ ] Reject attempts to change `login` or `role` at the module level, not just by omitting them from the menu
- [ ] Edit menu leaves a field unchanged when the prompt is left blank

**Done when:** a user can view their profile and change any permitted field.

---

## 7. Place a bid

**Labels:** `client`, `sql`, `buyer`

The most constraint-heavy feature in the project, and the one most likely to be probed during the demo.

**Rules (§6.3, §6.4)**

- The bid must be strictly greater than `auction.current_highest_bid`
- A seller cannot bid on their own auction
- Only `Active` auctions accept bids
- The bid must also clear `item.starting_price` — a fresh auction has `current_highest_bid = 0`, so the check against the current high alone is not enough

**Tasks**

- [ ] `bids.place(conn, auction_id, buyer_login, amount)`
- [ ] Wrap the whole thing in **one transaction**: read the auction, validate, `INSERT INTO bid`, `UPDATE auction SET current_highest_bid`
- [ ] Lock the auction row with `SELECT ... FOR UPDATE` so two bids cannot both pass validation against a stale high bid
- [ ] Raise `BidTooLow(current)`, `SelfBid`, or `AuctionClosed` as appropriate
- [ ] Let the `bid_id_seq` sequence supply the id — omit `bid_id` from the `INSERT` and add `RETURNING bid_id` (see `sql/extensions.sql`)
- [ ] Menu shows the current high bid before prompting, and reports the new bid id on success

**Note:** `current_highest_bid` is denormalized — it duplicates information derivable from `bid`. Keeping the two consistent is the entire point of the transaction. Write a paragraph about this for the report; it is exactly the kind of tradeoff the documentation grade rewards.

**Done when:** valid bids are recorded and every rule above is enforced with a clear message.

---

## 8. Create a listing

**Labels:** `client`, `sql`, `seller`

Sellers list an item and open an auction on it (§6.2, §6.3).

**Tasks**

- [ ] `items.create(conn, seller_login, name, category, starting_price, description=None, condition=None, image_url=None)`
- [ ] `auctions.create(conn, item_id, seller_login)` — status defaults to `Active`, `current_highest_bid` starts at 0
- [ ] Do both in one transaction; an item with no auction is useless
- [ ] Generate both ids via `ids.next_id`
- [ ] Guard with `require_role(session, "Seller")` — the schema's `seller_role` foreign key will reject a Buyer, but the error message would be incomprehensible

**Note:** `auction.item_id` is `UNIQUE`, so an item can only ever be auctioned once.

**Done when:** a seller can list an item and it immediately appears in browse.

---

## 9. Manage own listings

**Labels:** `client`, `sql`, `seller`

§6.2: sellers can create **and update** their own items.

**Tasks**

- [ ] `items.list_by_seller(conn, seller_login)` with each item's auction status and current bid
- [ ] `items.update(conn, item_id, seller_login, **fields)` — verifies ownership and raises `NotAuthorized` otherwise
- [ ] Refuse to change `starting_price` once bids exist; moving the goalposts mid-auction is indefensible
- [ ] Menu lists the seller's items and lets them pick one to edit

**Done when:** a seller can review and edit their own listings, and cannot touch anyone else's.

---

## 10. End an auction

**Labels:** `client`, `sql`, `seller`

§6.3: the seller may end an auction at any time; the highest bidder wins; status becomes `Closed`.

**Tasks**

- [ ] `auctions.end(conn, auction_id, seller_login)`
- [ ] Verify ownership and that the auction is still `Active`
- [ ] Find the highest bid, set `winner_login`, set `auction_status = 'Closed'`
- [ ] Handle the no-bids case — close it with `winner_login` left NULL, which the schema allows
- [ ] One transaction, with the auction row locked
- [ ] Menu confirms before closing, since it is irreversible, and reports the winner

**Done when:** a seller can close an auction and the correct winner is recorded.

---

## 11. Pay for a won auction

**Labels:** `client`, `sql`, `buyer`

§6.5. Statuses are `Pending`, `Completed`, `Failed`.

**Tasks**

- [ ] `payments.create(conn, auction_id, buyer_login, amount)`
- [ ] Verify the auction is `Closed` and `winner_login` is this buyer — raise `NotWinner` otherwise
- [ ] `payment.auction_id` is `UNIQUE`, so raise `AlreadyPaid` on a second attempt
- [ ] `payments.list_for_buyer(conn, login)` so a buyer can see what they owe and what they have paid
- [ ] Amount should default to the winning bid rather than being freely typed

**Done when:** a winning buyer can pay exactly once, and cannot pay for auctions they did not win.

---

## 12. Create and update a shipment

**Labels:** `client`, `sql`, `seller`

§6.6. Statuses are `Pending`, `Shipped`, `Delivered`. Shipment represents "delivery after payment completion", so payment must be `Completed` first.

**Tasks**

- [ ] `shipments.create(conn, auction_id, address)` — raise `PaymentIncomplete` unless the payment exists and is `Completed`
- [ ] Default the address from the winning buyer's `users.address`, but allow an override
- [ ] `shipments.update_status(conn, shipment_id, status, tracking_number=None)`
- [ ] Only the seller of that auction may create or update it
- [ ] Buyers should be able to view shipment status for what they bought

**Done when:** a seller can ship a paid auction and both parties can see the status and tracking number.

---

## 13. Admin: manage users

**Labels:** `client`, `sql`, `admin`

§6.1: admins manage users.

**Tasks**

- [ ] `users.list_all(conn, role=None, search=None)` with pagination
- [ ] `users.detail(conn, login)` showing their items, bids, and payments
- [ ] Guard every function with `require_role(session, "Admin")`
- [ ] Never display password values in any listing

**Done when:** an admin can browse and search all users and inspect one in detail.

---

## 14. Admin: change a user's role

**Labels:** `client`, `sql`, `admin`

§6.1: **only** Admin can promote a user to Seller or Admin. This is the single trickiest interaction with the schema, so read this whole block before starting.

`users` carries `UNIQUE (login, role)` specifically so `item`, `auction`, `bid`, and `payment` can foreign-key to `(login, role)` and pin it with a CHECK — `item.seller_role` must equal `'Seller'`, `bid.buyer_role` must equal `'Buyer'`. Those foreign keys are `ON UPDATE CASCADE`.

The consequence: **demoting a Seller who owns items will cascade `seller_role` to the new value and violate that CHECK**, producing a confusing low-level error. Promoting a Buyer who has bids has the same problem in reverse.

**Tasks**

- [ ] `users.change_role(conn, target_login, new_role)`
- [ ] Before updating, check whether the user has rows that depend on their current role, and raise a clear application-level error explaining why the change is refused
- [ ] Decide and document the policy: refuse outright, or allow only when no dependent rows exist. Refusing is defensible and far simpler
- [ ] Prevent an admin from demoting themselves and locking everyone out
- [ ] Write this up for the report — it is a genuine schema-level limitation and §2.2 asks for exactly this kind of documented constraint

**Done when:** an admin can change roles where it is safe, and gets an explanation rather than a stack trace where it is not.

---

## 15. Admin: manage and remove items

**Labels:** `client`, `sql`, `admin`

§6.2: admins can manage or remove items when needed.

**Tasks**

- [ ] `items.admin_update(conn, item_id, **fields)` — no ownership restriction
- [ ] `items.admin_delete(conn, item_id)`
- [ ] `item` is referenced by `auction` with `ON DELETE RESTRICT`, so a plain delete fails whenever an auction exists. Decide the policy: refuse while an auction exists, or cascade through auction → bids explicitly
- [ ] Confirm destructive actions in the menu

**Done when:** an admin can correct or remove listings, with the delete rules clearly enforced and explained.

---

## 16. Admin: monitor auctions

**Labels:** `client`, `sql`, `admin`

§6.1: admins monitor auctions. This is also where the "reports" half of the 30% SQL grade lives, so make the queries genuinely analytical rather than plain selects.

**Tasks**

- [ ] All active auctions ordered by current highest bid
- [ ] Auctions closed with no winner
- [ ] Auctions won but not yet paid, and paid but not yet shipped
- [ ] Top bidders by number of bids and by total value
- [ ] Most active categories
- [ ] Revenue by category or by seller

**Note:** use `GROUP BY`, `HAVING`, joins, and aggregates. A grader looking for "SQL queries/reports" is looking here.

**Done when:** an admin has a reports submenu covering all of the above.

---

## 17. Physical database design and tuning

**Labels:** `tuning`, `sql`

Worth 10% of the project grade on its own. Do this **after** the features work, because you need real queries to tune and real data to measure.

**Tasks**

- [ ] Collect the actual queries the app runs and identify the hot ones — search (#4), browse (#3), bid history (#5), the admin reports (#16)
- [ ] Record a baseline with `EXPLAIN ANALYZE` on each, before any indexes
- [ ] Write `sql/indexes.sql` with justified indexes — likely candidates: `item(category)`, `item(item_name)` for `ILIKE`, `bid(auction_id, bid_amount DESC)`, `auction(auction_status)`, `auction(seller_login)`
- [ ] Re-measure after each index and record the numbers
- [ ] Run `ANALYZE` so the planner has fresh statistics before measuring
- [ ] Write up what worked, what did not, and why — including indexes that made no difference, which is a real finding

**Postgres 10 constraints — read before writing any index:**

- No covering indexes: `CREATE INDEX ... INCLUDE (...)` is PG 11+ and will error
- No `CALL` or stored procedures; functions only
- None of the PG 11+ planner improvements
- Check syntax against the **PostgreSQL 10** docs; modern tutorials will hand you syntax that fails here

**Note:** indexes only demonstrably help on enough rows. If the provided dataset is small, generating additional data is worth doing — §2.3 permits dataset modification when documented.

**Done when:** `sql/indexes.sql` is committed and the report contains before/after timings with an explanation of each index.

---

## 18. Input validation and error handling

**Labels:** `client`

§3 offers extra credit for robust error handling, and this is what separates a demo that survives a grader poking at it from one that does not.

**Tasks**

- [ ] No unhandled traceback should ever reach the user — the top-level loop catches `AppError` and prints it, and catches everything else with an apology plus a return to the menu
- [ ] Every numeric prompt re-prompts on garbage input instead of crashing
- [ ] Money handled as `Decimal` throughout, never `float`
- [ ] Empty required fields rejected before hitting the database
- [ ] Field lengths validated against the schema — `login` is `VARCHAR(50)`, `address` is `VARCHAR(255)`, and a database-level truncation error is not a good user experience
- [ ] Ctrl+C exits cleanly rather than dumping a `KeyboardInterrupt`
- [ ] A dead database connection produces "is your Postgres running?" rather than a psycopg traceback

**Done when:** a deliberately hostile user cannot crash the client.

---

## 19. Final report and documentation

**Labels:** `docs`

Worth 10%. Start it early — everyone who leaves it to the last day loses points on it.

**Tasks**

- [ ] Description of the implementation and architecture
- [ ] Physical design section: indexes chosen, with before/after measurements from #17
- [ ] Documented assumptions and limitations — plain-text passwords, the role-change constraint from #14, the sequences we added in `sql/extensions.sql` as a documented schema extension, no auction end times in the schema
- [ ] Any dataset modifications, which §2.3 requires be reported
- [ ] **Per-member task and contribution breakdown — §4 requires this explicitly**
- [ ] Screenshots of the client in action

**Note:** the contribution breakdown is far easier if every issue has an assignee and every PR says `Closes #N`. That history is the report section.

**Done when:** the report is complete and submitted with the source.

---

## 20. Demo preparation

**Labels:** `docs`

§2.3: demo slots are first-come, first-served.

**Tasks**

- [ ] Claim a slot as soon as they are released
- [ ] Write a demo script walking one item end to end: register → list → bid → close → pay → ship
- [ ] Seed a small, known demo dataset so the walkthrough is reproducible and does not depend on whatever junk is in the database
- [ ] Rehearse on the server exactly as it will be run, including starting the Postgres instance first
- [ ] Have answers ready for the obvious questions: why these indexes, how concurrent bids are handled, what the role constraint means

**Done when:** the walkthrough runs start to finish without improvisation.
