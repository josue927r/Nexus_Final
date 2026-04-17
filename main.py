
from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Request, Response, Depends, Cookie
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
import pandas as pd
from datetime import datetime, timedelta
import io
import csv
import os
import traceback

from typing import List, Optional
from models import BranchInput, GlobalSummary
from services import calculate_cuadratura

# --- DB IMPORTS ---
from database import engine, get_db, Base
from auth_models import User
from security import verify_password
import json

app = FastAPI(title="Motor de Cuadratura Farmacia: iBot vs Transbank")

# Crear tablas
Base.metadata.create_all(bind=engine)

# Servir archivos estáticos (CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")


# --- AUTH SYSTEM ---
COOKIE_NAME = "nexus_session"

async def get_current_user(request: Request, db: Session = Depends(get_db)):
    username = request.cookies.get(COOKIE_NAME)
    if not username:
        return None
    
    try:
        user = db.query(User).filter(User.username == username).first()
        if user:
            return user.username
        return None
    except:
        return None

@app.get("/login")
async def login_page(request: Request, db: Session = Depends(get_db)):
    # Si ya esta logueado, mandar al home
    user = await get_current_user(request, db)
    if user:
         return RedirectResponse(url="/")
    return FileResponse('static/login.html')

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    
    response = JSONResponse(content={"message": "Login exitoso"})
    response.set_cookie(key=COOKIE_NAME, value=user.username, httponly=True)
    return response

@app.get("/register")
async def register_page(request: Request, db: Session = Depends(get_db)):
    user = await get_current_user(request, db)
    if user:
         return RedirectResponse(url="/")
    return FileResponse('static/register.html')

