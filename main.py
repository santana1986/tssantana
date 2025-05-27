# -*- coding: utf-8 -*-
"""Ponto de entrada principal para execução do aplicativo."""

from src import create_app

app = create_app()

if __name__ == '__main__':
    # Executar em modo de desenvolvimento. Para produção, usar um servidor WSGI como Gunicorn.
    # Ouvir em 0.0.0.0 para ser acessível externamente (inclusive via expose_port).
    app.run(host='0.0.0.0', port=5000, debug=True)

