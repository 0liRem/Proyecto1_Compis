"""
Analizador semantico de Compiscript

  1. MANEJAR TIPOS
  2. Declaraciones 
  3. Funciones y ciclos
  4. condiciones
  5. clases y objects
  6. arrays
  7. ERRORES Y COMENTARIOS


apex devastator
  - TYPE ERRORS
  - ERRORES CON EL HANDLER
  - Solo reportar 1 inalcanzable
  - JERARQUIAS Y BURGUESIAS
"""

import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.dirname(_THIS_DIR)
_GENERATED_DIR = os.path.join(_SRC_DIR, "generated")
for _p in (_SRC_DIR, _GENERATED_DIR, _THIS_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from CompiscriptParser import CompiscriptParser 
from CompiscriptVisitor import CompiscriptVisitor 

from semantic.types import (  
    INTEGER, FLOAT, BOOLEAN, STRING, VOID, NULL, ERROR,
    ArrayType, ClassType, FunctionType, ErrorType,
    is_numeric, is_assignable, are_comparable, result_of_arithmetic,
    class_is_subtype, primitive_from_name,
)
from semantic.symbols import ( 
    Symbol, VariableSymbol, FunctionSymbol, ClassSymbol, Scope, SymbolTable,
)
from semantic.errors import SemanticErrors  


class SemanticChecker(CompiscriptVisitor):

    def __init__(self):
        self.symtab = SymbolTable()
        self.errors = SemanticErrors()
        self._declared_ctx = {}
        self._scope_to_class = {}     # simbolo clase
        self._scope_to_function = {}  # funcion simbolo
        self._function_stack = []
        self._class_stack = []

#STARTO
    def analyze(self, tree):
        statements = tree.statement()
        self._predeclare_block(statements, self.symtab.global_scope)
        self._run_statements(statements)
        return self.errors


#utility tipos
    def _resolve_type(self, type_ctx):
        if type_ctx is None:
            return VOID
        base_ctx = type_ctx.baseType()
        base_name = base_ctx.getChild(0).getText()
        base = primitive_from_name(base_name)
        if base is None:
            cls_sym = self.symtab.current.resolve(base_name)
            if cls_sym is None or not isinstance(cls_sym, ClassSymbol):
                self.errors.report(
                    base_ctx,
                    f"El tipo '{base_name}' no es un tipo primitivo ni una "
                    f"clase declarada.",
                    symbol=base_name,
                )
                base = ERROR
            else:
                base = ClassType(base_name, cls_sym)
        dims = type_ctx.getText().count("[")
        result = base
        for _ in range(dims):
            result = ArrayType(result)
        return result

    def _type_from_annotation(self, annotation_ctx):
        if annotation_ctx is None:
            return None
        return self._resolve_type(annotation_ctx.type_())

    @staticmethod
    def _operators_between(ctx):
#posicion impar de los hijos para los operandos sino peta
        return [ctx.getChild(i).getText() for i in range(1, ctx.getChildCount(), 2)]

#predeclaracion por bloque

    def _make_function_symbol(self, fctx, enclosing_scope, owner_class=None):
        name = fctx.Identifier().getText()
        tok = fctx.Identifier().getSymbol()
        fscope = Scope("function", parent=enclosing_scope, label=name)

        param_names, param_types = [], []
        if fctx.parameters() is not None:
            for p in fctx.parameters().parameter():
                pname = p.Identifier().getText()
                ptok = p.Identifier().getSymbol()
                if p.type_() is not None:
                    ptype = self._resolve_type(p.type_())
                else:
                    self.errors.report(
                        p,
                        f"El parámetro '{pname}' no tiene un tipo declarado.",
                        symbol=pname,
                    )
                    ptype = ERROR
                psym = VariableSymbol(pname, ptype, ptok.line, ptok.column)
                psym.initialized = True
                if not fscope.define(psym):
                    self.errors.report(
                        p,
                        f"El parámetro '{pname}' está duplicado en la lista "
                        f"de parámetros de '{name}'.",
                        symbol=pname,
                    )
                param_names.append(pname)
                param_types.append(ptype)

        return_type = self._resolve_type(fctx.type_()) if fctx.type_() is not None else VOID
        fsym = FunctionSymbol(name, param_types, param_names, return_type, tok.line, tok.column)
        fsym.scope = fscope
        fsym.owner_class = owner_class
        self._scope_to_function[id(fscope)] = fsym
        return fsym

    def _predeclare_block(self, statements, scope):
        class_ctxs = [s.classDeclaration() for s in statements if s.classDeclaration() is not None]
#Reservar nombres de clases para futuras referencias y curces (como los perritos)
        for cctx in class_ctxs:
            ids = cctx.Identifier()
            name_tok = ids[0].getSymbol()
            name = ids[0].getText()
            sym = ClassSymbol(name, name_tok.line, name_tok.column)
            if not self.symtab.insert(sym, scope):
                self.errors.report(
                    cctx, f"La clase '{name}' ya fue declarada en este ámbito.", symbol=name
                )
                existing = scope.resolve_local(name)
                if isinstance(existing, ClassSymbol):
                    sym = existing
            self._declared_ctx[id(cctx)] = sym
        #superclase 
        for cctx in class_ctxs:
            sym = self._declared_ctx[id(cctx)]
            if sym.superclass_name is not None:
                continue  # clase repetida
            ids = cctx.Identifier()
            if len(ids) > 1:
                super_name = ids[1].getText()
                sym.superclass_name = super_name
                super_sym = scope.resolve(super_name)
                if super_sym is None or not isinstance(super_sym, ClassSymbol):
                    self.errors.report(
                        cctx, f"La clase base '{super_name}' no está declarada.", symbol=super_name
                    )
                elif super_sym is sym or class_is_subtype(super_sym, sym):
                    self.errors.report(
                        cctx,
                        f"Herencia cíclica: '{sym.name}' no puede heredar "
                        f"(directa o indirectamente) de sí misma a través de "
                        f"'{super_name}'.",
                        symbol=super_name,
                    )
                else:
                    sym.superclass = super_sym

        # miembros de cada clase
        for cctx in class_ctxs:
            sym = self._declared_ctx[id(cctx)]
            if sym.scope is not None:
                continue  # clase repetida
            cscope = Scope("class", parent=scope, label=sym.name)
            sym.scope = cscope
            self._scope_to_class[id(cscope)] = sym
            for member in cctx.classMember():
                if member.functionDeclaration() is not None:
                    fctx = member.functionDeclaration()
                    fsym = self._make_function_symbol(fctx, cscope, owner_class=sym)
                    if not self.symtab.insert(fsym, cscope):
                        self.errors.report(
                            fctx,
                            f"El método '{fsym.name}' ya fue declarado en la "
                            f"clase '{sym.name}'.",
                            symbol=fsym.name,
                        )
                    elif fsym.name == "constructor":
                        sym.constructor = fsym
                    else:
                        sym.methods[fsym.name] = fsym
                    self._declared_ctx[id(fctx)] = fsym
                else:
                    is_const = member.constantDeclaration() is not None
                    vctx = member.constantDeclaration() if is_const else member.variableDeclaration()
                    name_tok = vctx.Identifier().getSymbol()
                    mname = vctx.Identifier().getText()
                    declared_type = self._type_from_annotation(vctx.typeAnnotation())
                    vsym = VariableSymbol(
                        mname, declared_type if declared_type is not None else ERROR,
                        name_tok.line, name_tok.column, is_const=is_const,
                    )
                    if not self.symtab.insert(vsym, cscope):
                        self.errors.report(
                            vctx,
                            f"El atributo '{mname}' ya fue declarado en la "
                            f"clase '{sym.name}'.",
                            symbol=mname,
                        )
                    else:
                        sym.fields[mname] = vsym
                    self._declared_ctx[id(vctx)] = vsym

        # Registrar funciones
        for st in statements:
            fctx = st.functionDeclaration()
            if fctx is None:
                continue
            fsym = self._make_function_symbol(fctx, scope)
            if not scope.define(fsym):
                self.errors.report(
                    fctx,
                    f"La función '{fsym.name}' ya fue declarada en este "
                    f"ámbito (no se admite sobrecarga).",
                    symbol=fsym.name,
                )
            self._declared_ctx[id(fctx)] = fsym

#RECORRER LAS LISTAS 

    @staticmethod
    def _statement_always_terminates(st):
        return (
            st.returnStatement() is not None
            or st.breakStatement() is not None
            or st.continueStatement() is not None
        )

    def _run_statements(self, statements):
        terminated = False
        warned = False
        for st in statements:
            if terminated and not warned:
                self.errors.report( #codigo muerto sigue corriendo
                    st,
                    "Código muerto: esta instrucción nunca se ejecuta porque "
                    "la sentencia anterior siempre termina el bloque "
                    "(return/break/continue).",
                )
                warned = True
            self.visit(st)
            if self._statement_always_terminates(st):
                terminated = True

    def _check_block_body(self, statements, scope_kind, label="", extra_defs=()):
        prev = self.symtab.current
        scope = Scope(scope_kind, parent=prev, label=label)
        for d in extra_defs:
            self.symtab.insert(d, scope)
        self.symtab.enter(scope)
        self._predeclare_block(statements, scope)
        self._run_statements(statements)
        self.symtab.current = prev
        self.symtab.operation_log.append({"operation": "SALIR ALCANCE", "name": "-", "type": "-", "scope": self.symtab._scope_name(prev), "result": scope.label or scope.kind})
        return scope

    def _check_function_body(self, fctx):
        fsym = self._declared_ctx.get(id(fctx))
        if fsym is None:
            return
        prev = self.symtab.current
        self._function_stack.append(fsym)
        self.symtab.enter(fsym.scope)
        statements = fctx.block().statement()
        self._predeclare_block(statements, fsym.scope)
        self._run_statements(statements)
        self.symtab.current = prev
        self.symtab.operation_log.append({"operation": "SALIR ALCANCE", "name": "-", "type": "-", "scope": self.symtab._scope_name(prev), "result": fsym.scope.label or fsym.scope.kind})
        self._function_stack.pop()

#Declaracion y no de amor
    def visitVariableDeclaration(self, ctx):
        name = ctx.Identifier().getText()
        tok = ctx.Identifier().getSymbol()
        declared_type = self._type_from_annotation(ctx.typeAnnotation())
        init_type = self.visit(ctx.initializer().expression()) if ctx.initializer() is not None else None

        pre = self._declared_ctx.get(id(ctx))
        if pre is not None:
            sym = pre
            if declared_type is not None:
                self.symtab.update(sym, type=declared_type)
            elif init_type is not None:
                self.symtab.update(sym, type=init_type)
            elif sym.type is ERROR:
                self.errors.report(
                    ctx,
                    f"El atributo '{name}' no tiene tipo declarado ni valor "
                    f"inicial para inferirlo.",
                    symbol=name,
                )
        else:
            if declared_type is None and init_type is None:
                self.errors.report(
                    ctx,
                    f"La variable '{name}' no tiene tipo declarado ni valor "
                    f"inicial para inferirlo.",
                    symbol=name,
                )
                final_type = ERROR
            else:
                final_type = declared_type if declared_type is not None else init_type
            sym = VariableSymbol(name, final_type, tok.line, tok.column)
            if not self.symtab.insert(sym):
                self.errors.report(ctx, f"'{name}' ya fue declarado en este ámbito.", symbol=name)

        if declared_type is not None and init_type is not None and not is_assignable(declared_type, init_type):
            self.errors.report(
                ctx.initializer().expression(),
                f"No se puede inicializar '{name}' (tipo {declared_type}) "
                f"con un valor de tipo {init_type}.",
                symbol=name,
            )
        if ctx.initializer() is not None:
            self.symtab.update(sym, initialized=True)
        return None

    def visitConstantDeclaration(self, ctx):
        name = ctx.Identifier().getText()
        tok = ctx.Identifier().getSymbol()
        declared_type = self._type_from_annotation(ctx.typeAnnotation())
        init_type = self.visit(ctx.expression())
        final_type = declared_type if declared_type is not None else init_type

        pre = self._declared_ctx.get(id(ctx))
        if pre is not None:
            sym = pre
            self.symtab.update(sym, type=final_type, is_const=True)
        else:
            sym = VariableSymbol(name, final_type, tok.line, tok.column, is_const=True)
            if not self.symtab.insert(sym):
                self.errors.report(ctx, f"'{name}' ya fue declarado en este ámbito.", symbol=name)
        self.symtab.update(sym, initialized=True)

        if declared_type is not None and not is_assignable(declared_type, init_type):
            self.errors.report(
                ctx.expression(),
                f"No se puede inicializar la constante '{name}' (tipo "
                f"{declared_type}) con un valor de tipo {init_type}.",
                symbol=name,
            )
        return None

    def visitAssignment(self, ctx):
        exprs = ctx.expression()
        if len(exprs) == 1:
            name = ctx.Identifier().getText()
            sym = self.symtab.retrieve(name)
            value_type = self.visit(exprs[0])
            if sym is None:
                self.errors.report(ctx, f"La variable '{name}' no ha sido declarada.", symbol=name)
                return ERROR
            if not isinstance(sym, VariableSymbol):
                self.errors.report(
                    ctx, f"'{name}' no es una variable; no se le puede asignar un valor.", symbol=name
                )
                return ERROR
            if sym.is_const:
                self.errors.report(
                    ctx, f"No se puede asignar un nuevo valor a la constante '{name}'.", symbol=name
                )
            elif not is_assignable(sym.type, value_type):
                self.errors.report(
                    ctx,
                    f"No se puede asignar un valor de tipo {value_type} a "
                    f"'{name}', declarada de tipo {sym.type}.",
                    symbol=name,
                )
            self.symtab.update(sym, initialized=True)
            return sym.type
        else:
            obj_type = self.visit(exprs[0])
            prop_name = ctx.Identifier().getText()
            value_type = self.visit(exprs[1])
            field_type = self._check_property_type(obj_type, prop_name, ctx)
            if field_type is not None and not is_assignable(field_type, value_type):
                self.errors.report(
                    ctx,
                    f"No se puede asignar un valor de tipo {value_type} al "
                    f"atributo '{prop_name}' de tipo {field_type}.",
                    symbol=prop_name,
                )
            return field_type if field_type is not None else ERROR

    def _check_property_type(self, obj_type, prop_name, ctx):
        if obj_type.is_error():
            return None
        if not isinstance(obj_type, ClassType) or obj_type.symbol is None:
            self.errors.report(
                ctx,
                f"El operador '.' sólo aplica sobre instancias de una "
                f"clase; se usó sobre un valor de tipo {obj_type}.",
            )
            return None
        field = obj_type.symbol.find_field(prop_name)
        if field is None:
            self.errors.report(
                ctx,
                f"La clase '{obj_type.symbol.name}' no tiene ningún "
                f"atributo llamado '{prop_name}'.",
                symbol=prop_name,
            )
            return None
        if field.is_const:
            self.errors.report(
                ctx,
                f"No se puede asignar un nuevo valor al atributo constante "
                f"'{prop_name}'.",
                symbol=prop_name,
            )
        return field.type

    def _check_arguments(self, expected_types, actual_types, actual_ctxs, call_ctx, callee_desc):
        if len(expected_types) != len(actual_types):
            self.errors.report(
                call_ctx,
                f"Se esperaban {len(expected_types)} argumento(s) para "
                f"{callee_desc}, pero se encontraron {len(actual_types)}.",
            )
            return
        for i, (exp, act) in enumerate(zip(expected_types, actual_types)):
            if not is_assignable(exp, act):
                ctx_for_error = actual_ctxs[i] if i < len(actual_ctxs) else call_ctx
                self.errors.report(
                    ctx_for_error,
                    f"El argumento {i + 1} de {callee_desc} debe ser de "
                    f"tipo {exp}; se encontró {act}.",
                )

#Control de flujo
    def visitBlock(self, ctx):
        self._check_block_body(ctx.statement(), "block", "bloque")
        return None

    def _check_condition_is_boolean(self, expr_ctx, construccion):
        cond_type = self.visit(expr_ctx)
        if not (cond_type.is_error() or cond_type == BOOLEAN):
            self.errors.report(
                expr_ctx,
                f"La condición de '{construccion}' debe ser de tipo "
                f"boolean; se encontró {cond_type}.",
            )
        return cond_type

    def visitIfStatement(self, ctx):
        self._check_condition_is_boolean(ctx.expression(), "if")
        blocks = ctx.block()
        self._check_block_body(blocks[0].statement(), "block", "if")
        if len(blocks) > 1:
            self._check_block_body(blocks[1].statement(), "block", "else")
        return None

    def visitWhileStatement(self, ctx):
        self._check_condition_is_boolean(ctx.expression(), "while")
        self._check_block_body(ctx.block().statement(), "loop", "while")
        return None

    def visitDoWhileStatement(self, ctx):
        self._check_block_body(ctx.block().statement(), "loop", "do-while")
        self._check_condition_is_boolean(ctx.expression(), "do-while")
        return None

    def visitForStatement(self, ctx):
        prev = self.symtab.current
        scope = Scope("loop", parent=prev, label="for")
        self.symtab.current = scope

        children = ctx.children or []
        i = 2 
        n = len(children)
        if i < n and isinstance(children[i], CompiscriptParser.VariableDeclarationContext):
            self.visit(children[i])
            i += 1
        elif i < n and isinstance(children[i], CompiscriptParser.AssignmentContext):
            self.visit(children[i])
            i += 1
        elif i < n and children[i].getText() == ";":
            i += 1

        cond_type = None
        if i < n and isinstance(children[i], CompiscriptParser.ExpressionContext):
            cond_type = self.visit(children[i])
            i += 1
        if i < n and children[i].getText() == ";":
            i += 1
        if i < n and isinstance(children[i], CompiscriptParser.ExpressionContext):
            self.visit(children[i])
            i += 1

        if cond_type is not None and not (cond_type.is_error() or cond_type == BOOLEAN):
            self.errors.report(
                ctx, f"La condición de 'for' debe ser de tipo boolean; se encontró {cond_type}."
            )

        statements = ctx.block().statement()
        self._predeclare_block(statements, scope)
        self._run_statements(statements)
        self.symtab.current = prev
        return None

    def visitForeachStatement(self, ctx):
        iterable_type = self.visit(ctx.expression())
        name = ctx.Identifier().getText()
        tok = ctx.Identifier().getSymbol()
        if iterable_type.is_error():
            elem_type = ERROR
        elif isinstance(iterable_type, ArrayType):
            elem_type = iterable_type.element_type
        else:
            self.errors.report(
                ctx.expression(),
                f"'foreach' requiere iterar sobre una lista; se encontró {iterable_type}.",
            )
            elem_type = ERROR
        loop_var = VariableSymbol(name, elem_type, tok.line, tok.column)
        loop_var.initialized = True
        self._check_block_body(ctx.block().statement(), "loop", "foreach", extra_defs=[loop_var])
        return None

    def visitBreakStatement(self, ctx):
        if not self.symtab.current.is_inside_loop_or_switch():
            self.errors.report(ctx, "'break' sólo puede usarse dentro de un bucle o un 'switch'.")
        return None

    def visitContinueStatement(self, ctx):
        if not self.symtab.current.is_inside_loop():
            self.errors.report(ctx, "'continue' sólo puede usarse dentro de un bucle.")
        return None

    def visitReturnStatement(self, ctx):
        fscope = self.symtab.current.enclosing_function_scope()
        func = self._scope_to_function.get(id(fscope)) if fscope is not None else None
        if func is None:
            self.errors.report(ctx, "'return' sólo puede usarse dentro de una función o método.")
            if ctx.expression() is not None:
                self.visit(ctx.expression())
            return None
        if ctx.expression() is not None:
            value_type = self.visit(ctx.expression())
            if func.return_type == VOID:
                self.errors.report(
                    ctx,
                    f"La función '{func.name}' no declara un tipo de "
                    f"retorno, pero se intenta devolver un valor de tipo "
                    f"{value_type}.",
                    symbol=func.name,
                )
            elif not is_assignable(func.return_type, value_type):
                self.errors.report(
                    ctx,
                    f"El valor de retorno de '{func.name}' debe ser de "
                    f"tipo {func.return_type}; se encontró {value_type}.",
                    symbol=func.name,
                )
        else:
            if not func.return_type.is_error() and func.return_type != VOID:
                self.errors.report(
                    ctx,
                    f"La función '{func.name}' debe devolver un valor de "
                    f"tipo {func.return_type}.",
                    symbol=func.name,
                )
        return None

    def visitTryCatchStatement(self, ctx):
        blocks = ctx.block()
        self._check_block_body(blocks[0].statement(), "block", "try")
        name = ctx.Identifier().getText()
        tok = ctx.Identifier().getSymbol()
        catch_var = VariableSymbol(name, STRING, tok.line, tok.column)
        catch_var.initialized = True
        self._check_block_body(blocks[1].statement(), "block", "catch", extra_defs=[catch_var])
        return None

    def visitSwitchStatement(self, ctx):
        switch_type = self.visit(ctx.expression())
        prev = self.symtab.current
        scope = Scope("switch", parent=prev, label="switch")
        self.symtab.enter(scope)
        for case in ctx.switchCase():
            case_type = self.visit(case.expression())
            if not are_comparable(switch_type, case_type):
                self.errors.report(
                    case.expression(),
                    f"El valor de 'case' debe ser compatible con el tipo "
                    f"del 'switch' ({switch_type}); se encontró {case_type}.",
                )
            self._predeclare_block(case.statement(), scope)
            self._run_statements(case.statement())
        if ctx.defaultCase() is not None:
            self._predeclare_block(ctx.defaultCase().statement(), scope)
            self._run_statements(ctx.defaultCase().statement())
        self.symtab.current = prev
        self.symtab.operation_log.append({"operation": "SALIR ALCANCE", "name": "-", "type": "-", "scope": self.symtab._scope_name(prev), "result": scope.label or scope.kind})
        return None
#Function and class en ingles  xd
    def visitFunctionDeclaration(self, ctx):
        self._check_function_body(ctx)
        return None

    def visitClassDeclaration(self, ctx):
        cls_sym = self._declared_ctx.get(id(ctx))
        if cls_sym is None:
            return None
        self._class_stack.append(cls_sym)
        prev = self.symtab.current
        self.symtab.enter(cls_sym.scope)
        for member in ctx.classMember():
            if member.functionDeclaration() is not None:
                self._check_function_body(member.functionDeclaration())
            elif member.variableDeclaration() is not None:
                self.visit(member.variableDeclaration())
            else:
                self.visit(member.constantDeclaration())
        self.symtab.current = prev
        self.symtab.operation_log.append({"operation": "SALIR ALCANCE", "name": "-", "type": "-", "scope": self.symtab._scope_name(prev), "result": cls_sym.scope.label or cls_sym.scope.kind})
        self._class_stack.pop()
        return None


    #expresiones
    def visitExpression(self, ctx):
        return self.visit(ctx.assignmentExpr())

    def visitExprNoAssign(self, ctx):
        return self.visit(ctx.conditionalExpr())

    def visitAssignExpr(self, ctx):
        lhs_ctx = ctx.leftHandSide()
        lhs_type = self.visit(lhs_ctx)
        rhs_type = self.visit(ctx.assignmentExpr())
        if self._is_bare_identifier(lhs_ctx):
            name = lhs_ctx.primaryAtom().Identifier().getText()
            sym = self.symtab.retrieve(name)
            if isinstance(sym, VariableSymbol):
                if sym.is_const:
                    self.errors.report(
                        ctx, f"No se puede asignar un nuevo valor a la constante '{name}'.", symbol=name
                    )
                self.symtab.update(sym, initialized=True)
        if not is_assignable(lhs_type, rhs_type):
            self.errors.report(
                ctx, f"No se puede asignar un valor de tipo {rhs_type} a algo de tipo {lhs_type}."
            )
        return lhs_type

    def visitPropertyAssignExpr(self, ctx):
        obj_type = self.visit(ctx.leftHandSide())
        prop_name = ctx.Identifier().getText()
        value_type = self.visit(ctx.assignmentExpr())
        field_type = self._check_property_type(obj_type, prop_name, ctx)
        if field_type is not None and not is_assignable(field_type, value_type):
            self.errors.report(
                ctx,
                f"No se puede asignar un valor de tipo {value_type} al "
                f"atributo '{prop_name}' de tipo {field_type}.",
                symbol=prop_name,
            )
        return field_type if field_type is not None else ERROR

    @staticmethod
    def _is_bare_identifier(lhs_ctx):
        return (
            len(lhs_ctx.suffixOp()) == 0
            and isinstance(lhs_ctx.primaryAtom(), CompiscriptParser.IdentifierExprContext)
        )

    def visitTernaryExpr(self, ctx):
        exprs = ctx.expression()
        if len(exprs) == 2:
            cond_type = self.visit(ctx.logicalOrExpr())
            if not (cond_type.is_error() or cond_type == BOOLEAN):
                self.errors.report(
                    ctx.logicalOrExpr(),
                    f"La condición del operador ternario debe ser de tipo "
                    f"boolean; se encontró {cond_type}.",
                )
            then_type = self.visit(exprs[0])
            else_type = self.visit(exprs[1])
            if then_type.is_error() or else_type.is_error():
                return ERROR
            if is_assignable(then_type, else_type):
                return then_type
            if is_assignable(else_type, then_type):
                return else_type
            self.errors.report(
                ctx,
                f"Las dos ramas del operador ternario deben tener tipos "
                f"compatibles; se encontró {then_type} y {else_type}.",
            )
            return ERROR
        return self.visit(ctx.logicalOrExpr())

    def _check_logical_chain(self, subs, op_symbol):
        current = self.visit(subs[0])
        if not (current.is_error() or current == BOOLEAN):
            self.errors.report(
                subs[0],
                f"El operador '{op_symbol}' requiere operandos de tipo "
                f"boolean; se encontró {current}.",
            )
            current = ERROR
        for i in range(1, len(subs)):
            right = self.visit(subs[i])
            if not (right.is_error() or right == BOOLEAN):
                self.errors.report(
                    subs[i],
                    f"El operador '{op_symbol}' requiere operandos de tipo "
                    f"boolean; se encontró {right}.",
                )
                right = ERROR
            current = ERROR if (current.is_error() or right.is_error()) else BOOLEAN
        return current

    def visitLogicalOrExpr(self, ctx):
        subs = ctx.logicalAndExpr()
        if len(subs) == 1:
            return self.visit(subs[0])
        return self._check_logical_chain(subs, "||")

    def visitLogicalAndExpr(self, ctx):
        subs = ctx.equalityExpr()
        if len(subs) == 1:
            return self.visit(subs[0])
        return self._check_logical_chain(subs, "&&")

    def visitEqualityExpr(self, ctx):
        subs = ctx.relationalExpr()
        if len(subs) == 1:
            return self.visit(subs[0])
        ops = self._operators_between(ctx)
        current = self.visit(subs[0])
        for i, op in enumerate(ops):
            right = self.visit(subs[i + 1])
            if not are_comparable(current, right):
                self.errors.report(
                    subs[i + 1],
                    f"Los operandos de '{op}' deben ser de tipos "
                    f"compatibles; se encontró {current} y {right}.",
                )
                current = ERROR
            else:
                current = ERROR if (current.is_error() or right.is_error()) else BOOLEAN
        return current

    def visitRelationalExpr(self, ctx):
        subs = ctx.additiveExpr()
        if len(subs) == 1:
            return self.visit(subs[0])
        ops = self._operators_between(ctx)
        current = self.visit(subs[0])
        for i, op in enumerate(ops):
            right = self.visit(subs[i + 1])
            ok_left = current.is_error() or is_numeric(current)
            ok_right = right.is_error() or is_numeric(right)
            if not (ok_left and ok_right):
                self.errors.report(
                    subs[i + 1],
                    f"El operador relacional '{op}' requiere operandos "
                    f"numéricos (integer/float); se encontró {current} y {right}.",
                )
                current = ERROR
            else:
                current = ERROR if (current.is_error() or right.is_error()) else BOOLEAN
        return current

    def _check_arith_operand_pair(self, left, right, op, right_ctx, allow_string):
        if left.is_error() or right.is_error():
            return ERROR
        if op == "+" and allow_string and left == STRING and right == STRING:
            return STRING
        if not (is_numeric(left) and is_numeric(right)):
            self.errors.report(
                right_ctx,
                f"El operador '{op}' requiere operandos de tipo integer o "
                f"float; se encontró {left} y {right}.",
            )
            return ERROR
        return result_of_arithmetic(op, left, right)

    def visitAdditiveExpr(self, ctx):
        subs = ctx.multiplicativeExpr()
        if len(subs) == 1:
            return self.visit(subs[0])
        ops = self._operators_between(ctx)
        current = self.visit(subs[0])
        for i, op in enumerate(ops):
            right = self.visit(subs[i + 1])
            current = self._check_arith_operand_pair(current, right, op, subs[i + 1], allow_string=True)
        return current

    def visitMultiplicativeExpr(self, ctx):
        subs = ctx.unaryExpr()
        if len(subs) == 1:
            return self.visit(subs[0])
        ops = self._operators_between(ctx)
        current = self.visit(subs[0])
        for i, op in enumerate(ops):
            right = self.visit(subs[i + 1])
            current = self._check_arith_operand_pair(current, right, op, subs[i + 1], allow_string=False)
        return current

    def visitUnaryExpr(self, ctx):
        if ctx.unaryExpr() is not None:
            operand_type = self.visit(ctx.unaryExpr())
            op = ctx.getChild(0).getText()
            if op == "!":
                if not (operand_type.is_error() or operand_type == BOOLEAN):
                    self.errors.report(
                        ctx,
                        f"El operador de negación '!' requiere un operando "
                        f"boolean; se encontró {operand_type}.",
                    )
                    return ERROR
                return BOOLEAN
            else:  # '-'
                if not (operand_type.is_error() or is_numeric(operand_type)):
                    self.errors.report(
                        ctx,
                        f"El operador unario '-' requiere un operando "
                        f"numérico; se encontró {operand_type}.",
                    )
                    return ERROR
                return operand_type
        return self.visit(ctx.primaryExpr())

    def visitPrimaryExpr(self, ctx):
        if ctx.literalExpr() is not None:
            return self.visit(ctx.literalExpr())
        if ctx.leftHandSide() is not None:
            return self.visit(ctx.leftHandSide())
        return self.visit(ctx.expression())

    def visitLiteralExpr(self, ctx):
        if ctx.Literal() is not None:
            lit = ctx.Literal().getText()
            if lit.startswith('"'):
                return STRING
            if "." in lit:
                return FLOAT
            return INTEGER
        if ctx.arrayLiteral() is not None:
            return self.visit(ctx.arrayLiteral())
        text = ctx.getText()
        if text in ("true", "false"):
            return BOOLEAN
        return NULL

    def visitArrayLiteral(self, ctx):
        exprs = ctx.expression()
        if not exprs:
            return ArrayType(ERROR)
        elem_type = self.visit(exprs[0])
        for e in exprs[1:]:
            t = self.visit(e)
            if elem_type.is_error() and not t.is_error():
                elem_type = t
            elif not t.is_error() and not (is_assignable(elem_type, t) or is_assignable(t, elem_type)):
                self.errors.report(
                    e,
                    f"Todos los elementos de la lista deben ser del mismo "
                    f"tipo; se encontró {elem_type} y {t}.",
                )
        return ArrayType(elem_type)

    # cadena de sufijos

    def visitLeftHandSide(self, ctx):
        current = self.visit(ctx.primaryAtom())  # atomo primario
        for suf in ctx.suffixOp():
            if isinstance(suf, CompiscriptParser.CallExprContext):
                current = self._check_call_suffix(current, suf)
            elif isinstance(suf, CompiscriptParser.IndexExprContext):
                current = self._check_index_suffix(current, suf)
            elif isinstance(suf, CompiscriptParser.PropertyAccessExprContext):
                current = self._check_property_access_suffix(current, suf)
        return current[0]

    def visitIdentifierExpr(self, ctx):
        name = ctx.Identifier().getText()
        sym = self.symtab.retrieve(name)
        if sym is None:
            self.errors.report(ctx, f"'{name}' no ha sido declarado.", symbol=name)
            return (ERROR, None)
        if isinstance(sym, FunctionSymbol):
            return (FunctionType(sym.param_types, sym.return_type), sym)
        if isinstance(sym, ClassSymbol):
            self.errors.report(
                ctx,
                f"'{name}' es una clase; use 'new {name}(...)' para crear "
                f"una instancia.",
                symbol=name,
            )
            return (ERROR, None)
        return (sym.type, sym)

    def visitNewExpr(self, ctx):
        name = ctx.Identifier().getText()
        args_ctx = ctx.arguments()
        args = args_ctx.expression() if args_ctx is not None else []
        sym = self.symtab.retrieve(name)
        if sym is None or not isinstance(sym, ClassSymbol):
            self.errors.report(ctx, f"'{name}' no corresponde a ninguna clase declarada.", symbol=name)
            for a in args:
                self.visit(a)
            return (ERROR, None)
        arg_types = [self.visit(a) for a in args]
        ctor = sym.find_constructor()
        expected = ctor.param_types if ctor is not None else []
        self._check_arguments(expected, arg_types, args, ctx, callee_desc=f"el constructor de '{name}'")
        return (ClassType(name, sym), None)

    def visitThisExpr(self, ctx):
        cscope = self.symtab.current.enclosing_class_scope()
        cls_sym = self._scope_to_class.get(id(cscope)) if cscope is not None else None
        if cls_sym is None:
            self.errors.report(ctx, "'this' sólo puede usarse dentro de un método de una clase.")
            return (ERROR, None)
        return (ClassType(cls_sym.name, cls_sym), None)

    def _check_call_suffix(self, current, suf):
        base_type, ref = current
        args_ctx = suf.arguments()
        args = args_ctx.expression() if args_ctx is not None else []
        arg_types = [self.visit(a) for a in args]
        if base_type.is_error():
            return (ERROR, None)
        if isinstance(base_type, FunctionType):
            desc = f"'{ref.name}'" if isinstance(ref, (FunctionSymbol,)) else "la función"
            self._check_arguments(base_type.param_types, arg_types, args, suf, callee_desc=desc)
            return (base_type.return_type, None)
        self.errors.report(
            suf, f"Sólo se pueden invocar funciones o métodos; se intentó invocar un valor de tipo {base_type}."
        )
        return (ERROR, None)

    def _check_index_suffix(self, current, suf):
        base_type, _ref = current
        idx_type = self.visit(suf.expression())
        if base_type.is_error():
            return (ERROR, None)
        if not isinstance(base_type, ArrayType):
            self.errors.report(
                suf, f"El operador '[]' sólo aplica sobre listas; se usó sobre un valor de tipo {base_type}."
            )
            return (ERROR, None)
        if not (idx_type.is_error() or idx_type == INTEGER):
            self.errors.report(
                suf.expression(),
                f"El índice de una lista debe ser de tipo integer; se encontró {idx_type}.",
            )
        return (base_type.element_type, None)

    def _check_property_access_suffix(self, current, suf):
        base_type, _ref = current
        prop_name = suf.Identifier().getText()
        if base_type.is_error():
            return (ERROR, None)
        if not isinstance(base_type, ClassType) or base_type.symbol is None:
            self.errors.report(
                suf,
                f"El operador '.' sólo aplica sobre instancias de una "
                f"clase; se usó sobre un valor de tipo {base_type}.",
            )
            return (ERROR, None)
        cls_sym = base_type.symbol
        field = cls_sym.find_field(prop_name)
        if field is not None:
            return (field.type, field)
        method = cls_sym.find_method(prop_name)
        if method is not None:
            return (FunctionType(method.param_types, method.return_type), method)
        self.errors.report(
            suf,
            f"La clase '{cls_sym.name}' no tiene ningún atributo o método "
            f"llamado '{prop_name}'.",
            symbol=prop_name,
        )
        return (ERROR, None)

#Arbol revisa arbol arbol bien regresa arbol propio
def analizar_semantica(tree):
    checker = SemanticChecker()
    checker.analyze(tree)
    return checker
