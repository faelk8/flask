Arquitetura
===========

A aplicação segue separação por responsabilidades. ``app/domain.py`` contém entidades e regras sem dependência de Flask ou SQLAlchemy. ``app/application.py`` implementa casos de uso e declara portas por protocolos. ``app/infrastructure.py`` fornece adaptadores SQLAlchemy e bcrypt. ``app/presentation.py`` conecta os casos de uso às rotas HTML e JSON. ``app/covers.py`` controla validação e armazenamento de capas; ``app/security.py`` concentra controles de segurança.

Fluxo de dependências
---------------------

A apresentação chama a aplicação por interfaces. A aplicação depende de abstrações, não de adaptadores concretos. A fábrica em ``app/__init__.py`` instancia e conecta os adaptadores. Os serviços também podem ser substituídos na fábrica para testes ou outras composições.

.. code-block:: text

   presentation -> application <- infrastructure
                         ^
                         |
                       domain

Persistência
------------

SQLAlchemy é o adaptador de persistência. O desenvolvimento local usa SQLite por padrão; o ambiente de produção pode apontar para MySQL. Alembic mantém a evolução do esquema em ``migrations/``. Alterações de esquema devem ser entregues por migrações revisáveis, preservando os dados existentes.

Limites
-------

Banco de dados e armazenamento de capas locais não participam da mesma transação. Em falhas entre o commit e a operação de arquivo, uma capa pode ficar desatualizada ou órfã. Mais de uma instância requer armazenamento de capas compartilhado. Consulte os ADRs para o histórico das decisões registradas.