@app.post("/register")
async def register_user(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    from security import get_password_hash
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="El nombre de usuario ya está en uso")
    
    hashed_password = get_password_hash(password)
    new_user = User(username=username, password_hash=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return JSONResponse(content={"message": "Usuario creado exitosamente"})

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie(COOKIE_NAME)
    return response

# --- RUTAS PROTEGIDAS ---

async def get_current_admin(request: Request, db: Session = Depends(get_db)):
    username = request.cookies.get(COOKIE_NAME)
    if not username:
        raise HTTPException(status_code=401, detail="No autenticado")
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_admin:
        raise HTTPException(status_code=403, detail="No tienes permisos de administrador")
    return user

@app.get("/api/me")
async def read_users_me(request: Request, db: Session = Depends(get_db)):
    username = request.cookies.get(COOKIE_NAME)
    if not username:
        raise HTTPException(status_code=401)
    user = db.query(User).filter(User.username == username).first()
    if user:
        return {"username": user.username, "is_admin": user.is_admin}
    raise HTTPException(status_code=401)

@app.get("/admin")
async def admin_page(admin_user: User = Depends(get_current_admin)):
    return FileResponse('static/admin.html')

@app.get("/api/users")
async def get_users(admin_user: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [{"id": u.id, "username": u.username, "is_admin": u.is_admin} for u in users]

@app.delete("/api/users/{user_id}")
async def delete_user(user_id: int, admin_user: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    if admin_user.id == user_id:
        raise HTTPException(status_code=400, detail="No puedes eliminarte a ti mismo")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    db.delete(user)
    db.commit()
    return {"message": "Usuario eliminado"}

@app.patch("/api/users/{user_id}/role")
async def toggle_admin_role(user_id: int, request: Request, admin_user: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    if admin_user.id == user_id:
        raise HTTPException(status_code=400, detail="No puedes modificar tus propios permisos")
    
    data = await request.json()
    is_admin_new = data.get("is_admin")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    user.is_admin = is_admin_new
    db.commit()
    return {"message": "Rol actualizado", "is_admin": user.is_admin}
@app.get("/")
async def read_index(user: Optional[str] = Depends(get_current_user)):
    if not user:
        return RedirectResponse(url="/login")
    return FileResponse('static/index.html')

# --- UTILIDADES DE LIMPIEZA ---

def limpiar_monto(valor):
    """
    Normaliza montos monetarios eliminando $, puntos y comas.
    Ejemplo: '$ 1.990' -> 1990
    """
    if pd.isna(valor):
        return 0
    
    # Si ya es numérico, devolver entero directo
    if isinstance(valor, (int, float)):
        return int(valor)
        
    # Si es string, limpiar formato CLP ($ 1.990)
    s = str(valor).replace('$', '').replace('.', '').replace(',', '').strip()
    try:
        return int(s)
    except ValueError:
        return 0

def parsear_fecha_ibot(fecha_str, orden_str):
    """
    Reconstruye datetime desde el formato iBot.
    Input Fecha: '31-12-2025'
    Input Orden: '323493 - 17:22:09'
    Output: datetime object
    """
    try:
        # Extraer hora del string de Orden
        if ' - ' in str(orden_str):
            hora = str(orden_str).split(' - ')[1]
            fecha_completa = f"{fecha_str} {hora}"
            # Intentar formato con segundos
            return datetime.strptime(fecha_completa, "%d-%m-%Y %H:%M:%S")
    except:
        pass
    return None

def parsear_fecha_transbank(fecha_str, hora_str):
    """
    Reconstruye datetime desde el formato Transbank (CSV/Excel).
    Input Fecha: '31/12/2025'
    Input Hora: '14:49'
    """
    try:
        # Normalizar separadores de fecha
        fecha_clean = str(fecha_str).replace('-', '/')
        fecha_completa = f"{fecha_clean} {hora_str}"
        return datetime.strptime(fecha_completa, "%d/%m/%Y %H:%M")
    except:
        return None

# --- ENDPOINT PRINCIPAL (PROTEGIDO) ---

@app.post("/conciliar-caja/")
async def conciliar_caja(
    file_ibot: UploadFile = File(..., description="Archivo Excel o CSV exportado de iBot"),
    file_transbank: Optional[UploadFile] = File(None, description="Archivo Excel o CSV del portal Transbank (Opcional)"),
    voucher_sistema: int = Form(0),
    voucher_real: int = Form(0),
    shift_start: str = Form(""),
    shift_end: str = Form(""),
    fecha_reporte: str = Form(None), # Nueva fecha manual
    turno: str = Form(None),
    user: Optional[str] = Depends(get_current_user) # AUTH CHECK
):
    if not user: raise HTTPException(status_code=401)
    
    try:
        # 1. CARGA DE ARCHIVOS
        try:
            # Cargar iBot
            contents_ibot = await file_ibot.read()
            df_ibot = None
            
            # Estrategia de carga mejorada
            try:
                # Intento 1: Excel Header 1 (Caso reportado por usuario "Ventas - IBOT" en fila 1)
                df_ibot = pd.read_excel(io.BytesIO(contents_ibot), header=1)
                if not any('total' in c.lower() for c in df_ibot.columns): raise ValueError
            except:
                try:
                    # Intento 2: Excel Header 0
                    df_ibot = pd.read_excel(io.BytesIO(contents_ibot), header=0)
                except:
                    # Intento 3: CSV
                    try:
                        df_ibot = pd.read_csv(io.BytesIO(contents_ibot), header=1)
                    except:
                        df_ibot = pd.read_csv(io.BytesIO(contents_ibot), header=0)

            # Cargar Transbank (Optional)
            df_tb = None
            if file_transbank:
                contents_tb = await file_transbank.read()
                try:
                    df_tb = pd.read_csv(io.BytesIO(contents_tb), header=0)
                except:
                    df_tb = pd.read_excel(io.BytesIO(contents_tb))

        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Error leyendo archivos: {str(e)}")

        # 2. PREPARACIÓN DE DATOS
        
        # Normalizar columnas
        df_ibot.columns = [c.strip() for c in df_ibot.columns]
        if df_tb is not None:
            df_tb.columns = [c.strip().upper() for c in df_tb.columns]

        # -------------------------------------------------------------------------
        # NUEVO: ANÁLISIS DE CONSISTENCIA INTERNA (Raw vs Pivot)
        # -------------------------------------------------------------------------
        
        # Estrategia: Capturar los valores de la Tabla Dinámica (Suma de Total) vs Listado (Total)
        # antes de que las normalizaciones oscurezcan los nombres.
        
        alertas_internas = []
        try:
            from collections import Counter
            
            # 1. Buscar columna PIVOT (La que dice "Suma de Total")
            col_pivot_name = next((c for c in df_ibot.columns if "suma" in c.lower() and "total" in c.lower()), None)
            
            # 2. Buscar columna RAW (La que dice "Total" o "Monto" y TIENE DATOS en las filas donde no hay pivot)
            # Generalmente "TOTAL" o "Total"
            # Ojo: si hay duplicados, pandas los renombra Total, Total.1
            cols_posibles_raw = [c for c in df_ibot.columns if "total" in c.lower() and c != col_pivot_name]
            
            # Heurística: La raw suele estar antes de la pivot en el excel? 
            # O simplemente probamos la primera que encontremos que tenga datos.
            col_raw_name = cols_posibles_raw[0] if cols_posibles_raw else None
            
            if col_pivot_name and col_raw_name:
                # Extraemos valores
                raw_values = df_ibot[col_raw_name].apply(limpiar_monto)
                pivot_values = df_ibot[col_pivot_name].apply(limpiar_monto)
                
                # Filtramos ceros
                raw_nums = raw_values[raw_values > 0].tolist()
                pivot_nums = pivot_values[pivot_values > 0].tolist()
                
                # Si Pivot está vacío (tal vez porque no leyó bien las filas), abortamos para no dar falsos positivos
                if not pivot_nums:
                    pass # Posiblemente no es una tabla dinámica válida o está vacía
                else:
                    c_raw = Counter(raw_nums)
                    c_pivot = Counter(pivot_nums)
                    
                    # 1. Chequeo RAW vs PIVOT (Lo que está en detalle pero no en resumen)
                    diff = c_raw - c_pivot
                    for monto, count in diff.items():
                        for _ in range(count):
                            alertas_internas.append({
                                "monto": monto,
                                "mensaje": f"El monto ${monto:,.0f} aparece en el detalle (Col {col_raw_name}) pero NO en la tabla dinámica ({col_pivot_name})."
                            })

                    # 2. Chequeo PIVOT vs RAW (Lo que está en resumen pero no en detalle)
                    diff_reverse = c_pivot - c_raw
                    for monto, count in diff_reverse.items():
                        for _ in range(count):
                            alertas_internas.append({
                                "monto": monto,
                                "mensaje": f"El monto ${monto:,.0f} aparece en la tabla dinámica ({col_pivot_name}) pero NO en el detalle ({col_raw_name})."
                            })


            
        except Exception as e:
            print(f"Error en análisis interno: {e}")

        # Normalizar columnas (Renames para el resto del proceso)
        # --- SOPORTE FLUO TABLA DINÁMICA (Etiquetas de fila / Suma de Total) ---
        es_tabla_dinamica = False
        if "Etiquetas de fila" in df_ibot.columns:
            es_tabla_dinamica = True
            # Renombrar para estandarizar
            df_ibot.rename(columns={
                "Etiquetas de fila": "Orden", 
                "Suma de Total": "Total"
            }, inplace=True)
            
            # Si existía otra columna "Total" (la Raw), ahora tenemos conflicto. 
            # Pandas no renombra inplace si choca, o si?
            # En la práctica, el resto del código busca 'total' en lower.
            # Lo importante es que YA hicimos el chequeo de consistencia arriba.

        col_total_ibot = next((c for c in df_ibot.columns if 'total' in c.lower()), 'Total')
        
        # Limpieza de Montos
        df_ibot['monto_limpio'] = df_ibot[col_total_ibot].apply(limpiar_monto)
        
        # Detectar columnas clave
        col_orden = next((c for c in df_ibot.columns if 'orden' in c.lower()), 'Orden')
        
        # LÓGICA DE FECHAS MEJORADA
        # Si es tabla dinámica, NO tenemos fecha en el archivo, solo Hora en la columna Orden.
        # Usamos la fecha manual reportada por el usuario.
        
        def parsear_fecha_mix(row):
            # 1. Caso Tabla Dinámica (ID - Hora) + Fecha Manual
            if es_tabla_dinamica and fecha_reporte:
                try:
                    val = str(row[col_orden])
                    if ' - ' in val:
                        hora_str = val.split(' - ')[1].strip() # "22:52:00"
                        fecha_comp = f"{fecha_reporte} {hora_str}"
                        return datetime.strptime(fecha_comp, "%Y-%m-%d %H:%M:%S")
                except:
                    pass
            
            # 2. Caso Estándar iBot (Columna Fecha + Columna Orden con Hora)
            col_fecha = next((c for c in df_ibot.columns if 'fecha' in c.lower()), None)
            if col_fecha:
                return parsear_fecha_ibot(row.get(col_fecha), row.get(col_orden))
                
            return None

        df_ibot['dt'] = df_ibot.apply(parsear_fecha_mix, axis=1)
        
        # Limpieza columna Orden (Extraer ID)
        # Si es Tabla Dinámica: "338122 - 22:52:00" -> "338122"
        df_ibot['Orden_ID'] = df_ibot[col_orden].astype(str).apply(lambda x: x.split(' - ')[0].strip())

        # -------------------------------------------------------------------------
        # NUEVO: AGRUPAR POR ORDEN (Sumar productos de una misma boleta)
        # -------------------------------------------------------------------------
        
        # Corrección Error 'Producto' no existe en Tabla Dinámica
        if 'Producto' not in df_ibot.columns:
            df_ibot['Producto'] = 'Varios'

        # Agrupamos por ID de orden para obtener el MONTO TOTAL REAL de la transacción.
        ibot_agrupado = df_ibot.groupby('Orden_ID').agg({
            'monto_limpio': 'sum',
            'dt': 'min', # Tomamos la hora del primer producto
            'Producto': lambda x: ' + '.join(x.dropna().astype(str).unique()) 
        }).reset_index()
        
        # Filtramos ordenes con monto 0 o inválidas
        ibot_agrupado = ibot_agrupado[ibot_agrupado['monto_limpio'] > 0].copy()
        
        # Limpieza Transbank y Cruce solo si existe df_tb
        ibot_pendiente_cruce = ibot_agrupado.copy() # Default si no hay cruce
        tb_sobrantes = pd.DataFrame() # Empty default
        matches = []
        indices_tb_usados = []
        diferencia_archivos = 0      
        total_banco_calc = 0
        faltantes_reporte = []

        if df_tb is not None:
            col_total_tb = next((c for c in df_tb.columns if 'TOTAL' in c.upper()), 'TOTAL')
            col_fecha_tb = next((c for c in df_tb.columns if 'FECHA' in c.upper()), 'FECHA')
            col_hora_tb = next((c for c in df_tb.columns if 'HORA' in c.upper()), 'HORA')
            
            df_tb['monto_limpio'] = df_tb[col_total_tb].apply(limpiar_monto)
            # Corregido: Usar parsear_fecha_transbank
            df_tb['dt'] = df_tb.apply(lambda x: parsear_fecha_transbank(x.get(col_fecha_tb), x.get(col_hora_tb)), axis=1)

            # 3. FILTRO DE TURNO (Opcional)
            if turno and turno != "Todo el día":
                try:
                    # Lógica de Turnos (Sin cambios)
                    horarios = {
                        "Mañana": ("08:00", "16:00"),
                        "Tarde": ("15:00", "23:00"), 
                    }
                    shift_start, shift_end = horarios.get(turno, ("00:00", "23:59"))
                    
                    def parse_time(t_str):
                        try:
                            return datetime.strptime(str(t_str).strip(), "%H:%M:%S").time()
                        except ValueError:
                            return datetime.strptime(str(t_str).strip(), "%H:%M").time()

                    t_start = parse_time(shift_start)
                    t_end = parse_time(shift_end)
                    
                    def en_rango(dt_val):
                        if pd.isna(dt_val): return False
                        try:
                            t_val = pd.to_datetime(dt_val).time()
                        except:
                            return False
                        
                        if t_start <= t_end:
                            return t_start <= t_val <= t_end
                        else: 
                            return t_val >= t_start or t_val <= t_end

                    # Aplicar filtro a los DataFrames procesados
                    ibot_agrupado = ibot_agrupado[ibot_agrupado['dt'].apply(en_rango)].copy()
                    df_tb = df_tb[df_tb['dt'].apply(en_rango)].copy()
                    
                except Exception as e:
                    pass

            # Preparar listas para el cruce
            ibot_pendiente_cruce = ibot_agrupado.sort_values('dt')
            tb_pendientes = df_tb.copy().sort_values('dt')
            
            # LOGICA CRUCE ESTRICTO (< 60 min)
            tolerancia_estrica = timedelta(minutes=60)

            for idx_i, row_i in ibot_pendiente_cruce.iterrows():
                monto = row_i['monto_limpio']
                tiempo_i = row_i['dt']
                
                if pd.isna(tiempo_i): continue

                # Buscar en Transbank
                candidatos = tb_pendientes[
                    (tb_pendientes['monto_limpio'] == monto) & 
                    (~tb_pendientes.index.isin(indices_tb_usados))
                ]
                
                mejor_match_idx = None
                menor_diff_tiempo = tolerancia_estrica
                match_encontrado = False

                for idx_t, row_t in candidatos.iterrows():
                    tiempo_t = row_t['dt']
                    if pd.isna(tiempo_t): continue
                    
                    diff = abs(tiempo_t - tiempo_i)
                    
                    if diff < menor_diff_tiempo:
                        menor_diff_tiempo = diff
                        mejor_match_idx = idx_t
                        match_encontrado = True
                
                if match_encontrado and mejor_match_idx is not None:
                    # Match Encontrado
                    indices_tb_usados.append(mejor_match_idx)
                    
                    matches.append({
                        "orden": row_i['Orden_ID'],
                        "monto": monto,
                        "estado": "Correcto"
                    })
                    # Marcar como procesado borrandolo del dataframe temporal
                    ibot_pendiente_cruce.drop(idx_i, inplace=True)
                
                # Si no encontró match, se queda en ibot_pendiente_cruce (Faltante)

            # Identificar Sobrantes Reales en Banco (Lo que quedó sin match)
            tb_sobrantes = tb_pendientes[~tb_pendientes.index.isin(indices_tb_usados)]
            
            # Calculos Finales TB
            total_banco_calc = int(df_tb['monto_limpio'].sum())
            # total_sistema_calc = int(df_ibot['monto_limpio'].sum()) # Re-calc based on filtered? No, IBOT total is total.
            
            # Recalculamos total sistema based on agrupado filtered if shift applies? 
            # Original code logic: total_sistema_calc was at the end.
            
        else:
            # Single Mode: No TB
            pass

        # 4. GENERACIÓN DE REPORTE JSON
        
        # 5. ANÁLISIS CONTRA VOUCHER MANUAL
        
        # Calc Totals Final (If TB exists uses it, else 0)
        total_sistema_calc = int(df_ibot['monto_limpio'].sum()) # Always calc from ibot
        
        diferencia_voucher = voucher_real - voucher_sistema
        if total_banco_calc > 0:
            diferencia_archivos = total_banco_calc - total_sistema_calc
        else:
            diferencia_archivos = 0 # No hay comparacion externa

        # ¿La diferencia de los archivos explica la del voucher?
        explicacion_voucher = "No se ingresaron datos del voucher."
        if voucher_sistema > 0:
            if df_tb is None:
                 explicacion_voucher = "⚠️ Modo Archivo Único: No se puede validar contra banco."
            elif abs(diferencia_voucher - diferencia_archivos) < 500: # Tolerancia $500
                explicacion_voucher = "✅ La diferencia detectada en los archivos EXPLICA COMPLETAMENTE la diferencia de tu voucher."
            else:
                diff_restante = diferencia_voucher - diferencia_archivos
                explicacion_voucher = f"⚠️ Aún queda una diferencia de ${diff_restante} sin explicar por los archivos."

        # 5. ANÁLISIS INTELIGENTE DE FALTANTES (Intelligent Explainer)
        # Solo si hay TB
        if df_tb is not None:
            # Iteramos sobre lo que quedó en el dataframe agrupado (lo que no hizo match)
            for _, row_i in ibot_pendiente_cruce.iterrows():
                monto_i = row_i['monto_limpio']
                # Buscar coincidencia de monto en sobrantes (dentro del turno filtrado)
                posibles_matches = tb_sobrantes[tb_sobrantes['monto_limpio'] == monto_i]
                
                analisis_msg = "❌ No se encontró cobro por este monto en el turno."
                estilo_msg = "danger" # Rojo
                
                if not posibles_matches.empty:
                    # Encontramos montos iguales en el turno
                    # Tomar el más cercano en tiempo
                    row_i_dt = row_i['dt']
                    match_cercano = None
                    min_diff = None
                    
                    # Formatear lista de horarios encontrados
                    horarios_encontrados = []
                    
                    for _, row_t in posibles_matches.iterrows():
                        hora_t_str = row_t['dt'].strftime("%H:%M")
                        horarios_encontrados.append(hora_t_str)
                        
                        if pd.notna(row_i_dt) and pd.notna(row_t['dt']):
                            diff = abs(row_t['dt'] - row_i_dt)
                            if min_diff is None or diff < min_diff:
                                min_diff = diff
                                match_cercano = hora_t_str
                    
                    horarios_str = ", ".join(horarios_encontrados)
                    if len(horarios_encontrados) > 3:
                        horarios_str = f"{horarios_encontrados[0]}, {horarios_encontrados[1]} ... ({len(horarios_encontrados)} opciones)"
                    
                    # Crear mensaje
                    analisis_msg = f"⚠️ Hay cobros de ${monto_i} a las: {horarios_str}. ¿Posible desfase?"
                    estilo_msg = "warning" # Amarillo/Naranja

                faltantes_reporte.append({
                    "producto": row_i.get('Producto', 'Varios'),
                    "orden": row_i.get('Orden_ID', 'S/N'),
                    "monto": monto_i,
                    "hora_digitada": row_i['dt'].strftime("%H:%M") if pd.notna(row_i['dt']) else "N/A",
                    "analisis": analisis_msg,
                    "estilo_analisis": estilo_msg
                })

        # ... (Rest of return logic)

        return {
            "analisis_interno": alertas_internas,
            "voucher_analisis": {
                "diferencia_declarada": diferencia_voucher,
                "diferencia_encontrada_archivos": diferencia_archivos,
                "mensaje": explicacion_voucher
            },
            "resumen_general": {
                "total_declarado_sistema": total_sistema_calc,
                "total_real_banco": total_banco_calc,
                "diferencia_neta": diferencia_archivos
            },
            "analisis_detallado": {
                "faltantes_en_banco": faltantes_reporte,
                "sobrantes_en_banco": [
                    {
                        "hora_cobro": row['dt'].strftime("%H:%M") if pd.notna(row['dt']) else "N/A",
                        "monto": row['monto_limpio'],
                        "causa_probable": "Cobro realizado en POS sin registro en sistema (o con desfase mayor a 60 min)"
                    }
                    for _, row in tb_sobrantes.iterrows()
                ],
                "ventas_con_desfase_detectadas": [] # DEPRECADO: Ya no usamos esta lista
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Error Interno: {str(e)}\n\nTraceback:\n{traceback.format_exc()}"
        print(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

# --- ENDPOINT CAJA AUXILIAR ---

@app.post("/registrar-caja/")
async def registrar_caja(
    fecha: str = Form(...),
    vendedor: str = Form(...),
    turno: str = Form(...),
    total_efectivo: int = Form(...),
    total_transbank: int = Form(...),
    notas: str = Form(None),
    user: Optional[str] = Depends(get_current_user) # CHECK AUTH
):
    if not user: raise HTTPException(status_code=401)
    
    archivo_csv = "caja_auxiliar.csv"
    existe = os.path.exists(archivo_csv)
    
    try:
        with open(archivo_csv, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Escribir header si no existe
            if not existe:
                writer.writerow(["Fecha", "Vendedor", "Turno", "Total Efectivo", "Total Transbank", "Notas", "Timestamp"])
            
            # Escribir datos
            writer.writerow([
                fecha, 
                vendedor, 
                turno, 
                total_efectivo, 
                total_transbank, 
                notas if notas else "", 
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ])
            
        return {"mensaje": "Registro guardado exitosamente", "estado": "ok"}
    

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error guardando registro: {str(e)}")

# --- ENDPOINT CUADRATURA SUCURSALES ---

@app.post("/calculate-branches", response_model=GlobalSummary)
def calculate_endpoint(
    data: List[BranchInput],
    user: Optional[str] = Depends(get_current_user) # CHECK AUTH
):
    """
    Recibe una lista de datos de sucursales y devuelve el resumen de cuadratura.
    """
    if not user: raise HTTPException(status_code=401)
    return calculate_cuadratura(data)


