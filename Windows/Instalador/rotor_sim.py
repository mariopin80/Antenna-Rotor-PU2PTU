"""Atalho de demonstracao: nunca abre a porta COM nem controla o motor."""
import sys


def main():
    from rotor_pc import main as run
    sys.argv = [sys.argv[0], "--simular"]
    run()
