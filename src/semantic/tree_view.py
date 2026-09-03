# -*- coding: utf-8 -*-
"""
Representación visual del árbol sintáctico.

Graphviz

Codigo adaptado de un proyecto de IA del semestre pasado
"""

from antlr4 import ParserRuleContext, TerminalNode
from antlr4.tree.Tree import ErrorNode

import graphviz


def _rule_name(ctx, parser_class):
    return parser_class.ruleNames[ctx.getRuleIndex()]


def _short_text(text, max_len=18):
    if text is None:
        return ""
    text = text.replace("\\", "\\\\").replace('"', '\\"')
    if len(text) > max_len:
        text = text[: max_len - 1] + "…"
    return text

#Se construye basandose en el arbol de ANTLR
def build_tree_graph(tree_ctx, parser_class, titulo="Árbol sintáctico"):
    graph = graphviz.Digraph(name="arbol_sintactico")
    graph.attr(label=titulo, labelloc="t", fontsize="16", rankdir="TB")
    graph.attr("node", fontname="Helvetica", fontsize="10")
    graph.attr("edge", arrowsize="0.6")

    counter = {"n": 0}

    def new_id():
        counter["n"] += 1
        return f"n{counter['n']}"

    def visit(node):
        node_id = new_id()
        if isinstance(node, TerminalNode):
            if isinstance(node, ErrorNode):
                label = f" {_short_text(node.getText())}"
                graph.node(node_id, label=label, shape="box", style="filled",
                           fillcolor="#f8d7da", color="#b02a37")
            else:
                label = _short_text(node.getText())
                graph.node(node_id, label=label, shape="box", style="filled",
                           fillcolor="#eef1f5", color="#7a8794")
            return node_id

        if isinstance(node, ParserRuleContext):
            label = _rule_name(node, parser_class)
            graph.node(node_id, label=label, shape="ellipse", style="filled",
                       fillcolor="#d7e8fc", color="#2f6fb0")
            for i in range(node.getChildCount()):
                child = node.getChild(i)
                child_id = visit(child)
                graph.edge(node_id, child_id)
            return node_id

        graph.node(node_id, label=str(node), shape="box")
        return node_id

    visit(tree_ctx)
    return graph


def export_tree_image(tree_ctx, parser_class, out_path_sin_extension, formato="png", titulo="Árbol sintáctico"):
    graph = build_tree_graph(tree_ctx, parser_class, titulo=titulo)
    return graph.render(filename=out_path_sin_extension, format=formato, cleanup=True)
