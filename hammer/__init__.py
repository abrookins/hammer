"""
hammer.py: Convert Colander schemas into JSON Schema documents.
"""
import colander


class Invalid(Exception):
    """
    Raised when a Colander node is encountered that cannot be converted to
    a JSON schema type.
    """
    pass


class Ignore(Exception):
    """
    A Colander type that should be ignored. E.g., :class:`colander.Function`.
    """
    pass


class BaseAdapter(object):
    """
    Base class for JSON schema adapters.
    """
    def __init__(self, schema, *args, **kwargs):
        self.schema = schema
        super(BaseAdapter, self).__init__(*args, **kwargs)

    def to_json_schema(self):
        raise NotImplementedError

    def build_json_property(self, node):
        """
        Build a JSON property for ``node``, a :class:`colander.SchemaNode`
        object.
        """
        adapter = _adapters.get(node.schema_type, None)

        # XXX: Should these be separate dicts? E.g. Schema versus SchemaType.
        if not adapter:
            adapter = _adapters.get(node.typ.__class__, None)

        if not adapter:
            raise Invalid

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

        validators = []

        if hasattr(node.validator, '__call__'):
            validators.append(node.validator)

        for validator in validators:
            validator_adapter = _adapters.get(validator.__class__, None)

            if not validator_adapter:
                continue

            json_property.update(validator_adapter(validator))

        return json_property


class MappingAdapter(BaseAdapter):
    """
    Convert a :class:`colander.MappingSchema` into a JSON object property.
    """
    def to_json_schema(self):
        json_property = {
            'type': 'object',
            'properties': {}
        }

        for node in self.schema.children:
            json_property['properties'][node.name] = self.build_json_property(
                node)

        return json_property


class SequenceAdapter(BaseAdapter):
    """
    Convert a :class:`colander.Sequence` into a JSON array property.
    """
    def to_json_schema(self):
        return {
            'type': 'array',
            'items': self.build_json_property(self.schema.children[0])
        }


class SetAdapter(BaseAdapter):
    """
    Convert a :class:`colander.Set` into a JSON array property of unique items.
    """
    def to_json_schema(self):
        return {
            'type': 'array',
            'uniqueItems': True
        }


class TupleAdapter(BaseAdapter):
    """
    Convert a :class:`colander.Tuple` into a fixed-length JSON array property.
    """
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


class DatetimeAdapter(BaseAdapter):
    """
    Convert various Colander datetime types into a "string" type with a
    "datetime" format string.
    """
    def to_json_schema(self):
        return {
            'type': 'string',
            'format': 'date-time'
        }


def convert_regex(regex):
    """
    Convert a :class:`colander.Regex` into a "pattern" validator.
    """
    return {
        'pattern': regex.match_object.pattern
    }


def convert_email(email):
    """
    Convert a :class:`colander.Email` into an "email" validator.
    """
    return {
        'format': 'email'
    }


def convert_range(_range):
    """
    Convert a :class:`colander.Range` into "min" and "max" fields.
    """
    fields = {
        'min': _range.min,
    }

    if not _range.max is None:
        fields['max']  = _range.max

    return fields


def convert_length(length):
    """
    Convert a :class:`colander.Range` into "min" and "max" fields.
    """
    return {
        'minLength': length.min,
        'maxLength': length.max
    }


_adapters = {
    # SchemaTypes (non-container types)
    colander.Int: 'number',
    colander.Integer: 'number',
    colander.Float: 'number',
    colander.String: 'string',
    colander.Str: 'string',
    colander.Bool: 'boolean',
    colander.Date: DatetimeAdapter,
    colander.DateTime: DatetimeAdapter,
    colander.Time: DatetimeAdapter,

    # Numeric types that may require special formatting.
    colander.Decimal: 'number',
    colander.Money: 'number',

    # Schemas (container types)
    colander.Schema: MappingAdapter,
    colander.MappingSchema: MappingAdapter,
    colander.Mapping: MappingAdapter,
    colander.Sequence: SequenceAdapter,
    colander.Tuple: TupleAdapter,

    # Validators
    colander.Regex: convert_regex,
    colander.Email: convert_email,
    colander.Range: convert_range,
    colander.Length: convert_length
}


def get_adapter(schema):
    schema_type = schema.typ.__class__
    adapter = _adapters.get(schema_type, None)

    if not adapter:
        raise Invalid('Adapter not found for schema type: %s' % schema_type)

    return adapter


def to_json_schema(schema):
    return get_adapter(schema)(schema).to_json_schema()


