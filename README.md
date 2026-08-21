# Online Auction and Bidding System

CS166 Project — Phase 3. PostgreSQL backend with a Python terminal client.

**Everything runs on the UCR CS server.** There is no local database and no SSH tunnel. You may edit code on your own machine if you prefer, but the application and Postgres both live on the server, and that is where the code is run and demoed.

---

## Start here — the documentation

Four documents, each with a distinct job. Read them in this order.

| File | What it is |
|---|---|
| **[docs/overview.md](docs/overview.md)** | **Read this first.** A guided tour of `src/` — what every module is responsible for, what it may import, and how one user action travels from keystroke to database and back. Half an hour here will save you a day of reading files one by one. |
| [docs/architecture.md](docs/architecture.md) | Why the system is shaped the way it is. Worth reading before you write anything nontrivial — especially §1, which explains four properties of the schema that reading `sql/schema.sql` will not make obvious, and each of which will bite you if you do not know about it. It is also where the final report's design and limitations sections are already half-drafted. |
| [docs/issues.md](docs/issues.md) | The full task breakdown. **Source of truth for what gets built and in what order** — every GitHub issue came from here. Check it before starting anything, so two of us do not build the same feature twice. |
| [docs/CS166-Project.pdf](docs/CS166-Project.pdf) | The instructor's specification. Every requirement traces back to §6. |

This README covers setup and workflow only. It deliberately does not explain the code — that is `overview.md`'s job, and duplicating it here guarantees the two drift apart.

### Every file explains itself

Each module in `src/` opens with a docstring covering what it is for, which tables it touches, which modules it calls, and which call it. If you are already looking at a file, that paragraph is faster than any document. If you are trying to work out which file to open, start with `overview.md`.

```
src/
  db.py            connections only — reads .env, hands out psycopg connections
  errors.py        the exception vocabulary every module raises from
  ui.py            the only module that imports rich

  auth.py          register, log in, the Session object, and require_role()
  users.py         profiles, admin user management, role changes
  items.py         listings
  auctions.py      browse, search, detail, ending an auction
  bids.py          placing bids and bid history
  payments.py      paying for a won auction
  shipments.py     delivery after payment

  menus/
    __init__.py    login gate, then dispatch on role
    buyer.py
    seller.py
    admin.py

sql/
  schema.sql       the instructor's schema, verbatim — never edited
  extensions.sql   ours: sequences, so the ids generate themselves
  seed.sql         ours: sample data (written last, currently empty)
  indexes.sql      ours: tuning indexes (written last, currently empty)

scripts/
  load_db.py       run by hand — builds the database from the files above (destructive)
  smoke.py         run by hand — checks the code works against a live database
  ui_demo.py       run by hand — previews the interface, needs no database
```

## Project status

