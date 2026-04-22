from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify, abort

import pymysql
import csv
import io
from datetime import datetime
import json

app = Flask(__name__)
app.secret_key = 'clave_secreta'

# Conexion MySQL
def obtener_conexion():
    try:
        return pymysql.connect(
            host='localhost',
            user='root',
            password='',
            database='mi_crm',
            cursorclass=pymysql.cursors.Cursor
        )
    except Exception as e:
        print("Error de conexion:", e)
        return None

# --- LOGIN ---
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        password = request.form['password']
        conn = obtener_conexion()
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM usuarios WHERE usuario = %s AND password = %s", (usuario, password))
            user = cursor.fetchone()
        conn.close()
        if user:
            session['usuario'] = usuario
            return redirect(url_for('inicio'))
        else:
            return render_template('login.html', error='Credenciales inválidas')
    return render_template('login.html')

@app.route('/inicio')
def inicio():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    return render_template('inicio.html')

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('login'))

# --- CLIENTES ---
@app.route('/index')
def index():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    buscar = request.args.get('buscar', '')
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        if buscar:
            cursor.execute("SELECT * FROM clientes WHERE nombre LIKE %s", (f"%{buscar}%",))
        else:
            cursor.execute("SELECT * FROM clientes")
        clientes = cursor.fetchall()
    conn.close()
    return render_template('index.html', clientes=clientes, buscar=buscar)



@app.route('/agregar', methods=['GET', 'POST'])
def agregar():
    if request.method == 'POST':
        nombre = request.form['nombre']
        correo = request.form['correo']
        telefono = request.form['telefono']
        conn = obtener_conexion()
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO clientes (nombre, correo, telefono) VALUES (%s, %s, %s)", (nombre, correo, telefono))
            conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template('agregar.html')

@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        if request.method == 'POST':
            nombre = request.form['nombre']
            correo = request.form['correo']
            telefono = request.form['telefono']
            cursor.execute("UPDATE clientes SET nombre=%s, correo=%s, telefono=%s WHERE id=%s", (nombre, correo, telefono, id))
            conn.commit()
            conn.close()
            return redirect(url_for('index'))
        cursor.execute("SELECT * FROM clientes WHERE id = %s", (id,))
        cliente = cursor.fetchone()
    conn.close()
    return render_template('editar.html', cliente=cliente)

@app.route('/eliminar/<int:id>')
def eliminar(id):
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM clientes WHERE id = %s", (id,))
        conn.commit()
    conn.close()
    return redirect(url_for('index'))

# --- DOCTORES ---
@app.route('/gestionar_doctores')
def gestionar_doctores():
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM doctores")
        doctores = cursor.fetchall()
    conn.close()
    return render_template('doctores.html', doctores=doctores)

@app.route('/agregar_doctor', methods=['GET', 'POST'])
def agregar_doctor():
    if request.method == 'POST':
        nombre = request.form['nombre']
        especialidad = request.form['especialidad']
        conn = obtener_conexion()
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO doctores (nombre, especialidad) VALUES (%s, %s)", (nombre, especialidad))
            conn.commit()
        conn.close()
        return redirect(url_for('gestionar_doctores'))
    return render_template('agregar_doctor.html')

@app.route('/editar_doctor/<int:id>', methods=['GET', 'POST'])
def editar_doctor(id):
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        if request.method == 'POST':
            nombre = request.form['nombre']
            especialidad = request.form['especialidad']
            cursor.execute("UPDATE doctores SET nombre=%s, especialidad=%s WHERE id=%s", (nombre, especialidad, id))
            conn.commit()
            conn.close()
            return redirect(url_for('gestionar_doctores'))
        cursor.execute("SELECT * FROM doctores WHERE id = %s", (id,))
        doctor = cursor.fetchone()
    conn.close()
    return render_template('editar_doctor.html', doctor=doctor)

@app.route('/eliminar_doctor/<int:id>')
def eliminar_doctor(id):
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        cursor.execute("DELETE FROM doctores WHERE id = %s", (id,))
        conn.commit()
    conn.close()
    return redirect(url_for('gestionar_doctores'))

