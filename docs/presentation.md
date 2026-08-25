# Presentation plan — Thursday 2026-08-27

## The TA's requirements

1. **No runtime errors, no leftover debug output.** Test on the same environment you present from.
2. **At least two test cases per implemented function** — normal and edge — **prepared in advance.**
3. **Actively introduce the project.** Someone who has never seen it should understand what it does by the end.
4. **~10 minutes**

## What each section is worth

- **30%** SQL queries and reports, plus core functionality
- **10%** physical database design and performance tuning
- **10%** client application development
- **10%** documentation quality — written, not presented

## Run of show

| | Section | Time | Marker |
|---|---|---|---|
| **1** | Overview | **1:00** | frames everything |
| **2** | SQL and the four reports | **2:30** | 30% — the queries half |
| **3** | Physical design and tuning | **2:30** | 10% tuning |
| **4** | Live demo | **4:00** | 30% functionality + 10% client app |


- **2:00** — must be finished with the overview
- **4:30** — must be finished with the reports
- **6:00** — must be starting the demo, whatever is left unsaid

If section 3 is running long, cut straight to the results table and move on. The numbers are the part that matters; the reasoning is in the report.

---

# Section 1 — Overview (1:00)

No files, no code. Three things:

**What it is.** An online auction and bidding system. PostgreSQL back end, Python terminal client using Rich for a nice terminal UI, three roles — Buyer, Seller, Admin — each with its own menu. From these menus is where users make decisions that then call the funcitons living in the entity files that run the queries.

**Six tables:** `users`, `item`, `auction`, `bid`, `payment`, `shipment`.

---

# Section 2 — SQL and the four reports (2:30)

Here we can explain the 4 reports that an admin has access to. This involves going over to `src/reports.py`. There are 4 functions, get familiar with them and the sql.  

We will only show running one on the terminal (not through the application). Lightly explain the query

Use the **demo dataset**, not the bulk one.

## Top bidders report — `LEFT JOIN` and a correlated subquery

A plain JOIN would drop any buyer who never bid. With LEFT JOIN we can also see who is not engaging.

Expected against the demo data:

```
buyer2   4 bids  4 auctions  $245.00  1 won
buyer1   4 bids  3 auctions  $210.00  1 won
buyer3   3 bids  3 auctions  $155.00  1 won
newbie1  0 bids  0 auctions      -    0 won   <-- the LEFT JOIN, visible
```

Point at `newbie1`. If asked why `COUNT(b.bid_id)` and not `COUNT(*)`: a LEFT JOIN with no match still produces one row of NULLs, so `COUNT(*)` would say 1. Counting the column skips NULLs and correctly says 0.

---

# Section 3 — Physical design and tuning (2:30)

### 1. Sequences — `sql/extensions.sql`

The instructor's schema declares every primary key as a plain `INT` with no auto-increment, so something has to invent the next id on every insert.

Two options: compute `MAX(id) + 1` in the application, or add sequences. `MAX(id) + 1` has to run inside the same transaction as the insert it feeds, and two transactions can still read the same maximum and collide — so every insert would need retry logic wrapped around it. A sequence hands out a guaranteed-unique number with no locking and no retries.

```sql
CREATE SEQUENCE bid_id_seq;
ALTER TABLE bid ALTER COLUMN bid_id SET DEFAULT nextval('bid_id_seq');
```

Every INSERT in the application omits its id column and uses `RETURNING` to find out which one it got.

**This is also a documented schema extension** — extra credit

### 2. Two datasets, and why

`seed.sql` is about thirty rows. `bulk_seed.sql` is 5,000 items, 4,500 auctions and **36,000 bids**.

The small dataset is for building and demonstrating; the large one exists for tuning and metrics

### 3. The indexes — `sql/indexes.sql`

`bid.auction_id` is the most heavily joined column in the application — every bid history, every report, every max-bid grouping goes through it — In the given schema it had no index at all. With 36,000 bids, all of those were full table scans.

**Bid history.** Before: `Seq Scan on bid`, *Rows Removed by Filter: 36,003*, 340 buffers. After: `Bitmap Index Scan`, 13 buffers.
> "It was reading all 36,000 bids and throwing away 36,003 of them to find 8."

**Top bidders.** Two separate wins, and the second is the better story:
- The correlated subquery ran once per buyer — 404 full scans of `auction`. Buffers went **39,188 → 2,167**.
- The main join lost its sort *entirely*: a `Hash Right Join` feeding a 3.7 MB quicksort became a `Merge Left Join` reading the index in order. **The sort did not get faster. It stopped existing.**

**Search by item name — the one that did not improve, and say so deliberately.**
> "This is `ILIKE '%Item 3%'`. A B-tree is sorted by the start of a string, and a leading wildcard does not know its own start — so there is nothing to seek on, and no index can help it. The real fix is a trigram index, which needs an extension we could not install on a shared course server. We measured it, we know why, and we documented it as a limitation."

Cost, if asked: **3 MB of indexes on a 4.5 MB dataset**, and every INSERT now maintains them.

Two more measured negatives, worth one line each if there is time — browse, where the planner **declined** the partial index because the query wants two thirds of the table and a sequential scan genuinely wins; and the active-auctions report, which needs every bid for every active auction so there is nothing to narrow.

### Indexes

Eight indexes were built. Show two-ish:

```sql
CREATE INDEX idx_bid_auction_amount ON bid (auction_id, bid_amount DESC);

CREATE INDEX idx_bid_buyer          ON bid (buyer_login);
CREATE INDEX idx_auction_winner     ON auction (winner_login);'Active';
```

