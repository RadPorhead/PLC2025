# G = (T, N, S, P)
# T = {num , pa, pf, sum, sub, mul, div}
# N = {S, NCont, PaCont, PfCont, MCont}
# S = S

# P1: S -> num NCont
# P2:    | pa PaCont 

# P3: NCont -> sum num NCont
# P4:        | sub num NCont
# P5:        | mul MCont
# P6:        | div MCont
# P7:        | pf PfCont
# P8:        | epsilon

# P9: PaCont -> num NCont

# P10: PfCont -> mul MCont
# P11:         | div MCont
# P12:         | epsilon

# P13: MCont -> pa PaCont
# P14:        | num NCont

from analex import lexer

prox_simb = ('Erro', '', 0, 0)

def parserError(simb):
    print("Erro sintático, token inesperado: ", simb)

def rec_term(simb):
    global prox_simb
    if prox_simb.type == simb:
        prox_simb = lexer.token()
    else:
        parserError(prox_simb)

# P9: PaCont -> num NCont

def rec_PaCont():
    print("Derivando por P9: PaCont -> num NCont")
    rec_term('NUM')
    rec_NCont()
    print("Reconheci P9: PaCont -> num NCont")


# P13: MCont -> pa PaCont
# P14:        | num NCont

def rec_MCont():
    global prox_simb
    if prox_simb.type == 'PA':
        print("Derivando por P13: MCont -> pa PaCont")
        rec_term('PA')
        rec_PaCont()
        print("Reconheci P13: MCont -> pa PaCont")
    elif prox_simb.type == 'NUM':
        print("Derivando por P14: MCont -> num NCont")
        rec_term('NUM')
        rec_NCont()
        print("Reconheci P14: MCont -> num NCont")
    else:
        parserError(prox_simb)

# P10: PfCont -> mul MCont
# P11:         | div MCont
# P12:         | epsilon

def rec_PfCont():
    global prox_simb
    if prox_simb.type == 'MUL':
        print("Derivando por P10: PfCont -> mul MCont")
        rec_term('MUL')
        rec_MCont()
        print("Reconheci P10: PfCont -> mul MCont")
    elif prox_simb.type == 'DIV':
        print("Derivando por P11: PfCont -> div MCont")
        rec_term('DIV')
        rec_MCont()
        print("Reconheci P11: PfCont -> div MCont")
    else:
        print("Derivando por P12: PfCont -> ε")


# P3: NCont -> sum num NCont
# P4:        | sub num NCont
# P5:        | mul MCont
# P6:        | div MCont
# P7:        | pf PfCont
# P8:        | epsilon

def rec_NCont():
    global prox_simb
    if prox_simb.type == 'SUM':
        print("Derivando por P3: NCont -> sum num NCont")
        rec_term('SUM')
        rec_term('NUM')
        rec_NCont()
        print("Reconheci P3: NCont -> sum num NCont")
    elif prox_simb.type == 'SUB':
        print("Derivando por P4: NCont -> sub num NCont")
        rec_term('SUB')
        rec_term('NUM')
        rec_NCont()
        print("Reconheci P4: NCont -> sub num NCont")
    elif prox_simb.type == 'MUL':
        print("Derivando por P5: NCont -> mul MCont")
        rec_term('MUL')
        rec_MCont()
        print("Reconheci P5: NCont -> mul MCont")
    elif prox_simb.type == 'DIV':
        print("Derivando por P6: NCont -> div MCont")
        rec_term('DIV')
        rec_MCont()
        print("Reconheci P6: NCont -> div MCont")
    elif prox_simb.type == 'PF':
        print("Derivando por P7: NCont -> pf PfCont")
        rec_term('PF')
        rec_PfCont()
        print("Reconheci P7: NCont -> pf PfCont")
    else:
        print("Derivando por P8: NCont -> ε")                   

# P1: S -> num NCont
# P2:    | pa PaCont 

def rec_S():
    global prox_simb
    if prox_simb is None:
        parserError("Esperava NUM ou PA, mas input acabou")
        return
    if prox_simb.type == 'NUM':
        print("Derivando por P1: S -> num NCont")
        rec_term('NUM')
        rec_NCont()
        print("Reconheci P1: S -> num NCont")
    elif prox_simb.type == 'PA':
        print("Derivando por P2: S -> pa PaCont")
        rec_term('PA')
        rec_PaCont()
        print("Reconheci P2: S -> pa PaCont")
    else:
        parserError(prox_simb)

def rec_Parser(data):
    global prox_simb
    lexer.input(data)
    prox_simb = lexer.token()
    rec_S()
    print("That's all folks!")


rec_Parser(input("Introduza uma Expressão: "))