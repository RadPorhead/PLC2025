<! compound_statement é um mau nome >

block                   : label_dec const_def_part type_def_part var_dec_part proc_func_dec_part compound_statement 

label_dec               : 
                        | LABEL INT lcont ';'

lcont                   : 
                        | ',' INT lcont


const_def_part          : 
                        | CONST const_def ';' ccont

ccont                   : 
                        | const_def ';' ccont

type_def_part           :
                        | TYPE type_def ';' tcont
                        
tcont                   :
                        | type_def ';' tcont

var_dec_part            :
                        | VAR var_dec ';' vcont

vcont                   :
                        | var_dec ';' vcont

proc_func_dec_part      :
                        | proc_dec ';'
                        | func_dec ';'                        

const_def               : ID '=' constant

constant                : INT
                        | REAL
                        | ID
                        | '+' ID
                        | '-' ID
                        | CHAR

type_def                : ID = tipo <! o livro usa type_denoter em vez de tipo >

tipo                    : ID
                        | new_type

new_type                : enumerated_type
                        | subrange_type
                        | PACKED array_type
                        | array_type

enumerated_type         : '(' id_list ')'

id_list                 : ID
                        | ID ',' id_list

subrange_type           : constant DOTDOT constant

array_type              : ARRAY '['  ordinal_type acont ']' OF tipo

acont                   :
                        | ',' ordinal_type acont

ordinal_type            : enumerated_type
                        | subrange_type
                        | ID

<! falta proc_func_dec_part, compound_statement e falta o que está antes e depois do bloco>

var_dec                 : id_list ':' tipo

var_access              : ID
                        | indexed_var

indexed_var             : var_access '[' expression, expression_sequence ']'

expression_sequence     :
                        | , expression expression_sequence

compound_statement      : BEGIN statement statement_sequence END

statement_sequence      : 
                        | ';' statement statement_sequence

statement               : simple_statement
                        | structured_statement
                        | label ':' structured_statement
                        | label ':' simple_statement

simple_statement        :
                        | assignment_statement
                        | proc_statement
                        | goto_statement

assignment_statement    : variable_access ASSIGN expression
                        | ID ASSIGN expression

proc_statement          : proc_id proc_id_cont

proc_id_cont            : actual_param_list
                        | 
                        | read_param_list
                        | readln_param_list
                        | write_param_list
                        | writeln_param_list
                        

actual_param_list       : '(' actual_param actual_param_cont ')'
                        
actual_param_cont       :
                        | ',' actual_param

actual_param            : expression
                        | variable_access
                        | proc_id
                        | function_id

read_param_list         : '(' var_access var_access_sequence ')'
                        
var_access_sequence     :
                        | ',' var_access var_access_sequence


readln_param_list       :
                        | read_param_list

write_param_list        : '(' var_access write_param_sequence ')'
                        | '(' write_param write_param_sequence ')'

write_param_sequence    :
                        | ',' write_param write_param_sequence


write_param             : expression
                        | expression ':' expression
                        | expression ':' expression ':' expression

writeln_param_list      :
                        | write_param_list

<! Falta expression, variable_access,function_id,structured_statement, proc_dec, func_dec>

goto_statement          : GOTO label