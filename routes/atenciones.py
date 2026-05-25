from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from db import obtener_conexion
from datetime import datetime
import json
import os
import smtplib
import resend
from email.message import EmailMessage

atenciones_bp = Blueprint('atenciones', __name__)


@atenciones_bp.route('/atencion/<int:cita_id>', methods=['GET', 'POST'])
def registrar_atencion(cita_id):
    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT c.id,
               c.cliente_id,
               c.fecha,
               cl.nombre,
               d.nombre,
               d.especialidad
        FROM citas c
        JOIN clientes cl ON c.cliente_id = cl.id
        JOIN doctores d ON c.doctor_id = d.id
        WHERE c.id = %s
    """, (cita_id,))

    cita = cursor.fetchone()

    if not cita:
        cursor.close()
        conn.close()
        flash("Cita no encontrada", "danger")
        return redirect(url_for('clientes.index'))

    if request.method == 'POST':
        observaciones = request.form.get('observaciones')
        diagnostico = request.form.get('diagnostico')
        tratamiento = request.form.get('tratamiento')
        recetas = request.form.get('recetas')
        indicaciones = request.form.get('indicaciones')
        estudios_pedidos = request.form.get('estudios_pedidos')
        sintomas = request.form.get('sintomas')
        proxima_fecha = request.form.get('proxima_fecha')

        presion_arterial_clinica = request.form.get('presion_arterial_clinica')
        notas_clinica = request.form.get('notas_clinica')

        peso = request.form.get('peso')
        altura = request.form.get('altura')
        glucemia = request.form.get('glucemia')
        insulina_utilizada = request.form.get('insulina_utilizada')
        tipo_diabetes = request.form.get('tipo_diabetes')
        hba1c = request.form.get('hba1c')

        especialidad = cita[5]

        notas_extra = {}

        if especialidad == 'Cardiología':
            notas_extra['frecuencia_cardiaca'] = request.form.get('frecuencia_cardiaca')
            notas_extra['presion_arterial'] = request.form.get('presion_arterial')

        elif especialidad == 'Neurología':
            notas_extra['reflejos'] = request.form.get('reflejos')
            notas_extra['coordinacion'] = request.form.get('coordinacion')

        elif especialidad == 'Oftalmología':
            notas_extra['agudeza_visual'] = request.form.get('agudeza_visual')
            notas_extra['presion_intraocular'] = request.form.get('presion_intraocular')

        elif especialidad == 'Clínica':
            notas_extra['examen_fisico'] = request.form.get('examen_fisico')
            notas_extra['diagnostico_diferencial'] = request.form.get('diagnostico_diferencial')

        notas_extra_json = json.dumps(notas_extra, ensure_ascii=False)

        cursor.execute("""
            INSERT INTO atenciones (
                cita_id,
                fecha,
                observaciones,
                diagnostico,
                tratamiento,
                recetas,
                indicaciones,
                estudios_pedidos,
                sintomas,
                proxima_fecha,
                peso,
                altura,
                glucemia,
                insulina_utilizada,
                notas_clinica,
                tipo_diabetes,
                hba1c,
                notas_extra
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s
            )
        """, (
            cita_id,
            datetime.now(),
            observaciones,
            diagnostico,
            tratamiento,
            recetas,
            indicaciones,
            estudios_pedidos,
            sintomas,
            proxima_fecha,
            peso,
            altura,
            glucemia,
            insulina_utilizada,
            notas_clinica,
            tipo_diabetes,
            hba1c,
            notas_extra_json
        ))

        conn.commit()
        cursor.close()
        conn.close()

        flash("Atención registrada correctamente", "success")
        return redirect(url_for('citas.ver_citas', cliente_id=cita[1]))

    cursor.close()
    conn.close()

    return render_template('registrar_atencion.html', cita=cita)


@atenciones_bp.route('/atencion/<int:atencion_id>/ver')
def ver_atencion(atencion_id):
    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT a.*,
               cl.nombre,
               d.nombre,
               d.especialidad
        FROM atenciones a
        JOIN citas c ON a.cita_id = c.id
        JOIN clientes cl ON c.cliente_id = cl.id
        JOIN doctores d ON c.doctor_id = d.id
        WHERE a.id = %s
    """, (atencion_id,))

    atencion = cursor.fetchone()

    cursor.close()
    conn.close()

    if not atencion:
        flash("Atención no encontrada", "danger")
        return redirect(url_for('clientes.index'))

    return render_template('detalle_atencion.html', atencion=atencion)


