import unittest
import parse1c
import os
import config
import models


class TestParse1C(unittest.TestCase):
    def test_dotenv(self):
        self.assertEqual(os.environ.get('TG_TOKEN'), config.Config.TG_TOKEN)

    def test_db(self):
        self.assertTrue(parse1c.session_db.query(models.User).first())
