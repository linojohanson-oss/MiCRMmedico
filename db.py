import pymysql

def obtener_conexion(dict_cursor=False):
    try:
        cursor_type = pymysql.cursors.DictCursor if dict_cursor else pymysql.cursors.Cursor
        return pymysql.connect(
            host='localhost',
            user='root',
            password='',
            database='mi_crm',
            cursorclass=cursor_type
        )
    except Exception as e:
        print("Error de conexion:", e)
        return None