# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect, url_for, send_file
import sqlite3
import os
from datetime import datetime
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.graphics.shapes import Drawing, Rect, String as RLString

app = Flask(__name__)
app.secret_key = 'incovall-ini-2024'

# Jinja2 filter: ícono Bootstrap por sección
_ICONOS = {
    'SISTEMA SANITARIO': 'droplet-half',
    'SISTEMA ELÉCTRICO': 'lightning-charge',
    'INFRAESTRUCTURA GENERAL': 'building',
    'SISTEMA DE ALCANTARILLADO': 'pipe',
}

@app.template_filter('seccion_icon')
def seccion_icon(value):
    """Devuelve el ícono Bootstrap Icons según índice de sección."""
    iconos = ['droplet-half', 'lightning-charge', 'building', 'pipe']
    try:
        return iconos[int(value) - 1]
    except Exception:
        return 'check-circle'

BASE_DIR   = os.path.dirname(__file__)
DATABASE   = os.path.join(BASE_DIR, 'inspecciones.db')
STATIC_DIR = os.path.join(BASE_DIR, 'static')

SECCIONES = {
    'SISTEMA SANITARIO': ['WC', 'Lavamanos', 'Duchas', 'Agua Fría', 'Agua Caliente', 'Termo', 'Filtraciones'],
    'SISTEMA ELÉCTRICO': ['Equipos de Iluminación', 'Enchufes', 'Interruptores'],
    'INFRAESTRUCTURA GENERAL': ['Muros', 'Pisos', 'Cielos'],
    'SISTEMA DE ALCANTARILLADO': ['Cámaras', 'Tuberías'],
}

FLAT_ITEMS = [(s, item) for s, items in SECCIONES.items() for item in items]


