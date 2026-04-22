from flask import Blueprint, render_template, request, redirect, url_for, session
from db import obtener_conexion

clientes_bp = Blueprint('clientes', __name__)

@clientes_bp.route('/index')
def index():
    if 'usuario' not in session:
        return redirect(url_for('auth.login'))

    buscar = request.args.get('buscar', '')
    conn = obtener_conexion()

    if not conn:
        return "Error de conexión a la base de datos"

    with conn.cursor() as cursor:
        if buscar:
            cursor.execute("SELECT * FROM clientes WHERE nombre LIKE %s", (f"%{buscar}%",))
        else:
            cursor.execute("SELECT * FROM clientes")
        clientes = cursor.fetchall()

    conn.close()
    return render_template('index.html', clientes=clientes, buscar=buscar)


@clientes_bp.route('/agregar', methods=['GET', 'POST'])
def agregar():
    if 'usuario' not in session:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        nombre = request.form['nombre']
        correo = request.form['correo']
        telefono = request.form['telefono']

        conn = obtener_conexion()
        if not conn:
            return "Error de conexión a la base de datos"

        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO clientes (nombre, correo, telefono) VALUES (%s, %s, %s)",
                (nombre, correo, telefono)
            )
            conn.commit()

        conn.close()
        return redirect(url_for('clientes.index'))

    return render_template('agregar.html')


@clientes_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    if 'usuario' not in session:
        return redirect(url_for('auth.login'))

    conn = obtener_conexion()
    if not conn:
        return "Error de conexión a la base de datos"

    with conn.cursor() as cursor:
        if request.method == 'POST':
            nombre = request.form['nombre']
            correo = request.form['correo']
            telefono = request.form['telefono']

            cursor.execute(
                "UPDATE clientes SET nombre=%s, correo=%s, telefono=%s WHERE id=%s",
                (nombre, correo, telefono, id)
            )
            conn.commit()
            conn.close()
            return redirect(url_for('clientes.index'))

        cursor.execute("SELECT * FROM clientes WHERE id = %s", (id,))
        cliente = cursor.fetchone()

    conn.close()
    return render_template('editar.html', cliente=cliente)


@clientes_bp.route('/eliminar/<int:id>')
def eliminar(id):
    if 'usuario' not in session:
        return redirect(url_for('auth.login'))

    conn = obtener_conexion()
    if not conn:
        return "Error de conexión a la base de datos"

    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM clientes WHERE id = %s", (id,))
        conn.commit()

    conn.close()
    return redirect(url_for('clientes.index'))