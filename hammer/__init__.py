# coding=utf-8
"""
hammer.py: Convert Colander schemas into JSON Schema documents (draft 3 or 4).

To extend, register your Schema, SchemaType and validator adapters by decorating
a callable with :function:`adapts`.

To ignore a type or validator, define a callable that returns :class:`Ignore`
and decorate it with :function:`adapts`. E.g.:

    @adapts(colander.Length)
    def ignore_length(*args, **kwargs):
        return Ignore
"""
from collections import defaultdict
from functools import wraps
import functools
import colander


SUPPORTED_JSON_DRAFT_VERSIONS = (3, 4)


def make_iterable(obj, iter_type):
    """
    Wrap ``obj`` in an iterable identified by ``iter_type``.

    ``iter_type`` may be tuple, list or set.
    """
    try:
        len(obj)
    except TypeError:
        if iter_type is tuple:
            obj = obj,
        elif iter_type is list:
            obj = [obj]
        elif iter_type is set:
            obj = {obj}
        else:
            raise ValueError('iter_cls must be tuple, list or set')
    return obj


make_tuple = functools.partial(make_iterable, iter_type=tuple)


_adapters = defaultdict(dict)


def register_adapter(adaptees, adapter, draft_version=None):
    """
    Register the callable ``adapter`` as an adapter for the Colander entity
    ``adaptee`` for JSON Schema draft version ``draft_version``.
    """
    draft_version = draft_version or SUPPORTED_JSON_DRAFT_VERSIONS
    draft_version = make_tuple(draft_version)
    adaptees = make_tuple(adaptees)

    for version in draft_version:
        for adaptee in adaptees:
            _adapters[version][adaptee] = adapter


def adapts(*adaptees, **kwargs):
    """
    A decorator that registers the decorated function as a Hammer adapter for
    a Colander entity.

    ``adaptees`` should be the Colander entity or entities that this adapter
    adapts. This might be a Schema, SchemaType or validator.

    ``draft_version`` may be an integer specifying the JSON Schema draft
    version for which the adapter applies, or an iterable of version numbers. If
    not provided, this value defaults to all supported drafts via
    `SUPPORTED_JSON_DRAFT_VERSIONS`.
    """
    draft_version = kwargs.get('draft_version')

    def wrapper(fn):
        @wraps(fn)
        def inner_wrapper(*args, **kwargs):
            return fn(*args, **kwargs)

        register_adapter(adaptees, inner_wrapper, draft_version)

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


class Ignore(object):
    """
    A Colander adaptee that should be ignored.
    """
    pass


def get_schema_adapter(node, **kwargs):
    """
    Return an adapter function for the Colander Schema or SchemaType ``node``
    if one exists, else None.

    Checks for an adapter registered for the node's ``schema_type``
    field first, then the __class__ of its ``typ`` field.

    Keyword arguments:
        ``draft_version`` is the JSON Schema draft version the adapter should
            target
    """
    draft_version = kwargs['draft_version']
    adapters = _adapters.get(draft_version, None)

    if adapters is None:
        return

    adapter = adapters.get(node.schema_type, None)

    if adapter is None:
        adapter = adapters.get(node.typ.__class__, None)

    if adapter is None:
        raise Invalid(node)

    return functools.partial(adapter, **kwargs)


def get_validator_adapter(validator, **kwargs):
    """
    Return an adapter function for the Colander validator class ``validator``
    if one exists, else None.

    Keyword arguments:
        ``draft_version`` is the JSON Schema draft version the adapter should
            target
    """
    draft_version = kwargs['draft_version']
    adapters = _adapters.get(draft_version, None)

    if adapters is None:
        return

    adapter = adapters.get(validator.__class__, None)

    if adapter is None:
        adapter = adapters.get(validator, None)

    if adapter is None:
        return

    return functools.partial(adapter, **kwargs)


def to_json_schema(schema, draft_version=4, include_types=True):
    """
    Return a JSON schema document for the Colander schema *instance* ``schema``.
    """
    if draft_version not in SUPPORTED_JSON_DRAFT_VERSIONS:
        raise ValueError(
            'The following JSON Schema draft versions are supported: '
            '%s' % ', '.join(SUPPORTED_JSON_DRAFT_VERSIONS))

    adapter = get_schema_adapter(schema, draft_version=draft_version,
                                 include_types=include_types)
    return adapter(schema)


def build_json_validators(node, **kwargs):
    """
    Find any validator adapters for the Colander Schema or SchemaType ``node``
    and return a dict that contains the fields all of the adapters generated.
    """
    validators = []
    validator_adapters = {}

    if hasattr(node.validator, '__call__'):
        validators.append(node.validator)

    for validator in validators:
        validator_adapter = get_validator_adapter(validator, **kwargs)

        if not validator_adapter:
            continue

        json_validator = validator_adapter(validator)

        if json_validator is Ignore:
            continue

        validator_adapters.update(json_validator)

    return validator_adapters


def build_json_property(node, **kwargs):
    """
    Build a JSON property for ``node``, a :class:`colander.SchemaNode`
    object.

    Keyword arguments:
        ``draft_version`` is the JSON Schema draft version to target
        ``include_types`` is a boolean signifying whether or not the JSON
            property should include type information
    """
    adapter = get_schema_adapter(node, **kwargs)
    draft_version = kwargs['draft_version']
    include_types = kwargs['include_types']

    if adapter is None:
        raise Invalid(node)

    json_property = adapter(node)

    if json_property is Ignore:
        return Ignore

    if node.required and draft_version == 3:
        json_property['required'] = True

    if node.missing is colander.drop:
        json_property['optional'] = True

    if include_types is False:
        del json_property['type']

    validators = build_json_validators(node, **kwargs)

    if validators:
        json_property.update(validators)

    return json_property


