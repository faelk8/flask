ADR 0002: Migrações de esquema
==============================

Estado
------

Aceito (documentado retrospectivamente).

Contexto
--------

Criar tabelas ausentes não atualiza com segurança bancos existentes. Alterações de esquema precisam ser reproduzíveis e preservar os dados da aplicação.

Decisão
-------

Usar Alembic por meio de Flask-Migrate. Revisões versionadas em ``migrations/`` são o caminho normal de evolução do banco; ``create_all`` fica restrito a inicialização e testes.

Consequências
-------------

Implantações podem aplicar revisões ordenadas e auditáveis. Mudanças destrutivas exigem plano de migração, backup e verificação dos dados. Bancos legados só devem receber uma revisão-base depois de confirmar que o esquema existente corresponde a ela.
