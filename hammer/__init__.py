# coding=utf-8
"""
hammer.py: Convert Colander schemas into JSON Schema documents.

To extend, register your Schema and SchemaType adapters by creating a subclass
of :class:`BaseAdapter`. Create a validator adapter by decorating a function
with :function:`adapts_validator`.

TODO: Extensible way to mark a custom Schema, SchemaType or validator as
ignored.
"""
import colander


class Invalid(Exception):
    """
    Raised when a Colander node is encountered that cannot be converted to
    a JSON schema type.
    """
    def __str__(self):
        # The thing that was invalid should be passed to this exception.
        return self.args[0]

    def __repr__(self):
        return self.__str__()


class Ignore(object):
    """
    A Colander type or validator that should be ignored.
    """
    pass


_schema_adapters = {
    colander.Int: 'number',
    colander.Integer: 'number',
    colander.Float: 'number',
    colander.String: 'string',
    colander.Str: 'string',
    colander.Bool: 'boolean',
}


_validator_adapters = {
    colander.Function: Ignore
}


def adapts_validator(colander_class):
    """
    A decorator that registers the decorated function as a Hammer adapter for
    a validator.

    ``colander_class`` should be the Colander class that this adapter adapts.
    """
    def wrapper(fn):
        def inner_wrapper(*args, **kwargs):
            return f(*args, **kwargs)
        _validator_adapters[colander_class] = fn
    return wrapper


def get_adapter(node):
    """
    Return an adapter class for ``node``. Return None if one was not
    found.

    Checks for an adapter registered for the node's ``schema_type``
    field first, then the __class__ of its ``typ`` field.
    """
    adapter = _schema_adapters.get(node.schema_type, None)

    if adapter is None:
        adapter = _schema_adapters.get(node.typ.__class__, None)

    if adapter is None:
        print _schema_adapters.keys()
        raise Invalid(node)

    return adapter


def to_json_schema(schema):
    """
    Return a JSON schema document for the Colander schema *instance* ``schema``.
    """
    adapter_class = get_adapter(schema)
    adapter = adapter_class(schema)
    return adapter.to_json_schema()


class SchemaAdapterMetaclass(type):
    """
    A metaclass used by BaseAdapter that registers the class as a Hammer
    adapter if it defines an ``adapter_for`` class variable.

    The adapter class will be become available as an adapter for the
    ``adapter_for`` class.
    """
    def __new__(mcs, name, bases, dct):
        adapter_for = dct.get('adapter_for', None)
        cls = super(SchemaAdapterMetaclass, mcs).__new__(mcs, name, bases, dct)

        if adapter_for:
            try:
                for target in adapter_for:
                    _schema_adapters[target] = cls
            except TypeError:
                _schema_adapters[adapter_for] = cls

        return cls


class BaseSchemaAdapter(object):
    """
    Base class for JSON schema adapters.
    """
    __metaclass__ = SchemaAdapterMetaclass

    def __init__(self, schema, *args, **kwargs):
        self.schema = schema
        super(BaseSchemaAdapter, self).__init__(*args, **kwargs)

    def to_json_schema(self):
        raise NotImplementedError

    def build_validator_adapters(self, node):
        validators = []
        validator_adapters = {}

        if hasattr(node.validator, '__call__'):
            validators.append(node.validator)

        for validator in validators:
            validator_adapter = _validator_adapters.get(validator.__class__, None)

            if not validator_adapter:
                continue

            validator_adapters.update(validator_adapter(validator))

        return validator_adapters

    def build_json_property(self, node):
        """
        Build a JSON property for ``node``, a :class:`colander.SchemaNode`
        object.
        """
        adapter = get_adapter(node)

        if adapter is Ignore:
            return adapter

        if adapter is None:
            raise Invalid(node)

        try:
            json_property = adapter(node).to_json_schema()
        except (TypeError, AttributeError):
            # Fall-through - if no adapter class was found, just return the
            # JSON type string (e.g., "number".
            json_property = {
                'type': adapter,
            }
            # XXX: Is this how the required field works -- require an array
            # that includes the type of the field?
            if node.required:
                json_property['required'] = [adapter]

        validators = self.build_validator_adapters(node)

        if validators:
            json_property.update(validators)

        return json_property


