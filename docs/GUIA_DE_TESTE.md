# Guia de teste — Desafio 4

## 1. Teste automatizado

Na pasta raiz do projeto, execute:

```powershell
python -m unittest discover -s tests -v
```

O resultado esperado é `OK`, com nove testes aprovados.

## 2. Teste manual com o ZIP de exemplo

1. Gere ou use `sample_data/desafio4_sample.zip`.
2. Execute `streamlit run app.py`.
3. Na aba **Carregar dados**, envie o ZIP.
4. Clique em **Processar arquivos**.
5. Confira duas tabelas, o dicionário e a prévia.
6. Na aba **Consultar**, execute as perguntas abaixo.

Resultados esperados para o ZIP de exemplo:

| Pergunta | Resultado principal |
|---|---|
| Qual o valor total das notas fiscais? | R$ 650,00 |
| Quantas notas fiscais existem por UF do emitente? | SP = 2; RJ = 2 |
| Quais os 5 emitentes com maior valor total de notas? | Beta Indústria em primeiro, R$ 300,00 |
| Qual a média de valor por nota fiscal? | R$ 162,50 |
| Qual UF do destinatário recebeu mais notas fiscais? | RJ, 3 notas |
| Qual o CFOP mais frequente nas notas? | 5102, 3 itens |
| Qual a quantidade total por NCM? | NCM 1001 = 9; NCM 2002 = 7 |
| Liste as 2 notas fiscais de maior valor. | B e D, nesta ordem |

## 3. Teste com os dados reais do curso

Compacte os CSVs de uma das bases recebidas no desafio e faça o mesmo upload. Na base `202401_NFs`, as quatro consultas mínimas verificadas foram:

- total das notas: **R$ 3.371.754,84**;
- maior emitente por valor: **CHEMYUNION LTDA**, **R$ 1.292.418,75**;
- UF do destinatário com mais notas: **DF**, **26 notas**;
- maior NCM por quantidade: **49019900**, **68.684 unidades**.

## 4. Teste opcional com LangChain/Anthropic

1. Copie `.env.example` para `.env`.
2. Preencha `ANTHROPIC_API_KEY` com uma chave válida.
3. Execute a aplicação normalmente.
4. Faça uma pergunta e verifique na legenda se o agente LangChain foi utilizado.

Se a chave estiver ausente, inválida ou sem rede, a consulta deve continuar funcionando em modo offline local. Isso é intencional e permite a validação do MVP sem expor segredo no código.

## 5. Critérios de aceite

- o ZIP é aceito e os CSVs aparecem na prévia;
- o dicionário é exibido ou o schema é inferido;
- pelo menos quatro perguntas retornam valores verificáveis;
- respostas podem aparecer como texto, tabela e gráfico;
- o histórico pode ser exportado;
- nenhum código arbitrário gerado pelo modelo é executado.

