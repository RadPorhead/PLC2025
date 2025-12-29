import ply.yacc as yacc
import sys
from analex import tokens, literals
from ast1 import *
from codegen_ewvm import generate_ewvm

precedence = (
    ('left', 'OR'),
    ('left', '+', '-'),
    ('left', '*', '/', 'DIV', 'MOD', 'AND'),
    ('right', 'NOT'),
    ('nonassoc', 'NE', 'LE', 'GE', 'LT', 'GT'),
)

#
# PROGRAMA
#

def p_program(p):
    """
    program : program_heading ';' block '.'
    """
    name, params = p[1]
    p[0] = Program(name, params, p[3])

def p_program_heading(p):
    """
    program_heading : PROGRAM ID '(' id_list ')'
                    | PROGRAM ID
    """
    if len(p) == 6:
        p[0] = (p[2], p[4])
    else:
        p[0] = (p[2], [])


#
# BLOCO
#

def p_block(p):
    """
    block : const_part procfunc_part var_part compound_statement
    """
    p[0] = Block(p[1], p[2], p[3], p[4])


#
# CONSTANTES
#

def p_const_part(p):
    """
    const_part :
               | CONST const_list
    """
    p[0] = [] if len(p) == 1 else p[2]

def p_const_list(p):
    """
    const_list : const_def ';'
               | const_list const_def ';'
    """
    if len(p) == 3:
        p[0] = [p[1]]
    else:
        p[0] = p[1] + [p[2]]

def p_const_def(p):
    """
    const_def : ID '=' constant
    """
    p[0] = ConstDecl(p[1], p[3])

def p_constant(p):
    """
    constant : sign INT
             | INT
             | sign REAL
             | REAL
             | CHAR
             | STRING
             | ID
    """

    if len(p) == 3:
        sign = -1 if p[1] == '-' else 1
        p[0] = Literal(sign * p[2])
    elif isinstance(p[1], str) and p[1].upper() == 'TRUE':
        p[0] = Literal(True)
    elif isinstance(p[1], str) and p[1].upper() == 'FALSE':
        p[0] = Literal(False)
    elif p.slice[1].type == 'ID': 
        p[0] = VarAccess(p[1], [])
    else:
        p[0] = Literal(p[1])

# p.slice dá coisas do tipo [constant, LexToken(ID,'Max',5,56)]

def p_sign(p):
    """
    sign : '+'
         | '-'
    """
    p[0] = p[1]


#
# VARIÁVEIS
#

def p_var_part(p):
    """
    var_part :
             | VAR var_list
    """
    p[0] = [] if len(p) == 1 else p[2]

def p_var_list(p):
    """
    var_list : var_dec ';'
             | var_list var_dec ';'
    """
    if len(p) == 3:
        p[0] = [p[1]]
    else:
        p[0] = p[1] + [p[2]]

def p_var_dec(p):
    """
    var_dec : id_list ':' tipo
    """
    p[0] = VarDecl(p[1], p[3])

def p_id_list(p):
    """
    id_list : ID
            | ID ',' id_list
    """
    p[0] = [p[1]] if len(p) == 2 else [p[1]] + p[3]


#
# TIPOS
#

def p_tipo(p):
    """
    tipo : ID
         | new_type
    """
    if isinstance(p[1], str):
        p[0] = Type(p[1])
    else:
        p[0] = p[1]

def p_new_type(p):
    """
    new_type : enumerated_type
             | subrange_type
             | array_type
    """
    p[0] = p[1]

def p_enumerated_type(p):
    """
    enumerated_type : '(' id_list ')'
    """
    p[0] = EnumeratedType(p[2])

def p_subrange_type(p):
    """
    subrange_type : constant DOTDOT constant
    """
    p[0] = SubrangeType(p[1], p[3])

def p_array_type(p):
    """
    array_type : ARRAY '[' ordinal_type_list ']' OF tipo
    """
    p[0] = ArrayType(p[3], p[6])

def p_ordinal_type(p):
    """
    ordinal_type : enumerated_type
                 | subrange_type
                 | ID
    """
    p[0] = p[1]

def p_ordinal_type_list(p):
    """
    ordinal_type_list : ordinal_type
                      | ordinal_type_list ',' ordinal_type
    """
    p[0] = [p[1]] if len(p) == 2 else p[1] + [p[3]]


