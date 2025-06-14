from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import connection
from datetime import datetime
import logging
logger = logging.getLogger(__name__)

def es_admin(request):
    user_id = request.session.get('user_id')
    if not user_id:
        return False
    
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT r.nombre
                FROM Usuario u
                JOIN Rol r ON u.id_rol = r.id_rol
                WHERE u.id_usuario = %s
                """,
                [user_id]
            )
            rol = cursor.fetchone()
            if rol:
                return rol[0] == 'Administrador'
            return False
    except Exception as e:
        print(f"Error al verificar rol: {str(e)}")
        return False

# Panel de administración
def admin_panel(request):
    if not es_admin(request):
        if request.session.get('user_id'):
            messages.error(request, 'No tienes permisos para acceder a esta página.')
            return redirect('dashboard')
        else:
            return redirect('login')

    current_date_time = datetime.now().strftime("%I:%M %p -%H, %A %d de %B de %Y")
    response = render(request, 'administrador/admin.html', {'current_date_time': current_date_time})
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

def admin_usuarios(request):
    if not es_admin(request):
        if request.session.get('user_id'):
            messages.error(request, 'No tienes permisos para acceder a esta página.')
            return redirect('dashboard')
        else:
            return redirect('login')

    usuarios = []
    roles = []
    permisos = []
    try:
        with connection.cursor() as cursor:
            if request.method == 'POST':
                action = request.POST.get('action')
                if action == 'update':
                    id_usuario = request.POST.get('id_usuario')
                    rol_seleccionado = request.POST.get('rol')
                    permisos_seleccionados = request.POST.get('permisos', '').split(',')

                    cursor.execute("SELECT id_rol FROM Rol WHERE nombre = %s", [rol_seleccionado])
                    selected_rol_id_result = cursor.fetchone()
                    if not selected_rol_id_result:
                        raise Exception(f"Rol '{rol_seleccionado}' no encontrado.")
                    selected_rol_id = selected_rol_id_result[0]

                    cursor.execute(
                        "UPDATE Usuario SET id_rol = %s WHERE id_usuario = %s",
                        [selected_rol_id, id_usuario]
                    )

                    cursor.execute("DELETE FROM Usuario_Permiso WHERE id_usuario = %s", [id_usuario])
                    for permiso in permisos_seleccionados:
                        if permiso:
                            cursor.execute("SELECT id_permiso FROM Permiso WHERE nombre = %s", [permiso])
                            id_permiso_result = cursor.fetchone()
                            if id_permiso_result:
                                id_permiso = id_permiso_result[0]
                                cursor.execute(
                                    "INSERT INTO Usuario_Permiso (id_usuario, id_permiso) VALUES (%s, %s)",
                                    [id_usuario, id_permiso]
                                )

                    connection.commit()
                    messages.success(request, "Usuario actualizado correctamente.")
                elif action == 'add':
                    nombre = request.POST.get('nombre')
                    correo = request.POST.get('correo')
                    telefono = request.POST.get('telefono')
                    balance_puntos = request.POST.get('balance_puntos', 0)
                    rol_seleccionado = request.POST.get('rol')
                    contraseña = request.POST.get('contraseña')  # Generar o recibir contraseña

                    cursor.execute("SELECT id_rol FROM Rol WHERE nombre = %s", [rol_seleccionado])
                    selected_rol_id_result = cursor.fetchone()
                    if not selected_rol_id_result:
                        raise Exception(f"Rol '{rol_seleccionado}' no encontrado.")
                    selected_rol_id = selected_rol_id_result[0]

                    # Insertar nuevo usuario (contraseña debe ser hasheada en producción)
                    cursor.execute(
                        """
                        INSERT INTO Usuario (nombre, correo, telefono, balance_puntos, contraseña, id_rol, fecha_registro)
                        VALUES (%s, %s, %s, %s, %s, %s, NOW())
                        """,
                        [nombre, correo, telefono, balance_puntos, contraseña, selected_rol_id]
                    )
                    connection.commit()
                    messages.success(request, "Usuario añadido correctamente.")

                return redirect('admin_usuarios')

            # Obtener lista de usuarios (sin contraseña)
            cursor.execute(
                """
                SELECT 
                    u.id_usuario,
                    u.nombre,
                    u.correo,
                    u.telefono,
                    u.balance_puntos,
                    DATE_FORMAT(u.fecha_registro, '%d/%m/%Y') AS fecha_registro,
                    r.nombre AS rol
                FROM Usuario u
                JOIN Rol r ON u.id_rol = r.id_rol
                """
            )
            usuarios_raw = cursor.fetchall()

            # Procesar cada usuario para incluir permisos
            for usuario in usuarios_raw:
                id_usuario = usuario[0]
                cursor.execute("SELECT id_rol FROM Usuario WHERE id_usuario = %s", [id_usuario])
                id_rol = cursor.fetchone()[0]

                # Obtener permisos personalizados
                cursor.execute(
                    """
                    SELECT p.nombre
                    FROM Usuario_Permiso up
                    JOIN Permiso p ON up.id_permiso = p.id_permiso
                    WHERE up.id_usuario = %s
                    """,
                    [id_usuario]
                )
                permisos_personalizados = [row[0] for row in cursor.fetchall()]

                # Si no hay permisos personalizados, obtener los del rol
                if not permisos_personalizados:
                    cursor.execute(
                        """
                        SELECT p.nombre
                        FROM Rol_Permiso rp
                        JOIN Permiso p ON rp.id_permiso = p.id_permiso
                        WHERE rp.id_rol = %s
                        """,
                        [id_rol]
                    )
                    permisos_personalizados = [row[0] for row in cursor.fetchall()]

                permisos_str = ", ".join(permisos_personalizados) if permisos_personalizados else ""
                rol_permisos = f"{usuario[6]}: {permisos_str}" if permisos_str else usuario[6]
                usuarios.append(usuario[:6] + (rol_permisos,))

            # Obtener roles y permisos disponibles
            cursor.execute("SELECT nombre FROM Rol")
            roles = [row[0] for row in cursor.fetchall()]

            cursor.execute("SELECT nombre FROM Permiso")
            permisos = [row[0] for row in cursor.fetchall()]

            # Manejo de nuevos roles y permisos
            nuevo_permiso = request.POST.get('nuevo_permiso')
            nuevo_rol = request.POST.get('nuevo_rol')
            if nuevo_permiso and request.method == 'POST':
                cursor.execute("SELECT nombre FROM Permiso WHERE nombre = %s", [nuevo_permiso])
                if not cursor.fetchone():
                    cursor.execute("INSERT INTO Permiso (nombre) VALUES (%s)", [nuevo_permiso])
                    connection.commit()
                    permisos.append(nuevo_permiso)
            if nuevo_rol and request.method == 'POST':
                cursor.execute("SELECT nombre FROM Rol WHERE nombre = %s", [nuevo_rol])
                if not cursor.fetchone():
                    cursor.callproc('insertar_rol', [nuevo_rol, ''])  # Asegúrate de que este procedimiento existe
                    connection.commit()
                    roles.append(nuevo_rol)

    except Exception as e:
        messages.error(request, f"Error al cargar usuarios: {str(e)}")

    response = render(request, 'administrador/admin_usuarios.html', {
        'usuarios': usuarios,
        'roles': roles,
        'permisos': permisos
    })
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

# Otras vistas de admin (ajustadas con cabeceras de caché)
def admin_registros(request):
    if not es_admin(request):
        if request.session.get('user_id'):
            messages.error(request, 'No tienes permisos para acceder a esta página.')
            return redirect('dashboard')
        else:
            return redirect('login')
    registros = []
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT 
                    rr.id_registro_reciclaje,
                    u.nombre AS nombre_usuario,
                    u.correo AS correo_usuario,
                    pr.nombre AS nombre_punto,
                    rr.cantidad_kg,
                    rr.puntos_obtenidos,
                    rr.co2_reducido,
                    rr.fecha_registro,
                    rr.nombre_subtipo AS nombre_material
                FROM Registro_Reciclaje rr
                LEFT JOIN Usuario u ON rr.id_usuario = u.id_usuario
                LEFT JOIN Punto_Reciclaje pr ON rr.id_punto_reciclaje = pr.id_punto_reciclaje
                """
            )
            registros = cursor.fetchall()
    except Exception as e:
        messages.error(request, f'Error al cargar registros: {str(e)}')
    response = render(request, 'administrador/registros.html', {'registros': registros})
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

