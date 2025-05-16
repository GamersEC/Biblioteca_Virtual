import os
import uuid

from flask import (
    render_template, request, redirect, flash, url_for, session, g, abort, send_file
)
from modelos import db, Libro, Usuario, Prestamo, Configuracion, Genero
from werkzeug.utils import secure_filename
from datetime import datetime
from sqlalchemy import func

UPLOAD_FOLDER = 'static/uploads'
COVER_FOLDER_REL = 'static/covers'
ALLOWED_EXTENSIONS = {'pdf'}
ALLOWED_COVER_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def allowed_cover_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_COVER_EXTENSIONS


def configurar_rutas(app, login_required, admin_required):
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['COVER_FOLDER_REL'] = COVER_FOLDER_REL

    upload_path_abs = os.path.join(app.root_path, UPLOAD_FOLDER)
    if not os.path.exists(upload_path_abs): os.makedirs(upload_path_abs)
    app.config['UPLOAD_FOLDER_ABS'] = upload_path_abs

    cover_path_abs = os.path.join(app.root_path, COVER_FOLDER_REL)
    if not os.path.exists(cover_path_abs): os.makedirs(cover_path_abs)
    app.config['COVER_FOLDER_ABS'] = cover_path_abs


    # ========================
    # Rutas de Autenticación, Principales, Gestión de Géneros
    # ========================
    # (Estas rutas son las mismas, sin cambios)
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if g.user: return redirect(url_for('index'))
        if request.method == 'POST':
            email = request.form['email'].lower()
            password = request.form['password']
            user = Usuario.query.filter(func.lower(Usuario.email) == email).first()
            if user and user.check_password(password):
                session.clear(); session['user_id'] = user.id; session['user_role'] = user.role
                flash('Inicio de sesión exitoso.', 'success')
                return redirect(request.args.get('next') or url_for('index'))
            else: flash('Email o contraseña incorrectos.', 'error')
        return render_template('login.html')

    @app.route('/logout')
    @login_required
    def logout():
        session.clear(); g.user = None
        flash('Has cerrado sesión.', 'info')
        return redirect(url_for('login'))

    @app.route('/')
    def index():
        stats = {
            'total_libros': Libro.query.count(),
            'total_usuarios': Usuario.query.count(),
            'prestamos_activos': Prestamo.query.filter(Prestamo.fecha_devolucion_real == None).count()
        }
        ultimos_prestamos_query = Prestamo.query.order_by(Prestamo.fecha_prestamo.desc())
        if g.user and g.user.role != 'admin':
            ultimos_prestamos_query = ultimos_prestamos_query.filter_by(usuario_id=g.user.id)
        ultimos_prestamos = ultimos_prestamos_query.limit(5).all()
        return render_template('index.html', stats=stats, ultimos_prestamos=ultimos_prestamos)

    @app.route('/admin/generos', methods=['GET', 'POST'])
    @admin_required
    def admin_gestionar_generos():
        if request.method == 'POST':
            nombre_genero = request.form.get('nombre_genero', '').strip()
            if nombre_genero:
                if Genero.query.filter(func.lower(Genero.nombre) == func.lower(nombre_genero)).first():
                    flash(f"El género '{nombre_genero}' ya existe.", 'warning')
                else:
                    try:
                        db.session.add(Genero(nombre=nombre_genero)); db.session.commit()
                        flash(f"Género '{nombre_genero}' añadido.", 'success')
                    except Exception as e: db.session.rollback(); flash(f"Error: {e}", 'error')
            else: flash("El nombre del género no puede estar vacío.", 'error')
            return redirect(url_for('admin_gestionar_generos'))
        return render_template('admin_gestionar_generos.html', generos=Genero.query.order_by(Genero.nombre).all())

    @app.route('/admin/generos/eliminar/<int:genero_id>', methods=['POST'])
    @admin_required
    def admin_eliminar_genero(genero_id):
        genero = Genero.query.get_or_404(genero_id)
        if genero.libros: flash(f"No se puede eliminar '{genero.nombre}', está asignado a libros.", 'error')
        else:
            try: db.session.delete(genero); db.session.commit(); flash(f"Género '{genero.nombre}' eliminado.", 'success')
            except Exception as e: db.session.rollback(); flash(f"Error: {e}", 'error')
        return redirect(url_for('admin_gestionar_generos'))


    # ========================
    # Sección Libros (Admin)
    # ========================
    @app.route('/registro_libro', methods=['GET', 'POST'])
    @admin_required
    def registro_libro_admin():
        if request.method == 'POST':
            titulo = request.form['titulo']
            autor = request.form['autor']
            anio = request.form['anio']
            editorial = request.form['editorial']
            descripcion = request.form.get('descripcion', '').strip()
            ids_generos_seleccionados = request.form.getlist('generos')
            max_prestamos = int(request.form.get('max_prestamos', Configuracion.obtener_int('max_prestamos_default', 5)))
            archivo_subido = request.files.get('archivo')
            portada_manual_subida = request.files.get('portada_manual')

            nombre_archivo_libro_original = None
            nombre_archivo_portada_final_temp = None
            ruta_archivo_libro_abs_temp = None
            ruta_archivo_portada_abs_temp = None

            try:
                if not (archivo_subido and archivo_subido.filename != ''):
                    flash('Debe seleccionar un archivo PDF para el libro.', 'error')
                    return redirect(url_for('registro_libro_admin'))

                if not allowed_file(archivo_subido.filename):
                    flash(f'Tipo de archivo de libro no permitido. Solo se aceptan PDFs.', 'error')
                    return redirect(url_for('registro_libro_admin'))

                nombre_archivo_libro_original = secure_filename(archivo_subido.filename)
                _, ext_libro_temp = os.path.splitext(nombre_archivo_libro_original)
                nombre_libro_temp = f"temp_libro_{uuid.uuid4().hex}{ext_libro_temp}"
                ruta_archivo_libro_abs_temp = os.path.join(app.config['UPLOAD_FOLDER_ABS'], nombre_libro_temp)
                archivo_subido.save(ruta_archivo_libro_abs_temp)

                if portada_manual_subida and portada_manual_subida.filename != '':
                    if allowed_cover_file(portada_manual_subida.filename):
                        nombre_portada_manual_original = secure_filename(portada_manual_subida.filename)
                        _, ext_portada_manual = os.path.splitext(nombre_portada_manual_original)
                        nombre_portada_temp_manual = f"temp_cover_manual_{uuid.uuid4().hex}{ext_portada_manual}"
                        ruta_archivo_portada_abs_temp = os.path.join(app.config['COVER_FOLDER_ABS'], nombre_portada_temp_manual)
                        portada_manual_subida.save(ruta_archivo_portada_abs_temp)
                        nombre_archivo_portada_final_temp = nombre_portada_temp_manual
                    else:
                        flash(f'Tipo de archivo de portada no permitido.', 'warning')

                nuevo_libro = Libro(
                    titulo=titulo, autor=autor, anio=anio, editorial=editorial,
                    descripcion=descripcion, archivo=None, portada_archivo=None,
                    max_prestamos=max_prestamos
                )
                if ids_generos_seleccionados:
                    for genero_id_str in ids_generos_seleccionados:
                        genero = Genero.query.get(int(genero_id_str))
                        if genero: nuevo_libro.generos.append(genero)

                db.session.add(nuevo_libro)
                db.session.flush()

                if ruta_archivo_libro_abs_temp:
                    _, ext_libro = os.path.splitext(nombre_archivo_libro_original)
                    nombre_final_libro = f"libro_{nuevo_libro.id}{ext_libro}"
                    ruta_final_libro_abs = os.path.join(app.config['UPLOAD_FOLDER_ABS'], nombre_final_libro)
                    os.rename(ruta_archivo_libro_abs_temp, ruta_final_libro_abs)
                    nuevo_libro.archivo = nombre_final_libro
                    ruta_archivo_libro_abs_temp = None

                if ruta_archivo_portada_abs_temp:
                    _, ext_portada = os.path.splitext(nombre_archivo_portada_final_temp)
                    nombre_final_portada = f"cover_{nuevo_libro.id}{ext_portada}"
                    ruta_final_portada_abs = os.path.join(app.config['COVER_FOLDER_ABS'], nombre_final_portada)
                    os.rename(ruta_archivo_portada_abs_temp, ruta_final_portada_abs)
                    nuevo_libro.portada_archivo = nombre_final_portada
                    ruta_archivo_portada_abs_temp = None

                db.session.commit()
                flash('Libro registrado exitosamente!', 'success')
                return redirect(url_for('lista_libros'))

            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Error al registrar libro en DB: {e}", exc_info=True)
                flash(f'Error al registrar el libro: {str(e)}', 'error')
                if ruta_archivo_libro_abs_temp and os.path.exists(ruta_archivo_libro_abs_temp):
                    try: os.remove(ruta_archivo_libro_abs_temp)
                    except: pass
                if ruta_archivo_portada_abs_temp and os.path.exists(ruta_archivo_portada_abs_temp):
                    try: os.remove(ruta_archivo_portada_abs_temp)
                    except: pass
                return redirect(url_for('registro_libro_admin'))

        generos_disponibles = Genero.query.order_by(Genero.nombre).all()
        return render_template('registro_libro.html', generos_disponibles=generos_disponibles)

    @app.route('/editar_libro/<int:libro_id>', methods=['GET', 'POST'])
    @admin_required
    def editar_libro(libro_id):
        libro = Libro.query.get_or_404(libro_id)
        if request.method == 'POST':
            try:
                libro.titulo = request.form['titulo']
                libro.autor = request.form['autor']
                libro.anio = request.form['anio']
                libro.editorial = request.form['editorial']
                libro.descripcion = request.form.get('descripcion', '').strip()
                libro.max_prestamos = int(request.form.get('max_prestamos', libro.max_prestamos))

                ids_generos_seleccionados = request.form.getlist('generos')
                libro.generos.clear()
                if ids_generos_seleccionados:
                    for genero_id_str in ids_generos_seleccionados:
                        genero = Genero.query.get(int(genero_id_str))
                        if genero: libro.generos.append(genero)

                archivo_nuevo_subido = request.files.get('archivo')
                portada_manual_subida = request.files.get('portada_manual')

                if archivo_nuevo_subido and archivo_nuevo_subido.filename != '':
                    if not allowed_file(archivo_nuevo_subido.filename): # Solo PDF
                        flash(f'Tipo de archivo de libro no permitido. Solo PDFs.', 'error')
                        return render_template('editar_libro.html', libro=libro, generos_disponibles=Genero.query.order_by(Genero.nombre).all())

                    if libro.archivo and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER_ABS'], libro.archivo)):
                        try: os.remove(os.path.join(app.config['UPLOAD_FOLDER_ABS'], libro.archivo))
                        except OSError: pass

                    nombre_original_nuevo_libro = secure_filename(archivo_nuevo_subido.filename)
                    _, ext_libro = os.path.splitext(nombre_original_nuevo_libro)
                    nombre_final_nuevo_libro = f"libro_{libro.id}{ext_libro}"
                    ruta_nuevo_libro_guardado = os.path.join(app.config['UPLOAD_FOLDER_ABS'], nombre_final_nuevo_libro)
                    archivo_nuevo_subido.save(ruta_nuevo_libro_guardado)
                    libro.archivo = nombre_final_nuevo_libro

                if portada_manual_subida and portada_manual_subida.filename != '':
                    if allowed_cover_file(portada_manual_subida.filename):
                        if libro.portada_archivo and os.path.exists(os.path.join(app.config['COVER_FOLDER_ABS'], libro.portada_archivo)):
                            try: os.remove(os.path.join(app.config['COVER_FOLDER_ABS'], libro.portada_archivo))
                            except OSError: pass

                        nombre_portada_manual_original = secure_filename(portada_manual_subida.filename)
                        _, ext_portada_manual = os.path.splitext(nombre_portada_manual_original)
                        libro.portada_archivo = f"cover_{libro.id}{ext_portada_manual}"

                        ruta_portada_manual_abs = os.path.join(app.config['COVER_FOLDER_ABS'], libro.portada_archivo)
                        portada_manual_subida.save(ruta_portada_manual_abs)
                    else:
                        flash(f'Tipo de archivo de portada manual no permitido.', 'warning')

                db.session.commit()
                flash('Libro actualizado exitosamente!', 'success')
                return redirect(url_for('lista_libros'))
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Error al editar libro {libro_id}: {e}", exc_info=True)
                flash(f'Error al actualizar el libro: {str(e)}', 'error')

        generos_disponibles = Genero.query.order_by(Genero.nombre).all()
        return render_template('editar_libro.html', libro=libro, generos_disponibles=generos_disponibles)

    @app.route('/eliminar_libro/<int:libro_id>', methods=['GET', 'POST'])
    @admin_required
    def eliminar_libro(libro_id):
        libro = Libro.query.get_or_404(libro_id)
        prestamos_activos_del_libro = libro.prestamos.filter_by(fecha_devolucion_real=None).all()

        if request.method == 'POST':
            try:
                if libro.archivo and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER_ABS'], libro.archivo)):
                    try: os.remove(os.path.join(app.config['UPLOAD_FOLDER_ABS'], libro.archivo))
                    except OSError as e_os: flash(f"Adv: {e_os}", 'warning')
                if libro.portada_archivo and os.path.exists(os.path.join(app.config['COVER_FOLDER_ABS'], libro.portada_archivo)):
                    try: os.remove(os.path.join(app.config['COVER_FOLDER_ABS'], libro.portada_archivo))
                    except OSError as e_os: flash(f"Adv: {e_os}", 'warning')
                libro.generos.clear()
                db.session.delete(libro)
                db.session.commit()
                flash(f"Libro '{libro.titulo}' y sus préstamos asociados eliminados.", 'success')
                return redirect(url_for('lista_libros'))
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Error al eliminar: {e}", exc_info=True)
                flash(f'Error al eliminar: {e}', 'error')
                return redirect(url_for('lista_libros'))
        return render_template('confirmar_eliminar_libro.html', libro=libro, prestamos_activos=prestamos_activos_del_libro)

    @app.route('/lista_libros')
    @login_required
    def lista_libros():
        libros_query = Libro.query.order_by(Libro.titulo)
        prestamos_usuario_activo = {}
        if g.user and g.user.role != 'admin':
            prestamos = Prestamo.query.filter_by(usuario_id=g.user.id, fecha_devolucion_real=None).all()
            for p in prestamos: prestamos_usuario_activo[p.libro_id] = p.id
        libros_con_estado = [{'libro': l, 'prestamo_activo_usuario_id': prestamos_usuario_activo.get(l.id)} for l in libros_query.all()]
        return render_template('lista_libros.html', libros_con_estado=libros_con_estado)


    # ========================
    # Sección Usuarios (Admin)
    # ========================
    @app.route('/usuarios')
    @admin_required
    def lista_usuarios():
        return render_template('lista_usuarios.html', usuarios=Usuario.query.order_by(Usuario.nombre).all())

    @app.route('/registrar_usuario', methods=['GET', 'POST'])
    @admin_required
    def registrar_usuario():
        if request.method == 'POST':
            try:
                nombre = request.form['nombre']
                email = request.form['email'].lower()
                password = request.form['password']
                role = request.form.get('role', 'usuario')
                if not password: flash('Contraseña requerida.', 'error'); return redirect(url_for('registrar_usuario'))
                if Usuario.query.filter(func.lower(Usuario.email) == email).first():
                    flash('Email ya registrado.', 'error'); return redirect(url_for('registrar_usuario'))
                nuevo_usuario = Usuario(nombre=nombre, email=email, role=role)
                nuevo_usuario.set_password(password)
                db.session.add(nuevo_usuario); db.session.commit()
                flash('Usuario registrado!', 'success'); return redirect(url_for('lista_usuarios'))
            except Exception as e:
                db.session.rollback(); app.logger.error(f"Error: {e}", exc_info=True)
                flash(f'Error al registrar: {str(e)}', 'error'); return redirect(url_for('registrar_usuario'))
        return render_template('registrar_usuario.html')


    # ========================
    # Sección Préstamos
    # ========================
    @app.route('/prestar_libro', methods=['GET', 'POST'])
    @admin_required
    def prestar_libro():
        duracion_default = Configuracion.obtener_int('duracion_prestamo_default', 7)
        if request.method == 'POST':
            try:
                libro_id = request.form['libro_id']
                usuario_id = request.form['usuario_id']
                duracion = int(request.form.get('duracion', duracion_default))
                max_duracion = Configuracion.obtener_int('max_duracion_prestamo', 30)
                if not (1 <= duracion <= max_duracion):
                    flash(f'Duración debe ser entre 1 y {max_duracion} días', 'error'); return redirect(url_for('prestar_libro'))
                libro_obj = Libro.query.get(libro_id)
                usuario = Usuario.query.get(usuario_id)
                if not libro_obj or not usuario: flash('Libro o usuario no encontrado', 'error'); return redirect(url_for('prestar_libro'))
                if libro_obj.prestamos_activos >= libro_obj.max_prestamos:
                    flash('Libro con todos sus ejemplares prestados', 'error'); return redirect(url_for('prestar_libro'))
                nuevo_prestamo = Prestamo(libro_id=libro_obj.id, usuario_id=usuario.id, duracion=duracion)
                libro_obj.prestamos_activos += 1
                db.session.add(nuevo_prestamo); db.session.commit()
                flash('Préstamo registrado!', 'success'); return redirect(url_for('lista_prestamos'))
            except Exception as e:
                db.session.rollback(); app.logger.error(f"Error: {e}", exc_info=True)
                flash(f'Error en préstamo: {str(e)}', 'error'); return redirect(url_for('prestar_libro'))
        libros_disp = Libro.query.filter(Libro.prestamos_activos < Libro.max_prestamos).all()
        usuarios_todos = Usuario.query.all()
        max_dur_cfg = Configuracion.obtener_int('max_duracion_prestamo', 30)
        return render_template('prestar_libro.html', libros=libros_disp, usuarios=usuarios_todos, duracion_default=duracion_default, max_duracion_config=max_dur_cfg)

    @app.route('/solicitar_prestamo/<int:libro_id>', methods=['POST'])
    @login_required
    def solicitar_prestamo_usuario(libro_id):
        if g.user.role == 'admin': flash('Admins usan otra interfaz.', 'warning'); return redirect(url_for('lista_libros'))
        libro_obj = Libro.query.get_or_404(libro_id)
        if Prestamo.query.filter_by(libro_id=libro_obj.id, usuario_id=g.user.id, fecha_devolucion_real=None).first():
            flash('Ya tienes este libro prestado.', 'info'); return redirect(url_for('lista_libros'))
        if libro_obj.prestamos_activos >= libro_obj.max_prestamos:
            flash('Libro agotado.', 'error'); return redirect(url_for('lista_libros'))
        duracion = Configuracion.obtener_int('duracion_prestamo_default', 7)
        try:
            nuevo_prestamo = Prestamo(libro_id=libro_obj.id, usuario_id=g.user.id, duracion=duracion)
            libro_obj.prestamos_activos += 1
            db.session.add(nuevo_prestamo); db.session.commit()
            flash(f'"{libro_obj.titulo}" solicitado por {duracion} días.', 'success'); return redirect(url_for('mis_prestamos'))
        except Exception as e:
            db.session.rollback(); app.logger.error(f"Error: {e}", exc_info=True)
            flash('Error al solicitar.', 'error'); return redirect(url_for('lista_libros'))

    @app.route('/devolver_libro/<int:prestamo_id>')
    @admin_required
    def devolver_libro(prestamo_id):
        try:
            prestamo = Prestamo.query.get_or_404(prestamo_id)
            if prestamo.esta_activo:
                libro_obj = Libro.query.get(prestamo.libro_id)
                if libro_obj: libro_obj.prestamos_activos = max(0, libro_obj.prestamos_activos - 1)
                prestamo.fecha_devolucion_real = datetime.utcnow(); db.session.commit()
                flash('Libro devuelto por admin.', 'success')
            else: flash('Libro ya devuelto.', 'info')
            return redirect(url_for('lista_prestamos'))
        except Exception as e:
            db.session.rollback(); app.logger.error(f"Error: {e}", exc_info=True)
            flash(f'Error: {str(e)}', 'error'); return redirect(url_for('lista_prestamos'))

    @app.route('/devolver_mi_libro/<int:prestamo_id>', methods=['POST'])
    @login_required
    def devolver_libro_usuario(prestamo_id):
        prestamo = Prestamo.query.get_or_404(prestamo_id)
        if prestamo.usuario_id != g.user.id: flash('No es tu préstamo.', 'error'); return redirect(url_for('mis_prestamos'))
        if not prestamo.esta_activo: flash('Ya devuelto.', 'info'); return redirect(url_for('mis_prestamos'))
        try:
            libro_obj = Libro.query.get(prestamo.libro_id)
            if libro_obj: libro_obj.prestamos_activos = max(0, libro_obj.prestamos_activos - 1)
            prestamo.fecha_devolucion_real = datetime.utcnow(); db.session.commit()
            flash(f'"{libro_obj.titulo if libro_obj else "Libro"}" devuelto.', 'success')
        except Exception as e:
            db.session.rollback(); app.logger.error(f"Error: {e}", exc_info=True)
            flash('Error al devolver.', 'error')
        return redirect(url_for('mis_prestamos'))

    @app.route('/prestamos')
    @admin_required
    def lista_prestamos():
        activos = Prestamo.query.filter(Prestamo.fecha_devolucion_real == None).order_by(Prestamo.fecha_devolucion_prevista.asc()).all()
        devueltos = Prestamo.query.filter(Prestamo.fecha_devolucion_real != None).order_by(Prestamo.fecha_devolucion_real.desc()).limit(20).all()
        return render_template('lista_prestamos.html', prestamos_activos=activos, prestamos_devueltos=devueltos)

    @app.route('/mis_prestamos')
    @login_required
    def mis_prestamos():
        activos = Prestamo.query.filter_by(usuario_id=g.user.id, fecha_devolucion_real=None).order_by(Prestamo.fecha_devolucion_prevista.asc()).all()
        historial = Prestamo.query.filter(Prestamo.usuario_id == g.user.id, Prestamo.fecha_devolucion_real != None).order_by(Prestamo.fecha_devolucion_real.desc()).limit(10).all()
        return render_template('mis_prestamos.html', prestamos_activos=activos, prestamos_historial=historial)

    # --- Rutas para el Lector PDF ---
    @app.route('/leer_libro_pdf/<int:prestamo_id>') # Ruta que muestra el lector PDF.js
    @login_required
    def leer_libro_pdf(prestamo_id):
        prestamo = Prestamo.query.get_or_404(prestamo_id)
        libro_obj = Libro.query.get_or_404(prestamo.libro_id)

        if not (g.user.id == prestamo.usuario_id or g.user.role == 'admin'):
            flash('No tienes permiso para acceder a este préstamo.', 'error'); return abort(403)
        if not prestamo.esta_activo:
            flash('Este préstamo ha expirado o no está activo.', 'error'); return redirect(url_for('mis_prestamos'))
        if datetime.utcnow() > prestamo.fecha_devolucion_prevista:
            if prestamo.esta_activo: # Marcar como devuelto si expiró
                libro_obj.prestamos_activos = max(0, libro_obj.prestamos_activos - 1)
                prestamo.fecha_devolucion_real = prestamo.fecha_devolucion_prevista
                db.session.commit(); flash('Préstamo expirado y devuelto.', 'warning')
            else: flash('Préstamo expirado.', 'warning')
            return redirect(url_for('mis_prestamos'))
        if not libro_obj.archivo:
            flash('El archivo de este libro no está disponible.', 'error'); return redirect(url_for('mis_prestamos'))

        if not libro_obj.archivo.lower().endswith('.pdf'):
            flash('Este libro no es un PDF y no puede ser leído con este visor.', 'error')
            return redirect(url_for('mis_prestamos')) # O a la lista de libros

        # URL que PDF.js usará para obtener el contenido del PDF
        url_contenido_pdf = url_for('servir_pdf_crudo', prestamo_id=prestamo.id)

        return render_template('lector_pdf.html',
                               libro_titulo=libro_obj.titulo,
                               url_pdf=url_contenido_pdf)

    @app.route('/_servir_pdf_crudo/<int:prestamo_id>') # Ruta interna para que PDF.js obtenga el archivo
    @login_required
    def servir_pdf_crudo(prestamo_id):
        prestamo = Prestamo.query.get_or_404(prestamo_id)
        libro_obj = Libro.query.get_or_404(prestamo.libro_id)

        # Re-validar permisos aquí es crucial para seguridad
        if not (g.user.id == prestamo.usuario_id or g.user.role == 'admin'): abort(403)
        if not prestamo.esta_activo: abort(403)
        if datetime.utcnow() > prestamo.fecha_devolucion_prevista: abort(403)
        if not libro_obj.archivo or not libro_obj.archivo.lower().endswith('.pdf'): abort(404)

        ruta_archivo_abs = os.path.join(app.config['UPLOAD_FOLDER_ABS'], libro_obj.archivo)
        if not os.path.exists(ruta_archivo_abs): abort(404)

        try:
            return send_file(
                ruta_archivo_abs,
                mimetype='application/pdf',
                as_attachment=False # Importante para que PDF.js lo pueda cargar
            )
        except Exception as e:
            app.logger.error(f"Error al servir PDF crudo {libro_obj.archivo}: {e}", exc_info=True)
            abort(500)


    # ========================
    # Configuración (Admin)
    # ========================
    @app.route('/admin/configuracion', methods=['GET', 'POST'])
    @admin_required
    def admin_configuracion():
        if request.method == 'POST':
            try:
                Configuracion.establecer('max_prestamos_default', request.form['max_prestamos_default'])
                Configuracion.establecer('duracion_prestamo_default', request.form['duracion_prestamo_default'])
                Configuracion.establecer('max_duracion_prestamo', request.form.get('max_duracion_prestamo', '30'))
                flash('Configuración guardada.', 'success')
                g.config_max_prestamos_default = Configuracion.obtener_int('max_prestamos_default', 5)
                g.config_duracion_prestamo_default = Configuracion.obtener_int('duracion_prestamo_default', 7)
            except Exception as e:
                app.logger.error(f"Error guardando config: {e}", exc_info=True)
                flash(f'Error: {e}', 'error')
            return redirect(url_for('admin_configuracion'))
        configs = {
            'max_prestamos_default': Configuracion.obtener_int('max_prestamos_default', 5),
            'duracion_prestamo_default': Configuracion.obtener_int('duracion_prestamo_default', 7),
            'max_duracion_prestamo': Configuracion.obtener_int('max_duracion_prestamo', 30)
        }
        return render_template('admin_configuracion.html', configs=configs)


    # ========================
    # Manejo de errores
    # ========================
    @app.errorhandler(403)
    def forbidden_error(error): return render_template('403.html'), 403
    @app.errorhandler(404)
    def pagina_no_encontrada(error): return render_template('404.html'), 404
    @app.errorhandler(500)
    def error_servidor(error):
        db.session.rollback()
        app.logger.error(f"Error 500: {error}", exc_info=True)
        return render_template('500.html'), 500