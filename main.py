from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import psycopg2
import psycopg2.extras
import os
import json
from datetime import datetime, timedelta
import uuid
import math

app = FastAPI(
    title="BateaControl API",
    description="Sistema Municipal de Gestión de Servicios Territoriales",
    version="2.3.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.environ.get("DATABASE_URL", "")

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    # ── SOLICITUDES (bateas) ───────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS solicitudes (
            id VARCHAR(50) PRIMARY KEY,
            folio VARCHAR(30) UNIQUE,
            nombre_vecino VARCHAR(150) NOT NULL,
            rut VARCHAR(15) NOT NULL,
            direccion VARCHAR(255) NOT NULL,
            telefono VARCHAR(20),
            latitud DECIMAL(10,8),
            longitud DECIMAL(11,8),
            observaciones TEXT,
            foto_url TEXT,
            fotos_antes TEXT DEFAULT '[]',
            estado VARCHAR(30) DEFAULT 'pendiente',
            nivel_alerta VARCHAR(20) DEFAULT 'normal',
            fecha_solicitud TIMESTAMP DEFAULT NOW(),
            fecha_asignacion TIMESTAMP,
            numero_batea VARCHAR(30),
            grupo_id VARCHAR(50),
            creado_en TIMESTAMP DEFAULT NOW(),
            actualizado_en TIMESTAMP DEFAULT NOW()
        )
    """)
    for col, tipo in [
        ("grupo_id","VARCHAR(50)"),("numero_batea","VARCHAR(30)"),
        ("fecha_asignacion","TIMESTAMP"),("actualizado_en","TIMESTAMP DEFAULT NOW()"),
        ("fotos_antes","TEXT DEFAULT '[]'")
    ]:
        try: cur.execute(f"ALTER TABLE solicitudes ADD COLUMN IF NOT EXISTS {col} {tipo}")
        except: conn.rollback()

    # ── DESMALEZADOS ───────────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS desmalezados (
            id VARCHAR(50) PRIMARY KEY,
            folio VARCHAR(30) UNIQUE,
            nombre_solicitante VARCHAR(150),
            rut VARCHAR(15) DEFAULT 'SIN-RUT',
            telefono VARCHAR(20),
            es_recordatorio BOOLEAN DEFAULT FALSE,
            direccion VARCHAR(255) NOT NULL,
            descripcion TEXT,
            observaciones TEXT,
            latitud DECIMAL(10,8),
            longitud DECIMAL(11,8),
            fotos_antes TEXT DEFAULT '[]',
            fotos_despues TEXT DEFAULT '[]',
            estado VARCHAR(30) DEFAULT 'pendiente',
            fecha_solicitud TIMESTAMP DEFAULT NOW(),
            fecha_inicio TIMESTAMP,
            fecha_termino TIMESTAMP,
            dias_uso INTEGER,
            responsable VARCHAR(150),
            fecha_cierre TIMESTAMP,
            operativo_conjunto_id VARCHAR(50),
            observaciones_cierre TEXT,
            creado_en TIMESTAMP DEFAULT NOW()
        )
    """)
    for col, tipo in [
        ("fecha_inicio","TIMESTAMP"),("fecha_termino","TIMESTAMP"),
        ("dias_uso","INTEGER"),("responsable","VARCHAR(150)"),
        ("fotos_antes","TEXT DEFAULT '[]'"),("fotos_despues","TEXT DEFAULT '[]'"),
        ("rut","VARCHAR(15) DEFAULT 'SIN-RUT'"),
        ("telefono","VARCHAR(20)"),
        ("observaciones","TEXT"),
    ]:
        try: cur.execute(f"ALTER TABLE desmalezados ADD COLUMN IF NOT EXISTS {col} {tipo}")
        except: conn.rollback()

    # ── ARREGLO DE CAMINOS ─────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS arreglo_caminos (
            id VARCHAR(50) PRIMARY KEY,
            folio VARCHAR(30) UNIQUE,
            nombre_solicitante VARCHAR(150),
            rut VARCHAR(15) DEFAULT 'SIN-RUT',
            telefono VARCHAR(20),
            es_recordatorio BOOLEAN DEFAULT FALSE,
            direccion VARCHAR(255) NOT NULL,
            tipo_camino VARCHAR(50) DEFAULT 'camino',
            descripcion_problema TEXT,
            observaciones TEXT,
            latitud DECIMAL(10,8),
            longitud DECIMAL(11,8),
            fotos_antes TEXT DEFAULT '[]',
            fotos_despues TEXT DEFAULT '[]',
            estado VARCHAR(30) DEFAULT 'pendiente',
            prioridad VARCHAR(20) DEFAULT 'normal',
            fecha_solicitud TIMESTAMP DEFAULT NOW(),
            fecha_inicio TIMESTAMP,
            fecha_termino TIMESTAMP,
            dias_uso INTEGER,
            responsable VARCHAR(150),
            fecha_cierre TIMESTAMP,
            observaciones_cierre TEXT,
            creado_en TIMESTAMP DEFAULT NOW()
        )
    """)
    for col, tipo in [
        ("fecha_inicio","TIMESTAMP"),("fecha_termino","TIMESTAMP"),
        ("dias_uso","INTEGER"),("responsable","VARCHAR(150)"),
        ("fotos_antes","TEXT DEFAULT '[]'"),("fotos_despues","TEXT DEFAULT '[]'"),
        ("rut","VARCHAR(15) DEFAULT 'SIN-RUT'"),
        ("telefono","VARCHAR(20)"),
        ("observaciones","TEXT"),
    ]:
        try: cur.execute(f"ALTER TABLE arreglo_caminos ADD COLUMN IF NOT EXISTS {col} {tipo}")
        except: conn.rollback()

    # ── OPERATIVOS CENTRALES ───────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS operativos_centrales (
            id VARCHAR(50) PRIMARY KEY,
            codigo VARCHAR(30) UNIQUE,
            titulo VARCHAR(255) NOT NULL,
            descripcion TEXT,
            tipo_operativo VARCHAR(100) DEFAULT 'general',
            departamento VARCHAR(150),
            responsable_principal VARCHAR(150),
            equipo TEXT DEFAULT '[]',
            estado VARCHAR(30) DEFAULT 'planificado',
            prioridad VARCHAR(20) DEFAULT 'normal',
            latitud DECIMAL(10,8),
            longitud DECIMAL(11,8),
            sector VARCHAR(150),
            fecha_programada TIMESTAMP,
            fecha_inicio TIMESTAMP,
            fecha_termino TIMESTAMP,
            dias_uso INTEGER,
            fotos_antes TEXT DEFAULT '[]',
            fotos_despues TEXT DEFAULT '[]',
            servicios_incluidos TEXT DEFAULT '[]',
            observaciones TEXT,
            observaciones_cierre TEXT,
            fecha_cierre TIMESTAMP,
            creado_en TIMESTAMP DEFAULT NOW()
        )
    """)

    # ── OPERATIVOS CONJUNTOS ───────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS operativos_conjuntos (
            id VARCHAR(50) PRIMARY KEY,
            codigo VARCHAR(30) UNIQUE,
            solicitud_batea_id VARCHAR(50),
            desmalezado_id VARCHAR(50),
            centroide_lat DECIMAL(10,8),
            centroide_lon DECIMAL(11,8),
            numero_batea VARCHAR(30),
            estado VARCHAR(30) DEFAULT 'planificado',
            fecha_planificacion TIMESTAMP DEFAULT NOW(),
            fecha_inicio TIMESTAMP,
            fecha_termino TIMESTAMP,
            dias_uso INTEGER,
            responsable VARCHAR(150),
            fecha_cierre TIMESTAMP,
            observaciones TEXT,
            fotos_antes TEXT DEFAULT '[]',
            fotos_despues TEXT DEFAULT '[]',
            creado_en TIMESTAMP DEFAULT NOW()
        )
    """)
    for col, tipo in [
        ("fotos_antes","TEXT DEFAULT '[]'"),("fotos_despues","TEXT DEFAULT '[]'"),
        ("fecha_inicio","TIMESTAMP"),("fecha_termino","TIMESTAMP"),
        ("dias_uso","INTEGER"),("responsable","VARCHAR(150)")
    ]:
        try: cur.execute(f"ALTER TABLE operativos_conjuntos ADD COLUMN IF NOT EXISTS {col} {tipo}")
        except: conn.rollback()

    # ── GRUPOS TERRITORIALES ───────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS grupos_territoriales (
            id VARCHAR(50) PRIMARY KEY,
            codigo_grupo VARCHAR(30) UNIQUE,
            numero_batea VARCHAR(30),
            centroide_lat DECIMAL(10,8),
            centroide_lon DECIMAL(11,8),
            radio_metros INTEGER DEFAULT 100,
            total_vecinos INTEGER DEFAULT 0,
            dias_uso INTEGER DEFAULT 7,
            fecha_inicio TIMESTAMP,
            fecha_termino TIMESTAMP,
            estado_batea VARCHAR(30) DEFAULT 'asignada',
            fecha_creacion TIMESTAMP DEFAULT NOW()
        )
    """)
    for col, tipo in [
        ("dias_uso","INTEGER DEFAULT 7"),("fecha_inicio","TIMESTAMP"),
        ("fecha_termino","TIMESTAMP"),("estado_batea","VARCHAR(30) DEFAULT 'asignada'")
    ]:
        try: cur.execute(f"ALTER TABLE grupos_territoriales ADD COLUMN IF NOT EXISTS {col} {tipo}")
        except: conn.rollback()

    # ── HISTORIAL BATEAS ───────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS historial_bateas (
            id VARCHAR(50) PRIMARY KEY,
            rut VARCHAR(15) NOT NULL,
            nombre_vecino VARCHAR(150),
            direccion VARCHAR(255),
            numero_batea VARCHAR(30),
            fecha_asignacion TIMESTAMP,
            fecha_termino TIMESTAMP,
            dias_uso INTEGER,
            observaciones TEXT,
            creado_en TIMESTAMP DEFAULT NOW()
        )
    """)
    for col, tipo in [("fecha_termino","TIMESTAMP"),("dias_uso","INTEGER")]:
        try: cur.execute(f"ALTER TABLE historial_bateas ADD COLUMN IF NOT EXISTS {col} {tipo}")
        except: conn.rollback()

    conn.commit(); cur.close(); conn.close()

try:
    init_db()
except Exception as e:
    print(f"Error inicializando DB: {e}")

# ── UTILIDADES ────────────────────────────────────────────────────────────────

def distancia_metros(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2-lat1); dlambda = math.radians(lon2-lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def calcular_dias(fecha): return (datetime.now() - fecha).days

def calcular_alerta(dias):
    if dias >= 20: return "critica"
    elif dias >= 11: return "advertencia"
    return "normal"

def gen_folio(conn, prefijo, tabla):
    anio = datetime.now().year
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {tabla} WHERE folio LIKE %s", [f"{prefijo}-{anio}-%"])
    total = cur.fetchone()[0]; cur.close()
    return f"{prefijo}-{anio}-{str(total+1).zfill(4)}"

def parse_fecha(s):
    try: return datetime.strptime(s, "%Y-%m-%d")
    except: return datetime.now()

def parse_fotos(val):
    """Convierte columna TEXT a lista de URLs"""
    if not val: return []
    try: return json.loads(val)
    except: return [val] if val else []

def fotos_a_json(lista):
    """Convierte lista de URLs a TEXT para guardar"""
    return json.dumps([f for f in lista if f])

def obtener_historial_vecino(conn, rut):
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT numero_batea, fecha_asignacion, fecha_termino, dias_uso, direccion FROM historial_bateas WHERE rut=%s ORDER BY fecha_asignacion DESC", [rut])
    rows = cur.fetchall(); cur.close()
    return [{"numero_batea":r["numero_batea"], "fecha_asignacion":r["fecha_asignacion"].strftime("%d/%m/%Y") if r["fecha_asignacion"] else "", "fecha_termino":r["fecha_termino"].strftime("%d/%m/%Y") if r["fecha_termino"] else "", "dias_uso":r["dias_uso"] or 0, "direccion":r["direccion"]} for r in rows]

# ── MODELOS ───────────────────────────────────────────────────────────────────

class SolicitudCreate(BaseModel):
    nombre_vecino: str
    rut: Optional[str] = "SIN-RUT"
    direccion: Optional[str] = "Sin dirección"
    telefono: Optional[str] = ""
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    observaciones: Optional[str] = ""
    fotos_antes: Optional[List[str]] = []

class SolicitudEdit(BaseModel):
    nombre_vecino: Optional[str] = None
    rut: Optional[str] = None
    direccion: Optional[str] = None
    telefono: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    observaciones: Optional[str] = None
    fotos_antes: Optional[List[str]] = None

class DesmalezadoEdit(BaseModel):
    nombre_solicitante: Optional[str] = None
    es_recordatorio: Optional[bool] = None
    direccion: Optional[str] = None
    descripcion: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    fotos_antes: Optional[List[str]] = None

class CaminoEdit(BaseModel):
    nombre_solicitante: Optional[str] = None
    es_recordatorio: Optional[bool] = None
    direccion: Optional[str] = None
    tipo_camino: Optional[str] = None
    descripcion_problema: Optional[str] = None
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    fotos_antes: Optional[List[str]] = None
    prioridad: Optional[str] = None

class ClusteringRequest(BaseModel):
    radio_metros: Optional[int] = 100
    dias_uso: int = 7
    fecha_inicio: Optional[str] = None

class AsignacionRequest(BaseModel):
    fecha_inicio: str; dias_uso: int
    responsable: Optional[str] = ""

class DesmalezadoCreate(BaseModel):
    nombre_solicitante: Optional[str] = ""
    rut: Optional[str] = "SIN-RUT"
    telefono: Optional[str] = ""
    es_recordatorio: bool = False
    direccion: str
    descripcion: Optional[str] = ""
    observaciones: Optional[str] = ""
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    fotos_antes: Optional[List[str]] = []

class CaminoCreate(BaseModel):
    nombre_solicitante: Optional[str] = ""
    rut: Optional[str] = "SIN-RUT"
    telefono: Optional[str] = ""
    es_recordatorio: bool = False
    direccion: str
    tipo_camino: Optional[str] = "camino"
    descripcion_problema: Optional[str] = ""
    observaciones: Optional[str] = ""
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    fotos_antes: Optional[List[str]] = []
    prioridad: Optional[str] = "normal"

class OperativoCentralCreate(BaseModel):
    titulo: str
    descripcion: Optional[str] = ""
    tipo_operativo: Optional[str] = "general"
    departamento: Optional[str] = ""
    responsable_principal: Optional[str] = ""
    equipo: Optional[List[str]] = []
    prioridad: Optional[str] = "normal"
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    sector: Optional[str] = ""
    fecha_programada: Optional[str] = None
    servicios_incluidos: Optional[List[str]] = []
    observaciones: Optional[str] = ""
    fotos_antes: Optional[List[str]] = []

class OperativoCentralAsignar(BaseModel):
    fecha_inicio: str
    dias_uso: int
    responsable_principal: Optional[str] = ""
    equipo: Optional[List[str]] = []

class OperativoCentralCierre(BaseModel):
    fotos_despues: Optional[List[str]] = []
    observaciones_cierre: Optional[str] = ""
    fotos_antes: Optional[List[str]] = []
    prioridad: Optional[str] = "normal"

class CierreRequest(BaseModel):
    fotos_despues: Optional[List[str]] = []
    observaciones_cierre: Optional[str] = ""

# ── HEALTH ────────────────────────────────────────────────────────────────────

@app.get("/")
def root(): return {"sistema":"BateaControl","version":"2.3.0","estado":"operacional"}

@app.get("/api/health")
def health(): return {"status":"ok"}

# ═══════════════════════════════════════════════════════════════════════════════
# BATEAS
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/solicitudes")
def crear_solicitud(data: SolicitudCreate):
    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id, folio, fecha_solicitud FROM solicitudes WHERE rut=%s AND estado IN ('pendiente','agrupada')", [data.rut])
        pendiente = cur.fetchone()
        if pendiente:
            cur.close(); conn.close()
            raise HTTPException(status_code=400, detail=f"Vecino ya tiene solicitud pendiente: {pendiente['folio']} del {pendiente['fecha_solicitud'].strftime('%d/%m/%Y')}")
        historial = obtener_historial_vecino(conn, data.rut)
        folio = gen_folio(conn, "SOL", "solicitudes")
        sid = str(uuid.uuid4())
        fotos_json = fotos_a_json(data.fotos_antes[:5])  # máx 5
        cur.execute("""
            INSERT INTO solicitudes (id,folio,nombre_vecino,rut,direccion,telefono,latitud,longitud,observaciones,fotos_antes,estado,nivel_alerta,fecha_solicitud)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pendiente','normal',NOW())
        """, [sid,folio,data.nombre_vecino,data.rut,data.direccion,data.telefono,data.latitud,data.longitud,data.observaciones,fotos_json])
        conn.commit(); cur.close(); conn.close()
        return {
            "success":True,"id":sid,"folio":folio,
            "mensaje":"Solicitud registrada exitosamente",
            "tuvo_batea_antes":len(historial)>0,"historial_previo":historial,
            "alerta_duplicado":f"⚠️ Este vecino ya recibió la batea {historial[0]['numero_batea']} el {historial[0]['fecha_asignacion']} por {historial[0]['dias_uso']} días" if historial else None
        }
    except HTTPException: raise
    except Exception as e:
        conn.rollback(); conn.close(); raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/solicitudes")
def listar_solicitudes(estado: Optional[str] = None):
    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("UPDATE solicitudes SET nivel_alerta=CASE WHEN EXTRACT(DAY FROM (NOW()-fecha_solicitud))>=20 THEN 'critica' WHEN EXTRACT(DAY FROM (NOW()-fecha_solicitud))>=11 THEN 'advertencia' ELSE 'normal' END WHERE estado='pendiente'")
        conn.commit()
        if estado: cur.execute("SELECT * FROM solicitudes WHERE estado=%s ORDER BY fecha_solicitud ASC",[estado])
        else: cur.execute("SELECT * FROM solicitudes ORDER BY CASE nivel_alerta WHEN 'critica' THEN 1 WHEN 'advertencia' THEN 2 ELSE 3 END,fecha_solicitud ASC")
        rows = cur.fetchall(); cur.close(); conn.close()
        resultado = []
        for r in rows:
            conn2=get_db(); historial=obtener_historial_vecino(conn2,r["rut"]); conn2.close()
            dias = calcular_dias(r["fecha_solicitud"])
            resultado.append({
                "id":r["id"],"folio":r["folio"],"nombre_vecino":r["nombre_vecino"],"rut":r["rut"],
                "direccion":r["direccion"],"telefono":r["telefono"] or "",
                "latitud":float(r["latitud"]) if r["latitud"] else 0,
                "longitud":float(r["longitud"]) if r["longitud"] else 0,
                "observaciones":r["observaciones"] or "",
                "fotos_antes":parse_fotos(r.get("fotos_antes")),
                "foto_url":parse_fotos(r.get("fotos_antes"))[0] if parse_fotos(r.get("fotos_antes")) else "",
                "estado":r["estado"],"nivel_alerta":calcular_alerta(dias),
                "fecha_solicitud":r["fecha_solicitud"].strftime("%d/%m/%Y %H:%M"),
                "dias_pendiente":dias,
                "numero_batea":r.get("numero_batea") or "","grupo_id":r.get("grupo_id") or "",
                "tuvo_batea_antes":len(historial)>0,"historial_previo":historial
            })
        return {"solicitudes":resultado,"total":len(resultado)}
    except Exception as e:
        conn.close(); raise HTTPException(status_code=500,detail=str(e))

@app.put("/api/solicitudes/{id}/editar")
def editar_solicitud(id: str, data: SolicitudEdit):
    """Edita cualquier campo de una solicitud de batea"""
    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM solicitudes WHERE id=%s", [id])
        actual = cur.fetchone()
        if not actual:
            cur.close(); conn.close()
            raise HTTPException(status_code=404, detail="Solicitud no encontrada")

        # Solo actualiza los campos que vienen en el request (los demás quedan igual)
        campos = {}
        if data.nombre_vecino  is not None: campos["nombre_vecino"]  = data.nombre_vecino
        if data.rut            is not None: campos["rut"]            = data.rut
        if data.direccion      is not None: campos["direccion"]      = data.direccion
        if data.telefono       is not None: campos["telefono"]       = data.telefono
        if data.latitud        is not None: campos["latitud"]        = data.latitud
        if data.longitud       is not None: campos["longitud"]       = data.longitud
        if data.observaciones  is not None: campos["observaciones"]  = data.observaciones
        if data.fotos_antes    is not None: campos["fotos_antes"]    = fotos_a_json(data.fotos_antes[:5])

        if not campos:
            cur.close(); conn.close()
            return {"success": True, "mensaje": "Sin cambios"}

        sets = ", ".join([f"{k}=%s" for k in campos])
        vals = list(campos.values()) + [id]
        cur.execute(f"UPDATE solicitudes SET {sets}, actualizado_en=NOW() WHERE id=%s", vals)
        conn.commit(); cur.close(); conn.close()
        return {"success": True, "mensaje": "Solicitud actualizada correctamente"}
    except HTTPException: raise
    except Exception as e:
        conn.rollback(); conn.close(); raise HTTPException(status_code=500, detail=str(e))

# ═══════════════════════════════════════════════════════════════════════════════
# DESMALEZADOS
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/desmalezados")
def crear_desmalezado(data: DesmalezadoCreate):
    conn = get_db()
    try:
        folio = gen_folio(conn,"DES","desmalezados")
        did = str(uuid.uuid4())
        fotos_json = fotos_a_json(data.fotos_antes[:5])
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO desmalezados (id,folio,nombre_solicitante,rut,telefono,es_recordatorio,direccion,descripcion,observaciones,latitud,longitud,fotos_antes,estado,fecha_solicitud)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pendiente',NOW())
        """, [did,folio,data.nombre_solicitante,data.rut,data.telefono,data.es_recordatorio,data.direccion,data.descripcion,data.observaciones,data.latitud,data.longitud,fotos_json])
        cur2 = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur2.execute("SELECT id,nombre_vecino,direccion,latitud,longitud FROM solicitudes WHERE estado='pendiente' AND latitud IS NOT NULL AND longitud IS NOT NULL")
        bateas = cur2.fetchall(); cur2.close()
        sugerencia = None
        if data.latitud and data.longitud:
            for b in bateas:
                dist = distancia_metros(data.latitud,data.longitud,float(b["latitud"]),float(b["longitud"]))
                if dist<=100:
                    sugerencia={"batea_id":b["id"],"vecino":b["nombre_vecino"],"direccion":b["direccion"],"distancia_metros":round(dist,1)}
                    break
        conn.commit(); cur.close(); conn.close()
        return {"success":True,"id":did,"folio":folio,"mensaje":"Desmalezado registrado",
                "sugerencia_operativo_conjunto":sugerencia,
                "alerta_conjunto":f"🔧 Batea pendiente a {sugerencia['distancia_metros']}m — ¿Crear Operativo Conjunto?" if sugerencia else None}
    except Exception as e:
        conn.rollback(); conn.close(); raise HTTPException(status_code=500,detail=str(e))

