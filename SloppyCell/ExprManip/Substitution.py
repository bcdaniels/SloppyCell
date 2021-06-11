from ast import *
import copy

from SloppyCell.ExprManip  import AST
from SloppyCell.ExprManip.AST import strip_parse, ast2str
from SloppyCell.ExprManip  import Simplify

def sub_for_comps(expr, mapping):
    """
    For each pair out_name:in_expr in mapping, the returned string has all
    occurences of the variable out_compe substituted by in_expr.
    """
    if len(mapping) == 0:
        return expr

    ast = strip_parse(expr)
    ast_mapping = {}
    for out_expr, in_expr in mapping.items():
        out_ast = strip_parse(out_expr)
        nodes = [node for node in walk(out_ast)]
        if not isinstance(nodes[1], Compare):
            raise ValueError('Expression %s to substitute for is not a '\
                    'comparison.' % out_expr)
        ast_mapping[unparse(out_ast)] = strip_parse(in_expr)

    ast = _sub_subtrees_for_comps(ast, ast_mapping)
    return unparse(ast)

def _sub_subtrees_for_comps(ast, ast_mappings):
    for node in walk(ast):
        if isinstance(ast, Compare) and ast_mappings.has_key(unparse(ast)):
            return ast_mappings[unparse(ast)]
    return ast

def sub_for_var(expr, out_name, in_expr):
    """
    Returns a string with all occurances of the variable out_name substituted by
    in_expr.
    
    Perhaps regular expressions could do this more simply...
    """
    return sub_for_vars(expr, {out_name:in_expr})

def sub_for_vars(expr, mapping):
    """
    For each pair out_name:in_expr in mapping, the returned string has all
    occurences of the variable out_name substituted by in_expr.
    """
    if len(mapping) == 0:
        return expr

    ast = strip_parse(expr)
    ast_mapping = {}
    for out_name, in_expr in mapping.items():
        out_ast = strip_parse(out_name)
        nodes = [node for node in walk(out_ast)]
        if not isinstance(out_ast, Name):
            raise ValueError('Expression %s to substitute for is not a '\
                             'variable name.' % out_name)
        ast_mapping[str(out_ast.name)] = strip_parse(in_expr)

    ast = _sub_subtrees_for_vars(ast, ast_mapping)
    return unparse(ast)
    
def _sub_subtrees_for_vars(ast, ast_mappings):
    """
    For each out_name, in_ast pair in mappings, substitute in_ast for all 
    occurances of the variable named out_name in ast
    """
    for node in walk(ast):
        if isinstance(node, Name) and ast_mappings.has_key(unparse(ast)):
            node = ast_mappings[unparse(ast)]
    return ast
    # if isinstance(ast, Name) and ast_mappings.has_key(unparse(ast)):
    #     return ast_mappings[ast2str(ast)]
    # ast = AST.recurse_down_tree(ast, _sub_subtrees_for_vars, (ast_mappings,))
    # return ast

def sub_for_func(expr, func_name, func_vars, func_expr):
    """
    Return a string with the function func_name substituted for its exploded 
    form.
    
    func_name: The name of the function.
    func_vars: A sequence variables used by the function expression
    func_expr: The expression for the function.
    For example:
        If f(x, y, z) = sqrt(z)*x*y-z
        func_name = 'f'
        func_vars = ['x', 'y', 'z']
        func_expr = 'sqrt(z)*x*y-z'

    As a special case, functions that take a variable number of arguments can
    use '*' for func_vars.
    For example:
        sub_for_func('or_func(or_func(A,D),B,C)', 'or_func', '*', 'x or y')
        yields '(A or D) or B or C'
    """
    ast = strip_parse(expr)
    func_name_ast = strip_parse(func_name)
    nodes = [node for node in walk(func_name_ast.body[0])]
    print(nodes)
    if not isinstance(nodes[1], Name):
        raise ValueError('Function name is not a simple name.')
    
    func_name = func_name_ast.body[0].value.id
    print(func_name)
    func_expr_ast = strip_parse(func_expr)
    # We can strip_parse  the '*', so we special case it here.
    if func_vars == '*':
        if not hasattr(func_expr_ast, 'nodes'):
            raise ValueError("Top-level function in %s does not appear to "
                             "accept variable number of arguments. (It has no "
                             "'nodes' attribute.)" % func_expr)

        func_var_names = '*'
    else:
        func_vars_ast = [strip_parse(var).body[0].value for var in func_vars]
        for var_ast in func_vars_ast:
            if not isinstance(var_ast, Name):
                raise ValueError('Function variable is not a simple name.')
        func_var_names = [getattr(var_ast, 'id') for var_ast in func_vars_ast]
        print(func_var_names)

    ast = _sub_for_func_ast(ast, func_name, func_var_names, func_expr_ast)
    # simple = Simplify._simplify_ast(ast)
    print(ast)
    return unparse(ast)