@adapts(colander.Int, colander.Integer)
def adapt_int(schema, **kwargs):
    return {
        'type': 'number'
    }


@adapts(colander.String, colander.Str)
def adapt_string(schema, **kwargs):
    return {
        'type': 'string',
        'format': 'alphanumeric'
    }


@adapts(colander.Bool)
def adapt_bool(schema, **kwargs):
    return {
        'type': 'boolean'
    }


@adapts(colander.Schema, colander.MappingSchema, colander.Mapping)
def adapt_mapping(schema, **kwargs):
    """
    Convert a :class:`colander.MappingSchema` into a JSON object property.
    """
    properties = {}
    required_property_names = []
    draft_version = kwargs['draft_version']

    for node in schema.children:
        json_property = build_json_property(node, **kwargs)

        if json_property is Ignore:
            continue

        properties[node.name] = json_property

        if node.required and draft_version == 4:
            required_property_names.append(node.name)

    json_property = {
        'type': 'object',
        'properties': properties,
    }

    if required_property_names:
        json_property['required'] = required_property_names

    return json_property


@adapts(colander.Sequence)
def adapt_sequence(schema, **kwargs):
    """
    Convert a :class:`colander.Sequence` into a JSON array property.
    """
    # The first node contains the sequence (tuple, etc.) schema type. It
    # contains the schema of the object repeated in the sequence of items.
    sequence_node = schema.children[0]
    draft_version = kwargs['draft_version']

    json_property = {
        'type': 'array',
    }

    # The "items" field is a JSON schema that items of the sequence will be
    # validated against.
    items = build_json_property(sequence_node, **kwargs)

    if items is not Ignore:
        json_property['items'] = items

    if sequence_node.required and draft_version == 4:
        json_property['required'] = [sequence_node.name]

    return json_property


@adapts(colander.Set)
def adapt_set(schema, **kwargs):
    """
    Convert a :class:`colander.Set` into a JSON array property of unique items.
    """
    return {
        'type': 'array',
        'uniqueItems': True
    }


@adapts(colander.Tuple)
def adapt_tuple(schema, **kwargs):
    """
    Convert a :class:`colander.Tuple` into a fixed-length JSON array property.
    """
    draft_version = kwargs['draft_version']
    length = len(schema.children)
    properties = []
    required_property_names = []

    for node in schema.children:
        json_property = build_json_property(node, **kwargs)

        if json_property is Ignore:
            continue

        properties.append(json_property)

        if node.required and draft_version == 4:
            required_property_names.append(node.name)

    json_property = {
        'type': 'array',
        'minItems': length,
        'maxItems': length,
        'items': properties
    }

    if required_property_names:
        json_property['required'] = required_property_names

    return json_property


@adapts(colander.DateTime, colander.Date, colander.Time)
def adapt_datetime(schema, **kwargs):
    """
    Convert various Colander datetime types into a "string" type with a
    "datetime" format string.
    """
    return {
        'type': 'string',
        'format': 'date-time'
    }


@adapts(colander.Money, colander.Decimal, colander.Float)
def adapt_float(schema, **kwargs):
    """
    Convert a numeric SchemaType into a "float."

    There is no actual "float" type in the JSON schema spec, so we have to
    add a constraint that the number cannot be a multiple of 1 (_Source).

    .. _Source: https://groups.google.com/d/msg/json-schema/cmnBFW6fJ9I/mjTOYXspAFMJ
    """
    draft_version = kwargs['draft_version']
    json_property = {
        'type': 'number',
    }

    if draft_version == 3:
        json_property['not'] = {
            'divisibleBy': 1
        }
    elif draft_version == 4:
        json_property['not'] = {
            'multipleOf': 1
        }

    return json_property


@adapts(colander.Regex)
def adapt_regex(regex, **kwargs):
    """
    Convert a :class:`colander.Regex` into a "pattern" validator.
    """
    return {
        'pattern': regex.match_object.pattern
    }


@adapts(colander.Email)
def adapt_email(email, **kwargs):
    """
    Convert a :class:`colander.Email` into an "email" validator.
    """
    return {
        'format': 'email'
    }


@adapts(colander.Range)
def adapt_range(_range, **kwargs):
    """
    Convert a :class:`colander.Range` into "min" and "max" fields.
    """
    fields = {
        'minimum': _range.min,
    }

    if not _range.max is None:
        fields['maximum'] = _range.max

    return fields


@adapts(colander.Length)
def convert_length(length, **kwargs):
    """
    Convert a :class:`colander.Range` into "min" and "max" fields.
    """
    return {
        'minLength': length.min,
        'maxLength': length.max
    }


@adapts(colander.OneOf)
def adapt_one_of(one_of, **kwargs):
    """
    Convert a :class:`colander.OneOf` into an "enum" field.
    """
    return {
        'enum': one_of.choices
    }



# Ignored validators
@adapts(colander.Function, colander.All, colander.ContainsOnly, colander.luhnok)
def ignore(*args, **kwargs):
    return Ignore