@app.get("/api/desmalezados")
def listar_desmalezados(estado: Optional[str]=None):
    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if estado: cur.execute("SELECT * FROM desmalezados WHERE estado=%s ORDER BY fecha_solicitud ASC",[estado])
        else: cur.execute("SELECT * FROM desmalezados ORDER BY fecha_solicitud ASC")
        rows = cur.fetchall(); cur.close(); conn.close()
        return {"desmalezados":[{
            "id":r["id"],"folio":r["folio"],
            "nombre_solicitante":r["nombre_solicitante"] or "Sin nombre",
            "es_recordatorio":r["es_recordatorio"],
            "nombre_solicitante":r["nombre_solicitante"] or "Sin nombre",
            "rut": r["rut"] or "SIN-RUT",
            "telefono": r["telefono"] or "",
            "es_recordatorio":r["es_recordatorio"],
            "direccion":r["direccion"],"descripcion":r["descripcion"] or "",
            "observaciones": r["observaciones"] or "",
            "latitud":float(r["latitud"]) if r["latitud"] else 0,
            "longitud":float(r["longitud"]) if r["longitud"] else 0,
            "fotos_antes":parse_fotos(r.get("fotos_antes")),
            "fotos_despues":parse_fotos(r.get("fotos_despues")),
            "estado":r["estado"],
            "fecha_solicitud":r["fecha_solicitud"].strftime("%d/%m/%Y %H:%M"),
            "fecha_inicio":r["fecha_inicio"].strftime("%d/%m/%Y") if r["fecha_inicio"] else "",
            "fecha_termino":r["fecha_termino"].strftime("%d/%m/%Y") if r["fecha_termino"] else "",
            "dias_uso":r["dias_uso"] or 0,"responsable":r["responsable"] or "",
            "dias_pendiente":calcular_dias(r["fecha_solicitud"])
        } for r in rows],"total":len(rows)}
    except Exception as e:
        conn.close(); raise HTTPException(status_code=500,detail=str(e))

