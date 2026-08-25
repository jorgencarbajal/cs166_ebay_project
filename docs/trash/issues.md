ISSUE STATUS -- CS166 PHASE 3
FINAL, as of 2026-08-25


This file was originally the task breakdown, written as plain text so each block could be
pasted straight into a GitHub issue. It is now a record of what was built and what was not.

Deliberately still plain text. No headers, no backticks, no bold, no tables. Do not add
formatting to it.


:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

WHERE THINGS ENDED UP

Ten issues done, eight not built, one partial, one outstanding, one replaced by a document.

The team was three people until 2026-08-25, when it became one, two days before the demo.
Everything in the NOT BUILT list below was cut on that day. The reasoning is in the
SCOPE section at the bottom, and it was a deliberate trade rather than a shortfall.


DONE

  1   Load the schema into each developer's database
  2   Shared foundation -- errors, ui, auth, session, menu dispatch
  3   Browse auctions
  4   Search auctions
  5   View one auction in detail, with bid history
  7   Place a bid
  10  End an auction
  16  Admin reports, all four
  17  Physical database design and tuning
  21  Bulk dataset for the tuning measurements


NOT BUILT -- cut 2026-08-25

  6   View and edit your profile
  8   Create a listing and start an auction
  9   Manage your own listings
  11  Pay for a won auction
  12  Shipments
  13  Admin -- list and view users
  14  Admin -- change a user's role
  15  Admin -- manage and remove items

  Each of these still has a menu entry that names its issue number rather than pretending
  to work. src/users.py, src/items.py, src/payments.py and src/shipments.py are still
  module docstrings with no functions in them.


PARTIAL

  18  Input validation and error handling

  Most of the checklist was satisfied as the code was written rather than as a pass at the
  end. What exists: the single except AppError in menus/__init__.py, the OperationalError
  and KeyboardInterrupt handlers in main.py, prompts that re-ask on garbage input,
  max_length on the prompts that feed VARCHAR columns, Decimal everywhere and no float.

  What was never done: the deliberate hostile-user sweep. One known gap -- Ctrl+D at a
  pagination prompt raises EOFError, which main.py does not catch. One line to fix.


OUTSTANDING

  19  Final report and documentation

  The only graded item still at zero. 10% of Phase 3. Everything it needs already exists
  in note form -- docs/trash/architecture.md has the design rationale and the limitations,
  docs/presentation.md has the tuning numbers and the test cases, and this file has the
  scope decisions.


REPLACED BY A DOCUMENT

  20  Demo preparation

  Became docs/presentation.md -- run of show, the nine test cases with expected results,
  the tuning numbers, the limitations to volunteer, and a pre-flight checklist.


:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

WHAT EACH FINISHED ISSUE ACTUALLY PRODUCED


1 -- LOAD THE SCHEMA

scripts/load_db.py. Runs the .sql files in one transaction, skipping empty ones. Flags:
--yes, --dry-run, --bulk, --skip-indexes. The last two were added for issue #17 -- --bulk
inserts bulk_seed.sql after seed.sql and before indexes.sql, and --skip-indexes omits the
index file so the "before" half of a measurement can be taken.

This is the only destructive file in the project. schema.sql opens with six
DROP TABLE ... CASCADE.


2 -- SHARED FOUNDATION

src/db.py, src/errors.py, src/ui.py, src/auth.py, src/menus/__init__.py and the three role
menu files. 15 exception classes, all inheriting AppError. One try/except protects every
action in the whole application.


3 -- BROWSE AUCTIONS

auctions.browse() plus browse_auctions() in menus/buyer.py. Written first and deliberately
over-commented as the reference slice -- the pattern every other feature copied.


4 -- SEARCH AUCTIONS

auctions.search(). The only query with a WHERE clause assembled at runtime. Filters on
name (ILIKE substring), category (ILIKE exact), a starting-price range, and status.
Active-only by default.

The safety detail: SQL fragments containing %s go in one list, values go in another, and
the f-string only ever interpolates strings the function wrote itself. Verified locally
against a "'; DROP TABLE users; --" input -- the SQL text was byte-identical.


5 -- VIEW ONE AUCTION IN DETAIL

auctions.detail() and bids.history(). detail() is the one deliberately wide query in the
project, because a single record printed down the screen can afford columns a table
cannot. bid_count is a scalar subquery rather than a JOIN with GROUP BY, so counting the
bids does not multiply the auction row.


7 -- PLACE A BID

bids.place() and bids.list_for_buyer(). The hardest thing in the project and the only
row-locking transaction until #10.

Five checks in order: require_role Buyer, then NotFound, then AuctionClosed, then SelfBid,
then BidTooLow. The rule that matters -- a bid must beat max(current_highest_bid,
starting_price), not either one alone. Auction 3 in seed.sql has no bids and a $120
starting price, so a $0.01 bid must be refused. If it is accepted, the second half of the
rule is missing.

SELECT ... FOR UPDATE OF a, not bare FOR UPDATE. The query joins item, and a bare lock
would hold the item row too.

