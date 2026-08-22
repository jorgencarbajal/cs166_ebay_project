ISSUE DRAFTS -- CS166 PHASE 3
=============================

Each block below is one GitHub issue. Copy the block, paste it into a new issue, set the
labels and the assignee. This file is the working list until the board is populated.

Labels to create first:
  foundation / sql / client / tuning / docs / buyer / seller / admin / blocker

Last updated 2026-08-22, after issue #3 was finished.


::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

READ THIS FIRST -- THE RULES EVERY ISSUE FOLLOWS
================================================

Paste this as its own issue and pin it. Everything below assumes you have read it.
Nothing here is up for debate -- it was all settled on 2026-08-20 and 2026-08-21 and the
existing code already works this way. If you break one of these rules your code will
either crash or quietly corrupt data.


RULE 1 -- A FEATURE FUNCTION OPENS ITS OWN CONNECTION AND TAKES A SESSION
-------------------------------------------------------------------------

Every function you write in a feature module looks like this:

    from .db import get_connection

    def place(session, auction_id, amount):
        with get_connection() as conn:
            rows = conn.execute("SELECT ...", (auction_id,)).fetchall()
        return rows

- get_connection() comes from src/db.py. That is the only way to reach the database.
- The menu does NOT open a connection and pass it in. If it did, transaction management
  would leak up into the interface layer and every menu function would have to get it
  right.
- "with get_connection() as conn:" commits by itself when the block exits cleanly, and
  rolls back by itself if an exception escapes the block. THERE IS NO conn.commit()
  ANYWHERE IN THIS PROJECT. Do not add one.
- The first parameter is always the Session object, never a login string. The acting
  user's login is read off it as session.login. That is what stops someone acting as
  another user by passing a different name.
- A TARGET login is still a normal parameter -- for example
  users.change_role(session, target_login, new_role) on the admin screens. The rule is
  only about who is DOING the action.


RULE 2 -- FEATURE MODULES RETURN DATA OR RAISE. THEY NEVER PRINT.
------------------------------------------------------------------

- A feature module never calls print(), never imports rich, and never imports src/ui.py.
  It does not know a terminal exists.
- It returns plain Python -- a list of dicts, a single dict, an int -- or it raises one
  of the exceptions in src/errors.py.
- The menu layer is what turns that into something on screen.
- Reason: the whole interface can be restyled in one file, which is where the +10%
  usability extra credit lives.


RULE 3 -- MENU ROLE FILES CONTAIN NO CONTROL FLOW
--------------------------------------------------

src/menus/buyer.py, src/menus/seller.py and src/menus/admin.py each export exactly two
names:

  - TITLE -- a string, the heading.
  - ACTIONS -- a list of (key, label, function) triples.

That is all. No while loops. No try/except. No SQL.

src/menus/__init__.py owns the loop, the dispatch, and the ONE try/except AppError that
protects every action in the whole application. So when you write a menu action:

  - Do NOT wrap it in try/except. run_role_menu() already did that for you.
  - Do NOT loop. The loop is above you.
  - Just call the feature function and hand the result to ui.

seller.py starts with ACTIONS = list(buyer.ACTIONS) and appends. admin.py starts with
ACTIONS = list(seller.ACTIONS) and appends. The list() is a COPY, not an alias -- without
it the += would append to buyer.ACTIONS itself and the Buyer menu would sprout Seller
options.

THE ROLE FILES MUST NEVER IMPORT src/menus/__init__.py. Imports run one direction only.
Reversing it hits a half-built module and fails at startup. This already bit us once.


RULE 4 -- HOW YOU ADD A FEATURE, START TO FINISH
-------------------------------------------------

Two steps, and menus/__init__.py is never touched:

  1 / Write the function in its feature module (src/items.py, src/bids.py, and so on).
  2 / Open your role file and replace the placeholder body with a real one.

Every placeholder today calls buyer._not_built_yet("Some feature", N) where N is the
issue number. Delete that call when you write the real body. The entry in ACTIONS
already exists and does not need to change.

Look at src/auctions.py browse() and src/menus/buyer.py browse_auctions() before you
start. That pair is the REFERENCE SLICE -- issue #3, the first feature written,
deliberately over-commented so it can be copied. Copy its shape.


RULE 5 -- SQL
--------------

- Application SQL is written INLINE in the feature module as a parameterized string.
  It does not go in a .sql file. The "SQL lives in .sql files" rule covers schema and
  dataset only, because those have to survive losing the server instance.
- ALWAYS parameterize. Pass values as psycopg's second argument:

      conn.execute("SELECT * FROM item WHERE category = %s", (category,))

  NEVER build SQL with an f-string or + concatenation around user input. That is a SQL
  injection hole and it will cost marks.
- Rows come back as DICTS, not tuples, because src/db.py sets dict_row as the row
  factory. So you write row["item_name"], not row[1].
- Use .fetchall() for many rows, .fetchone() for one. .fetchone() returns None when
  nothing matched -- check for that and raise NotFound.
- NOTHING AUTO-INCREMENTS in the instructor's schema, but we fixed that ourselves in
  sql/extensions.sql by adding one sequence per numeric-PK table and wiring it in as the
  column DEFAULT. So in practice ids now generate themselves. What that means for you:
  EVERY INSERT OMITS THE ID COLUMN AND USES RETURNING.

      INSERT INTO bid (auction_id, buyer_login, bid_amount)
      VALUES (%s, %s, %s)
      RETURNING bid_id

  The users table has no sequence -- its primary key is the login string.
- Money is NUMERIC(10,2) in the schema. In Python that is decimal.Decimal, NEVER float.
  ui.prompt_decimal() already hands you a Decimal.


RULE 6 -- ERRORS
-----------------

src/errors.py already has 15 exception classes and they all inherit from AppError. Raise
one of those; do not invent new ones without asking, and do not let a raw psycopg error
reach the user.

The pattern is: catch the low-level psycopg exception, raise ours instead. A
UniqueViolation about constraint users_pkey becomes LoginTaken("jorge").

Available classes and what they take:

  - AppError                                        base class, catch-all
  - LoginTaken(login)
  - BadCredentials()                                deliberately vague, so it does not
                                                    leak which logins exist
  - NotAuthorized(action, required_role=None)       with a role it reads as a role
                                                    problem, without one as an ownership
                                                    problem
  - NotFound(what, key)                             e.g. NotFound("Auction", 42)
  - BidTooLow(amount, minimum)
  - SelfBid()
  - AuctionClosed(auction_id)
  - AuctionHasBids(item_id)
  - NotWinner(auction_id)
  - AlreadyPaid(auction_id)
  - PaymentIncomplete(auction_id, status=None)
  - RoleChangeBlocked(login, current_role, new_role, reason)
  - ItemInUse(item_id, auction_id)

Each one stores its data as attributes AND builds a finished sentence, so str(e) is
always safe to print. The menu layer already does that for you.

Genuine bugs -- a KeyError, a typo in your SQL -- deliberately do NOT inherit from
AppError, so they sail past every handler and give you a real traceback. That is on
purpose while we are still building.

For permission checks use require_role() from src/auth.py:

    from .auth import require_role
    require_role(session, "Seller", "create a listing")

It raises NotAuthorized when the role does not match. Put it at the TOP of the feature
function. Hiding a menu option is NOT access control -- the check belongs in the feature
module, not only in the menu.


RULE 7 -- THE UI HELPERS YOU ARE ALLOWED TO USE
------------------------------------------------

All of these live in src/ui.py. Import it in your MENU file only, never in a feature
module:

    from .. import ui

Messages:
  - ui.success(message)      green, with a tick
  - ui.error(message)        red
  - ui.warn(message)         yellow
  - ui.info(message)         plain
  - ui.blank()               one blank line
  - ui.heading(text)         a section heading

Tables:
  - ui.table(rows, columns, title=None)
  - ui.page(rows, columns, title=None, page_size=10)

  rows is the list of dicts your feature function returned. columns is a list where each
  entry is either a bare key string, or a (key, "Header") pair when you want to override
  the automatic header. Automatic headers turn item_name into "Item Name".

  Use ui.page() for anything that could be long -- it prints one screenful and handles
  next / back / quit itself. Use ui.table() only for something guaranteed short, like a
  single auction's detail.

  Both print "Nothing to show." for an empty list, so you do NOT need to special-case it.

Input, all of which re-prompt on bad input instead of crashing:
  - ui.prompt(label, default=None, required=True, max_length=None)     returns str
  - ui.prompt_int(label, default=None, minimum=None, maximum=None)     returns int
  - ui.prompt_decimal(label, default=None, minimum=None)               returns Decimal
  - ui.prompt_password(label="Password")                               masked
  - ui.confirm(label, default=False)                                   returns bool
  - ui.menu(title, options)   options is a list of (key, label) pairs, returns the key

Pass max_length to ui.prompt() to match the schema, so the user gets a clean re-prompt
instead of a database truncation error. The column widths are: login 50, password 100,
phone_num 20, address 255, role 10, favorite_category 50, item_name 100, category 50,
image_url 255, item_condition 50, auction_status 20, payment_status 20,
shipment_status 20, tracking_number 100. description is TEXT, so it is unlimited.

Watch out: rich treats square brackets as markup. A literal bracket has to be escaped as
\[n]ext. This has already bitten once.


RULE 8 -- THE SEED DATA YOU ARE WRITING AGAINST
------------------------------------------------

sql/seed.sql is loaded by scripts/load_db.py and it was built on purpose so that every
feature has rows in every state it needs on the day it is written. YOU ARE NOT BLOCKED
ON ANYONE ELSE'S ISSUE. Read this section before you say you cannot test something.

