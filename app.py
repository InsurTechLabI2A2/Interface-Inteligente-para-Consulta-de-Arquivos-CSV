from __future__ import annotations

import io
import json

import plotly.express as px
import streamlit as st
from dotenv import load_dotenv

from src.agent import LangChainCsvAgent
from src.csv_loader import LoadedDataset, load_zip


load_dotenv()
st.set_page_config(page_title="Multiagente CSV — Desafio 4", page_icon="📊", layout="wide")
st.title("📊 Multiagente de consulta de arquivos CSV")
st.caption("Desafio 4 — upload de ZIP, dicionário de dados e perguntas em linguagem natural.")

if "dataset" not in st.session_state:
    st.session_state.dataset = None
if "history" not in st.session_state:
    st.session_state.history = []

load_tab, query_tab, evidence_tab = st.tabs(["1. Carregar dados", "2. Consultar", "3. Evidências"])

with load_tab:
    st.subheader("Carregar ZIP com CSVs")
    st.write("O ZIP pode conter vários CSVs e, opcionalmente, um arquivo como `data_dictionary.csv`, `dicionario.md` ou `layout.txt`.")
    upload = st.file_uploader("Selecione o ZIP", type=["zip"])
    if upload and st.button("Processar arquivos", type="primary"):
        try:
            st.session_state.dataset = load_zip(upload.getvalue(), upload.name)
            st.session_state.history = []
            st.success("Arquivos carregados e descritos com sucesso.")
        except ValueError as exc:
            st.error(str(exc))

    dataset: LoadedDataset | None = st.session_state.dataset
    if dataset:
        st.dataframe(dataset.summary, use_container_width=True, hide_index=True)
        with st.expander("Dicionário de dados"):
            if dataset.dictionary_table is not None:
                st.dataframe(dataset.dictionary_table, use_container_width=True, hide_index=True)
            else:
                st.code(dataset.dictionary_text or "Nenhum dicionário textual foi identificado; o schema foi inferido dos CSVs.")
        for name, frame in dataset.tables.items():
            with st.expander(f"Prévia — {name}"):
                st.dataframe(frame.head(10), use_container_width=True, hide_index=True)

with query_tab:
    dataset = st.session_state.dataset
    if not dataset:
        st.info("Carregue e processe um ZIP na primeira aba.")
    else:
        st.subheader("Pergunte sobre os dados")
        question = st.text_input(
            "Pergunta em linguagem natural",
            placeholder="Ex.: Quais os 5 emitentes com maior valor total de notas?",
        )
        if st.button("Consultar", type="primary", disabled=not question.strip()):
            try:
                response = LangChainCsvAgent().answer(question, dataset.tables)
                st.session_state.history.append(response)
            except Exception as exc:
                st.error(f"Não foi possível executar a consulta: {exc}")

        for response in reversed(st.session_state.history):
            st.markdown(response.text)
            st.caption(f"Agente: {response.agent_name} | Tabela: {response.plan.table}")
            if not response.data.empty:
                st.dataframe(response.data, use_container_width=True, hide_index=True)
                if response.plan.output_type == "chart" and len(response.data.columns) >= 2:
                    x_column = response.data.columns[0]
                    y_column = response.data.columns[-1]
                    st.plotly_chart(px.bar(response.data, x=x_column, y=y_column), use_container_width=True)
            st.divider()

with evidence_tab:
    st.subheader("Exportar evidências")
    dataset = st.session_state.dataset
    if not dataset:
        st.info("As evidências aparecerão depois do processamento do ZIP.")
    else:
        schema = json.dumps(dataset.schema(), ensure_ascii=False, indent=2)
        st.download_button("Baixar schema.json", schema, file_name="schema.json", mime="application/json")
        history_text = "\n\n".join(
            f"Pergunta: {item.plan.explanation}\nResposta: {item.text}\nPlano: {item.plan.model_dump_json(indent=2)}"
            for item in st.session_state.history
        )
        st.download_button("Baixar histórico.txt", history_text or "Nenhuma consulta executada.", file_name="historico_consultas.txt", mime="text/plain")

st.divider()
st.caption("Arquitetura: Streamlit → agentes LangChain/Local → planos Pydantic → execução segura com Pandas → texto, tabela ou gráfico.")

