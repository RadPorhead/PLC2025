# infer_type

Falta integração com tabela de símbolos.

# size_type

Neste momento suporta múltiplas dimensões, mas o resto do codegen não suporta cálculo de endereços multidimensionais.

# lookup_var

Lançar erro explicito quando variável não existe

# Alterações significativas que fiz

        elif t == "Call":
            func_label = self.func_labels.get(expr.name, f"FUNC_{expr.name}")
            # tentar obter assinatura (expandida)
            sig = self.func_sigs.get(expr.name, None)  # lista de dicts com 'byref'
            # empilhar argumentos left->right
            for i, arg in enumerate(expr.args):
                is_byref = False
                if sig and i < len(sig):
                    is_byref = sig[i].get('byref', False)
                # se o parâmetro é byref e o arg é uma VarAccess, empilha o endereço
                if is_byref and isinstance(arg, VarAccess):
                    if arg.suffixes:
                        # endereço do elemento do array
                        self.generate_array_element_address(arg)
                    else:
                        # endereço da variável simples
                        storage, idx, meta = self.lookup_var(arg.name)
                        if storage == 'gp':
                            # empilha endereço global
                            self.emit("PUSHGP")
                            self.emit(f"PUSHI {idx}")
                            self.emit("PADD")
                        else:
                            # empilha endereço local (FP + idx)
                            self.emit("PUSHFP")
                            self.emit(f"PUSHI {idx}")
                            self.emit("PADD")
                else:
                    # byval ou não VarAccess => empilhar valor (avaliar expressão)
                    self.generate_expr(arg)
            # empilhar endereço da função e CALL
            self.emit(f"PUSHA {func_label}")
            self.emit("CALL")

    def generate_array_element_address(self, varaccess: VarAccess):
    
    self.func_sigs: Dict[str, List[Dict]] = {}

    def _expand_params(self, params):