def admin_catalogo(request):
    if not es_admin(request):
        if request.session.get('user_id'):
            messages.error(request, 'No tienes permisos para acceder a esta página.')
            return redirect('dashboard')
        else:
            return redirect('login')
    recompensas = []
    try:
        with connection.cursor() as cursor:
            if request.method == 'POST':
                action = request.POST.get('action')
                id_recompensa = request.POST.get('id_recompensa')
                if action == 'delete':
                    # Verificar si hay canjes asociados
                    cursor.execute(
                        "SELECT COUNT(*) FROM Canje_Recompensa WHERE id_catalogo_recompensa = %s",
                        [id_recompensa]
                    )
                    canjes_existentes = cursor.fetchone()[0]
                    if canjes_existentes > 0:
                        messages.error(request, "No se puede eliminar esta recompensa porque tiene canjes asociados.")
                    else:
                        # Verificar bitácoras asociadas
                        cursor.execute(
                            "SELECT COUNT(*) FROM Bitacora_Catalogo WHERE id_catalogo_recompensa = %s",
                            [id_recompensa]
                        )
                        bitacoras_existentes = cursor.fetchone()[0]
                        if bitacoras_existentes > 0:
                            # Desactivar en lugar de eliminar
                            cursor.execute(
                                "UPDATE Catalogo_Recompensa SET disponible = FALSE WHERE id_catalogo_recompensa = %s",
                                [id_recompensa]
                            )
                            connection.commit()
                            messages.success(request, "Recompensa desactivada correctamente (no eliminada por bitácoras asociadas).")
                        else:
                            cursor.execute("DELETE FROM Catalogo_Recompensa WHERE id_catalogo_recompensa = %s", [id_recompensa])
                            connection.commit()
                            messages.success(request, "Recompensa eliminada correctamente.")
                elif action == 'add':
                    nombre = request.POST.get('nombre')
                    puntos_coste = request.POST.get('puntos_coste')
                    disponible = request.POST.get('disponible') == 'on'
                    stock = request.POST.get('stock')
                    descuento = request.POST.get('descuento')
                    categoria = request.POST.get('categoria')
                    cursor.execute("SELECT COALESCE(MAX(id_catalogo_recompensa), 0) + 1 FROM Catalogo_Recompensa")
                    nuevo_id = cursor.fetchone()[0]
                    ruta_imagen = f'img/catalogo/img-{nuevo_id}.png'
                    cursor.callproc('insertar_catalogo_recompensa', [
                        nombre, puntos_coste, disponible, stock, descuento, categoria, ruta_imagen
                    ])
                    connection.commit()
                    messages.success(request, "Recompensa agregada correctamente.")
                else:  # update
                    nombre = request.POST.get('nombre')
                    puntos_coste = request.POST.get('puntos_coste')
                    disponible = request.POST.get('disponible') == 'on'
                    stock = request.POST.get('stock')
                    descuento = request.POST.get('descuento')
                    categoria = request.POST.get('categoria')
                    cursor.execute(
                        """
                        UPDATE Catalogo_Recompensa
                        SET nombre = %s, puntos_coste = %s, disponible = %s, stock = %s, descuento = %s, categoria = %s
                        WHERE id_catalogo_recompensa = %s
                        """,
                        [nombre, puntos_coste, disponible, stock, descuento, categoria, id_recompensa]
                    )
                    connection.commit()
                    messages.success(request, "Recompensa actualizada correctamente.")
                return redirect('admin_catalogo')
            cursor.execute(
                """
                SELECT id_catalogo_recompensa, nombre, puntos_coste, disponible, stock, descuento, categoria, ruta_imagen
                FROM Catalogo_Recompensa
                """
            )
            recompensas = cursor.fetchall()
    except Exception as e:
        messages.error(request, f"Error al cargar recompensas: {str(e)}")
    response = render(request, 'administrador/admin_catalogo.html', {'recompensas': recompensas})
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

