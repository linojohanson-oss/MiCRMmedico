from flask import Blueprint, render_template, request, redirect, url_for, session, jsonify, abort
from db import obtener_conexion
from datetime import datetime, date
from decimal import Decimal
import pymysql
import json

atenciones_bp = Blueprint('atenciones', __name__)


@atenciones_bp.route('/atencion/<int:cita_id>', methods=['GET', 'POST'])
def registrar_atencion(cita_id):
    if 'usuario' not in session:
        return redirect(url_for('auth.login'))

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

    if not cita:
        abort(404)

    if request.method == 'POST':
        def val(name):
            return (request.form.get(name) or '').strip()

        fecha = val('fecha') or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        observaciones = val('observaciones')
        diagnostico = val('diagnostico')
        tratamiento = val('tratamiento')
        recetas = val('recetas')
        indicaciones = val('indicaciones')
        estudios_pedidos = val('estudios_pedidos')
        sintomas = val('sintomas')
        proxima_fecha = val('proxima_fecha') or None

        presion_arterial = val('ta') or val('presion_arterial') or None

        peso = request.form.get('peso') or None
        altura = request.form.get('altura') or None
        glucemia = request.form.get('glucemia') or None
        insulina_utilizada = val('insulina_utilizada') or None

        tipo_diabetes = val('tipo_diabetes') or None
        hba1c = val('hba1c') or None
        notas_clinica = val('notas_clinica') or None

        esp = (cita.get('especialidad') or '').strip()
        notas_libres = val('notas_extra')
        extra = {}

        if esp == 'Oftalmología':
            extra['Agudeza visual'] = val('agudeza_visual')
            extra['PIO'] = val('pio')
        elif esp == 'Cardiología':
            extra['Frecuencia cardíaca'] = val('fc')
            if presion_arterial:
                extra['Tensión arterial'] = presion_arterial
        elif esp == 'Neurología':
            extra['Reflejos'] = val('reflejos')
            extra['Coordinación'] = val('coordinacion')
        elif esp == 'Clínica':
            extra['Examen físico'] = val('examen_fisico')
            extra['Diagnóstico diferencial'] = val('diagnostico_diferencial')
        elif esp == 'Endocrinología':
            if glucemia:
                extra['Glucemia'] = glucemia
            if insulina_utilizada:
                extra['Insulina utilizada'] = insulina_utilizada
            if peso:
                extra['Peso'] = peso
            if altura:
                extra['Altura'] = altura
            if tipo_diabetes:
                extra['Tipo de diabetes'] = tipo_diabetes
            if hba1c:
                extra['HbA1c'] = hba1c

        if extra or notas_libres:
            payload = {}
            if notas_libres:
                payload['Notas'] = notas_libres
            payload.update({k: v for k, v in extra.items() if v})
            notas_extra = json.dumps(payload, ensure_ascii=False)
        else:
            notas_extra = None

        conn = obtener_conexion()
        with conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO atenciones
                (cita_id, fecha, observaciones, diagnostico, tratamiento, recetas,
                 indicaciones, estudios_pedidos, sintomas, notas_extra, proxima_fecha,
                 presion_arterial, peso, altura,
                 glucemia, insulina_utilizada, notas_clinica, tipo_diabetes, hba1c)
                VALUES (%s,%s,%s,%s,%s,%s,
                        %s,%s,%s,%s,%s,
                        %s,%s,%s,%s,
                        %s,%s,%s,%s,%s)
            """, (
                cita_id, fecha, observaciones, diagnostico, tratamiento, recetas,
                indicaciones, estudios_pedidos, sintomas, notas_extra, proxima_fecha,
                presion_arterial, peso, altura,
                glucemia, insulina_utilizada, notas_clinica, tipo_diabetes, hba1c
            ))
            conn.commit()
        conn.close()

        # Volver al calendario del mes correspondiente a la cita
        fecha_cita = cita.get('fecha')
        if fecha_cita and hasattr(fecha_cita, 'month') and hasattr(fecha_cita, 'year'):
            return redirect(url_for('citas.calendario', mes=fecha_cita.month, anio=fecha_cita.year))

        return redirect(url_for('citas.calendario'))

    return render_template('registrar_atencion.html', cita=cita)


@atenciones_bp.route('/atencion/<int:atencion_id>/ver')
def ver_atencion(atencion_id):
    if 'usuario' not in session:
        return redirect(url_for('auth.login'))

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

    if not r:
        abort(404)

    peso, altura = r.get('peso'), r.get('altura')
    imc = imc_cat = None
    try:
        if peso and altura:
            alt = float(altura)
            if alt > 3:
                alt = alt / 100.0
            imc = round(float(peso) / (alt ** 2), 2)
            imc_cat = (
                "Bajo peso" if imc < 18.5 else
                "Normal" if imc < 25 else
                "Sobrepeso" if imc < 30 else "Obesidad"
            )
    except Exception:
        pass

    hba_cat = None
    try:
        h = float(str(r.get('hba1c') or '').replace(',', '.'))
        hba_cat = "Normal" if h < 5.7 else ("Prediabetes" if h < 6.5 else "Diabetes")
    except Exception:
        pass

    notas_extra = r.get('notas_extra')
    try:
        notas_extra = json.loads(notas_extra) if notas_extra else {}
    except Exception:
        notas_extra = {}

    atencion = dict(r)
    atencion.update({
        "imc": imc,
        "imc_cat": imc_cat,
        "hba1c_cat": hba_cat
    })

    return render_template(
        'detalle_atencion.html',
        atencion=atencion,
        notas_extra=notas_extra
    )


@atenciones_bp.route('/atencion/<int:atencion_id>/detalle', methods=['GET'])
def detalle_atencion_json(atencion_id):
    if 'usuario' not in session:
        return jsonify({"ok": False, "error": "No autorizado"}), 401

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

        def to_primitive(v):
            if isinstance(v, (datetime, date)):
                return v.strftime("%Y-%m-%d %H:%M")
            if isinstance(v, Decimal):
                return float(v)
            return v

        r = {k: to_primitive(v) for k, v in r.items()}

        ne = r.get("notas_extra")
        if isinstance(ne, str) and ne.strip():
            try:
                r["notas_extra"] = json.loads(ne)
            except Exception:
                pass
        elif ne is None:
            r["notas_extra"] = {}

        try:
            peso = float(r["peso"]) if r.get("peso") not in (None, "", "NULL") else None
            altura = float(r["altura"]) if r.get("altura") not in (None, "", "NULL") else None
            if peso and altura:
                alt = altura / 100.0 if altura > 3 else altura
                imc = round(peso / (alt ** 2), 2)
                r["imc"] = imc
                r["imc_cat"] = (
                    "Bajo peso" if imc < 18.5 else
                    "Normal" if imc < 25 else
                    "Sobrepeso" if imc < 30 else "Obesidad"
                )
        except Exception:
            pass

        try:
            h = float(str(r.get("hba1c") or "").replace(",", "."))
            r["hba1c_cat"] = "Normal" if h < 5.7 else ("Prediabetes" if h < 6.5 else "Diabetes")
        except Exception:
            r["hba1c_cat"] = None

        return jsonify({"ok": True, "data": r})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@atenciones_bp.route('/historial_atenciones/<int:cliente_id>')
def historial_atenciones(cliente_id):
    if 'usuario' not in session:
        return redirect(url_for('auth.login'))

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

    if not cliente:
        abort(404)

    return render_template(
        'historial_atenciones.html',
        cliente=cliente,
        atenciones=atenciones
    )