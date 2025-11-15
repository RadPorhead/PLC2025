import ply.lex as lex
import sys

# Palavras reservadas
reserved = ['AND', 'ARRAY', 'BEGIN', 'CONST', 'DIV', 'DO', 'DOWNTO', 'ELSE', 'END', 'FOR', 'FUNCTION', 'IF', 
            'MOD', 'NOT', 'OF', 'OR', 'PROCEDURE', 'PROGRAM', 'THEN', 'TO', 'VAR', 'WHILE', 'READ', 'READLN', 'WRITE', 'WRITELN']

tokens = [
    'ID', 'INT', 'REAL', 'STRING', 'CHAR', 
    'NE', 'LE', 'GE', 'ASSIGN', 'DOTDOT'
] + reserved

literals = ['+', '-', '*', '/', '=', '<', '>', '[', ']', 
            '.', ',', ':', ';', '(', ')']

t_NE      = r'<>'
t_LE      = r'<='
t_GE      = r'>='
t_ASSIGN  = r':='
t_DOTDOT  = r'\.\.'

t_ignore = ' \t'

def t_COMMENT(t):
    r'(\{[^}]*\})|(\(\*[^*]*\*\))' # Trato os casos {} e (* *)
    pass

def t_REAL(t):
    r'\d+(?:(?:\.\d+(?:[eE][\+\-]?\d+)?)|(?:[eE][\+\-]?\d+))'
    t.value = float(t.value)
    return t

def t_INT(t):
    r'\d+'
    t.value = int(t.value)
    return t

def t_CHAR(t):
    r'\'([^\'\n])\''
    t.value = t.value[1:-1]
    return t

def t_STRING(t):
    r'\'([^\'\n]|\'\')*\''
    t.value = t.value[1:-1].replace("''", "'") # transforma apóstrofos duplicados em apóstrofo único
    return t

def t_ID(t):
    r'[A-Za-z][A-Za-z0-9]*'
    t_upper = t.value.upper()
    t.type = t_upper if t_upper in reserved else 'ID'
    return t

def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)

def t_error(t):
    print(f"Linha {t.lineno}: caractere ilegal '{t.value[0]}'")
    t.lexer.skip(1)

lexer = lex.lex(reflags=lex.re.IGNORECASE) #Pascal é case insensitive