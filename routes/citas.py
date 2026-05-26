from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify
from db import obtener_conexion
from datetime import datetime
import calendar

citas_bp = Blueprint('citas', __name__)


@citas_bp.route('/citas/<int:cliente_id>')
def ver_citas(cliente_id):
    if 'usuario' not in session:
        return redirect(url_for('auth.login'))

    conn = obtener_conexion()

    with conn.cursor() as cursor:
        cursor.execute("SELECT id, nombre FROM clientes WHERE id = %s", (cliente_id,))
        cliente = cursor.fetchone()

        if not cliente:
            conn.close()
            return redirect(url_for('clientes.index'))

        cursor.execute("""
            SELECT 
                c.id,
                c.fecha,
                c.descripcion,
                d.nombre,
                a.id AS atencion_id
            FROM citas c
            LEFT JOIN doctores d ON c.doctor_id = d.id
            LEFT JOIN atenciones a ON a.cita_id = c.id
            WHERE c.cliente_id = %s
            ORDER BY c.fecha ASC
        """, (cliente_id,))

        citas_raw = cursor.fetchall()

    conn.close()

    citas = [
        {
            'id': row[0],
            'fecha': row[1],
            'descripcion': row[2],
            'doctor': row[3],
            'atencion_id': row[4]
        }
        for row in citas_raw
    ]

    return render_template(
        'citas.html',
        cliente={'id': cliente[0], 'nombre': cliente[1]},
        citas=citas
    )