@atenciones_bp.route('/atencion/<int:atencion_id>/detalle')
def detalle_atencion_json(atencion_id):
    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT a.*,
               cl.nombre AS cliente_nombre,
               d.nombre AS doctor_nombre,
               d.especialidad
        FROM atenciones a
        JOIN citas c ON a.cita_id = c.id
        JOIN clientes cl ON c.cliente_id = cl.id
        JOIN doctores d ON c.doctor_id = d.id
        WHERE a.id = %s
    """, (atencion_id,))

    row = cursor.fetchone()

    if not row:
        cursor.close()
        conn.close()
        return jsonify({"error": "No encontrada"}), 404

    columnas = [col[0] for col in cursor.description]

    cursor.close()
    conn.close()

    data = {}

    for i, col in enumerate(columnas):
        valor = row[i]

        if isinstance(valor, datetime):
            valor = valor.strftime('%d/%m/%Y %H:%M')

        data[col] = valor

    try:
        if data.get('notas_extra'):
            data['notas_extra'] = json.loads(data['notas_extra'])
    except:
        data['notas_extra'] = {}

    try:
        peso = float(data.get('peso') or 0)
        altura = float(data.get('altura') or 0)

        if peso > 0 and altura > 0:
            altura_m = altura / 100
            imc = round(peso / (altura_m ** 2), 2)

            data['imc'] = imc

            if imc < 18.5:
                data['imc_categoria'] = 'Bajo peso'
            elif imc < 25:
                data['imc_categoria'] = 'Normal'
            elif imc < 30:
                data['imc_categoria'] = 'Sobrepeso'
            else:
                data['imc_categoria'] = 'Obesidad'
    except:
        pass

    try:
        hba1c = float(data.get('hba1c') or 0)

        if hba1c < 5.7:
            data['hba1c_categoria'] = 'Normal'
        elif hba1c < 6.5:
            data['hba1c_categoria'] = 'Prediabetes'
        else:
            data['hba1c_categoria'] = 'Diabetes'
    except:
        pass

    return jsonify(data)
@atenciones_bp.route('/historial_atenciones/<int:cliente_id>')
def historial_atenciones(cliente_id):
    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, nombre, correo, telefono
        FROM clientes
        WHERE id = %s
    """, (cliente_id,))
    cliente = cursor.fetchone()

    cursor.execute("""
        SELECT a.id,
               a.fecha,
               a.diagnostico,
               a.tratamiento,
               a.observaciones,
               d.nombre AS doctor_nombre,
               d.especialidad
        FROM atenciones a
        JOIN citas c ON a.cita_id = c.id
        JOIN doctores d ON c.doctor_id = d.id
        WHERE c.cliente_id = %s
        ORDER BY a.fecha DESC
    """, (cliente_id,))
    atenciones = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        'historial_atenciones.html',
        cliente=cliente,
        atenciones=atenciones
    )
from flask import make_response
from fpdf import FPDF


@atenciones_bp.route('/atencion/<int:atencion_id>/receta_pdf')
def receta_pdf(atencion_id):

    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT a.*,
               cl.nombre,
               d.nombre,
               d.especialidad
        FROM atenciones a
        JOIN citas c ON a.cita_id = c.id
        JOIN clientes cl ON c.cliente_id = cl.id
        JOIN doctores d ON c.doctor_id = d.id
        WHERE a.id = %s
    """, (atencion_id,))

    atencion = cursor.fetchone()

    cursor.close()
    conn.close()

    if not atencion:
        return "Atención no encontrada", 404

    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Arial", 'B', 18)
    pdf.cell(0, 10, "Receta Médica", ln=True, align='C')

    pdf.ln(10)

    pdf.set_font("Arial", '', 12)

    pdf.cell(0, 10, f"Paciente: {atencion[18]}", ln=True)
    pdf.cell(0, 10, f"Doctor: {atencion[19]}", ln=True)
    pdf.cell(0, 10, f"Especialidad: {atencion[20]}", ln=True)

    pdf.ln(10)

    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "Recetas / Medicación:", ln=True)

    pdf.set_font("Arial", '', 12)

    receta = atencion[6] if atencion[6] else "Sin recetas registradas"

    pdf.multi_cell(0, 10, receta)

    pdf.ln(15)

    pdf.cell(0, 10, "Firma médica: ____________________", ln=True)

    response = make_response(pdf.output(dest='S').encode('latin-1'))

    response.headers.set(
        'Content-Disposition',
        'attachment',
        filename=f"receta_{atencion_id}.pdf"
    )

    response.headers.set('Content-Type', 'application/pdf')

    return response
@atenciones_bp.route('/atencion/<int:atencion_id>/pdf')
def atencion_pdf(atencion_id):

    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT a.*,
               cl.nombre,
               d.nombre,
               d.especialidad
        FROM atenciones a
        JOIN citas c ON a.cita_id = c.id
        JOIN clientes cl ON c.cliente_id = cl.id
        JOIN doctores d ON c.doctor_id = d.id
        WHERE a.id = %s
    """, (atencion_id,))

    atencion = cursor.fetchone()

    cursor.close()
    conn.close()

    if not atencion:
        return "Atención no encontrada", 404

    pdf = FPDF()
    pdf.add_page()

    # TITULO
    pdf.set_font("Arial", 'B', 20)
    pdf.cell(0, 12, "Informe de Atención Médica", ln=True, align='C')

    pdf.ln(10)

    # DATOS PACIENTE
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "Datos del Paciente", ln=True)

    pdf.set_font("Arial", '', 12)

    pdf.cell(0, 8, f"Paciente: {atencion[18]}", ln=True)
    pdf.cell(0, 8, f"Doctor: {atencion[19]}", ln=True)
    pdf.cell(0, 8, f"Especialidad: {atencion[20]}", ln=True)

    pdf.ln(8)

    # DATOS CLINICOS
    campos = [
        ("Diagnóstico", atencion[3]),
        ("Tratamiento", atencion[4]),
        ("Observaciones", atencion[2]),
        ("Recetas", atencion[5]),
        ("Indicaciones", atencion[6]),
        ("Estudios pedidos", atencion[7]),
        ("Síntomas", atencion[8]),
        ("Peso", atencion[10]),
        ("Altura", atencion[11]),
        ("Glucemia", atencion[12]),
        ("Insulina utilizada", atencion[13]),
        ("Tipo diabetes", atencion[15]),
        ("HbA1c", atencion[16]),
    ]

    for titulo, valor in campos:

        pdf.set_font("Arial", 'B', 13)
        pdf.cell(0, 8, titulo, ln=True)

        pdf.set_font("Arial", '', 12)

        texto = str(valor) if valor else "Sin información"

        pdf.multi_cell(0, 8, texto)

        pdf.ln(2)

    pdf.ln(10)

    pdf.cell(0, 10, "Firma médica: ____________________", ln=True)

    response = make_response(
        pdf.output(dest='S').encode('latin-1')
    )

    response.headers.set(
        'Content-Disposition',
        'attachment',
        filename=f"atencion_{atencion_id}.pdf"
    )

    response.headers.set(
        'Content-Type',
        'application/pdf'
    )

    return response