#
# PROCEDURES E FUNCTIONS
#

def p_procfunc_part(p):
    """
    procfunc_part :
                  | procfunc_part proc_dec
                  | procfunc_part func_dec
    """
    if len(p) == 1:
        p[0] = []
    else:
        p[0] = p[1] + [p[2]]

def p_proc_dec(p):
    """
    proc_dec : proc_heading ';' block ';'
    """
    name, params = p[1]
    p[0] = Proc(name, params, p[3])

def p_func_dec(p):
    """
    func_dec : func_heading ';' block ';'
    """
    name, params, rettype = p[1]
    p[0] = Func(name, params, rettype, p[3])

def p_proc_heading(p):
    """
    proc_heading : PROCEDURE ID
                 | PROCEDURE ID '(' param_list ')'
    """
    if len(p) == 3:
        p[0] = (p[2], [])
    else:
        p[0] = (p[2], p[4])

def p_func_heading(p):
    """
    func_heading : FUNCTION ID ':' ID
                 | FUNCTION ID '(' param_list ')' ':' ID
    """
    if len(p) == 5:
        p[0] = (p[2], [], Type(p[4]))
    else:
        p[0] = (p[2], p[4], Type(p[7]))

def p_param_list(p):
    """
    param_list : param
               | param_list ';' param
    """
    if len(p) == 2:
        p[0] = [p[1]]
    else:
        p[0] = p[1] + [p[3]]

def p_param(p):
    """
    param : id_list ':' ID
          | VAR id_list ':' ID
    """

    if isinstance(p[1], str) and p[1].upper() == 'VAR':
        p[0] = Param(p[2], Type(p[4]), byref=True)
    else:
        p[0] = Param(p[1], Type(p[3]))


#
# ACESSO A VARIÁVEIS
#

def p_var_access(p):
    """
    var_access : ID var_suffix
    """
    p[0] = VarAccess(p[1], p[2])

def p_var_suffix(p):
    """
    var_suffix :
               | '[' expr_list ']' var_suffix
    """
    if len(p) == 1:
        p[0] = []
    else:
        p[0] = [p[2]] + p[4]


#
# EXPRESSÕES
#

def p_expr_list(p):
    """
    expr_list : expr
              | expr_list ',' expr
    """
    p[0] = [p[1]] if len(p) == 2 else p[1] + [p[3]]

def p_expr(p):
    """
    expr : simple_expr
         | simple_expr relation_op simple_expr
    """
    if len(p) == 2:
        p[0] = p[1]
    else:
        p[0] = BinOp(p[2], p[1], p[3])

def p_simple_expr(p):
    """
    simple_expr : term term_sequence
                | sign term term_sequence
    """
    if len(p) == 3:
        expr = p[1]
        seq = p[2]
        p[0] = expr if not seq else seq[0](expr)
    else:
        expr = UnOp(p[1], p[2])
        seq = p[3]
        p[0] = expr if not seq else seq[0](expr)

def p_term(p):
    """
    term : factor factor_sequence
    """
    base = p[1]
    seq = p[2]
    p[0] = base if not seq else seq[0](base)

def p_term_sequence(p):
    """
    term_sequence :
                  | add_op term term_sequence
    """
    if len(p) == 1:
        p[0] = []
    else:
        op = p[1]
        right = p[2]
        rest = p[3]

        def builder(left):
            expr = BinOp(op, left, right)
            return expr if not rest else rest[0](expr)

        p[0] = [builder]

def p_factor_sequence(p):
    """
    factor_sequence :
                    | mul_op factor factor_sequence
    """
    if len(p) == 1:
        p[0] = []
    else:
        op = p[1]
        right = p[2]
        rest = p[3]

        def builder(left):
            expr = BinOp(op, left, right)
            return expr if not rest else rest[0](expr)

        p[0] = [builder]

def p_factor(p):
    """
    factor : var_access
           | INT
           | REAL
           | CHAR
           | STRING
           | ID '(' expr_list ')'
           | '(' expr ')'
           | NOT factor
           | TRUE
           | FALSE
    """
    if len(p) > 2:
        if p[1] == '(':
            p[0] = p[2]
        elif isinstance(p[1], str) and p[1].upper() == 'NOT':
            p[0] = UnOp('NOT', p[2])
        else:
            p[0] = Call(p[1], p[3])
            
    else:
        if isinstance(p[1], VarAccess):
            p[0] = p[1]
        else:
            p[0] = Literal(p[1])

