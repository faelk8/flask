# Jogoteca — Flask com Clean Architecture

Catálogo de jogos com interface HTML e API JSON em `/api/v1`. Python 3.12+.

## Arquitetura

- `app/domain.py`: entidades e validações independentes do framework.
- `application.py`: casos de uso e portas (`Protocol`) para repositórios e hash de senhas.
- `infrastructure.py`: adaptadores SQLAlchemy e bcrypt.
- `presentation.py`: blueprints HTML/JSON, formulários e tradução de erros para HTTP.
- `covers.py`: validação e armazenamento de capas JPEG.
- `__init__.py`: application factory, composição das dependências e comandos administrativos.

Os casos de uso recebem interfaces por construtor. `create_app(..., game_service=..., auth_service=...)` também aceita serviços substitutos. Não há imports de Flask/SQLAlchemy nas camadas de domínio e aplicação. Testes unitários demonstram execução sem Flask.

## Executar localmente

Com o ambiente Conda selecionado no VS Code e o terminal aberto nesta pasta:

```bash
python -m pip install -r requirements-dev.txt
cp .env.example .env
python -c 'import secrets; print(secrets.token_hex(32))'
```

Copie o valor gerado para `SECRET_KEY` no `.env`. Nunca versione segredos. O projeto usa o Python do ambiente Conda selecionado; não crie um ambiente virtual separado.

```bash
python -m flask --app jogoteca db upgrade
python -m flask --app jogoteca create-user
python -m flask --app jogoteca run
```

Acesse `http://127.0.0.1:5000`. O CLI carrega o `.env` desta pasta. Não existem usuários ou senhas padrão. O cadastro administrativo pede senha por entrada oculta (mínimo 12 caracteres). SQLite é o padrão local; para MySQL configure `DATABASE_URL=mysql+mysqlconnector://usuario:senha@host/jogoteca` e instale previamente o banco. Use um usuário de aplicação com privilégios limitados.

`init-db` e `prepara_banco.py` criam tabelas ausentes sem apagar registros; não atualizam esquemas existentes. Prefira as migrações acima para bancos novos.

## Migrar o banco antigo

Faça backup e teste a migração em uma cópia antes de alterar dados reais. Os nomes de tabelas e colunas e os hashes bcrypt anteriores foram preservados.

Para um banco que já contém exatamente as tabelas antigas `jogos` e `usuarios`, sem histórico Alembic:

```bash
flask --app jogoteca db stamp 0001
flask --app jogoteca db upgrade
```

Não execute `stamp 0001` em banco vazio ou com esquema diferente. A revisão `0002` acrescenta unicidade ao nome do jogo e interrompe se encontrar duplicatas; revise-as manualmente. Ela não apaga jogos. Bancos novos usam apenas `db upgrade`. Troque credenciais antigas expostas no código e as senhas dos usuários de demonstração; a nova chave também invalida sessões antigas.

## API

| Método | Caminho | Resultado |
|---|---|---|
| GET | `/api/v1/csrf` | Token CSRF para a sessão |
| POST | `/api/v1/auth/login` | Login com `nickname` e `senha`; novo token CSRF |
| POST | `/api/v1/auth/logout` | Encerra sessão, 204 |
| GET | `/api/v1/games?page=1&per_page=20` | Lista paginada, 200 |
| GET | `/api/v1/games/1` | Jogo, 200 |
| POST | `/api/v1/games` | Cria jogo, 201 e cabeçalho Location |
| PUT | `/api/v1/games/1` | Substitui campos, 200 |
| DELETE | `/api/v1/games/1` | Exclui jogo, 204 |

Corpo de criação/edição: `{"nome":"Tetris","categoria":"Puzzle","console":"PC"}`. Campos adicionais são rejeitados. Leitura é pública; toda escrita exige login. O catálogo é compartilhado: qualquer usuário cadastrado administra todos os jogos. Cadastro de usuários é feito somente pelo CLI.

