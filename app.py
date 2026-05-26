from flask import Flask
from routes.auth import auth_bp
from routes.clientes import clientes_bp
from routes.doctores import doctores_bp
from routes.citas import citas_bp
from routes.atenciones import atenciones_bp
from routes.reportes import reportes_bp

app = Flask(__name__)
app.secret_key = 'clave_secreta'

app.register_blueprint(auth_bp)
app.register_blueprint(clientes_bp)
app.register_blueprint(doctores_bp)
app.register_blueprint(citas_bp)
app.register_blueprint(atenciones_bp)
app.register_blueprint(reportes_bp)

if __name__ == '__main__':
    app.run(debug=True)