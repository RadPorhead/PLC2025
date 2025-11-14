# Diferenças em relação ao livro
```
statement-part = compound_statement

constant-identier = ID

type-denoter = tipo

new-ordinal-type = enumerated_type | subrange_type
new-structured-type = PACKED? array_type

unpacked-structured-type = array_type

index-type = ordinal_type

component-type = tipo

simple-type-identifier = ID
structured-type-identifier = ID 
type-identifier = ID

simple-type = enumerated_type | subrange_type | ID
ordinal-type-identifier = ID
real-type-identifier = ID

structured-type = PACKED? array_type | ID

index-type = ordinal_type
component-type = tipo

variable-access = ID | indexed_var

entire-variable = ID
variable-identifier = ID

component-variable = indexed_var
array-variable = var_access
index-expression = expression

file-variable = variable-access


```

# Coisas ignoradas
- new-pointer-type
- record-type 
- set-type
- file-type
- pointer-type-identifier
- field-designator
- identified-variable
- buffer_variable

