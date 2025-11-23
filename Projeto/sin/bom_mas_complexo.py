import ply.yacc as yacc
import sys
from analex import tokens, literals

precedence = (
    ('left', 'OR'),
    ('left', '+', '-'),
    ('left', '*', '/', 'DIV', 'MOD'),
    ('right', 'NOT'),
    ('nonassoc', 'NE', 'LE', 'GE', '<', '>'),
)


def p_grammar(p):
    """
    program                 : program_heading ';' block '.'

    program_heading         : PROGRAM ID '(' id_list ')'
                            | PROGRAM ID

    block                   : const_def_part proc_func_dec_part var_dec_part compound_statement

    const_def_part          : 
                            | CONST const_def ';' ccont

    ccont                   : 
                            | const_def ';' ccont

    var_dec_part            :
                            | VAR var_dec ';' vcont

    vcont                   :
                            | var_dec ';' vcont

    proc_func_dec_part      :
                            | proc_func_dec_part proc_dec ';'
                            | proc_func_dec_part func_dec ';'                        

    const_def               : ID '=' constant

    sign                    : '+'
                            | '-'

    constant                : sign INT
                            | INT
                            | sign REAL
                            | REAL
                            | ID
                            | sign ID
                            | CHAR
                            | STRING

    tipo                    : ID
                            | new_type

    new_type                : enumerated_type
                            | subrange_type
                            | array_type

    enumerated_type         : '(' id_list ')'

    id_list                 : ID
                            | ID ',' id_list

    subrange_type           : constant DOTDOT constant

    array_type              : ARRAY '[' ordinal_type acont ']' OF tipo

    acont                   :
                            | ',' ordinal_type acont

    ordinal_type            : enumerated_type
                            | subrange_type
                            | ID

    var_dec                 : id_list ':' tipo

    var_access              : ID
                            | var_access '[' expr expr_sequence ']'

    expr_sequence           : 
                            | ',' expr expr_sequence

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
                            | ID actual_param_list
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
                            | '<'
                            | '>'
                            | LE
                            | GE

    compound_statement      : BEGIN statement statement_sequence END

    statement_sequence      : 
                            | ';' statement statement_sequence

    statement               : simple_statement
                            | structured_statement
                            | labeled_statement

    labeled_statement  : INT ':' statement

    simple_statement        :
                            | assignment_statement
                            | proc_statement
                            | read_statement     
                            | write_statement   

    read_statement          : READ read_param_list
                            | READLN
                            | READLN read_param_list

    write_statement         : WRITE writeln_param_list
                            | WRITELN
                            | WRITELN writeln_param_list

    assignment_statement    : var_access ASSIGN expr

    proc_statement          : ID proc_id_cont

    proc_id_cont            : 
                            | actual_param_list

    actual_param_list       : '(' expr expr_sequence ')'

    read_param_list         : '(' var_access var_access_sequence ')'
                            
    var_access_sequence     :
                            | ',' var_access var_access_sequence

    write_param_sequence    :
                            | ',' write_param write_param_sequence

    write_param             : expr
                            | expr ':' expr
                            | expr ':' expr ':' expr

    writeln_param_list      : '(' write_param write_param_sequence ')'

    structured_statement    : compound_statement
                            | if_statement
                            | while_statement
                            | for_statement


    if_statement            : IF expr THEN statement
                            | IF expr THEN statement ELSE statement

    while_statement         : WHILE expr DO statement

    for_statement           : FOR ID ASSIGN expr TO expr DO statement
                            | FOR ID ASSIGN expr DOWNTO expr DO statement

    proc_dec                : proc_heading ';' block
                            | PROCEDURE ID ';' block

    proc_heading            : PROCEDURE ID
                            | PROCEDURE ID formal_param_list

    func_dec                : FUNCTION ID ';' block
                            | func_heading ';' block

    func_heading            : FUNCTION ID ':' ID
                            | FUNCTION ID formal_param_list ':' ID

    formal_param_list       : '(' formal_param_section fcont ')'

    fcont                   : 
                            | ';' formal_param_section fcont

    formal_param_section    : id_list ':' ID
                            | VAR id_list ':' ID
                            | proc_heading
                            | func_heading
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