# --- CITAS ---
# --- CITAS ---
@app.route('/citas/<int:cliente_id>')
def ver_citas(cliente_id):
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        cursor.execute("SELECT id, nombre FROM clientes WHERE id = %s", (cliente_id,))
        cliente = cursor.fetchone()
        cursor.execute("""
            SELECT c.id, c.fecha, c.descripcion, d.nombre
            FROM citas c
            LEFT JOIN doctores d ON c.doctor_id = d.id
            WHERE c.cliente_id = %s
        """, (cliente_id,))
        citas_raw = cursor.fetchall()
    conn.close()
    citas = [{'id': row[0], 'fecha': row[1], 'descripcion': row[2], 'doctor': row[3]} for row in citas_raw]
    return render_template('citas.html', cliente={'id': cliente[0], 'nombre': cliente[1]}, citas=citas)

@app.route('/agregar_cita/<int:cliente_id>', methods=['GET', 'POST'])
def agregar_cita(cliente_id):
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        cursor.execute("SELECT id, nombre FROM doctores")
        doctores = cursor.fetchall()
    if request.method == 'POST':
        fecha = request.form['fecha']
        descripcion = request.form['descripcion']
        doctor_id = request.form['doctor_id']
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO citas (cliente_id, fecha, descripcion, doctor_id) VALUES (%s, %s, %s, %s)", (cliente_id, fecha, descripcion, doctor_id))
            conn.commit()
        conn.close()
        return redirect(url_for('ver_citas', cliente_id=cliente_id))
    conn.close()
    return render_template('agregar_cita.html', cliente_id=cliente_id, doctores=doctores)

@app.route('/editar_cita/<int:cita_id>', methods=['GET', 'POST'])
def editar_cita(cita_id):
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        if request.method == 'POST':
            fecha = request.form['fecha']
            descripcion = request.form['descripcion']
            doctor_id = request.form['doctor_id']
            cursor.execute("UPDATE citas SET fecha = %s, descripcion = %s, doctor_id = %s WHERE id = %s", (fecha, descripcion, doctor_id, cita_id))
            conn.commit()
            cursor.execute("SELECT cliente_id FROM citas WHERE id = %s", (cita_id,))
            cliente_id = cursor.fetchone()[0]
            conn.close()
            return redirect(url_for('ver_citas', cliente_id=cliente_id))
        cursor.execute("SELECT id, cliente_id, fecha, descripcion, doctor_id FROM citas WHERE id = %s", (cita_id,))
        cita = cursor.fetchone()
        cita_dict = {
            'id': cita[0],
            'cliente_id': cita[1],
            'fecha': cita[2],
            'descripcion': cita[3],
            'doctor_id': cita[4]
        }
        cursor.execute("SELECT id, nombre FROM doctores")
        doctores = cursor.fetchall()
    conn.close()
    return render_template('editar_cita.html', cita=cita_dict, doctores=doctores)

@app.route('/eliminar_cita/<int:cita_id>')
def eliminar_cita(cita_id):
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        # Obtener cliente_id para redirigir correctamente después de eliminar
        cursor.execute("SELECT cliente_id FROM citas WHERE id = %s", (cita_id,))
        cliente_id = cursor.fetchone()[0]

        # Eliminar la cita
        cursor.execute("DELETE FROM citas WHERE id = %s", (cita_id,))
        conn.commit()
    conn.close()
    return redirect(url_for('ver_citas', cliente_id=cliente_id))

@app.route('/enviar_recordatorio/<int:cita_id>', methods=['POST'])
def enviar_recordatorio(cita_id):
    # TODO: acá va el envío real por email (cuando lo quieras activar)
    # Usamos el cliente_id que viene por querystring para volver a la vista de citas
    cliente_id = request.args.get('cliente_id')
    if not cliente_id:
        # Si no vino, lo buscamos para no romper
        conn = obtener_conexion()
        with conn.cursor() as cur:
            cur.execute("SELECT cliente_id FROM citas WHERE id = %s", (cita_id,))
            row = cur.fetchone()
        conn.close()
        cliente_id = row[0] if row else None

    if cliente_id:
        return redirect(url_for('ver_citas', cliente_id=cliente_id))
    else:
        # Fallback: ir al listado si no se pudo determinar el cliente
        return redirect(url_for('index'))



# --- ATENCIONES ---

# --- Registrar atención con campos por especialidad ---



# --- RUTA REGISTRAR ATENCIÓN ---

from types import SimpleNamespace