The first is composite, and the column order is the point: sorted by auction first, then by amount within each auction — so `WHERE auction_id = ? ORDER BY bid_amount DESC` is one seek followed by a backwards read, with no sort step at all. Reversed, it would be useless.

The second performance gain comes from the two indexes `idx_bid_buyer` and `idx_auction_winner`. When an admin runs the top bidders report, both those indexes help in the performance gain.


#### Results

| Query | Before | After | |
|---|---|---|---|
| **Bid history** | 3.39 ms | **0.14 ms** | **24× faster** |
| **Top bidders report** | 238.0 ms | **33.1 ms** | **7.2× faster** |

---

# Section 4 — Live demo (4:00)

**One unbroken session. Never restart the application.** Narrate each case *and its expected result* before running it — "now I'll bid one cent on an auction with no bids, and it should be refused, because…" — so the audience knows what to watch for.

Load the demo dataset first. **Do not have the bulk data loaded**, or browse shows 4,500 auctions.

```bash
.venv/bin/python scripts/load_db.py --yes
.venv/bin/python main.py
```

## The nine test cases

| | As | Action | Expected | Shows |
|---|---|---|---|---|
| 1 | — | Register `demo1`, then try registering `buyer1` again | ✗ *"The username 'buyer1' is already taken."* | edge case, immediately |
| 2 | `buyer1` | Browse open auctions | 4 rows, paginated | pagination, the join to item |
| 3 | `buyer1` | Search `jacket`, then category `books` | 1 row each | the runtime-built WHERE |
| 4 | `buyer1` | View auction 1 in detail | detail + 3 bids underneath | three-table join |
| 5 | `buyer1` | **Bid $0.01 on auction 3** | ✗ *"must be greater than $120.00"* | **the moment — see below** |
| 6 | `buyer1` | Bid $125.00 on auction 3 | ✓ *"Bid #12 placed"* | `RETURNING` gives the real id |
| 7 | `seller2` | Try to place a bid | ✗ *"Only Buyers can place a bid."* | the role-pinning CHECK |
| 8 | `seller2` | Close auction 3 | ✓ *"buyer1 won at $125.00"* | the second transaction |
| 9 | `buyer1` | Your bids | auction 3 now reads **Won** | proves the write landed |

Two account switches only — `buyer1` → `seller2` → `buyer1`. Log out and back in rather than restarting.

### Case 5 is the one to slow down on

It looks like a trivial rejection and it is two rules at once:

> "Auction 3 has no bids, so its `current_highest_bid` is 0.00 — and one cent beats zero. It is refused because a bid has to clear **both** the current high bid **and** the item's starting price, and this item started at $120. If we had only compared against the current high bid, one cent would have won a first-edition book."

### Case 7 — say it accurately

`seller2` gets *"Only Buyers can place a bid"*, **not** a self-bid message. That is correct and worth explaining rather than glossing:

> "`bid.buyer_role` is CHECK-constrained to 'Buyer' with a foreign key to `users(login, role)`, so a bid row belonging to a Seller cannot physically exist. The application refuses it with a sentence instead of letting the database refuse it with a constraint violation."

### Case 9 is the payoff

The bid from case 6 and the close from case 8 come back together as a single word changing from **Leading** to **Won**. Point at it — it is the only moment where the audience sees a write they watched happen show up somewhere else.

### The client-application sentence

Say this once, during the demo, or the 10% for client application goes unclaimed:

> "Every refusal you are seeing is a typed exception, caught in one place in the menu loop. There is no try/except scattered through the features, and the application never shows a traceback."

Then name, in passing: pagination reused by every table, three role menus built from one shared list, `.env` configuration so every team member's port and database differ with zero code changes.

### If there is time left

Finish on the **admin reports through the application** — the same four queries from section 2, rendered as tables. It closes the loop between "here is the SQL" and "here is the product."

---

# Limitations to volunteer

Naming these first is stronger than being asked.

- **Passwords are stored in plain text.** The given schema stores them as `VARCHAR` and the seeded accounts have to stay loginable; hashing would lock us out of every one. Known limitation, documented.
- **Auctions have no end time.** Nothing expires on its own — the only timestamp in the schema is on `bid`.
- **`current_highest_bid` is denormalized.** We kept it because it is the given schema, and protected it with a row lock on every bid rather than dropping the column.
- **Some features were deliberately scoped out** — profile editing, listing management, admin role changes. Say why: the time went into physical database design instead, which is 10% of the grade on its own.

# Extra credit to claim

Both are already built and cost nothing to mention:

- **Schema extension** — five sequences added to a schema with no auto-increment (§2.3 permits, §3 rewards).
- **Friendlier interface** — pagination, right-aligned money columns, colour-coded statuses, and a symbol set that falls back automatically when the terminal cannot encode it.

# Pre-flight checklist — Wednesday

- [ ] `cs166_db_status`. **Postgres is a user process, not a service** — it dies on reboot and gets reaped. If it is down when you sit down, the demo is over. `cs166_db_start` is the fix.
- [ ] `/extra` is essentially full and `$PGDATA` lives there. Run a full `load_db.py` to confirm there is headroom.
- [ ] Reload the **demo** dataset. Confirm browse shows 4 auctions, not 4,500.
- [ ] Walk all nine cases against that dataset. Every expected result above should match exactly.
- [ ] Have `tuning_before.txt` and `tuning_after.txt` open in a tab. **Do not re-run the measurement live** — it means reloading 36,000 bids.
- [ ] Write the nine cases on paper. Auction ids and amounts, in order.
- [ ] Full rehearsal against a clock, checkpoints at 2:00 / 4:30 / 6:00.
