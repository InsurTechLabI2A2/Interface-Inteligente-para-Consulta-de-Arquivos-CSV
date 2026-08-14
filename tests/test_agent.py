import unittest

import pandas as pd

from src.agent import LocalCsvAgent
from src.data_engine import execute_plan


class LocalCsvAgentTests(unittest.TestCase):
    def setUp(self):
        self.tables = {
            "cabecalho": pd.DataFrame(
                {
                    "CHAVE DE ACESSO": ["A", "B", "C", "D"],
                    "RAZÃO SOCIAL EMITENTE": ["Alfa", "Beta", "Alfa", "Gama"],
                    "VALOR NOTA FISCAL": [100.0, 300.0, 50.0, 200.0],
                    "UF EMITENTE": ["SP", "RJ", "SP", "RJ"],
                    "UF DESTINATÁRIO": ["SP", "SP", "RJ", "RJ"],
                    "CONSUMIDOR FINAL": ["1", "0", "1", "0"],
                    "NATUREZA DA OPERAÇÃO": ["Venda", "Venda", "Devolução", "Venda"],
                    "MUNICÍPIO EMITENTE": ["São Paulo", "Rio", "São Paulo", "Niterói"],
                }
            ),
            "itens": pd.DataFrame(
                {
                    "CHAVE DE ACESSO": ["A", "A", "B", "C", "D", "D"],
                    "CFOP": ["5102", "5102", "6102", "1202", "5102", "6102"],
                    "CÓDIGO NCM/SH": ["1001", "1001", "2002", "1001", "2002", "2002"],
                    "DESCRIÇÃO DO PRODUTO": ["Livro", "Caneta", "Papel", "Livro", "Papel", "Papel"],
                    "QUANTIDADE": [2, 3, 1, 4, 5, 1],
                    "VALOR TOTAL": [20, 30, 100, 40, 200, 50],
                }
            ),
        }

    def test_total_notes_uses_header_and_sum(self):
        answer = LocalCsvAgent().answer("Qual o valor total das notas fiscais?", self.tables)
        self.assertEqual(answer.data.iloc[0]["VALOR NOTA FISCAL"], 650.0)

    def test_count_notes_by_uf_is_distinct(self):
        answer = LocalCsvAgent().answer("Quantas notas fiscais existem por UF do emitente?", self.tables)
        self.assertEqual(answer.plan.group_by, ["UF EMITENTE"])
        self.assertEqual(answer.data.set_index("UF EMITENTE").loc["SP", "Quantidade"], 2)
        self.assertEqual(answer.data.set_index("UF EMITENTE").loc["RJ", "Quantidade"], 2)

    def test_top_five_emitters_respects_limit_and_value(self):
        answer = LocalCsvAgent().answer("Quais os 5 emitentes com maior valor total de notas?", self.tables)
        self.assertEqual(len(answer.data), 3)
        self.assertEqual(answer.data.iloc[0]["RAZÃO SOCIAL EMITENTE"], "Beta")
        self.assertEqual(answer.data.iloc[0]["VALOR NOTA FISCAL"], 300.0)

    def test_average_value_is_scalar(self):
        answer = LocalCsvAgent().answer("Qual a média de valor por nota fiscal?", self.tables)
        self.assertEqual(answer.plan.aggregations[0].function, "avg")
        self.assertAlmostEqual(answer.data.iloc[0, 0], 162.5)

    def test_destination_uf_is_not_recipient_name(self):
        answer = LocalCsvAgent().answer("Qual UF do destinatário recebeu mais notas fiscais?", self.tables)
        self.assertEqual(answer.plan.group_by, ["UF DESTINATÁRIO"])
        self.assertEqual(answer.data.iloc[0]["UF DESTINATÁRIO"], "SP")

    def test_cfop_frequency_counts_item_rows(self):
        answer = LocalCsvAgent().answer("Qual o CFOP mais frequente nas notas?", self.tables)
        self.assertEqual(answer.plan.table, "itens")
        self.assertEqual(answer.data.iloc[0]["CFOP"], "5102")
        self.assertEqual(answer.data.iloc[0]["Quantidade"], 3)

    def test_quantity_by_ncm_sums_quantity(self):
        answer = LocalCsvAgent().answer("Qual a quantidade total por NCM?", self.tables)
        result = answer.data.set_index("CÓDIGO NCM/SH")
        self.assertEqual(result.loc["1001", "QUANTIDADE"], 9)
        self.assertEqual(result.loc["2002", "QUANTIDADE"], 7)

    def test_listing_invoices_keeps_key_and_value(self):
        answer = LocalCsvAgent().answer("Liste as 2 notas fiscais de maior valor.", self.tables)
        self.assertEqual(list(answer.data.columns[:2]), ["CHAVE DE ACESSO", "VALOR NOTA FISCAL"])
        self.assertEqual(list(answer.data["CHAVE DE ACESSO"]), ["B", "D"])


if __name__ == "__main__":
    unittest.main()
