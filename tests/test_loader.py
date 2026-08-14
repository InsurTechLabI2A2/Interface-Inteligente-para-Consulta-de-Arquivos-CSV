import io
import unittest
from zipfile import ZipFile

from src.csv_loader import load_zip


class ZipLoaderTests(unittest.TestCase):
    def test_loads_csv_and_dictionary_from_zip(self):
        buffer = io.BytesIO()
        with ZipFile(buffer, "w") as archive:
            archive.writestr("dados.csv", "id;valor\n1;10,50\n")
            archive.writestr("data_dictionary.csv", "campo;descricao\nid;Identificador\n")
        dataset = load_zip(buffer.getvalue(), "fixture.zip")
        self.assertEqual(list(dataset.tables), ["dados"])
        self.assertIsNotNone(dataset.dictionary_table)
        self.assertEqual(dataset.tables["dados"].iloc[0]["valor"], "10,50")


if __name__ == "__main__":
    unittest.main()
