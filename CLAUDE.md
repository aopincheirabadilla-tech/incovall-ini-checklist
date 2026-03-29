# CLAUDE.md — INCOVALL: Sistema de Inspección Preventiva INI

## Descripción del Proyecto

Sistema web de gestión de inspecciones preventivas para instalaciones mineras, implementando el protocolo **INI (Inspección Preventiva INI)** — formulario **INCO-INI-VH-001**. Desarrollado para INCOVALL y operado en faenas de CMP.

**Faenas operacionales:**
- PLANTA MAGNETITA
- CNN (Cerro Negro Norte)
- PTT (Puerto Punta Totoralillo)

---

## Stack Tecnológico

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3 + Flask 2.3+ |
| Autenticación | Flask-Login 0.6+ |
| Base de datos | SQLite 3 (`inspecciones.db`) |
| Frontend | HTML5 + Jinja2 + Bootstrap 5.3.3 + Bootstrap Icons 1.11.3 |
| PDF | ReportLab 4.0+ |
| Excel | openpyxl 3.1+ |
| Imágenes | Pillow 9.0+ |

---

## Cómo Ejecutar

```bash
# Windows (recomendado)
run.bat

# Manual
pip install -r requirements.txt
python app.py
```

- URL: `http://localhost:5000`
- Credenciales por defecto: `admin` / `incovall2026`
- Puerto: 5000 (fijo en `app.py`)

---

## Estructura del Proyecto

```
app.py                  # Aplicación principal (~1627 líneas)
inspecciones.db         # Base de datos SQLite
requirements.txt        # Dependencias Python
run.bat                 # Lanzador Windows
static/
  style.css             # Estilos personalizados
  logo_incovall.png
  logo_cmp.png
  fotos/                # Fotos subidas (INI-YYYY-NNNN_N.jpg)
templates/
  base.html             # Layout base con navbar
  login.html
  index.html            # Formulario nueva inspección
  dashboard.html        # Panel de KPIs y gráficos
  historial.html        # Lista de inspecciones
  detalle.html          # Detalle de inspección
  acciones.html         # Lista de acciones correctivas
  accion_detalle.html   # Detalle/edición de acción
  requerimientos.html   # Requerimientos de materiales
  admin_usuarios.html   # Gestión de usuarios (admin)
  admin_usuario_form.html
  perfil.html           # Cambio de contraseña propio
  exito.html
```

---

## Módulos Principales

### 1. Autenticación y Roles
Cuatro roles con permisos distintos:
- `admin` — Acceso total, gestión de usuarios
- `supervisor` — Ve todas las inspecciones de su faena, gestiona acciones correctivas
- `inspector` — Crea inspecciones, ve sus propios registros
- `lectura` — Solo lectura (dashboard e historial)

Decoradores disponibles: `@admin_required`, `@escritura_required`

### 2. Módulo de Inspecciones (`/` → `/guardar`)
- Formulario con 4 categorías y 15+ ítems del checklist:
  - Sistema Sanitario (7 ítems): WC, Lavamanos, Duchas, Agua Fría/Caliente, Termo, Filtraciones
  - Sistema Eléctrico (3 ítems): Iluminación, Enchufes, Interruptores
  - Infraestructura General (3 ítems): Muros, Pisos, Cielos
  - Sistema de Alcantarillado (2 ítems): Cámaras, Tuberías
- Respuestas: SI / NO / N/A
- Fotos por ítem (máx. 5 MB, redimensionadas a 1400×1050, guardadas como JPG al 82%)
- Correlativo auto-generado: `INI-YYYY-NNNN`
- Los ítems con respuesta "NO" generan acciones correctivas automáticamente

### 3. Dashboard (`/dashboard`)
- KPIs: total inspecciones, ítems "NO", recintos distintos, inspectores activos, acciones pendientes
- Filtros por faena y rango de fechas (supervisores/admins)
- Gráfico de torta por sección

### 4. Acciones Correctivas (`/acciones`)
- Generadas automáticamente desde respuestas "NO"
- Estados: Pendiente / En proceso / Completada
- Prioridades: Alta / Media / Baja
- Asignación a responsable (usuario del sistema)
- Seguimiento con trazabilidad (audit trail de comentarios y cambios de estado)

### 5. Requerimientos de Materiales (`/requerimientos`)
- Seguimiento de materiales/equipos necesarios
- Estados: Pendiente / Gestionado
- Exportación a Excel (`/requerimientos/exportar`)

### 6. Gestión de Usuarios (`/admin/usuarios`)
- Solo para `admin`
- Alta/edición de usuarios, asignación de rol y faena
- Reset de contraseña al valor por defecto `incovall2026`
- Activación/desactivación de cuentas

### 7. Exportación PDF (`/pdf/<id>`)
- Genera PDF con logos INCOVALL + CMP, tablas, fotos y zona de firma
- Nombre de archivo: `INCO-INI-VH-001_{correlativo}.pdf`

---

## Esquema de Base de Datos

| Tabla | Descripción |
|-------|-------------|
| `usuarios` | id, username, nombre_completo, email, password_hash, rol, faena, activo |
| `inspecciones` | id, correlativo, valle, faena, fecha, nombre_recinto, nombre_inspector, cliente, usuario_id |
| `items_checklist` | id, inspeccion_id, seccion, item, valor (SI/NO/N/A), comentario |
| `fotos_items` | id, inspeccion_id, item_idx, filename |
| `acciones_correctivas` | id, inspeccion_id, item_idx, recinto, faena, item, responsable_id, prioridad, estado, fecha_cierre |
| `seguimiento_acciones` | id, accion_id, usuario_id, observacion, estado_nuevo (audit trail) |
| `requerimientos` | id, item_nombre, cantidad, faena, recinto, estado |

---

## Convenciones Importantes

- **Normalización de faenas:** Todas las variantes del nombre de faena se normalizan a los 3 valores oficiales (`_FAENA_VARIANTES` en `app.py`). Siempre usar esta lógica al agregar nuevas faenas.
- **Normalización de recintos:** Se guardan en Title Case.
- **Fotos:** Nombradas `{correlativo}_{item_idx}.jpg` dentro de `static/fotos/`.
- **Prevención SQL injection:** Usar `_build_where()` para construcción dinámica de queries.
- **Tamaño máximo de request:** 80 MB (para subidas multi-foto).

---

## Notas de Seguridad (Antes de Producción)

- `app.secret_key = 'incovall-ini-2024-auth'` está hardcodeado — mover a variable de entorno.
- Cambiar la contraseña por defecto `incovall2026` en producción.
- Actualmente corre en Flask dev server (`debug=True`) — usar Gunicorn/Waitress en producción.
