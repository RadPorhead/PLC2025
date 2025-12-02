# codegen_ewvm.py
# Gerador de código EWVM — versão melhorada
# Comentários em Português de Portugal, foco na clareza.
#
# Principais funcionalidades adicionadas:
# - Frames simples: prologue/epilogue de funções (parametros empilhados pelo caller;
#   callee retira com STOREL).
# - Parâmetros por valor e por referência (byref).
#   - Convenção: caller empilha argumentos (valor para byval, endereço lógico para byref).
#   - Callee, no prologue, faz STOREL para mover argumentos para slots locais de parâmetro.
#   - Para byref, o valor armazenado no local é a "referência": operações sobre essa variável
#     geram LOAD/STORE indirecto (LOADN/STOREN). Assumimos que a VM tem instruções
#     de acesso indirecto (LOADN / STOREN). Se a tua VM usar outros nomes, ajusta aí.
# - Inferência de tipo simples (int/float/string/bool) para escolher instruções
#   (ex.: DIV vs FDIV, WRITEI vs WRITEF).
# - Arrays unidimensionais/ multidimensionais: alocação em gp/locais como bloco contínuo.
#   O cálculo do offset suporta subranges (p.ex. 1..10 ou -5..5). Só arrays com limites constantes.
# - READ / WRITE por tipo: READ -> ATOI (inteiro) ou lemos string com READ (endereço).
# - Gestão de constantes simples (mapa de constantes não é ainda usado para relocação).
#
# Limitações / TODO:
# - Algumas instruções indirectas dependem do nome exacto na VM (LOADN / STOREN / READ / ATOI).
#   Ajusta os nomes conforme o manual se necessário.
# - Tipagem dinâmica simples; não há verificação de compatibilidade profunda.
# - Passagem de parâmetros complexos (arrays por valor) não está optimizada.
# - As funções/ procedimentos são emitidos no postamble; os CALL usam PUSHA label + CALL.

from typing import List, Dict, Tuple, Optional
from ast1 import *

# Gera rótulos únicos
class LabelGen:
    def __init__(self):
        self.counter = 0
    def new(self, base='L'):
        # Força o base a ser maiúsculo (ex: 'WHILESTART')
        lbl = f"{base.upper()}{self.counter}"
        self.counter += 1
        return lbl

# Pequena helper para inferir tipo de um Literal/Expressão (muito simples)
def infer_type(expr):
    """Inferência de tipo muito simples: int / float / string / bool (0/1)."""
    if expr is None:
        return None
    t = type(expr).__name__
    if t == "Literal":
        v = expr.value
        if isinstance(v, int):
            return "int"
        if isinstance(v, float):
            return "float"
        if isinstance(v, str):
            return "string"
    if t == "VarAccess":
        # idealmente consultar tabela de símbolos; fallback unknown
        # o generator mantém symbol table com tipos; chamaremos a função com esse contexto
        return None
    if t in ("BinOp",):
        # operadores aritméticos: se qualquer lado for float => float
        lt = infer_type(expr.left)
        rt = infer_type(expr.right)
        if lt == "float" or rt == "float":
            return "float"
        # comparadores -> bool
        if expr.op in ('=', '<', '>', '<=', '>=', '<>'):
            return "bool"
        return "int"
    if t in ("UnOp",):
        return infer_type(expr.expr)
    if t == "Call":
        # desconhecido sem tabela de funções
        return None
    return None