@citas_bp.route('/agregar_cita/<int:cliente_id>', methods=['GET', 'POST'])
def agregar_cita(cliente_id):
    if 'usuario' not in session:
        return redirect(url_for('auth.login'))

    conn = obtener_conexion()

    with conn.cursor() as cursor:
        cursor.execute("SELECT id, nombre FROM doctores ORDER BY nombre")
        doctores = cursor.fetchall()

    if request.method == 'POST':
        fecha = request.form['fecha']
        descripcion = request.form['descripcion']
        doctor_id = request.form['doctor_id']

        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO citas (cliente_id, fecha, descripcion, doctor_id)
                VALUES (%s, %s, %s, %s)
            """, (cliente_id, fecha, descripcion, doctor_id))

            conn.commit()

        conn.close()
        return redirect(url_for('citas.ver_citas', cliente_id=cliente_id))

    conn.close()

    return render_template(
        'agregar_cita.html',
        cliente_id=cliente_id,
        doctores=doctores
    )


@citas_bp.route('/editar_cita/<int:cita_id>', methods=['GET', 'POST'])
def editar_cita(cita_id):
    if 'usuario' not in session:
        return redirect(url_for('auth.login'))

    conn = obtener_conexion()

    with conn.cursor() as cursor:
        if request.method == 'POST':
            fecha = request.form['fecha']
            descripcion = request.form['descripcion']
            doctor_id = request.form['doctor_id']

            cursor.execute("SELECT cliente_id FROM citas WHERE id = %s", (cita_id,))
            fila_cliente = cursor.fetchone()
            cliente_id = fila_cliente[0] if fila_cliente else None

            cursor.execute("""
                UPDATE citas
                SET fecha = %s,
                    descripcion = %s,
                    doctor_id = %s
                WHERE id = %s
            """, (fecha, descripcion, doctor_id, cita_id))

            conn.commit()
            conn.close()

            if cliente_id:
                return redirect(url_for('citas.ver_citas', cliente_id=cliente_id))

            return redirect(url_for('clientes.index'))

        cursor.execute("""
            SELECT id, cliente_id, fecha, descripcion, doctor_id
            FROM citas
            WHERE id = %s
        """, (cita_id,))

        cita = cursor.fetchone()

        if not cita:
            conn.close()
            return redirect(url_for('clientes.index'))

        cita_dict = {
            'id': cita[0],
            'cliente_id': cita[1],
            'fecha': cita[2],
            'descripcion': cita[3],
            'doctor_id': cita[4]
        }

        cursor.execute("SELECT id, nombre FROM doctores ORDER BY nombre")
        doctores = cursor.fetchall()

    conn.close()

    return render_template(
        'editar_cita.html',
        cita=cita_dict,
        doctores=doctores
    )


@citas_bp.route('/eliminar_cita/<int:cita_id>')
def eliminar_cita(cita_id):
    if 'usuario' not in session:
        return redirect(url_for('auth.login'))

    conn = obtener_conexion()

    with conn.cursor() as cursor:
        cursor.execute("SELECT cliente_id FROM citas WHERE id = %s", (cita_id,))
        fila = cursor.fetchone()
        cliente_id = fila[0] if fila else None

        if fila:
            cursor.execute("DELETE FROM citas WHERE id = %s", (cita_id,))
            conn.commit()

    conn.close()

    if cliente_id:
        return redirect(url_for('citas.ver_citas', cliente_id=cliente_id))

    return redirect(url_for('clientes.index'))


@citas_bp.route('/enviar_recordatorio/<int:cita_id>', methods=['POST'])
def enviar_recordatorio(cita_id):
    if 'usuario' not in session:
        return redirect(url_for('auth.login'))

    cliente_id = request.args.get('cliente_id')

    if not cliente_id:
        conn = obtener_conexion()

        with conn.cursor() as cur:
            cur.execute("SELECT cliente_id FROM citas WHERE id = %s", (cita_id,))
            row = cur.fetchone()

        conn.close()

        cliente_id = row[0] if row else None

    if cliente_id:
        return redirect(url_for('citas.ver_citas', cliente_id=cliente_id))

    return redirect(url_for('clientes.index'))


@citas_bp.route('/calendario')
def calendario():
    if 'usuario' not in session:
        return redirect(url_for('auth.login'))

    hoy = datetime.now()
    mes = request.args.get('mes', type=int) or hoy.month
    anio = request.args.get('anio', type=int) or hoy.year
    doctor_id = request.args.get('doctor_id', type=int)

    cal = calendar.Calendar(firstweekday=0)
    semanas = cal.monthdayscalendar(anio, mes)

    conn = obtener_conexion()

    with conn.cursor() as cursor:
        cursor.execute("SELECT id, nombre, especialidad FROM doctores ORDER BY nombre")
        doctores = cursor.fetchall()

        sql = """
            SELECT 
                c.id,
                c.fecha,
                c.descripcion,
                c.cliente_id,
                cl.nombre AS cliente_nombre,
                d.id AS doctor_id,
                d.nombre AS doctor_nombre,
                d.especialidad,
                a.id AS atencion_id
            FROM citas c
            LEFT JOIN clientes cl ON c.cliente_id = cl.id
            LEFT JOIN doctores d ON c.doctor_id = d.id
            LEFT JOIN atenciones a ON a.cita_id = c.id
            WHERE YEAR(c.fecha) = %s
              AND MONTH(c.fecha) = %s
        """

        params = [anio, mes]

        if doctor_id:
            sql += " AND d.id = %s"
            params.append(doctor_id)

        sql += " ORDER BY c.fecha ASC"

        cursor.execute(sql, tuple(params))
        citas_raw = cursor.fetchall()

    conn.close()

    citas_por_dia = {}

    for row in citas_raw:
        cita_id = row[0]
        fecha = row[1]
        descripcion = row[2]
        cliente_id = row[3]
        cliente_nombre = row[4]
        doctor_id_row = row[5]
        doctor_nombre = row[6]
        especialidad = row[7]
        atencion_id = row[8]

        dia = fecha.day

        if dia not in citas_por_dia:
            citas_por_dia[dia] = []

        citas_por_dia[dia].append({
            'id': cita_id,
            'fecha': fecha,
            'hora': fecha.strftime('%H:%M') if hasattr(fecha, 'strftime') else '',
            'descripcion': descripcion,
            'cliente_id': cliente_id,
            'cliente_nombre': cliente_nombre,
            'doctor_id': doctor_id_row,
            'doctor_nombre': doctor_nombre,
            'especialidad': especialidad,
            'atendida': atencion_id is not None
        })

    if mes == 1:
        mes_anterior = 12
        anio_anterior = anio - 1
    else:
        mes_anterior = mes - 1
        anio_anterior = anio

    if mes == 12:
        mes_siguiente = 1
        anio_siguiente = anio + 1
    else:
        mes_siguiente = mes + 1
        anio_siguiente = anio

    nombres_meses = [
        "",
        "Enero",
        "Febrero",
        "Marzo",
        "Abril",
        "Mayo",
        "Junio",
        "Julio",
        "Agosto",
        "Septiembre",
        "Octubre",
        "Noviembre",
        "Diciembre"
    ]

    return render_template(
        'calendario.html',
        semanas=semanas,
        citas_por_dia=citas_por_dia,
        mes=mes,
        anio=anio,
        nombre_mes=nombres_meses[mes],
        hoy=hoy.date(),
        mes_anterior=mes_anterior,
        anio_anterior=anio_anterior,
        mes_siguiente=mes_siguiente,
        anio_siguiente=anio_siguiente,
        doctores=doctores,
        doctor_id=doctor_id
    )


@citas_bp.route('/agenda_dia/<fecha>')
def agenda_dia(fecha):
    if 'usuario' not in session:
        return redirect(url_for('auth.login'))

    conn = obtener_conexion()

    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT 
                c.id,
                c.fecha,
                c.descripcion,
                cl.nombre AS cliente_nombre,
                cl.id AS cliente_id,
                d.nombre AS doctor_nombre,
                a.id AS atendida
            FROM citas c
            LEFT JOIN clientes cl ON c.cliente_id = cl.id
            LEFT JOIN doctores d ON c.doctor_id = d.id
            LEFT JOIN atenciones a ON a.cita_id = c.id
            WHERE DATE(c.fecha) = %s
            ORDER BY c.fecha ASC
        """, (fecha,))

        citas = cursor.fetchall()

        cursor.execute("SELECT id, nombre FROM clientes ORDER BY nombre")
        clientes = cursor.fetchall()

        cursor.execute("SELECT id, nombre FROM doctores ORDER BY nombre")
        doctores = cursor.fetchall()

    conn.close()

    return render_template(
        'agenda_dia.html',
        citas=citas,
        fecha=fecha,
        clientes=clientes,
        doctores=doctores
    )


@citas_bp.route('/crear_cita_ajax', methods=['POST'])
def crear_cita_ajax():
    if 'usuario' not in session:
        return jsonify({"ok": False, "error": "No autorizado"}), 401

    data = request.get_json()

    cliente_id = data.get('cliente_id')
    doctor_id = data.get('doctor_id')
    fecha = data.get('fecha')
    descripcion = (data.get('descripcion') or '').strip()

    if not cliente_id or not doctor_id or not fecha:
        return jsonify({"ok": False, "error": "Faltan datos obligatorios"}), 400

    conn = obtener_conexion()

    with conn.cursor() as cursor:
        cursor.execute("""
            INSERT INTO citas (cliente_id, fecha, descripcion, doctor_id)
            VALUES (%s, %s, %s, %s)
        """, (cliente_id, fecha, descripcion, doctor_id))

        conn.commit()

    conn.close()

    return jsonify({"ok": True})