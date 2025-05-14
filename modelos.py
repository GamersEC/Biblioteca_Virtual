# modelos.py
libros = []

class Libro:
    def __init__(self, titulo, autor, anio, isbn, archivo):
        self.titulo = titulo
        self.autor = autor
        self.anio = anio
        self.isbn = isbn
        self.archivo = archivo
