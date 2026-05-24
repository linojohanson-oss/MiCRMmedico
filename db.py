import os
import pymysql

def obtener_conexion(dict_cursor=False):
    try:
        cursor_type = pymysql.cursors.DictCursor if dict_cursor else pymysql.cursors.Cursor

        return pymysql.connect(
            host=os.getenv("MYSQLHOST"),
            user=os.getenv("MYSQLUSER"),
            password=os.getenv("MYSQLPASSWORD"),
            database=os.getenv("MYSQLDATABASE"),
            port=int(os.getenv("MYSQLPORT")),
            cursorclass=cursor_type
        )

    except Exception as e:
        print("Error de conexion:", e)
        return None