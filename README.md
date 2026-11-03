# Campus Bookshop

A small microservices web application used in the COM3033 labs.

| Service | Port | Responsibility |
|---|---|---|
| catalogue | 5001 | Books, prices and stock levels (own SQLite database) |
| orders | 5002 | Customer orders; asks the catalogue about stock (own SQLite database) |
| gateway | 5000 | Single entry point; serves the shop web page and forwards `/api/...` requests |

## Run everything on one machine

```bash
docker compose up -d --build
```

Then open http://localhost:5000 in a browser.

Stop it with `docker compose down`. Add `-v` to delete the data as well.

## Configuration

Each service reads its configuration from environment variables, with local defaults:

| Variable | Used by | Default |
|---|---|---|
| `PORT` | all | 5001 / 5002 / 5000 |
| `DB_PATH` | catalogue, orders | `catalogue.db` / `orders.db` |
| `CATALOGUE_URL` | orders, gateway | `http://localhost:5001` |
| `ORDERS_URL` | gateway | `http://localhost:5002` |
