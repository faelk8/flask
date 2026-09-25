# APIs

Repositório para APIs Flask independentes. Cada aplicação e seus artefatos ficam em uma pasta própria, começando por [`01-jogo`](01-jogo/). O Python dos projetos é executado pelo ambiente Conda selecionado no VS Code; não é necessário criar venv.

## Projetos

| Projeto | Descrição | Documentação |
|---|---|---|
| [`01-jogo`](01-jogo/) | Catálogo de jogos em Flask, com interface web e API JSON. | [Guia do projeto](01-jogo/README.md) |

## Documentação

A documentação do repositório é construída com Sphinx. O portal central agrega os guias e ADRs mantidos dentro de cada projeto.

```bash
python -m pip install -r docs/requirements.txt
python -m sphinx -b html -c docs . _build/docs
```

Abra `_build/docs/index.html` após a compilação. Veja [as convenções de contribuição](docs/contributing.rst) para adicionar projetos, páginas e decisões arquiteturais.
