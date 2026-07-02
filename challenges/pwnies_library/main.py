"""
The public website (served at "/") only ever calls a handful of GraphQL
queries: `books`, `book(id)`, `authors` and `search(term)`.

There is, however, one more query in the schema that the frontend never
touches. It is simply not referenced anywhere in the UI. A player who runs a GraphQL *introspection*
query against /graphql will discover it and can then call it directly.
"""

import base64
from pathlib import Path
from typing import List, Optional

import strawberry
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from strawberry.fastapi import GraphQLRouter

BASE_DIR = Path(__file__).resolve().parent

# The flag lives OUTSIDE the public /static mount, so it can only be obtained
# through the (introspection-discovered) forbiddenBook query below — never by
# guessing a URL.
FLAG_IMAGE = BASE_DIR / "secret" / "flag.png"


def _flag_data_uri() -> str:
    """Read the flag image and return it as a base64 PNG data URI."""
    data = base64.b64encode(FLAG_IMAGE.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{data}"


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #


@strawberry.type
class Author:
    id: int
    name: str


@strawberry.type
class Book:
    id: int
    title: str
    author: str
    # URL of the cover image. Served from /static/covers/<id>.png
    # (populated automatically below, after the list is defined).
    image: str = ""


_AUTHORS = [
    Author(id=1, name="Torben Ægidius Mogensen"),
    Author(id=2, name="Manul Laphroaig"),
    Author(id=3, name="O RLY"),
]

_BOOKS = [
    Book(id=1, title="Introduction to compiler design", author="Torben Ægidius Mogensen"),
    Book(id=2, title="PoC or GTFO", author="Manul Laphroaig"),
    Book(id=3, title="Getting an Arduino LED to Blink", author="O RLY"),
    Book(id=4, title="Hoping Nobody Hacks You", author="O RLY"),
    Book(id=5, title="Memorizing Six Git Commands", author="O RLY"),
    Book(id=6, title="Parsing HTML Using Regular Expressions", author="O RLY"),
    Book(id=7, title="Pretending to Know About Stuff", author="O RLY"),
    Book(id=8, title="Coping with SAAS Addiction", author="O RLY"),
    Book(id=9, title="My Code is Cross-Browser Compatible", author="O RLY"),
    Book(id=10, title="'); DROP TABLE animals;--", author="O RLY"),
    Book(id=11, title="Good Enough to Ship", author="O RLY"),
    Book(id=12, title="The Guy Who Wrote This Is Gone", author="O RLY"),
    Book(id=13, title="JPEG compression", author="O RLY"),
    Book(id=14, title="Resolving Broken Dependencies", author="O RLY"),
    Book(id=15, title="Changing Stuff and Seeing What Happens", author="O RLY"),
    Book(id=16, title="Coding on the Weekend", author="O RLY"),
]

# Give every book a cover URL. Drop the matching images into
# static/covers/<id>.png ; the frontend falls back to a placeholder if missing.
for _b in _BOOKS:
    _b.image = f"/static/covers/{_b.id}.png"


# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #


@strawberry.type
class Query:
    @strawberry.field(description="List every book in the store.")
    def books(self) -> List[Book]:
        return _BOOKS

    @strawberry.field(description="Fetch a single book by its id.")
    def book(self, id: int) -> Optional[Book]:
        return next((b for b in _BOOKS if b.id == id), None)

    @strawberry.field(description="List every author.")
    def authors(self) -> List[Author]:
        return _AUTHORS

    @strawberry.field(description="Search books by a term in the title.")
    def search(self, term: str) -> List[Book]:
        term = term.lower()
        return [b for b in _BOOKS if term in b.title.lower()]

    # ---- Hidden API: never called by the frontend ----------------------- #
    # It is fully reachable; you just have to *know it exists*.
    # Introspection (`__schema { queryType { fields { name } } }`) reveals it.

    @strawberry.field(description="Pwnies members only. Returns the forbidden book")
    def forbidden_book(self) -> str:
        return _flag_data_uri()


schema = strawberry.Schema(Query)
graphql_app = GraphQLRouter(schema, graphql_ide=None)

app = FastAPI(title="GraphQL Bookstore")
app.include_router(graphql_app, prefix="/graphql")

# Static assets (book cover images live under static/covers/).
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


# --------------------------------------------------------------------------- #
# The "website" — only ever uses the public queries. Markup lives in index.html.
# --------------------------------------------------------------------------- #


@app.get("/")
def index() -> FileResponse:
    return FileResponse(BASE_DIR / "index.html")
