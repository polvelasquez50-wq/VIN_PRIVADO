from fastapi import FastAPI, Form, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import json
import os
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

app = FastAPI()

with open("paises.json", encoding="utf-8") as f:
    PAISES = json.load(f)

with open("fabricantes.json", encoding="utf-8") as f:
    FABRICANTES = json.load(f)

with open("anios.json", encoding="utf-8") as f:
    ANIOS = json.load(f)

# Carpeta de archivos estáticos (logo)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Contraseña de acceso
PASSWORD = "1234vin"

# Estilos base
BASE_STYLE = """
<style>
body {
    font-family: Arial, sans-serif;
    background: #0f172a;
    color: #e5e7eb;
    margin: 0;
    padding: 0;
}
.container {
    max-width: 420px;
    margin: 60px auto;
    background: #020617;
    padding: 30px;
    border-radius: 12px;
    box-shadow: 0 0 20px rgba(0,0,0,0.6);
    text-align: center;
}
h1 {
    font-size: 22px;
    margin-bottom: 10px;
}
input {
    width: 100%;
    padding: 12px;
    margin-top: 12px;
    border-radius: 6px;
    border: none;
    font-size: 16px;
}
button {
    width: 100%;
    padding: 12px;
    margin-top: 18px;
    background: #2563eb;
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 16px;
    cursor: pointer;
}
button:hover {
    background: #1d4ed8;
}
.logo {
    max-width: 120px;
    margin-bottom: 15px;
}
.footer {
    margin-top: 20px;
    font-size: 12px;
    color: #94a3b8;
}
.alert {
    margin-top: 15px;
    color: #f87171;
}
.success {
    color: #4ade80;
}
a {
    color: #93c5fd;
    text-decoration: none;
}

.box {
    background: #0b1120;
    padding: 25px;
    margin-top: 25px;
    border-radius: 14px;
    box-shadow: 0 10px 25px rgba(0,0,0,0.5);
    border: 2px solid #1e293b;
    text-align: left;
}

.box h2 {
    margin-top: 0;
    font-size: 18px;
    border-bottom: 1px solid #334155;
    padding-bottom: 8px;
    margin-bottom: 15px;
}
</style>
"""

# Pantalla de login
@app.get("/", response_class=HTMLResponse)
def login():
    return f"""
    {BASE_STYLE}
    <div class="container">
        <img src="/static/logo.png" class="logo">
        <h1>VELPOL – VERIFICADOR DE VIN</h1>
        <form action="/login" method="post">
            <input type="password" name="password" placeholder="Contraseña de acceso">
            <button type="submit">Ingresar</button>
        </form>
        <div class="footer">Uso privado • VELPOL</div>
    </div>
    """

# Procesar login
@app.post("/login")
def login_post(password: str = Form(...)):
    if password == PASSWORD:
        return RedirectResponse("/vin", status_code=302)

    return HTMLResponse(f"""
    {BASE_STYLE}
    <div class="container">
        <h1>Acceso denegado</h1>
        <div class="alert">Contraseña incorrecta</div>
        <a href="/">Volver</a>
    </div>
    """)

