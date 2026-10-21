# Dashboard de Backups

![Python 3.10](https://img.shields.io/badge/Python-3.10-3776AB?logo=python&logoColor=white)
![Flask 2.3.3](https://img.shields.io/badge/Flask-2.3.3-000000?logo=flask&logoColor=white)
![Docker Compose](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Uso interno](https://img.shields.io/badge/Uso-rede%20interna-10B981)

Painel web para **consultar, acompanhar e baixar backups de configuração** de equipamentos de rede. A interface organiza os arquivos por fabricante e equipamento e mostra quando cada backup foi atualizado pela última vez.

![Exemplo ilustrativo do dashboard com dados fictícios](backup-manager/docs/screenshots/dashboard-demo.png)

> **Imagem demonstrativa:** nomes, quantidades e datas acima são fictícios. O painel real exibe os arquivos encontrados nos diretórios configurados.

## ✨ Recursos

| Recurso | O que oferece |
| --- | --- |
| 🗂️ Navegação | Fabricante → equipamento → versões de backup. |
| 🔎 Busca | Filtra os itens exibidos na tela atual. |
| 🟢 Estado dos backups | Indica equipamentos em dia, atrasados, sem backup ou com diretório indisponível. |
| ⬇️ Download | Baixa arquivos listados para o equipamento selecionado. |
| 🕒 Horário | Exibe datas no fuso `America/Manaus`. |
| 🐳 Docker | Executa o painel com os diretórios de backup montados somente para leitura. |

## 🚀 Início rápido

```bash
git clone https://github.com/Pliffisson/dashboard-backup.git
cd dashboard-backup/backup-manager
cp .env.example .env
```

Edite o `.env` com os caminhos **absolutos** dos diretórios de backup no seu servidor. Depois execute:

```bash
docker compose up -d --build
```

Acesse `http://localhost:5005` no servidor ou use o endereço interno dele. A porta pode ser alterada por `BACKUP_PORT` no `.env`.

Para os formatos de arquivo aceitos, todas as opções de configuração e comandos de operação, leia o **[guia completo da aplicação](backup-manager/README.md)**.

## 🔒 Uso e dados

O projeto foi pensado para uma rede interna e **não inclui autenticação**. Restrinja o acesso à porta pela infraestrutura da sua rede. Os backups são montados como `:ro`; o `.env` local e os arquivos reais de backup não devem ser enviados ao GitHub.

## 📁 Estrutura

```text
.
├── README.md                    # Visão geral
└── backup-manager/
    ├── app.py                   # Aplicação Flask
    ├── docker-compose.yml       # Serviço e volumes
    ├── .env.example             # Modelo de configuração
    ├── templates/               # Interface HTML
    ├── static/                  # CSS e imagens
    └── docs/screenshots/        # Imagem demonstrativa
```
