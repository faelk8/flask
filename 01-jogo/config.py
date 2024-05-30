import os

SECRET_KEY = 'rafael'

# dados para conectar no banco
SQLALCHEMY_DATABASE_URI = \
    '{SGBD}://{usuario}:{senha}@{servidor}/{database}'.format(
        SGBD = 'mysql+mysqlconnector',
        usuario = 'root',
        senha = 'admin',
        servidor = 'localhost',
        database = 'jogoteca'
    )

# caminho relativo para a pasta que contem as imagens
UPLOAD_PATH = os.path.dirname(os.path.abspath(__file__)) + '/uploads'