# Pantalla de verificación VIN
@app.get("/vin", response_class=HTMLResponse)
def vin_page():
    return f"""
    {BASE_STYLE}
    <div class="container">
        <h1>VELPOL – VERIFICADOR DE VIN</h1>
	<form action="/verificar" method="post" enctype="multipart/form-data">

	    <input name="vin"
	           placeholder="Ingrese VIN (17 caracteres)"
	           style="text-transform:uppercase"
        	   oninput="this.value = this.value.toUpperCase()"
	           maxlength="17"
        	   required>

  	  <input type="file"
          	  name="imagen"
		  accept="image/*"
           	  style="margin-top:10px;">

   	 <button type="submit">Verificar VIN</button>
</form>

def procesar_vin(vin: str):
    vin = vin.upper().strip()

    pais = PAISES.get(vin[0], "No registrado en base VELPOL")

    fabricante = (
        FABRICANTES.get(vin[:3])
        or FABRICANTES.get(vin[:2])
        or FABRICANTES.get(vin[:1])
        or "No registrado en base VELPOL"
    )

    anio = ANIOS.get(vin[9], "No determinado")

    return pais, fabricante, anio
def validar_vin_matematico(vin: str):
 	valores = {str(i): i for i in range(10)}

	valores.update({
   	 "A": 1, "B": 2, "C": 3, "D": 4, "E": 5,
   	 "F": 6, "G": 7, "H": 8, "J": 1,
 	 "K": 2, "L": 3, "M": 4, "N": 5,
   	 "P": 7, "R": 9, "S": 2, "T": 3,
  	 "U": 4, "V": 5, "W": 6, "X": 7,
   	 "Y": 8, "Z": 9
})

    pesos = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]

    if any(c in "IOQ" for c in vin):
        return "INVÁLIDO", "Contiene caracteres no permitidos (I, O, Q)"

    total = 0
    for i, c in enumerate(vin):
        if c not in valores:
            return "INVÁLIDO", "Caracter no válido en VIN"
        total += valores[c] * pesos[i]

    residuo = total % 11
    digito_esperado = "X" if residuo == 10 else str(residuo)

    if vin[8] != digito_esperado:
        return "SOSPECHOSO", "El dígito de control no coincide"

    return "VÁLIDO", "Dígito de control correcto (ISO 3779)"

# Guardar en Google Sheets con correlativo automático
def guardar_en_sheets(vin, pais, fabricante, anio, estado):
    try:
        creds_json = os.getenv("GOOGLE_CREDENTIALS")
        if not creds_json:
            return

        creds_dict = json.loads(creds_json)

        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

        credentials = Credentials.from_service_account_info(
            creds_dict,
            scopes=scopes
        )

        client = gspread.authorize(credentials)

        sheet = client.open("VELPOL_REGISTRO_VIN").sheet1

        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        registros = sheet.get_all_values()
        correlativo = len(registros) + 1

        sheet.append_row([
            correlativo,
            ahora,
            vin,
            pais,
            fabricante,
            anio,
            estado
        ])

    except Exception as e:
        print("Error guardando en Google Sheets:", e)

def generar_reporte_pdf(vin, pais, fabricante, anio, estado):

    nombre_archivo = f"reporte_{vin}.pdf"
    ruta = f"/tmp/{nombre_archivo}"

    c = canvas.Canvas(ruta, pagesize=letter)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "VELPOL – REPORTE DE VALIDACIÓN VIN")

    c.setFont("Helvetica", 12)

    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    c.drawString(50, 700, f"Fecha: {fecha}")
    c.drawString(50, 680, f"VIN: {vin}")
    c.drawString(50, 660, f"País: {pais}")
    c.drawString(50, 640, f"Fabricante: {fabricante}")
    c.drawString(50, 620, f"Año: {anio}")
    c.drawString(50, 600, f"Estado: {estado}")

    c.drawString(50, 550, "Reporte generado por el sistema VELPOL")

    c.save()

    return ruta, nombre_archivo

# Verificar VIN (VELPOL)
@app.post("/verificar", response_class=HTMLResponse)
def verificar(
    vin: str = Form(...),
    imagen: UploadFile = File(None)
):

    vin = vin.upper().strip()

   if len(vin) != 17:
    return f"""
    {BASE_STYLE}
    <div class="container">
        <h1>Resultado</h1>
        <p><b>Error:</b> VIN inválido (debe tener 17 caracteres)</p>
        <a href="/vin">Intentar otro</a>
    </div>
    """
    pais, fabricante, anio = procesar_vin(vin)
    estado, detalle = validar_vin_matematico(vin)

    guardar_en_sheets(vin, pais, fabricante, anio, estado)

    # -------------------------
    # PROCESAMIENTO DE IMAGEN
    # -------------------------

    imagen_html = ""

    if imagen and imagen.filename != "":
        contenido = imagen.file.read()

        import base64
        imagen_base64 = base64.b64encode(contenido).decode("utf-8")

        imagen_html = f"""
        <div class="box">
            <h2>Imagen del vehículo</h2>

            <div style="
                width:100%;
                height:220px;
                border:2px dashed #334155;
                border-radius:12px;
                overflow:hidden;
            ">
                <img src="data:image/jpeg;base64,{imagen_base64}"
                     style="width:100%; height:100%; object-fit:cover;">
            </div>

        </div>
        """

    else:

        imagen_html = """
        <div class="box">
            <h2>Imagen del vehículo</h2>

            <div style="
                width:100%;
                height:220px;
                border:2px dashed #334155;
                border-radius:12px;
                display:flex;
                align-items:center;
                justify-content:center;
            ">

                <div style="
                    transform:rotate(-20deg);
                    font-size:28px;
                    color:#475569;
                    font-weight:bold;
                ">
                    NO DATA
                </div>

            </div>

        </div>
        """

    # -------------------------
    # RETORNO FINAL
    # -------------------------

    return f"""
    {BASE_STYLE}
    <div class="container">
        <h1>Resultado VIN</h1>

        <div class="box">
            <h2>VELPOL – Verificador de VIN</h2>
            <p><b>VIN:</b> {vin}</p>
            <p><b>País de origen:</b> {pais}</p>
            <p><b>Fabricante:</b> {fabricante}</p>
            <p><b>Año de fabricación:</b> {anio}</p>
        </div>

        <div class="box">
            <h2>VELPOL – Validación de VIN</h2>
            <p><b>Estado:</b> {estado}</p>
            <p>{detalle}</p>
        </div>

        {imagen_html}

        <br><br>

        <a href="/reporte/{vin}">
            <button>📄 Generar Reporte Profesional</button>
        </a>

        <br><br>

        <a href="/vin">Verificar otro VIN</a>

    </div>
    """
from fastapi.responses import FileResponse

@app.get("/reporte/{vin}")
def descargar_reporte(vin: str):

    pais, fabricante, anio = procesar_vin(vin)
    estado, detalle = validar_vin_matematico(vin)

    ruta, nombre = generar_reporte_pdf(vin, pais, fabricante, anio, estado)

    return FileResponse(
        ruta,
        media_type="application/pdf",
        filename=nombre
    )



