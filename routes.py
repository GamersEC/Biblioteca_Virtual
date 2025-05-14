import os
from flask import render_template, request, redirect
from modelos import libros, Libro
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'uploads'

def configurar_rutas(app):
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/registro_libro')
    def registro_libro():
        return render_template('registro_libro.html')

    @app.route('/registrar_libro', methods=['POST'])
    def registrar_libro():
        titulo = request.form['titulo']
        autor = request.form['autor']
        anio = request.form['anio']
        editorial = request.form['editorial']
        archivo = request.files['archivo']

        if archivo.filename != '':
            filename = secure_filename(archivo.filename)
            archivo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        else:
            filename = None

        nuevo_libro = Libro(titulo, autor, anio, editorial, filename)
        libros.append(nuevo_libro)
        return redirect('/lista_libros')

    @app.route('/lista_libros')
    def lista_libros():
        return render_template('lista_libros.html', libros=libros)
