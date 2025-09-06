# api/index.py - Arquivo para deploy na Vercel
import sys
import os

# Adicionar diretório raiz ao path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app

# Handler para Vercel
def handler(request, response):
    return app(request, response)

# Para executar localmente
if __name__ == "__main__":
    app.run(debug=True)