from flask import render_template, request, redirect, url_for
from datetime import datetime
import pymysql




@app.route('/atencion/<int:cita_id>', methods=['GET', 'POST'])
def registrar_atencion(cita_id):
    # 1) Traer info de la cita (cliente/doctor/especialidad)
    conn = obtener_conexion()
    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("""
            SELECT c.id, c.fecha, c.descripcion,
                   cl.nombre AS nombre_cliente, cl.id AS cliente_id,
                   d.nombre AS nombre_doctor, d.especialidad
            FROM citas c
            LEFT JOIN clientes cl ON c.cliente_id = cl.id
            LEFT JOIN doctores d ON c.doctor_id = d.id
            WHERE c.id = %s
        """, (cita_id,))
        cita = cursor.fetchone()
    conn.close()

    if request.method == 'POST':
        def val(name):  # helper
            return (request.form.get(name) or '').strip()

        # 2) Campos generales
        fecha            = val('fecha') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        observaciones    = val('observaciones')
        diagnostico      = val('diagnostico')
        tratamiento      = val('tratamiento')
        recetas          = val('recetas')
        indicaciones     = val('indicaciones')
        estudios_pedidos = val('estudios_pedidos')
        sintomas         = val('sintomas')
        proxima_fecha    = val('proxima_fecha') or None  # puede ir NULL

        # 3) Signos / métricas
        presion_arterial         = val('ta') or val('presion_arterial') or None
        presion_arterial_clinica = val('presion_arterial_clinica') or None
        peso     = request.form.get('peso') or None
        altura   = request.form.get('altura') or None
        glucemia = request.form.get('glucemia') or None
        insulina_utilizada = val('insulina_utilizada') or None

        # 4) Campos clínica/diabetes
        tipo_diabetes  = val('tipo_diabetes') or None
        hba1c          = val('hba1c') or None
        notas_clinica  = val('notas_clinica') or None

        # 5) Campos específicos por especialidad → en notas_extra (JSON)
        esp = (cita.get('especialidad') or '').strip()
        notas_libres = val('notas_extra')
        extra = {}
        if esp == 'Oftalmología':
            extra['Agudeza visual'] = val('agudeza_visual')
            extra['PIO'] = val('pio')
        elif esp == 'Cardiología':
            extra['Frecuencia cardíaca'] = val('fc')
            if presion_arterial:  # ya la guardamos aparte, pero la reflejamos si querés
                extra['Tensión arterial'] = presion_arterial
        elif esp == 'Neurología':
            extra['Reflejos'] = val('reflejos')
            extra['Coordinación'] = val('coordinacion')
        elif esp == 'Endocrinología':
            # Estos se guardan en columnas propias; no los duplicamos en JSON
            pass
        elif esp == 'Clínica':
            extra['Examen físico'] = val('examen_fisico')
            extra['Diagnóstico diferencial'] = val('diagnostico_diferencial')

        # Armar notas_extra final
        if extra or notas_libres:
            payload = {}
            if notas_libres:
                payload['Notas'] = notas_libres
            payload.update({k: v for k, v in extra.items() if v})
            notas_extra = json.dumps(payload, ensure_ascii=False)
        else:
            notas_extra = None

        # 6) Insert según TU tabla `atenciones`
        conn = obtener_conexion()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO atenciones
                (cita_id, fecha, observaciones, diagnostico, tratamiento, recetas,
                 indicaciones, estudios_pedidos, sintomas, notas_extra, proxima_fecha,
                 presion_arterial, presion_arterial_clinica, peso, altura,
                 glucemia, insulina_utilizada, notas_clinica, tipo_diabetes, hba1c)
                VALUES (%s,%s,%s,%s,%s,%s,
                        %s,%s,%s,%s,%s,
                        %s,%s,%s,%s,
                        %s,%s,%s,%s,%s)
            """, (
                cita_id, fecha, observaciones, diagnostico, tratamiento, recetas,
                indicaciones, estudios_pedidos, sintomas, notas_extra, proxima_fecha,
                presion_arterial, presion_arterial_clinica, peso, altura,
                glucemia, insulina_utilizada, notas_clinica, tipo_diabetes, hba1c
            ))
            conn.commit()
        conn.close()

        return redirect(url_for('ver_citas_general'))  # o donde prefieras

    # GET: mostrar formulario
    return render_template('registrar_atencion.html', cita=cita)


@app.route('/atencion/<int:atencion_id>/ver')
def ver_atencion(atencion_id):
    sql = """
    SELECT
        a.*, cli.nombre AS cliente_nombre, doc.nombre AS doctor_nombre, doc.especialidad
    FROM atenciones a
    LEFT JOIN citas ci     ON ci.id = a.cita_id
    LEFT JOIN clientes cli ON cli.id = ci.cliente_id
    LEFT JOIN doctores doc ON doc.id = ci.doctor_id
    WHERE a.id = %s
    """
    conn = obtener_conexion()
    with conn.cursor(pymysql.cursors.DictCursor) as cur:
        cur.execute(sql, (atencion_id,))
        r = cur.fetchone()
    conn.close()
    if not r: abort(404)

    # IMC y categorías
    peso, altura = r.get('peso'), r.get('altura')
    imc = imc_cat = None
    try:
        if peso and altura:
            alt = float(altura)
            if alt > 3:  # altura probablemente en cm
                alt = alt / 100.0
            imc = round(float(peso) / (alt**2), 2)
            imc_cat = ("Bajo peso" if imc < 18.5 else
                       "Normal" if imc < 25 else
                       "Sobrepeso" if imc < 30 else "Obesidad")
    except Exception:
        pass

    # HbA1c categoría
    hba_cat = None
    try:
        h = float(str(r.get('hba1c') or '').replace(',', '.'))
        hba_cat = "Normal" if h < 5.7 else ("Prediabetes" if h < 6.5 else "Diabetes")
    except Exception:
        pass

    # notas_extra: si es JSON lo parseamos, si no lo pasamos como texto
    notas_extra = r.get('notas_extra')
    try:
        notas_extra = json.loads(notas_extra) if notas_extra else {}
    except Exception:
        # lo dejamos como texto
        pass

    atencion = dict(r)
    atencion.update({"imc": imc, "imc_cat": imc_cat, "hba1c_cat": hba_cat})

    return render_template(
        'detalle_atencion.html',
        atencion=atencion,
        notas_extra=notas_extra
    )


from flask import jsonify
import json
from decimal import Decimal
from datetime import date, datetime

@app.route('/atencion/<int:atencion_id>/detalle', methods=['GET'])
def detalle_atencion_json(atencion_id):
    try:
        conn = obtener_conexion()
        with conn.cursor(pymysql.cursors.DictCursor) as cur:
            cur.execute("""
                SELECT
                    a.*,
                    cli.nombre AS cliente_nombre,
                    doc.nombre AS doctor_nombre,
                    doc.especialidad AS especialidad
                FROM atenciones a
                LEFT JOIN citas ci     ON ci.id = a.cita_id
                LEFT JOIN clientes cli ON cli.id = ci.cliente_id
                LEFT JOIN doctores doc ON doc.id = ci.doctor_id
                WHERE a.id = %s
            """, (atencion_id,))
            r = cur.fetchone()
        conn.close()

        if not r:
            return jsonify({"ok": False, "error": "Atención no encontrada"}), 404

        # --- normalizar todo a tipos JSON-friendly ---
        def to_primitive(v):
            if isinstance(v, (datetime, date)):
                return v.strftime("%Y-%m-%d %H:%M")
            if isinstance(v, Decimal):
                # usa float o str. Si querés conservar ceros finales, usá str(v)
                return float(v)
            return v

        r = {k: to_primitive(v) for k, v in r.items()}

        # notas_extra: intentar parsear JSON si viene como texto
        ne = r.get("notas_extra")
        if isinstance(ne, str) and ne.strip():
            try:
                r["notas_extra"] = json.loads(ne)
            except Exception:
                # dejar el texto tal cual
                pass
        elif ne is None:
            r["notas_extra"] = {}

        # Calcular IMC si hay peso/altura
        try:
            peso   = float(r["peso"])   if r.get("peso")   not in (None, "", "NULL") else None
            altura = float(r["altura"]) if r.get("altura") not in (None, "", "NULL") else None
            if peso and altura:
                alt = altura/100.0 if altura > 3 else altura  # si vino en cm
                imc = round(peso/(alt**2), 2)
                r["imc"] = imc
                r["imc_cat"] = ("Bajo peso" if imc < 18.5 else
                                "Normal"    if imc < 25   else
                                "Sobrepeso" if imc < 30   else "Obesidad")
        except Exception:
            pass

        # Categoría HbA1c
        try:
            h = float(str(r.get("hba1c") or "").replace(",", "."))
            r["hba1c_cat"] = "Normal" if h < 5.7 else ("Prediabetes" if h < 6.5 else "Diabetes")
        except Exception:
            r["hba1c_cat"] = None

        return jsonify({"ok": True, "data": r})

    except Exception as e:
        # te deja ver el error concreto en la consola del navegador (Network)
        return jsonify({"ok": False, "error": str(e)}), 500






# --- CITAS ---

# --- EXPORTAR ---
@app.route('/exportar')
def exportar():
    conn = obtener_conexion()
    with conn.cursor(pymysql.cursors.DictCursor) as cursor:

        cursor.execute("SELECT * FROM clientes")
        clientes = cursor.fetchall()
    conn.close()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Nombre', 'Correo', 'Telefono'])
    for cliente in clientes:
        writer.writerow(cliente)
    output.seek(0)
    return send_file(io.BytesIO(output.getvalue().encode('utf-8')), mimetype='text/csv', as_attachment=True, download_name='clientes.csv')

# --- REPORTES ---
@app.route('/reportes', methods=['GET'])
def reportes():
    tipo = request.args.get('tipo', 'dominio')  # valor por defecto

    conn = obtener_conexion()
    with conn.cursor() as cursor:
        if tipo == 'doctor':
            cursor.execute("""
                SELECT d.nombre, COUNT(*) 
                FROM citas c
                LEFT JOIN doctores d ON c.doctor_id = d.id
                GROUP BY d.nombre
            """)
        else:  # dominio
            cursor.execute("""
                SELECT SUBSTRING_INDEX(correo, '@', -1) AS dominio, COUNT(*) 
                FROM clientes 
                GROUP BY dominio
            """)

        resultados = cursor.fetchall()

    conn.close()
    labels = [fila[0] or 'Sin asignar' for fila in resultados]
    data = [fila[1] for fila in resultados]

    return render_template('reportes.html', labels=labels, data=data, tipo=tipo)


@app.route('/reporte_citas_por_doctor')
def reporte_citas_por_doctor():
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT d.nombre, COUNT(c.id) as total_citas
            FROM doctores d
            LEFT JOIN citas c ON d.id = c.doctor_id
            GROUP BY d.nombre
        """)
        resultados = cursor.fetchall()
    conn.close()

    labels = [fila[0] for fila in resultados]
    data = [fila[1] for fila in resultados]

    return render_template('reporte_citas_por_doctor.html', labels=labels, data=data)


