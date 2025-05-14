from flask import Flask
from routes import configurar_rutas

app = Flask(__name__)
configurar_rutas(app)

if __name__ == '__main__':
    app.run(debug=True)