from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import psycopg2
import psycopg2.extras
import os
from datetime import datetime, date
import uuid

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
    """Crear tablas si no existen"""
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
            creado_en TIMESTAMP DEFAULT NOW(),
            actualizado_en TIMESTAMP DEFAULT NOW()
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

# Inicializar DB al arrancar
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

class SolicitudResponse(BaseModel):
    id: str
    folio: str
    nombre_vecino: str
    rut: str
    direccion: str
    telefono: Optional[str]
    latitud: float
    longitud: float
    observaciones: Optional[str]
    foto_url: Optional[str]
    estado: str
    nivel_alerta: str
    fecha_solicitud: str
    dias_pendiente: int
    numero_batea: Optional[str]
    tuvo_batea_antes: bool
    historial_previo: List[dict]

# ── UTILIDADES ────────────────────────────────────────────────────────────────

def calcular_folio(conn) -> str:
    cur = conn.cursor()
    anio = datetime.now().year
    cur.execute("SELECT COUNT(*) FROM solicitudes WHERE folio LIKE %s", [f"SOL-{anio}-%"])
    total = cur.fetchone()[0]
    cur.close()
    return f"SOL-{anio}-{str(total + 1).zfill(4)}"

def calcular_alerta(fecha_solicitud) -> str:
    dias = (datetime.now() - fecha_solicitud).days
    if dias >= 20:
        return "critica"
    elif dias >= 11:
        return "advertencia"
    return "normal"

def calcular_dias(fecha_solicitud) -> int:
    return (datetime.now() - fecha_solicitud).days

def obtener_historial_vecino(conn, rut: str) -> List[dict]:
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT numero_batea, fecha_asignacion, direccion, observaciones
        FROM historial_bateas
        WHERE rut = %s
        ORDER BY fecha_asignacion DESC
    """, [rut])
    rows = cur.fetchall()
    cur.close()
    return [
        {
            "numero_batea": r["numero_batea"],
            "fecha_asignacion": r["fecha_asignacion"].strftime("%d/%m/%Y") if r["fecha_asignacion"] else "",
            "direccion": r["direccion"],
            "observaciones": r["observaciones"] or ""
        }
        for r in rows
    ]

# ── ENDPOINTS ─────────────────────────────────────────────────────────────────

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
        # Verificar si ya tiene solicitud pendiente
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT id, folio, fecha_solicitud FROM solicitudes
            WHERE rut = %s AND estado IN ('pendiente', 'agrupada')
        """, [data.rut])
        pendiente = cur.fetchone()
        if pendiente:
            cur.close()
            conn.close()
            raise HTTPException(
                status_code=400,
                detail=f"Este vecino ya tiene una solicitud pendiente: {pendiente['folio']} del {pendiente['fecha_solicitud'].strftime('%d/%m/%Y')}"
            )

        # Obtener historial previo
        historial = obtener_historial_vecino(conn, data.rut)
        tuvo_batea = len(historial) > 0

        # Generar folio e ID
        folio = calcular_folio(conn)
        solicitud_id = str(uuid.uuid4())

        # Insertar solicitud
        cur.execute("""
            INSERT INTO solicitudes (
                id, folio, nombre_vecino, rut, direccion, telefono,
                latitud, longitud, observaciones, foto_url,
                estado, nivel_alerta, fecha_solicitud
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'pendiente','normal',NOW())
        """, [
            solicitud_id, folio, data.nombre_vecino, data.rut,
            data.direccion, data.telefono, data.latitud, data.longitud,
            data.observaciones, data.foto_url
        ])

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
            "alerta_duplicado": f"⚠️ Este vecino ya recibió batea anteriormente el {historial[0]['fecha_asignacion']} en {historial[0]['direccion']}" if tuvo_batea else None
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

        # Actualizar niveles de alerta automáticamente
        cur.execute("""
            UPDATE solicitudes SET nivel_alerta = CASE
                WHEN EXTRACT(DAY FROM (NOW() - fecha_solicitud)) >= 20 THEN 'critica'
                WHEN EXTRACT(DAY FROM (NOW() - fecha_solicitud)) >= 11 THEN 'advertencia'
                ELSE 'normal'
            END
            WHERE estado = 'pendiente'
        """)
        conn.commit()

        if estado:
            cur.execute("SELECT * FROM solicitudes WHERE estado = %s ORDER BY fecha_solicitud ASC", [estado])
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
            historial = obtener_historial_vecino(get_db(), r["rut"])
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
                "nivel_alerta": r["nivel_alerta"],
                "fecha_solicitud": r["fecha_solicitud"].strftime("%d/%m/%Y %H:%M"),
                "dias_pendiente": calcular_dias(r["fecha_solicitud"]),
                "numero_batea": r["numero_batea"] or "",
                "tuvo_batea_antes": len(historial) > 0,
                "historial_previo": historial
            })

        return {"solicitudes": resultado, "total": len(resultado)}

    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))

# ── VERIFICAR VECINO POR RUT ──────────────────────────────────────────────────

@app.get("/api/vecinos/{rut}/historial")
def historial_vecino(rut: str):
    """Verifica si un vecino ya tuvo batea asignada anteriormente"""
    conn = get_db()
    try:
        historial = obtener_historial_vecino(conn, rut)

        # También verificar solicitudes anteriores
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT folio, estado, fecha_solicitud, numero_batea, direccion
            FROM solicitudes
            WHERE rut = %s
            ORDER BY fecha_solicitud DESC
        """, [rut])
        solicitudes_previas = cur.fetchall()
        cur.close()
        conn.close()

        return {
            "rut": rut,
            "tuvo_batea_antes": len(historial) > 0,
            "total_solicitudes_historicas": len(solicitudes_previas),
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
        kpis = cur.fetchone()
        cur.close()
        conn.close()
        return dict(kpis)
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=500, detail=str(e))