@app.put("/api/desmalezados/{id}/editar")
def editar_desmalezado(id: str, data: DesmalezadoEdit):
    """Edita cualquier campo de un desmalezado"""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM desmalezados WHERE id=%s", [id])
        if not cur.fetchone():
            cur.close(); conn.close()
            raise HTTPException(status_code=404, detail="Desmalezado no encontrado")
        campos = {}
        if data.nombre_solicitante is not None: campos["nombre_solicitante"] = data.nombre_solicitante
        if data.es_recordatorio    is not None: campos["es_recordatorio"]    = data.es_recordatorio
        if data.direccion          is not None: campos["direccion"]          = data.direccion
        if data.descripcion        is not None: campos["descripcion"]        = data.descripcion
        if data.latitud            is not None: campos["latitud"]            = data.latitud
        if data.longitud           is not None: campos["longitud"]           = data.longitud
        if data.fotos_antes        is not None: campos["fotos_antes"]        = fotos_a_json(data.fotos_antes[:5])
        if not campos:
            cur.close(); conn.close()
            return {"success": True, "mensaje": "Sin cambios"}
        sets = ", ".join([f"{k}=%s" for k in campos])
        vals = list(campos.values()) + [id]
        cur.execute(f"UPDATE desmalezados SET {sets} WHERE id=%s", vals)
        conn.commit(); cur.close(); conn.close()
        return {"success": True, "mensaje": "Desmalezado actualizado correctamente"}
    except HTTPException: raise
    except Exception as e:
        conn.rollback(); conn.close(); raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/desmalezados/{id}/asignar")
