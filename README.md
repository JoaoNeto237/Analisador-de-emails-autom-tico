Analisador Inteligente de E-mails
Uma solução digital para automatizar a classificação e resposta de e-mails, criada como parte de um desafio prático de desenvolvimento.

📄 Visão Geral do Projeto
Este projeto consiste em uma aplicação web simples que utiliza técnicas de Processamento de Linguagem Natural (NLP) para automatizar a triagem de e-mails em um ambiente corporativo. A aplicação é capaz de:

Classificar e-mails em duas categorias principais: Produtivo e Improdutivo.

Sugerir respostas automáticas baseadas na classificação realizada.

O objetivo é liberar a equipe de atendimento de tarefas manuais de triagem, permitindo que se concentrem em demandas que exigem intervenção humana.

🚀 Tecnologias Utilizadas
Backend: Python com o framework Flask para a API web.

Frontend: HTML, CSS e JavaScript puros para uma interface de usuário intuitiva e leve.

Processamento de Linguagem Natural (NLP):

Lógica Baseada em Regras: Utiliza um classificador de regras e padrões de texto para alta velocidade e previsibilidade.

Detecção de Idioma: A biblioteca langdetect é usada para garantir que a aplicação processe apenas e-mails em português.

⚙️ Como Executar Localmente
Siga estas instruções para configurar e rodar a aplicação em sua máquina.

Pré-requisitos
Certifique-se de ter o Python 3.8 ou superior instalado.

1. Clonar o Repositório
Bash

git clone https://github.com/JoaoNeto237/Analisador-de-emails.git
cd analisador-de-emails

2. Configurar o Ambiente Virtual

# Criar o ambiente virtual
python -m venv venv

# Ativar o ambiente virtual
# No Windows
venv\Scripts\activate
# No macOS ou Linux
source venv/bin/activat

3. Instalar as Dependências
As bibliotecas necessárias estão listadas no arquivo requirements.txt.

Bash

pip install -r requirements.txt
4. Rodar a Aplicação
Inicie o servidor Flask na pasta raiz do projeto.

Bash

python app.py

📞 Contato
Para dúvidas ou sugestões, entre em contato através do meu perfil no GitHub.
