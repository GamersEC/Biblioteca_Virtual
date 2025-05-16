from flask import Flask, session, redirect, url_for, g, flash
from modelos import db, Usuario, Configuracion
from routes import configurar_rutas
from datetime import datetime
from functools import wraps # Para decoradores

app = Flask(__name__, static_folder='static', static_url_path='')
app.secret_key = 'clave_secreta_ultrasegura_reloaded'

# Configuración de SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///biblioteca.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializar la base de datos
db.init_app(app)

def formatear_fecha_filter_func(dt_obj):
    if isinstance(dt_obj, datetime):
        return dt_obj.strftime('%d/%m/%Y %H:%M')
    return ''

app.jinja_env.filters['formatear_fecha'] = formatear_fecha_filter_func

@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None
    else:
        g.user = Usuario.query.get(user_id)
    # Cargar configuraciones globales para plantillas si es necesario
    g.config_max_prestamos_default = Configuracion.obtener_int('max_prestamos_default', 5)
    g.config_duracion_prestamo_default = Configuracion.obtener_int('duracion_prestamo_default', 7)


@app.context_processor
def inject_global_variables():
    return {
        'now': datetime.utcnow(),
        'current_user': g.user,
        'is_admin': g.user.role == 'admin' if g.user else False,
        'config_max_prestamos_default': g.config_max_prestamos_default,
        'config_duracion_prestamo_default': g.config_duracion_prestamo_default
    }

# Decoradores de autenticación y autorización
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            flash('Debes iniciar sesión para acceder a esta página.', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            flash('Debes iniciar sesión para acceder a esta página.', 'warning')
            return redirect(url_for('login', next=request.url))
        if g.user.role != 'admin':
            flash('No tienes permisos para acceder a esta página.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Crear tablas y usuario admin por defecto
with app.app_context():
    db.create_all()
    # Crear configuraciones por defecto si no existen
    if not Configuracion.obtener('max_prestamos_default'):
        Configuracion.establecer('max_prestamos_default', '5')
    if not Configuracion.obtener('duracion_prestamo_default'):
        Configuracion.establecer('duracion_prestamo_default', '7')

    # Crear usuario admin si no existe
    if not Usuario.query.filter_by(email='admin@biblioteca.com').first():
        admin_user = Usuario(nombre='Administrador', email='admin@biblioteca.com', role='admin')
        admin_user.set_password('admin123')
        db.session.add(admin_user)
        db.session.commit()
        print("Usuario administrador creado: admin@biblioteca.com / admin123")


configurar_rutas(app, login_required, admin_required) # Pasar los decoradores

if __name__ == '__main__':
    app.run(debug=True)