def p_add_op(p):
    """
    add_op : '+'
           | '-'
           | OR
    """
    p[0] = p[1]

def p_mul_op(p):
    """
    mul_op : '*'
           | '/'
           | DIV
           | MOD
           | AND
    """
    p[0] = p[1]

def p_relation_op(p):
    """
    relation_op : '='
                | NE
                | LT
                | GT
                | LE
                | GE
    """
    p[0] = p[1]


#
# INSTRUÇÕES
#

def p_compound_statement(p):
    """
    compound_statement : BEGIN statement_list END
    """
    p[0] = CompoundStatement(p[2])

def p_statement_list(p):
    """
    statement_list : statement
                   | statement_list ';' statement
    """
    p[0] = [p[1]] if len(p) == 2 else p[1] + [p[3]]

def p_statement(p):
    """
    statement :
              | assignment_statement
              | proc_statement
              | read_statement
              | write_statement
              | labeled_statement
              | compound_statement
              | if_statement
              | while_statement
              | for_statement
    """
    p[0] = p[1] if len(p) == 2 else None

def p_assignment_statement(p):
    """
    assignment_statement : var_access ASSIGN expr
    """
    p[0] = Assign(p[1], p[3])

def p_proc_statement(p):
    """
    proc_statement : ID
                   | ID '(' expr_list ')'
    """
    if len(p) == 2:
        p[0] = Call(p[1], [])
    else:
        p[0] = Call(p[1], p[3])

def p_labeled_statement(p):
    """
    labeled_statement : INT ':' statement
    """
    p[0] = p[3]

def p_read_statement(p):
    """
    read_statement : READ '(' var_access_list ')'
                   | READLN
                   | READLN '(' var_access_list ')'
    """
    if p[1].upper() == 'READ':
        p[0] = Read(p[3])
    else:
        if len(p) == 2:
            p[0] = Read([])
        else:
            p[0] = Read(p[3])

def p_var_access_list(p):
    """
    var_access_list : var_access
                    | var_access_list ',' var_access
    """
    p[0] = [p[1]] if len(p) == 2 else p[1] + [p[3]]

def p_write_statement(p):
    """
    write_statement : WRITE '(' write_list ')'
                    | WRITELN
                    | WRITELN '(' write_list ')'
    """
    if p[1].upper() == 'WRITE':
        p[0] = Write(p[3], newline=False)
    else:
        if len(p) == 2:
            p[0] = Write([], newline=True)
        else:
            p[0] = Write(p[3], newline=True)

def p_write_list(p):
    """
    write_list : write_param
               | write_list ',' write_param
    """
    p[0] = [p[1]] if len(p) == 2 else p[1] + [p[3]]

def p_write_param(p):
    """
    write_param : expr
                | expr ':' expr
                | expr ':' expr ':' expr
    """
    if len(p) == 2:
        p[0] = p[1]
    elif len(p) == 4:
        p[0] = (p[1], p[3])
    else:
        p[0] = (p[1], p[3], p[5])


def p_if_statement(p):
    """
    if_statement : IF expr THEN statement
                 | IF expr THEN statement ELSE statement
    """
    if len(p) == 5:
        p[0] = If(p[2], p[4])
    else:
        p[0] = If(p[2], p[4], p[6])

def p_while_statement(p):
    """
    while_statement : WHILE expr DO statement
    """
    p[0] = While(p[2], p[4])

def p_for_statement(p):
    """
    for_statement : FOR ID ASSIGN expr TO expr DO statement
                  | FOR ID ASSIGN expr DOWNTO expr DO statement
    """
    if p[5].upper() == 'TO':
        p[0] = For(p[2], p[4], p[6], p[8])
    else:
        p[0] = For(p[2], p[4], p[6], p[8], downto=True)


def p_error(p):
    print('Erro sintático:', p)
    parser.success = False


parser = yacc.yacc()
data = sys.stdin.read()
parser.success = True
ast = parser.parse(data)

if parser.success:
    print("Analise sintatica concluida com sucesso.")
    print(generate_ewvm(ast))