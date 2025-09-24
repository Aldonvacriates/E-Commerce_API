# E-Commerce API

Flask-based REST API for managing the core entities of a minimal e-commerce platform. It exposes CRUD endpoints for users and products, plus order management with user-product associations.

## Features
- CRUD endpoints for `users`, including email uniqueness validation.
- CRUD endpoints for `products`, including price validation and duplicate prevention in orders.
- Order workflows: create orders, attach or remove products, list orders for a user, and inspect products within an order.
- `/init-db` bootstrap endpoint to build the schema quickly in a new environment.

## Tech stack
- Python 3.11+
- Flask + Flask-REST style routing
- SQLAlchemy ORM with Marshmallow serialization
- MySQL (via `mysqlconnector` driver)

## Requirements
- Python and pip installed locally
- MySQL server with credentials that match the connection string in `app.py`
- Optional: a virtual environment tool such as `venv`

## Getting started
1. (Optional) Create and activate a virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
3. Ensure a MySQL database named `ecommerce_api` exists and the configured user has full access. Update `app.py` if you use different credentials or host information.
4. Initialize the schema by either:
   - Sending a POST request to `http://localhost:5000/init-db`, or
   - Running the app once to let the `db.create_all()` call execute inside the `__main__` block.
5. Start the development server:
   ```powershell
   python app.py
   ```

The app runs on `http://localhost:5000` in debug mode by default.

## Key endpoints
| Method | Path | Description |
| --- | --- | --- |
| GET | `/users` | List users |
| GET | `/users/<id>` | Retrieve a single user |
| POST | `/users` | Create a user |
| PUT | `/users/<id>` | Update a user |
| DELETE | `/users/<id>` | Remove a user |
| GET | `/products` | List products |
| GET | `/products/<id>` | Retrieve a single product |
| POST | `/products` | Create a product |
| PUT | `/products/<id>` | Update a product |
| DELETE | `/products/<id>` | Remove a product |
| POST | `/orders` | Create a new order for a user |
| PUT | `/orders/<order_id>/add_product/<product_id>` | Attach a product to an order |
| DELETE | `/orders/<order_id>/remove_product/<product_id>` | Remove a product from an order |
| GET | `/orders/user/<user_id>` | List orders for a user |
| GET | `/orders/<order_id>` | Inspect an order |
| GET | `/orders/<order_id>/products` | List products linked to an order |
| POST | `/init-db` | Create tables in the configured database |

## Example: create an order
```bash
curl -X POST http://localhost:5000/orders \
  -H "Content-Type: application/json" \
  -d '{
        "user_id": 1,
        "order_date": "2025-09-23T12:00:00",
        "product_ids": [1, 2]
      }'
```

## Troubleshooting
- If you see MySQL connection errors, confirm that the `mysql+mysqlconnector://root:Lolita1!@localhost/ecommerce_api` URI matches your local setup. Update it or load it from environment variables if needed.
- The `/init-db` endpoint is idempotent, but database schema changes require migrations. Consider introducing Flask-Migrate for production-grade workflows.

## Next steps
- Add authentication/authorization before deploying publicly.
- Expand automated testing to cover critical endpoints.
- Externalize secrets (database credentials) and configuration into environment variables or a `.env` file.