# codegen_ewvm.py

from typing import List, Dict, Tuple, Optional
from ast1 import *

# Gera rótulos únicos
class LabelGen:
    def __init__(self):
        self.counter = 0
    def new(self, base='L'):
        lbl = f"{base.upper()}{self.counter}"
        self.counter += 1
        return lbl

class CodeGenerator:
    def __init__(self):
        self.code: List[str] = []
        self.postamble: List[str] = []
        self.labelgen = LabelGen()

        # símbolos
        self.globals: Dict[str, Dict] = {}
        self.current_locals: Dict[str, Dict] = {}
        self.local_frames: List[Dict[str, Dict]] = []

        # funções: name -> label
        self.func_labels: Dict[str, str] = {}

        # ponteiros de alocação
        self.next_gp = 0
        self.next_local = 0

    # --- utilitários de emissão
    def emit(self, instr: str):
        self.code.append(instr)

    def emit_post(self, instr: str):
        self.postamble.append(instr)

    def new_label(self, base='L'):
        return self.labelgen.new(base)

    # --- alocação de memória para variáveis (suporta arrays com SubrangeType)
    def size_of_type(self, type_node):
        if type(type_node).__name__ == 'Type':
            return 1
        elif type(type_node).__name__ == 'ArrayType':
            prod = 1
            for ordinal in type_node.ordinals:
                if type(ordinal).__name__ == 'SubrangeType':
                    low = ordinal.low.value if isinstance(ordinal.low, Literal) else None
                    high = ordinal.high.value if isinstance(ordinal.high, Literal) else None
                    if low is None or high is None:
                        raise NotImplementedError("Array com limites não-constantes não suportado (ainda).")
                    prod *= (high - low + 1)
                else:
                    raise NotImplementedError("Array com ordinal não-subrange não suportado (ainda).")
            elem_size = self.size_of_type(type_node.elemtype)
            return prod * elem_size
        elif type(type_node).__name__ == 'SubrangeType':
            return 1
        else:
            return 1

    def allocate_globals(self, var_decls: List[VarDecl]):
        for vdecl in var_decls:
            tnode = vdecl.type
            size_per_name = self.size_of_type(tnode)
            for name in vdecl.names:
                if name in self.globals:
                    raise Exception(f"Variável global repetida: {name}")
                self.globals[name] = {'idx': self.next_gp, 'size': size_per_name, 'type': tnode}
                self.next_gp += size_per_name

    # frames para funções
    def enter_frame(self):
        self.current_locals = {}
        self.local_frames.append(self.current_locals)
        self.next_local = 0

    def exit_frame(self):
        self.local_frames.pop()
        self.current_locals = self.local_frames[-1] if self.local_frames else {}
        self.next_local = len(self.current_locals)

    def allocate_local(self, name, type_node=None, size=None):
        sz = size if size is not None else (self.size_of_type(type_node) if type_node else 1)
        idx = self.next_local
        self.current_locals[name] = {'idx': idx, 'size': sz, 'type': type_node}
        self.next_local += sz
        return idx

    # localizar variável (resolva gp / fp / param_byref)
    def lookup_var(self, name) -> Tuple[str, int, Dict]:
        if name in self.current_locals:
            meta = self.current_locals[name]
            return ('fp', meta['idx'], meta)
        if name in self.globals:
            meta = self.globals[name]
            return ('gp', meta['idx'], meta)
        # criar global automaticamente (pragmático)
        self.globals[name] = {'idx': self.next_gp, 'size': 1, 'type': None}
        self.next_gp += 1
        return ('gp', self.globals[name]['idx'], self.globals[name])

    # ----------------------
    # inferência de tipo (agora método da classe)
    # ----------------------
    def infer_type(self, expr):
        if expr is None:
            return None

        # Literais
        if isinstance(expr, Literal):
            v = expr.value
            if isinstance(v, bool):
                return "int"
            if isinstance(v, int):
                return "int"
            if isinstance(v, float):
                return "float"
            if isinstance(v, str):
                return "string"
            return None

        # Acesso a variável
        if isinstance(expr, VarAccess):
            storage, idx, meta = self.lookup_var(expr.name)
            t = meta.get('type')
            if isinstance(t, Type):
                name = t.name.upper()
                if name in ("INTEGER", "INT"):
                    return "int"
                if name in ("REAL", "FLOAT"):
                    return "float"
                if name == "STRING":
                    return "string"
            # arrays -> o tipo relevante pode ser elemtype se houver sufixes,
            # mas aqui sem contexto devolvemos tipo do identificador
            return None

        # Operadores binários
        if isinstance(expr, BinOp):
            lt = self.infer_type(expr.left)
            rt = self.infer_type(expr.right)
            # comparadores produzem boolean (mapeado para int)
            if expr.op in ('=', '<', '>', '<=', '>=', '<>'):
                return "int"
            # se qualquer lado for float -> float
            if lt == "float" or rt == "float":
                return "float"
            # fallback inteiro
            return "int"

        # UnOp herda tipo do operando
        if isinstance(expr, UnOp):
            return self.infer_type(expr.expr)

        # chamadas: desconhecido sem tabela de símbolos de funções
        if isinstance(expr, Call):
            return None

        return None

    # -------------
    # geração top-level
    # -------------
    def generate_program(self, program: Program) -> str:
        self.emit("START")
        self.allocate_globals(program.block.vars)
        for decl in program.block.procsfuncs:
            if isinstance(decl, Proc) or isinstance(decl, Func):
                self.func_labels[decl.name] = f"FUNC{decl.name}"
        self.generate_block(program.block, is_main=True)
        self.emit("STOP")
        self.code += self.postamble
        return "\n".join(self.code)

    def generate_block(self, block: Block, is_main=False):
        if not is_main:
            self.enter_frame()
            for vdecl in block.vars:
                for name in vdecl.names:
                    self.allocate_local(name, vdecl.type)
        else:
            pass

        for decl in block.procsfuncs:
            if isinstance(decl, Proc) or isinstance(decl, Func):
                self.func_labels[decl.name] = f"FUNC{decl.name}"

        self.generate_statement(block.compound)

        for decl in block.procsfuncs:
            if isinstance(decl, Proc):
                self.generate_proc(decl)
            elif isinstance(decl, Func):
                self.generate_func(decl)

        if not is_main:
            self.exit_frame()

    # ----------------------------------------------------
    # procedures / functions
    # ----------------------------------------------------
    def generate_proc(self, proc: Proc):
        lbl = self.func_labels.get(proc.name, f"FUNC{proc.name}")
        self.emit_post(f"{lbl}:")
        self.enter_frame()
        params = proc.params or []
        for p in params:
            for name in p.names:
                self.allocate_local(name, p.type)
                self.current_locals[name]['byref'] = getattr(p, 'byref', False)
        for vdecl in proc.block.vars:
            for name in vdecl.names:
                self.allocate_local(name, vdecl.type)
        for p in reversed(params):
            for name in reversed(p.names):
                meta = self.current_locals[name]
                idx = meta['idx']
                self.emit(f"STOREL {idx}")
        self.generate_statement(proc.block.compound)
        self.emit_post("RETURN")
        self.exit_frame()

    def generate_func(self, func: Func):
        lbl = self.func_labels.get(func.name, f"FUNC_{func.name}")
        self.emit_post(f"{lbl}:")
        self.enter_frame()
        params = func.params or []
        for p in params:
            for name in p.names:
                self.allocate_local(name, p.type)
                self.current_locals[name]['byref'] = getattr(p, 'byref', False)
        for vdecl in func.block.vars:
            for name in vdecl.names:
                self.allocate_local(name, vdecl.type)
        for p in reversed(params):
            for name in reversed(p.names):
                meta = self.current_locals[name]
                self.emit(f"STOREL {meta['idx']}")
        self.generate_statement(func.block.compound)
        self.emit_post("RETURN")
        self.exit_frame()

    # ---------------------
    # Statements
    # ---------------------
    def generate_statement(self, stmt):
        if stmt is None:
            return
        t = type(stmt).__name__
        if t == "CompoundStatement":
            for s in stmt.statements:
                self.generate_statement(s)
        elif t == "Assign":
            self.generate_expr(stmt.expr)
            target = stmt.target
            if not isinstance(target, VarAccess):
                raise Exception("Assign target inesperado")
            if target.suffixes:
                self.generate_store_to_array(target)
            else:
                storage, idx, meta = self.lookup_var(target.name)
                if meta.get('byref', False):
                    self.emit(f"PUSHL {idx}")
                    self.emit("STOREN")
                else:
                    if storage == 'gp':
                        self.emit(f"STOREG {idx}")
                    else:
                        self.emit(f"STOREL {idx}")
        elif t == "If":
            else_lbl = self.new_label("else")
            end_lbl = self.new_label("ifend")
            self.generate_expr(stmt.cond)
            self.emit(f"JZ {else_lbl}")
            self.generate_statement(stmt.thenstmt)
            self.emit(f"JUMP {end_lbl}")
            self.emit(f"{else_lbl}:")
            if stmt.elsestmt:
                self.generate_statement(stmt.elsestmt)
            self.emit(f"{end_lbl}:")
        elif t == "While":
            start = self.new_label("whilestart")
            end = self.new_label("whileend")
            self.emit(f"{start}:")
            self.generate_expr(stmt.cond)
            self.emit(f"JZ {end}")
            self.generate_statement(stmt.body)
            self.emit(f"JUMP {start}")
            self.emit(f"{end}:")
        elif t == "For":
            varname = stmt.var
            self.generate_expr(stmt.start)
            storage, idx, meta = self.lookup_var(varname)
            if storage == 'gp':
                self.emit(f"STOREG {idx}")
            else:
                self.emit(f"STOREL {idx}")
            start_lbl = self.new_label("forstart")
            end_lbl = self.new_label("forend")
            self.emit(f"{start_lbl}:")
            if storage == 'gp':
                self.emit(f"PUSHG {idx}")
            else:
                self.emit(f"PUSHL {idx}")
            self.generate_expr(stmt.end)
            if stmt.downto:
                self.emit("SUPEQ")
            else:
                self.emit("INFEQ")
            self.emit(f"JZ {end_lbl}")
            self.generate_statement(stmt.body)
            if storage == 'gp':
                self.emit(f"PUSHG {idx}")
            else:
                self.emit(f"PUSHL {idx}")
            self.emit("PUSHI 1")
            if stmt.downto:
                self.emit("SUB")
            else:
                self.emit("ADD")
            if storage == 'gp':
                self.emit(f"STOREG {idx}")
            else:
                self.emit(f"STOREL {idx}")
            self.emit(f"JUMP {start_lbl}")
            self.emit(f"{end_lbl}:")
        elif t == "Read":
            for v in stmt.vars:
                self.emit("READ")
                storage, idx, meta = self.lookup_var(v.name)
                tdecl = meta.get('type')
                if v.suffixes and isinstance(tdecl, ArrayType):
                    tdecl = tdecl.elemtype
                if tdecl and hasattr(tdecl, 'name') and tdecl.name.upper() in ('REAL', 'FLOAT'):
                    # ler string -> converter para float via ATOI+ITOF não é ideal; mantemos ATOI se a implementação da VM for esta.
                    self.emit("ATOI")
                    self.emit("ITOF")
                else:
                    self.emit("ATOI")
                if v.suffixes:
                    self.generate_store_to_array(v)
                else:
                    if storage == 'gp':
                        self.emit(f"STOREG {idx}")
                    else:
                        self.emit(f"STOREL {idx}")
        elif t == "Write":
            for wp in stmt.params:
                width = None; prec = None
                expr = None
                if isinstance(wp, tuple):
                    if len(wp) == 2:
                        expr, width = wp
                    elif len(wp) == 3:
                        expr, width, prec = wp
                else:
                    expr = wp
                self.generate_expr(expr)
                itype = self.infer_type(expr)
                if itype == "float":
                    self.emit("WRITEF")
                elif itype == "string":
                    self.emit("WRITES")
                else:
                    self.emit("WRITEI")
            if stmt.newline:
                self.emit("WRITELN")
        else:
            raise NotImplementedError(f"Statement não suportado: {t}")

    # ---------------------
    # Expressões
    # ---------------------
    def generate_expr(self, expr):
        if expr is None:
            return
        t = type(expr).__name__
        if t == "Literal":
            v = expr.value
            if isinstance(v, bool):
                self.emit(f"PUSHI {1 if v else 0}")
            elif isinstance(v, int):
                self.emit(f"PUSHI {v}")
            elif isinstance(v, float):
                # representar floats com ponto
                self.emit(f"PUSHF {v}")
            elif isinstance(v, str):
                if v.upper() == 'TRUE':
                    self.emit("PUSHI 1")
                elif v.upper() == 'FALSE':
                    self.emit("PUSHI 0")
                else:
                    s = v.replace('"', '\\"')
                    self.emit(f'PUSHS "{s}"')
            else:
                raise NotImplementedError("Literal tipo não suportado.")
        elif t == "VarAccess":
            if expr.suffixes:
                self.generate_load_from_array(expr)
            else:
                storage, idx, meta = self.lookup_var(expr.name)
                if meta.get('byref', False):
                    self.emit(f"PUSHL {idx}")
                    self.emit("LOADN")
                else:
                    if storage == 'gp':
                        self.emit(f"PUSHG {idx}")
                    else:
                        self.emit(f"PUSHL {idx}")
        elif t == "BinOp":
            self.generate_expr(expr.left)
            self.generate_expr(expr.right)
            op = expr.op
            ltype = self.infer_type(expr.left) or "int"
            rtype = self.infer_type(expr.right) or "int"
            use_float = (ltype == "float" or rtype == "float")
            if op == '+':
                self.emit("FADD" if use_float else "ADD")
            elif op == '-':
                self.emit("FSUB" if use_float else "SUB")
            elif op == '*':
                self.emit("FMUL" if use_float else "MUL")
            elif op == '/':
                # em Pascal '/' é divisão real
                if use_float:
                    self.emit("FDIV")
                else:
                    self.emit("DIV")
            elif op.upper() == 'DIV':
                self.emit("DIV")
            elif op.upper() == 'MOD':
                self.emit("MOD")
            elif op == '=':
                self.emit("EQUAL")
            elif op == '<':
                self.emit("INF")
            elif op == '<=':
                self.emit("INFEQ")
            elif op == '>':
                self.emit("SUP")
            elif op == '>=':
                self.emit("SUPEQ")
            elif op.upper() == 'AND':
                self.emit("AND")
            elif op.upper() == 'OR':
                self.emit("OR")
            else:
                raise NotImplementedError(f"Operador binário não suportado: {op}")
        elif t == "UnOp":
            op = expr.op
            if op == '+' or op == '-':
                if op == '+':
                    self.generate_expr(expr.expr)
                else:
                    self.emit("PUSHI 0")
                    self.generate_expr(expr.expr)
                    self.emit("SUB")
            elif op.upper() == 'NOT':
                self.generate_expr(expr.expr)
                self.emit("NOT")
            else:
                raise NotImplementedError(f"UnOp não suportado: {op}")
        elif t == "Call":
            func_label = self.func_labels.get(expr.name, f"FUNC_{expr.name}")
            for arg in expr.args:
                # simplificação: empilha valores (byval). byref exige convenção com assinatura.
                self.generate_expr(arg)
            self.emit(f"PUSHA {func_label}")
            self.emit("CALL")
        else:
            raise NotImplementedError(f"Expr tipo não suportado: {t}")

    # ---------------------------
    # Array helpers (load/store)
    # ---------------------------
    def generate_load_from_array(self, varaccess: VarAccess):
        storage, base_idx, meta = self.lookup_var(varaccess.name)
        arr_type = meta.get('type')
        if not arr_type or type(arr_type).__name__ != 'ArrayType':
            raise Exception("Acesso a array mas o tipo não é ArrayType conhecido.")

        if storage == 'gp':
            self.emit("PUSHGP")
            self.emit(f"PUSHI {base_idx}")
            self.emit("PADD")
        else:
            self.emit("PUSHFP")
            self.emit(f"PUSHI {base_idx}")
            self.emit("PADD")

        dims = arr_type.ordinals
        sizes = []
        for ordinal in dims:
            low = ordinal.low.value
            high = ordinal.high.value
            sizes.append(high - low + 1)

        n_dims = len(sizes)
        self.emit("PUSHI 0")
        for i in range(n_dims):
            expr_list = varaccess.suffixes[i]
            idx_expr = expr_list[0]
            self.generate_expr(idx_expr)
            low_i = dims[i].low.value
            if low_i != 0:
                self.emit(f"PUSHI {low_i}")
                self.emit("SUB")
            prod = 1
            for j in range(i+1, n_dims):
                prod *= sizes[j]
            if prod != 1:
                self.emit(f"PUSHI {prod}")
                self.emit("MUL")
            self.emit("ADD")

        self.emit("LOADN")

    def generate_store_to_array(self, varaccess: VarAccess):
        storage, base_idx, meta = self.lookup_var(varaccess.name)
        arr_type = meta.get('type')
        if not arr_type or type(arr_type).__name__ != 'ArrayType':
            raise Exception("Atribuição a array mas o tipo não é ArrayType conhecido.")

        tmp_name = "__tmp_store"
        is_global_scope = len(self.local_frames) == 0
        tmp_idx = 0

        if is_global_scope:
            if tmp_name in self.globals:
                tmp_idx = self.globals[tmp_name]['idx']
            else:
                tmp_idx = self.next_gp
                self.globals[tmp_name] = {'idx': tmp_idx, 'size': 1, 'type': None}
                self.next_gp += 1
            self.emit(f"STOREG {tmp_idx}")
        else:
            if tmp_name in self.current_locals:
                tmp_idx = self.current_locals[tmp_name]['idx']
            else:
                tmp_idx = self.allocate_local(tmp_name)
            self.emit(f"STOREL {tmp_idx}")

        if storage == 'gp':
            self.emit("PUSHGP")
            self.emit(f"PUSHI {base_idx}")
            self.emit("PADD")
        else:
            self.emit("PUSHFP")
            self.emit(f"PUSHI {base_idx}")
            self.emit("PADD")

        dims = arr_type.ordinals
        sizes = []
        for ordinal in dims:
            low = ordinal.low.value
            high = ordinal.high.value
            sizes.append(high - low + 1)

        n_dims = len(sizes)
        self.emit("PUSHI 0")
        for i in range(n_dims):
            expr_list = varaccess.suffixes[i]
            idx_expr = expr_list[0]
            self.generate_expr(idx_expr)
            low_i = dims[i].low.value
            if low_i != 0:
                self.emit(f"PUSHI {low_i}")
                self.emit("SUB")
            prod = 1
            for j in range(i+1, n_dims):
                prod *= sizes[j]
            if prod != 1:
                self.emit(f"PUSHI {prod}")
                self.emit("MUL")
            self.emit("ADD")

        if is_global_scope:
            self.emit(f"PUSHG {tmp_idx}")
        else:
            self.emit(f"PUSHL {tmp_idx}")

        self.emit("STOREN")


# função de interface
def generate_ewvm(ast_root: Program) -> str:
    gen = CodeGenerator()
    return gen.generate_program(ast_root)
