from flask import Blueprint, render_template, request, redirect, url_for, session
from db import obtener_conexion

doctores_bp = Blueprint('doctores', __name__)

@doctores_bp.route('/gestionar_doctores')
def gestionar_doctores():
    if 'usuario' not in session:
        return redirect(url_for('auth.login'))

    conn = obtener_conexion()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM doctores")
        doctores = cursor.fetchall()
    conn.close()

    return render_template('doctores.html', doctores=doctores)


@doctores_bp.route('/agregar_doctor', methods=['GET', 'POST'])
def agregar_doctor():
    if 'usuario' not in session:
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        nombre = request.form['nombre']
        especialidad = request.form['especialidad']

        conn = obtener_conexion()
        with conn.cursor() as cursor:
            cursor.execute(
                "INSERT INTO doctores (nombre, especialidad) VALUES (%s, %s)",
                (nombre, especialidad)
            )
            conn.commit()
        conn.close()

        return redirect(url_for('doctores.gestionar_doctores'))

    return render_template('agregar_doctor.html')


@doctores_bp.route('/editar_doctor/<int:id>', methods=['GET', 'POST'])
def editar_doctor(id):
    if 'usuario' not in session:
        return redirect(url_for('auth.login'))

    conn = obtener_conexion()
    with conn.cursor() as cursor:
        if request.method == 'POST':
            nombre = request.form['nombre']
            especialidad = request.form['especialidad']

            cursor.execute(
                "UPDATE doctores SET nombre=%s, especialidad=%s WHERE id=%s",
                (nombre, especialidad, id)
            )
            conn.commit()
            conn.close()
            return redirect(url_for('doctores.gestionar_doctores'))

        cursor.execute("SELECT * FROM doctores WHERE id = %s", (id,))
        doctor = cursor.fetchone()

    conn.close()
    return render_template('editar_doctor.html', doctor=doctor)


@doctores_bp.route('/eliminar_doctor/<int:id>')
def eliminar_doctor(id):
    if 'usuario' not in session:
        return redirect(url_for('auth.login'))

    conn = obtener_conexion()
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM doctores WHERE id = %s", (id,))
        conn.commit()
    conn.close()

    return redirect(url_for('doctores.gestionar_doctores'))