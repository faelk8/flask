ADR 0001: Separação de camadas
==============================

Estado
------

Aceito (documentado retrospectivamente).

Contexto
--------

A aplicação combina interface web e API JSON. Regras de negócio acopladas às rotas ou ao ORM dificultariam testar casos de uso e oferecer novas interfaces.

Decisão
-------

Separar domínio, aplicação, infraestrutura e apresentação. O domínio não importa Flask nem SQLAlchemy; a aplicação expressa dependências externas por protocolos. A fábrica de aplicação compõe adaptadores concretos.

Consequências
-------------

Casos de uso podem ser testados sem subir Flask e adaptadores podem ser substituídos. A composição explícita exige manter interfaces e adaptadores alinhados. A nova interface deve depender dos casos de uso, sem duplicar regras de domínio.