class MappingAdapter(BaseSchemaAdapter):
    """
    Convert a :class:`colander.MappingSchema` into a JSON object property.
    """
    adapter_for = [colander.Schema, colander.MappingSchema, colander.Mapping]

    def to_json_schema(self):
        json_property = {
            'type': 'object',
            'properties': {}
        }

        for node in self.schema.children:
            json_property['properties'][node.name] = self.build_json_property(
                node)

        return json_property


class SequenceAdapter(BaseSchemaAdapter):
    """
    Convert a :class:`colander.Sequence` into a JSON array property.
    """
    adapter_for = colander.Sequence

    def to_json_schema(self):
        return {
            'type': 'array',
            'items': self.build_json_property(self.schema.children[0])
        }


class SetAdapter(BaseSchemaAdapter):
    """
    Convert a :class:`colander.Set` into a JSON array property of unique items.
    """
    adapter_for = colander.Set

    def to_json_schema(self):
        return {
            'type': 'array',
            'uniqueItems': True
        }


class TupleAdapter(BaseSchemaAdapter):
    """
    Convert a :class:`colander.Tuple` into a fixed-length JSON array property.
    """
    adapter_for = colander.Tuple

    def to_json_schema(self):
        length = len(self.schema.children)
        json_property = {
            'type': 'array',
            'items': [],
            'minItems': length,
            'maxItems': length
        }

        for node in self.schema.children:
            json_property['items'].append(self.build_json_property(node))

        return json_property


class DatetimeAdapter(BaseSchemaAdapter):
    """
    Convert various Colander datetime types into a "string" type with a
    "datetime" format string.
    """
    adapter_for = [colander.DateTime, colander.Date, colander.Time]

    def to_json_schema(self):
        return {
            'type': 'string',
            'format': 'date-time'
        }


class FloatAdapter(BaseSchemaAdapter):
    """
    Convert a numeric SchemaType into a "float."

    There is no actual "float" type in the JSON schema spec, so we have to
    add a constraint that the number cannot be a multiple of 1 (_Source).

    .. _Source: https://groups.google.com/d/msg/json-schema/cmnBFW6fJ9I/mjTOYXspAFMJ
    """
    adapter_for = [colander.Money, colander.Decimal]

    def to_json_schema(self):
        return {
            'type': 'number',
            'not': {
                'multipleOf': 1
            }
        }


@adapts_validator(colander.Regex)
def convert_regex(regex):
    """
    Convert a :class:`colander.Regex` into a "pattern" validator.
    """
    return {
        'pattern': regex.match_object.pattern
    }


@adapts_validator(colander.Email)
def convert_email(email):
    """
    Convert a :class:`colander.Email` into an "email" validator.
    """
    return {
        'format': 'email'
    }


@adapts_validator(colander.Range)
def convert_range(_range):
    """
    Convert a :class:`colander.Range` into "min" and "max" fields.
    """
    fields = {
        'min': _range.min,
    }

    if not _range.max is None:
        fields['max'] = _range.max

    return fields


@adapts_validator(colander.Length)
def convert_length(length):
    """
    Convert a :class:`colander.Range` into "min" and "max" fields.
    """
    return {
        'minLength': length.min,
        'maxLength': length.max
    }


@adapts_validator(colander.OneOf)
def convert_one_of(one_of):
    """
    Convert a :class:`colander.OneOf` into an "enum" field.
    """
    return {
        'enum': one_of.choices
    }


@adapts_validator(colander.url)
def convert_url(url):
    """
    Convert a :class:`colander.url` into a "uri" field.
    """
    return {
        'format': 'uri'
    }
