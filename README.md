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
  session.py       who is logged in, plus require_role()
  ids.py           primary key generation — nothing in the schema auto-increments
  ui.py            the only module that imports rich

  auth.py          register and log in
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
```

Only `db.py` is implemented today. The rest hold their docstring and nothing else — the map exists so three people can build against it in parallel without colliding.

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

---

## Part 2 — Every session

```bash
ssh <your-netid>@cs166.cs.ucr.edu
cs166_db_status              # start it with cs166_db_start if it is down
cd ~/cs166_ebay_project
git pull
```

That's it. There is no tunnel to open and nothing to leave running in a second terminal.

You do **not** need to stop the database when you are finished. Leaving it running costs nothing and saves you a step next time.

---

## Development workflow

Jorge edits on his own machine and runs on the server; you may do the same or edit directly over SSH. Either way, **git is how code moves** — never copy-paste files onto the server. Pasted files silently diverge from what is committed, and you will eventually spend an hour debugging code that isn't the code you think you are running.

**Your server clone is yours alone.** We each have our own home directory, our own clone, and our own Postgres instance. Nothing is shared, so think of the server as simply a second machine of your own that happens to be the only one that can run the code.

Pick one of the two workflows below. They produce identical history — the difference is only how many machines your code has to travel across before you can run it.

---

### Workflow A — editing on the server (simpler)

You SSH in, edit the files in place (`vim`, `nano`, or VS Code Remote-SSH), and run them right there. This is plain, ordinary git. There is nothing extra to learn.

```bash
# on the server, in ~/cs166_ebay_project
git checkout main
git pull                              # start from current main, not something stale
git checkout -b feat/thing

# ...edit files, then run them...
.venv/bin/python main.py

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

### Workflow B — editing locally, running on the server (what Jorge does)

Jorge edits locally. The catch is that **his machine has no database, so he cannot run anything locally** — the code has to reach the server before it can be tested, and git is the only acceptable way to move it.

This adds two requirements that Workflow A does not have:

1. **You must push before you can test.** Expect throwaway `wip` commits; that is normal and they get squashed later.
2. **The first time you test a new branch on the server you need `git fetch` and `git checkout`, not `git pull`.** `git pull` only updates the branch you are currently standing on. If your server clone is sitting on `main` and you pull, git reports "Already up to date" and your new code is nowhere to be seen — because it is on a branch you have not switched to yet.

Start the branch on your own machine:

```bash
# your machine
git checkout main
git pull
git checkout -b feat/thing

# ...edit files...
git commit -am "wip"
git push -u origin feat/thing
```

Pick the branch up in your server clone — this pair of commands is needed **once per branch**:

```bash
# your server clone
git fetch                    # download the new branch from GitHub
git checkout feat/thing      # switch onto it — this is the step people forget
.venv/bin/python main.py     # now you can actually test
```

From here on, every round trip is a two-command loop, because both clones are already on the same branch:

```bash
# your machine
git commit -am "wip" && git push

# your server clone
git pull && .venv/bin/python main.py
```

Worth adding to your server `~/.bashrc`:

```bash
alias rerun='git pull && .venv/bin/python main.py'
```

Once it works on the server, open the pull request, get a review, and merge. Then return **both** clones to a clean base — remember you have two working copies to keep straight, which is the price of this workflow:

```bash
git checkout main
git pull
```

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

## Troubleshooting

Work top to bottom — the cause is almost never the Python.

| Symptom | Cause | Fix |
|---|---|---|
| `connection refused` | Postgres isn't running | `cs166_db_start` |
| `server closed the connection unexpectedly` | Postgres isn't running | `cs166_db_start` |
| `connection timeout expired` | `.env` points somewhere unreachable | `DB_HOST` must be `localhost`, `DB_PORT` must equal `echo $PGPORT` |
| `database "..." does not exist` | Wrong `DB_NAME` | Check spelling and capitals against `cs166_psql -d postgres -l` |
| `password authentication failed` | Wrong `DB_USER` | Should be your netid |
| `KeyError: 'DB_...'` | A variable is missing from `.env` | All five keys must be present, even if empty |
| `psql: could not connect ... /var/run/postgresql` | Used plain `psql` | Use `cs166_psql` |
| `git push` asks for a password | Remote is still HTTPS | `git remote set-url origin git@github.com:...` |
| `ssh -T git@github.com` hangs | Port 22 blocked | Add the `~/.ssh/config` block from step 1.5 |
| `cannot open display` / askpass error | Git tried a GUI prompt | `unset SSH_ASKPASS` |

Reading the error precisely saves time. A `database does not exist` or `authentication failed` message is actually **good news** — it means you reached Postgres and only the `.env` values are wrong.

---

Two separations we hold to deliberately:

- **Connecting vs. initializing.** `src/db.py` only opens connections and is imported everywhere, so importing it must never be able to drop a table. Anything destructive lives in `scripts/`.
- **Creating the instance vs. creating tables.** Starting the Postgres instance is a manual, documented step (Part 1). Creating tables and loading data is repeatable and scripted.

Schema and data live in `.sql` files, never in Python strings — those files are the source of truth if an instance is lost, and the Python is only a thin runner.

---

## Conventions

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

## Dependencies

- `psycopg[binary]` — Postgres driver
- `rich` — terminal UI
- `python-dotenv` — loads `.env`

---

## Open questions

- What format is the instructor's dataset, and how large? Size determines whether our indexing work shows measurable improvement, and whether the files belong in git or should be gitignored with download instructions.

---

## Team

| Name | NetID | Responsibilities |
|------|-------|------------------|
|      |       |                  |
|      |       |                  |
|      |       |                  |
