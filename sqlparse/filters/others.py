# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Andi Albrecht, albrecht.andi@gmail.com
#
# This module is part of python-sqlparse and is released under
# the BSD License: http://www.opensource.org/licenses/bsd-license.php

from sqlparse import sql, tokens as T
from sqlparse.compat import text_type
from sqlparse.utils import split_unquoted_newlines


class StripCommentsFilter(object):
    def _get_next_comment(self, tlist):
        # TODO(andi) Comment types should be unified, see related issue38
        token = tlist.token_next_by(i=sql.Comment, t=T.Comment)
        return token

    def _process(self, tlist):
        token = self._get_next_comment(tlist)
        while token:
            tidx = tlist.token_index(token)
            prev = tlist.token_prev(tidx, skip_ws=False)
            next_ = tlist.token_next(tidx, skip_ws=False)
            # Replace by whitespace if prev and next exist and if they're not
            # whitespaces. This doesn't apply if prev or next is a paranthesis.
            if (prev is not None and next_ is not None
                and not prev.is_whitespace() and not next_.is_whitespace()
                and not (prev.match(T.Punctuation, '(')
                         or next_.match(T.Punctuation, ')'))):
                tlist.tokens[tidx] = sql.Token(T.Whitespace, ' ')
            else:
                tlist.tokens.pop(tidx)
            token = self._get_next_comment(tlist)

    def process(self, stmt):
        [self.process(sgroup) for sgroup in stmt.get_sublists()]
        self._process(stmt)


class StripWhitespaceFilter(object):
    def _stripws(self, tlist):
        func_name = '_stripws_%s' % tlist.__class__.__name__.lower()
        func = getattr(self, func_name, self._stripws_default)
        func(tlist)

    def _stripws_default(self, tlist):
        last_was_ws = False
        is_first_char = True
        for token in tlist.tokens:
            if token.is_whitespace():
                if last_was_ws or is_first_char:
                    token.value = ''
                else:
                    token.value = ' '
            last_was_ws = token.is_whitespace()
            is_first_char = False

    def _stripws_identifierlist(self, tlist):
        # Removes newlines before commas, see issue140
        last_nl = None
        for token in tlist.tokens[:]:
            if last_nl and token.ttype is T.Punctuation and token.value == ',':
                tlist.tokens.remove(last_nl)

            last_nl = token if token.is_whitespace() else None
        return self._stripws_default(tlist)

    def _stripws_parenthesis(self, tlist):
        if tlist.tokens[1].is_whitespace():
            tlist.tokens.pop(1)
        if tlist.tokens[-2].is_whitespace():
            tlist.tokens.pop(-2)
        self._stripws_default(tlist)

    def process(self, stmt, depth=0):
        [self.process(sgroup, depth + 1) for sgroup in stmt.get_sublists()]
        self._stripws(stmt)
        if depth == 0 and stmt.tokens and stmt.tokens[-1].is_whitespace():
            stmt.tokens.pop(-1)


class SpacesAroundOperatorsFilter(object):
    whitelist = (sql.Identifier, sql.Comparison, sql.Where)

    def _process(self, tlist):
        def next_token(idx):
            return tlist.token_next_by(t=(T.Operator, T.Comparison), idx=idx)

        idx = 0
        token = next_token(idx)
        while token:
            idx = tlist.token_index(token)
            if idx > 0 and tlist.tokens[idx - 1].ttype != T.Whitespace:
                # insert before
                tlist.tokens.insert(idx, sql.Token(T.Whitespace, ' '))
                idx += 1
            if idx < len(tlist.tokens) - 1:
                if tlist.tokens[idx + 1].ttype != T.Whitespace:
                    tlist.tokens.insert(idx + 1, sql.Token(T.Whitespace, ' '))

            idx += 1
            token = next_token(idx)

        for sgroup in tlist.get_sublists():
            self._process(sgroup)

    def process(self, stmt):
        self._process(stmt)


# ---------------------------
# postprocess

class SerializerUnicode(object):
    def process(self, stmt):
        raw = text_type(stmt)
        lines = split_unquoted_newlines(raw)
        res = '\n'.join(line.rstrip() for line in lines)
        return res