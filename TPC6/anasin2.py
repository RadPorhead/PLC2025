'''
P1: Expr   → Term ExprTail
P2: ExprTail → sum Term ExprTail
P3:           | sub Term ExprTail
P4:           | ε

P5: Term   → Factor TermTail
P6: TermTail → mul Factor TermTail
P7:           | div Factor TermTail
P8:           | ε

P9: Factor → num
P10:        | pa Expr pf
'''

from analex import lexer
import sys

prox_simb = None

def parserError(simb):
    print("Erro sintático, token inesperado: ", simb)

def rec_term(simb):
    global prox_simb
    if prox_simb.type == simb:
        prox_simb = lexer.token()
    else:
        parserError(prox_simb)

'''
P6: TermTail → mul Factor TermTail
P7:           | div Factor TermTail
P8:           | ε
'''

def rec_TermTail():
    global prox_simb
    if prox_simb is not None and prox_simb.type in ['MUL', 'DIV']:
        if prox_simb.type == 'MUL':
            rec_term('MUL')
            rec_Factor()
            rec_TermTail()
            print("Derivando por P6: TermTail → mul Factor TermTail")
        elif prox_simb.type == 'DIV':
            rec_term('DIV')
            rec_Factor()
            rec_TermTail()
            print("Derivando por P7: TermTail → div Factor TermTail")
    elif prox_simb is None or prox_simb.type in ['SUM', 'SUB', 'PF']:
        print("Derivando por P8: TermTail → epsilon")
    else:
        parserError(prox_simb)

#P9: Factor → num
#P10:        | pa Expr pf

def rec_Factor():
    global prox_simb
    if prox_simb.type == 'NUM':
        rec_term('NUM')
        print("Derivando por P9: Factor -> num")
    elif prox_simb.type == 'PA':
        rec_term('PA')
        rec_Expr()
        rec_term('PF')
        print("Derivando por P10: Factor -> pa Expr pf")
    else:
        parserError(prox_simb)

#P5: Term → Factor TermTail
def rec_Term():
    global prox_simb
    if prox_simb.type in ['NUM', 'PA']:
        rec_Factor()
        rec_TermTail()
        print("Derivando por P5: Term → Factor TermTail")
    else:
        parserError(prox_simb)

'''
P2: ExprTail → sum Term ExprTail
P3:           | sub Term ExprTail
P4:           | ε
'''

def rec_ExprTail():
    global prox_simb
    if prox_simb is not None and prox_simb.type in ['SUM', 'SUB']:
        if prox_simb.type == 'SUM':
            rec_term('SUM')
            rec_Term()
            rec_ExprTail()
            print("Derivando por P2: ExprTail → sum Term ExprTail")
        elif prox_simb.type == 'SUB':
            rec_term('SUB')
            rec_Term()
            rec_ExprTail()
            print("Derivando por P3: ExprTail → sub Term ExprTail")
    elif prox_simb is None or prox_simb.type == 'PF':
        print("Derivando por P4: ExprTail → epsilon")
    else:
        parserError(prox_simb)

# P1: Expr   → Term ExprTail

def rec_Expr():
    global prox_simb
    if prox_simb.type in ['NUM', 'PA']:
        rec_Term()
        rec_ExprTail()
        print("Derivando por P1: Expr → Term ExprTail")
    else:
        parserError(prox_simb)

def rec_Parser(data):
    global prox_simb
    lexer.input(data)
    prox_simb = lexer.token()
    rec_Expr()
    print("That's all folks!")


rec_Parser(sys.stdin.read())