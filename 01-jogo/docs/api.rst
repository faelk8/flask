API HTTP
========

Base: ``/api/v1``. Leituras são públicas; escrita exige sessão autenticada e proteção CSRF.

.. list-table:: Endpoints
   :header-rows: 1
   :widths: 12 38 50

   * - Método
     - Caminho
     - Resultado
   * - GET
     - ``/csrf``
     - Token CSRF da sessão
   * - POST
     - ``/auth/login``
     - Autentica com ``nickname`` e ``senha``; retorna token renovado
   * - POST
     - ``/auth/logout``
     - Encerra sessão (204)
   * - GET
     - ``/games?page=1&per_page=20``
     - Lista paginada
   * - GET
     - ``/games/{id}``
     - Consulta jogo
   * - POST
     - ``/games``
     - Cria jogo (201)
   * - PUT
     - ``/games/{id}``
     - Substitui os campos do jogo
   * - DELETE
     - ``/games/{id}``
     - Exclui jogo (204)

Autenticação e CSRF
-------------------

A autenticação usa cookies de sessão. Obtenha o token em ``GET /api/v1/csrf``, preserve o cookie e envie o token no cabeçalho ``X-CSRFToken`` em toda operação de escrita, inclusive login. Use o token renovado retornado depois da autenticação. Requisições JSON também exigem CSRF.

Criação e atualização
---------------------

O corpo contém ``nome``, ``categoria`` e ``console``. Campos desconhecidos são rejeitados. Exemplo:

.. code-block:: json

   {"nome": "Tetris", "categoria": "Puzzle", "console": "PC"}

Paginação e erros
-----------------

A listagem aceita ``page`` e ``per_page``, com máximo de 100 itens por página. A resposta inclui ``data``, ``meta`` e links ``next`` e ``previous``. Erros usam o formato ``{"error":{"status":404,"message":"...","request_id":"..."}}``. Consulte o guia do projeto para limites, códigos HTTP e controles de segurança completos.
