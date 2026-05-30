# SSC0158 - Checkpoint 3

Projeto de protótipo de streaming de dados com arquitetura containerizada e coleta em tempo real.

## Objetivo

Implementar o Checkpoint 3 com:
- protótipo funcional executando coleta real de dados;
- documentação do setup experimental;
- resultados preliminares;
- evidências de coleta real.

## Arquitetura

Serviços:
- `mqtt-broker`: broker MQTT para transporte de eventos de telemetria;
- `sensor`: simulador de sensores que publica dados reais em tempo real;
- `collector`: consumidor MQTT que persiste medições em banco SQLite;
- `api`: API web que expõe dados coletados e interface de visualização.

## Execução

1. Acesse o diretório do projeto:
   ```bash
   cd ~/Documents/Disciplinas/Projeto\ de\ SI/SSC0158_checkpoint3
   ```

2. Inicie o sistema:
   ```bash
   docker compose up --build
   ```

3. Acesse a interface web:
   - `http://localhost:8000`

4. Verifique a API de dados:
   - `http://localhost:8000/api/latest`
   - `http://localhost:8000/api/history?limit=20`

## Executando os testes

Para rodar os testes de API localmente:

```bash
pip install --no-cache-dir -r src/requirements.txt
pip install --no-cache-dir -r requirements-dev.txt
pytest
```

Os testes ficam em `tests/test_api.py` e validam os endpoints principais de `api.py`.

## Conteúdo do projeto

- `docker-compose.yml`: orquestração dos serviços;
- `src/Dockerfile`: imagem do serviço Python;
- `src/api.py`: serviço HTTP e dashboard web;
- `src/collector.py`: coleta MQTT e persistência em SQLite;
- `src/sensor_simulator.py`: simulação de telemetria em tempo real;
- `src/static/index.html`: dashboard de visualização básica;
- `mosquitto/config/mosquitto.conf`: configuração de broker MQTT;
- `scripts/run_experiment.sh`: script para rodar o experimento e coletar evidências.
- `.gitignore`: lista de arquivos e pastas que não devem ser versionados, como `.venv/`, `data/`, caches e arquivos temporários.

## Setup Experimental

A documentação do setup experimental está em `scripts/run_experiment.sh`.
Ele inicia os serviços, aguarda coleta e salva os resultados preliminares em `results/`.

## Entrega Checkpoint 3

Checklist atendido:
- [x] Protótipo implementado em containers Docker;
- [x] Setup experimental documentado;
- [x] Coleta real de dados via MQTT e persistência em SQLite;
- [x] Interface web simples para demonstrar informações em tempo real.

> Observação: o ambiente local deste agente não possui Docker instalado, portanto a execução precisa ser feita em uma máquina com Docker disponível.
