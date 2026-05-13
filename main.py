from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import psycopg2
import psycopg2.extras
import os
from datetime import datetime
import uuid
import math

app = FastAPI(
    title="BateaControl API",
    description="Sistema Municipal de Gestión de Servicios Territoriales",
    version="2.0.0"
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

    # ── TABLA SOLICITUDES ──────────────────────────────────────────────────
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

    # Agregar columnas faltantes si no existen (para tablas ya creadas)
    columnas_solicitudes = [
        ("grupo_id", "VARCHAR(50)"),
        ("numero_batea", "VARCHAR(30)"),
        ("fecha_asignacion", "TIMESTAMP"),
        ("actualizado_en", "TIMESTAMP DEFAULT NOW()"),
    ]
    for col, tipo in columnas_solicitudes:
        try:
            cur.execute(f"ALTER TABLE solicitudes ADD COLUMN IF NOT EXISTS {col} {tipo}")
        except Exception:
            conn.rollback()

    # ── TABLA DESMALEZADOS ─────────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS desmalezados (
            id VARCHAR(50) PRIMARY KEY,
            folio VARCHAR(30) UNIQUE,
            nombre_solicitante VARCHAR(150),
            es_recordatorio BOOLEAN DEFAULT FALSE,
            direccion VARCHAR(255) NOT NULL,
            descripcion TEXT,
            latitud DECIMAL(10,8),
            longitud DECIMAL(11,8),
            foto_antes TEXT,
            foto_despues TEXT,
            estado VARCHAR(30) DEFAULT 'pendiente',
            fecha_solicitud TIMESTAMP DEFAULT NOW(),
            fecha_ejecucion TIMESTAMP,
            fecha_cierre TIMESTAMP,
            operativo_conjunto_id VARCHAR(50),
            observaciones_cierre TEXT,
            creado_en TIMESTAMP DEFAULT NOW()
        )
    """)

    # ── TABLA ARREGLO DE CAMINOS ───────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS arreglo_caminos (
            id VARCHAR(50) PRIMARY KEY,
            folio VARCHAR(30) UNIQUE,
            nombre_solicitante VARCHAR(150),
            es_recordatorio BOOLEAN DEFAULT FALSE,
            direccion VARCHAR(255) NOT NULL,
            tipo_camino VARCHAR(50) DEFAULT 'camino',
            descripcion_problema TEXT,
            latitud DECIMAL(10,8),
            longitud DECIMAL(11,8),
            foto_antes TEXT,
            foto_despues TEXT,
            estado VARCHAR(30) DEFAULT 'pendiente',
            prioridad VARCHAR(20) DEFAULT 'normal',
            fecha_solicitud TIMESTAMP DEFAULT NOW(),
            fecha_ejecucion TIMESTAMP,
            fecha_cierre TIMESTAMP,
            observaciones_cierre TEXT,
            creado_en TIMESTAMP DEFAULT NOW()
        )
    """)

    # ── TABLA OPERATIVOS CONJUNTOS ─────────────────────────────────────────
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
            fecha_ejecucion TIMESTAMP,
            fecha_cierre TIMESTAMP,
            observaciones TEXT,
            foto_antes TEXT,
            foto_despues TEXT,
            creado_en TIMESTAMP DEFAULT NOW()
        )
    """)

    # ── TABLA GRUPOS TERRITORIALES ─────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS grupos_territoriales (
            id VARCHAR(50) PRIMARY KEY,
            codigo_grupo VARCHAR(30) UNIQUE,
            numero_batea VARCHAR(30),
            centroide_lat DECIMAL(10,8),
            centroide_lon DECIMAL(11,8),
            radio_metros INTEGER DEFAULT 100,
            total_vecinos INTEGER DEFAULT 0,
            fecha_creacion TIMESTAMP DEFAULT NOW()
        )
    """)

    # ── TABLA HISTORIAL BATEAS ─────────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS historial_bateas (
            id VARCHAR(50) PRIMARY KEY,
            rut VARCHAR(15) NOT NULL,
            nombre_vecino VARCHAR(150),
            direccion VARCHAR(255),
            numero_batea VARCHAR(30),
            fecha_asignacion TIMESTAMP,
            fecha_retiro TIMESTAMP,
            observaciones TEXT,
            creado_en TIMESTAMP DEFAULT NOW()
        )
    """)

    conn.commit()
    cur.close()
    conn.close()

try:
    init_db()
except Exception as e:
    print(f"Error inicializando DB: {e}")

# ── MODELOS ───────────────────────────────────────────────────────────────────

class SolicitudCreate(BaseModel):
    nombre_vecino: str
    rut: str
    direccion: str
    telefono: Optional[str] = ""
    latitud: float
    longitud: float
    observaciones: Optional[str] = ""
    foto_url: Optional[str] = ""

class DesmalezadoCreate(BaseModel):
    nombre_solicitante: Optional[str] = ""
    es_recordatorio: bool = False
    direccion: str
    descripcion: Optional[str] = ""
    latitud: float
    longitud: float
    foto_antes: Optional[str] = ""

class DesmalezadoCierre(BaseModel):
    foto_despues: Optional[str] = ""
    observaciones_cierre: Optional[str] = ""

class CaminoCreate(BaseModel):
    nombre_solicitante: Optional[str] = ""
    es_recordatorio: bool = False
    direccion: str
    tipo_camino: Optional[str] = "camino"
    descripcion_problema: Optional[str] = ""
    latitud: float
    longitud: float
    foto_antes: Optional[str] = ""
    prioridad: Optional[str] = "normal"

class CaminoCierre(BaseModel):
    foto_despues: Optional[str] = ""
    observaciones_cierre: Optional[str] = ""

# ── UTILIDADES ────────────────────────────────────────────────────────────────

def distancia_metros(lat1, lon1, lat2, lon2) -> float:
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def calcular_dias(fecha) -> int:
    return (datetime.now() - fecha).days

def calcular_alerta(dias: int) -> str:
    if dias >= 20: return "critica"
    elif dias >= 11: return "advertencia"
    return "normal"

def gen_folio(conn, prefijo: str, tabla: str) -> str:
    anio = datetime.now().year
    cur = conn.cursor()
    cur.execute(f"SELECT COUNT(*) FROM {tabla} WHERE folio LIKE %s", [f"{prefijo}-{anio}-%"])
    total = cur.fetchone()[0]
    cur.close()
    return f"{prefijo}-{anio}-{str(total + 1).zfill(4)}"

def obtener_historial_vecino(conn, rut: str) -> List[dict]:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT numero_batea, fecha_asignacion, direccion
        FROM historial_bateas WHERE rut = %s
        ORDER BY fecha_asignacion DESC
    """, [rut])
    rows = cur.fetchall()
    cur.close()
    return [
        {
            "numero_batea": r["numero_batea"],
            "fecha_asignacion": r["fecha_asignacion"].strftime("%d/%m/%Y") if r["fecha_asignacion"] else "",
            "direccion": r["direccion"],
        }
        for r in rows
    ]

