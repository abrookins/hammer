# coding=utf-8
"""
hammer.py: Convert Colander schemas into JSON Schema documents.

To extend, register your Schema and SchemaType adapters by creating a subclass
of :class:`BaseAdapter`. Create a validator adapter by decorating a function
with :function:`adapts_validator`.

TODO: Extensible way to mark a custom Schema, SchemaType or validator as
ignored.
"""
from collections import defaultdict
from functools import wraps
import functools
import colander


SUPPORTED_JSON_DRAFT_VERSIONS = (3, 4)


_adapters = defaultdict(dict)


def adapts(*adaptees, **kwargs):
    """
    A decorator that registers the decorated function as a Hammer adapter for
    a Colander entity.

    ``adaptees`` should be the Colander entity or entities that this adapter
    adapts. This might be a Schema, SchemaType or validator or an iterable of
    such.

    ``draft_version`` may be an integer specifying the JSON Schema draft
    version for which the adapter applies, or an iterable of version numbers. If
    not provided, this value defaults to all supported drafts via
    `SUPPORTED_JSON_DRAFT_VERSIONS`.
    """
    draft_version = kwargs.get('draft_version', SUPPORTED_JSON_DRAFT_VERSIONS)

    # Ensure that ``draft_version`` is iterable.
    try:
        len(draft_version)
    except TypeError:
        draft_version = (draft_version,)

    def wrapper(fn):
        @wraps(fn)
        def inner_wrapper(*args, **kwargs):
            return fn(*args, **kwargs)

        for version in draft_version:
            for key in adaptees:
                _adapters[version][key] = inner_wrapper

        return inner_wrapper
    return wrapper


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


@adapts(colander.Function, colander.All, colander.ContainsOnly,
        colander.luhnok)
class Ignore(object):
    """
    A Colander adaptee that should be ignored.
    """
    pass


def get_schema_adapter(node, draft_version):
    """
    Return an adapter function for the Colander Schema or SchemaType ``node``
    if one exists, else None.

    Checks for an adapter registered for the node's ``schema_type``
    field first, then the __class__ of its ``typ`` field.
    """
    adapters = _adapters.get(draft_version, None)

    if adapters is None:
        return

    adapter = adapters.get(node.schema_type, None)

    if adapter is None:
        adapter = adapters.get(node.typ.__class__, None)

    if adapter is None:
        raise Invalid(node)

    return functools.partial(adapter, draft_version=draft_version)


def get_validator_adapter(validator, draft_version):
    """
    Return an adapter function for the Colander validator class ``validator``
    if one exists, else None.
    """
    adapters = _adapters.get(draft_version, None)

    if adapters is None:
        return

    adapter = adapters.get(validator.__class__, None)

    if adapter is None:
        return

    return functools.partial(adapter, draft_version=draft_version)


def to_json_schema(schema, draft_version=4):
    """
    Return a JSON schema document for the Colander schema *instance* ``schema``.
    """
    if draft_version not in SUPPORTED_JSON_DRAFT_VERSIONS:
        raise ValueError(
            'The following JSON Schema draft versions are supported: '
            '%s' % ', '.join(SUPPORTED_JSON_DRAFT_VERSIONS))

    adapter = get_schema_adapter(schema, draft_version)
    return adapter(schema)


def build_json_validators(node, draft_version):
    """
    Find any validator adapters for the Colander Schema or SchemaType ``node``
    and return a dict that contains the fields all of the adapters generated.
    """
    validators = []
    validator_adapters = {}

    if hasattr(node.validator, '__call__'):
        validators.append(node.validator)

    for validator in validators:
        validator_adapter = get_validator_adapter(validator, draft_version)

        if not validator_adapter:
            continue

        validator_adapters.update(validator_adapter(validator))

    return validator_adapters


def build_json_property(node, draft_version):
    """
    Build a JSON property for ``node``, a :class:`colander.SchemaNode`
    object.
    """
    adapter = get_schema_adapter(node, draft_version)

    if adapter is Ignore:
        return adapter

    if adapter is None:
        raise Invalid(node)

    json_property = adapter(node)
    validators = build_json_validators(node, draft_version)

    if validators:
        json_property.update(validators)

    return json_property