Validation happens after the lock, deliberately. Checking before it validates a stale
number, which is the exact bug the lock exists to prevent.

list_for_buyer() derives Won / Lost / Leading / Outbid in SQL with a CASE, because the
label comes entirely from columns the query already fetched.


10 -- END AN AUCTION

auctions.end(). The second transaction, built the same way as place(). A seller or any
Admin may close. An auction nobody bid on closes with winner_login NULL and the item stays
the seller's.

The trap worth remembering: winner_role must be set to NULL in the same UPDATE. It has
DEFAULT 'Buyer', but column defaults apply only to INSERT -- an UPDATE that ignores the
column leaves the old value and produces a row claiming a Buyer role for a winner who does
not exist.


16 -- ADMIN REPORTS

src/reports.py -- a new module, because these four queries each span three or four tables
and belong to none of them. Four reports: top bidders, revenue by category, won but
unpaid, active auctions by high bid.

Techniques spread across them deliberately -- LEFT JOIN, GROUP BY, HAVING, a correlated
subquery, an anti-join, and COUNT against COUNT(DISTINCT).

Two rows in the demo data are worth pointing at. newbie1 appears with zero bids, which is
the LEFT JOIN visible. Auction 1 shows three bids from two bidders, which is the whole
justification for COUNT(DISTINCT).


17 -- PHYSICAL DATABASE DESIGN AND TUNING

sql/indexes.sql -- eight indexes. sql/tuning_queries.sql -- nine EXPLAIN (ANALYZE,
BUFFERS) statements, run twice, before and after.

The fact the section rests on: PostgreSQL indexes PRIMARY KEY and UNIQUE automatically and
does NOT index a FOREIGN KEY. bid.auction_id, the most joined column in the application,
had no index at all.

Results:

  bid history        3.39 ms -> 0.14 ms      24x    340 buffers -> 13
  top bidders      238.0 ms  -> 33.1 ms       7.2x  39,188 buffers -> 2,167 in the subquery
  search by name     3.96 ms ->  4.02 ms      none, and cannot improve

The third is in the set on purpose. ILIKE '%term%' has a leading wildcard and a B-tree is
sorted by the start of a string, so no index can serve it. The real fix is a trigram
index, which needs an extension we could not install on a shared server.

Also measured and declined: the partial index on Active auctions. The planner chose a
sequential scan, correctly, because browse wants two thirds of the table.

Cost: 3 MB of indexes on a 4.5 MB dataset.

PostgreSQL 10.23 constraints -- no CREATE INDEX ... INCLUDE, and no CONCURRENTLY, because
load_db.py wraps every file in a single transaction.


21 -- BULK DATASET

sql/bulk_seed.sql. 440 users, 5,000 items, ~4,500 auctions, ~36,000 bids, built with
generate_series() and CROSS JOIN LATERAL so the bid count varies per auction.

seed.sql was never edited. Every statement in the bulk file is guarded by
LIKE 'bulkseller%' or LIKE 'bulkbuyer%', so it provably cannot touch a demo row.

Two invariants preserved deliberately: every generated bid clears its item's
starting_price, and amount and time increase together so newest is always highest.

setseed() fixes the randomness, so the dataset is reproducible. ANALYZE runs last, and it
is not optional -- without it the planner still believes the tables hold thirty rows.


:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

SCOPE -- WHY EIGHT FEATURES WERE CUT

Decided 2026-08-25, with three days left and one person.

Phase 3 is 60% of the project grade, split four ways:

  30%   SQL queries and reports, plus core functionality
  10%   physical database design and performance tuning
  10%   client application development
  10%   documentation quality

The client-application 10% was already earned -- ui.py, the menu dispatch, the error
vocabulary, pagination and the prompts were all finished and working. Every additional
feature written from that point would have earned fractions of the 30%, while #17 was a
full 10% sitting at zero and #19 still is.

So the trade was: eight menu screens, or the entire physical-design section plus a written
report. Tuning won.

The honest consequence, and it should be said out loud rather than hidden -- a Seller
cannot list an item through the application. The demo runs on seeded items only.


:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

TESTING

There is no automated test suite and no test runner. Testing was manual throughout, run
against named rows in seed.sql.

The nine demo cases and their expected results are in docs/presentation.md. The one that
matters most is case 5 -- $0.01 on auction 3 must be refused.

Reload the demo dataset before testing:

  .venv/bin/python scripts/load_db.py --yes

Note that the bid ids move if you run the demo twice without reloading. Case 6 expects
"Bid #12", which is only true on a fresh load.


:::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

BRANCHES

  main           canonical, fully commented, the version to hand in
  comment_free   comments stripped, docstrings cut to summary plus returns
  ui_change      NOT MERGED -- right-aligned numbers, colour-coded statuses, a
                 "logged in as" subtitle, and a rich markup escape fix

ui_change is worth merging. The escape fix is a genuine bug -- without it an item name
containing square brackets has part of it eaten as a style tag.

If both branches are merged, ui.py will conflict. Take the ui_change version and re-run
the comment strip on it rather than resolving by hand.
