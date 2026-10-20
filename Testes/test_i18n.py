"""Integridade das traduções, persistência do idioma e limites da simulação."""
from pathlib import Path
import string
import sys
import tempfile
import time
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'Windows'))
from rotor_i18n import LANGUAGES, ORDER, TEXT, Translator, flag_image
from rotor_map import SettingsStore
from rotor_pc import DemoLink, PWM_LEVELS, Status


class LanguageAndSpeedTests(unittest.TestCase):
    def test_all_languages_have_matching_format_fields(self):
        formatter=string.Formatter()
        for key,row in TEXT.items():
            self.assertEqual(len(row),len(ORDER),key)
            fields=[{name for _,name,_,_ in formatter.parse(text) if name} for text in row]
            for text,actual in zip(row,fields):
                self.assertTrue(text.strip(),key)
                self.assertEqual(actual,fields[0],key)

    def test_language_persists_without_overwriting_rotor_limit(self):
        with tempfile.TemporaryDirectory() as folder:
            store=SettingsStore(folder)
            settings=store.load()
            self.assertEqual(settings['language'],'pt')
            settings['language']='ru';settings['speed_level']=2
            store.save(settings)
            loaded=store.load()
            self.assertEqual(loaded['language'],'ru')
            self.assertNotIn('speed_level',loaded)
            settings['language']='bad';store.save(settings)
            self.assertEqual(store.load()['language'],'pt')

    def test_flags_and_validation_messages(self):
        for language in LANGUAGES:
            t=Translator(language)
            self.assertEqual(flag_image(language).size,(24,16))
            self.assertEqual(t.error('Grid inválido. Use 2, 4 ou 6 caracteres, como GG66 ou GG66dr.'),t('invalid_grid'))
            self.assertNotIn('informe um número',t.error('Longitude: informe um número de -180 a 180.') if language!='pt' else '')

    def test_demo_honours_all_six_limits(self):
        for level,ceiling in enumerate(PWM_LEVELS,1):
            link=DemoLink();link.send(f'SPEED,{level}')
            link.send('JOG,R');link.command_start=time.monotonic()-4
            link.tick();self.assertEqual(link.pwm,ceiling)
            link.send('STOP');link.send('MOVE,300')
            link.pwm=220;link.tick();self.assertLessEqual(link.pwm,ceiling)

    def test_configuration_telemetry(self):
        state=Status.parse('STAT,120,120,34,5,0,0,NA,0,9')
        self.assertEqual(state.mode,5)
        self.assertEqual(state.reason,9)
