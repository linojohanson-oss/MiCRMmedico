from flask import Blueprint, render_template, request, redirect, url_for, session
from db import obtener_conexion

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        password = request.form['password']

        conn = obtener_conexion()
        if not conn:
            return render_template('login.html', error='Error de conexión a la base de datos')

        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT * FROM usuarios WHERE usuario = %s AND password = %s",
                (usuario, password)
            )
            user = cursor.fetchone()
        conn.close()

        if user:
            session['usuario'] = usuario
            return redirect(url_for('auth.inicio'))
        else:
            return render_template('login.html', error='Credenciales inválidas')

    return render_template('login.html')


@auth_bp.route('/inicio')
def inicio():
    if 'usuario' not in session:
        return redirect(url_for('auth.login'))
    return render_template('inicio.html')


@auth_bp.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('auth.login'))