def asignar_desmalezado(id: str, data: AsignacionRequest):
    conn = get_db()
    try:
        fi=parse_fecha(data.fecha_inicio); ft=fi+timedelta(days=data.dias_uso)
        cur=conn.cursor()
        cur.execute("UPDATE desmalezados SET estado='asignado',fecha_inicio=%s,fecha_termino=%s,dias_uso=%s,responsable=%s WHERE id=%s",
                    [fi,ft,data.dias_uso,data.responsable,id])
        conn.commit(); cur.close(); conn.close()
        return {"success":True,"mensaje":f"Asignado — Inicio: {fi.strftime('%d/%m/%Y')} — Término: {ft.strftime('%d/%m/%Y')} ({data.dias_uso} días)","fecha_inicio":fi.strftime("%d/%m/%Y"),"fecha_termino":ft.strftime("%d/%m/%Y"),"dias_uso":data.dias_uso}
    except Exception as e:
        conn.rollback(); conn.close(); raise HTTPException(status_code=500,detail=str(e))

@app.put("/api/desmalezados/{id}/cerrar")
def cerrar_desmalezado(id: str, data: CierreRequest):
    conn = get_db()
    try:
        fotos_json = fotos_a_json(data.fotos_despues[:5])
        cur=conn.cursor()
        cur.execute("UPDATE desmalezados SET estado='completado',fotos_despues=%s,observaciones_cierre=%s,fecha_cierre=NOW() WHERE id=%s",
                    [fotos_json,data.observaciones_cierre,id])
        conn.commit(); cur.close(); conn.close()
        return {"success":True,"mensaje":"Desmalezado cerrado exitosamente"}
    except Exception as e:
        conn.rollback(); conn.close(); raise HTTPException(status_code=500,detail=str(e))

# ═══════════════════════════════════════════════════════════════════════════════
# ARREGLO DE CAMINOS
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/caminos")
def crear_camino(data: CaminoCreate):
    conn = get_db()
    try:
        folio=gen_folio(conn,"CAM","arreglo_caminos")
        cid=str(uuid.uuid4())
        fotos_json=fotos_a_json(data.fotos_antes[:5])
        cur=conn.cursor()
        cur.execute("""
            INSERT INTO arreglo_caminos (id,folio,nombre_solicitante,es_recordatorio,direccion,tipo_camino,descripcion_problema,latitud,longitud,fotos_antes,estado,prioridad,fecha_solicitud)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pendiente',%s,NOW())
        """, [cid,folio,data.nombre_solicitante,data.es_recordatorio,data.direccion,data.tipo_camino,data.descripcion_problema,data.latitud,data.longitud,fotos_json,data.prioridad])
        conn.commit(); cur.close(); conn.close()
        return {"success":True,"id":cid,"folio":folio,"mensaje":"Arreglo de camino registrado"}
    except Exception as e:
        conn.rollback(); conn.close(); raise HTTPException(status_code=500,detail=str(e))

@app.get("/api/caminos")
def listar_caminos(estado: Optional[str]=None):
    conn = get_db()
    try:
        cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if estado: cur.execute("SELECT * FROM arreglo_caminos WHERE estado=%s ORDER BY fecha_solicitud ASC",[estado])
        else: cur.execute("SELECT * FROM arreglo_caminos ORDER BY CASE prioridad WHEN 'urgente' THEN 1 WHEN 'alta' THEN 2 ELSE 3 END,fecha_solicitud ASC")
        rows=cur.fetchall(); cur.close(); conn.close()
        return {"caminos":[{
            "id":r["id"],"folio":r["folio"],
            "nombre_solicitante":r["nombre_solicitante"] or "Registro interno",
            "es_recordatorio":r["es_recordatorio"],
            "direccion":r["direccion"],"tipo_camino":r["tipo_camino"],
            "descripcion_problema":r["descripcion_problema"] or "",
            "latitud":float(r["latitud"]) if r["latitud"] else 0,
            "longitud":float(r["longitud"]) if r["longitud"] else 0,
            "fotos_antes":parse_fotos(r.get("fotos_antes")),
            "fotos_despues":parse_fotos(r.get("fotos_despues")),
            "estado":r["estado"],"prioridad":r["prioridad"],
            "fecha_solicitud":r["fecha_solicitud"].strftime("%d/%m/%Y %H:%M"),
            "fecha_inicio":r["fecha_inicio"].strftime("%d/%m/%Y") if r["fecha_inicio"] else "",
            "fecha_termino":r["fecha_termino"].strftime("%d/%m/%Y") if r["fecha_termino"] else "",
            "dias_uso":r["dias_uso"] or 0,"responsable":r["responsable"] or "",
            "fecha_cierre":r["fecha_cierre"].strftime("%d/%m/%Y") if r["fecha_cierre"] else "",
            "dias_pendiente":calcular_dias(r["fecha_solicitud"])
        } for r in rows],"total":len(rows)}
    except Exception as e:
        conn.close(); raise HTTPException(status_code=500,detail=str(e))

