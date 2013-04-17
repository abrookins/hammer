import colander
import hammer

from jsonschema import Draft4Validator
from unittest import TestCase


class Friend(colander.TupleSchema):
    rank = colander.SchemaNode(colander.Int(),
                              validator=colander.Range(0, 9999))
    name = colander.SchemaNode(colander.String())
    still_friends = colander.SchemaNode(colander.Boolean())


class Phone(colander.MappingSchema):
    location = colander.SchemaNode(colander.String(),
                                   validator=colander.OneOf(['home', 'work']))
    number = colander.SchemaNode(colander.String())


class Friends(colander.SequenceSchema):
    friend = Friend()


class UniqueThings(colander.Schema):
    things = colander.SchemaNode(colander.Set())


class Person(colander.MappingSchema):
    name = colander.SchemaNode(colander.String())
    age = colander.SchemaNode(colander.Int(),
                             validator=colander.Range(0, 200))
    friends = Friends()


class HammerTestCase(TestCase):
    def validate_schema(self, schema):
        return Draft4Validator.check_schema(schema)


class TestTupleSchemaAdapter(HammerTestCase):
    def test_converts_tuple_to_fixed_length_array(self):
        schema = Friend()
        json_schema = hammer.TupleAdapter(schema).to_json_schema()
        self.assertEqual(len(json_schema['items']), 3)
        self.assertEqual(json_schema['maxItems'], 3)
        self.assertEqual(json_schema['minItems'], 3)
        self.assertEqual(json_schema['type'], 'array')
        self.assertEqual(json_schema['items'][0]['type'], 'number')
        self.assertEqual(json_schema['items'][0]['required'], ['number'])
        self.assertEqual(json_schema['items'][1]['type'], 'string')
        self.assertEqual(json_schema['items'][1]['required'], ['string'])
        self.assertEqual(json_schema['items'][2]['type'], 'boolean')
        self.assertEqual(json_schema['items'][2]['required'], ['boolean'])
        self.validate_schema(json_schema)


class TestSequenceAdapter(HammerTestCase):
    def test_converts_sequence_to_array(self):
        schema = Friends()
        json_schema = hammer.SequenceAdapter(schema).to_json_schema()
        self.assertEqual(json_schema['type'], 'array')

        items = json_schema['items']
        self.assertEqual(len(items['items']), 2)
        self.assertEqual(items['type'], 'array')
        self.assertEqual(items['maxItems'], 2)
        self.assertEqual(items['minItems'], 2)
        self.validate_schema(json_schema)


class TestSequenceAdapter(HammerTestCase):
    def test_converts_sequence_to_array(self):
        schema = Friends()
        json_schema = hammer.SequenceAdapter(schema).to_json_schema()
        self.assertEqual(json_schema['type'], 'array')

        items = json_schema['items']
        self.assertEqual(len(items['items']), 3)
        self.assertEqual(items['type'], 'array')
        self.assertEqual(items['maxItems'], 3)
        self.assertEqual(items['minItems'], 3)
        self.validate_schema(json_schema)


class TestMappingAdapter(HammerTestCase):
    def test_converts_mapping_to_json_object(self):
        schema = Phone()
        json_schema = hammer.MappingAdapter(schema).to_json_schema()
        self.assertEqual(json_schema['type'], 'object')
        self.assertEqual(len(json_schema['properties'].values()), 2)

        properties = json_schema['properties']
        self.assertEqual(properties['location']['type'], 'string')
        self.assertEqual(properties['location']['required'], ['string'])
        self.assertEqual(properties['number']['type'], 'string')
        self.assertEqual(properties['number']['required'], ['string'])
        self.validate_schema(json_schema)


class TestSetAdapter(HammerTestCase):
    def test_converts_set_to_unique_items_array(self):
        schema = UniqueThings()
        json_schema = hammer.SetAdapter(schema).to_json_schema()
        self.assertEqual(json_schema['uniqueItems'], True)
        self.assertEqual(json_schema['type'], 'array')
        self.validate_schema(json_schema)


class TestBooleanAdapter(HammerTestCase):
    def test_boolean_converts_to_boolean(self):
        schema = Friends()
        json_schema = hammer.to_json_schema(schema)
        self.assertEqual('boolean', json_schema['items']['items'][2]['type'])
        self.validate_schema(json_schema)


class TestRegexAdapter(HammerTestCase):
    def test_regex_converts_to_pattern(self):
        email_address = r'(?i)^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,4}$'
        regex = colander.Regex(email_address)

        class RegexEmailSchema(colander.Schema):
            address = colander.SchemaNode(colander.String(), validator=regex)

        schema = RegexEmailSchema()
        json_schema = hammer.to_json_schema(schema)

        address_field = json_schema['properties']['address']

        self.assertEqual(address_field['type'], 'string')
        self.assertEqual(address_field['pattern'], email_address)
        self.validate_schema(json_schema)


