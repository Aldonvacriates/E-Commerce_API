from __future__ import annotations
from datetime import datetime
from typing import List

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from marshmallow import validates, ValidationError, fields
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from sqlalchemy import UniqueConstraint

# ──────────────────────────────────────────────────────────────────────────────
# App & DB config
# ──────────────────────────────────────────────────────────────────────────────
app = Flask(__name__)


app.config["SQLALCHEMY_DATABASE_URI"] = (
    "mysql+mysqlconnector://root:Lolita1!@localhost/ecommerce_api"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
ma = Marshmallow(app)

# ──────────────────────────────────────────────────────────────────────────────
# Association (Many↔Many): orders ↔ products
# Using a composite PK prevents duplicates by design.
# ──────────────────────────────────────────────────────────────────────────────
order_product = db.Table(
    "order_product",
    db.Column("order_id", db.Integer, db.ForeignKey("orders.id"), primary_key=True),
    db.Column("product_id", db.Integer, db.ForeignKey("products.id"), primary_key=True),
    # Redundant with composite PK but explicit for clarity:
    UniqueConstraint("order_id", "product_id", name="uix_order_product"),
)

# ──────────────────────────────────────────────────────────────────────────────
# Models
# ──────────────────────────────────────────────────────────────────────────────
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    address = db.Column(db.String(255), nullable=True)
    email = db.Column(db.String(255), unique=True, nullable=False)

    # One-to-Many: user → orders
    orders = db.relationship("Order", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User {self.id} {self.email}>"


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    product_name = db.Column(db.String(255), nullable=False)
    price = db.Column(db.Float, nullable=False)

    # reverse side of many-to-many via secondary in Order
    orders = db.relationship("Order", secondary=order_product, back_populates="products")

    def __repr__(self) -> str:
        return f"<Product {self.id} {self.product_name}>"


class Order(db.Model):
    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    order_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # FK to User (One-to-Many)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user = db.relationship("User", back_populates="orders")

    # Many-to-Many to Product
    products = db.relationship(
        "Product",
        secondary=order_product,
        back_populates="orders",
        lazy="joined",  # eager-load to keep responses snappy
    )

    def __repr__(self) -> str:
        return f"<Order {self.id} user={self.user_id}>"

# ──────────────────────────────────────────────────────────────────────────────
# Schemas (Marshmallow)
# NOTE: include_fk=True is IMPORTANT so user_id is included on OrderSchema.
# ──────────────────────────────────────────────────────────────────────────────
class ProductSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Product
        load_instance = True
        include_fk = False
        sqla_session = db.session
        ordered = True

    id = ma.auto_field(dump_only=True)
    product_name = ma.auto_field(required=True)
    price = ma.auto_field(required=True)

    @validates("price")
    def validate_price(self, value: float, **kwargs):
        if value is None or value < 0:
            raise ValidationError("price must be a non-negative number.")


class UserSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = User
        load_instance = True
        include_fk = False
        sqla_session = db.session
        ordered = True

    id = ma.auto_field(dump_only=True)
    name = ma.auto_field(required=True)
    address = ma.auto_field()
    email = ma.auto_field(required=True)

    @validates("email")
    def validate_email(self, value: str, **kwargs):
        if not value or "@" not in value:
            raise ValidationError("email must be a valid email address.")


class OrderSchema(SQLAlchemyAutoSchema):
    class Meta:
        model = Order
        load_instance = True
        include_fk = True  # ← IMPORTANT so user_id shows up
        sqla_session = db.session
        ordered = True

    id = ma.auto_field(dump_only=True)
    user_id = ma.auto_field(required=True)
    order_date = fields.DateTime(required=True)
    # nest minimal product info for convenience
    products = fields.List(fields.Nested(ProductSchema(only=("id", "product_name", "price"))))


user_schema = UserSchema()
users_schema = UserSchema(many=True)
product_schema = ProductSchema()
products_schema = ProductSchema(many=True)
order_schema = OrderSchema()
orders_schema = OrderSchema(many=True)

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────
def get_or_404(model, obj_id: int):
    obj = model.query.get(obj_id)
    if not obj:
        return None, jsonify({"error": f"{model.__name__} {obj_id} not found"}), 404
    return obj, None, None


@app.errorhandler(ValidationError)
def handle_validation_error(err):
    return jsonify({"errors": err.messages}), 400


@app.errorhandler(404)
def handle_not_found(_):
    return jsonify({"error": "Not found"}), 404


@app.errorhandler(400)
def handle_bad_request(err):
    return jsonify({"error": str(err)}), 400


# ──────────────────────────────────────────────────────────────────────────────
# USERS CRUD
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/users")
def list_users():
    return jsonify(users_schema.dump(User.query.order_by(User.id).all()))


@app.get("/users/<int:user_id>")
def get_user(user_id: int):
    user, resp, code = get_or_404(User, user_id)
    if resp:
        return resp, code
    return jsonify(user_schema.dump(user))


@app.post("/users")
def create_user():
    data = request.get_json(force=True)
    obj = user_schema.load(data)
    # unique email check
    if User.query.filter_by(email=obj.email).first():
        return jsonify({"error": "email already exists"}), 409
    db.session.add(obj)
    db.session.commit()
    return jsonify(user_schema.dump(obj)), 201


@app.put("/users/<int:user_id>")
def update_user(user_id: int):
    user, resp, code = get_or_404(User, user_id)
    if resp:
        return resp, code
    data = request.get_json(force=True)
    # partial update allowed; validate fields
    for field in ("name", "address", "email"):
        if field in data:
            setattr(user, field, data[field])

    # unique email check if changed
    if "email" in data:
        exists = User.query.filter(User.email == user.email, User.id != user.id).first()
        if exists:
            return jsonify({"error": "email already exists"}), 409

    db.session.commit()
    return jsonify(user_schema.dump(user))


@app.delete("/users/<int:user_id>")
def delete_user(user_id: int):
    user, resp, code = get_or_404(User, user_id)
    if resp:
        return resp, code
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": f"user {user_id} deleted"}), 200


# ──────────────────────────────────────────────────────────────────────────────
# PRODUCTS CRUD
# ──────────────────────────────────────────────────────────────────────────────
@app.get("/products")
def list_products():
    return jsonify(products_schema.dump(Product.query.order_by(Product.id).all()))


@app.get("/products/<int:product_id>")
def get_product(product_id: int):
    product, resp, code = get_or_404(Product, product_id)
    if resp:
        return resp, code
    return jsonify(product_schema.dump(product))


@app.post("/products")
def create_product():
    data = request.get_json(force=True)
    obj = product_schema.load(data)
    db.session.add(obj)
    db.session.commit()
    return jsonify(product_schema.dump(obj)), 201


@app.put("/products/<int:product_id>")
def update_product(product_id: int):
    product, resp, code = get_or_404(Product, product_id)
    if resp:
        return resp, code
    data = request.get_json(force=True)
    if "product_name" in data:
        product.product_name = data["product_name"]
    if "price" in data:
        # validate via schema field
        product_schema.load({"price": data["price"]}, partial=True)
        product.price = float(data["price"])
    db.session.commit()
    return jsonify(product_schema.dump(product))


@app.delete("/products/<int:product_id>")
def delete_product(product_id: int):
    product, resp, code = get_or_404(Product, product_id)
    if resp:
        return resp, code
    db.session.delete(product)
    db.session.commit()
    return jsonify({"message": f"product {product_id} deleted"}), 200


# ──────────────────────────────────────────────────────────────────────────────
# ORDERS
# ──────────────────────────────────────────────────────────────────────────────
@app.post("/orders")
def create_order():
    """
    Body:
    {
      "user_id": 1,
      "order_date": "2025-09-23T12:00:00",  // ISO8601
      "product_ids": [1, 2, 3]              // optional
    }
    """
    data = request.get_json(force=True)

    # validate with OrderSchema (ensures user_id and order_date exist)
    _ = order_schema.load(
        {
            "user_id": data.get("user_id"),
            "order_date": data.get("order_date"),
            "products": [],  # not loading products here
        }
    )

    user = User.query.get(data["user_id"])
    if not user:
        return jsonify({"error": f"user {data['user_id']} not found"}), 404

    try:
        dt = datetime.fromisoformat(data["order_date"])
    except Exception:
        return jsonify({"error": "order_date must be ISO 8601 (e.g. 2025-09-23T10:30:00)"}), 400

    order = Order(user_id=user.id, order_date=dt)

    # optional: initial product_ids
    product_ids: List[int] = data.get("product_ids") or []
    if product_ids:
        products = Product.query.filter(Product.id.in_(product_ids)).all()
        if len(products) != len(set(product_ids)):
            return jsonify({"error": "one or more product_ids do not exist"}), 400
        order.products.extend(products)

    db.session.add(order)
    db.session.commit()
    return jsonify(order_schema.dump(order)), 201


@app.put("/orders/<int:order_id>/add_product/<int:product_id>")
def add_product_to_order(order_id: int, product_id: int):
    order, resp, code = get_or_404(Order, order_id)
    if resp:
        return resp, code
    product, resp, code = get_or_404(Product, product_id)
    if resp:
        return resp, code

    if product in order.products:
        # duplicate-prevention: no-op or 409; choose 200 with message
        return jsonify({"message": "product already in order", "order": order_schema.dump(order)}), 200

    order.products.append(product)
    db.session.commit()
    return jsonify(order_schema.dump(order)), 200


@app.delete("/orders/<int:order_id>/remove_product/<int:product_id>")
def remove_product_from_order(order_id: int, product_id: int):
    order, resp, code = get_or_404(Order, order_id)
    if resp:
        return resp, code
    product, resp, code = get_or_404(Product, product_id)
    if resp:
        return resp, code

    if product not in order.products:
        return jsonify({"error": "product not in order"}), 404

    order.products.remove(product)
    db.session.commit()
    return jsonify(order_schema.dump(order)), 200


@app.get("/orders/user/<int:user_id>")
def list_orders_for_user(user_id: int):
    user, resp, code = get_or_404(User, user_id)
    if resp:
        return resp, code
    return jsonify(orders_schema.dump(Order.query.filter_by(user_id=user.id).order_by(Order.id).all()))


@app.get("/orders/<int:order_id>/products")
def list_products_for_order(order_id: int):
    order, resp, code = get_or_404(Order, order_id)
    if resp:
        return resp, code
    return jsonify(products_schema.dump(order.products))


# (Optional convenience) Inspect a single order
@app.get("/orders/<int:order_id>")
def get_order(order_id: int):
    order, resp, code = get_or_404(Order, order_id)
    if resp:
        return resp, code
    return jsonify(order_schema.dump(order))


# ──────────────────────────────────────────────────────────────────────────────
# Bootstrap (db.create_all for assignment verification)
# ──────────────────────────────────────────────────────────────────────────────
@app.route("/init-db", methods=["POST"])
def init_db():
    db.create_all()
    return jsonify({"message": "tables created"}), 201


if __name__ == "__main__":
    # Ensure tables exist when running locally
    with app.app_context():
        db.create_all()
    app.run(debug=True)