def admin_donacion(request):
    if not es_admin(request):
        if request.session.get('user_id'):
            messages.error(request, 'No tienes permisos para acceder a esta página.')
            return redirect('dashboard')
        else:
            return redirect('login')
    donaciones = []
    try:
        with connection.cursor() as cursor:
            if request.method == 'POST':
                action = request.POST.get('action')
                id_donacion = request.POST.get('id_donacion')
                if action == 'delete':
                    # Verificar si hay canjes asociados
                    cursor.execute(
                        "SELECT COUNT(*) FROM Canje_Donacion WHERE id_donacion = %s",
                        [id_donacion]
                    )
                    canjes_existentes = cursor.fetchone()[0]
                    if canjes_existentes > 0:
                        messages.error(request, "No se puede eliminar esta donación porque tiene canjes asociados.")
                    else:
                        cursor.execute("DELETE FROM Donacion WHERE id_donacion = %s", [id_donacion])
                        connection.commit()
                        messages.success(request, "Donación eliminada correctamente.")
                elif action == 'add':
                    nombre = request.POST.get('nombre')
                    entidad_donacion = request.POST.get('entidad_donacion')
                    monto_donacion = request.POST.get('monto_donacion')
                    # Generar una ruta de imagen basada en el siguiente ID
                    cursor.execute("SELECT COALESCE(MAX(id_donacion), 0) + 1 FROM Donacion")
                    nuevo_id = cursor.fetchone()[0]
                    ruta_imagen = f'img/donacion/img-{nuevo_id}.png'
                    cursor.execute(
                        "INSERT INTO Donacion (nombre, entidad_donacion, monto_donacion, ruta_imagen) VALUES (%s, %s, %s, %s)",
                        [nombre, entidad_donacion, monto_donacion, ruta_imagen]
                    )
                    connection.commit()
                    messages.success(request, "Donación añadida correctamente.")
                else:  # update
                    nombre = request.POST.get('nombre')
                    entidad_donacion = request.POST.get('entidad_donacion')
                    monto_donacion = request.POST.get('monto_donacion')
                    cursor.execute(
                        "UPDATE Donacion SET nombre = %s, entidad_donacion = %s, monto_donacion = %s WHERE id_donacion = %s",
                        [nombre, entidad_donacion, monto_donacion, id_donacion]
                    )
                    connection.commit()
                    messages.success(request, "Donación actualizada correctamente.")
                return redirect('admin_donacion')
            cursor.execute("SELECT id_donacion, nombre, entidad_donacion, monto_donacion, ruta_imagen FROM Donacion")
            donaciones = cursor.fetchall()
    except Exception as e:
        messages.error(request, f"Error al cargar donaciones: {str(e)}")
    response = render(request, 'administrador/admin_donacion.html', {'donaciones': donaciones})
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