@adapts(colander.Int, colander.Integer)
def adapt_int(schema, draft_version):
    return {
        'type': 'number'
    }


@adapts(colander.String, colander.Str)
def string_adapter(schema, draft_version):
    return {
        'type': 'string'
    }


@adapts(colander.Bool)
def bool_adapter(schema, draft_version):
    return {
        'type': 'boolean'
    }


@adapts(colander.Schema, colander.MappingSchema, colander.Mapping)
def adapt_mapping(schema, draft_version):
    """
    Convert a :class:`colander.MappingSchema` into a JSON object property.
    """
    properties = {}
    required_property_names = []

    for node in schema.children:
        properties[node.name] = build_json_property(node, draft_version)

        if node.required:
            required_property_names.append(node.name)

    return {
        'type': 'object',
        'properties': properties,
        'required': required_property_names
    }


@adapts(colander.Sequence)
def adapt_sequence(schema, draft_version):
    """
    Convert a :class:`colander.Sequence` into a JSON array property.
    """
    # The first node contains the sequence (tuple, etc.) schema type. It
    # contains the schema of the object repeated in the sequence of items.
    sequence_node = schema.children[0]

    json_property = {
        'type': 'array',
        'items': build_json_property(sequence_node, draft_version)
    }

    if sequence_node.required:
        json_property['required'] = [sequence_node.name]

    return json_property


@adapts(colander.Set)
def adapt_set(schema, draft_version):
    """
    Convert a :class:`colander.Set` into a JSON array property of unique items.
    """
    return {
        'type': 'array',
        'uniqueItems': True
    }


@adapts(colander.Tuple)
def adapt_tuple(schema, draft_version):
    """
    Convert a :class:`colander.Tuple` into a fixed-length JSON array property.
    """
    length = len(schema.children)
    properties = []
    required_property_names = []

    for node in schema.children:
        properties.append(build_json_property(node, draft_version))

        if node.required:
            required_property_names.append(node.name)

    return {
        'type': 'array',
        'minItems': length,
        'maxItems': length,
        'required': required_property_names,
        'items': properties
    }


@adapts(colander.DateTime, colander.Date, colander.Time)
def adapt_datetime(schema, draft_version):
    """
    Convert various Colander datetime types into a "string" type with a
    "datetime" format string.
    """
    return {
        'type': 'string',
        'format': 'date-time'
    }


@adapts(colander.Money, colander.Decimal, colander.Float)
def adapt_float(schema, draft_version):
    """
    Convert a numeric SchemaType into a "float."

    There is no actual "float" type in the JSON schema spec, so we have to
    add a constraint that the number cannot be a multiple of 1 (_Source).

    .. _Source: https://groups.google.com/d/msg/json-schema/cmnBFW6fJ9I/mjTOYXspAFMJ
    """
    return {
        'type': 'number',
        'not': {
            'multipleOf': 1
        }
    }


@adapts(colander.Regex)
def convert_regex(regex, draft_version):
    """
    Convert a :class:`colander.Regex` into a "pattern" validator.
    """
    return {
        'pattern': regex.match_object.pattern
    }


@adapts(colander.Email)
def convert_email(email, draft_version):
    """
    Convert a :class:`colander.Email` into an "email" validator.
    """
    return {
        'format': 'email'
    }


@adapts(colander.Range)
def convert_range(_range, draft_version):
    """
    Convert a :class:`colander.Range` into "min" and "max" fields.
    """
    fields = {
        'min': _range.min,
    }

    if not _range.max is None:
        fields['max'] = _range.max

    return fields


@adapts(colander.Length)
def convert_length(length, draft_version):
    """
    Convert a :class:`colander.Range` into "min" and "max" fields.
    """
    return {
        'minLength': length.min,
        'maxLength': length.max
    }


@adapts(colander.OneOf)
def convert_one_of(one_of, draft_version):
    """
    Convert a :class:`colander.OneOf` into an "enum" field.
    """
    return {
        'enum': one_of.choices
    }
