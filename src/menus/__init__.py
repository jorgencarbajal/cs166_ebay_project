"""The entry point into the interface: login gate and role dispatch."""

from .. import auth, ui
from ..errors import AppError

from . import admin, buyer, seller


ROLE_MENUS = {
    "Buyer": buyer,
    "Seller": seller,
    "Admin": admin,
}


def run_role_menu(session, title, actions):
    """
    Show one role's menu and keep showing it until the user logs out.
    Returns str: "logout" to go back to the login gate, or "quit" to exit the program.
    """
    while True:
        options = [(key, label) for key, label, _function in actions]

        options.append(("logout", "Log out"))
        options.append(("quit", "Quit"))

        choice = ui.menu(f"{title}  ({session.login})", options)

        if choice in ("logout", "quit"):
            return choice

        by_key = {key: function for key, _label, function in actions}
        function = by_key[choice]

        try:
            function(session)

        except AppError as e:
            ui.blank()
            ui.error(str(e))


def dispatch(session):
    """
    Send a logged-in user to the menu for their role.
    Returns str: "logout" or "quit", passed straight up from run_role_menu().
    """
    module = ROLE_MENUS.get(session.role)

    if module is None:
        ui.error(f"Unknown role {session.role!r}. This is a bug -- the schema should not permit it.")
        return "logout"

    return run_role_menu(session, module.TITLE, module.ACTIONS)


def do_login():
    """Ask for credentials and return a Session."""
    ui.blank()
    ui.heading("Log in")

    login = ui.prompt("Username", max_length=50)
    password = ui.prompt_password()

    return auth.login(login, password)


def do_register():
    """Collect the fields users needs, create the account, and return the Session it is already logged in on."""
    ui.blank()
    ui.heading("Register")
    ui.info("New accounts start as Buyers. An Admin can promote you to Seller later.")
    ui.blank()

    login = ui.prompt("Choose a username", max_length=50)
    password = ui.prompt_password("Choose a password")
    phone_num = ui.prompt("Phone number", max_length=20)
    address = ui.prompt("Address", max_length=255)

    favorite_category = ui.prompt("Favourite category (optional)", required=False, max_length=50)
    favorite_category = favorite_category or None

    return auth.register(login, password, phone_num, address, favorite_category)


def run():
    """The login gate."""
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

        try:
            if choice == "login":
                session = do_login()
            else:
                session = do_register()

        except AppError as e:
            ui.blank()
            ui.error(str(e))
            continue

        ui.blank()
        ui.success(f"Signed in as {session.login} ({session.role}).")

        outcome = dispatch(session)

        if outcome == "quit":
            return

        ui.blank()
        ui.info("Logged out.")
