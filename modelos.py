from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

tabla_libro_genero = db.Table('libro_genero',
                              db.Column('libro_id', db.Integer, db.ForeignKey('libros.id'), primary_key=True),
                              db.Column('genero_id', db.Integer, db.ForeignKey('generos.id'), primary_key=True)
                              )

class Genero(db.Model):
    __tablename__ = 'generos'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False)

    def __repr__(self):
        return f'<Genero {self.nombre}>'

class Libro(db.Model):
    __tablename__ = 'libros'

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    autor = db.Column(db.String(50), nullable=False)
    anio = db.Column(db.Integer, nullable=False)
    editorial = db.Column(db.String(50), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    archivo = db.Column(db.String(100), nullable=True)
    portada_archivo = db.Column(db.String(100), nullable=True)
    max_prestamos = db.Column(db.Integer, default=5)
    prestamos_activos = db.Column(db.Integer, default=0)

    # MODIFICACIÓN AQUÍ para la cascada
    prestamos = db.relationship('Prestamo', backref='libro', lazy='dynamic', # lazy='dynamic' para poder hacer .filter()
                                cascade="all, delete-orphan")

    generos = db.relationship('Genero', secondary=tabla_libro_genero,
                              lazy='subquery',
                              backref=db.backref('libros', lazy=True))

    def __init__(self, titulo, autor, anio, editorial, descripcion=None, archivo=None, portada_archivo=None, max_prestamos=5):
        self.titulo = titulo
        self.autor = autor
        self.anio = anio
        self.editorial = editorial
        self.descripcion = descripcion
        self.archivo = archivo
        self.portada_archivo = portada_archivo
        self.max_prestamos = max_prestamos

class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    role = db.Column(db.String(10), default='usuario')
    prestamos = db.relationship('Prestamo', backref='usuario', lazy='dynamic')

    def __init__(self, nombre, email, role='usuario'):
        self.nombre = nombre
        self.email = email
        self.role = role

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Prestamo(db.Model):
    __tablename__ = 'prestamos'
    id = db.Column(db.Integer, primary_key=True)
    fecha_prestamo = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_devolucion_prevista = db.Column(db.DateTime)
    fecha_devolucion_real = db.Column(db.DateTime, nullable=True)
    duracion = db.Column(db.Integer, nullable=False)
    libro_id = db.Column(db.Integer, db.ForeignKey('libros.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id'), nullable=False)

    def __init__(self, libro_id, usuario_id, duracion):
        self.libro_id = libro_id
        self.usuario_id = usuario_id
        self.duracion = duracion
        self.calcular_fecha_devolucion_prevista()

    def calcular_fecha_devolucion_prevista(self):
        self.fecha_devolucion_prevista = datetime.utcnow() + timedelta(days=self.duracion)

    @property
    def esta_activo(self):
        return self.fecha_devolucion_real is None

    @property
    def tiempo_restante(self):
        if self.esta_activo and self.fecha_devolucion_prevista:
            restante = self.fecha_devolucion_prevista - datetime.utcnow()
            if restante.total_seconds() < 0: return "Vencido"
            days = restante.days
            hours, remainder = divmod(restante.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            if days > 0: return f"{days}d {hours}h"
            elif hours > 0: return f"{hours}h {minutes}m"
            else: return f"{minutes}m"
        return "N/A"

class Configuracion(db.Model):
    # ... (sin cambios) ...
    __tablename__ = 'configuracion'
    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(50), unique=True, nullable=False)
    valor = db.Column(db.String(100), nullable=False)

    def __init__(self, clave, valor):
        self.clave = clave
        self.valor = valor

    @staticmethod
    def obtener(clave, default=None):
        config = Configuracion.query.filter_by(clave=clave).first()
        return config.valor if config else default

    @staticmethod
    def establecer(clave, valor):
        config = Configuracion.query.filter_by(clave=clave).first()
        if config:
            config.valor = str(valor)
        else:
            config = Configuracion(clave=clave, valor=str(valor))
            db.session.add(config)
        db.session.commit()

    @staticmethod
    def obtener_int(clave, default=0):
        val = Configuracion.obtener(clave)
        try:
            return int(val) if val else default
        except ValueError:
            return default