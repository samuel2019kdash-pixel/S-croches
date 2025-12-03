from flask import Flask, render_template, redirect, url_for, session, request
from authlib.integrations.flask_client import OAuth
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.secret_key = "sua_chave_segura_aqui"

# Banco
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///croche.db"
db = SQLAlchemy(app)

# Google Login
oauth = OAuth(app)
oauth.register(
    name="google",
    client_id="SEU_CLIENT_ID",
    client_secret="SEU_CLIENT_SECRET",
    access_token_url="https://oauth2.googleapis.com/token",
    authorize_url="https://accounts.google.com/o/oauth2/auth",
    authorize_params={"prompt": "select_account"},
    api_base_url="https://www.googleapis.com/oauth2/v1/",
    client_kwargs={"scope": "openid profile email"},
)

# ------------------------- MODELOS -------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    google_id = db.Column(db.String(200))
    name = db.Column(db.String(200))
    email = db.Column(db.String(200))


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    description = db.Column(db.Text)
    price = db.Column(db.Float)
    image_url = db.Column(db.String(300))


class Pedido(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"))
    status = db.Column(db.String(50), default="Pendente")
    data = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship("User")
    product = db.relationship("Product")


# ------------------------- ROTAS -------------------------

@app.route("/")
def index():
    products = Product.query.all()
    user = session.get("user")
    return render_template("index.html", products=products, user=user)


@app.route("/login")
def login():
    redirect_uri = url_for("auth", _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


@app.route("/auth")
def auth():
    token = oauth.google.authorize_access_token()
    user_info = oauth.google.get("userinfo").json()

    user = User.query.filter_by(email=user_info["email"]).first()

    if not user:
        user = User(
            google_id=user_info["id"],
            name=user_info["name"],
            email=user_info["email"],
        )
        db.session.add(user)
        db.session.commit()

    session["user"] = {
        "id": user.id,
        "name": user.name,
        "email": user.email,
    }

    return redirect(url_for("index"))


@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("index"))


# ------------------------- PEDIDO -------------------------

@app.route("/pedido/<int:id>")
def fazer_pedido(id):
    if "user" not in session:
        return redirect(url_for("login"))

    novo = Pedido(
        user_id=session["user"]["id"],
        product_id=id,
        status="Pendente"
    )
    db.session.add(novo)
    db.session.commit()

    return redirect(url_for("index"))


# ------------------------- PAINEL ADM -------------------------

def is_admin():
    return "user" in session and session["user"]["email"] == "denizeetiago1992@gmail.com"


@app.route("/adm")
def painel_adm():
    if not is_admin():
        return "Acesso negado"

    pedidos = Pedido.query.order_by(Pedido.data.desc()).all()
    produtos = Product.query.all()

    return render_template("adm.html", pedidos=pedidos, produtos=produtos)


@app.route("/aprovar/<int:id>")
def aprovar_pedido(id):
    if not is_admin():
        return "Acesso negado"

    p = Pedido.query.get(id)
    p.status = "Aprovado"
    db.session.commit()
    return redirect(url_for("painel_adm"))


@app.route("/rejeitar/<int:id>")
def rejeitar_pedido(id):
    if not is_admin():
        return "Acesso negado"

    p = Pedido.query.get(id)
    p.status = "Rejeitado"
    db.session.commit()
    return redirect(url_for("painel_adm"))


# ------------------------- PRODUTO -------------------------

@app.route("/novo_produto", methods=["POST"])
def novo_produto():
    if not is_admin():
        return "Acesso negado"

    nome = request.form["nome"]
    desc = request.form["descricao"]
    preco = float(request.form["preco"])
    img = request.form["imagem"]

    produto = Product(
        name=nome,
        description=desc,
        price=preco,
        image_url=img
    )
    db.session.add(produto)
    db.session.commit()

    return redirect(url_for("painel_adm"))


# ------------------------ INICIALIZAÇÃO ------------------------

# O Render usa o Gunicorn, então não coloque app.run() duas vezes
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run()
