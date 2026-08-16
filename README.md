# Online Auction and Bidding System

CS166 Project — Phase 3. PostgreSQL backend with a Python terminal client.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
git clone <repo-url>
cd <repo-name>
uv sync
cp .env.example .env
```

Then fill in your own values in `.env`. It is gitignored — never commit it.

## Database

The app connects to `DB_HOST:DB_PORT` from `.env`. Two options, same code.

### Option A — School server (over SSH tunnel)

Our Postgres instances live on the school server. Each of us has our own instance;
it stays running after you disconnect, so remember to stop it when you're done.

Start your instance (only if it isn't already running):

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

The app connects to localhost — SSH forwards it to the server.

### Option B — Local Postgres

TBD

## Project structure

```
sql/
  schema.sql      table definitions (provided by instructor)
  indexes.sql     our physical design work
  seed.sql        sample data
src/              application code
scripts/
  load.sh         rebuild the database
.env.example      copy to .env and fill in
```

## Running

```bash
uv run python src/main.py
```

## Dependencies

- `psycopg[binary]` — Postgres driver (psycopg 3, not psycopg2)
- `rich` — terminal UI
- `python-dotenv` — reads `.env`

Add with `uv add <package>`.

## Workflow

Feature branches, PRs into `main`. No direct pushes to `main`.

## Open questions

- Is a dataset provided by the instructor, and in what format? This determines
  whether `seed.sql` is ours or theirs, and dataset size affects whether our
  indexing work shows measurable improvement.

## Team

| Name | NetID | Responsibilities |
|------|-------|------------------|
|      |       |                  |
|      |       |                  |
|      |       |                  |