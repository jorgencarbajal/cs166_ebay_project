FLOW OF CONSTRUCTION

┌────────────────────────────┬──────────────────────────────┬───────────────────────────────────┐
│           Index            │            Serves            │             Expected              │
├────────────────────────────┼──────────────────────────────┼───────────────────────────────────┤
│ bid(auction_id, bid_amount │ history, active_auctions     │ the big one                       │
│  DESC)                     │ report, every max-bid group  │                                   │
├────────────────────────────┼──────────────────────────────┼───────────────────────────────────┤
│ bid(buyer_login)           │ my bids, top bidders         │ large

db.py

- 

extensions.sql 

- is a great way of showing the use of sequencing, everyone should read and understand this.
- Consideration: User doesnt have any sequencing so an open question to consider is how can we make account creations unique so they dont collide. Maybe add some sort of indexing here for fast retrieval.
- Consideration: Reset each sequence past the seeded data at the end of seed.sql. Maybe do this: The cleanest alternative is for seed.sql to omit the id columns too and let these sequences number the seed rows as well, which sidesteps the problem entirely.

load_db.py

- This file is primarily for loading the db. We added the ability to add arguments when running the file. Describe the database we are targeting and also shows which sql files have data and which will be running. Finally establishes the connections an runs the queries.

errors.py

- This file is intended to make application restrictions understandable rather than throwing terminal errors. All classes inherit the AppError class which is the overall class used in the menu. Feature modules raise the specific errors, while the menu module catches them.


ui.py

- 

auth.py

- 

__init__.py

- 

menu.py

- 

admin.py

- 

buyer.py

- 

seller.py

-

sql/seed.sql

- Here we seed the data. We also have to consider that the sequencing in the extensions file is still sitting at one. The next insert will cause a collision, so we forward the sequence with the setval code at the bottom.

GOING TO READ IN THE ORDER THAT MAKES THE MOST SENSE.

- keep in mind that ui.py gets called by everything inside the menus package. These 4 modules essentially run the menu.

main.py

- Our main function uses the ui to print a heading and check if there is a connection to the database. If there is, we import the menus module and call the run funciton.

src/menus/__init__.py

- menus.run(): The login gate to the application. In here we populate the main menu where we ask for login, register, or quit. If we dont quit then that either takes us to the login or register option.

- menus.do_login(): Here we prompt the user for a username and password. The prompt function asks for information and ensures required fields are filled and guidlines are followed. In the end we return the string of both login and password where it is then sent off to get authenticated.

src/auth.py

*****
- auth.login(): Check username and password and returns a session on success. Here is where our firth sql query is used. We run a select on the users table to see if we find a match for the username password combo. If one is not found we raise BadCredentials(). This will bubble back up to menus.run() and hit that except AppError. If authentication is achieved. We return the session.

src/menus/__init__.py

- menus.do_register(): If instead we took the registration route. This function is called and we use the prompt to take in the required information. In the end this function will return the result of the auth.register() function which itself is a session object containing the login and role of the user.

src/auth.py

*****
- auth.register(): sql lives here again. We attempt to INSERT into the users table. The psycopg uniqueviolation error is thrown if that user already exists in the table. That except statement raises the LoginTaken class which trickles up and tells the user that the login is already taken. If successfull we return the Session object with the user and the role.

src/menus/__init__.py (the packages own module body)

- menus.run(): Back in this function where we take the user input and dispatch the session they belong to. This ultimately populates the menu that belongs to there role through run_role_menu() funciton.

- menus.dispatch(): This function will then send a user from the login menu to the menu that fits their role. It grabs the role according to the session.role variable. If valid, this calls run_role_menu().

- menus.run_role_menu(): Show one roles menu and keep showing it until the user logs out. We create the options variable that essentially gives us key, label pairs to display on the ui. User picks a choice and then according to that choice calles the right function with the session. As always that is wrapped in a try except incase the user does something they are not allowed to do. This is an entire while

- From here the user is given the option to use any of the funcitonality that they have. The first functionality that we added was for the buyer user to be able to browse auctions.

## src/menus/buyer.py

### src/menus/buyer.browse_auctions(): 

- In this file is where we call the function that will then run the query. Ultimately that query call will return the data from the database to display on the UI through this function.

#### src/auctions.py

- auctions.browse(): Here we start by making the connection to the database. After doing so we fetch all the returning rows, store then and return them so the buyers.py file can use the UI to display.

### src/menus/buyer.view_auction():

- Prompt the user to enter an auction id. With that id we call the function `auction.detail()` and `bids.history()`. One function returns the details of the auction and the other returns the bid history of the auction.

#### src/auction.detail():

- Return everything known about one auction, as a single row.

#### src/bid.history():

- Return every bid placed on one auction, highest first.

### src/menus/buyer.browse_auction():

- First call `auctions.browse()` to return all the rows of the current Active auctions. After returning with the rows, we take the rows dict to format it nicely using `ui.page()`.

#### src/auctions.browse():

- Return every Active auction, newest first.

### src/menus/buyer.my_bids():

- Calls `bids.list_for_buyer()` which returns every bid this user has placed. Formats using `ui.page()`.

#### src/bids.list_for_buyer()

- Return every bid this user has placed, newest first, each labelled with how it turned out.

### src/menus/buyer.place_bid():

- First we prompt the user of an auction id and bid amount. This information is then used in the `bids.place()` function.

#### src/bids.place()

- Takes the auction id and amount as parameters and places the bid. First we run a check that ensure we are a buyer, `auth.require_role()`, an exception is thrown if not. Ensure the auction exist, it is active, the seller is not placing a bid on their own item, and the bid amount is higher than the current bid. If all this passes we insert the bid into the bid table, update the auction, and return the `bid_id`, `bid_amount`, and `bid_timestamp` for the ui.

### src/menus/buyer.search_items():

- We populate prompts that asks the user about the details of the item they want to search. We then call the `auction.search()` function that returns auctions based on those filters.

#### src/auctions.search():

- Return auctions matching whichever filters were actually supplied.

## src/menus/admin.py

### src/menus/admin.report_*():

- These 4 functions provide reports for the data living in the database. The functions have a one to one mapping of a function inside the `reports.py` file. Inside that file is where the SQL queries live.

##





















