"""
The entry point into the interface: login gate and role dispatch.

Shows the opening menu -- log in, register, quit -- and once auth.py hands back a Session, dispatches on its role to buyer.menu(), seller.menu(), or admin.menu(). main.py calls into here and does nothing else.

This is also where the top-level try/except for AppError lives, so a violated business rule prints one red line and returns to the menu instead of killing the program. Sellers and Admins reach the buyer actions too: the spec lists those as available to every user, with the role privileges layered on top.

Three loops are nested here, and it is worth holding them apart in your head:

    run()                  the login gate -- log in, register, or quit
      run_role_menu()      one role's actions, repeating until Log out
        one action         does its work, prints, and returns to the menu above

The role modules export two names and nothing else: TITLE, a string, and ACTIONS, a list of (key, label, function) triples. No while loops, no exception handling, no rendering. That is deliberate for two reasons. Three people own those three files and none of them should have to get control flow right for the interface to behave consistently -- and because the role modules never call back into this one, the imports run in one direction only and there is no circular import to work around.
"""

from .. import auth, ui
from ..errors import AppError

# Safe to import at the top precisely because these three are leaves: they import ui and the feature modules, never this package. Reverse that -- have buyer.py import run_role_menu from here -- and Python would hit a half-built module and fail.
from . import admin, buyer, seller


# The schema's CHECK constraint allows exactly these three, so anything else coming out of the database is a bug rather than a case to handle.
ROLE_MENUS = {
    "Buyer": buyer,
    "Seller": seller,
    "Admin": admin,
}


def run_role_menu(session, title, actions):
    """
    Show one role's menu and keep showing it until the user logs out.

    This is the generic loop every role menu runs on. buyer.py, seller.py, and admin.py each declare a list and let this function do the work, so the three files stay lists of functions rather than three slightly different copies of the same while loop.

    Args:
        session (auth.Session): the logged-in user, passed to every action.
        title (str): heading above the list, e.g. "Buyer menu".
        actions (list): (key, label, function) triples. The function takes the Session and returns nothing -- it prints its own results through ui.

    Returns:
        str: "logout" to go back to the login gate, or "quit" to exit the program. The caller needs to tell those apart, which is why this returns a string rather than nothing.
    """
    while True:
        # ui.menu() wants (key, label) pairs, so drop the function from each triple. The two lists stay in the same order, which is what makes the lookup below correct.
        options = [(key, label) for key, label, _function in actions]

        # Two endings on every menu, added here rather than in each role file so they are always present, always last, and always worded the same.
        options.append(("logout", "Log out"))
        options.append(("quit", "Quit"))

        choice = ui.menu(f"{title}  ({session.login})", options)

        # Both endings leave this loop. Returning the key rather than a bool means run() can tell "back to the login screen" from "close the program".
        if choice in ("logout", "quit"):
            return choice

        # Turn the list into a {key: function} lookup so the chosen key finds its function directly. Built from the same list that drew the menu, so the two can never disagree about what option 4 means.
        by_key = {key: function for key, _label, function in actions}
        function = by_key[choice]

        # The one try/except that protects every action in the entire application. Anything inheriting AppError means the user did something the rules forbid -- a bid too low, an auction already closed -- which is a normal event, not a crash.
        try:
            function(session)

        except AppError as e:
            # Every AppError subclass builds a finished sentence, so str(e) is always safe to print straight to the screen. See errors.py.
            ui.blank()
            ui.error(str(e))

        # Deliberately no bare "except Exception" here. A KeyError or a typo in our SQL is a bug, and swallowing it would hide it -- main.py catches those at the very top and exits, which is the behaviour we want while we are still building.


def dispatch(session):
    """
    Send a logged-in user to the menu for their role.

    Each role module declares TITLE and ACTIONS, and this function feeds them to run_role_menu() above. Looking the module up in a dict rather than writing three ifs means adding a role later is one dictionary entry.

    Returns:
        str: "logout" or "quit", passed straight up from run_role_menu().
    """
    # .get() rather than [] so an unexpected role is a clear message instead of a KeyError traceback. The schema's CHECK makes this near-impossible, but the cost of the guard is one line.
    module = ROLE_MENUS.get(session.role)

    if module is None:
        ui.error(f"Unknown role {session.role!r}. This is a bug -- the schema should not permit it.")
        return "logout"

    return run_role_menu(session, module.TITLE, module.ACTIONS)


def do_login():
    """Ask for credentials and return a Session. Raises BadCredentials if they are wrong."""
    ui.blank()
    ui.heading("Log in")

    # max_length matches users.login VARCHAR(50) in the schema, so an over-long username is caught here with a readable message rather than by the database.
    login = ui.prompt("Username", max_length=50)
    password = ui.prompt_password()

    # No try/except -- run() catches AppError for both this and do_register(), since the two failures are handled identically.
    return auth.login(login, password)


def do_register():
    """Collect the fields users needs, create the account, and return the Session it is already logged in on."""
    ui.blank()
    ui.heading("Register")
    ui.info("New accounts start as Buyers. An Admin can promote you to Seller later.")
    ui.blank()

    # Each max_length is the column width from sql/schema.sql. Keeping them here means a too-long value is rejected before a round trip to the database.
    login = ui.prompt("Choose a username", max_length=50)
    password = ui.prompt_password("Choose a password")
    phone_num = ui.prompt("Phone number", max_length=20)
    address = ui.prompt("Address", max_length=255)

    # favorite_category is the only nullable column on users, so this is the only field that may be left blank. required=False lets an empty answer through, and we turn "" into None because SQL's empty string and SQL's NULL are not the same thing.
    favorite_category = ui.prompt("Favourite category (optional)", required=False, max_length=50)
    favorite_category = favorite_category or None

    return auth.register(login, password, phone_num, address, favorite_category)


def run():
    """
    The login gate. Runs until the user quits.

    This is the outermost of the three loops and the only function main.py calls. It owns exactly one piece of state -- whether someone is logged in -- and hands everything else to dispatch().
    """
    while True:
        choice = ui.menu(
            "Online Auction and Bidding System",
            [
                ("login", "Log in"),
                ("register", "Create an account"),
                ("quit", "Quit"),
            ],
        )

        if choice == "quit":
            return

        # The second of the two exception levels. Registration and login are the only things that can fail before a Session exists, and both failures mean the same thing here: say what went wrong and show the gate again.
        try:
            if choice == "login":
                session = do_login()
            else:
                session = do_register()

        except AppError as e:
            ui.blank()
            ui.error(str(e))
            # Back to the top of the while loop, which redraws the gate. Without this the code below would run with no session.
            continue

        ui.blank()
        ui.success(f"Signed in as {session.login} ({session.role}).")

        # Blocks here for as long as the person is logged in. Comes back only when they choose Log out or Quit.
        outcome = dispatch(session)

        if outcome == "quit":
            return

        ui.blank()
        ui.info("Logged out.")