@app.put("/api/caminos/{id}/editar")
def editar_camino(id: str, data: CaminoEdit):
    """Edita cualquier campo de un arreglo de camino"""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM arreglo_caminos WHERE id=%s", [id])
        if not cur.fetchone():
            cur.close(); conn.close()
            raise HTTPException(status_code=404, detail="Camino no encontrado")
        campos = {}
        if data.nombre_solicitante  is not None: campos["nombre_solicitante"]  = data.nombre_solicitante
        if data.es_recordatorio     is not None: campos["es_recordatorio"]     = data.es_recordatorio
        if data.direccion           is not None: campos["direccion"]           = data.direccion
        if data.tipo_camino         is not None: campos["tipo_camino"]         = data.tipo_camino
        if data.descripcion_problema is not None: campos["descripcion_problema"] = data.descripcion_problema
        if data.latitud             is not None: campos["latitud"]             = data.latitud
        if data.longitud            is not None: campos["longitud"]            = data.longitud
        if data.fotos_antes         is not None: campos["fotos_antes"]         = fotos_a_json(data.fotos_antes[:5])
        if data.prioridad           is not None: campos["prioridad"]           = data.prioridad
        if not campos:
            cur.close(); conn.close()
            return {"success": True, "mensaje": "Sin cambios"}
        sets = ", ".join([f"{k}=%s" for k in campos])
        vals = list(campos.values()) + [id]
        cur.execute(f"UPDATE arreglo_caminos SET {sets} WHERE id=%s", vals)
        conn.commit(); cur.close(); conn.close()
        return {"success": True, "mensaje": "Camino actualizado correctamente"}
    except HTTPException: raise
    except Exception as e:
        conn.rollback(); conn.close(); raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/caminos/{id}/asignar")
def asignar_camino(id: str, data: AsignacionRequest):
    conn = get_db()
    try:
        fi=parse_fecha(data.fecha_inicio); ft=fi+timedelta(days=data.dias_uso)
        cur=conn.cursor()
        cur.execute("UPDATE arreglo_caminos SET estado='asignado',fecha_inicio=%s,fecha_termino=%s,dias_uso=%s,responsable=%s WHERE id=%s",
                    [fi,ft,data.dias_uso,data.responsable,id])
        conn.commit(); cur.close(); conn.close()
        return {"success":True,"mensaje":f"Asignado — Inicio: {fi.strftime('%d/%m/%Y')} — Término: {ft.strftime('%d/%m/%Y')} ({data.dias_uso} días)","fecha_inicio":fi.strftime("%d/%m/%Y"),"fecha_termino":ft.strftime("%d/%m/%Y"),"dias_uso":data.dias_uso}
    except Exception as e:
        conn.rollback(); conn.close(); raise HTTPException(status_code=500,detail=str(e))

@app.put("/api/caminos/{id}/cerrar")
def cerrar_camino(id: str, data: CierreRequest):
    conn = get_db()
    try:
        fotos_json=fotos_a_json(data.fotos_despues[:5])
        cur=conn.cursor()
        cur.execute("UPDATE arreglo_caminos SET estado='completado',fotos_despues=%s,observaciones_cierre=%s,fecha_cierre=NOW() WHERE id=%s",
                    [fotos_json,data.observaciones_cierre,id])
        conn.commit(); cur.close(); conn.close()
        return {"success":True,"mensaje":"Camino cerrado exitosamente"}
    except Exception as e:
        conn.rollback(); conn.close(); raise HTTPException(status_code=500,detail=str(e))

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIVOS CENTRALES
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/operativos-centrales")
def crear_operativo_central(data: OperativoCentralCreate):
    conn = get_db()
    try:
        anio = datetime.now().year
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM operativos_centrales WHERE codigo LIKE %s", [f"OC-{anio}-%"])
        total = cur.fetchone()[0]
        codigo = f"OC-{anio}-{str(total+1).zfill(4)}"
        oid = str(uuid.uuid4())
        fp = parse_fecha(data.fecha_programada) if data.fecha_programada else None
        cur.execute("""
            INSERT INTO operativos_centrales (
                id,codigo,titulo,descripcion,tipo_operativo,departamento,
                responsable_principal,equipo,prioridad,latitud,longitud,sector,
                fecha_programada,servicios_incluidos,observaciones,fotos_antes,
                estado,creado_en
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'planificado',NOW())
        """, [oid,codigo,data.titulo,data.descripcion,data.tipo_operativo,data.departamento,
              data.responsable_principal,json.dumps(data.equipo),data.prioridad,
              data.latitud,data.longitud,data.sector,fp,
              json.dumps(data.servicios_incluidos),data.observaciones,
              fotos_a_json(data.fotos_antes[:5])])
        conn.commit(); cur.close(); conn.close()
        return {"success":True,"id":oid,"codigo":codigo,"mensaje":f"Operativo Central {codigo} creado"}
    except Exception as e:
        conn.rollback(); conn.close(); raise HTTPException(status_code=500,detail=str(e))

@app.get("/api/operativos-centrales")
def listar_operativos_centrales():
    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM operativos_centrales ORDER BY creado_en DESC")
        rows = cur.fetchall(); cur.close(); conn.close()
        return {"operativos_centrales":[{
            "id":r["id"],"codigo":r["codigo"],"titulo":r["titulo"],
            "descripcion":r["descripcion"] or "",
            "tipo_operativo":r["tipo_operativo"] or "general",
            "departamento":r["departamento"] or "",
            "responsable_principal":r["responsable_principal"] or "",
            "equipo":json.loads(r["equipo"]) if r["equipo"] else [],
            "estado":r["estado"],"prioridad":r["prioridad"],
            "latitud":float(r["latitud"]) if r["latitud"] else 0,
            "longitud":float(r["longitud"]) if r["longitud"] else 0,
            "sector":r["sector"] or "",
            "fecha_programada":r["fecha_programada"].strftime("%d/%m/%Y") if r["fecha_programada"] else "",
            "fecha_inicio":r["fecha_inicio"].strftime("%d/%m/%Y") if r["fecha_inicio"] else "",
            "fecha_termino":r["fecha_termino"].strftime("%d/%m/%Y") if r["fecha_termino"] else "",
            "dias_uso":r["dias_uso"] or 0,
            "servicios_incluidos":json.loads(r["servicios_incluidos"]) if r["servicios_incluidos"] else [],
            "observaciones":r["observaciones"] or "",
            "observaciones_cierre":r["observaciones_cierre"] or "",
            "fotos_antes":parse_fotos(r.get("fotos_antes")),
            "fotos_despues":parse_fotos(r.get("fotos_despues")),
            "creado_en":r["creado_en"].strftime("%d/%m/%Y %H:%M"),
        } for r in rows],"total":len(rows)}
    except Exception as e:
        conn.close(); raise HTTPException(status_code=500,detail=str(e))

@app.put("/api/operativos-centrales/{id}/asignar")
def asignar_operativo_central(id: str, data: OperativoCentralAsignar):
    conn = get_db()
    try:
        fi = parse_fecha(data.fecha_inicio)
        ft = fi + timedelta(days=data.dias_uso)
        cur = conn.cursor()
        cur.execute("""
            UPDATE operativos_centrales SET estado='en_ejecucion',
            fecha_inicio=%s,fecha_termino=%s,dias_uso=%s,
            responsable_principal=%s,equipo=%s WHERE id=%s
        """, [fi,ft,data.dias_uso,data.responsable_principal,json.dumps(data.equipo),id])
        conn.commit(); cur.close(); conn.close()
        return {"success":True,"mensaje":f"Operativo asignado — {fi.strftime('%d/%m/%Y')} al {ft.strftime('%d/%m/%Y')} ({data.dias_uso} días)"}
    except Exception as e:
        conn.rollback(); conn.close(); raise HTTPException(status_code=500,detail=str(e))

@app.put("/api/operativos-centrales/{id}/cerrar")
def cerrar_operativo_central(id: str, data: OperativoCentralCierre):
    conn = get_db()
    try:
        fotos_json = fotos_a_json(data.fotos_despues[:5])
        cur = conn.cursor()
        cur.execute("""
            UPDATE operativos_centrales SET estado='completado',
            fotos_despues=%s,observaciones_cierre=%s,fecha_cierre=NOW() WHERE id=%s
        """, [fotos_json,data.observaciones_cierre,id])
        conn.commit(); cur.close(); conn.close()
        return {"success":True,"mensaje":"Operativo Central cerrado exitosamente"}
    except Exception as e:
        conn.rollback(); conn.close(); raise HTTPException(status_code=500,detail=str(e))