A API usa cookies de sessão: primeiro obtenha `/csrf`, preserve o cookie e envie `X-CSRFToken` em **todas** as operações de escrita, inclusive login. Após login, use o novo token retornado. Envie JSON com `Content-Type: application/json`. Não há isenção CSRF para JSON.

Paginação usa `LIMIT/OFFSET`, ordenação estável por ID, limite de 100 itens e `page` entre 1 e 100000. Retorna `data`, `meta` (`page`, `per_page`, `total`, `pages`) e links `next`/`previous`. Páginas além do total retornam lista vazia com 200. A interface HTML também oferece navegação por páginas.

## Respostas e segurança

2xx significam sucesso; 3xx são redirecionamentos, não erros. Formulários concluídos redirecionam com 303. Erros JSON seguem:

```json
{"error":{"status":404,"message":"Jogo não encontrado.","request_id":"..."}}
```

Tratamento central para 400 (requisição/CSRF), 401 (autenticação), 404, 405 (preserva Allow), 409 (duplicidade), 413 (limite de upload), 415 (tipo de conteúdo), 422 (validação), 429 (limite de requisições, com Retry-After) e demais exceções HTTP. Falhas inesperadas retornam 500 genérico, fazem rollback da sessão do banco e registram stack trace apenas no servidor, com identificador de requisição.

Cookies HttpOnly/SameSite, CSRF global, consultas parametrizadas, escape HTML, CSP, bloqueio de frames e MIME sniffing. Exclusão e logout não aceitam GET. Login limita 5 tentativas/minuto por IP; limite geral de 300 requisições/minuto. Uploads limitados a 2 MiB por requisição, JPEG real e 16 megapixels, reencodificados sem metadados e com nome gerado pelo servidor. Capas são opcionais.

Banco e arquivos locais não participam de uma transação única: falhas de disco depois do commit podem deixar a capa desatualizada ou um arquivo órfão. Para múltiplas instâncias, use armazenamento compartilhado de capas. As medidas seguem as [orientações de segurança do Flask](https://flask.palletsprojects.com/en/stable/web-security/); não substituem uma auditoria do ambiente implantado.

## Produção

Defina `APP_ENV=production`, uma `SECRET_KEY` aleatória, `DATABASE_URL`, `TRUSTED_HOSTS` (hosts separados por vírgula) e `RATELIMIT_STORAGE_URI=redis://...`. A aplicação recusa produção com armazenamento de rate limit em memória ou hosts ausentes. Cookies Secure e HSTS ficam ativos nesse modo. Exporte as variáveis no ambiente do processo; Gunicorn não carrega o `.env` automaticamente.

```bash
gunicorn --workers 2 --bind 127.0.0.1:8000 'app:create_app()'
```

Publique atrás de HTTPS. Debug permanece desativado. Não confie em `X-Forwarded-For` enviado diretamente pelo cliente; o limitador usa o IP da conexão. Se houver proxy reverso, configure confiança no número exato de proxies na implantação, para não agrupar todos os usuários no mesmo IP nem permitir falsificação. Redis deve ser compartilhado entre workers. Configure backup, logs e monitoramento no ambiente de implantação.

O arquivo `requirements.lock` registra as versões exatas verificadas, incluindo ferramentas de teste. `requirements.txt` contém apenas dependências da aplicação e `requirements-dev.txt` acrescenta testes.

## Verificação

```bash
python -m pytest -q
```

Testes usam SQLite isolado e diretórios temporários, cobrindo casos de uso, CRUD, paginação, validação, CSRF real, login/logout, limitação de tentativas, uploads, redirecionamentos e erros. MySQL e infraestrutura de produção devem ser validados no ambiente de destino.

## Documentação

A documentação central em Sphinx e os ADRs deste projeto ficam em [`../docs`](../docs) e [`docs/adr`](docs/adr). Para compilar o portal, consulte as instruções da raiz do repositório.
