# Online Auction and Bidding System

CS166 Project — Phase 3. PostgreSQL backend with a Python terminal client.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.14 (see `.python-version`).

```bash
git clone <repo-url>
cd <repo-name>
uv sync
cp .env.example .env
```

`.env.example` is the committed template listing every setting the app needs, with
no real values. Copy it to `.env` and fill in your own — `.env` is gitignored and
must never be committed. All connection settings come from `.env`; nothing is
hardcoded, so switching between the school server and a local Postgres is a
config change, not a code change.

## Database

The app connects to `DB_HOST:DB_PORT` from `.env`. Two options, same code.

### Option A — School server (over SSH tunnel)

We each run our own Postgres instance on the school server, so either of us can
drop and reload without disturbing the other.

Your instance is a process you started, not a system service. It survives
disconnecting, but **not a server reboot** — you have to start it again. Record
the exact start command here the first time you run it:

```bash
ssh <user>@<school-server>
<start command>
exit
```

Open the tunnel in its own terminal and leave it running:

```bash
ssh -L 5433:localhost:<remote-pg-port> <user>@<school-server> -N
```

`.env`:

```
DB_HOST=localhost
DB_PORT=5433
```

The app connects to localhost:5433 — SSH forwards it to Postgres on the server.
Port 5433 is used so the tunnel never collides with a local Postgres on 5432.

Worth adding to your SSH config, so a dead tunnel fails loudly instead of hanging:

```
ServerAliveInterval 60
ServerAliveCountMax 3
ExitOnForwardFailure yes
```

**When a connection fails, check the tunnel and the instance before reading your
code.** An authentication error is good news — it means you reached Postgres.

### Option B — Local Postgres

TBD. Only the `.env` values change.

## Project structure

Split by what a file is, not what it is about: Python you import, SQL you run,
data you load, scripts you invoke.

```
src/              application code (importable) — db.py first
sql/
  schema.sql      table definitions (provided by instructor, verbatim)
  indexes.sql     our physical design work
scripts/          run by hand — e.g. load_db.py
data/             dataset provided by the instructor
docs/             report and design notes
.env.example      template — copy to .env and fill in
```

Creating the cluster (`initdb`) and starting the instance are manual, one-time
steps done on the server over SSH — documented above, not scripted. Creating
tables and loading data is repeatable and belongs in `scripts/`.

## Running

Nothing to run yet. First file is `src/db.py`: it exposes `connect()` for the rest
of the app and doubles as a connection probe — run it directly and it reports the
target it tried and the server version.

## Dependencies

- `psycopg[binary]` — Postgres driver (psycopg 3, not psycopg2)
- `rich` — terminal UI
- `python-dotenv` — reads `.env`

Add with `uv add <package>`.

## Workflow

Feature branches, PRs into `main`. No direct pushes to `main`.

## Open questions

- What format is the instructor's dataset, and how large? Size determines whether
  our indexing work shows measurable improvement, and whether the files belong in
  git or should be gitignored with download instructions.

## Team

| Name | NetID | Responsibilities |
|------|-------|------------------|
|      |       |                  |
|      |       |                  |
|      |       |                  |
