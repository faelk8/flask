Desenvolvimento e operação
==========================

Ambiente local
--------------

Use o ambiente Conda selecionado no VS Code. Não crie venv. Na pasta ``01-jogo/``, instale as dependências e prepare a configuração local:

.. code-block:: console

   python -m pip install -r requirements-dev.txt
   cp .env.example .env
   python -c 'import secrets; print(secrets.token_hex(32))'

Defina o segredo gerado como ``SECRET_KEY`` no arquivo ``.env``. Esse arquivo contém configuração local e não deve ser versionado.

Atualize o banco e inicie a aplicação:

.. code-block:: console

   python -m flask --app jogoteca db upgrade
   python -m flask --app jogoteca run

Crie usuários administrativos pelo comando ``python -m flask --app jogoteca create-user``; não há credenciais padrão.

Testes
------

A suíte usa SQLite isolado e diretórios temporários. Execute-a na pasta do projeto:

.. code-block:: console

   python -m pytest -q

Migrações
---------

Use ``flask --app jogoteca db upgrade`` para aplicar migrações. Para um banco legado que contém exatamente as tabelas antigas ``jogos`` e ``usuarios`` e ainda não tem histórico Alembic, faça backup e valide uma cópia antes de executar ``flask --app jogoteca db stamp 0001`` seguido de ``flask --app jogoteca db upgrade``. Não use ``stamp`` em um banco vazio ou com esquema diferente.

Produção
--------

A implantação usa Docker Compose, Gunicorn, MySQL, Redis e Nginx, com configuração em ``compose.yaml`` e ``deploy/``. Configure os segredos e certificados a partir de ``deploy/production.env.example``; nunca inclua valores reais no repositório. Leia ``README.md`` e os arquivos de implantação antes de publicar mudanças.
