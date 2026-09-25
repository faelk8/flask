ADR 0003: Sessão e proteção CSRF
================================

Estado
------

Aceito (documentado retrospectivamente).

Contexto
--------

A interface web e a API compartilham autenticação baseada em sessão. Navegadores enviam cookies automaticamente, inclusive em requisições iniciadas por outro site.

Decisão
-------

Usar cookies de sessão e exigir token CSRF em toda operação de escrita, inclusive nas rotas JSON e no login. Não criar exceção CSRF para chamadas da API.

Consequências
-------------

Clientes de navegador precisam obter e enviar o token CSRF e preservar o cookie de sessão. Operações de leitura permanecem públicas; as escritas continuam autenticadas. Clientes não baseados em navegador devem implementar o mesmo fluxo ao usar esses endpoints.
