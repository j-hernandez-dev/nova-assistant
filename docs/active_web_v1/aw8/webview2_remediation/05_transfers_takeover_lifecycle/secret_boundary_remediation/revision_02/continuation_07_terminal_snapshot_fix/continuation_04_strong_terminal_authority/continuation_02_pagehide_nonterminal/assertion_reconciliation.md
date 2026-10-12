# PAGEHIDE — reconciliación prospectiva autorizada

Decisión humana: PAGEHIDE carece de autoridad terminal. Sólo SUBMIT_CONFIRMED, ENGINE_WORLD_RETIRE y TAKEOVER_END_CHECKPOINT producen snapshots COMMIT-able.
Se conserva literalmente continuation_01: A=48 PASS; B=102 PASS; C=0 PASS / 1 FAIL, PAGEHIDE/SensitiveMessage/rev48.

## native/nova-browser-host/tests/terminal_ordering_runner/Program.cs — reason-pagehide

Preparación/assertion antigua: PAGEHIDE snapshot -> Commit -> COMMITTED.
Nueva semántica: PAGEHIDE updates exact observed current/revision -> TRANSIENT, no snapshot/Commit.
Frontera fuerte posterior: ninguna; permanece TRANSIENT.
SHA anterior: 225d7ebcc1cabf57371be6b0f565b6a09478916ea12acf9150e8f689c6a28f87. SHA posterior: 91ebaf1b207080a0b647b5a72ee5f703d8014d514c1400e83a5a56a95319b775.

## native/nova-browser-host/tests/terminal_ordering_runner/Program.cs — old-document

Preparación/assertion antigua: PAGEHIDE supplies old terminal proof before retire.
Nueva semántica: PAGEHIDE weak observed value first; explicit CHECKPOINT proof supplies the old terminal before document retires; old ownership/stale assertions preserved.
Frontera fuerte posterior: TAKEOVER_END_CHECKPOINT.
SHA anterior: 225d7ebcc1cabf57371be6b0f565b6a09478916ea12acf9150e8f689c6a28f87. SHA posterior: 91ebaf1b207080a0b647b5a72ee5f703d8014d514c1400e83a5a56a95319b775.

## native/nova-browser-host/tests/retirement_seal_runner/Program.cs — pagehide-reuse, pagehide-uncommitted

Preparación/assertion antigua: PAGEHIDE creates COMMIT-able proof then seal reuses it.
Nueva semántica: PAGEHIDE cannot terminalize; a separate explicit CHECKPOINT proof is reusable by the unchanged retirement seal; same identity/revision/commit-count assertions.
Frontera fuerte posterior: TAKEOVER_END_CHECKPOINT and ENGINE_WORLD_RETIRE.
SHA anterior: 8912a1dd14913ae6f68a46c0d1c206bb112110c567b7b3a06e65ba9748fd7367. SHA posterior: c7748c629c898c151bd99d44cf11cd00cf4d7f4ff79d146e819f516a2a8f0ac2.

## native/nova-browser-host/tests/transient_policy_runner/Program.cs — terminal-retire, short-retire-denied

Preparación/assertion antigua: PAGEHIDE proof + generic Retire.
Nueva semántica: PAGEHIDE weak, then exact registered protected-world retirement seal supplies terminal authority; long COMMITTED and genuine short denial unchanged.
Frontera fuerte posterior: ENGINE_WORLD_RETIRE.
SHA anterior: 97cdc45bd8881366f64daf100c56019577ffdca06315247d26609fa37ebebd2f. SHA posterior: 1017b4710353da5de7bd46182a9ec93e293fe368e10b46e32a5925b236d3f072.

## native/nova-browser-host/tests/strong_terminal_runner/Program.cs — blur-then-pagehide, strong-pagehide-long, strong-pagehide-short

Preparación/assertion antigua: PAGEHIDE directly COMMITTED/SHORT_COMMITTED_VALUE.
Nueva semántica: PAGEHIDE TRANSIENT with no failure; a separate CHECKPOINT proves COMMITTED or true short denial.
Frontera fuerte posterior: TAKEOVER_END_CHECKPOINT.
SHA anterior: fdd36faeed8d8b60e83ff740a3c0b668d6ddcdaa26bbbb5ee6c4981ee845d746. SHA posterior: 91cd8aceae55af0d3df87cb20a5018dac0ce12354483aa632e2cc33b905e989c.

Valores, longitudes, fixtures y secuencias nativas históricas no cambian. Se mantienen assertions de no exposición, monotonicidad, short-terminal denial, ownership, exact current/revision y no commit duplicado.
Los nombres de casos PAGEHIDE antiguos se conservan como identidades de regresión, no como claims de terminal authority. La referencia stale del caso old-document procede ahora de un CHECKPOINT explícito; su assertion de ownership/retired rejection permanece.
Las assertions de COMMITTED/short denial se satisfacen exclusivamente tras una frontera fuerte separada; no se añaden ForceTerminal/TestOnlyCommit ni una cuarta fuente terminal.
