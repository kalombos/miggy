

import re

from miggy.serializer import serialize_value


class OperationWriter:
    def __init__(self, operation, indentation=2):
        self.operation = operation
        self.buff = []
        self.indentation = indentation

    def _write(self, _arg_name, _arg_value):
        if isinstance(_arg_value, dict):
            self.feed("%s={" % _arg_name)
            self.indent()
            for key, value in _arg_value.items():
                key_string = serialize_value(key)
                arg_string = serialize_value(value)
                args = arg_string.splitlines()
                if len(args) > 1:
                    self.feed("%s: %s" % (key_string, args[0]))
                    for arg in args[1:-1]:
                        self.feed(arg)
                    self.feed("%s," % args[-1])
                else:
                    self.feed("%s: %s," % (key_string, arg_string))
            self.unindent()
            self.feed("},")
        else:
            arg_string = serialize_value(_arg_value)
            args = arg_string.splitlines()
            if len(args) > 1:
                self.feed("%s=%s" % (_arg_name, args[0]))
                for arg in args[1:-1]:
                    self.feed(arg)
                self.feed("%s," % args[-1])
            else:
                self.feed("%s=%s," % (_arg_name, arg_string))

    def get_func_name(self) -> str:
        name = self.operation.__class__.__name__
        shortcut = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
        return f"migrator.{shortcut}"

    def serialize(self) -> str:
        params = self.operation.deconstruct()
        self.feed("%s(" % self.get_func_name())
        self.indent()
        for name, value in params.items():
            self._write(name, value)

        self.unindent()
        self.feed("),")
        return self.render()

    def indent(self) -> None:
        self.indentation += 1

    def unindent(self) -> None:
        self.indentation -= 1

    def feed(self, line) -> None:
        self.buff.append(" " * (self.indentation * 4) + line)

    def render(self) -> str:
        return "\n".join(self.buff)
