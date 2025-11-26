# codegen_ewvm.py
from collections import OrderedDict
from ast1 import *

# Helper: escape strings for PUSHS/ERR messages
def esc(s):
    return s.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')

class CodeGenError(Exception):
    pass

class CodeGenerator:
    def __init__(self):
        self.code = []              # list[str] - emitted instructions
        self.constants = []         # stored string constants if needed
        self.label_count = 0
        self.procs = OrderedDict()  # name -> label (for user procs)
        # symbol tables (stacked)
        self.global_sym = {}        # name -> {'kind':'var'|'const'|'proc','idx':int,'type':...}
        self.next_gp = 0
        self.current_locals = None  # dict name -> slot index (for current function)
        self.next_local = 0
        self.current_func = None
        self.fixups = []            # tuples for later patching if needed

    # ---------- emission helpers ----------
    def emit(self, instr):
        self.code.append(instr)

    def new_label(self, prefix='L'):
        lab = f"{prefix}{self.label_count}"
        self.label_count += 1
        return lab

    def place_label(self, label):
        # Represent label as "label:" in output
        self.emit(f"{label}:")

    def get_code(self):
        return "\n".join(self.code)

    # ---------- symbol management ----------
    def declare_global_var(self, name, type_=None, is_array=False, array_size=0):
        if name in self.global_sym:
            raise CodeGenError(f"global {name} already declared")
        idx = self.next_gp
        self.next_gp += 1
        self.global_sym[name] = {'kind': 'var', 'idx': idx, 'type': type_, 'is_array': is_array, 'size': array_size}
        # initialize: for arrays allocate heap and store address; for scalars default 0 (PUSHI 0 then STOREG)
        if is_array:
            # allocate array on heap (size = array_size)
            self.emit(f"PUSHI {array_size}")   # size
            self.emit("ALLOCN")                # stacks address
            # store this address into gp[idx]
            self.emit(f"STOREG {idx}")
        else:
            self.emit("PUSHI 0")
            self.emit(f"STOREG {idx}")
        return idx

    def declare_global_const(self, name, literal):
        idx = self.declare_global_var(name, type_=None, is_array=False, array_size=0)
        # overwrite with literal value
        # push literal
        self.push_literal(literal)
        self.emit(f"STOREG {idx}")

    def enter_function(self, name):
        self.current_func = name
        self.current_locals = {}
        self.next_local = 0

    def leave_function(self):
        self.current_func = None
        self.current_locals = None
        self.next_local = 0

    def declare_local_var(self, name, type_=None, is_array=False, array_size=0):
        if self.current_locals is None:
            raise CodeGenError("not inside function when declaring local")
        idx = self.next_local
        self.next_local += 1
        self.current_locals[name] = {'idx': idx, 'type': type_, 'is_array': is_array, 'size': array_size}
        # initialize: scalars default 0 stored in fp[idx]; arrays: ALLOCN and STOREL idx
        if is_array:
            self.emit(f"PUSHI {array_size}")
            self.emit("ALLOCN")
            self.emit(f"STOREL {idx}")
        else:
            self.emit("PUSHI 0")
            self.emit(f"STOREL {idx}")
        return idx

    def lookup_var(self, name):
        # prefer locals, then globals
        if self.current_locals and name in self.current_locals:
            info = self.current_locals[name].copy()
            info['scope'] = 'local'
            return info
        if name in self.global_sym:
            info = self.global_sym[name].copy()
            info['scope'] = 'global'
            return info
        raise CodeGenError(f"undeclared variable {name}")

    # ---------- literal pushing ----------
    def push_literal(self, lit):
        # lit may be int, float, or str
        if isinstance(lit, bool):
            self.emit(f"PUSHI {1 if lit else 0}")
        elif isinstance(lit, int):
            self.emit(f"PUSHI {lit}")
        elif isinstance(lit, float):
            # Use PUSHF for floats
            # Keep full repr
            self.emit(f"PUSHF {repr(lit)}")
        elif isinstance(lit, str):
            # store string in heap and push its address
            # PUSHS string_n : archives s in the String Heap and stacks its address
            # escape quotes and backslashes
            s = lit
            s_escaped = s.replace("'", "''")  # if needed; follow PUSHS conventions (single quotes inside)
            self.emit(f'PUSHS "{s_escaped}"')
        else:
            raise CodeGenError(f"unsupported literal type: {lit!r}")

    # ---------- expression generation ----------
    def gen_expr(self, node):
        # returns nothing but emits instructions which push value onto stack
        if node is None:
            raise CodeGenError("gen_expr got None")
        cls = node.__class__.__name__
        if cls == "Literal":
            self.push_literal(node.value)
        elif cls == "VarAccess":
            self.gen_varaccess_load(node)
        elif cls == "BinOp":
            # generate left then right (note: EWVM binary ops pop n then m and compute m op n)
            # We will push left then right so stack top is right; the instruction semantics described earlier use top as n then m
            # Example: ADD "takes n and m from the pile and stacks the result m + n" => after pushing left then right, ADD works.
            self.gen_expr(node.left)
            self.gen_expr(node.right)
            op = node.op.upper()
            # arithmetic ops and comparison mapping
            if op in ('+', '-', '*', '/'):
                # decide int or float: naive approach, if either operand literal float then float op
                # We can't robustly know; use runtime approach: emit FLOAT ops only if one literal float was present. Simpler: if either operand is Literal float use float op else integer op.
                left_is_float = getattr(node.left, 'value', None) is not None and isinstance(getattr(node.left, 'value'), float)
                right_is_float = getattr(node.right, 'value', None) is not None and isinstance(getattr(node.right, 'value'), float)
                if left_is_float or right_is_float or op == '/':
                    mapping = {'+':'FADD','-':'FSUB','*':'FMUL','/':'FDIV'}
                else:
                    mapping = {'+':'ADD','-':'SUB','*':'MUL','/':'DIV'}
                self.emit(mapping[op])
            elif op in ('DIV','MOD','AND','OR'):
                if op == 'DIV':
                    self.emit("DIV")
                elif op == 'MOD':
                    self.emit("MOD")
                elif op == 'AND':
                    self.emit("AND")
                elif op == 'OR':
                    self.emit("OR")
            elif op in ('=', 'NE', 'LT', 'GT', 'LE', 'GE'):
                # comparisons: map to integer or float variants if possible
                # we use integer ops INF,INFEQ,SUP,SUPEQ or float FINF,...
                left_is_float = isinstance(getattr(node.left, 'value', None), float)
                right_is_float = isinstance(getattr(node.right, 'value', None), float)
                is_float = left_is_float or right_is_float
                if op == '=':
                    self.emit("EQUAL")
                elif op == 'NE':
                    # no direct NE — implement as EQUAL then NOT
                    self.emit("EQUAL")
                    self.emit("NOT")
                elif op == 'LT':
                    self.emit("FINF" if is_float else "INF")
                elif op == 'LE':
                    self.emit("FINFEQ" if is_float else "INFEQ")
                elif op == 'GT':
                    self.emit("FSUP" if is_float else "SUP")
                elif op == 'GE':
                    self.emit("FSUPEQ" if is_float else "SUPEQ")
                else:
                    raise CodeGenError(f"unknown relation {op}")
            else:
                # arithmetic tokens like '+', '-' handled; named tokens OR,AND,DIV handled above; else raise
                raise CodeGenError(f"unsupported binary op {op}")
        elif cls == "UnOp":
            if node.op == 'NOT' or node.op == 'not':
                self.gen_expr(node.expr)
                self.emit("NOT")
            elif node.op in ('+', '-'):
                if node.op == '+':
                    self.gen_expr(node.expr)
                else:  # unary minus -> 0 expr SUB
                    self.emit("PUSHI 0")
                    self.gen_expr(node.expr)
                    self.emit("SUB")
            else:
                # sign used in constants previously
                raise CodeGenError(f"unsupported unary op {node.op}")
        elif cls == "Call":
            # handle builtins: READ/READLN/WRITE/WRITELN/WRITEI/WRITEF/WRITES etc.
            name = node.name.upper()
            if name == 'READ' or name == 'READLN':
                # For READ(varlist): evaluate as READ builtin which returns string address; then convert/store
                # Simpler: for each argument, call READ, then ATOI/ATOF or store string depending on variable type not known -> assume integer
                # We'll perform: for each var: emit READ (reads string), then ATOI, then STORE to variable
                # But READ with no args: call READ builtin and push address
                if len(node.args) == 0:
                    self.emit("READ")
                else:
                    for varnode in node.args:
                        # varnode should be VarAccess
                        # call READ -> pushes address
                        self.emit("READ")
                        # convert to int then store into variable (assume int)
                        self.emit("ATOI")
                        self.store_to_varnode(varnode)
            elif name == 'WRITE' or name == 'WRITELN':
                newline = (name == 'WRITELN')
                if len(node.args) == 0 and newline:
                    self.emit("WRITELN")
                else:
                    for expr in node.args:
                        # expr may be literal or something; push it, then choose write instruction by type
                        # If expr is Literal string -> PUSHS already would have put address
                        # We'll generate code to push expr and then WRITE based on node type
                        self.gen_expr(expr)
                        # decide which write op: if Literal str -> WRITES; if float -> WRITEF; else WRITEI
                        if isinstance(expr, type) and False:
                            pass
                        # crude runtime check: we cannot decide type; use WRITEI for ints, WRITEF for floats, WRITES for string addresses
                        if expr.__class__.__name__ == 'Literal' and isinstance(expr.value, float):
                            self.emit("WRITEF")
                        elif expr.__class__.__name__ == 'Literal' and isinstance(expr.value, str):
                            self.emit("WRITES")
                        else:
                            # default integer write (if it's actually float will probably f int)
                            self.emit("WRITEI")
                    if newline:
                        self.emit("WRITELN")
            else:
                # user-defined procedure/function call
                if name not in self.procs:
                    raise CodeGenError(f"call to undefined procedure {name}")
                label = self.procs[name]
                # push label address and CALL
                self.emit(f"PUSHA {label}")
                self.emit("CALL")
        else:
            raise CodeGenError(f"gen_expr: unhandled node type {cls}")

    # ---------- var access / load / store ----------
    def gen_varaccess_load(self, vnode):
        # vnode.name, vnode.suffixes is list of expr-lists (each suffix is an expr-list used for multi-dimensional)
        info = self.lookup_var(vnode.name)
        if len(vnode.suffixes) == 0:
            # simple scalar or stored address (array base) -> push value
            if info['scope'] == 'global':
                # push value in gp[idx]
                self.emit(f"PUSHG {info['idx']}")
            else:
                self.emit(f"PUSHL {info['idx']}")
        else:
            # array access (one or more indices). We'll support single-dim first and multiple by nested indexing
            # For each index list (we expect one expression per suffix), compute index value then push base address then LOADN
            # Base address: if variable holds address (both global and local store address of heap block), push that
            # For dynamic index, LOADN expects integer n then address a on pile -> it will stack a[n]
            # So we must push index THEN push base address, then LOADN
            # We'll only use the first index for now if multiple (but implement loop)
            # push indexes+base:
            # For nested multi-dim, we compute successive LOADN results as new base if arrays of arrays — simplified approach: use single-level
            # Implementation:
            # push index1 ; push base_address ; LOADN -> pushes value
            # if more indices: treat result as an address and repeat
            is_first = True
            for idx_expr_list in vnode.suffixes:
                # idx_expr_list is a list of expressions (we expect single expr)
                if not isinstance(idx_expr_list, list) or len(idx_expr_list) != 1:
                    raise CodeGenError("only single expression indices supported")
                idx_expr = idx_expr_list[0]
                # compute index (push)
                self.gen_expr(idx_expr)
                # push base address
                if is_first:
                    if info['scope'] == 'global':
                        # push value stored in gp[idx] (which is the base address)
                        self.emit(f"PUSHG {info['idx']}")
                    else:
                        self.emit(f"PUSHL {info['idx']}")
                    is_first = False
                else:
                    # after previous LOADN, top of stack was value; but for nested arrays that value should be an address - we assume it already is.
                    pass
                # now we have index (below) and base address (top) -> LOADN
                self.emit("LOADN")
            # after loop the top of stack is the element value

    def store_to_varnode(self, vnode):
        # expects value already pushed onto stack; will emit store instructions consuming that value
        info = self.lookup_var(vnode.name)
        if len(vnode.suffixes) == 0:
            # scalar store
            if info['scope'] == 'global':
                self.emit(f"STOREG {info['idx']}")
            else:
                self.emit(f"STOREL {info['idx']}")
        else:
            # array element store: expects value v on stack, then need index and base address then STOREN
            # Our calling code currently will have only pushed value; so we need to compute index and base address and reorder.
            # To simplify: the caller should not have pushed value before calling store_to_varnode; instead we will generate code that:
            #   - evaluate value -> leave at top
            #   - evaluate index -> pushes index on top of value -> we need index then address then call STOREN which expects v, n, a
            # Because current code path may push value before calling store_to_varnode, we assume that and generate index and base after it.
            # So stack top now = value, below it other stuff. We'll compute index then push base address. After that, we need the stack to be v, n, a in that order.
            # If we push index (PUSHI/expr) it will be on top -> order becomes v, n. Then push base address -> v, n, a -> perfect for STOREN.
            for idx_expr_list in vnode.suffixes:
                if not isinstance(idx_expr_list, list) or len(idx_expr_list) != 1:
                    raise CodeGenError("only single expression indices supported")
                idx_expr = idx_expr_list[0]
                # generate index (push)
                self.gen_expr(idx_expr)
                # push base address
                info = self.lookup_var(vnode.name)
                if info['scope'] == 'global':
                    self.emit(f"PUSHG {info['idx']}")
                else:
                    self.emit(f"PUSHL {info['idx']}")
                # then STOREN will consume v, n, a
                self.emit("STOREN")

    # ---------- statement generation ----------
    def gen_statement(self, node):
        if node is None:
            return
        cls = node.__class__.__name__
        if cls == "CompoundStatement":
            for s in node.statements:
                self.gen_statement(s)
        elif cls == "Assign":
            # generate expr (push value), then store into var
            self.gen_expr(node.expr)
            # node.target is VarAccess
            self.store_to_varnode(node.target)
        elif cls == "If":
            # generate cond -> pushes integer (0/1)
            self.gen_expr(node.cond)
            lelse = self.new_label("Lelse")
            lend = self.new_label("Lend")
            # if false jump to else
            self.emit(f"JZ {lelse}")
            # then
            self.gen_statement(node.thenstmt)
            self.emit(f"JUMP {lend}")
            # else
            self.place_label(lelse)
            if node.elsestmt:
                self.gen_statement(node.elsestmt)
            self.place_label(lend)
        elif cls == "While":
            lstart = self.new_label("Lwhile_start")
            lend = self.new_label("Lwhile_end")
            self.place_label(lstart)
            self.gen_expr(node.cond)
            self.emit(f"JZ {lend}")
            self.gen_statement(node.body)
            self.emit(f"JUMP {lstart}")
            self.place_label(lend)
        elif cls == "For":
            # for var := start TO/DOWNTO end DO body
            # transform into: assign start; loop label; compare; if false break; body; increment/decrement; jump loop
            varname = node.var
            # ensure var exists - if not, declare as local? We'll require previously declared
            # initialize
            self.gen_expr(node.start)
            # store to var
            self.store_to_varnode(VarAccess(varname, []))
            lloop = self.new_label("Lfor")
            lend = self.new_label("Lfor_end")
            self.place_label(lloop)
            # load var and end and compare
            self.gen_expr(VarAccess(varname, []))
            self.gen_expr(node.end)
            if node.downto:
                # var >= end
                self.emit("SUPEQ")
            else:
                # var <= end
                self.emit("INFEQ")
            self.emit(f"JZ {lend}")  # if condition false jump end
            # body
            self.gen_statement(node.body)
            # increment/decrement var
            # compute new value: load var, push 1, ADD or SUB, then store
            self.gen_expr(VarAccess(varname, []))
            self.emit("PUSHI 1")
            if node.downto:
                self.emit("SUB")
            else:
                self.emit("ADD")
            self.store_to_varnode(VarAccess(varname, []))
            self.emit(f"JUMP {lloop}")
            self.place_label(lend)
        elif cls == "Read":
            # Read(vars) - for each var, perform READ then convert ATOI then store
            for vnode in node.vars:
                self.emit("READ")
                # convert to integer by default
                self.emit("ATOI")
                self.store_to_varnode(vnode)
        elif cls == "Write":
            for param in node.params:
                # param may be expr or list etc; in AST we stored exprs
                self.gen_expr(param)
                # choose write primitive: if Literal string used PUSHS previously and WRITES is correct
                if param.__class__.__name__ == 'Literal' and isinstance(param.value, str):
                    self.emit("WRITES")
                elif param.__class__.__name__ == 'Literal' and isinstance(param.value, float):
                    self.emit("WRITEF")
                else:
                    # default integer
                    self.emit("WRITEI")
            if node.newline:
                self.emit("WRITELN")
        else:
            raise CodeGenError(f"unhandled statement node {cls}")

    # ---------- top-level generation ----------
    def register_proc_label(self, name, label):
        self.procs[name] = label

    def gen_program(self, prog_node):
        # Program(name, params, block)
        # Create entry point label "main" and place START and call block compound code in global init, then jump to main body
        # We'll emit a START then the block's compound statement; procedures/functions will be emitted as separate labeled blocks after main.
        # First: reserve globals from var declarations in block.vars (the AST Block has lists)
        # Process consts
        # consts: list of ConstDecl(name, value)
        for c in prog_node.block.consts or []:
            # push literal value then STOREG into next gp slot
            # but our declare_global_const handles storing value; but it also created gp slot; so do that
            self.declare_global_const(c.name, c.value.value if isinstance(c.value, type(prog_node)) == False else c.value)
        # Process vars global declarations block.vars is list of VarDecl(names, type)
        for vard in prog_node.block.vars or []:
            # vard.names is list of strings; type may be Type or ArrayType etc.
            # if array type: vard.type is ArrayType
            if vard.type.__class__.__name__ == 'ArrayType':
                # for simplicity handle single-dim only and with constant subrange size if possible
                # array_type.ordinals -> list of ordinal_types; we'll try to read first one and compute size from subrange
                array_size = 0
                ordinals = vard.type.ordinals
                if len(ordinals) >= 1:
                    ot = ordinals[0]
                    if ot.__class__.__name__ == 'SubrangeType':
                        low = ot.low.value if hasattr(ot.low, 'value') else None
                        high = ot.high.value if hasattr(ot.high, 'value') else None
                        if low is not None and high is not None:
                            array_size = (high - low) + 1
                    elif ot.__class__.__name__ == 'EnumeratedType':
                        array_size = len(ot.elems)
                if array_size <= 0:
                    raise CodeGenError("unable to determine static array size for global array declaration")
                for name in vard.names:
                    self.declare_global_var(name, type_=vard.type, is_array=True, array_size=array_size)
            else:
                for name in vard.names:
                    self.declare_global_var(name, type_=vard.type, is_array=False)
        # Before emitting main code, register labels for procedures/functions declared in block.procsfuncs
        # We'll first create labels
        for decl in prog_node.block.procsfuncs or []:
            if decl.__class__.__name__ == 'Proc':
                lab = f"proc_{decl.name}"
                self.register_proc_label(decl.name.upper(), lab)
            elif decl.__class__.__name__ == 'Func':
                lab = f"func_{decl.name}"
                self.register_proc_label(decl.name.upper(), lab)
        # Emit program start
        self.emit("START")
        # Emit main program body (compound statement)
        # The Block stores the compound statement in block.compound
        self.gen_statement(prog_node.block.compound)
        # After main finish, add STOP
        self.emit("STOP")
        # Now emit procedures/functions code
        for decl in prog_node.block.procsfuncs or []:
            if decl.__class__.__name__ == 'Proc':
                lab = self.procs[decl.name.upper()]
                self.place_label(lab)
                # function prologue: START? The EWVM protocol: CALL saved pc and fp; when called, fp is set to current sp.
                # On entry, we might not need explicit START; still we can set local state and then generate block code.
                self.enter_function(decl.name)
                # allocate locals from decl.block.var_part if any: but AST Block structure inside decl.block is same Block nodes - use var declarations there
                for vard in decl.block.vars or []:
                    if vard.type.__class__.__name__ == 'ArrayType':
                        # compute array size similar as above
                        array_size = 0
                        ordinals = vard.type.ordinals
                        if len(ordinals) >= 1:
                            ot = ordinals[0]
                            if ot.__class__.__name__ == 'SubrangeType':
                                low = ot.low.value if hasattr(ot.low, 'value') else None
                                high = ot.high.value if hasattr(ot.high, 'value') else None
                                if low is not None and high is not None:
                                    array_size = (high - low) + 1
                            elif ot.__class__.__name__ == 'EnumeratedType':
                                array_size = len(ot.elems)
                        if array_size <= 0:
                            raise CodeGenError("unable to determine static array size for local array")
                        for name in vard.names:
                            self.declare_local_var(name, type_=vard.type, is_array=True, array_size=array_size)
                    else:
                        for name in vard.names:
                            self.declare_local_var(name, type_=vard.type, is_array=False)
                # generate body
                self.gen_statement(decl.block.compound)
                # emit RETURN
                self.emit("RETURN")
                self.leave_function()
            elif decl.__class__.__name__ == 'Func':
                lab = self.procs[decl.name.upper()]
                self.place_label(lab)
                self.enter_function(decl.name)
                # locals
                for vard in decl.block.vars or []:
                    # same logic as above
                    if vard.type.__class__.__name__ == 'ArrayType':
                        array_size = 0
                        ordinals = vard.type.ordinals
                        if len(ordinals) >= 1:
                            ot = ordinals[0]
                            if ot.__class__.__name__ == 'SubrangeType':
                                low = ot.low.value if hasattr(ot.low, 'value') else None
                                high = ot.high.value if hasattr(ot.high, 'value') else None
                                if low is not None and high is not None:
                                    array_size = (high - low) + 1
                            elif ot.__class__.__name__ == 'EnumeratedType':
                                array_size = len(ot.elems)
                        if array_size <= 0:
                            raise CodeGenError("unable to determine static array size for local array")
                        for name in vard.names:
                            self.declare_local_var(name, type_=vard.type, is_array=True, array_size=array_size)
                    else:
                        for name in vard.names:
                            self.declare_local_var(name, type_=vard.type, is_array=False)
                # body
                self.gen_statement(decl.block.compound)
                # proceed with RETURN (assume function value is left on top of stack by user code)
                self.emit("RETURN")
                self.leave_function()

# ---------- convenience API ----------
def generate_ewvm(program_node):
    cg = CodeGenerator()
    cg.gen_program(program_node)
    return cg.get_code()

