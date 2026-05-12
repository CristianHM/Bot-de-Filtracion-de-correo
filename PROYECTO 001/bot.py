import imaplib
import email
import time
import config
import requests

INTERVALO_SEGUNDOS = 300  # 5 minutos
MAX_ERRORES_CONSECUTIVOS = 5

def es_urgente(remitente: str, asunto: str) -> bool:
    for r in config.REMITENTES_URGENTES:
        if r.lower() in remitente:
            return True
    for p in config.PALABRAS_URGENTES:
        if p.lower() in asunto:
            return True
    return False

def enviar_alerta_telegram(remitente: str, asunto: str, urgente: bool = False) -> None:
    """Envía una notificación push al celular vía Telegram."""

    # Limpieza PRIMERO — antes de construir el texto HTML
    remitente = remitente.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    asunto    = asunto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    if urgente:
        encabezado = "🔴 <b>ACCIÓN REQUERIDA</b>"
    else:
        encabezado = "🟡 <b>CORREO IMPORTANTE</b>"
    texto =(
        f"{encabezado}\n\n"
        f"📧 <b>De:</b> {remitente}\n"
        f"📝 <b>Asunto:</b> {asunto}"
    
    )
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": texto,
        "parse_mode": "HTML"
    }
    try:
        respuesta = requests.post(url, json=payload, timeout=10)
        respuesta.raise_for_status()
        print("  📲 Alerta enviada a Telegram.")
    except requests.exceptions.Timeout:
        print("  ⚠️ Telegram no respondió (timeout).")
    except requests.exceptions.HTTPError as e:
        print(f"  ⚠️ Error HTTP de Telegram: {e}")
    except Exception as e:
        print(f"  ⚠️ No se pudo enviar la alerta: {e}")

def detectar_papelera(servidor) -> str:
    for nombre in ('[Gmail]/Papelera', '[Gmail]/Trash'):
        res, _ = servidor.select(nombre)
        if res == 'OK':
            servidor.select("INBOX")
            return nombre
    raise RuntimeError("No se encontró carpeta de papelera.")

def conectar() -> imaplib.IMAP4_SSL:
    """Crea una conexión fresca y selecciona INBOX."""
    servidor = imaplib.IMAP4_SSL("imap.gmail.com")
    servidor.login(config.EMAIL_USUARIO, config.CLAVE_APP)
    return servidor

def es_permitido(remitente: str, asunto: str) -> bool:
    for p in config.REMITENTES_PERMITIDOS:
        if p.lower() in remitente:
            return True
    for pal in config.PALABRAS_PERMITIDAS:
        if pal.lower() in asunto:
            return True
    return False

def procesar_nuevos(servidor, papelera: str) -> tuple[int, int]:
    """
    Revisa los correos UNSEEN y filtra.
    Retorna (mantenidos, eliminados).
    """
    servidor.select("INBOX")
    status, datos = servidor.uid('search', None, 'UNSEEN')
    if status != 'OK':
        print("  ⚠️  No se pudo buscar correos nuevos.")
        return 0, 0

    uids = datos[0].split()
    if not uids:
        return 0, 0

    print(f"  🔍 {len(uids)} mensaje(s) nuevo(s) detectado(s).")
    mantenidos = eliminados = 0

    for uid in uids:
        res, msg_data = servidor.uid('fetch', uid, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])')

        if res != 'OK' or not isinstance(msg_data[0], tuple):
            print(f"  ⚠️  No se pudo leer UID {uid.decode()}, omitiendo.")
            continue

        msg = email.message_from_bytes(msg_data[0][1])
        remitente = str(msg.get("From", "")).lower()
        asunto    = str(msg.get("Subject", "")).lower()
        preview   = asunto[:40] or "(sin asunto)"

        if es_urgente(remitente, asunto):
            print(f"  🔴 Urgente  → '{preview}'")
            enviar_alerta_telegram(remitente, asunto, urgente=True)
            mantenidos += 1
        elif es_permitido(remitente, asunto):
            print(f"  ✅ Útil     → '{preview}'")
            mantenidos += 1  # Se queda, sin alerta
        else:
            res_copy, _  = servidor.uid('copy',  uid, papelera)
            res_store, _ = servidor.uid('store', uid, '+FLAGS', '\\Deleted')

            if res_copy == 'OK' and res_store == 'OK':
                print(f"  🗑️  Borrado → '{preview}'")
                eliminados += 1
            else:
                print(f"  ⚠️  Fallo al borrar UID {uid.decode()}: copy={res_copy}, store={res_store}")

    if eliminados:
        servidor.expunge()

    return mantenidos, eliminados

def vigilancia_en_tiempo_real():
    print(f"🛡️  Escudo activado para: {config.EMAIL_USUARIO}")
    print(f"    Revisión cada {INTERVALO_SEGUNDOS // 60} min | Ctrl+C para detener\n")

    errores_consecutivos = 0
    servidor = None
    papelera = None

    while True:
        try:
            # Reconectar solo si no hay sesión activa
            if servidor is None:
                print("🔌 Conectando a Gmail...")
                servidor = conectar()
                papelera = detectar_papelera(servidor)
                print(f"   Papelera detectada: {papelera}\n")

            mantenidos, eliminados = procesar_nuevos(servidor, papelera)

            if mantenidos or eliminados:
                print(f"   Resumen: {mantenidos} conservados, {eliminados} eliminados.\n")

            errores_consecutivos = 0  # Reset al tener éxito

        except KeyboardInterrupt:
            print("\n🛑 Escudo desactivado por el usuario.")
            break

        except imaplib.IMAP4.abort:
            # Conexión caída por timeout del servidor — reconectar
            print("⚡ Conexión caída. Reconectando en el próximo ciclo...")
            servidor = None
            papelera = None
            errores_consecutivos += 1

        except Exception as e:
            errores_consecutivos += 1
            print(f"❌ Error ({errores_consecutivos}/{MAX_ERRORES_CONSECUTIVOS}): {e}")
            servidor = None
            papelera = None

            if errores_consecutivos >= MAX_ERRORES_CONSECUTIVOS:
                print("🚨 Demasiados errores consecutivos. Deteniendo el escudo.")
                break

            pausa = min(60 * errores_consecutivos, 300)  # Back-off: 1min, 2min... hasta 5min
            print(f"   Reintentando en {pausa}s...")
            time.sleep(pausa)
            continue

        finally:
            pass  # No cerrar sesión aquí — reusar la conexión

        print(f"💤 Próxima revisión en {INTERVALO_SEGUNDOS // 60} min...")
        time.sleep(INTERVALO_SEGUNDOS)

    # Cerrar sesión limpiamente al salir
    if servidor:
        try:
            servidor.logout()
            print("🔌 Sesión cerrada.")
        except Exception:
            pass

if __name__ == "__main__":
    vigilancia_en_tiempo_real()