# --- CALENDARIO GENERAL ---

from datetime import datetime
import calendar

@app.route('/calendario', methods=['GET', 'POST'])
def calendario():
    conn = obtener_conexion()
    hoy = datetime.today()
    mes_actual = request.form.get('mes', hoy.month)
    anio_actual = request.form.get('anio', hoy.year)

    # Aseguramos que sean enteros
    mes_actual = int(mes_actual)
    anio_actual = int(anio_actual)

    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("""
            SELECT c.id, c.fecha, c.descripcion, c.cliente_id, cl.nombre as cliente, d.nombre as doctor
            FROM citas c
            LEFT JOIN clientes cl ON c.cliente_id = cl.id
            LEFT JOIN doctores d ON c.doctor_id = d.id
            WHERE MONTH(c.fecha) = %s AND YEAR(c.fecha) = %s
            ORDER BY c.fecha
        """, (mes_actual, anio_actual))
        citas = cursor.fetchall()

    conn.close()

    meses = list(enumerate(calendar.month_name))[1:]  # [(1, 'January'), (2, 'February'), ...]
    anios = list(range(hoy.year - 2, hoy.year + 3))    # Por ejemplo: [2023, 2024, 2025, 2026, 2027]

    return render_template('calendario.html',
                           citas=citas,
                           mes_actual=mes_actual,
                           anio_actual=anio_actual,
                           meses=meses,
                           anios=anios)


