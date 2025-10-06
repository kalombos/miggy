def exec_in(code, glob, loc=None):
    if isinstance(code, str):
        code = compile(code, "<string>", "exec", dont_inherit=True)
    exec(code, glob, loc)
