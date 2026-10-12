# Corrección mecánica de compilación del harness (aditiva)

La primera B terminó 132 PASS / 16 ERROR, 0 FAIL/skip. Los 16 errores comparten CS0136 en tests/sensitive_runner/Program.cs:80: la adaptación scoped declaró registry dentro de un bloque cuyo método ya declaraba registry posteriormente. No se ejecutaron los 16 cuerpos bloqueados por setup. XML/stdout completos permanecen en el directorio externo B_authority_leaf_ordering.

Se corrigió únicamente el nombre local a lostRegistry, sin cambio de test values, expectativas, assertions ni producto. candidate_freeze.json conserva el candidato inicial; candidate_freeze_02.json registra before/after y es el candidato final. A y B se reinician completas después de esta corrección de compilación; no se aprovecha el error ni se reintenta un resultado de seguridad para conseguir calidad. No cambia la clasificación congelada.

La corrección forma parte de la preparación mínima del caller equivalente autorizado; no cambia ningún contrato de seguridad. Las pruebas nativas positivas y los restantes 132 checks efectivamente ejecutados no fallaron, pero no sustituyen la nueva corrida final.

