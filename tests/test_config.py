from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from purple_dragon_agent import config

class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.defaults = json.loads(config.DEFAULT_CONFIG.read_text())
    def test_older_config_merges_missing_fields(self):
        result = config.normalize_config({'workspace':'project', 'permissions':{'write_file':'deny'}}, self.defaults)
        self.assertEqual(result['workspace'], 'project')
        self.assertEqual(result['permissions']['write_file'], 'deny')
        self.assertFalse(result['lm_studio']['enabled'])
        self.assertEqual(self.defaults['permissions']['write_file'], 'ask')
    def test_invalid_policy_fails_closed(self):
        result = config.normalize_config({'permissions':{'read_file':['allow']}}, self.defaults)
        self.assertEqual(result['permissions']['read_file'], 'deny')
    def test_invalid_model_settings_rejected(self):
        for value in ({'enabled':'false'}, {'timeout_seconds':0}, {'temperature':3}, {'enabled':True,'endpoint':'https://example.com'}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                config.normalize_config({'lm_studio':value}, self.defaults)
    def test_corrupt_file_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'user.json';path.write_text('{broken')
            with patch.object(config,'USER_CONFIG',path):
                with self.assertRaisesRegex(ValueError,'settings were preserved'):
                    config.load_config()
            self.assertEqual(path.read_text(), '{broken')
    def test_atomic_save_no_temporary_left(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'user.json'
            with patch.object(config,'CONFIG_DIR',Path(temp)),patch.object(config,'USER_CONFIG',path):
                config.save_config(self.defaults)
                self.assertEqual(json.loads(path.read_text()),self.defaults)
                self.assertEqual(list(Path(temp).glob('*.tmp')), [])
