class Node:
    pass

#
# Programa e bloco
#

class Program(Node):
    def __init__(self, name, params, block):
        self.name = name
        self.params = params or []
        self.block = block

class Block(Node):
    def __init__(self, consts, procsfuncs, vars, compound):
        self.consts = consts      # lista de ConstDecl
        self.procsfuncs = procsfuncs  # lista de Proc / Func
        self.vars = vars          # lista de VarDecl
        self.compound = compound  # CompoundStatement


#
# Declarações
#

class ConstDecl(Node):
    def __init__(self, name, value):
        self.name = name
        self.value = value  # Constant node

class VarDecl(Node):
    def __init__(self, names, type_):
        self.names = names      # lista de strings
        self.type = type_       # Type node

class Proc(Node):
    def __init__(self, name, params, block):
        self.name = name
        self.params = params or []
        self.block = block

class Func(Node):
    def __init__(self, name, params, rettype, block):
        self.name = name
        self.params = params or []
        self.rettype = rettype # tipo de retorno da função (procedimentos não têm)
        self.block = block

class Param(Node):
    def __init__(self, names, type_, byref=False):
        self.names = names
        self.type = type_
        self.byref = byref # para parâmetros passados por referência


#
# Tipos
#

class Type(Node):
    def __init__(self, name):
        self.name = name  # ID ou tipo novo

class EnumeratedType(Node):
    def __init__(self, elems):
        self.elems = elems  # lista de IDs

class SubrangeType(Node):
    def __init__(self, low, high):
        self.low = low      # Constant
        self.high = high

class ArrayType(Node):
    def __init__(self, ordinals, elemtype):
        self.ordinals = ordinals      # lista de ordinal_types
        self.elemtype = elemtype      # Type node


#
# Expressões
#

class BinOp(Node):
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right

class UnOp(Node):
    def __init__(self, op, expr):
        self.op = op
        self.expr = expr

class Literal(Node):
    def __init__(self, value):
        self.value = value

class VarAccess(Node):
    def __init__(self, name, suffixes):
        self.name = name
        self.suffixes = suffixes  # lista de expr-lists para índices

class Call(Node):
    def __init__(self, name, args):
        self.name = name
        self.args = args or []


#
# Instruções
#

class CompoundStatement(Node):
    def __init__(self, statements):
        self.statements = statements or []

class Assign(Node):
    def __init__(self, target, expr):
        self.target = target
        self.expr = expr

class If(Node):
    def __init__(self, cond, thenstmt, elsestmt=None):
        self.cond = cond
        self.thenstmt = thenstmt
        self.elsestmt = elsestmt

class While(Node):
    def __init__(self, cond, body):
        self.cond = cond
        self.body = body

class For(Node):
    def __init__(self, var, start, end, body, downto=False):
        self.var = var
        self.start = start
        self.end = end
        self.body = body
        self.downto = downto

class Read(Node):
    def __init__(self, vars):
        self.vars = vars

class Write(Node):
    def __init__(self, params, newline=False):
        self.params = params
        self.newline = newline