from datetime import datetime
import calendar


@app.route('/calendario_general', methods=['GET', 'POST'])
def ver_citas_general():
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        cursor.execute("SELECT id, nombre FROM doctores")
        doctores = cursor.fetchall()

    citas = []
    selected_month = None
    selected_year = None
    selected_doctor_id = None

    if request.method == 'POST':
        selected_month = int(request.form.get('mes'))
        selected_year = int(request.form.get('anio'))
        doctor_raw = request.form.get('doctor')
        selected_doctor_id = int(doctor_raw) if doctor_raw else None
    else:
        # Por defecto: mes y año actual
        hoy = datetime.today()
        selected_month = hoy.month
        selected_year = hoy.year

    conn = obtener_conexion()
    with conn.cursor() as cursor:
        query = """
            SELECT c.id, c.fecha, c.descripcion, d.nombre AS doctor, cl.nombre AS cliente
            FROM citas c
            LEFT JOIN doctores d ON c.doctor_id = d.id
            LEFT JOIN clientes cl ON c.cliente_id = cl.id
            WHERE MONTH(c.fecha) = %s AND YEAR(c.fecha) = %s
        """
        params = [selected_month, selected_year]

        if selected_doctor_id:
            query += " AND d.id = %s"
            params.append(selected_doctor_id)

        cursor.execute(query, params)
        citas_raw = cursor.fetchall()
    conn.close()

    colores = ['#1abc9c', '#3498db', '#9b59b6', '#e67e22', '#e74c3c']
    doctor_colores = {}

    for row in citas_raw:
        cita_id, fecha, descripcion, doctor, cliente = row
        if not fecha or not cliente:
            continue
        fecha_str = fecha.isoformat() if hasattr(fecha, 'isoformat') else str(fecha)

        hoy = datetime.today().date()
        es_hoy = fecha.date() == hoy
        link = f"/atencion/{cita_id}" if es_hoy else None
        titulo = f"{descripcion} - {doctor} ({cliente})" if doctor else f"{descripcion} ({cliente})"
        color = doctor_colores.setdefault(doctor, colores[len(doctor_colores) % len(colores)])

        evento = {
            'title': titulo,
            'start': fecha_str,
            'color': color
        }
        if link:
            evento['url'] = link  # Redirige a atención si es hoy
        citas.append(evento)

    return render_template(
        'calendario_general.html',
        citas=citas,
        doctores=doctores,
        mes=selected_month,
        anio=selected_year,
        selected_doctor_id=selected_doctor_id
    )




