# Desafio 4 — Multiagente de consulta de arquivos CSV

Protótipo funcional para carregar um ZIP com arquivos CSV, inferir o schema, consultar os dados em linguagem natural e exibir a resposta em texto, tabela ou gráfico.

## Framework e arquitetura

O framework obrigatório utilizado é **LangChain**. O modelo opcional é integrado por `create_agent`, com saída estruturada em um plano Pydantic (`QueryPlan`). Sem chave de API, o mesmo contrato é executado pelo agente local determinístico, o que permite demonstrar e testar o MVP offline.

`Streamlit → LoaderAgent → SchemaAgent → QueryAgent (LangChain ou local) → ExecutorAgent/Pandas → VizAgent`

O modelo não executa código gerado. Ele produz apenas um plano validado; a execução fica restrita às operações implementadas em `src/data_engine.py`.

## Instalação

Requer Python 3.10 ou superior.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Para ativar o planejador com Anthropic, copie `.env.example` para `.env` e informe `ANTHROPIC_API_KEY`. A chave não deve ser incluída no ZIP entregue.

## Como usar

1. Abra a aba **Carregar dados**.
2. Envie um ZIP com um ou mais CSVs. O projeto aceita dicionário em `data_dictionary.csv`, `dicionario.md`, `layout.txt` ou nome equivalente.
3. Clique em **Processar arquivos** e confira o resumo e a prévia.
4. Abra **Consultar** e faça perguntas como:
   - `Qual o valor total das notas fiscais emitidas?`
   - `Quais os 5 emitentes com maior valor total de notas?`
   - `Qual UF do destinatário recebeu mais notas fiscais?`
   - `Qual a quantidade total por NCM?`
5. Em **Evidências**, baixe o schema e o histórico de consultas.

## Testes automatizados

```powershell
python -m unittest discover -s tests -v
```

A suíte cobre leitura do ZIP, dicionário, soma, média, contagem distinta de notas, rankings, CFOP, NCM, UF do destinatário e listagem ordenada de notas. O roteiro completo está em `docs/GUIA_DE_TESTE.md`.

## Estrutura

- `app.py`: interface Streamlit com três interfaces: carga, consulta e evidências.
- `src/csv_loader.py`: validação do ZIP, leitura de CSV e identificação de dicionário.
- `src/models.py`: planos de consulta Pydantic.
- `src/agent.py`: agentes local e LangChain com fallback seguro.
- `src/data_engine.py`: filtros, agregações, ordenação, formatação e execução determinística.
- `tests/`: testes automatizados.
- `sample_data/`: ZIP pequeno para demonstração rápida.
- `docs/`: guia de teste e documentação de entrega.

## Limitações conhecidas

O MVP executa perguntas baseadas em campos e agregações previstas. Consultas que exigem joins complexos, regras fiscais específicas ou semântica fora do schema devem ser refinadas ou respondidas como não mapeadas. O modo LangChain depende de rede e de uma chave válida; o modo local permanece disponível para a demonstração.