@app.put("/api/operativos-centrales/{id}/editar")
def editar_operativo_central(id: str, data: OperativoCentralCreate):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM operativos_centrales WHERE id=%s", [id])
        if not cur.fetchone():
            cur.close(); conn.close()
            raise HTTPException(status_code=404, detail="Operativo no encontrado")
        fp = parse_fecha(data.fecha_programada) if data.fecha_programada else None
        campos = {}
        if data.titulo               : campos["titulo"]               = data.titulo
        if data.descripcion is not None: campos["descripcion"]        = data.descripcion
        if data.tipo_operativo       : campos["tipo_operativo"]        = data.tipo_operativo
        if data.departamento is not None: campos["departamento"]      = data.departamento
        if data.responsable_principal is not None: campos["responsable_principal"] = data.responsable_principal
        if data.equipo is not None   : campos["equipo"]               = json.dumps(data.equipo)
        if data.prioridad            : campos["prioridad"]             = data.prioridad
        if data.latitud is not None  : campos["latitud"]              = data.latitud
        if data.longitud is not None : campos["longitud"]             = data.longitud
        if data.sector is not None   : campos["sector"]               = data.sector
        if data.fecha_programada     : campos["fecha_programada"]     = fp
        if data.servicios_incluidos is not None: campos["servicios_incluidos"] = json.dumps(data.servicios_incluidos)
        if data.observaciones is not None: campos["observaciones"]    = data.observaciones
        if data.fotos_antes is not None: campos["fotos_antes"]        = fotos_a_json(data.fotos_antes[:5])
        if not campos:
            cur.close(); conn.close()
            return {"success": True, "mensaje": "Sin cambios"}
        sets = ", ".join([f"{k}=%s" for k in campos])
        vals = list(campos.values()) + [id]
        cur.execute(f"UPDATE operativos_centrales SET {sets} WHERE id=%s", vals)
        conn.commit(); cur.close(); conn.close()
        return {"success": True, "mensaje": "Operativo Central actualizado correctamente"}
    except HTTPException: raise
    except Exception as e:
        conn.rollback(); conn.close(); raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/solicitudes/{id}/realizar")
def realizar_solicitud(id: str):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE solicitudes SET estado='instalada', actualizado_en=NOW() WHERE id=%s", [id])
        conn.commit(); cur.close(); conn.close()
        return {"success": True, "mensaje": "Batea marcada como Instalada"}
    except Exception as e:
        conn.rollback(); conn.close(); raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/desmalezados/{id}/realizar")
def realizar_desmalezado(id: str):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE desmalezados SET estado='completado', fecha_cierre=NOW() WHERE id=%s", [id])
        conn.commit(); cur.close(); conn.close()
        return {"success": True, "mensaje": "Desmalezado marcado como Completado"}
    except Exception as e:
        conn.rollback(); conn.close(); raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/caminos/{id}/realizar")
def realizar_camino(id: str):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE arreglo_caminos SET estado='completado', fecha_cierre=NOW() WHERE id=%s", [id])
        conn.commit(); cur.close(); conn.close()
        return {"success": True, "mensaje": "Arreglo de camino marcado como Completado"}
    except Exception as e:
        conn.rollback(); conn.close(); raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/operativos-conjuntos/{id}/realizar")
def realizar_operativo_conjunto(id: str):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE operativos_conjuntos SET estado='completado', fecha_cierre=NOW() WHERE id=%s", [id])
        conn.commit(); cur.close(); conn.close()
        return {"success": True, "mensaje": "Operativo Conjunto marcado como Completado"}
    except Exception as e:
        conn.rollback(); conn.close(); raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/operativos-centrales/{id}/realizar")
def realizar_operativo_central(id: str):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE operativos_centrales SET estado='completado', fecha_cierre=NOW() WHERE id=%s", [id])
        conn.commit(); cur.close(); conn.close()
        return {"success": True, "mensaje": "Operativo Central marcado como Completado"}
    except Exception as e:
        conn.rollback(); conn.close(); raise HTTPException(status_code=500, detail=str(e))

# ═══════════════════════════════════════════════════════════════════════════════
# ESTADÍSTICAS GENERALES PARA DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/estadisticas")
def estadisticas_generales():
    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        # Bateas
        cur.execute("""SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE estado='pendiente') as pendientes,
            COUNT(*) FILTER (WHERE estado='asignada') as asignadas,
            COUNT(*) FILTER (WHERE estado='instalada') as instaladas,
            COUNT(*) FILTER (WHERE estado='completado') as completadas,
            COUNT(*) FILTER (WHERE fecha_solicitud >= date_trunc('month', NOW())) as este_mes
            FROM solicitudes""")
        bateas = dict(cur.fetchone())
        cur.execute("SELECT COUNT(*) as grupos FROM grupos_territoriales")
        bateas["grupos"] = cur.fetchone()["grupos"]
        # Desmalezados
        cur.execute("""SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE estado='pendiente') as pendientes,
            COUNT(*) FILTER (WHERE estado='asignado') as asignados,
            COUNT(*) FILTER (WHERE estado='completado') as completados,
            COUNT(*) FILTER (WHERE fecha_solicitud >= date_trunc('month', NOW())) as este_mes
            FROM desmalezados""")
        desmalezados = dict(cur.fetchone())
        # Caminos
        cur.execute("""SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE estado='pendiente') as pendientes,
            COUNT(*) FILTER (WHERE estado='asignado') as asignados,
            COUNT(*) FILTER (WHERE estado='completado') as completados,
            COUNT(*) FILTER (WHERE fecha_solicitud >= date_trunc('month', NOW())) as este_mes
            FROM arreglo_caminos""")
        caminos = dict(cur.fetchone())
        # Operativos conjuntos
        cur.execute("""SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE estado='planificado') as planificados,
            COUNT(*) FILTER (WHERE estado='completado') as completados,
            COUNT(*) FILTER (WHERE fecha_planificacion >= date_trunc('month', NOW())) as este_mes
            FROM operativos_conjuntos""")
        op_conjuntos = dict(cur.fetchone())
        # Operativos centrales
        cur.execute("""SELECT
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE estado='planificado') as planificados,
            COUNT(*) FILTER (WHERE estado='en_ejecucion') as en_ejecucion,
            COUNT(*) FILTER (WHERE estado='completado') as completados,
            COUNT(*) FILTER (WHERE creado_en >= date_trunc('month', NOW())) as este_mes
            FROM operativos_centrales""")
        op_centrales = dict(cur.fetchone())
        cur.close(); conn.close()
        # Total realizados (todas las categorías)
        total_realizados = (
            int(bateas.get("instaladas",0) or 0) +
            int(bateas.get("completadas",0) or 0) +
            int(desmalezados.get("completados",0) or 0) +
            int(caminos.get("completados",0) or 0) +
            int(op_conjuntos.get("completados",0) or 0) +
            int(op_centrales.get("completados",0) or 0)
        )
        return {
            "bateas": bateas,
            "desmalezados": desmalezados,
            "caminos": caminos,
            "op_conjuntos": op_conjuntos,
            "op_centrales": op_centrales,
            "total_realizados": total_realizados,
        }
    except Exception as e:
        conn.close(); raise HTTPException(status_code=500, detail=str(e))