Logins, all with the password pass123:
  - admin1                Admin
  - seller1, seller2      Sellers, both own items
  - buyer1, buyer2, buyer3  Buyers, all three have placed bids
  - newbie1               Buyer with NO items and NO bids. The only account that can be
                          promoted to Seller (see issue #14). buyer3 has a NULL
                          favorite_category, so screens have a real NULL to render.

Items: 9 of them across 6 categories. ITEMS 7 AND 8 HAVE NO AUCTION -- that is
deliberate, so there is something to put up for auction in issue #8.

Auctions:
  - 1   Active, has bids                          the ordinary case
  - 2   Active, has bids                          a second ordinary case
  - 3   Active, NO BIDS AT ALL, high bid is 0.00  forces bidding to fall back to the
                                                  item's starting_price
  - 4   Closed, won by buyer2, paid, Delivered    the complete happy path
  - 5   Closed, won by buyer1, NEVER PAID         what the unpaid report looks for, and
                                                  what issue #11 pays off
  - 6   Active, has bids                          gives browse enough rows to paginate
  - 7   Closed, won by buyer3, paid, shipment
        still Pending, tracking_number NULL       what issue #12 marks as Shipped

Bids: 11 of them. Every one clears its item's starting_price, and every auction's
highest bid matches the current_highest_bid recorded on the auction row.

Payments: 2, both Completed -- auction 4 and auction 7.

Shipments: 2 -- auction 4 is Delivered with a tracking number, auction 7 is Pending with
none.

Running scripts/load_db.py WIPES the database and rebuilds it from this. Run it once,
not every session. Data you create through the running app persists between sessions.


RULE 9 -- FOUR SCHEMA FACTS THAT DRIVE MOST OF THE DESIGN
----------------------------------------------------------

Read sql/schema.sql. It is 106 lines and it is the instructor's, verbatim -- we never
edit it. Four things about it are not obvious:

  1 / UNIQUE (login, role) on users is LOAD-BEARING. It exists so the child tables can
      foreign-key to the PAIR (login, role) and then pin the role with a CHECK --
      item.seller_role must equal 'Seller', bid.buyer_role must equal 'Buyer'. That is
      how role-based integrity is enforced in pure SQL with no triggers.

      The consequence: those foreign keys are ON UPDATE CASCADE. So changing a user's
      role cascades into every dependent row and lands them on the wrong side of their
      pinning CHECK. This is the whole subject of issue #14.

  2 / auction.current_highest_bid IS DENORMALIZED. It duplicates information you could
      derive from the bid table. Placing a bid therefore has to INSERT and UPDATE in one
      transaction with SELECT ... FOR UPDATE on the auction row, or the two drift apart.
      That is issue #7.

  3 / NOTHING AUTO-INCREMENTS in the original schema -- see RULE 5. We added sequences in
      sql/extensions.sql. Omit the id, use RETURNING.

  4 / AUCTIONS HAVE NO START OR END TIME. The only timestamp in the entire schema is
      bid.bid_timestamp. An auction closes when its seller closes it, and never
      otherwise. Do not write code that looks for an end date -- there isn't one.

Also worth knowing:
  - auction.item_id, payment.auction_id and shipment.auction_id are all UNIQUE. So an
    item can only ever be auctioned once, an auction can only ever be paid once, and an
    auction can only ever have one shipment. Those UNIQUE constraints are what enforce
    "cannot pay twice" for free.
  - item is referenced by auction with ON DELETE RESTRICT, so deleting an item that has
    an auction fails at the database level. Issue #15 turns that into a clean message.
  - Passwords are PLAIN TEXT. That matches the schema and it matches seed.sql. Do not
    "fix" it by hashing -- that would lock us out of every seeded account. It is written
    up as a documented limitation in the report instead.


RULE 10 -- GIT
---------------

- Branch per issue. Do not push to main. Jorge was committing straight to main while
  building the baseline alone; now that there are three of us that stops.
- Branch naming: issue-7-place-bid, issue-13-list-users, and so on.
- Squash your wip commits with git rebase -i before opening the PR.
- EVERY PR BODY MUST SAY "Closes #N". Section 4 of the spec requires the final report to
  document each member's individual contributions, and that git history is what writes
  that section for us. This is not bureaucracy, it is 10% of the grade.
- Code moves by git only. Commit and push from your laptop, git pull on the server, run
  it there. Never copy-paste a file onto the server -- pasted files diverge from what is
  committed and you will lose an evening to it.


RULE 11 -- HOW TO ACTUALLY RUN AND TEST IT
-------------------------------------------

Everything runs on the UCR CS server. There is no local Postgres and no SSH tunnel.

  ssh <your-netid>@cs166.cs.ucr.edu
  cs166_db_status            is your Postgres running?
  cs166_db_start             start it if it is not
  cd ~/cs166_ebay_project
  git pull
  uv run main.py             the application

Your instance is a USER PROCESS, not a service. It dies on reboot and gets reaped.
Checking cs166_db_status is the FIRST step for any connection failure.

There is no automated test suite. You test by running the application and working through
the cases yourself. Every issue below has a TESTING AGAINST SEED DATA section listing the
exact rows that exercise it -- which auction has no bids, which one was won and never
paid, which items have no auction. Work through that list before you open your PR, and
say in the PR which cases you checked.

Connection failure triage, in order:
  - "connection refused" or "server closed the connection unexpectedly"
        -> Postgres is down. Run cs166_db_start.
  - "connection timeout expired"
        -> your .env points somewhere unreachable. Almost always a leftover remote host
           or port where localhost belongs.
  - "database does not exist" or "password authentication failed"
        -> good news. Postgres answered, only your .env values are wrong.

Plain psql will NOT work -- it looks for a socket in /var/run/postgresql. Use the
cs166_psql wrapper, which passes the real socket path.

The server runs PostgreSQL 10.23, from 2017. Check any SQL syntax you find online against
the PostgreSQL 10 docs. Modern tutorials will hand you syntax that errors here. This
matters most in issue #17.


::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

WHO OWNS WHAT, AND WHAT ORDER TO ATTACK IT
===========================================

Paste this as its own issue too, so everybody can see the plan in one place.

The split is BY MODULE, not by difficulty, so that two people are never editing the same
file at the same time. Merge conflicts in a feature module are painful; merge conflicts
in a menu file are trivial, because each menu action is a ten-line function plus one line
in ACTIONS.


JORGE -- every transaction and every schema trap
  #7   Place a bid              the hardest thing in the project
  #10  End an auction           the second transaction
  #5   Auction detail + history straddles auctions.py and bids.py
  #4   Search                   feeds #17
  #14  Change a user's role     short code, hardest reasoning
  #17  Physical design + tuning 10% of the grade on its own
  Owns: src/auctions.py, src/bids.py, sql/indexes.sql

PARTNER A -- owns src/items.py and src/shipments.py end to end
  #8   Create a listing and start an auction
  #9   Manage your own listings
  #15  Admin: remove an item     it is items.py, so it is yours
  #12  Shipments
  Owns: src/items.py, src/shipments.py, src/menus/seller.py

PARTNER B -- owns src/users.py, src/payments.py and src/reports.py
  #16  Admin reports             DO THIS FIRST, it blocks Jorge's #17
  #13  List and view users       the easiest issue on the board, start here to warm up
  #6   View and edit profile
  #11  Pay for a won auction
  Owns: src/users.py, src/payments.py, src/reports.py, src/menus/admin.py

Shared, at the end, everybody:
  #18  Input validation and error handling
  #19  Final report
  #20  Demo preparation
  #21  Bulk dataset

Two collisions to be aware of, both small:
  - Issue #8 needs auctions.create(), which lands in Jorge's src/auctions.py. It is about
    15 lines and it does not touch browse, search, detail or end. Write it, tell Jorge.
  - Issues #9 and #15 are both in src/items.py and both belong to Partner A, so they are
    sequential, not parallel. Do #9 first.


WHAT IS ACTUALLY BLOCKED BY WHAT

Almost nothing. sql/seed.sql was written early precisely so that every feature has rows
in every state it needs, which killed the runtime dependencies. Issues #4 through #16 can
all be started today, in any order, by anybody.

There is exactly ONE real chain in the whole remaining project:

    #4 search   ----+
    #5 detail   ----+---->  #17 tuning  ---->  #19 report
    #16 reports ----+            ^
                                 |
    #21 bulk dataset ------------+

#17 cannot start until the queries it tunes exist (#4, #5, #16) and until there is enough
data for a measurement to mean anything (#21). #17 is worth 10% by itself and it is the
thing most likely to get squeezed at the end, so #16 and #21 are the two issues that
matter most for scheduling. Get them out of the way early.

Then at the very end:

    everything ----> #18 validation ----> #20 demo


::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

ISSUE 1 -- LOAD THE SCHEMA INTO EACH DEVELOPER'S DATABASE
==========================================================

Labels: foundation, sql, blocker
Assignee: Jorge
STATUS: DONE, 2026-08-20

scripts/load_db.py is written, verified on the server, and documented in README section
1.10. It runs sql/schema.sql, then sql/extensions.sql, then sql/seed.sql, then
sql/indexes.sql, all inside ONE transaction, skipping any file that is empty. Flags:
--yes skips the confirmation prompt, --dry-run shows the plan without connecting.

Nothing left to do here. Kept for the record.


::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

ISSUE 2 -- SHARED FOUNDATION: ERRORS, UI, AUTH, SESSION, MENU DISPATCH
=======================================================================

Labels: foundation, client, blocker
Assignee: Jorge
STATUS: DONE, 2026-08-21

Everything every feature imports. Shipped:

  - src/errors.py     15 exception classes, all inheriting AppError.
  - src/ui.py         the full helper set. All rich usage lives here and nowhere else.
  - src/auth.py       Session (a frozen dataclass of login and role), require_role(),
                      register(), login(). No separate src/session.py -- a five-line
                      dataclass did not justify a module.
  - src/menus/__init__.py   the login gate, dispatch(), run_role_menu(), and the one
                      try/except AppError that protects the whole application.
  - src/menus/buyer.py, seller.py, admin.py   menu structure complete, all actions
                      listed, bodies still placeholders naming their issue.
  - main.py           one SELECT 1 startup check so a dead Postgres is reported before
                      anyone types a password, then menus.run().

Also settled here and NOT to be relitigated: primary keys come from sequences in
sql/extensions.sql, so there is no src/ids.py. Both src/ids.py and src/session.py were
deleted. Do not recreate either.

Nothing left to do here. Kept for the record.


::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

ISSUE 3 -- BROWSE AUCTIONS
===========================

Labels: client, sql, buyer
Assignee: Jorge
STATUS: DONE, 2026-08-21

auctions.browse(session) in src/auctions.py, rendered by browse_auctions(session) in
src/menus/buyer.py.

THIS IS THE REFERENCE SLICE. It was written first, on its own, specifically so the other
eleven features have a worked example to copy. Before you start your issue, read those
two functions -- they are deliberately over-commented and the comments explain WHY, not
just what.

Nothing left to do here. Kept as the template.


::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

ISSUE 4 -- SEARCH AUCTIONS
===========================

Labels: client, sql, buyer
Assignee: Jorge
Blocks: #17

WHAT IT IS
Filtered search over auctions. Spec section 6.1. Available to every logged-in user, so
there is no require_role() call.

FILES YOU TOUCH
  - src/auctions.py           add search()
  - src/menus/buyer.py        replace the body of search_items(session)

THE FUNCTION

    def search(session, name=None, category=None, max_price=None, status=None):

  - Returns a list of dicts, same column shape as browse() so the menu can reuse the
    same columns list.
  - Every filter is optional. None means "do not filter on this".

STEPS
  1 / Start from the SELECT in auctions.browse(). It already joins auction to item on
      item_id, which is safe and cannot duplicate rows because auction.item_id is UNIQUE
      and NOT NULL.
  2 / Build the WHERE clause from whichever filters were actually supplied. The way to
      do this WITHOUT string-concatenating user input:

        clauses = []
        params = []
        if name is not None:
            clauses.append("i.item_name ILIKE %s")
            params.append(f"%{name}%")
        ...
        where = " AND ".join(clauses) if clauses else "TRUE"

      The CLAUSE text is ours and is a fixed string. Only the VALUES go into params, and
      they reach the database through psycopg's second argument. That is the safe
      pattern. Note the % wildcards go on the VALUE, not into the SQL text.
  3 / The four filters:
        - name         ILIKE with wildcards both sides, case-insensitive partial match
        - category     exact match on i.category
        - max_price    a ceiling: a.current_highest_bid <= %s
        - status       a.auction_status = %s, either 'Active' or 'Closed'
  4 / Unlike browse(), do NOT hardcode a status filter. The whole point of the status
      filter is that search is how you reach closed auctions.
  5 / ORDER BY a.auction_id DESC, same as browse.

THE MENU ACTION
  - Prompt for each of the four filters with ui.prompt() and ui.prompt_decimal().
  - A BLANK ANSWER MEANS "do not filter". So pass required=False to ui.prompt() and turn
    an empty string into None before calling search().
  - For status, ui.menu() with options Active / Closed / Any is friendlier than making
    them type it.
  - Render with ui.page(), reusing the same columns list browse_auctions() uses.

TESTING AGAINST SEED DATA
  - Searching category with a value that appears on several items should return several
    rows -- there are 9 items across 6 categories.
  - status='Closed' must return auctions 4, 5 and 7. If it returns nothing you have
    accidentally kept browse's hardcoded Active filter.
  - A max_price below every current_highest_bid should return an empty list, and
    ui.page() should print "Nothing to show." rather than crash.

NOTE FOR ISSUE 17
This query is the headline candidate for the tuning work. Write down which columns you
end up filtering on -- item_name, category, current_highest_bid, auction_status -- because
that list is what the index work in #17 starts from.

DONE WHEN
A buyer can find auctions by any combination of name, category, price and status, and
leaving every filter blank returns everything.


::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

ISSUE 5 -- VIEW ONE AUCTION IN DETAIL
======================================

Labels: client, sql, buyer
Assignee: Jorge
Blocks: #17

WHAT IT IS
Full detail on a single auction plus its bid history. Spec section 6.1. Available to
every logged-in user.

This is the only issue that touches two feature modules, which is why it is assigned to
the person who owns both.

FILES YOU TOUCH
  - src/auctions.py           add detail()
  - src/bids.py               add history()      -- currently only a docstring
  - src/menus/buyer.py        replace the body of view_auction(session)

THE FUNCTIONS

    def detail(session, auction_id):

  - Returns ONE dict, not a list. Join auction to item, and select the item attributes
    (item_name, category, starting_price, item_condition, description, image_url), the
    seller_login, current_highest_bid, auction_status, and winner_login.
  - Use .fetchone(). If it returns None, raise NotFound("Auction", auction_id).

    def history(session, auction_id):

  - Returns a list of dicts: bid_id, buyer_login, bid_amount, bid_timestamp.
  - ORDER BY bid_timestamp DESC -- newest first. bid_timestamp is the ONLY timestamp in
    the whole schema, so it is what every "newest first" ordering in the application
    sorts on.
  - An empty list is a normal answer, not an error. Auction 3 has no bids on purpose.
  - Do NOT raise NotFound here. detail() already validated the id; if you raise in both
    places you get two different errors for the same mistake.

THE MENU ACTION
  1 / ui.prompt_int() for the auction id.
  2 / Call auctions.detail(). If it raises NotFound, you do nothing -- run_role_menu()
      catches it and prints it. Do not write a try/except.
  3 / Render the detail with ui.table([row], columns) -- a one-row table -- or with
      ui.heading() plus a few ui.info() lines. A single record does not need pagination.
  4 / Then call bids.history() and render that with ui.page().
  5 / Show winner_login only when auction_status is 'Closed'. On an Active auction it is
      always NULL and printing "Winner: --" is noise.

TESTING AGAINST SEED DATA
  - Auction 1 -- Active with several bids, the ordinary case.
  - Auction 3 -- Active with NO bids. current_highest_bid is 0.00 and the history table
    must come back empty and render cleanly.
  - Auction 4 -- Closed, won by buyer2. winner_login must display.
  - Auction 99 -- does not exist. Must print one clean red line, not a traceback.

DONE WHEN
A buyer can inspect one auction and see who has bid what, and a bad id gives a clean
message.


::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

ISSUE 6 -- VIEW AND EDIT YOUR PROFILE
======================================

Labels: client, sql, buyer
Assignee: Partner B

WHAT IT IS
Spec section 6.1: a user may update their profile fields EXCEPT login and role.

This is a good second issue to warm up on. It is small and it has no traps.

FILES YOU TOUCH
  - src/users.py              add get_profile() and update_profile()  -- currently only
                              a docstring, so you are starting this module
  - src/menus/buyer.py        replace the bodies of view_profile(session) and
                              edit_profile(session)

THE FUNCTIONS

    def get_profile(session):

  - SELECT login, phone_num, address, role, favorite_category FROM users WHERE login = %s
  - Pass session.login as the parameter. Do NOT take a login argument -- a user views
    their own profile, and taking a login would let anyone view anyone.
  - DO NOT SELECT THE PASSWORD. Never put a password on screen.
  - Returns one dict via .fetchone().

    def update_profile(session, **fields):

  - Accepts ONLY these four keys: password, phone_num, address, favorite_category.
  - REJECT login and role AT THE MODULE LEVEL, not just by leaving them out of the menu.
    Build an allowed set, and if any key is not in it, raise
    NotAuthorized("change your login or role"). Leaving them out of the menu is not
    access control.
  - Build the SET clause from whichever fields were actually passed, using the same
    safe pattern as issue #4 -- fixed clause text, values in params.
  - If no fields were passed at all, return early without running an UPDATE. An UPDATE
    with an empty SET is a syntax error.
  - WHERE login = %s with session.login.

THE MENU ACTIONS
  - view_profile(): call get_profile(), render with ui.table([row], columns).
  - edit_profile(): prompt for each editable field, passing the CURRENT value as the
    default so ui.prompt(label, default=current) leaves it unchanged when the user just
    presses enter. Collect only the fields that actually changed into a dict and pass it
    as **fields.
  - Use ui.prompt_password() for the password field.
  - Pass max_length to match the schema: phone_num 20, address 255,
    favorite_category 50, password 100.
  - ui.success("Profile updated.") at the end.

TESTING AGAINST SEED DATA
  - buyer3 has a NULL favorite_category, so it is the account that proves a NULL renders
    as a dim dash rather than crashing.
  - Change buyer1's address, log out, log back in, view the profile again -- it must
    persist. That proves the "with get_connection()" block really did commit.
  - Try passing role="Admin" into update_profile() from a Python shell. It must raise
    NotAuthorized, not silently promote them.

DONE WHEN
A user can view their profile and change any permitted field, and cannot change login or
role by any route.


::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

ISSUE 7 -- PLACE A BID
=======================

Labels: client, sql, buyer
Assignee: Jorge

WHAT IT IS
The most constraint-heavy feature in the project and the one most likely to be probed
during the demo. Spec sections 6.3 and 6.4.

FILES YOU TOUCH
  - src/bids.py               add place() and list_for_buyer()
  - src/menus/buyer.py        replace the bodies of place_bid(session) and
                              my_bids(session)

THE RULES, ALL FOUR
  1 / The bid must be STRICTLY GREATER than auction.current_highest_bid.
  2 / The bid must ALSO clear item.starting_price. A fresh auction has
      current_highest_bid = 0.00, so checking against the current high alone would let
      someone bid one cent on a $200 item. The minimum is therefore
      max(current_highest_bid, starting_price) and BidTooLow takes that as its second
      argument.
  3 / A seller cannot bid on their own auction -> SelfBid().
  4 / Only Active auctions accept bids -> AuctionClosed(auction_id).

THE FUNCTION

    def place(session, auction_id, amount):

STEPS -- ALL OF THIS IS ONE TRANSACTION
  1 / Open the connection with "with get_connection() as conn:". Everything below happens
      inside that block. Do NOT call conn.commit() -- the block does it.
  2 / SELECT the auction row JOINED to item, and add FOR UPDATE:

        SELECT a.auction_status, a.current_highest_bid, a.seller_login,
               i.starting_price
        FROM auction a
        JOIN item i ON i.item_id = a.item_id
        WHERE a.auction_id = %s
        FOR UPDATE

      FOR UPDATE takes a row lock that is held until the transaction ends. Without it,
      two people bidding at the same moment can BOTH read the same current_highest_bid,
      both pass validation, and both insert -- and the auction ends up with a
      current_highest_bid that is lower than the highest actual bid. This is the entire
      reason this function is a transaction.

      Note: in PostgreSQL 10 you may need "FOR UPDATE OF a" because of the join. Test it.
  3 / .fetchone() returned None -> raise NotFound("Auction", auction_id).
  4 / Validate, in this order, raising immediately:
        - auction_status != 'Active'          -> AuctionClosed(auction_id)
        - seller_login == session.login       -> SelfBid()
        - amount <= max(high, starting_price) -> BidTooLow(amount, minimum)
      Raising inside the with block rolls the transaction back and releases the lock.
      That is correct and automatic.
  5 / INSERT the bid. Omit bid_id, let the sequence supply it, take it back with
      RETURNING:

        INSERT INTO bid (auction_id, buyer_login, bid_amount)
        VALUES (%s, %s, %s)
        RETURNING bid_id

      buyer_role has a column DEFAULT of 'Buyer' and a CHECK pinning it, so you do not
      pass it.
  6 / UPDATE auction SET current_highest_bid = %s WHERE auction_id = %s.
  7 / Return the new bid_id.

    def list_for_buyer(session):

  - Every bid this user has placed, joined to auction and item so the screen can show
    what they bid on. ORDER BY bid_timestamp DESC.
  - WHERE b.buyer_login = %s with session.login.
  - Worth including whether they are currently the high bidder -- compare bid_amount to
    a.current_highest_bid in the SELECT and return it as a boolean column.

THE MENU ACTIONS
  - place_bid(): prompt for the auction id, then CALL auctions.detail() FIRST and show
    the current high bid before prompting for an amount. Nobody can bid sensibly without
    seeing what they are bidding against. Use ui.prompt_decimal(minimum=...) so an
    obviously bad number is rejected before it reaches the database. On success,
    ui.success() with the new bid id.
  - my_bids(): call list_for_buyer(), render with ui.page().

TESTING AGAINST SEED DATA
  - Auction 3 has NO bids and current_highest_bid 0.00. Bidding 0.01 on it must be
    REFUSED because of rule 2 -- it has to clear the item's starting_price. This is the
    single most important test in this issue.
  - seller1 owns auctions 1, 2, 5 and 7. Logging in as seller1 and bidding on auction 1
    must raise SelfBid.
  - Auction 4 is Closed. Bidding on it must raise AuctionClosed.
  - Bid below the current high on auction 1 -> BidTooLow.
  - After a successful bid, check that auction.current_highest_bid changed too. If the
    bid row exists but the auction did not move, your transaction is wrong.

FOR THE REPORT
current_highest_bid is denormalized -- it duplicates information derivable from the bid
table. Keeping the two consistent is the entire point of the transaction and the row
lock. Write a paragraph about this. It is exactly the kind of tradeoff the documentation
grade rewards.

DONE WHEN
Valid bids are recorded, every rule above is enforced with a clear message, and the
auction row and the bid rows never disagree.


::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

ISSUE 8 -- CREATE A LISTING AND START AN AUCTION
=================================================

Labels: client, sql, seller
Assignee: Partner A

WHAT IT IS
Sellers list an item, and then separately put that item up for auction. Spec sections
6.2 and 6.3.

THESE ARE TWO SEPARATE MENU ACTIONS, NOT ONE TRANSACTION. They are already two separate
entries on the Seller menu. The reason: auction.item_id is UNIQUE, so auctioning an item
is IRREVERSIBLE -- there is no relisting a failed auction without creating a new item
row. A seller should be able to create a listing, look at it, fix a typo, and only then
put it up. sql/seed.sql deliberately carries two items with no auction (items 7 and 8) so
this path has data to work with on day one.

FILES YOU TOUCH
  - src/items.py              add create()  -- currently only a docstring, you are
                              starting this module
  - src/auctions.py           add create()  -- THIS IS JORGE'S FILE. It is about 15 lines
                              and it does not touch browse, search, detail or end. Write
                              it, then tell him.
  - src/menus/seller.py       replace the bodies of create_listing(session) and
                              start_auction(session)

THE FUNCTIONS

    def create(session, name, category, starting_price,
               description=None, condition=None, image_url=None):

  - In src/items.py.
  - FIRST LINE: require_role(session, "Seller", "create a listing"). The schema's
    seller_role foreign key would reject a Buyer anyway, but the error would be an
    incomprehensible constraint-violation message. Catch it ourselves and say something
    useful.
  - INSERT INTO item, omitting item_id, with RETURNING item_id.
  - Columns: item_name, category, starting_price, image_url, item_condition,
    description, seller_login. Note the column is item_condition, NOT condition --
    condition is close to a reserved word and the schema spells it out.
  - seller_login is session.login. seller_role has a DEFAULT of 'Seller' and a CHECK, so
    you do not pass it.
  - starting_price has a CHECK (starting_price >= 0), so a negative number raises a
    database error. Validate it in the menu with ui.prompt_decimal(minimum=0) so it never
    gets that far.
  - Returns the new item_id.

    def create(session, item_id):

  - In src/auctions.py.
  - require_role(session, "Seller", "start an auction").
  - Look up the item first. If it does not exist, raise NotFound("Item", item_id).
  - VERIFY OWNERSHIP: if item.seller_login != session.login, raise
    NotAuthorized("auction an item you do not own"). A seller must not be able to auction
    someone else's item by guessing an id.
  - INSERT INTO auction (item_id, seller_login) omitting auction_id, with
    RETURNING auction_id. current_highest_bid defaults to 0 and auction_status defaults
    to 'Active', so you do not pass either.
  - auction.item_id is UNIQUE. If the item is already auctioned, psycopg raises
    UniqueViolation. Catch it and raise ItemInUse(item_id, existing_auction_id) instead --
    look up the existing auction id first so the message can name it.

THE MENU ACTIONS
  - create_listing(): prompt for name (max_length 100), category (max_length 50),
    starting price with ui.prompt_decimal(minimum=0), then condition (max_length 50),
    description and image_url (max_length 255) as OPTIONAL -- pass required=False and
    turn empty strings into None. ui.success() naming the new item id.
  - start_auction(): show the seller their un-auctioned items first so they can pick one
    without guessing an id. That is a small SELECT, so it can live in items.py as part of
    issue #9's list_by_seller(), or as its own query here. Then ui.prompt_int() for the
    id and ui.confirm() before creating, because it cannot be undone.

TESTING AGAINST SEED DATA
  - Log in as seller1. Items 7 and 8 have no auction -- put one of them up and it must
    then appear in Browse.
  - Try to auction item 1, which auction 1 already covers. Must raise ItemInUse, not a
    raw UniqueViolation.
  - Log in as seller2 and try to auction one of seller1's items. Must raise
    NotAuthorized.
  - Log in as buyer1 and reach create_listing somehow -- it must raise NotAuthorized from
    require_role, proving the check is in the module and not just the menu.

DONE WHEN
A seller can list an item, then separately auction it, and it appears in browse.


::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

ISSUE 9 -- MANAGE YOUR OWN LISTINGS
====================================

Labels: client, sql, seller
Assignee: Partner A
Do this BEFORE #15 -- they are both in src/items.py.

WHAT IT IS
Spec section 6.2: sellers can create AND update their own items.

FILES YOU TOUCH
  - src/items.py              add list_by_seller() and update()
  - src/menus/seller.py       replace the bodies of my_listings(session) and
                              edit_listing(session)

THE FUNCTIONS

    def list_by_seller(session):

  - Every item belonging to session.login, LEFT JOINed to auction so items with no
    auction still appear. USE A LEFT JOIN, NOT AN INNER JOIN -- items 7 and 8 have no
    auction and an inner join would silently hide them, which is exactly the case issue
    #8 needs to see.
  - Return item_id, item_name, category, starting_price, and from the auction side
    auction_id, auction_status and current_highest_bid. Those three come back as NULL for
    an un-auctioned item, which ui renders as a dim dash.
  - ORDER BY i.item_id DESC.

    def update(session, item_id, **fields):

  - Allowed fields: item_name, category, starting_price, description, item_condition,
    image_url. NOT item_id and NOT seller_login.
  - Look the item up first. Not found -> NotFound("Item", item_id).
  - VERIFY OWNERSHIP: item.seller_login != session.login -> NotAuthorized("edit that
    listing"). Note there is no required_role argument here -- this is an ownership
    problem, not a role problem, and NotAuthorized words itself differently depending on
    whether you pass one.
  - REFUSE TO CHANGE starting_price ONCE BIDS EXIST. Check for bids on that item's
    auction:

        SELECT COUNT(*) FROM bid b
        JOIN auction a ON a.auction_id = b.auction_id
        WHERE a.item_id = %s

    If the count is greater than 0 and starting_price is among the fields being changed,
    raise AuctionHasBids(item_id). Moving the goalposts mid-auction is indefensible and
    the error class exists specifically for this.
  - Build the SET clause from the supplied fields only, same safe pattern as issue #6.
    Return early if no fields were passed.

THE MENU ACTIONS
  - my_listings(): call list_by_seller(), render with ui.page().
  - edit_listing(): show the list first, ui.prompt_int() for the id, then prompt for each
    field with the current value as the default so enter means unchanged. Only send the
    fields that actually changed.

TESTING AGAINST SEED DATA
  - seller1 owns items with auctions AND items without. Both must appear in my_listings.
  - Editing the starting_price of an item whose auction has bids -- auctions 1, 2 and 6
    all have bids -- must raise AuctionHasBids.
  - Editing the starting_price of item 7 or 8, which have no auction at all, must
    SUCCEED.
  - seller2 editing one of seller1's items must raise NotAuthorized.

DONE WHEN
A seller can review and edit their own listings, cannot touch anyone else's, and cannot
change a price out from under existing bidders.


::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

ISSUE 10 -- END AN AUCTION
===========================

Labels: client, sql, seller
Assignee: Jorge

WHAT IT IS
Spec section 6.3: the seller may end an auction at any time. The highest bidder wins and
the status becomes Closed.

Remember schema fact 4 -- there are no auction end times anywhere in the schema. An
auction closes when its seller closes it and never otherwise. This function is the ONLY
way an auction ever becomes Closed.

FILES YOU TOUCH
  - src/auctions.py           add end()
  - src/menus/seller.py       replace the body of end_auction(session)

THE FUNCTION

    def end(session, auction_id):

STEPS -- ONE TRANSACTION, SAME SHAPE AS ISSUE 7
  1 / "with get_connection() as conn:" around everything.
  2 / SELECT the auction FOR UPDATE. Not found -> NotFound("Auction", auction_id).
  3 / Verify ownership: seller_login != session.login -> NotAuthorized("end that
      auction").
  4 / Verify it is still open: auction_status != 'Active' -> AuctionClosed(auction_id).
  5 / Find the highest bidder:

        SELECT buyer_login, bid_amount
        FROM bid
        WHERE auction_id = %s
        ORDER BY bid_amount DESC, bid_timestamp ASC
        LIMIT 1

      The tiebreak on bid_timestamp ASC matters: if two bids somehow have the same
      amount, the EARLIER one wins, which is the conventional rule.
  6 / HANDLE THE NO-BIDS CASE. .fetchone() returns None when nobody bid. Close it anyway
      with winner_login left NULL -- the schema allows that, the column is nullable. Do
      NOT raise here; an auction nobody wanted is a normal outcome, not an error.
  7 / UPDATE auction SET winner_login = %s, auction_status = 'Closed' WHERE auction_id.
      winner_role has a DEFAULT of 'Buyer' and a CHECK pinning it, so you do not pass it.
      When there is no winner, pass None -- psycopg turns that into SQL NULL.
  8 / Return the winner's login and amount, or None, so the menu can report it.

THE MENU ACTION
  - Show the seller their active auctions first, then ui.prompt_int() for the id.
  - ui.confirm("This cannot be undone. Close auction 4?") BEFORE calling end(). It is
    irreversible.
  - Report the winner with ui.success(), or ui.warn("Closed with no bids.") when there
    was no winner.

TESTING AGAINST SEED DATA
  - Auction 1 is Active with bids. Closing it must set winner_login to whoever holds the
    highest bid -- cross-check against the bid table by hand.
  - AUCTION 3 IS ACTIVE WITH NO BIDS AT ALL. Closing it must succeed with winner_login
    NULL. This is the case people forget and it is the one a grader will try.
  - Auction 4 is already Closed. Closing it again must raise AuctionClosed.
  - seller2 closing one of seller1's auctions must raise NotAuthorized.

DONE WHEN
A seller can close an auction, the correct winner is recorded, and an auction with no
bids closes cleanly with no winner.


::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

ISSUE 11 -- PAY FOR A WON AUCTION
==================================

Labels: client, sql, buyer
Assignee: Partner B

WHAT IT IS
Spec section 6.5. The payment_status values are exactly Pending, Completed and Failed --
that is a CHECK constraint, so anything else is rejected by the database.

FILES YOU TOUCH
  - src/payments.py           add create() and list_for_buyer()  -- currently only a
                              docstring, you are starting this module
  - src/menus/buyer.py        replace the body of pay_for_won_auction(session)

THE FUNCTIONS

    def create(session, auction_id, amount):

  1 / Look the auction up. Not found -> NotFound("Auction", auction_id).
  2 / The auction must be Closed. If auction_status is still 'Active', raise
      NotWinner(auction_id) -- nobody has won it yet.
  3 / winner_login must equal session.login. Otherwise raise NotWinner(auction_id). A
      buyer must not be able to pay for an auction they did not win by guessing an id.
  4 / payment.auction_id is UNIQUE, so a second payment attempt fails at the database
      level with a UniqueViolation. Catch it and raise AlreadyPaid(auction_id). You can
      also check for an existing payment row first and raise before attempting the
      insert -- do BOTH, because the pre-check gives the clean message and the caught
      UniqueViolation covers the race.
  5 / INSERT INTO payment (auction_id, buyer_login, amount, payment_status), omitting
      payment_id, with RETURNING payment_id. buyer_role defaults to 'Buyer'.
  6 / Set payment_status to 'Completed'. We are not simulating a payment processor, so
      Pending and Failed exist in the schema but nothing in our application produces
      them. Note that in the report as a deliberate simplification.
  7 / Return the new payment_id.

    def list_for_buyer(session):

  - Everything this buyer has won, LEFT JOINed to payment so UNPAID wins still show up
    with NULLs. That is what makes this screen useful -- it shows what they owe as well
    as what they have paid.
  - FROM auction a LEFT JOIN payment p ON p.auction_id = a.auction_id
    JOIN item i ON i.item_id = a.item_id
    WHERE a.winner_login = %s
  - Return item_name, auction_id, current_highest_bid, p.amount, p.payment_status.

THE MENU ACTION
  - Call list_for_buyer() FIRST and show it, so they can see what they owe.
  - ui.prompt_int() for the auction id.
  - THE AMOUNT SHOULD DEFAULT TO THE WINNING BID rather than being freely typed. Read
    current_highest_bid off the row you already fetched and pass it as the default to
    ui.prompt_decimal(). Letting someone type any number they like for what they owe is
    the kind of thing a grader pokes at.
  - ui.success() with the payment id.

TESTING AGAINST SEED DATA
  - AUCTION 5 WAS WON BY buyer1 AND NEVER PAID. That is your happy path -- log in as
    buyer1 and pay it.
  - Auction 4 was won by buyer2 and IS already paid. Paying it again must raise
    AlreadyPaid.
  - Log in as buyer2 and try to pay for auction 5, which buyer1 won. Must raise
    NotWinner.
  - Try to pay for auction 1, which is still Active. Must raise NotWinner.

DONE WHEN
A winning buyer can pay exactly once, cannot pay for auctions they did not win, and can
see at a glance what is still outstanding.


::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

ISSUE 12 -- SHIPMENTS
======================

Labels: client, sql, seller
Assignee: Partner A

WHAT IT IS
Spec section 6.6. The shipment_status values are exactly Pending, Shipped and Delivered.
A shipment represents delivery AFTER payment completion, so the payment must exist and
be Completed before anything can ship.

SIMPLIFICATION ALREADY AGREED: there is NO tracking-number update flow. The status moves
Pending -> Shipped -> Delivered and that is all. Set the tracking number once, when you
mark it Shipped.

FILES YOU TOUCH
  - src/shipments.py          add create(), update_status() and list_for_buyer()  --
                              currently only a docstring, you are starting this module
  - src/menus/seller.py       replace the body of mark_shipped(session)
  - src/menus/buyer.py        replace the body of track_deliveries(session)

THE FUNCTIONS

    def create(session, auction_id, address=None):

  1 / require_role(session, "Seller", "create a shipment").
  2 / Look up the auction. Not found -> NotFound("Auction", auction_id).
  3 / Verify ownership -- only the SELLER of that auction may ship it. Otherwise
      NotAuthorized("ship that auction").
  4 / Check the payment:

        SELECT payment_status FROM payment WHERE auction_id = %s

      No row at all, or a status that is not 'Completed' -> raise
      PaymentIncomplete(auction_id, status). Pass the status you found when there is one,
      so the message can say what it actually is.

      NOTE: you are querying the payment table directly here. You are NOT calling
      anything in src/payments.py. That is deliberate -- it means this issue does not
      depend on issue #11 being finished, and seed.sql already has two Completed
      payments to work against.
  5 / DEFAULT THE ADDRESS from the winning buyer's users.address, but allow the caller
      to override it. When address is None, look it up:

        SELECT u.address FROM users u
        JOIN auction a ON a.winner_login = u.login
        WHERE a.auction_id = %s

      Copy it into the shipment row rather than joining to users at read time. A delivery
      address has to record where the parcel was ACTUALLY sent, even if the buyer moves
      house later. seed.sql does the same thing for the same reason.
  6 / INSERT INTO shipment (auction_id, address), omitting shipment_id, with
      RETURNING shipment_id. shipment_status defaults to 'Pending'.
  7 / shipment.auction_id is UNIQUE, so a second shipment for the same auction raises
      UniqueViolation. Catch it and raise a clear AppError.

    def update_status(session, shipment_id, status, tracking_number=None):

  - Only the seller of that auction may update it. You have to join shipment to auction
    to find out who that is:

        SELECT a.seller_login, s.shipment_status
        FROM shipment s
        JOIN auction a ON a.auction_id = s.auction_id
        WHERE s.shipment_id = %s

  - Not found -> NotFound("Shipment", shipment_id). Wrong seller -> NotAuthorized.
  - Validate that status is one of Pending, Shipped, Delivered before sending it. The
    CHECK constraint would catch it, but the error would be unreadable.
  - UPDATE shipment SET shipment_status = %s, and set tracking_number too when one was
    supplied.

    def list_for_buyer(session):

  - What this buyer bought and where it is. Join shipment to auction to item, filtered on
    a.winner_login = session.login.
  - Return item_name, auction_id, shipment_status, tracking_number, address.
  - Use a LEFT JOIN from auction so a won-and-paid auction with no shipment row yet still
    appears, showing NULL status. Otherwise the buyer just sees nothing and cannot tell
    the difference between "not shipped yet" and "does not exist".

THE MENU ACTIONS
  - mark_shipped() in seller.py: list the seller's paid-but-unshipped auctions, prompt
    for one, prompt for a tracking number (max_length 100, required=False), then either
    create() the shipment or update_status() it to 'Shipped' depending on whether one
    exists yet. ui.success() at the end.
  - track_deliveries() in buyer.py: call list_for_buyer(), render with ui.page().

TESTING AGAINST SEED DATA
  - AUCTION 7 IS PAID AND ITS SHIPMENT IS STILL PENDING WITH A NULL TRACKING NUMBER.
    That is your happy path -- log in as seller1 and mark it Shipped.
  - Auction 4 is already Delivered.
  - AUCTION 5 WAS WON BY buyer1 AND NEVER PAID. Trying to ship it must raise
    PaymentIncomplete. This is the rule this issue exists to enforce.
  - Auction 1 is still Active and has no winner. Trying to ship it must fail cleanly.
  - seller2 trying to update seller1's shipment must raise NotAuthorized.

DONE WHEN
A seller can ship a paid auction, cannot ship an unpaid one, and both parties can see the
status and tracking number.


::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

ISSUE 13 -- ADMIN: LIST AND VIEW USERS
=======================================

Labels: client, sql, admin
Assignee: Partner B
This is the easiest issue on the board. Start here.

WHAT IT IS
Spec section 6.1: admins manage users.

FILES YOU TOUCH
  - src/users.py              add list_all() and detail()
  - src/menus/admin.py        replace the bodies of list_users(session) and
                              view_user(session)

THE FUNCTIONS

    def list_all(session, role=None, search=None):

  - FIRST LINE: require_role(session, "Admin", "list all users").
  - SELECT login, phone_num, address, role, favorite_category FROM users.
  - NEVER SELECT THE PASSWORD COLUMN. Not here, not in detail(), not anywhere. It is
    plain text in this schema and putting it on screen in front of a grader is the
    worst possible look.
  - Optional filters, same safe pattern as issue #4: role is an exact match, search is
    an ILIKE partial match on login.
  - ORDER BY login.

    def detail(session, target_login):

  - require_role(session, "Admin", "view a user").
  - NOTE THE SECOND PARAMETER. This is the case Rule 1 mentions -- the ACTING user comes
    from session, but the TARGET user is a normal argument, because an admin is
    deliberately looking at somebody else.
  - Not found -> NotFound("User", target_login).
  - Return the profile PLUS their activity. Simplest version is three separate small
    queries returned as a dict of lists:
      - their items:     SELECT item_id, item_name, category FROM item
                         WHERE seller_login = %s
      - their bids:      SELECT b.bid_id, b.auction_id, b.bid_amount, b.bid_timestamp
                         FROM bid b WHERE b.buyer_login = %s
      - their payments:  SELECT payment_id, auction_id, amount, payment_status
                         FROM payment WHERE buyer_login = %s
    Three simple queries beats one clever query with three left joins that multiplies
    rows together.

THE MENU ACTIONS
  - list_users(): prompt for an optional role filter with ui.menu() offering
    Buyer / Seller / Admin / Any, and an optional login search with ui.prompt(
    required=False). Render with ui.page() -- this is exactly what pagination was built
    for.
  - view_user(): ui.prompt() for the login, then render the profile with ui.table() and
    each of the three activity lists with its own ui.heading() plus ui.page().

TESTING AGAINST SEED DATA
  - There are 7 users. Filtering by role Seller must return exactly seller1 and seller2.
  - Filtering by role Buyer must return buyer1, buyer2, buyer3 and newbie1.
  - view_user("seller1") must show their items. view_user("buyer1") must show their bids
    AND the fact that they won auction 5.
  - view_user("newbie1") must show empty lists everywhere without crashing.
  - Log in as buyer1 and reach these functions -- require_role must raise NotAuthorized.
  - Grep your own output. If the word "password" or the string "pass123" appears
    anywhere, fix it.

DONE WHEN
An admin can browse and search all users, inspect one in detail, and no password is ever
displayed.


::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

ISSUE 14 -- ADMIN: CHANGE A USER'S ROLE
========================================

Labels: client, sql, admin
Assignee: Jorge

WHAT IT IS
Spec section 6.1: ONLY an Admin can promote a user to Seller or Admin.

This is the single trickiest interaction with the schema in the entire project. The code
is short; the reasoning is not. Read the whole block before writing anything.

WHY IT IS HARD

The users table carries UNIQUE (login, role) specifically so that item, auction, bid and
payment can foreign-key to the PAIR (login, role) and then pin the role with a CHECK --
item.seller_role must equal 'Seller', bid.buyer_role must equal 'Buyer'. That is how
role-based integrity is enforced in pure SQL.

Those foreign keys are ON UPDATE CASCADE.

So: UPDATE users SET role = 'Buyer' WHERE login = 'seller1' does not just change one row.
It CASCADES into item.seller_role and auction.seller_role, setting them to 'Buyer' too --
and those columns have CHECK (seller_role = 'Seller'). The update blows up with a
constraint violation from a table you never mentioned.

The same thing happens in reverse: promoting a Buyer who has bids cascades into
bid.buyer_role, which has CHECK (buyer_role = 'Buyer').

THE POLICY, ALREADY DECIDED: REFUSE OUTRIGHT

Whenever the user owns rows that depend on their current role, refuse the change and
explain why. Both directions are blocked. We do not try to be clever about it -- there is
no safe way to rewrite the dependent rows without dropping and recreating foreign keys,
and that is not worth it for a feature nobody demos twice.

Promoting a FRESH Buyer still works, so the sequence register -> promote -> list an item
is intact, which is the only path the demo actually needs.

FILES YOU TOUCH
  - src/users.py              add change_role()
  - src/menus/admin.py        replace the body of change_user_role(session)

THE FUNCTION

    def change_role(session, target_login, new_role):

  1 / require_role(session, "Admin", "change a user's role").
  2 / PREVENT AN ADMIN FROM DEMOTING THEMSELVES. If target_login == session.login, raise
      RoleChangeBlocked with the reason "you cannot change your own role". Without this,
      the last admin can lock everybody out of the admin menu and the only fix is a
      manual UPDATE in psql.
  3 / Look the user up. Not found -> NotFound("User", target_login).
  4 / new_role must be one of Buyer, Seller, Admin. The CHECK constraint would catch it,
      but catch it first.
  5 / If new_role equals the current role, return early. Nothing to do.
  6 / COUNT THE DEPENDENT ROWS. Which ones matter depends on the CURRENT role:
        - currently a Seller: count item WHERE seller_login = %s, and count auction
          WHERE seller_login = %s
        - currently a Buyer:  count bid WHERE buyer_login = %s, count payment WHERE
          buyer_login = %s, and count auction WHERE winner_login = %s
      Any count greater than zero -> raise
      RoleChangeBlocked(login, current_role, new_role, reason) with a reason naming what
      you found, e.g. "they own 3 items and 2 auctions".
  7 / Only if everything is zero, run the UPDATE.

THE MENU ACTION
  - ui.prompt() for the target login, ui.menu() for the new role.
  - ui.confirm() before applying it.
  - On refusal you do nothing -- run_role_menu() catches RoleChangeBlocked and prints the
    sentence it built.

TESTING AGAINST SEED DATA
  - newbie1 IS A BUYER WITH NO ITEMS AND NO BIDS. It is the ONLY account in the seed data
    that can actually be promoted. Promoting newbie1 to Seller must SUCCEED, and after
    that they must be able to create a listing.
  - Promoting buyer1 to Seller must be REFUSED -- they have bids and they won auction 5.
  - Demoting seller1 to Buyer must be REFUSED -- they own items and auctions.
  - admin1 changing their own role must be REFUSED by step 2.
  - Log in as seller1 and reach this -- require_role must raise NotAuthorized.

FOR THE REPORT
Write this one up properly. It is a genuine schema-level limitation, spec section 2.2
asks for exactly this kind of documented constraint, and the docstring on
RoleChangeBlocked in src/errors.py was already written to drop straight into the report.

DONE WHEN
An admin can change roles where it is safe, and gets a clear explanation rather than a
stack trace where it is not.


::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

ISSUE 15 -- ADMIN: MANAGE AND REMOVE ITEMS
===========================================

Labels: client, sql, admin
Assignee: Partner A
Do this AFTER #9 -- they are both in src/items.py.

WHAT IT IS
Spec section 6.2: admins can manage or remove items when needed.

FILES YOU TOUCH
  - src/items.py              add admin_update() and admin_delete()
  - src/menus/admin.py        replace the body of remove_item(session)

THE FUNCTIONS

    def admin_update(session, item_id, **fields):

  - require_role(session, "Admin", "edit any item").
  - Identical to items.update() from issue #9 EXCEPT there is no ownership check -- an
    admin can edit anyone's item. Keep the AuctionHasBids guard on starting_price
    though; that rule protects bidders, not sellers, so it applies to admins too.
  - Do not copy-paste the whole of update(). Factor the shared SET-clause building into a
    small private helper, e.g. _apply_item_fields(conn, item_id, fields), and have both
    call it.

    def admin_delete(session, item_id):

  - require_role(session, "Admin", "delete an item").
  - Not found -> NotFound("Item", item_id).
  - THE POLICY, ALREADY DECIDED: REFUSE WHILE AN AUCTION EXISTS. No cascade logic.

        SELECT auction_id FROM auction WHERE item_id = %s

    If a row comes back, raise ItemInUse(item_id, auction_id). The error class takes both
    so the message can name the auction that is blocking the delete.
  - The schema would refuse anyway -- item is referenced by auction with ON DELETE
    RESTRICT -- but the raw error is unreadable. We check first so the message is ours.
  - Only if there is no auction, DELETE FROM item WHERE item_id = %s.

THE MENU ACTION
  - ui.prompt_int() for the item id.
  - ui.confirm() before deleting. It is destructive and there is no undo.
  - ui.success() on completion.

TESTING AGAINST SEED DATA
  - ITEMS 7 AND 8 HAVE NO AUCTION. They are the only two that can actually be deleted.
    Note that deleting one of them takes away the data issue #8 needs, so either delete
    only one, or re-run scripts/load_db.py afterwards.
  - Items 1 through 6 and item 9 all have auctions. Deleting any of them must raise
    ItemInUse naming the auction, not a raw ForeignKeyViolation.
  - Log in as seller1 and reach these -- require_role must raise NotAuthorized.

DONE WHEN
An admin can correct or remove listings, and the delete rule is enforced with an
explanation rather than a database error.


::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

ISSUE 16 -- ADMIN: MONITOR AUCTIONS, THE REPORTS
=================================================

Labels: client, sql, admin
Assignee: Partner B
DO THIS FIRST. It blocks Jorge's issue #17.

WHAT IT IS
Spec section 6.1: admins monitor auctions. This is also where the "SQL queries and
reports" half of the 30% lives. A grader looking for real SQL is looking HERE, so these
queries must be genuinely analytical -- GROUP BY, HAVING, aggregates, outer joins -- not
plain selects with a WHERE.

SCOPE ALREADY AGREED: FOUR REPORTS, NOT SIX. The four menu actions already exist in
src/menus/admin.py. Do those four properly rather than six badly.

WHERE THE CODE GOES -- DECISION
Create a NEW MODULE, src/reports.py. The "one feature module per table" rule does not fit
here because every one of these queries spans three or four tables and belongs to none of
them. Do not scatter them across auctions.py and users.py.

FILES YOU TOUCH
  - src/reports.py            NEW FILE. Give it a module docstring in the same style as
                              the others, saying what it is and why it exists as its own
                              module.
  - src/menus/admin.py        replace the bodies of report_top_bidders(session),
                              report_revenue_by_category(session),
                              report_unpaid_wins(session) and
                              report_active_auctions(session)

Every function takes (session), starts with require_role(session, "Admin", "..."), opens
its own connection, and returns a list of dicts. Same contract as everything else.

THE FOUR REPORTS

  1 / def top_bidders(session):
      Who bids the most, by COUNT and by total value.
        SELECT b.buyer_login, COUNT(*) AS bid_count, SUM(b.bid_amount) AS total_value,
               MAX(b.bid_amount) AS highest_bid
        FROM bid b
        GROUP BY b.buyer_login
        ORDER BY bid_count DESC, total_value DESC
      Consider adding HAVING COUNT(*) >= 2 so the report is about ACTIVE bidders rather
      than everyone who ever clicked once. Using HAVING at all is worth marks.

  2 / def revenue_by_category(session):
      Money actually taken, grouped by item category. Join payment to auction to item.
        SELECT i.category, COUNT(*) AS sales, SUM(p.amount) AS revenue,
               AVG(p.amount) AS average_sale
        FROM payment p
        JOIN auction a ON a.auction_id = p.auction_id
        JOIN item i ON i.item_id = a.item_id
        WHERE p.payment_status = 'Completed'
        GROUP BY i.category
        ORDER BY revenue DESC
      Only count Completed payments. Revenue that failed is not revenue.

  3 / def unpaid_wins(session):
      Auctions that closed with a winner but have no payment. THIS IS AN OUTER JOIN
      PROBLEM and it is the most interesting query of the four:
        SELECT a.auction_id, i.item_name, a.winner_login, a.current_highest_bid,
               a.seller_login
        FROM auction a
        JOIN item i ON i.item_id = a.item_id
        LEFT JOIN payment p ON p.auction_id = a.auction_id
        WHERE a.auction_status = 'Closed'
          AND a.winner_login IS NOT NULL
          AND p.payment_id IS NULL
        ORDER BY a.current_highest_bid DESC
      The LEFT JOIN plus "IS NULL on the right-hand side" is the standard way to express
      "rows in A with no match in B". payment.auction_id being UNIQUE is what makes this
      simple.

  4 / def active_auctions(session):
      Every open auction ordered by current highest bid, with how many bids it has drawn.
        SELECT a.auction_id, i.item_name, i.category, a.seller_login,
               a.current_highest_bid, COUNT(b.bid_id) AS bid_count
        FROM auction a
        JOIN item i ON i.item_id = a.item_id
        LEFT JOIN bid b ON b.auction_id = a.auction_id
        WHERE a.auction_status = 'Active'
        GROUP BY a.auction_id, i.item_name, i.category, a.seller_login,
                 a.current_highest_bid
        ORDER BY a.current_highest_bid DESC
      LEFT JOIN again, so an auction with no bids still appears with a count of 0. An
      inner join would hide auction 3, which is exactly the row that makes the report
      interesting.
      In PostgreSQL 10 every non-aggregated column must be in the GROUP BY. Newer
      Postgres lets you group by the primary key alone; PG 10 does not. List them all.

THE MENU ACTIONS
All four are the same three lines: call the report function, define a columns list,
ui.page(). Copy browse_auctions() in src/menus/buyer.py.

TESTING AGAINST SEED DATA
  - top_bidders: 11 bids across buyer1, buyer2 and buyer3. Cross-check one login's count
    by hand.
  - revenue_by_category: two Completed payments, 245.00 and 40.00, on different items.
    Check the categories are right and the SUM matches.
  - unpaid_wins: MUST RETURN EXACTLY AUCTION 5. buyer1 won it and never paid, and it is
    in the seed data specifically for this report. If you get 0 rows your LEFT JOIN or
    your IS NULL is wrong. If you get 3 rows you have inner-joined.
  - active_auctions: must return auctions 1, 2, 3 and 6. AUCTION 3 MUST APPEAR WITH A
    bid_count OF 0. If it is missing, you inner-joined the bids.

NOTE FOR ISSUE 17
Write down the tables and columns each of these four queries touches. That list feeds
straight into the index work.

DONE WHEN
An admin has four working reports, each using real aggregation, and the numbers can be
verified by hand against the seed data.


::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

ISSUE 17 -- PHYSICAL DATABASE DESIGN AND TUNING
================================================

Labels: tuning, sql
Assignee: Jorge
DEPENDS ON: #4, #5, #16 (the queries to tune) and #21 (enough data to measure)

WHAT IT IS
Worth 10% of the project grade on its own. Do it AFTER the features work, because you
need real queries to tune and real data to measure.

FILES YOU TOUCH
  - sql/indexes.sql           currently EMPTY on purpose. This is where the work lands.
                              scripts/load_db.py already runs it last and skips it while
                              it is empty, so nothing needs wiring up.
  - docs/                     the write-up

STEPS
  1 / Collect the actual queries the application runs. The hot ones are search (#4),
      browse (#3), auction detail and bid history (#5), and the four reports (#16).
      Copy the real SQL out of the modules -- do not invent representative queries.
  2 / Load the bulk dataset from issue #21 first. Indexes only demonstrably help on
      enough rows; on 30 seed rows Postgres will sequential-scan everything and every
      measurement will be noise.
  3 / RUN ANALYZE before measuring anything, so the planner has fresh statistics.
      Re-run it after each bulk load.
  4 / Record a BASELINE with EXPLAIN ANALYZE on each query, before any indexes. Save the
      output. Note the plan node types -- Seq Scan versus Index Scan -- as well as the
      timings.
  5 / Write sql/indexes.sql with justified indexes. Likely candidates, from the columns
      the features actually filter and join on:
        - item(category)                  -- search filter, revenue report GROUP BY
        - item(item_name)                 -- the ILIKE in search
        - bid(auction_id, bid_amount DESC) -- bid history ordering, and finding the
                                             winner in #10
        - auction(auction_status)         -- browse, and the active-auctions report
        - auction(seller_login)           -- my listings, ownership checks
        - auction(winner_login)           -- the unpaid-wins report
      Add them ONE AT A TIME and re-measure after each. Adding six at once tells you
      nothing about which one helped.
  6 / Re-measure and record the numbers.
  7 / Write up what worked, what did not, and WHY -- INCLUDING THE INDEXES THAT MADE NO
      DIFFERENCE. An index that did not help is a real finding and saying so is worth
      more than pretending everything worked.

POSTGRESQL 10 CONSTRAINTS -- READ BEFORE WRITING ANY INDEX
The server runs PostgreSQL 10.23, from 2017.
  - NO covering indexes. CREATE INDEX ... INCLUDE (...) is PostgreSQL 11 and up. It will
    error here.
  - NO CALL, and no stored procedures. Functions only.
  - None of the PostgreSQL 11+ planner improvements exist.
  - A plain B-tree index does NOT help "ILIKE '%foo%'" with a leading wildcard. If you
    want that to be indexable you need a trigram index (pg_trgm), and whether the
    extension is available on this server needs checking BEFORE you plan on it. If it is
    not available, say so in the write-up -- that is a legitimate finding too.
  - Check any syntax you find online against the PostgreSQL 10 docs. Modern tutorials
    will hand you syntax that fails here.

DONE WHEN
sql/indexes.sql is committed, and the report contains before-and-after timings with an
explanation of every index -- including the ones that did nothing.


::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

ISSUE 18 -- INPUT VALIDATION AND ERROR HANDLING
================================================

Labels: client
Assignee: everybody, at the end
DEPENDS ON: all the feature issues

WHAT IT IS
Spec section 3 offers extra credit for robust error handling. This is what separates a
demo that survives a grader poking at it from one that does not. Most of it is already
built -- this issue is the pass where we go and check.

CHECKLIST
  - No unhandled traceback ever reaches the user. run_role_menu() in
    src/menus/__init__.py already catches AppError. main.py catches everything else at
    the very top. Verify both, and decide whether to add a friendly "something went
    wrong, returning to the menu" rather than exiting.
  - Every numeric prompt re-prompts on garbage input instead of crashing. ui.prompt_int()
    and ui.prompt_decimal() already do. Try typing "abc" into every single one.
  - Money is Decimal throughout, never float. Grep the codebase for "float(" -- there
    should be no hits.
  - Empty required fields are rejected before hitting the database.
  - FIELD LENGTHS ARE VALIDATED AGAINST THE SCHEMA. Every ui.prompt() that feeds a
    VARCHAR column needs max_length set. The widths are listed under RULE 7 above. A
    database truncation error is not a user experience.
  - Ctrl+C exits cleanly rather than dumping a KeyboardInterrupt traceback.
  - A dead database connection produces "is your Postgres running?" rather than a psycopg
    traceback. main.py's SELECT 1 check covers startup; check what happens if Postgres
    dies MID-SESSION.
  - Every feature module raises an AppError subclass rather than letting a raw psycopg
    exception escape. Go through each module and check.

HOW TO TEST IT
Sit down with the app and genuinely try to break it. Type letters into number prompts,
negative amounts, empty strings, 300-character addresses, auction ids that do not exist,
ids that are negative, ids that are zero. Anything that produces a traceback is a bug.

DONE WHEN
A deliberately hostile user cannot crash the client.


::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

ISSUE 19 -- FINAL REPORT AND DOCUMENTATION
===========================================

Labels: docs
Assignee: everybody
DEPENDS ON: #17 for the numbers

WHAT IT IS
Worth 10%. Start it early. Everyone who leaves it to the last day loses points on it.

WHAT GOES IN IT
  - A description of the implementation and the architecture. docs/overview.md and
    docs/architecture.md already exist and most of this can be lifted from them.
  - The physical design section: which indexes, why, and the before-and-after
    measurements from #17.
  - DOCUMENTED ASSUMPTIONS AND LIMITATIONS. We have four real ones, and each already has
    its reasoning written down somewhere in the code:
      - Passwords are stored in PLAIN TEXT, matching the instructor's schema.
      - The role-change constraint from #14 -- see the RoleChangeBlocked docstring in
        src/errors.py, which was written to be lifted straight into the report.
      - The sequences we added in sql/extensions.sql, as a documented schema extension.
        The header comment in that file was also written for this purpose. Spec section
        2.3 permits documented extensions and section 3 gives extra credit for
        meaningful ones.
      - Auctions have no start or end time anywhere in the schema, so they close only
        when the seller closes them.
    Also worth listing: payment_status Pending and Failed exist in the schema but our
    application only ever writes Completed, because we do not simulate a payment
    processor.
  - Any dataset modifications. Spec section 2.3 REQUIRES these be reported. That means
    both sql/seed.sql and the bulk data from #21.
  - PER-MEMBER TASK AND CONTRIBUTION BREAKDOWN. Spec section 4 requires this explicitly.
    This is why every issue has an assignee and every PR says "Closes #N" -- that git
    history IS this section. Run "git log --author=..." per person to generate it.
  - Screenshots of the client in action.

DONE WHEN
The report is complete and submitted with the source.


::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

ISSUE 20 -- DEMO PREPARATION
=============================

Labels: docs
Assignee: everybody
DEPENDS ON: the whole feature set

WHAT IT IS
Spec section 2.3: demo slots are first-come, first-served. The demo can run anywhere --
this was confirmed with the professor.

TASKS
  - CLAIM A SLOT AS SOON AS THEY ARE RELEASED.
  - Write a demo script walking ONE item end to end:
      register -> promote to Seller -> list an item -> start the auction -> log in as a
      buyer -> bid -> log back in as the seller -> close the auction -> log in as the
      winner -> pay -> log back in as the seller -> ship -> log in as an admin -> show
      the reports.
    Note that this path needs newbie1 or a freshly registered account for the promote
    step, because #14 refuses to promote anyone who already has bids.
  - Reset to a known state before the walkthrough. Run scripts/load_db.py so the demo
    does not depend on whatever junk accumulated during testing. REMEMBER THAT WIPES
    EVERYTHING, so do it before the demo, not during.
  - Rehearse ON THE SERVER, exactly as it will be run, INCLUDING starting the Postgres
    instance first with cs166_db_start. The instance is a user process, not a service --
    it dies on reboot. Assume it will be down when you sit down to demo.
  - Have answers ready for the obvious questions:
      - Why these indexes? (issue #17)
      - How are concurrent bids handled? (SELECT ... FOR UPDATE, issue #7)
      - What does the role constraint mean and why do you refuse? (issue #14)
      - Why is current_highest_bid denormalized and how do you keep it correct?
      - Why plain-text passwords?

DONE WHEN
The walkthrough runs start to finish without improvisation.


::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

ISSUE 21 -- BULK DATASET FOR THE TUNING MEASUREMENTS
====================================================

Labels: sql, tuning
Assignee: whoever finishes their feature issues first
BLOCKS: #17

WHAT IT IS
This work was previously buried inside the notes on issues #1 and #17, which meant nobody
owned it and it was not on the board. It is on Jorge's critical path, so it is its own
issue now.

sql/seed.sql is the DEVELOPMENT dataset -- about 30 rows, deliberately tiny and readable,
written so every feature has something to work against. It is NOT big enough for issue
#17. On 30 rows Postgres sequential-scans everything and an index measurement is
meaningless noise.

WHAT TO BUILD
A second SQL file -- sql/bulk_seed.sql -- that produces the SAME SHAPE of data at
volume. Tens of thousands of bids, not twenty.

  - DO NOT EDIT sql/seed.sql. Keep the small readable one for development and demos. This
    is a separate file that is run instead of it when measuring.
  - Keep the predictable logins. admin1, seller1, seller2, buyer1, buyer2, buyer3 and
    newbie1 must still exist with the password pass123, and the seven auction states
    described in RULE 8 must still exist, so every feature and every test keeps working
    against the bulk data. Add volume AROUND them, do not replace them.
  - generate_series() is the right tool. PostgreSQL 10 has it. Something like:

        INSERT INTO item (item_name, category, starting_price, seller_login)
        SELECT 'Item ' || g, ...
        FROM generate_series(1, 5000) AS g

    Note this INSERT omits item_id, so the sequences fill it in -- which means unlike
    seed.sql, this file does NOT need a setval block at the end.
  - Randomise the category, price and seller across a realistic spread, so GROUP BY
    reports have many groups and the planner has real selectivity to work with. A
    category that appears on every single row teaches the planner nothing.
  - Every bid must still clear its item's starting_price, and every auction's
    current_highest_bid must still match its highest bid row. The whole application
    assumes that invariant. Generate the bids first, then UPDATE the auctions from them
    in one statement rather than trying to keep them in step row by row.
  - Run ANALYZE at the end of the file.

WIRING IT UP
scripts/load_db.py runs a fixed list of files. Either add a flag to it, or just run the
bulk file by hand with cs166_psql -d jcarb044_DB -f sql/bulk_seed.sql after a normal
load. The hand-run version is fine and is less code -- decide with Jorge.

FOR THE REPORT
Spec section 2.3 requires dataset modifications be reported. Write down how many rows of
each kind, how they were generated, and why -- that paragraph belongs in issue #19.

DONE WHEN
sql/bulk_seed.sql is committed, it loads without error, the invariants above hold, and
issue #17 has enough data that EXPLAIN ANALYZE shows a real difference.
