import json
import sys
import ply.lex as lex
import re
from datetime import datetime

stock = [
    {"cod": "A01", "nome": "agua 0.5L",       "quant": 10, "preco": 0.70},
    {"cod": "A02", "nome": "refrigerante","quant": 5,  "preco": 1.20},
    {"cod": "A03", "nome": "sumo laranja","quant": 7, "preco": 1.00},
    {"cod": "B01", "nome": "chocolate",    "quant": 15, "preco": 0.90},
    {"cod": "B02", "nome": "barra cereais", "quant": 12, "preco": 1.10},
    {"cod": "C01", "nome": "bolachas",   "quant": 20, "preco": 0.85},
    {"cod": "C02", "nome": "snack salgado", "quant": 8, "preco": 1.50},
    {"cod": "D01", "nome": "cafe 20cl",       "quant": 6, "preco": 1.00},
    {"cod": "D02", "nome": "cha 20cl",        "quant": 10, "preco": 0.80},
]

with open("stock.json", "w") as f:
    json.dump(stock, f, indent=4)

print(f"maq: {str(datetime.today()).split()[0]}, Stock carregado, Estado atualizado.")
print("maq: Bom dia. Estou disponível para atender o seu pedido.")

tokens = (
    'LISTAR',
    'MOEDA',
    'SELECIONAR',
    'SAIR',
    'PONTO'
)

t_ignore = ' \t\n'

def t_LISTAR(t):
    r'LISTAR'
    print("cod  | nome           | quant | preço")
    print("----------------------------------------")
    for item in stock:
        print(f"{item['cod']:<4} | {item['nome']:<14} | {item['quant']:<5} | {item['preco']:.2f}")
    return t

saldo = 0.0

def t_MOEDA(t):
    r'MOEDA[\t ]+(\d+)(e|c)(,\s*\d+(e|c))*'
    global saldo
    m = re.findall(r'(\d+)(e|c)', t.value)
    for tuplo in m:
        if tuplo[1] == 'e':
            saldo += float(tuplo[0])
        else:
            saldo += float(tuplo[0]) / 100

    print(f"maq: Saldo = {int(saldo)}e{int((saldo - int(saldo))*100)}c")
    return t

def t_PONTO(t):
    r'\.'
    return t

def t_SELECIONAR(t):
    r'SELECIONAR[ \t]+[A-Z]\d\d'
    global saldo
    m = re.match(r'SELECIONAR[ \t]+([A-Z]\d\d)', t.value)
    for item in stock:
        if item["cod"] == m.group(1):
            preco = item["preco"]
            if preco > saldo:
                print("maq: Saldo insufuciente para satisfazer o seu pedido")
                print(f"maq: Saldo = {int(saldo)}e{int((saldo - int(saldo))*100)}; Pedido = {int(preco)}e{int((preco - int(preco))*100)}")
            else:
                saldo -= preco
                item["quant"] -= 1
                print(f"maq: Saldo = {int(saldo)}e{int((saldo - int(saldo))*100)}")
    return t

def dar_troco(valor):
    moedas = [200, 100, 50, 20, 10, 5, 2, 1]  # em cêntimos
    troco = []
    restante = round(valor * 100) # saldo em centimos

    for m in moedas:
        qtd = restante // m #quantidade de cada moeda
        if qtd:
            troco.append((qtd, m))
            restante %= m

    partes = []
    for qtd, m in troco:
        if m >= 100:
            partes.append(f"{qtd}x {m//100}e")
        else:
            partes.append(f"{qtd}x {m}c")

    if len(partes) > 1:
        return ", ".join(partes[:-1]) + " e " + partes[-1] 
    else:
        return partes[0] if partes else "sem troco"


def t_SAIR(t):
    r'SAIR'
    if saldo > 0:
        print(f"maq: Pode retirar o troco: {dar_troco(saldo)}.")
    else:
        print("maq: Sem troco.")
    print("maq: Até à próxima")
    return t

def t_error(t):
    print(f"Carácter ilegal {t.value[0]}")
    t.lexer.skip(1)

lexer = lex.lex()

for linha in sys.stdin:
    lexer.input(linha)
    for tok in lexer:
        if tok.type=='SAIR':
            with open("stock.json", "w") as f:
                json.dump(stock, f, indent=4)
            sys.exit()