class TestEmailAdapter(HammerTestCase):
    def test_email_converts_to_format_string(self):
        class EmailSchema(colander.Schema):
            address = colander.SchemaNode(colander.String(),
                                          validator=colander.Email())

        schema = EmailSchema()
        json_schema = hammer.to_json_schema(schema)

        address_field = json_schema['properties']['address']

        self.assertEqual(address_field['type'], 'string')
        self.assertEqual(address_field['format'], 'email')
        self.validate_schema(json_schema)


class TestDatetimeAdapter(HammerTestCase):
    def test_datetime_converts_to_format_string(self):
        class DatetimeSchema(colander.Schema):
            date = colander.SchemaNode(colander.Date())
            date = colander.SchemaNode(colander.Time())
            date = colander.SchemaNode(colander.DateTime())

        schema = DatetimeSchema()
        json_schema = hammer.to_json_schema(schema)

        for field in json_schema['properties'].values():
            self.assertEqual(field['type'], 'string')
            self.assertEqual(field['format'], 'date-time')

        self.validate_schema(json_schema)


class TestRangeAdapter(HammerTestCase):
    def test_range_converts_to_min_and_max_fields(self):
        class RangeSchema(colander.Schema):
            constrained_number = colander.SchemaNode(
                colander.Int(), validator=colander.Range(min=1, max=5))

        schema = RangeSchema()
        json_schema = hammer.to_json_schema(schema)
        field = json_schema['properties']['constrained_number']

        self.assertEqual(field['type'], 'number')
        self.assertEqual(field['min'], 1)
        self.assertEqual(field['max'], 5)

        self.validate_schema(json_schema)

    def test_range_allows_max_as_optional(self):
        class RangeSchema(colander.Schema):
            constrained_number = colander.SchemaNode(
                colander.Int(), validator=colander.Range(min=1))

        schema = RangeSchema()
        json_schema = hammer.to_json_schema(schema)
        field = json_schema['properties']['constrained_number']

        self.assertEqual(field['type'], 'number')
        self.assertEqual(field['min'], 1)

        self.assertTrue('max' not in field)
        self.validate_schema(json_schema)


class TestLengthAdapter(HammerTestCase):
    def test_length_converts_to_minlength_and_maxlength_fields(self):
        class LengthSchema(colander.Schema):
            constrained_text = colander.SchemaNode(
                colander.String(), validator=colander.Length(min=1, max=5))

        schema = LengthSchema()
        json_schema = hammer.to_json_schema(schema)
        field = json_schema['properties']['constrained_text']

        self.assertEqual(field['type'], 'string')
        self.assertEqual(field['minLength'], 1)
        self.assertEqual(field['maxLength'], 5)

        self.validate_schema(json_schema)


class TestOneOfAdapter(HammerTestCase):
    def test_oneOf_converts_to_enum_field(self):
        class OneOfSchema(colander.Schema):
            constrained_number = colander.SchemaNode(
                colander.Int(), validator=colander.OneOf(choices=[1, 2, 3]))

        schema = OneOfSchema()
        json_schema = hammer.to_json_schema(schema)
        field = json_schema['properties']['constrained_number']

        self.assertEqual(field['type'], 'number')
        self.assertEqual(field['enum'], [1, 2, 3])

        self.validate_schema(json_schema)


class TestUrlAdapter(HammerTestCase):
    def test_url_converts_to_pattern(self):
        class UrlSchema(colander.Schema):
            constrained_text = colander.SchemaNode(
                colander.String(), validator=colander.url)

        schema = UrlSchema()
        json_schema = hammer.to_json_schema(schema)
        field = json_schema['properties']['constrained_text']

        self.assertEqual(field['type'], 'string')
        self.assertEqual(field['pattern'],
                         schema.children[0].validator.match_object.pattern)

        self.validate_schema(json_schema)


class TestFloatAdapter(HammerTestCase):
    def test_money_converts_to_float(self):
        class MoneySchema(colander.Schema):
            money = colander.SchemaNode(colander.Money())

        schema = MoneySchema()
        json_schema = hammer.to_json_schema(schema)
        field = json_schema['properties']['money']

        self.assertEqual(field['type'], 'number')
        self.assertEqual(field['not']['multipleOf'], 1)

        self.validate_schema(json_schema)

    def test_decimal_converts_to_float(self):
        class DecimalSchema(colander.Schema):
            number = colander.SchemaNode(colander.Decimal())

        schema = DecimalSchema()
        json_schema = hammer.to_json_schema(schema)
        field = json_schema['properties']['number']

        self.assertEqual(field['type'], 'number')
        self.assertEqual(field['not']['multipleOf'], 1)

        self.validate_schema(json_schema)
