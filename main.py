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
    description="Sistema Municipal de Gestión de Bateas Comunitarias",
    version="1.0.0"
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

# ── UTILIDADES ────────────────────────────────────────────────────────────────

def calcular_folio(conn) -> str:
    cur = conn.cursor()
    anio = datetime.now().year
    cur.execute("SELECT COUNT(*) FROM solicitudes WHERE folio LIKE %s", [f"SOL-{anio}-%"])
    total = cur.fetchone()[0]
    cur.close()
    return f"SOL-{anio}-{str(total + 1).zfill(4)}"

def calcular_dias(fecha_solicitud) -> int:
    return (datetime.now() - fecha_solicitud).days

def calcular_alerta(dias: int) -> str:
    if dias >= 20:
        return "critica"
    elif dias >= 11:
        return "advertencia"
    return "normal"

def distancia_metros(lat1, lon1, lat2, lon2) -> float:
    """Calcula distancia en metros entre dos coordenadas usando Haversine"""
    R = 6371000  # radio tierra en metros
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def obtener_historial_vecino(conn, rut: str) -> List[dict]:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT numero_batea, fecha_asignacion, direccion, observaciones
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

def generar_numero_batea(conn) -> str:
    anio = datetime.now().year
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM grupos_territoriales WHERE codigo_grupo LIKE %s", [f"GT-{anio}-%"])
    total = cur.fetchone()[0]
    cur.close()
    return f"BC-{anio}-{str(total + 1).zfill(4)}"

def generar_codigo_grupo(conn) -> str:
    anio = datetime.now().year
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM grupos_territoriales WHERE codigo_grupo LIKE %s", [f"GT-{anio}-%"])
    total = cur.fetchone()[0]
    cur.close()
    return f"GT-{anio}-{str(total + 1).zfill(4)}"

# ── ENDPOINTS BASE ────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"sistema": "BateaControl", "estado": "operacional", "version": "1.0.0"}

@app.get("/api/health")
def health():
    return {"status": "ok"}

# ── CREAR SOLICITUD ───────────────────────────────────────────────────────────

@app.post("/api/solicitudes")
def crear_solicitud(data: SolicitudCreate):
    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Verificar solicitud pendiente duplicada
        cur.execute("""
            SELECT id, folio, fecha_solicitud FROM solicitudes
            WHERE rut = %s AND estado IN ('pendiente','agrupada')
        """, [data.rut])
        pendiente = cur.fetchone()
        if pendiente:
            cur.close()
            conn.close()
            raise HTTPException(status_code=400,
                detail=f"Este vecino ya tiene solicitud pendiente: {pendiente['folio']} del {pendiente['fecha_solicitud'].strftime('%d/%m/%Y')}")

        historial = obtener_historial_vecino(conn, data.rut)
        tuvo_batea = len(historial) > 0
        folio = calcular_folio(conn)
        solicitud_id = str(uuid.uuid4())

        cur.execute("""
            INSERT INTO solicitudes (
                id, folio, nombre_vecino, rut, direccion, telefono,
                latitud, longitud, observaciones, foto_url,
                estado, nivel_alerta, fecha_solicitud
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pendiente','normal',NOW())
        """, [solicitud_id, folio, data.nombre_vecino, data.rut,
              data.direccion, data.telefono, data.latitud, data.longitud,
              data.observaciones, data.foto_url])

        conn.commit()
        cur.close()
        conn.close()

        return {
            "success": True,
            "id": solicitud_id,
            "folio": folio,
            "mensaje": "Solicitud registrada exitosamente",
            "tuvo_batea_antes": tuvo_batea,
            "historial_previo": historial,
            "alerta_duplicado": f"⚠️ Este vecino ya recibió batea el {historial[0]['fecha_asignacion']} en {historial[0]['direccion']}" if tuvo_batea else None
        }

    except HTTPException:
        raise
    except Exception as e:
        conn.rollback()
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

# ── LISTAR SOLICITUDES ────────────────────────────────────────────────────────

