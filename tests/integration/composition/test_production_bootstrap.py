import unittest

from app.main import build_application


class ProductionBootstrapTest(unittest.TestCase):
    def test_build_application_wires_runtime_health(self):
        app = build_application()
        health = app.health()
        self.assertTrue(health["runtime"])


if __name__ == "__main__":
    unittest.main()