def admin_puntos(request):
    if not es_admin(request):
        if request.session.get('user_id'):
            messages.error(request, 'No tienes permisos para acceder a esta página.')
            return redirect('dashboard')
        else:
            return redirect('login')

    puntos_reciclaje = []
    materiales = []
    try:
        with connection.cursor() as cursor:
            # Obtener todos los materiales reciclables
            cursor.execute("SELECT id_material_reciclable, nombre FROM Material_Reciclable")
            materiales = cursor.fetchall()

            # Obtener lista de puntos de reciclaje con sus materiales y condiciones
            cursor.execute("""
                SELECT 
                    pr.id_punto_reciclaje,
                    pr.nombre,
                    pr.capacidad_maxima,
                    pr.hora_apertura,
                    pr.hora_cierre,
                    pr.latitud,
                    pr.longitud,
                    pr.estado_punto,
                    GROUP_CONCAT(CONCAT(mr.id_material_reciclable, ':', COALESCE(mpr.condiciones_especificas, '')) SEPARATOR ',') as material_conditions,
                    GROUP_CONCAT(mr.nombre SEPARATOR ', ') as materiales_permitidos
                FROM Punto_Reciclaje pr
                LEFT JOIN Material_Punto_Reciclaje mpr ON pr.id_punto_reciclaje = mpr.id_punto_reciclaje
                LEFT JOIN Material_Reciclable mr ON mpr.id_material_reciclable = mr.id_material_reciclable
                GROUP BY pr.id_punto_reciclaje, pr.nombre, pr.capacidad_maxima, pr.hora_apertura, 
                         pr.hora_cierre, pr.latitud, pr.longitud, pr.estado_punto
            """)
            puntos_reciclaje = cursor.fetchall()

            if request.method == 'POST':
                action = request.POST.get('action')
                if action == 'add':
                    nombre = request.POST.get('nombre')
                    capacidad_maxima = request.POST.get('capacidad_maxima')
                    hora_apertura = request.POST.get('hora_apertura')
                    hora_cierre = request.POST.get('hora_cierre')
                    latitud = request.POST.get('latitud')
                    longitud = request.POST.get('longitud')
                    estado_punto = request.POST.get('estado_punto')
                    materiales_seleccionados = request.POST.getlist('materiales')
                    condiciones = request.POST.getlist('condiciones')  # Lista de condiciones
                    if not all([nombre, capacidad_maxima, hora_apertura, hora_cierre, latitud, longitud, estado_punto]):
                        messages.error(request, 'Todos los campos son obligatorios.')
                    elif int(capacidad_maxima) < 0:
                        messages.error(request, 'La capacidad máxima no puede ser negativa.')
                    elif hora_apertura >= hora_cierre:
                        messages.error(request, 'La hora de apertura debe ser anterior a la hora de cierre.')
                    else:
                        cursor.callproc('insertar_punto_reciclaje', [nombre, int(capacidad_maxima), hora_apertura, hora_cierre, float(latitud), float(longitud), estado_punto])
                        cursor.execute("SELECT LAST_INSERT_ID()")
                        new_id = cursor.fetchone()[0]
                        for i, mat_id in enumerate(materiales_seleccionados):
                            condicion = condiciones[i] if i < len(condiciones) else None
                            cursor.callproc('insertar_material_punto_reciclaje', [int(mat_id), new_id, condicion])
                        connection.commit()
                        messages.success(request, 'Punto de reciclaje añadido correctamente.')
                        return redirect('admin_puntos')
                elif action == 'edit':
                    id_punto_reciclaje = int(request.POST.get('id_punto_reciclaje'))
                    nombre = request.POST.get('nombre')
                    capacidad_maxima = request.POST.get('capacidad_maxima')
                    hora_apertura = request.POST.get('hora_apertura')
                    hora_cierre = request.POST.get('hora_cierre')
                    latitud = request.POST.get('latitud')
                    longitud = request.POST.get('longitud')
                    estado_punto = request.POST.get('estado_punto')
                    materiales_seleccionados = request.POST.getlist('materiales')
                    condiciones = request.POST.getlist('condiciones')
                    if not all([nombre, capacidad_maxima, hora_apertura, hora_cierre, latitud, longitud, estado_punto]):
                        messages.error(request, 'Todos los campos son obligatorios.')
                    elif int(capacidad_maxima) < 0:
                        messages.error(request, 'La capacidad máxima no puede ser negativa.')
                    elif hora_apertura >= hora_cierre:
                        messages.error(request, 'La hora de apertura debe ser anterior a la hora de cierre.')
                    else:
                        cursor.callproc('actualizar_punto_reciclaje', [id_punto_reciclaje, nombre, int(capacidad_maxima), hora_apertura, hora_cierre, float(latitud), float(longitud), estado_punto])
                        cursor.execute("DELETE FROM Material_Punto_Reciclaje WHERE id_punto_reciclaje = %s", [id_punto_reciclaje])
                        for i, mat_id in enumerate(materiales_seleccionados):
                            condicion = condiciones[i] if i < len(condiciones) else None
                            cursor.callproc('insertar_material_punto_reciclaje', [int(mat_id), id_punto_reciclaje, condicion])
                        connection.commit()
                        messages.success(request, 'Punto de reciclaje actualizado correctamente.')
                        return redirect('admin_puntos')
            elif request.method == 'GET' and request.GET.get('action') == 'delete':
                id_punto_reciclaje = int(request.GET.get('id'))
                cursor.execute("DELETE FROM Material_Punto_Reciclaje WHERE id_punto_reciclaje = %s", [id_punto_reciclaje])
                cursor.callproc('eliminar_punto_reciclaje', [id_punto_reciclaje])
                connection.commit()
                messages.success(request, 'Punto de reciclaje eliminado correctamente.')
                return redirect('admin_puntos')

    except Exception as e:
        messages.error(request, f'Error al procesar puntos de reciclaje: {str(e)}')

    response = render(request, 'administrador/admin_puntos.html', {'puntos_reciclaje': puntos_reciclaje, 'materiales': materiales})
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