def eliminar_operativo_central(id: str):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT codigo FROM operativos_centrales WHERE id=%s",[id])
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close()
            raise HTTPException(status_code=404,detail="Operativo no encontrado")
        cur.execute("DELETE FROM operativos_centrales WHERE id=%s",[id])
        conn.commit(); cur.close(); conn.close()
        return {"success":True,"mensaje":f"Operativo {row[0]} eliminado"}
    except HTTPException: raise
    except Exception as e:
        conn.rollback(); conn.close(); raise HTTPException(status_code=500,detail=str(e))

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIVOS CONJUNTOS
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/operativos-conjuntos")
def crear_operativo_conjunto(solicitud_batea_id: str, desmalezado_id: str):
    conn = get_db()
    try:
        cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM solicitudes WHERE id=%s",[solicitud_batea_id]); batea=cur.fetchone()
        cur.execute("SELECT * FROM desmalezados WHERE id=%s",[desmalezado_id]); desmalezado=cur.fetchone()
        if not batea or not desmalezado: raise HTTPException(status_code=404,detail="Solicitud no encontrada")
        cent_lat=(float(batea["latitud"])+float(desmalezado["latitud"]))/2
        cent_lon=(float(batea["longitud"])+float(desmalezado["longitud"]))/2
        cur2=conn.cursor(); cur2.execute("SELECT COUNT(*) FROM operativos_conjuntos"); total=cur2.fetchone()[0]; cur2.close()
        anio=datetime.now().year
        codigo=f"OPC-{anio}-{str(total+1).zfill(4)}"
        numero_batea=f"BC-{anio}-{str(total+1).zfill(4)}"
        oid=str(uuid.uuid4())
        cur.execute("INSERT INTO operativos_conjuntos (id,codigo,solicitud_batea_id,desmalezado_id,centroide_lat,centroide_lon,numero_batea,estado,fecha_planificacion) VALUES (%s,%s,%s,%s,%s,%s,%s,'planificado',NOW())",
                    [oid,codigo,solicitud_batea_id,desmalezado_id,cent_lat,cent_lon,numero_batea])
        cur.execute("UPDATE solicitudes SET estado='asignada',numero_batea=%s WHERE id=%s",[numero_batea,solicitud_batea_id])
        cur.execute("UPDATE desmalezados SET estado='planificado',operativo_conjunto_id=%s WHERE id=%s",[oid,desmalezado_id])
        conn.commit(); cur.close(); conn.close()
        return {"success":True,"id":oid,"codigo":codigo,"numero_batea":numero_batea,"mensaje":f"Operativo Conjunto {codigo} creado"}
    except HTTPException: raise
    except Exception as e:
        conn.rollback(); conn.close(); raise HTTPException(status_code=500,detail=str(e))

@app.put("/api/operativos-conjuntos/{id}/asignar")
def asignar_operativo(id: str, data: AsignacionRequest):
    conn = get_db()
    try:
        fi=parse_fecha(data.fecha_inicio); ft=fi+timedelta(days=data.dias_uso)
        cur=conn.cursor()
        cur.execute("UPDATE operativos_conjuntos SET estado='asignado',fecha_inicio=%s,fecha_termino=%s,dias_uso=%s,responsable=%s WHERE id=%s",
                    [fi,ft,data.dias_uso,data.responsable,id])
        conn.commit(); cur.close(); conn.close()
        return {"success":True,"mensaje":f"Operativo asignado — {fi.strftime('%d/%m/%Y')} a {ft.strftime('%d/%m/%Y')} ({data.dias_uso} días)"}
    except Exception as e:
        conn.rollback(); conn.close(); raise HTTPException(status_code=500,detail=str(e))

@app.put("/api/operativos-conjuntos/{id}/cerrar")
def cerrar_operativo(id: str, data: CierreRequest):
    conn = get_db()
    try:
        fotos_json=fotos_a_json(data.fotos_despues[:5])
        cur=conn.cursor()
        cur.execute("UPDATE operativos_conjuntos SET estado='completado',fotos_despues=%s,observaciones=%s,fecha_cierre=NOW() WHERE id=%s",
                    [fotos_json,data.observaciones_cierre,id])
        conn.commit(); cur.close(); conn.close()
        return {"success":True,"mensaje":"Operativo cerrado exitosamente"}
    except Exception as e:
        conn.rollback(); conn.close(); raise HTTPException(status_code=500,detail=str(e))

@app.get("/api/operativos-conjuntos")
def listar_operativos_conjuntos():
    conn = get_db()
    try:
        cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT oc.*,s.nombre_vecino,s.direccion as direccion_batea,d.direccion as direccion_desmalezado
            FROM operativos_conjuntos oc
            LEFT JOIN solicitudes s ON oc.solicitud_batea_id=s.id
            LEFT JOIN desmalezados d ON oc.desmalezado_id=d.id
            ORDER BY oc.fecha_planificacion DESC
        """)
        rows=cur.fetchall(); cur.close(); conn.close()
        return {"operativos":[{
            "id":r["id"],"codigo":r["codigo"],"numero_batea":r["numero_batea"],"estado":r["estado"],
            "nombre_vecino":r["nombre_vecino"],"direccion_batea":r["direccion_batea"],
            "direccion_desmalezado":r["direccion_desmalezado"],
            "centroide_lat":float(r["centroide_lat"]) if r["centroide_lat"] else 0,
            "centroide_lon":float(r["centroide_lon"]) if r["centroide_lon"] else 0,
            "fecha_planificacion":r["fecha_planificacion"].strftime("%d/%m/%Y %H:%M"),
            "fecha_inicio":r["fecha_inicio"].strftime("%d/%m/%Y") if r["fecha_inicio"] else "",
            "fecha_termino":r["fecha_termino"].strftime("%d/%m/%Y") if r["fecha_termino"] else "",
            "dias_uso":r["dias_uso"] or 0,"responsable":r["responsable"] or "",
            "fotos_antes":parse_fotos(r.get("fotos_antes")),
            "fotos_despues":parse_fotos(r.get("fotos_despues")),
        } for r in rows],"total":len(rows)}
    except Exception as e:
        conn.close(); raise HTTPException(status_code=500,detail=str(e))

@app.delete("/api/solicitudes/{id}")
def eliminar_solicitud(id: str):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT folio FROM solicitudes WHERE id=%s", [id])
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close()
            raise HTTPException(status_code=404, detail="Solicitud no encontrada")
        cur.execute("DELETE FROM solicitudes WHERE id=%s", [id])
        conn.commit(); cur.close(); conn.close()
        return {"success": True, "mensaje": f"Solicitud {row[0]} eliminada correctamente"}
    except HTTPException: raise
    except Exception as e:
        conn.rollback(); conn.close(); raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/desmalezados/{id}")
def eliminar_desmalezado(id: str):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT folio FROM desmalezados WHERE id=%s", [id])
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close()
            raise HTTPException(status_code=404, detail="Desmalezado no encontrado")
        cur.execute("DELETE FROM desmalezados WHERE id=%s", [id])
        conn.commit(); cur.close(); conn.close()
        return {"success": True, "mensaje": f"Desmalezado {row[0]} eliminado correctamente"}
    except HTTPException: raise
    except Exception as e:
        conn.rollback(); conn.close(); raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/caminos/{id}")
def eliminar_camino(id: str):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT folio FROM arreglo_caminos WHERE id=%s", [id])
        row = cur.fetchone()
        if not row:
            cur.close(); conn.close()
            raise HTTPException(status_code=404, detail="Camino no encontrado")
        cur.execute("DELETE FROM arreglo_caminos WHERE id=%s", [id])
        conn.commit(); cur.close(); conn.close()
        return {"success": True, "mensaje": f"Camino {row[0]} eliminado correctamente"}
    except HTTPException: raise
    except Exception as e:
        conn.rollback(); conn.close(); raise HTTPException(status_code=500, detail=str(e))

# ═══════════════════════════════════════════════════════════════════════════════
# CLUSTERING
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/clustering/ejecutar")
def ejecutar_clustering(data: ClusteringRequest):
    conn = get_db()
    try:
        radio=data.radio_metros or 100; dias=data.dias_uso
        if dias<1 or dias>365: raise HTTPException(status_code=400,detail="Días entre 1 y 365")
        fi=parse_fecha(data.fecha_inicio) if data.fecha_inicio else datetime.now()
        ft=fi+timedelta(days=dias)
        cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT id,nombre_vecino,rut,direccion,CAST(latitud AS FLOAT) as latitud,CAST(longitud AS FLOAT) as longitud,
            fecha_solicitud,EXTRACT(DAY FROM (NOW()-fecha_solicitud))::INTEGER as dias
            FROM solicitudes WHERE estado='pendiente' AND latitud IS NOT NULL AND longitud IS NOT NULL
            ORDER BY CASE WHEN EXTRACT(DAY FROM (NOW()-fecha_solicitud))>=20 THEN 1 WHEN EXTRACT(DAY FROM (NOW()-fecha_solicitud))>=11 THEN 2 ELSE 3 END,fecha_solicitud ASC
        """)
        pendientes=cur.fetchall()
        if not pendientes:
            cur.close(); conn.close()
            return {"success":True,"grupos_creados":0,"bateas_asignadas":0,"solicitudes_agrupadas":0,"grupos_omitidos":0,"dias_uso":dias,"fecha_inicio":fi.strftime("%d/%m/%Y"),"fecha_termino":ft.strftime("%d/%m/%Y"),"mensaje":"No hay solicitudes pendientes","detalle_grupos":[]}
        cur.execute("SELECT CAST(centroide_lat AS FLOAT) as lat,CAST(centroide_lon AS FLOAT) as lon FROM grupos_territoriales")
        existentes=cur.fetchall()
        visitados=set(); grupos=[]
        for sol in pendientes:
            if sol["id"] in visitados: continue
            cluster=[sol]; visitados.add(sol["id"])
            for otra in pendientes:
                if otra["id"] in visitados: continue
                if distancia_metros(sol["latitud"],sol["longitud"],otra["latitud"],otra["longitud"])<=radio:
                    cluster.append(otra); visitados.add(otra["id"])
            cl=sum(s["latitud"] for s in cluster)/len(cluster)
            co=sum(s["longitud"] for s in cluster)/len(cluster)
            cercana=any(distancia_metros(cl,co,b["lat"],b["lon"])<=radio for b in existentes)
            grupos.append({"solicitudes":cluster,"cl":cl,"co":co,"cercana":cercana})
        resumen={"grupos_creados":0,"bateas_asignadas":0,"solicitudes_agrupadas":0,"grupos_omitidos":0,"dias_uso":dias,"fecha_inicio":fi.strftime("%d/%m/%Y"),"fecha_termino":ft.strftime("%d/%m/%Y"),"detalle_grupos":[]}
        for g in grupos:
            if g["cercana"]: resumen["grupos_omitidos"]+=1; continue
            gid=str(uuid.uuid4()); anio=datetime.now().year
            cur2=conn.cursor(); cur2.execute("SELECT COUNT(*) FROM grupos_territoriales WHERE codigo_grupo LIKE %s",[f"GT-{anio}-%"]); tot=cur2.fetchone()[0]; cur2.close()
            cg=f"GT-{anio}-{str(tot+1).zfill(4)}"; nb=f"BC-{anio}-{str(tot+1).zfill(4)}"
            cur.execute("INSERT INTO grupos_territoriales (id,codigo_grupo,numero_batea,centroide_lat,centroide_lon,radio_metros,total_vecinos,dias_uso,fecha_inicio,fecha_termino,estado_batea,fecha_creacion) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'asignada',NOW())",
                        [gid,cg,nb,g["cl"],g["co"],radio,len(g["solicitudes"]),dias,fi,ft])
            for sol in g["solicitudes"]:
                cur.execute("UPDATE solicitudes SET estado='asignada',grupo_id=%s,numero_batea=%s,fecha_asignacion=NOW() WHERE id=%s",[gid,nb,sol["id"]])
                cur.execute("INSERT INTO historial_bateas (id,rut,nombre_vecino,direccion,numero_batea,fecha_asignacion,fecha_termino,dias_uso) VALUES (%s,%s,%s,%s,%s,NOW(),%s,%s)",
                            [str(uuid.uuid4()),sol["rut"],sol["nombre_vecino"],sol["direccion"],nb,ft,dias])
            conn.commit()
            resumen["grupos_creados"]+=1; resumen["bateas_asignadas"]+=1; resumen["solicitudes_agrupadas"]+=len(g["solicitudes"])
            resumen["detalle_grupos"].append({"codigo_grupo":cg,"numero_batea":nb,"vecinos":len(g["solicitudes"]),"centroide_lat":g["cl"],"centroide_lon":g["co"],"dias_uso":dias,"fecha_inicio":fi.strftime("%d/%m/%Y"),"fecha_termino":ft.strftime("%d/%m/%Y"),"nombres":[s["nombre_vecino"] for s in g["solicitudes"]]})
        cur.close(); conn.close()
        resumen["success"]=True; resumen["mensaje"]=f"{resumen['grupos_creados']} grupos — {resumen['bateas_asignadas']} bateas — Desde {fi.strftime('%d/%m/%Y')} hasta {ft.strftime('%d/%m/%Y')} ({dias} días)"
        return resumen
    except HTTPException: raise
    except Exception as e:
        conn.rollback(); conn.close(); raise HTTPException(status_code=500,detail=str(e))