# ── HEALTH ────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"sistema": "BateaControl", "version": "2.0.0", "estado": "operacional"}

@app.get("/api/health")
def health():
    return {"status": "ok"}

# ═══════════════════════════════════════════════════════════════════════════════
# BATEAS
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/solicitudes")
def crear_solicitud(data: SolicitudCreate):
    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT id, folio, fecha_solicitud FROM solicitudes
            WHERE rut = %s AND estado IN ('pendiente','agrupada')
        """, [data.rut])
        pendiente = cur.fetchone()
        if pendiente:
            cur.close()
            conn.close()
            raise HTTPException(status_code=400,
                detail=f"Vecino ya tiene solicitud pendiente: {pendiente['folio']} del {pendiente['fecha_solicitud'].strftime('%d/%m/%Y')}")

        historial = obtener_historial_vecino(conn, data.rut)
        folio = gen_folio(conn, "SOL", "solicitudes")
        sid = str(uuid.uuid4())

        cur.execute("""
            INSERT INTO solicitudes (
                id, folio, nombre_vecino, rut, direccion, telefono,
                latitud, longitud, observaciones, foto_url,
                estado, nivel_alerta, fecha_solicitud
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pendiente','normal',NOW())
        """, [sid, folio, data.nombre_vecino, data.rut,
              data.direccion, data.telefono, data.latitud, data.longitud,
              data.observaciones, data.foto_url])
        conn.commit()
        cur.close()
        conn.close()

        return {
            "success": True, "id": sid, "folio": folio,
            "mensaje": "Solicitud registrada exitosamente",
            "tuvo_batea_antes": len(historial) > 0,
            "historial_previo": historial,
            "alerta_duplicado": f"⚠️ Este vecino ya recibió batea el {historial[0]['fecha_asignacion']} en {historial[0]['direccion']}" if historial else None
        }
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/solicitudes")
def listar_solicitudes(estado: Optional[str] = None):
    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            UPDATE solicitudes SET nivel_alerta = CASE
                WHEN EXTRACT(DAY FROM (NOW() - fecha_solicitud)) >= 20 THEN 'critica'
                WHEN EXTRACT(DAY FROM (NOW() - fecha_solicitud)) >= 11 THEN 'advertencia'
                ELSE 'normal'
            END WHERE estado = 'pendiente'
        """)
        conn.commit()
        if estado:
            cur.execute("SELECT * FROM solicitudes WHERE estado=%s ORDER BY fecha_solicitud ASC", [estado])
        else:
            cur.execute("""
                SELECT * FROM solicitudes ORDER BY
                CASE nivel_alerta WHEN 'critica' THEN 1 WHEN 'advertencia' THEN 2 ELSE 3 END,
                fecha_solicitud ASC
            """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        resultado = []
        for r in rows:
            conn2 = get_db()
            historial = obtener_historial_vecino(conn2, r["rut"])
            conn2.close()
            dias = calcular_dias(r["fecha_solicitud"])
            resultado.append({
                "id": r["id"], "folio": r["folio"],
                "nombre_vecino": r["nombre_vecino"], "rut": r["rut"],
                "direccion": r["direccion"], "telefono": r["telefono"] or "",
                "latitud": float(r["latitud"]) if r["latitud"] else 0,
                "longitud": float(r["longitud"]) if r["longitud"] else 0,
                "observaciones": r["observaciones"] or "",
                "foto_url": r["foto_url"] or "",
                "estado": r["estado"],
                "nivel_alerta": calcular_alerta(dias),
                "fecha_solicitud": r["fecha_solicitud"].strftime("%d/%m/%Y %H:%M"),
                "dias_pendiente": dias,
                "numero_batea": r["numero_batea"] or "" if "numero_batea" in r.keys() else "",
                "grupo_id": r["grupo_id"] or "" if "grupo_id" in r.keys() else "",
                "tuvo_batea_antes": len(historial) > 0,
                "historial_previo": historial
            })
        return {"solicitudes": resultado, "total": len(resultado)}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

# ═══════════════════════════════════════════════════════════════════════════════
# DESMALEZADOS
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/desmalezados")
def crear_desmalezado(data: DesmalezadoCreate):
    conn = get_db()
    try:
        folio = gen_folio(conn, "DES", "desmalezados")
        did = str(uuid.uuid4())
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO desmalezados (
                id, folio, nombre_solicitante, es_recordatorio,
                direccion, descripcion, latitud, longitud,
                foto_antes, estado, fecha_solicitud
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'pendiente',NOW())
        """, [did, folio, data.nombre_solicitante, data.es_recordatorio,
              data.direccion, data.descripcion, data.latitud, data.longitud,
              data.foto_antes])

        cur2 = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur2.execute("""
            SELECT id, nombre_vecino, direccion, latitud, longitud
            FROM solicitudes WHERE estado='pendiente'
            AND latitud IS NOT NULL AND longitud IS NOT NULL
        """)
        bateas_pendientes = cur2.fetchall()
        cur2.close()

        sugerencia_conjunto = None
        for b in bateas_pendientes:
            dist = distancia_metros(
                data.latitud, data.longitud,
                float(b["latitud"]), float(b["longitud"])
            )
            if dist <= 100:
                sugerencia_conjunto = {
                    "batea_id": b["id"],
                    "vecino": b["nombre_vecino"],
                    "direccion": b["direccion"],
                    "distancia_metros": round(dist, 1)
                }
                break

        conn.commit()
        cur.close()
        conn.close()

        return {
            "success": True, "id": did, "folio": folio,
            "mensaje": "Desmalezado registrado exitosamente",
            "sugerencia_operativo_conjunto": sugerencia_conjunto,
            "alerta_conjunto": f"🔧 Hay una batea pendiente a {sugerencia_conjunto['distancia_metros']}m — ¿Crear Operativo Conjunto?" if sugerencia_conjunto else None
        }
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/desmalezados")
def listar_desmalezados(estado: Optional[str] = None):
    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if estado:
            cur.execute("SELECT * FROM desmalezados WHERE estado=%s ORDER BY fecha_solicitud ASC", [estado])
        else:
            cur.execute("SELECT * FROM desmalezados ORDER BY fecha_solicitud ASC")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {
            "desmalezados": [
                {
                    "id": r["id"], "folio": r["folio"],
                    "nombre_solicitante": r["nombre_solicitante"] or "Sin nombre",
                    "es_recordatorio": r["es_recordatorio"],
                    "direccion": r["direccion"],
                    "descripcion": r["descripcion"] or "",
                    "latitud": float(r["latitud"]) if r["latitud"] else 0,
                    "longitud": float(r["longitud"]) if r["longitud"] else 0,
                    "foto_antes": r["foto_antes"] or "",
                    "foto_despues": r["foto_despues"] or "",
                    "estado": r["estado"],
                    "fecha_solicitud": r["fecha_solicitud"].strftime("%d/%m/%Y %H:%M"),
                    "dias_pendiente": calcular_dias(r["fecha_solicitud"])
                }
                for r in rows
            ],
            "total": len(rows)
        }
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/desmalezados/{id}/cerrar")
def cerrar_desmalezado(id: str, data: DesmalezadoCierre):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE desmalezados SET estado='completado', foto_despues=%s,
            observaciones_cierre=%s, fecha_cierre=NOW() WHERE id=%s
        """, [data.foto_despues, data.observaciones_cierre, id])
        conn.commit()
        cur.close()
        conn.close()
        return {"success": True, "mensaje": "Desmalezado cerrado exitosamente"}
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