# ─── Database ────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS inspecciones (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            correlativo      TEXT UNIQUE,
            valle            TEXT,
            faena            TEXT,
            fecha            TEXT,
            nombre_recinto   TEXT,
            nombre_inspector TEXT,
            cliente          TEXT,
            observaciones    TEXT,
            supervisor       TEXT,
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS items_checklist (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            inspeccion_id INTEGER,
            seccion       TEXT,
            item          TEXT,
            valor         TEXT,
            comentario    TEXT,
            FOREIGN KEY (inspeccion_id) REFERENCES inspecciones(id)
        )
    ''')
    conn.commit()
    conn.close()


def generate_correlativo():
    conn = get_db()
    year = datetime.now().year
    row = conn.execute(
        "SELECT COUNT(*) as n FROM inspecciones WHERE correlativo LIKE ?",
        (f'INI-{year}-%',)
    ).fetchone()
    conn.close()
    return f'INI-{year}-{row["n"] + 1:04d}'


# ─── Routes ──────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    correlativo = generate_correlativo()
    today = datetime.now().strftime('%Y-%m-%d')
    return render_template('index.html',
                           secciones=SECCIONES,
                           flat_items=FLAT_ITEMS,
                           correlativo=correlativo,
                           today=today)


@app.route('/guardar', methods=['POST'])
def guardar():
    data = request.form
    conn = get_db()
    try:
        conn.execute('''
            INSERT INTO inspecciones
                (correlativo, valle, faena, fecha, nombre_recinto,
                 nombre_inspector, cliente, observaciones, supervisor)
            VALUES (?,?,?,?,?,?,?,?,?)
        ''', (
            data.get('correlativo'),
            data.get('valle'),
            data.get('faena'),
            data.get('fecha'),
            data.get('nombre_recinto'),
            data.get('nombre_inspector'),
            data.get('cliente'),
            data.get('observaciones'),
            data.get('supervisor'),
        ))
        inspeccion_id = conn.execute(
            "SELECT id FROM inspecciones WHERE correlativo=?",
            (data.get('correlativo'),)
        ).fetchone()['id']

        for i, (seccion, item) in enumerate(FLAT_ITEMS):
            valor = data.get(f'valor_{i}', 'N/A')
            comentario = data.get(f'comentario_{i}', '')
            conn.execute('''
                INSERT INTO items_checklist (inspeccion_id, seccion, item, valor, comentario)
                VALUES (?,?,?,?,?)
            ''', (inspeccion_id, seccion, item, valor, comentario))

        conn.commit()
    finally:
        conn.close()

    return redirect(url_for('exito', inspeccion_id=inspeccion_id))


@app.route('/exito/<int:inspeccion_id>')
def exito(inspeccion_id):
    conn = get_db()
    insp = conn.execute(
        "SELECT correlativo, nombre_recinto FROM inspecciones WHERE id=?",
        (inspeccion_id,)
    ).fetchone()
    conn.close()
    return render_template('exito.html', inspeccion_id=inspeccion_id, insp=insp)


@app.route('/historial')
def historial():
    recinto = request.args.get('recinto', '').strip()
    fecha_desde = request.args.get('fecha_desde', '').strip()
    fecha_hasta = request.args.get('fecha_hasta', '').strip()

    query = "SELECT * FROM inspecciones WHERE 1=1"
    params = []
    if recinto:
        query += " AND nombre_recinto LIKE ?"
        params.append(f'%{recinto}%')
    if fecha_desde:
        query += " AND fecha >= ?"
        params.append(fecha_desde)
    if fecha_hasta:
        query += " AND fecha <= ?"
        params.append(fecha_hasta)
    query += " ORDER BY created_at DESC"

    conn = get_db()
    inspecciones = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('historial.html',
                           inspecciones=inspecciones,
                           recinto=recinto,
                           fecha_desde=fecha_desde,
                           fecha_hasta=fecha_hasta)


@app.route('/pdf/<int:inspeccion_id>')
def descargar_pdf(inspeccion_id):
    conn = get_db()
    insp = conn.execute(
        "SELECT * FROM inspecciones WHERE id=?", (inspeccion_id,)
    ).fetchone()
    if insp is None:
        conn.close()
        return "Inspección no encontrada", 404
    items = conn.execute(
        "SELECT * FROM items_checklist WHERE inspeccion_id=? ORDER BY id",
        (inspeccion_id,)
    ).fetchall()
    conn.close()

    buf = generate_pdf(insp, items)
    filename = f'INCO-INI-VH-001_{insp["correlativo"]}.pdf'
    return send_file(buf, as_attachment=True,
                     download_name=filename, mimetype='application/pdf')


# ─── PDF Generation ──────────────────────────────────────────────────────────

C_AZUL       = colors.HexColor('#0d47a1')
C_AZUL_SEC   = colors.HexColor('#1565C0')
C_AZUL_LIGHT = colors.HexColor('#E3F2FD')
C_VERDE      = colors.HexColor('#388E3C')
C_ROJO       = colors.HexColor('#C62828')
C_GRIS       = colors.HexColor('#757575')
C_VERDE_BG   = colors.HexColor('#C8E6C9')
C_ROJO_BG    = colors.HexColor('#FFCDD2')
C_GRIS_BG    = colors.HexColor('#E0E0E0')
C_LINEA      = colors.HexColor('#BDBDBD')
C_FILA_ALT   = colors.HexColor('#F5F5F5')


def pdf_logo(filename, fallback_text, max_w=4.0, max_h=2.2):
    """Devuelve un Image de reportlab si el archivo existe y es válido,
    o un Drawing de texto como fallback.
    La imagen se escala proporcionalmente para caber en max_w × max_h (cm).
    """
    path = os.path.join(STATIC_DIR, filename)
    if os.path.exists(path):
        try:
            # Validar que Pillow pueda decodificar la imagen completamente
            from PIL import Image as PILImage
            with PILImage.open(path) as pil_img:
                pil_img.load()          # fuerza decodificación completa
                nat_w, nat_h = pil_img.size

            max_w_pt = max_w * cm
            max_h_pt = max_h * cm
            ratio    = min(max_w_pt / nat_w, max_h_pt / nat_h)
            img = Image(path, width=nat_w * ratio, height=nat_h * ratio)
            img.hAlign = 'CENTER'
            return img
        except Exception:
            pass  # imagen inválida o Pillow no disponible → fallback

    # Fallback: rectángulo azul con texto
    w, h = max_w * cm, max_h * cm
    d = Drawing(w, h)
    d.add(Rect(0, 0, w, h, fillColor=C_AZUL, strokeColor=None))
    d.add(RLString(8, h * 0.52, fallback_text,
                   fontName='Helvetica-Bold', fontSize=15,
                   fillColor=colors.white))
    return d


def generate_pdf(insp, items):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            rightMargin=1.5 * cm, leftMargin=1.5 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    W = 18 * cm  # usable width

    def style(name, **kw):
        return ParagraphStyle(name, parent=styles['Normal'], **kw)

    s_white_bold   = style('wb',  fontSize=9,  fontName='Helvetica-Bold',
                           textColor=colors.white, alignment=TA_CENTER)
    s_label        = style('lbl', fontSize=7.5, textColor=colors.HexColor('#555'),
                           fontName='Helvetica')
    s_value        = style('val', fontSize=9,  fontName='Helvetica-Bold')
    s_sec_header   = style('sh',  fontSize=8.5, fontName='Helvetica-Bold',
                           textColor=colors.white)
    s_item         = style('it',  fontSize=8.5, fontName='Helvetica')
    s_comment      = style('cm',  fontSize=7.5, fontName='Helvetica',
                           textColor=colors.HexColor('#444'))
    s_mark_si      = style('msi', fontSize=13, fontName='Helvetica-Bold',
                           textColor=C_VERDE, alignment=TA_CENTER)
    s_mark_no      = style('mno', fontSize=13, fontName='Helvetica-Bold',
                           textColor=C_ROJO, alignment=TA_CENTER)
    s_mark_na      = style('mna', fontSize=13, fontName='Helvetica-Bold',
                           textColor=C_GRIS, alignment=TA_CENTER)
    s_mark_empty   = style('me',  fontSize=13, alignment=TA_CENTER)
    s_footer       = style('ft',  fontSize=7,  textColor=colors.HexColor('#999'),
                           alignment=TA_CENTER)
    s_obs_label    = style('ol',  fontSize=9,  fontName='Helvetica-Bold',
                           textColor=colors.white)
    s_obs_body     = style('ob',  fontSize=9,  fontName='Helvetica', leading=13)
    s_title        = style('ttl', fontSize=12, fontName='Helvetica-Bold',
                           textColor=colors.white, alignment=TA_CENTER)
    s_subtitle     = style('st',  fontSize=8,  fontName='Helvetica',
                           textColor=colors.HexColor('#BBDEFB'), alignment=TA_CENTER)

    story = []

    # ── Cabecera: Logo INCOVALL | Título central | Logo CMP ─────────────────
    s_title_main = style('tm', fontSize=13, fontName='Helvetica-Bold',
                         textColor=colors.white, alignment=TA_CENTER)
    s_title_sub  = style('ts', fontSize=8.5, fontName='Helvetica',
                         textColor=colors.HexColor('#BBDEFB'), alignment=TA_CENTER)
    s_title_info = style('ti', fontSize=8, fontName='Helvetica',
                         textColor=colors.HexColor('#90CAF9'), alignment=TA_CENTER)

    logo_incovall = pdf_logo('logo_incovall.png', 'INCOVALL', max_w=4.0, max_h=2.2)
    logo_cmp      = pdf_logo('logo_cmp.png',      'CMP',      max_w=4.0, max_h=2.2)

    title_block = [
        Paragraph('Inspección Preventiva INI', s_title_main),
        Spacer(1, 4),
        Paragraph('INCO-INI-VH-001', s_title_sub),
        Spacer(1, 6),
        Paragraph(
            f'Correlativo: <b>{insp["correlativo"]}</b> &nbsp;|&nbsp; '
            f'Fecha: <b>{insp["fecha"] or ""}</b>',
            s_title_info
        ),
    ]

    header_data = [[logo_incovall, title_block, logo_cmp]]
    header_t = Table(header_data, colWidths=[4.0 * cm, 10.0 * cm, 4.0 * cm])
    header_t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), C_AZUL),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN',         (0, 0), (0, 0),   'CENTER'),
        ('ALIGN',         (1, 0), (1, 0),   'CENTER'),
        ('ALIGN',         (2, 0), (2, 0),   'CENTER'),
        ('TOPPADDING',    (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 6),
    ]))
    story.append(header_t)
    story.append(Spacer(1, 0.35 * cm))

    # ── Ficha de datos ───────────────────────────────────────────────────────
    def field(label, value):
        return [Paragraph(label, s_label), Paragraph(str(value or ''), s_value)]

    info_rows = [
        field('VALLE', insp['valle']) + field('FAENA', insp['faena']) + field('CLIENTE', insp['cliente']),
        field('RECINTO', insp['nombre_recinto']) + field('INSPECTOR', insp['nombre_inspector']) + ['', ''],
    ]
    col_w = [2.2 * cm, 3.8 * cm, 2 * cm, 3.8 * cm, 2 * cm, 4.2 * cm]
    info_t = Table(info_rows, colWidths=col_w)
    info_t.setStyle(TableStyle([
        ('BOX',         (0, 0), (-1, -1), 0.5, C_LINEA),
        ('INNERGRID',   (0, 0), (-1, -1), 0.3, C_LINEA),
        ('BACKGROUND',  (0, 0), (-1, 0),  C_AZUL_LIGHT),
        ('BACKGROUND',  (0, 1), (-1, 1),  colors.white),
        ('VALIGN',      (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',  (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('SPAN',        (3, 1), (5, 1)),
    ]))
    story.append(info_t)
    story.append(Spacer(1, 0.35 * cm))

    # ── Checklist ────────────────────────────────────────────────────────────
    # Agrupar items por sección
    items_by_sec = {}
    for row in items:
        items_by_sec.setdefault(row['seccion'], []).append(row)

    COL_ITEM = 5.8 * cm
    COL_CHK  = 1.6 * cm
    COL_CMT  = W - COL_ITEM - 3 * COL_CHK  # resto

    # Encabezado de tabla
    tbl_data = [[
        Paragraph('<b>ÍTEM</b>', s_white_bold),
        Paragraph('<b>SI</b>', s_white_bold),
        Paragraph('<b>NO</b>', s_white_bold),
        Paragraph('<b>N/A</b>', s_white_bold),
        Paragraph('<b>COMENTARIOS</b>', s_white_bold),
    ]]
    tbl_styles = [
        ('BACKGROUND',    (0, 0), (-1, 0),  C_AZUL),
        ('TEXTCOLOR',     (0, 0), (-1, 0),  colors.white),
        ('FONTSIZE',      (0, 0), (-1, -1), 8.5),
        ('BOX',           (0, 0), (-1, -1), 0.5, C_LINEA),
        ('INNERGRID',     (0, 0), (-1, -1), 0.3, C_LINEA),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING',   (0, 0), (-1, -1), 5),
    ]

    row_idx = 1
    for seccion_name in SECCIONES.keys():
        # Fila de sección
        tbl_data.append([
            Paragraph(seccion_name, s_sec_header), '', '', '', ''
        ])
        tbl_styles += [
            ('BACKGROUND', (0, row_idx), (-1, row_idx), C_AZUL_SEC),
            ('SPAN',       (0, row_idx), (-1, row_idx)),
        ]
        row_idx += 1

        for it in items_by_sec.get(seccion_name, []):
            valor = it['valor'] or ''
            si  = Paragraph('✓', s_mark_si)  if valor == 'SI'  else Paragraph('', s_mark_empty)
            no  = Paragraph('✓', s_mark_no)  if valor == 'NO'  else Paragraph('', s_mark_empty)
            na  = Paragraph('✓', s_mark_na)  if valor == 'N/A' else Paragraph('', s_mark_empty)

            tbl_data.append([
                Paragraph(it['item'], s_item),
                si, no, na,
                Paragraph(it['comentario'] or '', s_comment),
            ])

            if row_idx % 2 == 0:
                tbl_styles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), C_FILA_ALT))

            if valor == 'SI':
                tbl_styles.append(('BACKGROUND', (1, row_idx), (1, row_idx), C_VERDE_BG))
            elif valor == 'NO':
                tbl_styles.append(('BACKGROUND', (2, row_idx), (2, row_idx), C_ROJO_BG))
            elif valor == 'N/A':
                tbl_styles.append(('BACKGROUND', (3, row_idx), (3, row_idx), C_GRIS_BG))

            tbl_styles.append(('ALIGN', (1, row_idx), (3, row_idx), 'CENTER'))
            row_idx += 1

    checklist_t = Table(tbl_data, colWidths=[COL_ITEM, COL_CHK, COL_CHK, COL_CHK, COL_CMT])
    checklist_t.setStyle(TableStyle(tbl_styles))
    story.append(checklist_t)
    story.append(Spacer(1, 0.4 * cm))

    # ── Observaciones ────────────────────────────────────────────────────────
    obs_t = Table([
        [Paragraph('OBSERVACIONES GENERALES:', s_obs_label)],
        [Paragraph(insp['observaciones'] or ' ', s_obs_body)],
    ], colWidths=[W])
    obs_t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0), C_AZUL),
        ('BACKGROUND',    (0, 1), (-1, 1), colors.white),
        ('BOX',           (0, 0), (-1, -1), 0.5, C_LINEA),
        ('LEFTPADDING',   (0, 0), (-1, -1), 7),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 7),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('MINROWHEIGHT',  (0, 1), (-1, 1), 1.8 * cm),
        ('VALIGN',        (0, 1), (-1, 1), 'TOP'),
    ]))
    story.append(obs_t)
    story.append(Spacer(1, 0.4 * cm))

    # ── Supervisor / Firma ───────────────────────────────────────────────────
    s_sup_lbl = style('sl', fontSize=9, fontName='Helvetica-Bold',
                      textColor=colors.HexColor('#333'))
    s_sup_val = style('sv', fontSize=10, fontName='Helvetica-Bold',
                      textColor=C_AZUL)
    s_linea   = style('ln', fontSize=8, textColor=colors.HexColor('#888'),
                      alignment=TA_CENTER)

    firma_t = Table([
        [Paragraph('SUPERVISOR RESPONSABLE:', s_sup_lbl),
         Paragraph(insp['supervisor'] or '', s_sup_val)],
        ['',
         Paragraph('___________________________________', s_linea)],
        ['',
         Paragraph('Firma', s_linea)],
    ], colWidths=[6 * cm, 12 * cm])
    firma_t.setStyle(TableStyle([
        ('BOX',           (0, 0), (-1, -1), 0.5, C_LINEA),
        ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 7),
        ('ALIGN',         (1, 1), (1, 2),   'CENTER'),
    ]))
    story.append(firma_t)
    story.append(Spacer(1, 0.3 * cm))

    # ── Pie de página ────────────────────────────────────────────────────────
    story.append(Paragraph(
        f'Generado el {datetime.now().strftime("%d/%m/%Y %H:%M")} &nbsp;|&nbsp; '
        f'INCOVALL – Inspección Preventiva INI &nbsp;|&nbsp; INCO-INI-VH-001',
        s_footer
    ))

    doc.build(story)
    buf.seek(0)
    return buf


# ─── Main ────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    import webbrowser, threading
    def open_browser():
        import time; time.sleep(1.2)
        webbrowser.open('http://localhost:5000')
    threading.Thread(target=open_browser, daemon=True).start()
    print("\n  INCOVALL - Inspección Preventiva INI")
    print("  Servidor en http://localhost:5000")
    print("  Presione Ctrl+C para detener.\n")
    app.run(debug=False, host='0.0.0.0', port=5000)
