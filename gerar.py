"""Gera um Short pela linha de comando.

    .venv\\Scripts\\python gerar.py                       -> canal "escolha_caminho", tema sorteado
    .venv\\Scripts\\python gerar.py --tema "farol isolado"
"""
import argparse

from fabrica.produzir import produzir

p = argparse.ArgumentParser()
p.add_argument("--canal", default="escolha_caminho")
p.add_argument("--tema")
a = p.parse_args()
produzir(a.canal, a.tema)
