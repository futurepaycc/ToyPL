from tokens import *
from ast_node import *
from error import InvalidSyntaxError


####################
# PARSER RESULT 解析结果
####################

class ParserResult(object):
    def __init__(self):
        self.error = None
        self.node = None
        self.advance_count = 0 # 便于选择不同的报错，具体看failure方法

    def register_advancement(self):
        self.advance_count += 1

    def register(self, parser_result):
        self.advance_count += parser_result.advance_count
        if parser_result.error:
            self.error = parser_result.error
        return parser_result.node

    def success(self, node):
        self.node = node
        return self

    def failure(self, error):
        # 使用advance_count来选择显示的报错信息
        if not self.error or self.advance_count == 0:
            self.error = error
        return self


####################
# PARSER 解析器
####################

class Parser(object):
    def __init__(self, tokens):
        self.tokens = tokens
        self.tok_idx = -1
        self.advance()

    def advance(self):
        """
        从tokens列表中获得下一个token
        :return:
        """
        self.tok_idx += 1
        if self.tok_idx < len(self.tokens):
            self.current_tok = self.tokens[self.tok_idx]
        return self.current_tok

    def parse(self):
        # 语法解析Tokens

        # 从其实非终结符开始 => AST Root Node
        res = self.expr()
        if not res.error and self.current_tok.type != TT_EOF:
            return res.failure(InvalidSyntaxError(
                self.current_tok.pos_start, self.current_tok.pos_end,
                "Expected '+', '-', '*' or '/'"
            ))
        return res

    def atom(self):
        res = ParserResult()
        tok = self.current_tok

        if tok.type in (TT_INT, TT_FLOAT):
            # atom  : INT|FLOAT
            res.register_advancement()
            self.advance()
            return res.success(NumberNode(tok))

        elif tok.type == TT_IDENTIFIER:
            # atom  : IDENTIFIER
            res.register_advancement()
            self.advance()
            # 访问变量时，只会输入单独的变量名
            return res.success(VarAccessNode(tok))

        elif tok.type == TT_LPAREN:
            # factor : LPAREN expr RPAREN => (1 + 2) * 3
            self.advance()
            expr = res.register(self.expr())
            if res.error:
                return res

            if self.current_tok.type == TT_RPAREN:
                self.advance()
                return res.success(expr)
            else:
                return res.failure(InvalidSyntaxError(
                    self.current_tok.pos_start, self.current_tok.pos_end,
                    "Expected ')'"
                ))
        return res.failure(InvalidSyntaxError(
            tok.pos_start, tok.pos_end,
            # 报错中，期望的值中不包含var，虽然其文法中包含expr（LPAREN expr RPAREN），而expr中又包含var KEYWORD
            # 但这里并不存赋值的情况，所以报错中不包含var
            # 编程语言中的错误提示非常重要，所以要尽可能保持正确
            "Expected int, float, identifier, '+', '-', or'('"
        ))

    def power(self):
        """
        power   : atom (POW factor)*
        :return:
        """
        return self.bin_op(self.atom, (TT_POW,), self.factor)

    def factor(self):
        """
        因子
        factor  : (PLUS|MINUS) factor
                : power
        :return:
        """
        res = ParserResult()
        tok = self.current_tok

        # factor  : (PLUS|MINUS) factor
        if tok.type in (TT_PLUS, TT_MINUS):
            res.register_advancement()
            self.advance()
            factor = res.register(self.factor())
            if res.error: return res
            return res.success(UnaryOpNode(tok, factor))
        # factor    : power
        return self.power()

    def term(self):
        """
        项
        term    : factor (MUL|DIV) factor)*
        :return:
        """
        return self.bin_op(self.factor, (TT_MUL, TT_DIV))

    def expr(self):
        """
        表达式
        expr    : KEYWORD:var IDENTIFIER EQ expr
                : term ((PLUS|MINUS) term)*
        :return:
        """
        res = ParserResult()

        # 如果token为var，则是声明语句
        # expr    : KEYWORD:var IDENTIFIER EQ expr
        if self.current_tok.matches(TT_KEYWORDS, 'var'):
            res.register_advancement()
            self.advance()

            if self.current_tok.type != TT_IDENTIFIER:
                # 不是变量名，语法异常，报错
                return res.failure(InvalidSyntaxError(
                    self.current_tok.pos_start, self.current_tok.pos_end,
                    "Expected identifier"
                ))

            var_name = self.current_tok
            res.register_advancement()
            self.advance()
            if self.current_tok.type != TT_EQ:
                # 表示等号，语法异常，报错
                return res.failure(InvalidSyntaxError(
                    self.current_tok.pos_start, self.current_tok.pos_end,
                    "Expected '='"
                ))

            res.register_advancement()
            self.advance()
            # 变量赋值时，右值为表达式expr，此时可以调用self.expr() 递归处理
            # 此外，等于操作符不会出现在生成树中
            # basic > var a = 1
            # [KEYWORDS:var, IDENTIFIER:a, EQ, INT:1, EOF]
            # (IDENTIFIER:a, INT:1) => EQ 不存在
            # 1
            expr = res.register(self.expr())
            if res.error: return res
            # 赋值操作 var a = 1 + 4 => KEYWORD: var, Identifier: a, expr: 1 + 4
            return res.success(VarAssignNode(var_name, expr))
        else:
           # expr    : term ((PLUS|MINUS) term)*
            node = res.register(self.bin_op(self.term, (TT_PLUS, TT_MINUS)))
            if res.error:
                return res.failure(InvalidSyntaxError(
                    self.current_tok.pos_end, self.current_tok.pos_end,
                    # 期望的值中，包含var
                    "Expected 'var', int, float, identifier, '+', '-' or '('"
                ))
            return res.success(node)


    def bin_op(self, func_a, ops, func_b=None):
        if func_b == None:
            func_b = func_a
        res = ParserResult()
        left = res.register((func_a()))  # 递归调用
        if res.error: return res

        while self.current_tok.type in ops:
            op_tok = self.current_tok
            res.register_advancement()
            self.advance()
            right = res.register(func_b())
            if res.error: return res
            left = BinOpNode(left, op_tok, right)
        return res.success(left)