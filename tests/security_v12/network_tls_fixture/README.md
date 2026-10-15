# S5 TLS fixture

El certificado autofirmado y la clave privada de este directorio son material
**público y exclusivo de test**, para `server.test`. Nunca deben usarse en
producción. Fueron generados offline con el OpenSSL ya incluido en Git del host;
no son una dependencia de Nova ni del runner, que usa sólo la stdlib Python.

Los tests cargan el certificado en un `SSLContext` privado y no modifican el
almacén de confianza del sistema. `CERT_REQUIRED` y `check_hostname` permanecen
activos: se prueba éxito con esta CA de fixture y rechazo con CA no confiable
y con hostname distinto. No existe un modo productivo de TLS sin validación.
