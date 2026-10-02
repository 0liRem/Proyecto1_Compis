# -*- coding: utf-8 -*-
"""
Generador de código intermedio 
"""

from CompiscriptParser import CompiscriptParser
from semantic.checker import SemanticChecker
from semantic.symbols import VariableSymbol, FunctionSymbol
from semantic.types import INTEGER, FLOAT, VOID

from ir.tac import ProgramaTAC
from ir.temp_manager import TempManager
from ir.activation import build_activation_records, ampliar_marco_con_temporales, WORD_SIZE

_ops_entre = SemanticChecker._operators_between


class TACGenerator:
    def __init__(self, checker):
        self.checker = checker
        self.tac = ProgramaTAC()
        self.temps = TempManager()
        self.funcion_actual = None
        self._break_stack = []
        self._continue_stack = []
        self.reporte_activacion = None


    def generate(self, tree):
        self.reporte_activacion = build_activation_records(self.checker)
        self._emit_global_init(tree.statement())
        for fsym, _filas in self.reporte_activacion.funciones:
            self._emit_function(fsym)
        return self.tac

    def _emit_global_init(self, statements):
        self.funcion_actual = None
        self.temps.reiniciar()
        begin = self.tac.emit("func_begin", args=(0,), dest="__global__")
        for st in statements:
            if st.functionDeclaration() is not None or st.classDeclaration() is not None:
                continue
            self.emit_statement(st)
        self.tac.emit("return")
        self.tac.emit("func_end", dest="__global__")
        begin.args = (self.temps.max_live * WORD_SIZE,)

    def _emit_function(self, fsym):
        ctx = getattr(fsym, "ctx", None)
        if ctx is None:
            return
        self.funcion_actual = fsym
        self.temps.reiniciar()
        begin = self.tac.emit("func_begin", args=(0,), dest=fsym.tac_label, linea=fsym.line)
        for st in ctx.block().statement():
            self.emit_statement(st)
        if fsym.return_type == VOID:
            self.tac.emit("return")
        self.tac.emit("func_end", dest=fsym.tac_label)
        ampliar_marco_con_temporales(fsym, self.temps.max_live)
        begin.args = (fsym.tac_frame_size,)
        self.funcion_actual = None


    @staticmethod
    def _nombre(sym):
        if isinstance(sym, FunctionSymbol):
            return sym.tac_label
        return getattr(sym, "tac_name", sym.name)

    def _coerce(self, operando, origen, destino):
        if origen == INTEGER and destino == FLOAT and not origen.is_error():
            t = self.temps.nuevo()
            self.tac.emit("itof", args=(operando,), dest=t)
            self.temps.liberar(operando)
            return t
        return operando

    def _binario(self, op, izq, t_izq, der, t_der, linea=0):
        if t_izq == FLOAT and t_der == INTEGER:
            der = self._coerce(der, INTEGER, FLOAT)
        elif t_der == FLOAT and t_izq == INTEGER:
            izq = self._coerce(izq, INTEGER, FLOAT)
        t = self.temps.nuevo()
        self.tac.emit(op, args=(izq, der), dest=t, linea=linea)
        self.temps.liberar(izq)
        self.temps.liberar(der)
        return t



    def emit_statement(self, ctx):
        if ctx.variableDeclaration() is not None:
            return self.emit_variable_declaration(ctx.variableDeclaration())
        if ctx.constantDeclaration() is not None:
            return self.emit_constant_declaration(ctx.constantDeclaration())
        if ctx.assignment() is not None:
            return self.emit_assignment_stmt(ctx.assignment())
        if ctx.functionDeclaration() is not None or ctx.classDeclaration() is not None:
            return None  # se generan aparte (ver generate())
        if ctx.expressionStatement() is not None:
            valor = self.emit_expression(ctx.expressionStatement().expression())
            self.temps.liberar(valor)
            return None
        if ctx.printStatement() is not None:
            valor = self.emit_expression(ctx.printStatement().expression())
            self.tac.emit("print", args=(valor,))
            self.temps.liberar(valor)
            return None
        if ctx.block() is not None:
            return self.emit_block(ctx.block())
        if ctx.ifStatement() is not None:
            return self.emit_if(ctx.ifStatement())
        if ctx.whileStatement() is not None:
            return self.emit_while(ctx.whileStatement())
        if ctx.doWhileStatement() is not None:
            return self.emit_do_while(ctx.doWhileStatement())
        if ctx.forStatement() is not None:
            return self.emit_for(ctx.forStatement())
        if ctx.foreachStatement() is not None:
            return self.emit_foreach(ctx.foreachStatement())
        if ctx.tryCatchStatement() is not None:
            return self.emit_try_catch(ctx.tryCatchStatement())
        if ctx.switchStatement() is not None:
            return self.emit_switch(ctx.switchStatement())
        if ctx.breakStatement() is not None:
            self.tac.emit("goto", dest=self._break_stack[-1])
            return None
        if ctx.continueStatement() is not None:
            self.tac.emit("goto", dest=self._continue_stack[-1])
            return None
        if ctx.returnStatement() is not None:
            return self.emit_return(ctx.returnStatement())
        raise NotImplementedError("Sentencia no reconocida")

    def emit_block(self, ctx):
        for st in ctx.statement():
            self.emit_statement(st)

    def emit_variable_declaration(self, ctx):
        if ctx.initializer() is None:
            return None
        sym = self.checker.get_declared_symbol(ctx)
        expr = ctx.initializer().expression()
        valor = self.emit_expression(expr)
        valor = self._coerce(valor, expr.tac_tipo, sym.type)
        self.tac.emit("=", args=(valor,), dest=self._nombre(sym), linea=ctx.start.line)
        self.temps.liberar(valor)

    def emit_constant_declaration(self, ctx):
        sym = self.checker.get_declared_symbol(ctx)
        valor = self.emit_expression(ctx.expression())
        valor = self._coerce(valor, ctx.expression().tac_tipo, sym.type)
        self.tac.emit("=", args=(valor,), dest=self._nombre(sym), linea=ctx.start.line)
        self.temps.liberar(valor)

    def emit_assignment_stmt(self, ctx):
        exprs = ctx.expression()
        if len(exprs) == 1:
            sym = self.checker.get_declared_symbol(ctx)
            valor = self.emit_expression(exprs[0])
            valor = self._coerce(valor, exprs[0].tac_tipo, sym.type)
            self.tac.emit("=", args=(valor,), dest=self._nombre(sym), linea=ctx.start.line)
            self.temps.liberar(valor)
        else:
            obj = self.emit_expression(exprs[0])
            prop = ctx.Identifier().getText()
            valor = self.emit_expression(exprs[1])
            self.tac.emit("field_store", args=(obj, prop, valor), linea=ctx.start.line)
            self.temps.liberar(obj)
            self.temps.liberar(valor)

    def emit_if(self, ctx):
        cond = self.emit_expression(ctx.expression())
        blocks = ctx.block()
        l_else = self.tac.nueva_etiqueta()
        self.tac.emit("if_false", args=(cond,), dest=l_else)
        self.temps.liberar(cond)
        self.emit_block(blocks[0])
        if len(blocks) > 1:
            l_end = self.tac.nueva_etiqueta()
            self.tac.emit("goto", dest=l_end)
            self.tac.emit_label(l_else)
            self.emit_block(blocks[1])
            self.tac.emit_label(l_end)
        else:
            self.tac.emit_label(l_else)

    def emit_while(self, ctx):
        l_ini = self.tac.nueva_etiqueta()
        l_fin = self.tac.nueva_etiqueta()
        self.tac.emit_label(l_ini)
        cond = self.emit_expression(ctx.expression())
        self.tac.emit("if_false", args=(cond,), dest=l_fin)
        self.temps.liberar(cond)
        self._break_stack.append(l_fin)
        self._continue_stack.append(l_ini)
        self.emit_block(ctx.block())
        self._break_stack.pop()
        self._continue_stack.pop()
        self.tac.emit("goto", dest=l_ini)
        self.tac.emit_label(l_fin)

    def emit_do_while(self, ctx):
        l_ini = self.tac.nueva_etiqueta()
        l_cond = self.tac.nueva_etiqueta()
        l_fin = self.tac.nueva_etiqueta()
        self.tac.emit_label(l_ini)
        self._break_stack.append(l_fin)
        self._continue_stack.append(l_cond)
        self.emit_block(ctx.block())
        self._break_stack.pop()
        self._continue_stack.pop()
        self.tac.emit_label(l_cond)
        cond = self.emit_expression(ctx.expression())
        self.tac.emit("if_true", args=(cond,), dest=l_ini)
        self.temps.liberar(cond)
        self.tac.emit_label(l_fin)

    def emit_for(self, ctx):
        children = ctx.children or []
        i, n = 2, len(children)
        if i < n and isinstance(children[i], CompiscriptParser.VariableDeclarationContext):
            self.emit_variable_declaration(children[i]); i += 1
        elif i < n and isinstance(children[i], CompiscriptParser.AssignmentContext):
            self.emit_assignment_stmt(children[i]); i += 1
        elif i < n and children[i].getText() == ";":
            i += 1
        cond_ctx = update_ctx = None
        if i < n and isinstance(children[i], CompiscriptParser.ExpressionContext):
            cond_ctx = children[i]; i += 1
        if i < n and children[i].getText() == ";":
            i += 1
        if i < n and isinstance(children[i], CompiscriptParser.ExpressionContext):
            update_ctx = children[i]; i += 1

        l_cond = self.tac.nueva_etiqueta()
        l_update = self.tac.nueva_etiqueta()
        l_fin = self.tac.nueva_etiqueta()
        self.tac.emit_label(l_cond)
        if cond_ctx is not None:
            cond = self.emit_expression(cond_ctx)
            self.tac.emit("if_false", args=(cond,), dest=l_fin)
            self.temps.liberar(cond)
        self._break_stack.append(l_fin)
        self._continue_stack.append(l_update)
        self.emit_block(ctx.block())
        self._break_stack.pop()
        self._continue_stack.pop()
        self.tac.emit_label(l_update)
        if update_ctx is not None:
            self.temps.liberar(self.emit_expression(update_ctx))
        self.tac.emit("goto", dest=l_cond)
        self.tac.emit_label(l_fin)

    def emit_foreach(self, ctx):
        base = self.emit_expression(ctx.expression())
        var = self._nombre(self.checker.get_declared_symbol(ctx))
        idx = self.temps.nuevo()
        self.tac.emit("=", args=("0",), dest=idx)
        n = self.temps.nuevo()
        self.tac.emit("array_len", args=(base,), dest=n)
        l_cond = self.tac.nueva_etiqueta()
        l_update = self.tac.nueva_etiqueta()
        l_fin = self.tac.nueva_etiqueta()
        self.tac.emit_label(l_cond)
        cmp = self.temps.nuevo()
        self.tac.emit("<", args=(idx, n), dest=cmp)
        self.tac.emit("if_false", args=(cmp,), dest=l_fin)
        self.temps.liberar(cmp)
        self.tac.emit("array_load", args=(base, idx), dest=var)
        self._break_stack.append(l_fin)
        self._continue_stack.append(l_update)
        self.emit_block(ctx.block())
        self._break_stack.pop()
        self._continue_stack.pop()
        self.tac.emit_label(l_update)
        sig = self.temps.nuevo()
        self.tac.emit("+", args=(idx, "1"), dest=sig)
        self.tac.emit("=", args=(sig,), dest=idx)
        self.temps.liberar(sig)
        self.tac.emit("goto", dest=l_cond)
        self.tac.emit_label(l_fin)
        for t in (base, idx, n):
            self.temps.liberar(t)

    def emit_try_catch(self, ctx):
        blocks = ctx.block()
        self.tac.emit("comment", args=("try",))
        self.emit_block(blocks[0])
        var = self._nombre(self.checker.get_declared_symbol(ctx))
        self.tac.emit("comment", args=(f"catch ({var})",))
        self.emit_block(blocks[1])
        self.tac.emit("comment", args=("fin try/catch",))

    def emit_switch(self, ctx):
        valor = self.emit_expression(ctx.expression())
        l_fin = self.tac.nueva_etiqueta()
        casos = ctx.switchCase()
        etiquetas = [self.tac.nueva_etiqueta() for _ in casos]
        l_default = self.tac.nueva_etiqueta() if ctx.defaultCase() is not None else l_fin
        self._break_stack.append(l_fin)
        for i, caso in enumerate(casos):
            v = self.emit_expression(caso.expression())
            cmp = self.temps.nuevo()
            self.tac.emit("==", args=(valor, v), dest=cmp)
            self.tac.emit("if_true", args=(cmp,), dest=etiquetas[i])
            self.temps.liberar(cmp)
            self.temps.liberar(v)
        self.tac.emit("goto", dest=l_default)
        for i, caso in enumerate(casos):
            self.tac.emit_label(etiquetas[i])
            for st in caso.statement():
                self.emit_statement(st)
        if ctx.defaultCase() is not None:
            self.tac.emit_label(l_default)
            for st in ctx.defaultCase().statement():
                self.emit_statement(st)
        self._break_stack.pop()
        self.tac.emit_label(l_fin)
        self.temps.liberar(valor)

    def emit_return(self, ctx):
        if ctx.expression() is not None:
            valor = self.emit_expression(ctx.expression())
            if self.funcion_actual is not None:
                valor = self._coerce(valor, ctx.expression().tac_tipo, self.funcion_actual.return_type)
            self.tac.emit("return", args=(valor,), linea=ctx.start.line)
            self.temps.liberar(valor)
        else:
            self.tac.emit("return", linea=ctx.start.line)

    # Expresiones 

    def emit_expression(self, ctx):
        return self.emit_assignment_expr(ctx.assignmentExpr())

    def emit_assignment_expr(self, ctx):
        if isinstance(ctx, CompiscriptParser.AssignExprContext):
            expr = ctx.assignmentExpr()
            valor = self.emit_assignment_expr(expr)
            lhs = ctx.leftHandSide()
            destino_tipo = getattr(lhs, "tac_tipo", None)
            if destino_tipo is not None:
                valor = self._coerce(valor, getattr(expr, "tac_tipo", None), destino_tipo)
            self._store_lhs(lhs, valor)
            return valor
        if isinstance(ctx, CompiscriptParser.PropertyAssignExprContext):
            obj = self.emit_left_hand_side(ctx.leftHandSide())
            valor = self.emit_assignment_expr(ctx.assignmentExpr())
            self.tac.emit("field_store", args=(obj, ctx.Identifier().getText(), valor))
            self.temps.liberar(obj)
            return valor
        return self.emit_conditional(ctx.conditionalExpr())

    def _store_lhs(self, lhs, valor):
        sufijos = lhs.suffixOp()
        if not sufijos:
            sym = lhs.primaryAtom().tac_ref
            self.tac.emit("=", args=(valor,), dest=self._nombre(sym))
            return
        ultimo = sufijos[-1]
        base, _, _ = self._chain(lhs, len(sufijos) - 1)
        idx = self.emit_expression(ultimo.expression())
        self.tac.emit("array_store", args=(base, idx, valor))
        self.temps.liberar(base)
        self.temps.liberar(idx)

    def emit_conditional(self, ctx):
        exprs = ctx.expression()
        if len(exprs) != 2:
            return self.emit_logical_or(ctx.logicalOrExpr())
        cond = self.emit_logical_or(ctx.logicalOrExpr())
        l_else = self.tac.nueva_etiqueta()
        l_end = self.tac.nueva_etiqueta()
        res = self.temps.nuevo()
        self.tac.emit("if_false", args=(cond,), dest=l_else)
        self.temps.liberar(cond)
        v1 = self.emit_expression(exprs[0])
        self.tac.emit("=", args=(v1,), dest=res)
        self.temps.liberar(v1)
        self.tac.emit("goto", dest=l_end)
        self.tac.emit_label(l_else)
        v2 = self.emit_expression(exprs[1])
        self.tac.emit("=", args=(v2,), dest=res)
        self.temps.liberar(v2)
        self.tac.emit_label(l_end)
        return res

    def _short_circuit(self, izq, der_ctx, op, siguiente):
        t = self.temps.nuevo()
        l_corto = self.tac.nueva_etiqueta()
        l_fin = self.tac.nueva_etiqueta()
        self.tac.emit("if_false" if op == "&&" else "if_true", args=(izq,), dest=l_corto)
        self.temps.liberar(izq)
        der = siguiente(der_ctx)
        self.tac.emit("=", args=(der,), dest=t)
        self.temps.liberar(der)
        self.tac.emit("goto", dest=l_fin)
        self.tac.emit_label(l_corto)
        self.tac.emit("=", args=("0" if op == "&&" else "1",), dest=t)
        self.tac.emit_label(l_fin)
        return t

    def emit_logical_or(self, ctx):
        subs = ctx.logicalAndExpr()
        res = self.emit_logical_and(subs[0])
        for s in subs[1:]:
            res = self._short_circuit(res, s, "||", self.emit_logical_and)
        return res

    def emit_logical_and(self, ctx):
        subs = ctx.equalityExpr()
        res = self.emit_equality(subs[0])
        for s in subs[1:]:
            res = self._short_circuit(res, s, "&&", self.emit_equality)
        return res

    def _cadena_binaria(self, ctx, subs, siguiente):
        ops = _ops_entre(ctx)
        res = siguiente(subs[0])
        t_res = subs[0].tac_tipo if hasattr(subs[0], "tac_tipo") else None
        for i, op in enumerate(ops):
            der = siguiente(subs[i + 1])
            t_der = getattr(subs[i + 1], "tac_tipo", None)
            res = self._binario(op, res, t_res, der, t_der, linea=subs[i + 1].start.line)
            # tipo del resultado acumulado: el que el checker anotó no
            # existe para resultados parciales; se aproxima por promoción
            if op in ("==", "!=", "<", "<=", ">", ">="):
                t_res = None
            elif t_res == FLOAT or t_der == FLOAT:
                t_res = FLOAT
        return res

    def emit_equality(self, ctx):
        return self._cadena_binaria(ctx, ctx.relationalExpr(), self.emit_relational)

    def emit_relational(self, ctx):
        return self._cadena_binaria(ctx, ctx.additiveExpr(), self.emit_additive)

    def emit_additive(self, ctx):
        return self._cadena_binaria(ctx, ctx.multiplicativeExpr(), self.emit_multiplicative)

    def emit_multiplicative(self, ctx):
        return self._cadena_binaria(ctx, ctx.unaryExpr(), self.emit_unary)

    def emit_unary(self, ctx):
        if ctx.unaryExpr() is not None:
            op = ctx.getChild(0).getText()
            v = self.emit_unary(ctx.unaryExpr())
            t = self.temps.nuevo()
            self.tac.emit("not" if op == "!" else "uminus", args=(v,), dest=t)
            self.temps.liberar(v)
            return t
        return self.emit_primary(ctx.primaryExpr())

    def emit_primary(self, ctx):
        if ctx.literalExpr() is not None:
            return self.emit_literal(ctx.literalExpr())
        if ctx.leftHandSide() is not None:
            return self.emit_left_hand_side(ctx.leftHandSide())
        return self.emit_expression(ctx.expression())

    def emit_literal(self, ctx):
        if ctx.Literal() is not None:
            return ctx.Literal().getText()
        if ctx.arrayLiteral() is not None:
            return self.emit_array_literal(ctx.arrayLiteral())
        texto = ctx.getText()
        if texto == "true":
            return "1"
        if texto == "false":
            return "0"
        return "null"

    def emit_array_literal(self, ctx):
        exprs = ctx.expression()
        t = self.temps.nuevo()
        self.tac.emit("array_new", args=(len(exprs),), dest=t)
        for i, e in enumerate(exprs):
            v = self.emit_expression(e)
            self.tac.emit("array_store", args=(t, str(i), v))
            self.temps.liberar(v)
        return t

    # leftHandSide

    def emit_left_hand_side(self, ctx):
        return self._chain(ctx, len(ctx.suffixOp()))[0]

    def _chain(self, ctx, n):
        operando, tipo, ref = self._atom(ctx.primaryAtom())
        for suf in ctx.suffixOp()[:n]:
            operando, tipo, ref = self._suffix(operando, tipo, ref, suf)
        return operando, tipo, ref

    def _atom(self, ctx):
        if isinstance(ctx, CompiscriptParser.IdentifierExprContext):
            sym = ctx.tac_ref
            nombre = self._nombre(sym) if sym is not None else ctx.Identifier().getText()
            dueno = getattr(sym, "tac_owner_function", None)
            if isinstance(sym, VariableSymbol) and dueno is not None and dueno is not self.funcion_actual:
                t = self.temps.nuevo()
                self.tac.emit("noloc", args=(nombre, dueno.tac_label), dest=t)
                return t, ctx.tac_tipo, sym
            return nombre, ctx.tac_tipo, sym
        if isinstance(ctx, CompiscriptParser.NewExprContext):
            return self._new(ctx)
        return "this", ctx.tac_tipo, None  # ThisExpr

    def _new(self, ctx):
        ctor = ctx.tac_ref
        t_obj = self.temps.nuevo()
        self.tac.emit("obj_new", args=(ctx.Identifier().getText(),), dest=t_obj)
        args_ctx = ctx.arguments()
        exprs = args_ctx.expression() if args_ctx is not None else []
        if ctor is not None:
            valores = [self._coerce(self.emit_expression(e), e.tac_tipo, pt)
                       for e, pt in zip(exprs, ctor.param_types)]
            self.tac.emit("param", args=(t_obj,))
            for v in valores:
                self.tac.emit("param", args=(v,))
            self.tac.emit("call", args=(ctor.tac_label, len(valores) + 1))
            for v in valores:
                self.temps.liberar(v)
        return t_obj, ctx.tac_tipo, ctor

    def _suffix(self, operando, tipo, ref, suf):
        if isinstance(suf, CompiscriptParser.CallExprContext):
            return self._call(operando, ref, suf)
        if isinstance(suf, CompiscriptParser.IndexExprContext):
            idx = self.emit_expression(suf.expression())
            t = self.temps.nuevo()
            self.tac.emit("array_load", args=(operando, idx), dest=t)
            self.temps.liberar(operando)
            self.temps.liberar(idx)
            return t, suf.tac_tipo, None
        # PropertyAccessExpr
        if isinstance(suf.tac_ref, FunctionSymbol):
            return operando, suf.tac_tipo, suf.tac_ref  # método
        t = self.temps.nuevo()
        self.tac.emit("field_load", args=(operando, suf.Identifier().getText()), dest=t)
        self.temps.liberar(operando)
        return t, suf.tac_tipo, suf.tac_ref

    def _call(self, operando, ref, suf):
        args_ctx = suf.arguments()
        exprs = args_ctx.expression() if args_ctx is not None else []
        es_metodo = ref.owner_class is not None
        valores = [self._coerce(self.emit_expression(e), e.tac_tipo, pt)
                   for e, pt in zip(exprs, ref.param_types)]
        if es_metodo:
            self.tac.emit("param", args=(operando,))
        for v in valores:
            self.tac.emit("param", args=(v,))
        t = self.temps.nuevo() if ref.return_type != VOID else None
        self.tac.emit("call", args=(ref.tac_label, len(valores) + (1 if es_metodo else 0)),
                      dest=t, linea=suf.start.line)
        for v in valores:
            self.temps.liberar(v)
        if es_metodo:
            self.temps.liberar(operando)
        return (t if t is not None else "void"), ref.return_type, None


def generar_tac(tree, checker):

    gen = TACGenerator(checker)
    tac = gen.generate(tree)
    return tac, gen.reporte_activacion
