# Presentation plan

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

# Section 1 — Overview

No files, no code. Three things:

**What it is.** An online auction and bidding system. PostgreSQL back end, Python terminal client using Rich for a nice terminal UI, three roles — Buyer, Seller, Admin — each with its own menu. From these menus is where users make decisions that then call the funcitons living in the entity files that run the queries.

**Six tables:** `users`, `item`, `auction`, `bid`, `payment`, `shipment`.

---

# Section 2 — SQL and the four reports

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

# Section 3 — Physical design and tuning

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

`bid.auction_id` is the most heavily joined column in the application — every bid history, every report, every max-bid grouping goes through it. In the given schema it had no index at all. With 36,000 bids, all of those were full table scans.

#### Indexes

```sql
CREATE INDEX idx_bid_auction_amount ON bid (auction_id, bid_amount DESC);

CREATE INDEX idx_auction_winner     ON auction (winner_login);
CREATE INDEX idx_bid_buyer          ON bid (buyer_login);
```

The first is composite, and the column order is the point: sorted by auction first, then by amount within each auction — so `WHERE auction_id = ? ORDER BY bid_amount DESC` is one seek followed by a backwards read, with no sort step at all. Reversed, it would be useless.

#### Top bidders

Two separate wins, both from `idx_auction_winner` and `idx_bid_buyer`:

- The correlated subquery ran once per buyer — 404 full scans of `auction`. Buffers (8KB pages read from disk or cache) went **39,188 → 2,167**. 18x less data touched.
- The main join stopped sorting altogether. Postgres used to pull every bid into memory and sort it by buyer — a 3.7 MB sort. With `idx_bid_buyer`, the bids are already stored in buyer order, so it reads them in order and skips the sort entirely. The step is gone from the plan, not just faster.


#### Results

| Query | Before | After | |
|---|---|---|---|
| **Bid history** | 3.39 ms | **0.14 ms** | **24× faster** |
| **Top bidders report** | 238.0 ms | **33.1 ms** | **7.2× faster** |

---

# Section 4 — Live demo

**One unbroken session. Never restart the application.** Narrate each case *and its expected result* before running it — "now I'll bid one cent on an auction with no bids, and it should be refused, because…".

Load the demo dataset first. **Do not have the bulk data loaded**, or browse shows 4,500 auctions.

```bash
uv run scripts/load_db.py --yes
uv run main.py
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

Pick 2-3 of the nine test cases to demo and show, pick the best ones.