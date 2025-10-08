
import sys
import re

def tokenize(input_string):
    reconhecidos = []
    mo = re.finditer(r'(?P<SELECT>SELECT)|(?P<WHERE>WHERE)|(?P<var>\?\w+)|(?P<ID>(?:\w+)?:\w+)|(?P<END>\.)|(?P<PA>{)|(?P<PF>})|(?P<SKIP>[ \t])|(?P<NEWLINE>\n)|(?P<ERRO>.)', input_string)
    for m in mo:
        dic = m.groupdict()
        if dic['SELECT']:
            t = ("SELECT", dic['SELECT'], nlinha, m.span())

        elif dic['WHERE']:
            t = ("WHERE", dic['WHERE'], nlinha, m.span())
    
        elif dic['var']:
            t = ("var", dic['var'], nlinha, m.span())
    
        elif dic['ID']:
            t = ("ID", dic['ID'], nlinha, m.span())
    
        elif dic['END']:
            t = ("END", dic['END'], nlinha, m.span())
    
        elif dic['PA']:
            t = ("PA", dic['PA'], nlinha, m.span())
    
        elif dic['PF']:
            t = ("PF", dic['PF'], nlinha, m.span())
    
        elif dic['SKIP']:
            t = ("SKIP", dic['SKIP'], nlinha, m.span())
    
        elif dic['NEWLINE']:
            t = ("NEWLINE", dic['NEWLINE'], nlinha, m.span())
    
        elif dic['ERRO']:
            t = ("ERRO", dic['ERRO'], nlinha, m.span())
    
        else:
            t = ("UNKNOWN", m.group(), nlinha, m.span())
        if not dic['SKIP'] and t[0] != 'UNKNOWN': reconhecidos.append(t)
    return reconhecidos

nlinha = 1
for linha in sys.stdin:
    for tok in tokenize(linha):
        print(tok) 
    nlinha += 1   