@app.get("/api/solicitudes")
def listar_solicitudes(estado: Optional[str] = None):
    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Actualizar alertas automáticamente
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
                SELECT * FROM solicitudes
                ORDER BY
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
                "id": r["id"],
                "folio": r["folio"],
                "nombre_vecino": r["nombre_vecino"],
                "rut": r["rut"],
                "direccion": r["direccion"],
                "telefono": r["telefono"] or "",
                "latitud": float(r["latitud"]) if r["latitud"] else 0,
                "longitud": float(r["longitud"]) if r["longitud"] else 0,
                "observaciones": r["observaciones"] or "",
                "foto_url": r["foto_url"] or "",
                "estado": r["estado"],
                "nivel_alerta": calcular_alerta(dias),
                "fecha_solicitud": r["fecha_solicitud"].strftime("%d/%m/%Y %H:%M"),
                "dias_pendiente": dias,
                "numero_batea": r["numero_batea"] or "",
                "grupo_id": r["grupo_id"] or "",
                "tuvo_batea_antes": len(historial) > 0,
                "historial_previo": historial
            })

        return {"solicitudes": resultado, "total": len(resultado)}

    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

# ── HISTORIAL VECINO ──────────────────────────────────────────────────────────

@app.get("/api/vecinos/{rut}/historial")
def historial_vecino(rut: str):
    conn = get_db()
    try:
        historial = obtener_historial_vecino(conn, rut)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT folio, estado, fecha_solicitud, numero_batea, direccion
            FROM solicitudes WHERE rut=%s ORDER BY fecha_solicitud DESC
        """, [rut])
        solicitudes_previas = cur.fetchall()
        cur.close()
        conn.close()

        return {
            "rut": rut,
            "tuvo_batea_antes": len(historial) > 0,
            "historial_bateas": historial,
            "solicitudes_previas": [
                {
                    "folio": s["folio"],
                    "estado": s["estado"],
                    "fecha": s["fecha_solicitud"].strftime("%d/%m/%Y"),
                    "batea": s["numero_batea"] or "-",
                    "direccion": s["direccion"]
                }
                for s in solicitudes_previas
            ],
            "alerta": f"⚠️ Este vecino ya recibió batea el {historial[0]['fecha_asignacion']} en {historial[0]['direccion']}" if historial else None
        }
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

# ── CLUSTERING GEOESPACIAL ────────────────────────────────────────────────────

@app.post("/api/clustering/ejecutar")
def ejecutar_clustering(radio_metros: int = 100):
    """
    Motor de clustering geoespacial.
    - Prioriza solicitudes más antiguas y críticas
    - Agrupa TODAS las solicitudes pendientes
    - Radio configurable (default 100m)
    - Evita duplicar bateas en zonas ya cubiertas
    - Genera múltiples grupos en un solo click
    """
    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Cargar TODAS las solicitudes pendientes ordenadas por prioridad
        # Prioridad: críticas primero, luego por días (más antiguas primero)
        cur.execute("""
            SELECT id, nombre_vecino, rut, direccion,
                   CAST(latitud AS FLOAT) as latitud,
                   CAST(longitud AS FLOAT) as longitud,
                   fecha_solicitud,
                   EXTRACT(DAY FROM (NOW() - fecha_solicitud))::INTEGER as dias
            FROM solicitudes
            WHERE estado = 'pendiente'
              AND latitud IS NOT NULL
              AND longitud IS NOT NULL
            ORDER BY
                CASE
                    WHEN EXTRACT(DAY FROM (NOW() - fecha_solicitud)) >= 20 THEN 1
                    WHEN EXTRACT(DAY FROM (NOW() - fecha_solicitud)) >= 11 THEN 2
                    ELSE 3
                END,
                fecha_solicitud ASC
        """)
        pendientes = cur.fetchall()

        if not pendientes:
            cur.close()
            conn.close()
            return {
                "success": True,
                "grupos_creados": 0,
                "bateas_asignadas": 0,
                "solicitudes_agrupadas": 0,
                "grupos_omitidos": 0,
                "mensaje": "No hay solicitudes pendientes",
                "detalle_grupos": []
            }

        # Obtener bateas ya existentes para evitar duplicados
        cur.execute("""
            SELECT CAST(centroide_lat AS FLOAT) as lat,
                   CAST(centroide_lon AS FLOAT) as lon
            FROM grupos_territoriales
        """)
        bateas_existentes = cur.fetchall()

        # ── ALGORITMO DBSCAN SIMPLIFICADO ────────────────────────────────────
        visitados = set()
        grupos = []

        for solicitud in pendientes:
            if solicitud["id"] in visitados:
                continue

            # Iniciar nuevo cluster con esta solicitud como semilla
            cluster = [solicitud]
            visitados.add(solicitud["id"])

            # Buscar todos los vecinos dentro del radio
            for otra in pendientes:
                if otra["id"] in visitados:
                    continue
                dist = distancia_metros(
                    solicitud["latitud"], solicitud["longitud"],
                    otra["latitud"], otra["longitud"]
                )
                if dist <= radio_metros:
                    cluster.append(otra)
                    visitados.add(otra["id"])

            # Calcular centroide del cluster
            cent_lat = sum(s["latitud"] for s in cluster) / len(cluster)
            cent_lon = sum(s["longitud"] for s in cluster) / len(cluster)

            # Verificar si ya existe batea cerca del centroide
            batea_cercana = False
            for b in bateas_existentes:
                dist = distancia_metros(cent_lat, cent_lon, b["lat"], b["lon"])
                if dist <= radio_metros:
                    batea_cercana = True
                    break

            grupos.append({
                "solicitudes": cluster,
                "centroide_lat": cent_lat,
                "centroide_lon": cent_lon,
                "batea_cercana": batea_cercana
            })

        # ── CREAR GRUPOS Y ASIGNAR BATEAS ─────────────────────────────────────
        resumen = {
            "grupos_creados": 0,
            "bateas_asignadas": 0,
            "solicitudes_agrupadas": 0,
            "grupos_omitidos": 0,
            "detalle_grupos": []
        }

        for grupo in grupos:
            if grupo["batea_cercana"]:
                resumen["grupos_omitidos"] += 1
                continue

            grupo_id = str(uuid.uuid4())
            codigo_grupo = generar_codigo_grupo(conn)
            numero_batea = generar_numero_batea(conn)

            # Insertar grupo territorial
            cur.execute("""
                INSERT INTO grupos_territoriales (
                    id, codigo_grupo, numero_batea,
                    centroide_lat, centroide_lon,
                    radio_metros, total_vecinos, fecha_creacion
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,NOW())
            """, [
                grupo_id, codigo_grupo, numero_batea,
                grupo["centroide_lat"], grupo["centroide_lon"],
                radio_metros, len(grupo["solicitudes"])
            ])

            # Actualizar todas las solicitudes del grupo
            ids = [s["id"] for s in grupo["solicitudes"]]
            for sol_id in ids:
                cur.execute("""
                    UPDATE solicitudes
                    SET estado='asignada',
                        grupo_id=%s,
                        numero_batea=%s,
                        fecha_asignacion=NOW(),
                        actualizado_en=NOW()
                    WHERE id=%s
                """, [grupo_id, numero_batea, sol_id])

                # Registrar en historial para cada vecino
                sol = next(s for s in grupo["solicitudes"] if s["id"] == sol_id)
                cur.execute("""
                    INSERT INTO historial_bateas (
                        id, rut, nombre_vecino, direccion,
                        numero_batea, fecha_asignacion
                    ) VALUES (%s,%s,%s,%s,%s,NOW())
                """, [
                    str(uuid.uuid4()),
                    sol["rut"],
                    sol["nombre_vecino"],
                    sol["direccion"],
                    numero_batea
                ])

            conn.commit()

            resumen["grupos_creados"] += 1
            resumen["bateas_asignadas"] += 1
            resumen["solicitudes_agrupadas"] += len(grupo["solicitudes"])
            resumen["detalle_grupos"].append({
                "codigo_grupo": codigo_grupo,
                "numero_batea": numero_batea,
                "vecinos": len(grupo["solicitudes"]),
                "centroide_lat": grupo["centroide_lat"],
                "centroide_lon": grupo["centroide_lon"],
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

# ── KPIs DASHBOARD ────────────────────────────────────────────────────────────

@app.get("/api/dashboard/kpis")
def kpis_dashboard():
    conn = get_db()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE estado='pendiente') as pendientes,
                COUNT(*) FILTER (WHERE nivel_alerta='critica' AND estado='pendiente') as criticas,
                COUNT(*) FILTER (WHERE estado='asignada') as asignadas,
                COUNT(*) FILTER (WHERE estado='instalada') as instaladas,
                COUNT(*) as total
            FROM solicitudes
        """)
        kpis = dict(cur.fetchone())
        cur.execute("SELECT COUNT(*) as grupos FROM grupos_territoriales")
        kpis["grupos"] = cur.fetchone()["grupos"]
        cur.close()
        conn.close()
        return kpis
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))