def enviar_email(destinatario, asunto, cuerpo):

    resend_api_key = os.getenv("RESEND_API_KEY")

    email_from = os.getenv(
        "EMAIL_FROM",
        "CRM Médico <onboarding@resend.dev>"
    )

    if not resend_api_key:
        return False, "Falta RESEND_API_KEY"

    try:

        resend.api_key = resend_api_key

        params = {
            "from": email_from,
            "to": [destinatario],
            "subject": asunto,
            "html": cuerpo.replace("\n", "<br>")
        }

        resend.Emails.send(params)

        return True, "Email enviado correctamente"

    except Exception as e:

        return False, f"Error enviando email con Resend: {str(e)}"

@atenciones_bp.route('/atencion/<int:atencion_id>/enviar_receta')
def enviar_receta_email(atencion_id):
    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT a.id, cl.nombre, cl.correo
        FROM atenciones a
        JOIN citas c ON a.cita_id = c.id
        JOIN clientes cl ON c.cliente_id = cl.id
        WHERE a.id = %s
    """, (atencion_id,))

    data = cursor.fetchone()

    cursor.close()
    conn.close()

    if not data:
        return "Atención no encontrada", 404

    if not data[2]:
        return "El paciente no tiene correo cargado", 400

    link_receta = url_for('atenciones.receta_pdf', atencion_id=atencion_id, _external=True)

    cuerpo = f"""
Hola {data[1]},

Te enviamos el enlace para descargar tu receta médica:

{link_receta}

Saludos,
CRM Médico
"""

    ok, mensaje = enviar_email(
        data[2],
        "Receta médica",
        cuerpo
    )

    if not ok:
        return mensaje, 500

    return "Receta enviada correctamente por email"


@atenciones_bp.route('/atencion/<int:atencion_id>/enviar_pdf')
def enviar_pdf_email(atencion_id):
    conn = obtener_conexion()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT a.id, cl.nombre, cl.correo
        FROM atenciones a
        JOIN citas c ON a.cita_id = c.id
        JOIN clientes cl ON c.cliente_id = cl.id
        WHERE a.id = %s
    """, (atencion_id,))

    data = cursor.fetchone()

    cursor.close()
    conn.close()

    if not data:
        return "Atención no encontrada", 404

    if not data[2]:
        return "El paciente no tiene correo cargado", 400

    link_pdf = url_for('atenciones.atencion_pdf', atencion_id=atencion_id, _external=True)

    cuerpo = f"""
Hola {data[1]},

Te enviamos el enlace para descargar el informe completo de tu atención médica:

{link_pdf}

Saludos,
CRM Médico
"""

    ok, mensaje = enviar_email(
        data[2],
        "Informe de atención médica",
        cuerpo
    )

    if not ok:
        return mensaje, 500

    return "Informe enviado correctamente por email"
