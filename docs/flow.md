# Flow of the project

Read this to understand how the pieces fit together before you write code. It covers two things: the order the project was **built**, and the order the code actually **runs**.

Setup instructions are in the [README](../README.md). The file-by-file map is in [overview.md](overview.md). The *why* behind the decisions is in [architecture.md](architecture.md). (honestly the README.md and this file are the most important, other two are a bunch of AI slop tbh)

---

## Getting it running

1. SSH into the server.
2. Start the database if it is down — check with `cs166_db_status`, start with `cs166_db_start`.
3. Run `uv run scripts/load_db.py`.
   - That runs the SQL files in order: `schema.sql` (the tables), `extensions.sql` (so far just the sequences), `seed.sql` (the starter data), and `indexes.sql` (empty, so it gets skipped).
   - **Every run of this wipes the database and starts from that initial state.** So run it once, not every session.
4. Run `uv run main.py`. The database has data now, so you can log in as any of the users in `seed.sql` and browse as whoever you want.

Every login in the seed data uses the password `pass123`: `admin1`, `seller1`, `seller2`, `buyer1`, `buyer2`, `buyer3`, `newbie1`.

**Daily routine after the first time** is just: ssh in → `cs166_db_status` → `git pull` → `uv run main.py`.

---

## The commands

Everything below runs **on the server**, from `~/cs166_ebay_project`.

### Every session

```bash
ssh <your-netid>@cs166.cs.ucr.edu     # log in to the server
cs166_db_status                        # is your Postgres running?
cs166_db_start                         # start it if it is not
cd ~/cs166_ebay_project
git pull                               # get everyone else's work
uv run main.py                         # run the application
```

### The application and the scripts

```bash
uv run main.py                         # the application itself

uv run scripts/ui_demo.py              # preview the interface, no database needed
uv run scripts/ui_demo.py --all        # every section in order
uv run scripts/ui_demo.py --static     # only the sections that need no typing
```

### Building the database

**`load_db.py` is destructive — it drops all six tables and reloads them.** Everything you created by hand is gone. That is the point: it is how you get back to a clean state.

```bash
uv run scripts/load_db.py              # asks you to type yes first
uv run scripts/load_db.py --dry-run    # show the plan, change nothing
uv run scripts/load_db.py --yes        # skip the confirmation
```

### Talking to the database directly

Plain `psql` does not work here — it looks for a socket in the wrong place. Use the wrapper:

```bash
cs166_psql -d <your-netid>_DB                        # open a SQL session
cs166_psql -d <your-netid>_DB -c '\dt'               # list the tables
cs166_psql -d <your-netid>_DB -c 'SELECT * FROM users;'
cs166_psql -d <your-netid>_DB -f sql/seed.sql        # run one SQL file
cs166_psql -d postgres -l                            # list your databases
```

Inside a `cs166_psql` session: `\dt` lists tables, `\d users` describes one, `\q` quits.

### Packages

```bash
uv sync                                # install/refresh the venv from uv.lock
uv add <package>                       # add a dependency
```

Never use `pip`, and never hand-edit `pyproject.toml`.

### Git

```bash
git checkout main
git pull                               # start from current main, not something stale
git checkout -b feat/thing             # your feature branch

# ...edit and run...

git commit -am "implement thing"
git push -u origin feat/thing          # then open the PR on GitHub
```

After it merges:

```bash
git checkout main
git pull
git branch -d feat/thing               # delete your local branch
git fetch --prune                      # clean up remote-tracking refs
```

Put `Closes #N` in the PR description. §4 of the spec wants each member's contributions documented, and the issue history is how we prove it.

---

# Part 1 — Flow of construction

The order the files were built, and what each one is for.

## `db.py`

-

## `extensions.sql`

- This is a great way of showing the use of sequencing. Everyone should read and understand this file.
- **Consideration:** `users` does not have any sequencing, so an open question is how we make account creation unique so logins do not collide. Maybe add some sort of indexing here for fast retrieval.
- **Consideration:** we reset each sequence past the seeded data at the end of `seed.sql`. Maybe do this instead — the cleanest alternative is for `seed.sql` to omit the id columns too and let these sequences number the seed rows as well, which sidesteps the problem entirely.

## `load_db.py`

- This file is primarily for loading the database. We added the ability to pass arguments when running the file. It describes the database we are targeting, shows which SQL files have data and which will be running, and finally establishes the connection and runs the queries.

## `errors.py`

- This file is intended to make application restrictions understandable rather than throwing terminal errors. All classes inherit the `AppError` class, which is the overall class used in the menu. Feature modules raise the specific errors, while the menu module catches them.

## `ui.py`

-

## `auth.py`

-

## `menus/__init__.py`

-

## `menus/admin.py`

-

## `menus/buyer.py`

-

## `menus/seller.py`

-

## `seed.sql`

-

---

# Part 2 — Flow of execution

Going to read in the order that makes the most sense.

Keep in mind that `ui.py` gets called by everything inside the `menus` package. These four modules essentially run the menu.

## `main.py`

- Our main function uses the `ui` to print a heading and check if there is a connection to the database. If there is, we import the `menus` module and call the `run` function.

## `menus/__init__.py`

- **`menus.run()`** — the login gate to the application. In here we populate the main menu where we ask for login, register, or quit. If we do not quit, then that takes us to either the login or the register option.

- **`menus.do_login()`** — here we prompt the user for a username and password. The `prompt` function asks for information and ensures required fields are filled and guidelines are followed. In the end we return the string of both login and password, where it is then sent off to get authenticated.

## `auth.py`

- **`auth.login()`** — checks username and password and returns a session on success. Here is where our first SQL query is used. We run a `SELECT` on the `users` table to see if we find a match for the username and password combo. If one is not found, we raise `BadCredentials()`. This will bubble back up to `menus.run()` and hit that `except AppError`. If authentication is achieved, we return the session.

## `menus/__init__.py`

- **`menus.do_register()`** — if instead we took the registration route, this function is called and we use the `prompt` to take in the required information. In the end this function will return the result of the `auth.register()` function, which itself is a `Session` object containing the login and role of the user.

## `auth.py`

- **`auth.register()`** — SQL lives here again. We attempt to `INSERT` into the `users` table. The psycopg `UniqueViolation` error is thrown if that user already exists in the table. That `except` statement raises the `LoginTaken` class, which trickles up and tells the user that the login is already taken. If successful, we return the `Session` object with the user and the role.

## `menus/__init__.py`

- **`menus.run()`** — back in this function, where we take the user input and dispatch the session they belong to. This ultimately populates the menu that belongs to their role through the `run_role_menu()` function.

- **`menus.dispatch()`** — this function will then send a user from the login menu to the menu that fits their role. It grabs the role according to the `session.role` variable. If valid, this calls `run_role_menu()`.

- **`menus.run_role_menu()`** — shows one role's menu and keeps showing it until the user logs out. We create the `options` variable that essentially gives us key/label pairs to display on the UI. The user picks a choice, and according to that choice we call the right function with the session. As always, that is wrapped in a `try`/`except` in case the user does something they are not allowed to do. This is an entire `while` loop, so once the action finishes we come straight back to the menu and show it again. It only exits when the user picks **Log out** or **Quit**.