@app.route('/reporte_citas_doctor')
def reporte_citas_doctor():
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT d.nombre, COUNT(c.id) as total
            FROM citas c
            LEFT JOIN doctores d ON c.doctor_id = d.id
            GROUP BY d.nombre
        """)
        resultados = cursor.fetchall()
    conn.close()
    labels = [fila[0] if fila[0] else 'Sin doctor' for fila in resultados]
    data = [fila[1] for fila in resultados]
    return render_template('reporte_citas_por_doctor.html', labels=labels, data=data)

@app.route('/reporte_clientes_dominio')
def reporte_clientes_dominio():
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT SUBSTRING_INDEX(correo, '@', -1) AS dominio, COUNT(*) as cantidad
            FROM clientes
            GROUP BY dominio
        """)
        resultados = cursor.fetchall()
    conn.close()

    labels = [fila[0] for fila in resultados]
    data = [fila[1] for fila in resultados]

    return render_template(
        'reporte_clientes_dominio.html',
        resultados=resultados,
        labels=labels,
        data=data
    )

# Reporte: Citas por Mes
@app.route('/reporte_citas_mes')
def reporte_citas_mes():
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT DATE_FORMAT(fecha, '%Y-%m') AS mes, COUNT(*) 
            FROM citas 
            GROUP BY mes 
            ORDER BY mes
        """)
        resultados = cursor.fetchall()
    conn.close()
    labels = [row[0] for row in resultados]
    data = [row[1] for row in resultados]
    return render_template('reporte_citas_mes.html', resultados=resultados, labels=labels, data=data)

# Reporte: Clientes Frecuentes
@app.route('/reporte_clientes_frecuentes')
def reporte_clientes_frecuentes():
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT cl.nombre, COUNT(*) 
            FROM citas c 
            JOIN clientes cl ON c.cliente_id = cl.id 
            GROUP BY cl.id 
            HAVING COUNT(*) > 3
            ORDER BY COUNT(*) DESC
        """)
        resultados = cursor.fetchall()
    conn.close()
    return render_template('reporte_clientes_frecuentes.html', resultados=resultados)

