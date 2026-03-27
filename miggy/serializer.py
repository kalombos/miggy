import types
import enum



class BaseSerializer:
    def __init__(self, value):
        self.value = value

    def serialize(self) -> str:
        return repr(self.value)
    

class EnumSerializer(BaseSerializer):
    def serialize(self) -> str:
        return repr(self.value.value)



def serialize_value(value):
    if isinstance(value, enum.Enum):
        return EnumSerializer(value).serialize()
    return BaseSerializer(value=value).serialize()
