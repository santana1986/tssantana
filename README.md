# TS Sant'ana Gerenciador de Competições

Este é um aplicativo web desenvolvido em Flask para gerenciar competições esportivas (Futebol, Futsal, Fut7, Futebol Suíço).

## Funcionalidades

*   Criação de competições com escolha de formato:
    *   Grupos + Mata-Mata
    *   Pontos Corridos (Turno Único)
*   Gerenciamento de Times e Jogadores.
*   Configuração de Fase de Grupos (para formato Grupos + Mata-Mata).
*   Geração automática de partidas (Fase de Grupos e Pontos Corridos).
*   Registro de resultados das partidas, incluindo eventos de jogadores (gols, cartões amarelos/vermelhos).
*   Cálculo e exibição de classificações (Grupos e Pontos Corridos) com critérios de desempate.
*   Configuração e geração de Fase Eliminatória (Mata-Mata) a partir dos classificados dos grupos.
*   Exibição da programação completa dos jogos.
*   Cálculo e exibição de estatísticas: Artilharia, Disciplina (cartões), Goleiros Menos Vazados.
*   Geração de Súmulas das partidas finalizadas em formato PDF.
*   **Persistência de Dados:** Os dados são salvos em um arquivo `data.json` para não serem perdidos.

## Como Executar Localmente

**Pré-requisitos:**

*   Python 3.11 ou superior instalado.
*   `pip` (gerenciador de pacotes Python).
*   A fonte DejaVu Sans (geralmente pré-instalada no Linux ou pode ser baixada).

**Passos:**

1.  **Descompacte** o arquivo `competition_manager.zip` em um diretório de sua escolha.
2.  **Navegue** até o diretório descompactado (`competition_manager`) pelo terminal:
    ```bash
    cd caminho/para/competition_manager
    ```
3.  **(Importante para Deploy) Crie o diretório de dados se não existir:** Antes de rodar pela primeira vez ou fazer deploy, certifique-se de que o diretório onde `data.json` será salvo existe. Para execução local, o caminho está em `src/models.py` (ajuste se necessário). Para deploy no Render (conforme configurado), o diretório `/var/data` deve ser montado como disco persistente.
4.  **(Opcional, mas recomendado) Crie e ative um ambiente virtual:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # No Linux/macOS
    # venv\Scripts\activate    # No Windows
    ```
5.  **Instale as dependências:**
    ```bash
    pip install -r requirements.txt
    ```
6.  **Execute o aplicativo Flask (para desenvolvimento):**
    ```bash
    flask --app src.main run --host=0.0.0.0 --port=5000
    ```
    *   O aplicativo estará acessível no seu navegador em `http://localhost:5000` ou `http://<seu-ip-local>:5000`.

7.  **Execute com Gunicorn (para simular produção):**
    ```bash
    gunicorn src.main:app --bind 0.0.0.0:5000
    ```

## Como Implantar Permanentemente (Exemplo: Render.com)

Este aplicativo foi preparado para implantação em plataformas como o Render.com, que oferece planos gratuitos para serviços web e discos persistentes.

**Passos Gerais (Consulte a documentação do Render para detalhes):**

1.  **Crie uma conta** no [Render.com](https://render.com/).
2.  **Crie um "New Web Service"**.
3.  **Conecte seu repositório Git** (GitHub, GitLab, etc.) onde você subiu o código deste projeto, ou faça upload manual do código (descompacte o ZIP e suba a pasta `competition_manager`).
4.  **Configurações do Serviço:**
    *   **Environment:** Python 3
    *   **Region:** Escolha a mais próxima de você.
    *   **Build Command:** `pip install -r requirements.txt` (geralmente detectado automaticamente).
    *   **Start Command:** `gunicorn src.main:app --preload` (deve ser detectado pelo `Procfile`).
5.  **Adicione um "Disk" (Disco Persistente):**
    *   **Name:** `data` (ou outro nome)
    *   **Mount Path:** `/var/data` (Este caminho **DEVE** corresponder ao `DATA_FILE` em `src/models.py`).
    *   **Size:** Escolha o tamanho desejado (o plano gratuito oferece um tamanho limitado).
6.  **Clique em "Create Web Service"**.
7.  Aguarde o build e o deploy. O Render fornecerá uma URL pública no formato `https://seu-servico.onrender.com`.

**Observações:**

*   A primeira vez que o aplicativo rodar no Render, ele criará o arquivo `data.json` no disco persistente `/var/data`.
*   Certifique-se de que as permissões de escrita estão corretas para o diretório `/var/data` no ambiente do Render.
*   Outras plataformas (Heroku, Vercel com Serverless Functions, etc.) podem exigir configurações diferentes, especialmente para persistência de dados.

