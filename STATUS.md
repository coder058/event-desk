# STATUS — 2026-10-08 11:13:45 UTC

TEST oficial: sí, uno histórico (test_d096b526791e46bdbf0012d63de8dbfd; TEST neutral/API 201; last_test_prediction_at=2026-10-07T22:03:48.125853Z). TEST nuevo por 443: pendiente del titular. | Eventos oficiales: 0, excluye TEST | Envíos oficiales: 0 no-TEST.

## Hecho

- Jordi autorizó la publicación y el despliegue con «ok hazlo». Se publicaron los 14 commits revisados hasta 8553954; worktree e índice estaban limpios, sin incorporar cambios ajenos.
- Gate local previo a publicación: 186 tests pasaron, uno omitido por symlinks Windows, 104.10 s; ruff global, mypy estricto de 23 módulos, secret scan contra claves privadas del titular y diff --check pasaron. Tests, push y deploy fueron comandos separados.
- CI 37768023493 del SHA exacto 855395446e41813eb3584dab516f20ceced7ed10: success. Linux: 187 tests pasaron en 12.68 s; Docker smoke, concurrencia y TLS mux también pasaron.
- Despliegue autorizado mediante ops/deploy.py: archivo de fuente verificado contra blobs Git, modelo SHA declarado sin cambios, configuración de ingress validada, migración y servicios arrancados.
- Verificación posterior: 217 archivos del host y 28 archivos de cada paquete instalado en API, worker y observer coinciden con 8553954, sin discrepancias. Servicios running, no OOM; base reachable y worker recent_heartbeat.
- HTTPS estándar con CA/hostname válidos: dashboard, walkthrough, salud y APIs de lectura respondieron 200.
- Comprobación controlada del logger: una petición sin firma por 443 recibió 401 y dejó únicamente `webhook_rejection status=401 reason=signature_headers_missing` en el registro privado. Estados/TEST de la base permanecieron iguales. No fue un TEST oficial ni una delivery firmada.
- Modelo da212d24d1f3bb2c0d8528d62160667f7ca61029e748ca8dac6b5df9a2210bce y configuración 7e15d626651b578a1686c90b1ee1c473f29f9355ef6aa1b4c866ee520f538cd1 sin cambios; fixture=false, hybrid=false. Sin nueva cartera, blend, sondas LLM ni SEC.
- Evidencia fechada: reports/deployment-8553954-20261008.json. La observación oficial retenida tras el arranque seguía en un 2xx y 15 fallos 4xx consecutivos anteriores; cero no-TEST, sin score. No identifica su causa.

## Desplegado

855395446e41813eb3584dab516f20ceced7ed10, coincide con GitHub main y CI aprobada. El diagnóstico de rechazo está activo en producción. Los nuevos informes/STATUS posteriores al despliegue son documentación local; no constituyen otro despliegue.

## ACK de la bandeja

ACK #1 — hecho — cf63519 / ff2c1d7 / fb5b1dd: TEST histórico, caché validada, HTTPS 443 autorizado y comprobado.
ACK #2 — hecho — 94a1dd5 / b4080dc: checklist operacional y backup nocturno con ciphertext/SHA iguales en ambos hosts. Restauración del nuevo archivo todavía no verificada.
ACK #3 — hecho — 94a1dd5: solo Event Desk/INBOX_CODEX.md. Borrador ajeno conservado privado; no publicado. Revisiones de diff y rutas propias antes de commits.
ACK #4 — hecho — 907cabd: README veraz y descripción propuesta.
ACK #5 — hecho — 3c1a763 / 463190f / 514aa0b / d417d0e: clon limpio con dos suites consecutivas 186/1 omitido, lint/tipos verdes. Docker/Compose local no ejecutado; ahora la CI Linux del código publicado pasó Compose y fixtures. No código archivado sin prueba de inutilidad.
ACK #6 — hecho — cancelada por #8; ningún cambio en otro repo.
ACK #7 — hecho — 514aa0b / b4080dc / 8553954: diagnóstico local y comparación real local de proxies; logger ahora publicado y desplegado tras autorización. La causa histórica sigue desconocida.
ACK #8 — hecho — 514aa0b / d417d0e: prioridad de diagnóstico y clon limpio resuelta; #6 cancelada.
ACK #9 — hecho — b40aab8 / b4080dc: resumen de portfolio de 43 líneas y guion propuesto de 90 segundos publicados con el lote aprobado. La duración de la demo no está medida.

## Bloqueado (necesita a Jordi)

- LISTO PARA TEST: https://52.17.192.36.sslip.io/competition/webhook. Jordi pega esta URL en el campo Webhook URL de su submission, guarda y pulsa Send test event. Abrirla en el navegador hace GET y no envía el TEST. Falta verificar una delivery firmada y predicción aceptada por HTTPS estándar en ambos lados.
- Los 15 rechazos anteriores no se pueden reconstruir. Ante un próximo rechazo se leerá el motivo privado enumerado; no cambiar firma, reloj ni secretos a ciegas.
- SEC omitido sin contacto administrativo escrito; no bloquea Phase A. Alertas externas no conectadas; diagnóstico/alertas actuales locales. Sin score ni evidencia prospectiva de edge.

## Siguiente bloque

- Verificar la nueva recepción/ACK/job/predicción persistida y aceptación oficial cuando Jordi envíe TEST. Si falla, leer solo el enum y código de rechazo; conservar evidencia fechada.
- Releer INBOX_CODEX.md al cerrar cada punto y revisar status/diff antes de cualquier commit. Mantener alcance Event Desk.
- Informe y STATUS de este despliegue quedan locales; una nueva publicación necesita la confirmación correspondiente. No repetir el despliegue para cambios documentales.

## Tiempo activo real del objetivo

La última lectura disponible del objetivo anterior fue 8.596 segundos (2 h 23 min 16 s), antes de este turno. Este turno de autorización y despliegue se registra por sus comandos y timestamps; no se ha medido por separado como tiempo activo y no se afirma un bloque de cuatro horas completado.
