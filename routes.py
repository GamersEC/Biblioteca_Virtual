import os
from flask import render_template, request, redirect, flash
from modelos import db, Libro
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def configurar_rutas(app):
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

    # Crear directorio de uploads si no existe
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
        # Obtener datos del formulario
        titulo = request.form['titulo']
        autor = request.form['autor']
        anio = request.form['anio']
        editorial = request.form['editorial']
        archivo = request.files['archivo']

        # Validar archivo
        if archivo.filename == '':
            flash('No se seleccionó ningún archivo', 'error')
            return redirect('/registro_libro')

        if not allowed_file(archivo.filename):
            flash('Solo se permiten archivos PDF', 'error')
            return redirect('/registro_libro')

        try:
            # Guardar archivo
            filename = secure_filename(archivo.filename)
            archivo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            # Crear y guardar libro en la base de datos
            nuevo_libro = Libro(
                titulo=titulo,
                autor=autor,
                anio=anio,
                editorial=editorial,
                archivo=filename
            )

            db.session.add(nuevo_libro)
            db.session.commit()

            flash('Libro registrado exitosamente!', 'success')
            return redirect('/lista_libros')

        except Exception as e:
            db.session.rollback()
            flash(f'Error al registrar el libro: {str(e)}', 'error')
            return redirect('/registro_libro')

    @app.route('/lista_libros')
    def lista_libros():
        libros = Libro.query.order_by(Libro.titulo).all()
        return render_template('lista_libros.html', libros=libros)

    # Manejo de errores básico
    @app.errorhandler(404)
    def pagina_no_encontrada(error):
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def error_servidor(error):
        db.session.rollback()
        return render_template('500.html'), 500