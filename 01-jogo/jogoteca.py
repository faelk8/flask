from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from flask_bcrypt import Bcrypt

app = Flask(__name__)
# carrega os dados de configuração para conexão do banco
app.config.from_pyfile('config.py')

# conecta no banco
db = SQLAlchemy(app)
csrf = CSRFProtect(app)
bcrypt = Bcrypt(app)

# importar as rotas
from views_game import *
from views_user import *

# executa toda a aplicação
if __name__ == '__main__':
    app.run(debug=True)