# -*- coding: utf-8 -*-
"""Inicialização do aplicativo Flask."""

from flask import Flask

def create_app():
    """Cria e configura uma instância do aplicativo Flask."""
    app = Flask(__name__, template_folder='templates')
    app.config['SECRET_KEY'] = 'dev_secret_key' # Usar uma chave segura em produção

    # Importar e registrar blueprints ou rotas aqui
    from . import routes
    app.register_blueprint(routes.bp)

    # Inicializar extensões (ex: banco de dados) aqui, se necessário

    return app