def admin_historial(request):
    if not es_admin(request):
        if request.session.get('user_id'):
            messages.error(request, 'No tienes permisos para acceder a esta página.')
            return redirect('dashboard')
        else:
            return redirect('login')

    historial_acceso = []
    try:
        with connection.cursor() as cursor:
            # Consulta ajustada para mostrar fecha y hora
            cursor.execute(
                "SELECT id_bitacora_acceso, id_usuario, tipo_acceso, DATE_FORMAT(fecha_acceso, '%Y-%m-%d %H:%i:%s') AS fecha_acceso, resultado, detalle FROM Bitacora_Acceso ORDER BY fecha_acceso DESC"
            )
            historial_acceso = cursor.fetchall()
    except Exception as e:
        messages.error(request, f'Error al cargar el historial: {str(e)}')
        logger.error(f"Error al obtener historial: {str(e)}")

    response = render(request, 'administrador/admin_historial.html', {'historial_acceso': historial_acceso})
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

def bitacora_reciclaje(request):
    if not es_admin(request):
        if request.session.get('user_id'):
            messages.error(request, 'No tienes permisos para acceder a esta página.')
            return redirect('dashboard')
        else:
            return redirect('login')
    bitacora = []
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id_bitacora_reciclaje, ip, id_registro_reciclaje, accion, 
                       DATE_FORMAT(fecha_accion, '%%d/%%m/%%Y %%H:%%i') AS fecha_accion, detalle
                FROM Bitacora_Reciclaje
                """
            )
            bitacora = cursor.fetchall()
    except Exception as e:
        messages.error(request, f'Error al cargar bitácora: {str(e)}')
    response = render(request, 'administrador/bitacora_reciclaje.html', {'bitacora': bitacora})
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

def bitacora_catalogo(request):
    if not es_admin(request):
        if request.session.get('user_id'):
            messages.error(request, 'No tienes permisos para acceder a esta página.')
            return redirect('dashboard')
        else:
            return redirect('login')
    bitacora = []
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id_bitacora_catalogo, ip, id_catalogo_recompensa, accion, 
                       DATE_FORMAT(fecha_accion, '%%d/%%m/%%Y %%H:%%i') AS fecha_accion, detalle
                FROM Bitacora_Catalogo
                """
            )
            bitacora = cursor.fetchall()
    except Exception as e:
        messages.error(request, f'Error al cargar bitácora: {str(e)}')
    response = render(request, 'administrador/bitacora_catalogo.html', {'bitacora': bitacora})
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response

def bitacora_canje(request):
    if not es_admin(request):
        if request.session.get('user_id'):
            messages.error(request, 'No tienes permisos para acceder a esta página.')
            return redirect('dashboard')
        else:
            return redirect('login')
    bitacora = []
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id_bitacora_canje, ip, id_canje_recompensa, id_catalogo_recompensa, accion, 
                       DATE_FORMAT(fecha_accion, '%%d/%%m/%%Y %%H:%%i') AS fecha_accion, detalle
                FROM Bitacora_Canje
                """
            )
            bitacora = cursor.fetchall()
    except Exception as e:
        messages.error(request, f'Error al cargar bitácora: {str(e)}')
    response = render(request, 'administrador/bitacora_canje.html', {'bitacora': bitacora})
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response