# ----------------------
# CodeGenerator principal
# ----------------------
class CodeGenerator:
    def __init__(self):
        self.code: List[str] = []
        self.postamble: List[str] = []
        self.labelgen = LabelGen()

        # símbolos
        # globals: name -> {idx: start_index, size: n, type: TypeNode}
        self.globals: Dict[str, Dict] = {}
        # current function frame: locals name -> {idx: offset, size: n, type}
        self.current_locals: Dict[str, Dict] = {}
        # stack de frames (cada função entra/saí)
        self.local_frames: List[Dict[str, Dict]] = []

        # funções: name -> label
        self.func_labels: Dict[str, str] = {}

        # ponteiros de alocação
        self.next_gp = 0  # próxima célula global livre
        self.next_local = 0  # usados por frame corrente

    # --- utilitários de emissão
    def emit(self, instr: str):
        self.code.append(instr)

    def emit_post(self, instr: str):
        self.postamble.append(instr)

    def new_label(self, base='L'):
        return self.labelgen.new(base)

    # --- alocação de memória para variáveis (suporta arrays com SubrangeType)
    def size_of_type(self, type_node):
        """Retorna o número de células ocupadas pelo tipo (inteiro:1, float:1, string:1, arrays: produto)."""
        if type(type_node).__name__ == 'Type':
            # tipos simples referenciados por nome: assumimos 1 célula
            return 1
        elif type(type_node).__name__ == 'ArrayType':
            # calcular produto dos ordinais se forem subranges com literais
            prod = 1
            for ordinal in type_node.ordinals:
                if type(ordinal).__name__ == 'SubrangeType':
                    # cada bound é um Literal node (ou VarAccess referindo const) — assumimos Literal para já
                    low = ordinal.low.value if isinstance(ordinal.low, Literal) else None
                    high = ordinal.high.value if isinstance(ordinal.high, Literal) else None
                    if low is None or high is None:
                        raise NotImplementedError("Array com limites não-constantes não suportado (ainda).")
                    prod *= (high - low + 1)
                else:
                    # enumerated or ID not implemented robustly
                    raise NotImplementedError("Array com ordinal não-subrange não suportado (ainda).")
            # cada elemento considerado 1 célula (ajustar se elemtype for maior)
            elem_size = self.size_of_type(type_node.elemtype)
            return prod * elem_size
        elif type(type_node).__name__ == 'SubrangeType':
            # subrange por si não é um tipo de armazenamento separado — usar 1
            return 1
        else:
            # fallback
            return 1

    def allocate_globals(self, var_decls: List[VarDecl]):
        """Aloca gp indices para variáveis globais. Suporta arrays reservando bloco contínuo."""
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
        """Aloca uma entrada local (slot) / bloco. size em células."""
        sz = size if size is not None else (self.size_of_type(type_node) if type_node else 1)
        idx = self.next_local
        self.current_locals[name] = {'idx': idx, 'size': sz, 'type': type_node}
        self.next_local += sz
        return idx

    # localizar variável (resolva gp / fp / param_byref)
    def lookup_var(self, name) -> Tuple[str, int, Dict]:
        """
        Retorna (storage, idx, meta)
        storage: 'gp' ou 'fp'
        idx: índice base
        meta: dicionário com 'size' e 'type' e 'byref' possivelmente
        """
        if name in self.current_locals:
            meta = self.current_locals[name]
            return ('fp', meta['idx'], meta)
        if name in self.globals:
            meta = self.globals[name]
            return ('gp', meta['idx'], meta)
        # se não existir, criar global automaticamente (pressuposto pragmático)
        self.globals[name] = {'idx': self.next_gp, 'size': 1, 'type': None}
        self.next_gp += 1
        return ('gp', self.globals[name]['idx'], self.globals[name])

    # -------------
    # geração top-level
    # -------------
    def generate_program(self, program: Program) -> str:
        # START
        self.emit("START")
        # alocar globais do bloco principal
        self.allocate_globals(program.block.vars)
        # registar etiquetas de funções primeiro
        for decl in program.block.procsfuncs:
            if isinstance(decl, Proc) or isinstance(decl, Func):
                self.func_labels[decl.name] = f"FUNC{decl.name}"
        # gerar bloco principal
        self.generate_block(program.block, is_main=True)
        # STOP e acrescentar funções
        self.emit("STOP")
        self.code += self.postamble
        return "\n".join(self.code)

    def generate_block(self, block: Block, is_main=False):
        # se não for main, entrar frame e alocar locais declarados
        if not is_main:
            self.enter_frame()
            for vdecl in block.vars:
                for name in vdecl.names:
                    self.allocate_local(name, vdecl.type)
        else:
            # para bloco principal, já alocámos globais
            pass

        # registar labels de procs/funcs locais (shadowing possível)
        for decl in block.procsfuncs:
            if isinstance(decl, Proc) or isinstance(decl, Func):
                self.func_labels[decl.name] = f"FUNC{decl.name}"

        # gerar corpo
        self.generate_statement(block.compound)

        # gerar procs/funcs no postamble; isto permite referências a labels antes
        for decl in block.procsfuncs:
            if isinstance(decl, Proc):
                self.generate_proc(decl)
            elif isinstance(decl, Func):
                self.generate_func(decl)

        if not is_main:
            self.exit_frame()

    # ----------------------------------------------------
    # procedures / functions
    # Convenção simples:
    # - Caller empilha argumentos (left->right). Para byref, empilha um inteiro que representa
    #   a referência: index base e storage (codificado).
    # - Antes do corpo, callee executa STOREL para mover argumentos p/ locais de parâmetros.
    # - Para byref, local contém a referência; accesses geram LOADN/STOren (indirect).
    # ----------------------------------------------------
    def generate_proc(self, proc: Proc):
        lbl = self.func_labels.get(proc.name, f"FUNC{proc.name}")
        self.emit_post(f"{lbl}:")
        # entrar frame local
        self.enter_frame()
        # reservar espaço para parâmetros (ordenar para podermos STOREL em ordem invertida)
        params = proc.params or []
        # alocar slots para parâmetros antes dos locais
        for p in params:
            # p: Param(names, type, byref)
            for name in p.names:
                # cada nome recebe slot (size determinado por type)
                self.allocate_local(name, p.type)
                # marcar se byref
                self.current_locals[name]['byref'] = getattr(p, 'byref', False)

        # alocar restantes locais do bloco
        for vdecl in proc.block.vars:
            for name in vdecl.names:
                self.allocate_local(name, vdecl.type)

        # PROLOGUE: retirar argumentos da stack (caller empilhou left->right, o topo é o último arg)
        # Para cada parâmetro em ordem inversa (do último para o primeiro) fazemos STOREL idx
        # Assim o primeiro param (leftmost) fica no local com idx atribuído.
        # Nota: isto consome os valores que o caller deixou.
        # se param.byref: espera-se que caller tenha empilhado uma representação de referência (índice)
        for p in reversed(params):
            for name in reversed(p.names):
                meta = self.current_locals[name]
                idx = meta['idx']
                # STOREL retira do topo e guarda em fp[idx]
                self.emit(f"STOREL {idx}")

        # gerar corpo
        self.generate_statement(proc.block.compound)
        # RETURN (procedimento não devolve valor)
        self.emit_post("RETURN")
        # sair frame
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

        # retirar parâmetros do topo para locals
        for p in reversed(params):
            for name in reversed(p.names):
                meta = self.current_locals[name]
                self.emit(f"STOREL {meta['idx']}")

        # gera corpo
        self.generate_statement(func.block.compound)
        # função deve deixar valor no topo (convenção simples); RETURN
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
            # target: VarAccess, expr
            # suportar arrays / indices
            self.generate_expr(stmt.expr)  # deixa valor no topo
            target = stmt.target
            if not isinstance(target, VarAccess):
                raise Exception("Assign target inesperado")
            # se é acesso a array (sufixos)
            if target.suffixes:
                self.generate_store_to_array(target)
            else:
                storage, idx, meta = self.lookup_var(target.name)
                # se este identificador foi declarado como byref param
                if meta.get('byref', False):
                    # o slot contém uma referência (endereço). Precisamos de armazenar por indirecção.
                    # Assume-se instruções STOREN (store to address top-of-stack) ou equivalente.
                    # Pseudocódigo:
                    # - valor está no topo
                    # - carregar referência (fp idx) -> PUSHL idx ; LOAD address (se necessário)
                    # - chamar STOREN (que toma value,address do topo? ordem depende da VM)
                    #
                    # A convenção assumida aqui (para STOREN):
                    # - empilhar address, empilhar value, depois STOREN -> guarda value em memória[address]
                    # Para obedecer a isso: vamos rearranjar:
                    #   1) empilhar value (já está no topo)
                    #   2) empilhar endereço da referência (PUSHL idx)
                    #   3) EMIT STOREN expects (value,address) -> se a VM tiver ordem oposta, muda-se aqui.
                    #
                    # Atenção: isto depende do manual; ajusta conforme a tua EWVM.
                    self.emit(f"PUSHL {idx}")   # empilha o endereço/ponteiro guardado no local
                    # supondo STOREN consome value,address -> adapt as needed
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
            # for var := start to|downto end do body
            varname = stmt.var
            # inicializar var
            self.generate_expr(stmt.start)
            storage, idx, meta = self.lookup_var(varname)
            if storage == 'gp':
                self.emit(f"STOREG {idx}")
            else:
                self.emit(f"STOREL {idx}")
            # controle
            start_lbl = self.new_label("forstart")
            end_lbl = self.new_label("forend")
            self.emit(f"{start_lbl}:")
            # carregar var e comparar com end
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
            # corpo
            self.generate_statement(stmt.body)
            # incrementa/decrementa
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
            # para cada var da lista, fazer READ e converter conforme tipo
            for v in stmt.vars:
                if v.suffixes:
                    raise NotImplementedError("READ para arrays/indices não implementado.")
                storage, idx, meta = self.lookup_var(v.name)
                # READ instr empilha string / valor? Vamos usar READ (que lê uma linha/string) um then ATOI se int
                # Supondo: READ -> coloca string no topo (endereço), depois usamos ATOI para inteiro.
                self.emit("READ")
                # escolher conversão consoante tipo declarado
                tdecl = meta.get('type')
                # inferir se for None -> assumimos inteiro
                if tdecl and type(tdecl).__name__ == 'Type' and tdecl.name.upper() in ('REAL', 'FLOAT'):
                    # converter string->float: não existe normalmente ATOF; poderás necessitar de ATOF
                    # fallback: ATOI -> ITOF
                    self.emit("ATOI")
                    self.emit("ITOF")
                    if storage == 'gp':
                        self.emit(f"STOREG {idx}")
                    else:
                        self.emit(f"STOREL {idx}")
                else:
                    # inteiro por omissão
                    self.emit("ATOI")
                    if storage == 'gp':
                        self.emit(f"STOREG {idx}")
                    else:
                        self.emit(f"STOREL {idx}")
        elif t == "Write":
            # cada param pode ser expr, (expr,width) ou (expr,width,prec)
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
                # gerar expressão
                self.generate_expr(expr)
                # determinar tipo para escolher instrução de escrita
                itype = infer_type(expr)
                if itype == "float":
                    self.emit("WRITEF")
                elif itype == "string":
                    self.emit("WRITES")
                else:
                    # por defeito integer
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
                self.emit(f"PUSHF {v}")
            elif isinstance(v, str):
                # CORREÇÃO AQUI:
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
            # se tiver sufixos -> array indexing
            if expr.suffixes:
                self.generate_load_from_array(expr)
            else:
                storage, idx, meta = self.lookup_var(expr.name)
                # se local é um parâmetro byref -> local contém referência, devemos carregar indiretamente
                if meta.get('byref', False):
                    # carregar referência (PUSHL idx) e depois LOADN para obter valor
                    # assumimos que LOADN consome address no topo e empilha value
                    self.emit(f"PUSHL {idx}")
                    self.emit("LOADN")
                else:
                    if storage == 'gp':
                        self.emit(f"PUSHG {idx}")
                    else:
                        self.emit(f"PUSHL {idx}")
        elif t == "BinOp":
            # gerar left then right
            self.generate_expr(expr.left)
            self.generate_expr(expr.right)
            op = expr.op
            # inferir tipo para escolher versão float/int
            ltype = infer_type(expr.left) or "int"
            rtype = infer_type(expr.right) or "int"
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
                    # se ambos inteiros mas operador '/', Pascal converte para real: ITOF + FDIV
                    # aqui, pragmaticamente: emitir DIV (inteiro) se nenhuma float detectada
                    self.emit("DIV")
            elif op.upper() == 'DIV':
                # DIV é divisão inteira
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
            # empilhar argumentos left->right
            # para byref args, caller deve empilhar a referência (endereço).
            # Aqui precisamos conhecer assinatura da função (params) para decidir se empilhar value ou address.
            func_label = self.func_labels.get(expr.name, f"FUNC_{expr.name}")
            # tentar recuperar assinatura se conhecida (proc/func definidas no mesmo módulo)
            # nota: não temos tabela de declarations completas com params, mas podemos procurar no postamble
            # simplificação pragmática: empilhar valores (byval). Para byref exigiremos o caller passar VarAccess especificamente.
            for arg in expr.args:
                # se arg é VarAccess e a declaração do parâmetro for byref, empilhamos referência:
                if isinstance(arg, VarAccess):
                    # tentativa melhor: se o arg é exactamente um VarAccess, empilhar endereço em vez do valor
                    storage, idx, meta = self.lookup_var(arg.name)
                    if meta.get('byref_caller', False):
                        # marcação opcional; por defeito empilhamos valor
                        pass
                    # convenção prática: para byref, o programmer deve escrever var (we detect by callee signature ideally)
                # simplesmente gerar expr (valor) - para referencias, o callee espera o endereço, o caller
                # deve empilhar o endereço (não fazemos isto automaticamente sem assinatura).
                self.generate_expr(arg)
            # empilhar endereço da função e CALL
            self.emit(f"PUSHA {func_label}")
            self.emit("CALL")
            # se função devolve valor, assume-se no topo
        else:
            raise NotImplementedError(f"Expr tipo não suportado: {t}")

    # ---------------------------
    # Array helpers (load/store)
    # ---------------------------
    def generate_load_from_array(self, varaccess: VarAccess):
        """
        Calcular índice linear para arrays multidimensionais e carregar o valor.
        Pressupostos:
         - os ordinais são subranges com limites constantes (Literal).
         - array está armazenado como bloco contínuo no gp/fp começando em base idx.
         - cada elemento tem size 1 (ajustar se necessário).
        """
        # obter metadados da variável
        storage, base_idx, meta = self.lookup_var(varaccess.name)
        arr_type = meta.get('type')
        if not arr_type or type(arr_type).__name__ != 'ArrayType':
            raise Exception("Acesso a array mas o tipo não é ArrayType conhecido.")
        # calcular offset: para cada dimensão, index - low, multiplicar pelo product dos dims seguintes
        # sufixes: cada item é expr_list, por norma só usamos 1 expr por dimensão
        dims = arr_type.ordinals
        if len(dims) != len(varaccess.suffixes):
            raise Exception("Número de índices não coincide com dimensões do array.")
        # calcular todos os índices (empilha valores)
        # vamos calcular o offset em código gerado (avaliar exprs e operar)
        # estratégia: gerar expressão que computa linearIndex e depois:
        #   PUSHI base_idx ; ADD -> endereço ; LOADN (ou usar addressing via LOADN)
        # Implementação:
        # 1) calcular linear index e deixar no topo
        # 2) PUSHI base_idx
        # 3) ADD
        # 4) LOADN (carregar mem[base_idx + offset])
        # Para calcular linear index, geramos código que computa formula.
        # Vamos montar produto dos tamanhos das dimensões seguintes
        sizes = []
        for ordinal in dims:
            if type(ordinal).__name__ != 'SubrangeType':
                raise NotImplementedError("Só suportamos ordinais SubrangeType para arrays.")
            low = ordinal.low.value if isinstance(ordinal.low, Literal) else None
            high = ordinal.high.value if isinstance(ordinal.high, Literal) else None
            if low is None or high is None:
                raise NotImplementedError("Array com limites não-constantes não suportado.")
            sizes.append(high - low + 1)
        # calcular linear index em runtime:
        # fórmula: Σ_{i=0..n-1} ( (index_i - low_i) * product_{j=i+1..n-1} sizes[j] )
        # implementamos em código gerado:
        n = len(sizes)
        # gerar 0 no topo como acumulador
        self.emit("PUSHI 0")  # acc = 0
        for i in range(n):
            # avaliar index_i
            expr_list = varaccess.suffixes[i]  # expr_list node
            if len(expr_list) != 1:
                raise NotImplementedError("Só suportamos um índice por dimensão.")
            idx_expr = expr_list[0]
            # empilhar (index_i - low_i)
            self.generate_expr(idx_expr)
            low_i = dims[i].low.value
            if low_i != 0:
                self.emit(f"PUSHI {low_i}")
                self.emit("SUB")  # index_i - low_i
            # multiplicar pelo produto dos tamanhos seguintes
            prod = 1
            for j in range(i+1, n):
                prod *= sizes[j]
            if prod != 1:
                self.emit(f"PUSHI {prod}")
                self.emit("MUL")
            # agora somar ao acumulador
            self.emit("ADD")  # acc = acc + term
        # agora topo tem linear index
        # empilhar base_idx
        if storage == 'gp':
            self.emit(f"PUSHI {base_idx}")  # base em gp index absoluto
        else:
            # para locais, precisamos de uma forma de referenciar bloco local base; assumimos PUSHL base_idx devolve valor
            # mas para endereço relativo, a VM pode não suportar; simplificação: transformar locais em gp para arrays
            # por agora, não suportamos arrays locais; exigir arrays globais
            raise NotImplementedError("Arrays locais não suportados (só arrays globais).")
        # endereço = base + offset
        self.emit("ADD")
        # carregar valor da memória[address] -> instrução LOADN (assumida). Ajusta se a VM usar outro nome.
        self.emit("LOADN")

    def generate_store_to_array(self, varaccess: VarAccess):
        # supondo a mesma convenção que load, exceto que armazenamos valor (value) no endereço
        # valor já deve estar no topo quando esta função é chamada
        storage, base_idx, meta = self.lookup_var(varaccess.name)
        arr_type = meta.get('type')
        if not arr_type or type(arr_type).__name__ != 'ArrayType':
            raise Exception("Atribuição a array mas o tipo não é ArrayType conhecido.")
        # cálculos de offsets semelhantes ao load; contudo temos value no topo; a convenção esperada para STOREN
        # precisa de (value, address) ou (address, value) dependendo do VM.
        # Vamos reordenar: vamos deixar (value, address) e assumir STOREN consome (value,address) e escreve.
        # Para isso, calculamos address, empilhamos em seguida, depois emitimos STOREN.
        # Calcular offset (produz no topo) – mas temos value no topo: precisamos de guardá-lo temporariamente.
        # Simplificação: usar uma stack buffer: empilhar value duplicado? Não há DUP instrução assumida.
        # Estratégia:
        # 1) mover value para um local temporário: STOREL temp_idx (colocar em locals temporário)
        # 2) calcular address e empilhá-lo
        # 3) PUSHL temp_idx ; LOADL? Em vez disso, usar PUSHL temp_idx then LOADN? Depende.
        # Para não introduzir complexidade, vamos exigir que no caller o value seja gerado **após** o cálculo do endereço.
        # Mas o parser chama generate_expr primeiro (deixando value), pelo que temos que salvar.
        # Implementação pragmática:
        # - alocar local temporário (temporário por nome interno)
        tmp_name = "__tmp_store"
        if tmp_name in self.current_locals:
            tmp_idx = self.current_locals[tmp_name]['idx']
        else:
            tmp_idx = self.allocate_local(tmp_name)
        # guardar value em tmp
        self.emit(f"STOREL {tmp_idx}")  # retira value e guarda em fp[tmp_idx]
        # agora calcular offset (similar a load)
        # reconstituir offset...
        dims = arr_type.ordinals
        sizes = []
        for ordinal in dims:
            low = ordinal.low.value
            high = ordinal.high.value
            sizes.append(high - low + 1)
        n = len(sizes)
        self.emit("PUSHI 0")
        for i in range(n):
            expr_list = varaccess.suffixes[i]
            if len(expr_list) != 1:
                raise NotImplementedError("Só suportamos um índice por dimensão.")
            idx_expr = expr_list[0]
            self.generate_expr(idx_expr)
            low_i = dims[i].low.value
            if low_i != 0:
                self.emit(f"PUSHI {low_i}")
                self.emit("SUB")
            prod = 1
            for j in range(i+1, n):
                prod *= sizes[j]
            if prod != 1:
                self.emit(f"PUSHI {prod}")
                self.emit("MUL")
            self.emit("ADD")
        # empilhar base
        if storage == 'gp':
            self.emit(f"PUSHI {base_idx}")
        else:
            raise NotImplementedError("Arrays locais não suportados para store.")
        self.emit("ADD")
        # recuperar value do tmp e empilhar (PUSHL tmp_idx -> empilha valor local)
        self.emit(f"PUSHL {tmp_idx}")
        # instrução de escrita indirecta: STOREN (assumida) consume (value,address)
        self.emit("STOREN")
        # opcional: liberar tmp (não fazemos; tmp permanece mas é sombra apenas)

# função de interface
def generate_ewvm(ast_root: Program) -> str:
    gen = CodeGenerator()
    return gen.generate_program(ast_root)
