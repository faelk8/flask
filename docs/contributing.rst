Contribuir com a documentação
==============================

Organização
-----------

* Mantenha código, dependências, testes, implantação e documentação específica dentro da pasta da API correspondente.
* Use ``docs/`` na raiz para o portal, padrões aplicáveis a todo o repositório e índice de projetos.
* Use ``<projeto>/docs/`` para arquitetura, operação, contratos e ADRs específicos daquela aplicação.
* Escreva páginas em reStructuredText (``.rst``) para que o Sphinx as inclua no portal.

Adicionar um projeto
--------------------

1. Crie uma pasta com identificador e nome, por exemplo ``02-clientes/``.
2. Mantenha nela a aplicação, ``requirements.txt``, testes, configuração de execução e ``docs/index.rst``.
3. Adicione a página de índice do projeto ao toctree de ``docs/index.rst``.
4. Registre decisões locais em ``<projeto>/docs/adr/`` e ligue o índice de ADRs ao índice do projeto.
5. Documente instalação e execução com o Python do Conda selecionado no VS Code. Não instrua a criação de venv.

Decisões arquiteturais
----------------------

Use um arquivo por decisão em ``<projeto>/docs/adr/`` com nome sequencial, como ``0001-limites-da-aplicacao.rst``. Cada ADR deve registrar contexto, decisão, estado e consequências, incluindo custos e alternativas relevantes. Não reescreva uma decisão aceita: marque-a como superseded e crie um novo ADR que a substitua.

Validação
---------

Compile o portal a partir da raiz do repositório:

.. code-block:: console

   python -m sphinx -b html -c docs . _build/docs

Confira avisos de referências quebradas e confirme que cada projeto novo aparece na navegação.
