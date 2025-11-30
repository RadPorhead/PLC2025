import ply.yacc as yacc
import sys
from analex import tokens, literals

precedence = (
    ('left', 'OR'),
    ('left', '+', '-'),
    ('left', '*', '/', 'DIV', 'MOD', 'AND'),
    ('right', 'NOT'),
    ('nonassoc', 'NE', 'LE', 'GE', 'LT', 'GT'),
)


def p_grammar(p):
    """
    program                 : program_heading ';' block '.'

    program_heading         : PROGRAM ID '(' id_list ')'
                            | PROGRAM ID

    block                   : const_part procfunc_part var_part compound_statement

    const_part              : 
                            | CONST const_list

    const_list              : const_def ';'
                            | const_list const_def ';' 

    const_def               : ID '=' constant

    constant                : sign INT
                            | INT
                            | sign REAL
                            | REAL
                            | CHAR
                            | STRING
                            | ID

    sign                    : '+'
                            | '-'

    var_part                :
                            | VAR var_list

    var_list                : var_dec ';'
                            | var_list var_dec ';'

    var_dec                 : id_list ':' tipo

    id_list                 : ID
                            | ID ',' id_list

    tipo                    : ID
                            | new_type                       

    new_type                : enumerated_type
                            | subrange_type
                            | array_type

    enumerated_type         : '(' id_list ')'

    subrange_type           : constant DOTDOT constant

    array_type              : ARRAY '[' ordinal_type_list ']' OF tipo

    ordinal_type            : enumerated_type
                            | subrange_type
                            | ID

    ordinal_type_list       : ordinal_type
                            | ordinal_type_list ',' ordinal_type

    procfunc_part           :
                            | procfunc_part proc_dec 
                            | procfunc_part func_dec 

    proc_dec                : proc_heading ';' block ';'

    func_dec                : func_heading ';' block ';'

    proc_heading            : PROCEDURE ID
                            | PROCEDURE ID '(' param_list ')'

    func_heading            : FUNCTION ID ':' ID
                            | FUNCTION ID '(' param_list ')' ':' ID

    param_list              : param
                            | param_list ';' param

    param                   : id_list ':' ID
                            | VAR id_list ':' ID

    var_access              : ID var_suffix
                                             
    var_suffix              : 
                            | '[' expr_list ']' var_suffix

    expr_list               : expr
                            | expr_list ',' expr

    expr                    : simple_expr
                            | simple_expr relation_op simple_expr

    simple_expr             : term term_sequence
                            | sign term term_sequence

    term                    : factor factor_sequence

    term_sequence           :
                            | add_op term term_sequence

    factor                  : var_access
                            | INT
                            | REAL
                            | CHAR
                            | STRING
                            | ID '(' expr_list ')'
                            | '(' expr ')'
                            | NOT factor

    factor_sequence         :
                            | mul_op factor factor_sequence

    add_op                  : '+'
                            | '-'
                            | OR

    mul_op                  : '*'
                            | '/'
                            | DIV
                            | MOD
                            | AND

    relation_op             : '='
                            | NE
                            | LT
                            | GT
                            | LE
                            | GE

    compound_statement      : BEGIN statement_list END

    statement_list          : statement
                            | statement_list ';' statement 

    statement               :
                            | assignment_statement
                            | proc_statement
                            | read_statement     
                            | write_statement 
                            | labeled_statement
                            | compound_statement
                            | if_statement
                            | while_statement
                            | for_statement

    assignment_statement    : var_access ASSIGN expr

    proc_statement          : ID
                            | ID '(' expr_list ')'

    labeled_statement       : INT ':' statement

    read_statement          : READ '(' var_access_list ')'
                            | READLN
                            | READLN '(' var_access_list ')'

    write_statement         : WRITE '(' write_list ')'
                            | WRITELN
                            | WRITELN '(' write_list ')'
                            
    var_access_list         : var_access
                            | var_access_list ',' var_access 

    write_list              : write_param
                            | write_list ',' write_param

    write_param             : expr
                            | expr ':' expr
                            | expr ':' expr ':' expr

    if_statement            : IF expr THEN statement
                            | IF expr THEN statement ELSE statement

    while_statement         : WHILE expr DO statement

    for_statement           : FOR ID ASSIGN expr TO expr DO statement
                            | FOR ID ASSIGN expr DOWNTO expr DO statement
    """

def p_error(p):
    print('Erro sintático:', p)
    parser.success = False

parser = yacc.yacc()

data = sys.stdin.read()
parser.success = True
parser.parse(data)

if parser.success:
    print("Análise sintática concluída com sucesso.")