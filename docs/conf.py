project = "APIs"
author = "Equipe de desenvolvimento"
copyright = ""
release = ""

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
]

root_doc = "docs/index"
source_suffix = {".rst": "restructuredtext"}
exclude_patterns = [
    "_build",
    ".git",
    ".venv",
    "**/__pycache__",
    "**/.pytest_cache",
    "**/.ruff_cache",
    "**/uploads/**",
]

language = "pt_BR"
html_title = "APIs | Documentação"
html_theme = "alabaster"
html_static_path = []

autodoc_typehints = "description"
autoclass_content = "both"
todo_include_todos = False