# Reporte: Citas por Especialidad
@app.route('/reporte_citas_especialidad')
def reporte_citas_especialidad():
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT d.especialidad, COUNT(*) 
            FROM citas c 
            JOIN doctores d ON c.doctor_id = d.id 
            GROUP BY d.especialidad
        """)
        resultados = cursor.fetchall()
    conn.close()
    labels = [row[0] for row in resultados]
    data = [row[1] for row in resultados]
    return render_template('reporte_citas_especialidad.html', resultados=resultados, labels=labels, data=data)

@app.route('/reporte_clientes_sin_citas')
def reporte_clientes_sin_citas():
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT cl.nombre, cl.correo
            FROM clientes cl
            LEFT JOIN citas c ON cl.id = c.cliente_id
            WHERE c.id IS NULL
        """)
        resultados = cursor.fetchall()
    conn.close()
    return render_template('reporte_clientes_sin_citas.html', resultados=resultados)

@app.route('/reporte_doctores_sin_citas')
def reporte_doctores_sin_citas():
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT d.nombre, d.especialidad
            FROM doctores d
            LEFT JOIN citas c ON d.id = c.doctor_id
            WHERE c.id IS NULL
        """)
        resultados = cursor.fetchall()
    conn.close()
    return render_template('reporte_doctores_sin_citas.html', resultados=resultados)

@app.route('/reporte_citas_por_cliente')
def reporte_citas_por_cliente():
    conn = obtener_conexion()
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT cl.nombre AS cliente, COUNT(c.id) AS cantidad
            FROM clientes cl
            LEFT JOIN citas c ON cl.id = c.cliente_id
            GROUP BY cl.id
            ORDER BY cantidad DESC
        """)
        resultados = cursor.fetchall()

    conn.close()
    labels = [fila[0] for fila in resultados]
    data = [fila[1] for fila in resultados]
    return render_template('reporte_citas_por_cliente.html', resultados=resultados, labels=labels, data=data)



@app.route('/historial_atenciones/<int:cliente_id>')
def historial_atenciones(cliente_id):
    conn = obtener_conexion()
    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("""
            SELECT a.id, a.fecha, a.diagnostico, a.tratamiento, a.observaciones,
                   a.recetas, a.notas_extra, a.proxima_fecha, d.nombre AS doctor
            FROM atenciones a
            JOIN citas c ON a.cita_id = c.id
            JOIN doctores d ON c.doctor_id = d.id
            WHERE c.cliente_id = %s
            ORDER BY a.fecha DESC
        """, (cliente_id,))
        atenciones = cursor.fetchall()

        cursor.execute("SELECT id, nombre FROM clientes WHERE id = %s", (cliente_id,))
        cliente = cursor.fetchone()

    conn.close()
    return render_template('historial_atenciones.html', cliente=cliente, atenciones=atenciones)


@app.route('/detalle_atencion/<int:atencion_id>')
def detalle_atencion(atencion_id):
    conn = obtener_conexion()
    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("""
            SELECT 
                a.*, 
                c.cliente_id, 
                cl.nombre AS paciente, 
                d.nombre AS doctor_nombre,
                d.especialidad
            FROM atenciones a
            JOIN citas c ON a.cita_id = c.id
            JOIN doctores d ON c.doctor_id = d.id
            JOIN clientes cl ON c.cliente_id = cl.id
            WHERE a.id = %s
        """, (atencion_id,))
        atencion = cursor.fetchone()
    conn.close()
    return render_template('detalle_atencion.html', atencion=atencion)


@app.route('/historial_cliente/<int:cliente_id>')
def historial_cliente(cliente_id):
    conn = obtener_conexion()
    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
        cursor.execute("""
            SELECT a.*, d.nombre AS doctor, d.especialidad, c.fecha AS fecha_cita
            FROM atenciones a
            JOIN citas c ON a.cita_id = c.id
            JOIN doctores d ON c.doctor_id = d.id
            WHERE c.cliente_id = %s
            ORDER BY a.fecha DESC
        """, (cliente_id,))
        atenciones = cursor.fetchall()
    conn.close()
    return render_template('historial_clientes.html', atenciones=atenciones)


# --- MAIN ---
if __name__ == '__main__':
    app.run(debug=True)