@app.get("/api/clustering/preview")
def preview_clustering(radio_metros: int=100):
    conn = get_db()
    try:
        cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT id,nombre_vecino,CAST(latitud AS FLOAT) as latitud,CAST(longitud AS FLOAT) as longitud,EXTRACT(DAY FROM (NOW()-fecha_solicitud))::INTEGER as dias FROM solicitudes WHERE estado='pendiente' AND latitud IS NOT NULL")
        pendientes=cur.fetchall(); cur.close(); conn.close()
        visitados=set(); grupos=[]
        for sol in pendientes:
            if sol["id"] in visitados: continue
            cluster=[sol]; visitados.add(sol["id"])
            for otra in pendientes:
                if otra["id"] in visitados: continue
                if distancia_metros(sol["latitud"],sol["longitud"],otra["latitud"],otra["longitud"])<=radio_metros:
                    cluster.append(otra); visitados.add(otra["id"])
            grupos.append({"vecinos":len(cluster),"nombres":[s["nombre_vecino"] for s in cluster],"dias_max":max(s["dias"] for s in cluster)})
        return {"total_pendientes":len(pendientes),"grupos_estimados":len(grupos),"radio_metros":radio_metros,"grupos":grupos}
    except Exception as e:
        conn.close(); raise HTTPException(status_code=500,detail=str(e))

# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/dashboard/kpis")
def kpis_dashboard():
    conn = get_db()
    try:
        cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT COUNT(*) FILTER (WHERE estado='pendiente') as pendientes,COUNT(*) FILTER (WHERE nivel_alerta='critica' AND estado='pendiente') as criticas,COUNT(*) FILTER (WHERE estado='asignada') as asignadas,COUNT(*) as total FROM solicitudes")
        kpis=dict(cur.fetchone())
        cur.execute("SELECT COUNT(*) as n FROM grupos_territoriales"); kpis["grupos"]=cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) as n FROM desmalezados WHERE estado='pendiente'"); kpis["desmalezados_pendientes"]=cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) as n FROM arreglo_caminos WHERE estado='pendiente'"); kpis["caminos_pendientes"]=cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) as n FROM operativos_conjuntos WHERE estado='planificado'"); kpis["operativos_conjuntos"]=cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) as n FROM grupos_territoriales WHERE fecha_termino IS NOT NULL AND fecha_termino<=NOW()+INTERVAL '2 days' AND fecha_termino>=NOW() AND estado_batea='asignada'")
        kpis["bateas_por_vencer"]=cur.fetchone()["n"]
        cur.close(); conn.close(); return kpis
    except Exception as e:
        conn.close(); raise HTTPException(status_code=500,detail=str(e))

@app.get("/api/vecinos/{rut}/historial")
def historial_vecino(rut: str):
    conn = get_db()
    try:
        historial=obtener_historial_vecino(conn,rut)
        cur=conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT folio,estado,fecha_solicitud,numero_batea,direccion FROM solicitudes WHERE rut=%s ORDER BY fecha_solicitud DESC",[rut])
        previas=cur.fetchall(); cur.close(); conn.close()
        alerta=f"⚠️ Este vecino ya recibió la batea {historial[0]['numero_batea']} el {historial[0]['fecha_asignacion']} por {historial[0]['dias_uso']} días en {historial[0]['direccion']}" if historial else None
        return {"rut":rut,"tuvo_batea_antes":len(historial)>0,"historial_bateas":historial,
                "solicitudes_previas":[{"folio":s["folio"],"estado":s["estado"],"fecha":s["fecha_solicitud"].strftime("%d/%m/%Y"),"batea":s["numero_batea"] or "-","direccion":s["direccion"]} for s in previas],
                "alerta":alerta}
    except Exception as e:
        conn.close(); raise HTTPException(status_code=500,detail=str(e))