# ═══════════════════════════════════════════════════════════════════════════════
# ARREGLO DE CAMINOS
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/caminos")
def crear_camino(data: CaminoCreate):
    conn = get_db()
    try:
        folio = gen_folio(conn, "CAM", "arreglo_caminos")
        cid = str(uuid.uuid4())
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO arreglo_caminos (
                id, folio, nombre_solicitante, es_recordatorio,
                direccion, tipo_camino, descripcion_problema,
                latitud, longitud, foto_antes, estado, prioridad, fecha_solicitud
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pendiente',%s,NOW())
        """, [cid, folio, data.nombre_solicitante, data.es_recordatorio,
              data.direccion, data.tipo_camino, data.descripcion_problema,
              data.latitud, data.longitud, data.foto_antes, data.prioridad])
        conn.commit()
        cur.close()
        conn.close()
        return {"success": True, "id": cid, "folio": folio, "mensaje": "Arreglo de camino registrado exitosamente"}
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/caminos")
def listar_caminos(estado: Optional[str] = None):
    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        if estado:
            cur.execute("SELECT * FROM arreglo_caminos WHERE estado=%s ORDER BY fecha_solicitud ASC", [estado])
        else:
            cur.execute("""
                SELECT * FROM arreglo_caminos ORDER BY
                CASE prioridad WHEN 'urgente' THEN 1 WHEN 'alta' THEN 2 ELSE 3 END,
                fecha_solicitud ASC
            """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {
            "caminos": [
                {
                    "id": r["id"], "folio": r["folio"],
                    "nombre_solicitante": r["nombre_solicitante"] or "Registro interno",
                    "es_recordatorio": r["es_recordatorio"],
                    "direccion": r["direccion"],
                    "tipo_camino": r["tipo_camino"],
                    "descripcion_problema": r["descripcion_problema"] or "",
                    "latitud": float(r["latitud"]) if r["latitud"] else 0,
                    "longitud": float(r["longitud"]) if r["longitud"] else 0,
                    "foto_antes": r["foto_antes"] or "",
                    "foto_despues": r["foto_despues"] or "",
                    "estado": r["estado"],
                    "prioridad": r["prioridad"],
                    "fecha_solicitud": r["fecha_solicitud"].strftime("%d/%m/%Y %H:%M"),
                    "fecha_cierre": r["fecha_cierre"].strftime("%d/%m/%Y") if r["fecha_cierre"] else "",
                    "dias_pendiente": calcular_dias(r["fecha_solicitud"])
                }
                for r in rows
            ],
            "total": len(rows)
        }
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/caminos/{id}/cerrar")
def cerrar_camino(id: str, data: CaminoCierre):
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE arreglo_caminos SET estado='completado', foto_despues=%s,
            observaciones_cierre=%s, fecha_cierre=NOW() WHERE id=%s
        """, [data.foto_despues, data.observaciones_cierre, id])
        conn.commit()
        cur.close()
        conn.close()
        return {"success": True, "mensaje": "Arreglo de camino cerrado exitosamente"}
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIVOS CONJUNTOS
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/operativos-conjuntos")
def crear_operativo_conjunto(solicitud_batea_id: str, desmalezado_id: str):
    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT * FROM solicitudes WHERE id=%s", [solicitud_batea_id])
        batea = cur.fetchone()
        cur.execute("SELECT * FROM desmalezados WHERE id=%s", [desmalezado_id])
        desmalezado = cur.fetchone()
        if not batea or not desmalezado:
            raise HTTPException(status_code=404, detail="Solicitud no encontrada")

        cent_lat = (float(batea["latitud"]) + float(desmalezado["latitud"])) / 2
        cent_lon = (float(batea["longitud"]) + float(desmalezado["longitud"])) / 2

        cur2 = conn.cursor()
        cur2.execute("SELECT COUNT(*) FROM operativos_conjuntos")
        total = cur2.fetchone()[0]
        cur2.close()

        anio = datetime.now().year
        codigo = f"OPC-{anio}-{str(total + 1).zfill(4)}"
        numero_batea = f"BC-{anio}-{str(total + 1).zfill(4)}"
        oid = str(uuid.uuid4())

        cur.execute("""
            INSERT INTO operativos_conjuntos (
                id, codigo, solicitud_batea_id, desmalezado_id,
                centroide_lat, centroide_lon, numero_batea, estado, fecha_planificacion
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,'planificado',NOW())
        """, [oid, codigo, solicitud_batea_id, desmalezado_id, cent_lat, cent_lon, numero_batea])

        cur.execute("UPDATE solicitudes SET estado='asignada', numero_batea=%s WHERE id=%s", [numero_batea, solicitud_batea_id])
        cur.execute("UPDATE desmalezados SET estado='planificado', operativo_conjunto_id=%s WHERE id=%s", [oid, desmalezado_id])

        conn.commit()
        cur.close()
        conn.close()
        return {
            "success": True, "id": oid, "codigo": codigo,
            "numero_batea": numero_batea,
            "mensaje": f"Operativo Conjunto {codigo} creado — Batea {numero_batea} asignada"
        }
    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/operativos-conjuntos")
