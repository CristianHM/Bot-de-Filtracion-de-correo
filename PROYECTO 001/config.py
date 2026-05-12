

import os

# Credenciales — se leen desde Railway, nunca en el código
EMAIL_USUARIO    = os.environ.get("cristianmozo51@gmail.com")
CLAVE_APP        = os.environ.get("klmn jorn nztk qpsr")
# Datos de Telegram
TELEGRAM_TOKEN   = os.environ.get("8437520874:AAGPgRLpT6XPvLXfs4D53a6FWuqNwIwMTGc")
TELEGRAM_CHAT_ID = os.environ.get("8518571657")

REMITENTES_PERMITIDOS = [
    "gestiondepagos@isil.pe", 
    "info@turecibo.com",
    "bcp.com.pe",      # Bancos
    "bbva.pe",
    "gob.pe",          # Trámites del estado
    "google.com"
]

PALABRAS_PERMITIDAS = ["importante", "pago", "confirmacion", "seguridad", "contraseña", "CENCOSUD",'verificacion', 'cuenta', 'ISIL','firmar',
                       'compra','estado de cuenta', 'recibo','tarea','pedido','verificacion','clave',',acceso']

# urgentes 
REMITENTES_URGENTES = [
    "gestiondepagos@isil.pe",
]

PALABRAS_URGENTES = [
    "firmar", "firma", "vencido", "urgente", 'PA1','PA2','PA3','PA4'
]