def _sub_for_func_ast(ast, func_name, func_vars, func_expr_ast):
    """
    Return an ast with the function func_name substituted out.
    """
    print(dump(ast), func_name, func_vars, dump(func_expr_ast))
    for node in walk(ast):
        print(node)
        if isinstance(node, Call) and unparse(node) == func_name\
           and func_vars == '*':
            working_ast = copy.deepcopy(func_expr_ast)
            new_args = [_sub_for_func_ast(arg_ast, func_name, func_vars, 
                                          func_expr_ast) for arg_ast in node.value.args]
            # This subs out the arguments of the original function.
            working_ast.node.value.args = new_args
            return working_ast
        if isinstance(ast, Call) and unparse(node) == func_name\
           and len(node.value.args) == len(func_vars):
            # If our ast is the function we're looking for, we take the ast
            #  for the function expression, substitute for its arguments, and
            #  return
            working_ast = copy.deepcopy(func_expr_ast)
            mapping = {}
            for var_name, arg_ast in zip(func_vars, node.value.args):
                subbed_arg_ast = _sub_for_func_ast(arg_ast, func_name, func_vars, 
                                                   func_expr_ast)
                mapping[var_name] = subbed_arg_ast
            _sub_subtrees_for_vars(working_ast, mapping)
            return working_ast
    return ast

def make_c_compatible(expr):
    """
    Convert a python math string into one compatible with C.

    Substitute all python-style x**n exponents with pow(x, n).
    Replace all integer constants with float values to avoid integer
     casting problems (e.g. '1' -> '1.0').
    Replace 'and', 'or', and 'not' with C's '&&', '||', and '!'. This may be
     fragile if the parsing library changes in newer python versions.
    """
    tree = strip_parse(expr)
    tree = PowForDoubleStar().visit(tree)
    tree = ast2str(tree)
    return tree

class PowForDoubleStar(NodeTransformer):
    def visit_BinOp(self, node):
        node.left = self.visit(node.left)
        node.right = self.visit(node.right)

        if isinstance(node.op, Pow):
            node = copy_location(
                       Call(func=Name('pow'),
                                args=[node.left, node.right],
                                keywords=[]
                               ),
                       node
                   )
        return node
    def visit_Constant(self, node):
        if isinstance(node, Constant) and isinstance(node.value, int):
            print("entered here")
            node.value = float(node.value)
        return node
    def visit_And(self, node):
        if isinstance(node, And):
            node = copy_location(
                       Call(func=Name('&&'),
                                keywords=[]
                               ),
                       node
                   )
            return node
    def visit_Or(self, node):
        if isinstance(node, Or):
            node = copy_location(
                       Call(func=Name('||'),
                                keywords=[]
                               ),
                       node
                   )
            return node
    def visit_Or(self, node):
        if isinstance(node, Or):
            node = copy_location(
                       Call(func=Name('!(%s)'),
                                keywords=[]
                               ),
                       node
                   )
            return node
    
