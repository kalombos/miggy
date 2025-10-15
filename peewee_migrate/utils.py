

import peewee as pw

from peewee_migrate.ext import Default


def exec_in(code, glob, loc=None):
    if isinstance(code, str):
        code = compile(code, "<string>", "exec", dont_inherit=True)
    exec(code, glob, loc)


def get_default_constraint(field = pw.Field) -> None | Default:
    if field.constraints is None:
        return None
    constraints =  []
    for constraint in field.constraints:
        if isinstance(constraint, Default):
            constraints.append(constraint)
        elif isinstance(constraint, pw.SQL):
            if _constraint := Default.from_SQL(constraint):
                constraints.append(_constraint)
    if len(constraints) > 1: 
        raise ValueError(f'"{field.name}" field has more than one default constraint')
    return constraints[0] if constraints else None