Current as of 2026-08-21. See [Important notes](#important-notes) at the bottom for the two decisions that affect how you write code.

**Built, tested, and on `main`:**

| File | State |
|---|---|
| `src/db.py` | Connections only. Reads `.env`, hands out psycopg connections. |
| `src/errors.py` | The 15 exception classes every feature module raises from. |
| `src/ui.py` | The full terminal helper set — messages, headings, tables, pagination, menus, prompts, confirmations. The only module that imports `rich`. |
| `src/auth.py` | `Session`, `require_role()`, `register()`, `login()`. New accounts are always Buyer, straight from the schema default. |
| `src/menus/__init__.py` | The login gate, the role dispatch, and the one generic menu loop the three role files run on. |
| `src/menus/{buyer,seller,admin}.py` | Menu structure complete — every action is listed and reachable. The action *bodies* are placeholders naming the issue that will replace them. |
| `main.py` | Checks the database is reachable, then hands off to `menus.run()`. |
| `scripts/load_db.py` | Builds the database from the `sql/` files in one transaction. See [1.10](#110--build-the-database). |
| `scripts/smoke.py` | Checks the code against a live database — 13 checks today, one section per module as they land. See [1.11](#111--verify-everything-works). |
| `scripts/ui_demo.py` | Previews the whole interface with fake data and no database — `--all` runs every section, `--static` skips the interactive ones. |
| `sql/schema.sql`, `sql/extensions.sql` | Both loaded on the server. Six tables and five sequences exist; the tables are still empty. |

**The application runs.** `.venv/bin/python main.py` gets you: register → log in → your role's menu → log out → quit. Every action is on the menu; the ones whose feature module isn't written yet say so and name their issue.

**Not started.** These files hold a docstring and nothing else: `users.py`, `items.py`, `auctions.py`, `bids.py`, `payments.py`, `shipments.py`. `sql/seed.sql` and `sql/indexes.sql` are empty on purpose — both are written last.

**Next up:** the features themselves, issues #3 onward. Each one is a vertical slice — a feature module plus the menu action that calls it — so three people can take three slices without touching the same file.

**How to add a feature.** Write the function in its feature module, then replace the placeholder body in `menus/buyer.py`, `seller.py`, or `admin.py`. You never touch `menus/__init__.py`: it owns the loop, the dispatch, and the `except AppError`, and the role files are nothing but a `TITLE` and a list of `(key, label, function)`.

The map above exists so three people can build against it in parallel without colliding. Claim your work in [docs/issues.md](docs/issues.md) before you start on it.

---

## Part 1 — One-time server setup

Do this section once. After it is done, see [Part 2](#part-2--every-session) for the short daily routine.

Every command in Part 1 is run **on the server**, unless a step says otherwise.

### 1.1 — Log in to the server

```bash
ssh <your-netid>@cs166.cs.ucr.edu
```

`cs166.cs.ucr.edu` and `xe-10.cs.ucr.edu` are the same physical machine — your shell prompt will say `xe-10`. Don't be thrown by that.

**Why:** All the work happens here, so every step below assumes you are logged in.

### 1.2 — Start your Postgres instance

Each of us runs our **own private** Postgres instance. Check whether yours is up, and start it if not:

```bash
cs166_db_status     # is it running?
cs166_db_start      # start it if not
```

**Why this matters more than it looks:** Your Postgres is a plain user process that you launched — not a system service. Nothing restarts it for you. It dies when the server reboots, and the department may reap idle user processes. So `cs166_db_status` is the first thing to check whenever the application cannot connect. Roughly 90% of "my code is broken" turns out to be "my database isn't running."

Useful facts about your instance:

- Its port is in `$PGPORT` (Jorge's is `40875`; yours will differ — run `echo $PGPORT`).
- It listens on `127.0.0.1` only, so it is unreachable from outside the server. That is a feature, and it is why we are not bothering with tunnels.
- Its data directory is `$PGDATA`, under `/extra/<your-netid>/cs166`.
- Plain `psql` will **not** work — it looks for a socket in `/var/run/postgresql`, but our instances put theirs in `/extra/<netid>/cs166/sockets`. Use the `cs166_psql` wrapper instead, which passes the right paths.

### 1.3 — Find or create your database

An "instance" (the running server process) is not the same thing as a "database" (a named collection of tables inside it). One instance holds many databases. List yours:

```bash
cs166_psql -d postgres -l
```

You are looking for a project database — Jorge's is `jcarb044_DB`. If you don't have one, create it:

```bash
cs166_createdb <your-netid>_DB
```

**Why:** The name you find here goes into `DB_NAME` in `.env` later. Copy it **exactly**, including capital letters — `jcarb044_DB` was created with quotes, so the capital `DB` is literal and `jcarb044_db` will not match.

### 1.4 — Install uv

[uv](https://docs.astral.sh/uv/) is our package manager. Install it into your own home directory:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
~/.local/bin/uv python install 3.14
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
uv --version
```

**Why uv and not pip:** uv installs from a lockfile (`uv.lock`), so every one of us gets byte-identical package versions. No "works on my machine." It also needs no root access and downloads its own Python 3.14 rather than depending on whatever the server has — the server's system Python is old and we don't control it.

**Why the PATH line:** The installer puts `uv` in `~/.local/bin`, which isn't searched by default. Adding it to `.bashrc` means plain `uv` works in every future shell instead of you typing the full path forever.

### 1.5 — Set up GitHub access over SSH

This is the fiddliest part. Three separate problems stack on top of each other, so it is worth understanding each one.

**Problem 1: GitHub no longer accepts passwords for git.** Pushing over an `https://` remote fails with `Password authentication is not supported for Git operations`. The fix is either a personal access token or an SSH key. We use SSH keys — nothing to paste, nothing to expire.

Generate a key pair on the server (press Enter at all three prompts to accept defaults and skip the passphrase):

```bash
ssh-keygen -t ed25519 -C "cs166-server"
cat ~/.ssh/id_ed25519.pub
```

This creates two files. `~/.ssh/id_ed25519` is the **private** key — it stays on the server forever and you never share it. `~/.ssh/id_ed25519.pub` is the **public** key — it is safe to hand out, and it is the one `cat` just printed.

Copy that whole printed line (it starts with `ssh-ed25519 AAAA...`) and add it to GitHub: avatar menu → **Settings** → **SSH and GPG keys** → **New SSH key** → give it a title like `cs166 school server`, leave type as *Authentication Key*, paste, **Add SSH key**.

**Why key pairs work:** GitHub keeps your public key. When you push, your machine proves it holds the matching private key without ever transmitting it. Authentication by math instead of by secret-you-type.

**Problem 2: the school blocks outbound port 22.** Ports are numbered doors; SSH normally uses 22. Campus networks routinely block outbound 22 so a compromised machine can't be used to attack other servers. The symptom is that `ssh -T git@github.com` just hangs until you Ctrl+C. GitHub runs a second SSH endpoint on port 443 — the port HTTPS uses, which no firewall blocks — so we point at that instead:

```bash
mkdir -p ~/.ssh
printf 'Host github.com\n    Hostname ssh.github.com\n    Port 443\n    User git\n' >> ~/.ssh/config
chmod 600 ~/.ssh/config
```

Same SSH protocol, same key, different door. Now test it:

```bash
ssh -T git@github.com
```

Expect `Hi <your-username>! You've successfully authenticated, but GitHub does not provide shell access.` That message is success — GitHub never gives you a shell. The first run will ask you to confirm a host fingerprint; type `yes`.

**Problem 3: a GUI password popup on a machine with no GUI.** Git may try to launch `gnome-ssh-askpass` and fail with `cannot open display`. Prevent it:

```bash
echo 'unset SSH_ASKPASS' >> ~/.bashrc
```

### 1.6 — Clone the repository

Clone into your **home directory**, not `/extra`:

```bash
cd ~
git clone git@github.com:jorgencarbajal/cs166_ebay_project.git
cd cs166_ebay_project
```

**Why home and not `/extra`:** `/extra` sits on the root filesystem, which is **100% full** with only a few GB left and shared with every other user. Home is on a separate 3.4 TB volume with plenty of room. Note that your `$PGDATA` is unavoidably on the full disk — if Postgres ever starts throwing write errors, that is why.

**Why the `git@github.com:` form and not `https://`:** the SSH URL is what makes git use the key you just set up. If you cloned with HTTPS by mistake, fix it without re-cloning:

```bash
git remote set-url origin git@github.com:jorgencarbajal/cs166_ebay_project.git
git remote -v      # confirm both lines now start with git@github.com
```

Set your identity so commits are attributed to you:

```bash
git config --global user.name "Your Name"
git config --global user.email "your-github-email@example.com"
```

Use the email attached to your GitHub account, otherwise your commits won't link to your profile.

### 1.7 — Install dependencies

```bash
uv sync
```

**What it does:** reads `pyproject.toml` and `uv.lock`, creates `.venv/` inside the project, and installs the exact pinned versions — psycopg 3, python-dotenv, rich, and their dependencies. Running it again is harmless; it just makes the venv match the lockfile.

### 1.8 — Create your `.env`

```bash
cp .env.example .env
```

Then edit `.env` and fill in your values:

```
DB_HOST=localhost
DB_PORT=<your $PGPORT — run: echo $PGPORT>
DB_NAME=<your database from step 1.3, e.g. jcarb044_DB>
DB_USER=<your netid>
DB_PASSWORD=
```

`DB_PASSWORD` is intentionally left empty — the class instances use trust authentication. The variable must still be **present**, because the code reads it directly and will raise `KeyError` if it is missing.

**Why `.env` at all:** every connection setting lives in this one file, and nothing is hardcoded. `.env` is gitignored so it never gets committed — which is what lets us each have different ports and database names while sharing identical code. `.env.example` is the committed template that tells you which settings exist; it holds no real values.

**Why `DB_HOST=localhost` works here:** you are running the application on the same machine as Postgres, so `localhost` really is the database server. No tunnel, no forwarding, no port 5433.

### 1.9 — Verify the connection

```bash
.venv/bin/python -c "from src import db; c = db.get_connection(); print(c.execute('SELECT version()').fetchone()); c.close()"
```

Success looks like:

```
{'version': 'PostgreSQL 10.23 on x86_64-redhat-linux-gnu, ...'}
```

If it fails, see [Troubleshooting](#troubleshooting).

This one deliberately depends on nothing but `db.py`, which is why it is a raw one-liner and not a script — it is the check that still works when everything else is broken. The fuller check comes in [1.11](#111--verify-everything-works), once there are tables to check against.

### 1.10 — Build the database

Your database exists but has no tables in it yet. Create them:

```bash
.venv/bin/python scripts/load_db.py
```

It prints the database it is about to target, lists the files it will run, and asks you to type `yes` before doing anything. Two other flags are available:

```bash
.venv/bin/python scripts/load_db.py --dry-run   # show the plan, touch nothing
.venv/bin/python scripts/load_db.py --yes       # skip the prompt
```

Confirm it worked:

```bash
cs166_psql -d <your-netid>_DB -c '\dt'
```

You should see six tables — `users`, `item`, `auction`, `bid`, `payment`, `shipment`.

**Read this before you run it a second time.** `scripts/load_db.py` is the only destructive file in the project: `sql/schema.sql` opens with six `DROP TABLE ... CASCADE` statements, so re-running it throws away every row you have. That is the point — it is how you get back to a clean database after testing corrupts your data — but it is not something to run casually. It only ever touches those six tables; anything else in your database is left alone.

**Why it is a script and not part of the app:** `src/db.py` is imported by everything and only ever opens connections, so no stray import can drop a table. Everything destructive lives in `scripts/`, which is only ever run by hand.

### 1.11 — Verify everything works

```bash
.venv/bin/python scripts/smoke.py
```

This is the "is my setup actually correct" check. It connects, confirms all six tables and all five sequences exist, then registers a throwaway user, logs in as them, and confirms that a duplicate username, a wrong password, and an unknown username are each refused. Every check prints a green `✓` or a red `✗` with what it expected.

```
·   Target: jcarb044@localhost:40875/jcarb044_DB

───────────────────────── Database and schema ─────────────────────────
✓   Connection opens and Postgres answers
✓   All six tables exist
...
✓   13 checks passed.
```

Two flags:

```bash
.venv/bin/python scripts/smoke.py --list          # what sections exist
.venv/bin/python scripts/smoke.py --only auth     # run just one
```

**It is safe to re-run, and safe to run mid-demo.** It writes exactly one row — a user called `smoke_test_user` — and deletes it both before and after the auth section, so a run that crashed halfway cannot poison the next one. It drops nothing and touches no other data. That is the difference between this and `load_db.py`.

**Run it after every `git pull`.** It grows a section per module as we build them, so it is the fastest way to find out whether someone else's merge broke something of yours. It exits `0` when everything passes and `1` when anything fails.

If a check fails, the message says what it expected. `psycopg.OperationalError` on the very first check almost always means your Postgres instance is down — see [Troubleshooting](#troubleshooting).

---

## Part 2 — Every session

```bash
ssh <your-netid>@cs166.cs.ucr.edu
cs166_db_status                          # start it with cs166_db_start if it is down
cd ~/cs166_ebay_project
git pull
.venv/bin/python scripts/smoke.py        # confirm nothing that landed while you were away is broken
```

That's it. There is no tunnel to open and nothing to leave running in a second terminal.

The `smoke.py` line is optional but cheap — it takes a second and tells you whether the problem you are about to hit is yours or came in with the pull.

---

## Development workflow

Jorge edits on his own machine and runs on the server; you may do the same or edit directly over SSH. Either way, **git is how code moves** — never copy-paste files onto the server. Pasted files silently diverge from what is committed, and you will eventually spend an hour debugging code that isn't the code you think you are running.

**Your server clone is yours alone.** We each have our own home directory, our own clone, and our own Postgres instance. Nothing is shared, so think of the server as simply a second machine of your own that happens to be the only one that can run the code.

---

### Editing on the server (simpler)

You SSH in, edit the files in place (`vim`, `nano`, or VS Code Remote-SSH), and run them right there. This is plain, ordinary git. There is nothing extra to learn.

```bash
# on the server, in ~/cs166_ebay_project
git checkout main
git pull                              # start from current main, not something stale
git checkout -b feat/thing

# ...edit files, then run them...
.venv/bin/python main.py              # the application itself

git commit -am "implement thing"
git push -u origin feat/thing
```

Then open the pull request on GitHub, get a review, merge, and come back to a clean base:

```bash
git checkout main
git pull
```

**Editing and running happen in the same place, so you never push just to test.** You push when the work is actually done.

---

### Cleaning up

Optional, but keeps `git branch -a` readable. GitHub offers a **Delete branch** button after merging, which removes the remote copy; the local ones are yours to remove:

```bash
git branch -d feat/thing     # in each clone you used — one for Workflow A, two for Workflow B
git fetch --prune            # drop remote-tracking refs for branches that are gone
```

### Reading `git branch -a`

```
* main
  remotes/origin/HEAD -> origin/main
  remotes/origin/main
```

`origin/HEAD` is not a branch. It is a pointer recording which branch the remote treats as its default, which is how git knows what you mean if you write `origin` without naming a branch. Real branches are the lines without an arrow.

### Branch rules

Feature branches, pull requests into `main`, no direct pushes to `main`. Squash noisy `wip` commits with `git rebase -i` before opening the PR.

---

### Two separations to keep in mind:

- **Connecting vs. initializing.** `src/db.py` only opens connections and is imported everywhere, so importing it must never be able to drop a table. Anything destructive lives in `scripts/`.
- **Creating the instance vs. creating tables.** Starting the Postgres instance is a manual, documented step (Part 1). Creating tables and loading data is repeatable and scripted.

Schema and data live in `.sql` files, never in Python strings — those files are the source of truth if an instance is lost, and the Python is only a thin runner.

---

## Dependencies

Since the libraries are declared in `pyproject.toml`, all you have to do is `uv sync`. This is a command that syncs all the libraries into your uv environment.  

- `psycopg[binary]` — Postgres driver
- `rich` — terminal UI
- `python-dotenv` — loads `.env`

## Conventions/libraries

- **psycopg 3**, imported as `psycopg` — *not* psycopg2. Row factories, connection strings, and transaction semantics all differ; do not paste psycopg2 snippets.
- **rich** for terminal UI.
- **Python 3.14**, pinned in `.python-version` and `requires-python`.
- Dependencies via `uv add <package>` — never `pip`, never hand-edited.

### Postgres 10.23

The server runs **PostgreSQL 10.23**, released 2017. This is old, and it matters for the physical-design portion of the grade:

- No covering indexes — `CREATE INDEX ... INCLUDE (...)` is PG 11+.
- No `CALL` or stored procedures — functions only.
- None of the PG 11+ planner improvements.

Check syntax against the **PostgreSQL 10** documentation before proposing index or tuning work. Modern tutorials will hand you syntax that errors here.

---

## Important notes

Two decisions that change how you write code. Neither is visible from reading `sql/schema.sql`, and both will cost you an hour if you find them the hard way.

### Primary keys — omit the id and use `RETURNING`

Nothing in the instructor's schema auto-increments; every primary key is a plain `INT`. We fixed that ourselves in `sql/extensions.sql`, which adds one sequence per numeric-PK table and wires it in as the column `DEFAULT` — the same thing `SERIAL` does under the hood. So ids do generate themselves now, but only if you let them.

Practical upshot for every `INSERT` you write: **leave the id column out, and get the new id back with `RETURNING`.**

```sql
INSERT INTO bid (auction_id, buyer_login, bid_amount) VALUES (%s, %s, %s) RETURNING bid_id
```

`users` is the exception — it has no sequence, because its primary key is the `login` string you already have in hand.

### The dataset is ours, and it comes last

**Resolved 2026-08-20:** we generate our own dataset rather than waiting on one from the instructor. It lives in `sql/seed.sql` and is deliberately being written **last**, once the features are built and we know what shape the data needs to be. It needs enough rows for the indexing work in issue #17 to show measurable improvement, and it will use predictable logins (`buyer1`, `seller1`, `admin1`) so nobody has to grep generated rows mid-demo. §2.3 requires dataset choices be reported, so this paragraph goes in the report.

Data you create through the running application persists — `load_db.py` is run once, not once per session.

---

## Team

| Name | NetID | Responsibilities |
|------|-------|------------------|
|      |       |                  |
|      |       |                  |
|      |       |                  |
