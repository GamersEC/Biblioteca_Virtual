from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Libro(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    autor = db.Column(db.String(50), nullable=False)
    anio = db.Column(db.Integer, nullable=False)
    editorial = db.Column(db.String(50), nullable=False)
    archivo = db.Column(db.String(100))

    def __init__(self, titulo, autor, anio, editorial, archivo):
        self.titulo = titulo
        self.autor = autor
        self.anio = anio
        self.editorial = editorial
        self.archivo = archivo