def listar_operativos_conjuntos():
    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT oc.*, s.nombre_vecino, s.direccion as direccion_batea,
                d.direccion as direccion_desmalezado, d.nombre_solicitante as solicitante_desmalezado
            FROM operativos_conjuntos oc
            LEFT JOIN solicitudes s ON oc.solicitud_batea_id = s.id
            LEFT JOIN desmalezados d ON oc.desmalezado_id = d.id
            ORDER BY oc.fecha_planificacion DESC
        """)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {
            "operativos": [
                {
                    "id": r["id"], "codigo": r["codigo"],
                    "numero_batea": r["numero_batea"], "estado": r["estado"],
                    "nombre_vecino": r["nombre_vecino"],
                    "direccion_batea": r["direccion_batea"],
                    "direccion_desmalezado": r["direccion_desmalezado"],
                    "centroide_lat": float(r["centroide_lat"]) if r["centroide_lat"] else 0,
                    "centroide_lon": float(r["centroide_lon"]) if r["centroide_lon"] else 0,
                    "fecha_planificacion": r["fecha_planificacion"].strftime("%d/%m/%Y %H:%M"),
                }
                for r in rows
            ],
            "total": len(rows)
        }
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

# ═══════════════════════════════════════════════════════════════════════════════
# CLUSTERING
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/clustering/ejecutar")
def ejecutar_clustering(radio_metros: int = 100):
    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT id, nombre_vecino, rut, direccion,
                   CAST(latitud AS FLOAT) as latitud,
                   CAST(longitud AS FLOAT) as longitud,
                   fecha_solicitud,
                   EXTRACT(DAY FROM (NOW() - fecha_solicitud))::INTEGER as dias
            FROM solicitudes
            WHERE estado = 'pendiente'
              AND latitud IS NOT NULL AND longitud IS NOT NULL
            ORDER BY
                CASE WHEN EXTRACT(DAY FROM (NOW() - fecha_solicitud)) >= 20 THEN 1
                     WHEN EXTRACT(DAY FROM (NOW() - fecha_solicitud)) >= 11 THEN 2
                     ELSE 3 END,
                fecha_solicitud ASC
        """)
        pendientes = cur.fetchall()

        if not pendientes:
            cur.close()
            conn.close()
            return {
                "success": True, "grupos_creados": 0, "bateas_asignadas": 0,
                "solicitudes_agrupadas": 0, "grupos_omitidos": 0,
                "mensaje": "No hay solicitudes pendientes", "detalle_grupos": []
            }

        cur.execute("""
            SELECT CAST(centroide_lat AS FLOAT) as lat, CAST(centroide_lon AS FLOAT) as lon
            FROM grupos_territoriales
        """)
        bateas_existentes = cur.fetchall()

        visitados = set()
        grupos = []

        for solicitud in pendientes:
            if solicitud["id"] in visitados:
                continue
            cluster = [solicitud]
            visitados.add(solicitud["id"])
            for otra in pendientes:
                if otra["id"] in visitados:
                    continue
                dist = distancia_metros(solicitud["latitud"], solicitud["longitud"], otra["latitud"], otra["longitud"])
                if dist <= radio_metros:
                    cluster.append(otra)
                    visitados.add(otra["id"])

            cent_lat = sum(s["latitud"] for s in cluster) / len(cluster)
            cent_lon = sum(s["longitud"] for s in cluster) / len(cluster)
            batea_cercana = any(distancia_metros(cent_lat, cent_lon, b["lat"], b["lon"]) <= radio_metros for b in bateas_existentes)
            grupos.append({"solicitudes": cluster, "centroide_lat": cent_lat, "centroide_lon": cent_lon, "batea_cercana": batea_cercana})

        resumen = {"grupos_creados":0, "bateas_asignadas":0, "solicitudes_agrupadas":0, "grupos_omitidos":0, "detalle_grupos":[]}

        for grupo in grupos:
            if grupo["batea_cercana"]:
                resumen["grupos_omitidos"] += 1
                continue

            grupo_id = str(uuid.uuid4())
            anio = datetime.now().year
            cur2 = conn.cursor()
            cur2.execute("SELECT COUNT(*) FROM grupos_territoriales WHERE codigo_grupo LIKE %s", [f"GT-{anio}-%"])
            total = cur2.fetchone()[0]
            cur2.close()
            codigo_grupo = f"GT-{anio}-{str(total+1).zfill(4)}"
            numero_batea = f"BC-{anio}-{str(total+1).zfill(4)}"

            cur.execute("""
                INSERT INTO grupos_territoriales (id, codigo_grupo, numero_batea, centroide_lat, centroide_lon, radio_metros, total_vecinos, fecha_creacion)
                VALUES (%s,%s,%s,%s,%s,%s,%s,NOW())
            """, [grupo_id, codigo_grupo, numero_batea, grupo["centroide_lat"], grupo["centroide_lon"], radio_metros, len(grupo["solicitudes"])])

            for sol in grupo["solicitudes"]:
                cur.execute("UPDATE solicitudes SET estado='asignada', grupo_id=%s, numero_batea=%s, fecha_asignacion=NOW() WHERE id=%s",
                            [grupo_id, numero_batea, sol["id"]])
                cur.execute("INSERT INTO historial_bateas (id, rut, nombre_vecino, direccion, numero_batea, fecha_asignacion) VALUES (%s,%s,%s,%s,%s,NOW())",
                            [str(uuid.uuid4()), sol["rut"], sol["nombre_vecino"], sol["direccion"], numero_batea])

            conn.commit()
            resumen["grupos_creados"] += 1
            resumen["bateas_asignadas"] += 1
            resumen["solicitudes_agrupadas"] += len(grupo["solicitudes"])
            resumen["detalle_grupos"].append({
                "codigo_grupo": codigo_grupo, "numero_batea": numero_batea,
                "vecinos": len(grupo["solicitudes"]),
                "centroide_lat": grupo["centroide_lat"], "centroide_lon": grupo["centroide_lon"],
                "nombres": [s["nombre_vecino"] for s in grupo["solicitudes"]]
            })

        cur.close()
        conn.close()
        resumen["success"] = True
        resumen["mensaje"] = f"{resumen['grupos_creados']} grupos creados, {resumen['bateas_asignadas']} bateas asignadas, {resumen['solicitudes_agrupadas']} vecinos atendidos"
        return resumen

    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD KPIs
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/dashboard/kpis")
def kpis_dashboard():
    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT COUNT(*) FILTER (WHERE estado='pendiente') as pendientes,
                   COUNT(*) FILTER (WHERE nivel_alerta='critica' AND estado='pendiente') as criticas,
                   COUNT(*) FILTER (WHERE estado='asignada') as asignadas,
                   COUNT(*) as total
            FROM solicitudes
        """)
        kpis = dict(cur.fetchone())
        cur.execute("SELECT COUNT(*) as grupos FROM grupos_territoriales")
        kpis["grupos"] = cur.fetchone()["grupos"]
        cur.execute("SELECT COUNT(*) as n FROM desmalezados WHERE estado='pendiente'")
        kpis["desmalezados_pendientes"] = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) as n FROM arreglo_caminos WHERE estado='pendiente'")
        kpis["caminos_pendientes"] = cur.fetchone()["n"]
        cur.execute("SELECT COUNT(*) as n FROM operativos_conjuntos WHERE estado='planificado'")
        kpis["operativos_conjuntos"] = cur.fetchone()["n"]
        cur.close()
        conn.close()
        return kpis
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

# ═══════════════════════════════════════════════════════════════════════════════
# HISTORIAL VECINO
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/vecinos/{rut}/historial")
def historial_vecino(rut: str):
    conn = get_db()
    try:
        historial = obtener_historial_vecino(conn, rut)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT folio, estado, fecha_solicitud, numero_batea, direccion FROM solicitudes WHERE rut=%s ORDER BY fecha_solicitud DESC", [rut])
        solicitudes_previas = cur.fetchall()
        cur.close()
        conn.close()
        return {
            "rut": rut,
            "tuvo_batea_antes": len(historial) > 0,
            "historial_bateas": historial,
            "solicitudes_previas": [
                {"folio": s["folio"], "estado": s["estado"], "fecha": s["fecha_solicitud"].strftime("%d/%m/%Y"), "batea": s["numero_batea"] or "-", "direccion": s["direccion"]}
                for s in solicitudes_previas
            ],
            "alerta": f"⚠️ Este vecino ya recibió batea el {historial[0]['fecha_asignacion']} en {historial[0]['direccion']}" if historial else None
        }
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))
