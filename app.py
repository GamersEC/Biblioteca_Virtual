from flask import Flask
from modelos import db, Libro
from routes import configurar_rutas

app = Flask(__name__, static_folder='static', static_url_path='')
app.secret_key = 'clave_secreta_ultrasegura'

# Configuración de SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///biblioteca.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializar la base de datos
db.init_app(app)
with app.app_context():
    db.create_all()  # Crea las tablas si no existen

configurar_rutas(app)

if __name__ == '__main__':
    app.run(debug=True)